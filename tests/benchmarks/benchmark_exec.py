#!/usr/bin/env python3
"""Bounded REAL installed Codex/public exec benchmark with an owned FAKE model."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from mock_responses_provider import MockResponsesProvider

ROOT = Path(__file__).resolve().parents[2]
EXEC = ROOT / 'skills/agent/scripts/exec.py'
TERMINAL = {'completed', 'failed', 'cancelled', 'needs-human-decision'}


def read_json(path):
    return json.loads(path.read_text())


def tool_named(tools, name, namespace=None):
    for tool in tools:
        if tool.get('type') == 'namespace':
            child = tool_named(tool.get('tools', []), name, tool['name'])
            if child:
                return child
        function = tool.get('function', tool)
        if function.get('name', '').split('.')[-1] == name:
            return {'name': function['name'], 'namespace': namespace,
                    'parameters': function.get('parameters', {})}
    return None


class ExecProvider(MockResponsesProvider):
    """Have the real host execute one local write tool, then emit its final JSON."""

    def __init__(self, project, runtime_home):
        super().__init__('unused')
        self.project = project
        self.runtime_home = runtime_home
        self.agent = None
        self.calls = []
        self.writes_sent = set()
        self.finals = 0
        self.failure = None
        self.diagnostics = []

    def fail(self, message, n, result_path='unused'):
        # A deterministic fixture failure must not become a retryable HTTP 500.
        self.failure = self.failure or message
        return self.message(n, 'failed', result_path)

    @staticmethod
    def message(n, status, result_path):
        return {'id': f'msg_{n}', 'type': 'message', 'role': 'assistant', 'status': 'completed',
                'phase': 'final_answer', 'content': [{'type': 'output_text', 'annotations': [],
                    'text': json.dumps({'status': status, 'resultPath': result_path})}]}

    def output(self, request, n):
        try:
            return self.respond(request, n)
        except Exception as error:
            return self.fail(f'fixture response error: {type(error).__name__}: {error}', n)

    def respond(self, request, n):
        # Preserve only bounded contract/response evidence, not the full prompt history.
        outputs = [item for item in request.get('input', []) if isinstance(item, dict)
                   and item.get('type') in ('function_call_output', 'custom_tool_call_output')]
        self.diagnostics.append({'sequence': n,
                                 'toolResponses': json.dumps(outputs[-4:])[:8000]})
        if self.failure:
            return self.message(n, 'failed', 'unused')
        if request.get('model') != 'fixture-model':
            return self.fail('refusing unexpected model identity', n)
        paths = list(self.runtime_home.glob(f'projects/*/agents/{self.agent}/runs/*/state.json'))
        states = [read_json(path) for path in paths]
        active = [state for state in states if state['status'] not in TERMINAL]
        if len(active) != 1:
            return self.fail('expected exactly one owned active run', n)
        state = active[0]
        self.calls.append({'at': time.monotonic(), 'runId': state['runId'], 'sequence': n})
        result = Path(state['resultPath'])
        if not result.is_relative_to(self.runtime_home) or not Path(state["receiptPath"]).is_relative_to(self.runtime_home):
            return self.fail('fixture result escaped private runtime home', n)
        if state['runId'] not in self.writes_sent:
            tool = tool_named(request.get('tools', []), 'exec_command')
            self.diagnostics[-1]['advertisedTool'] = json.dumps(tool)[:8000]
            if tool is None:
                return self.fail('installed host did not advertise exec_command', n, str(result))
            receipt = {'schemaVersion': '0.1.0', 'kind': 'work-receipt',
                       'runId': state['runId'], 'requestHash': state['receiptRequestHash'],
                       'outcome': 'implemented', 'changedPaths': [], 'addressedFindingIds': [],
                       'tests': {'run': False, 'reason': 'work-agent-prohibited'}}
            script = ('from pathlib import Path; '
                      f'Path({str(result)!r}).write_text("Owned fake-model performance fixture completed.\\n"); '
                      f'Path({state["receiptPath"]!r}).write_text({json.dumps(receipt)!r})')
            properties = tool['parameters'].get('properties', {})
            offered = {'cmd': 'python3 -c ' + shlex.quote(script), 'workdir': str(self.project),
                       'shell': '/bin/sh', 'login': False, 'yield_time_ms': 10000,
                       'max_output_tokens': 2000}
            arguments = {key: value for key, value in offered.items() if key in properties}
            missing = set(tool['parameters'].get('required', [])) - arguments.keys()
            if 'cmd' not in arguments or missing:
                return self.fail(f'unsupported exec_command parameters: missing {sorted(missing)}',
                                 n, str(result))
            self.writes_sent.add(state['runId'])
            call = {'id': f'fc_{n}', 'type': 'function_call', 'call_id': f'call_write_{n}',
                    'name': tool['name'], 'arguments': json.dumps(arguments), 'status': 'completed'}
            # Responses carries namespace separately. A dotted synthetic name is
            # not the function name advertised inside a namespace tool.
            if tool['namespace'] is not None:
                call['namespace'] = tool['namespace']
            self.diagnostics[-1]['emittedCall'] = call
            return call
        if not result.is_file() or not Path(state['receiptPath']).is_file():
            return self.fail('real host write tool did not create result and receipt; '
                             'see provider.diagnostics toolResponses', n, str(result))
        self.finals += 1
        return self.message(n, 'completed', str(result))


def isolated_env(home):
    # Allowlist rather than an incomplete list of provider-specific credential names.
    names = ('PATH', 'LANG', 'LC_ALL', 'TZ', 'USER', 'LOGNAME',
             'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS', 'SYSTEMD_EXEC_PID')
    env = {key: os.environ[key] for key in names if key in os.environ}
    env.update({'HOME': str(home), 'CODEX_HOME': str(home), 'XDG_CONFIG_HOME': str(home / 'config'),
                'XDG_CACHE_HOME': str(home / 'cache'), 'TMPDIR': str(home / 'tmp'),
                'AGENT_FACTORY_HOME': str(home / '.agent-factory'),
                'AF_LOCAL_DUMMY_TOKEN': 'dummy-local-only', 'NO_PROXY': '127.0.0.1,localhost'})
    return env


def summary(rows):
    result = {}
    for kind in ('initial', 'resumed'):
        selected = [row for row in rows if row['kind'] == kind and row.get('completed')]
        metrics = {}
        for key in ('acceptanceSeconds', 'workerObservedSeconds', 'threadObservedSeconds',
                    'firstProviderSeconds', 'firstAssistantObservedSeconds',
                    'terminalObservedSeconds', 'resultCommandSeconds', 'statusCommandSeconds'):
            values = [row[key] for row in selected if row.get(key) is not None]
            metrics[key] = ({'n': len(values), 'median': statistics.median(values),
                             'min': min(values), 'max': max(values)} if values else None)
        result[kind] = metrics
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exec-path', type=Path, default=EXEC)
    parser.add_argument('--sandbox', choices=('workspace-write', 'danger-full-access'), default='workspace-write')
    parser.add_argument('--codex', default=shutil.which('codex'))
    parser.add_argument('--iterations', type=int, default=3, choices=range(3, 5))
    parser.add_argument('--timeout', type=float, default=90)
    parser.add_argument('--poll-interval', type=float, default=.1)
    args = parser.parse_args()
    exec_path = args.exec_path.resolve(strict=True)
    if not 40 <= args.timeout <= 90 or not .02 <= args.poll_interval <= 1:
        parser.error('timeout must be 40..90 seconds; poll interval must be .02..1 seconds')
    output = args.output.absolute()
    # Never overwrite an existing measurement or follow a caller-supplied final symlink.
    with output.open('x') as stream:
        stream.write('{}\n')
    start = time.monotonic()
    deadline = start + args.timeout - 25
    evidence = {'label': 'REAL installed Codex / selected public exec.py / FAKE loopback Responses',
                'ok': False, 'runs': [], 'commands': [], 'cleanup': [],
                'pollIntervalSeconds': args.poll_interval, 'timeoutSeconds': args.timeout,
                'environment': {'platform': platform.platform(), 'python': sys.version,
                    'execPath': str(exec_path), 'execSha256': hashlib.sha256(exec_path.read_bytes()).hexdigest(),
                    'nativeSha256': hashlib.sha256((exec_path.parent.parent / 'runtime/native_codex.py').read_bytes()).hexdigest()},
                'isolation': {'privateCodexHome': True, 'environmentPolicy': 'allowlist',
                    'sandbox': args.sandbox, 'externalProviderCalls': None,
                    'externalProviderCallsBasis': 'No network packet audit; provider selection is configured and fixture requests are counted.'}}
    directory = Path(tempfile.mkdtemp(prefix='af-exec-perf-'))
    home, project = directory / 'home', directory / 'project'
    home.mkdir(mode=0o700)
    (home / 'tmp').mkdir()
    project.mkdir()
    env = isolated_env(home)
    runtime_home = home / '.agent-factory'
    provider = ExecProvider(project, runtime_home)
    runtime = None
    command_identities = []

    def command(arguments, *, json_output=True):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('shared measurement budget exhausted (25 seconds reserved for cleanup)')
        began = time.monotonic()
        process = subprocess.Popen(arguments, cwd=project, env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        if runtime is not None:
            command_identities.append(runtime.linux_process_identity(process.pid))
        try:
            stdout, stderr = process.communicate(timeout=remaining)
        except BaseException:
            # This exact Popen child owns its private group; no name-based process search.
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=1)
            raise
        elapsed = time.monotonic() - began
        record = {'argv': arguments, 'seconds': elapsed, 'returncode': process.returncode,
                  'stdout': stdout[-16000:], 'stderr': stderr[-8000:]}
        evidence['commands'].append(record)
        if process.returncode:
            raise RuntimeError(f'command failed: {json.dumps(record)}')
        return (json.loads(stdout) if json_output else stdout.strip()), elapsed

    def public(verb, *arguments):
        return command([sys.executable, str(exec_path), verb, '--project-root', str(project), *arguments])

    def interrupted(signum, frame):
        raise InterruptedError(f'received signal {signum}')

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        if sys.platform != 'linux':
            raise RuntimeError('Linux identity/containment and child reaping are required')
        if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
            raise OSError('cannot become an owned-child subreaper')
        spec = importlib.util.spec_from_file_location('benchmark_exec_runtime', exec_path)
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        codex = shutil.which(args.codex or '')
        if not codex:
            raise RuntimeError('installed Codex executable not found')
        evidence['environment']['codexPath'] = codex
        evidence['environment']['codexResolvedPath'] = str(Path(codex).resolve())
        evidence['environment']['codexSha256'] = hashlib.sha256(Path(codex).read_bytes()).hexdigest()
        # No inherited config, auth, plugins, proxies, provider URLs or shell startup files.
        with provider:
            (home / 'config.toml').write_text(
                'model = "fixture-model"\nmodel_provider = "fixture"\napproval_policy = "never"\n'
                f'sandbox_mode = {json.dumps(args.sandbox)}\n[features]\nenable_request_compression = false\n'
                '[model_providers.fixture]\nname = "Owned local fixture"\nbase_url = '
                + json.dumps(provider.base_url) + '\nwire_api = "responses"\nrequires_openai_auth = false\n'
                'supports_websockets = false\nenv_key = "AF_LOCAL_DUMMY_TOKEN"\n')
            evidence['isolation']['providerUrl'] = provider.base_url
            command(['git', 'init', '--quiet', str(project)], json_output=False)
            evidence['environment']['codexVersion'], _ = command([codex, '--version'], json_output=False)
            caps, cost = public('capabilities', '--codex', codex)
            evidence['capabilities'] = {'seconds': cost, 'response': caps, 'includedInTurnLatency': False}
            evidence['capabilitySamples'] = [cost]
            for _ in range(2):
                _, cost = public('capabilities', '--codex', codex)
                evidence['capabilitySamples'].append(cost)
            for iteration in range(args.iterations):
                agent = f'perf-{iteration}'
                session_id = None
                for kind in ('initial', 'resumed'):
                    provider.agent = agent
                    began = time.monotonic()
                    row = {'iteration': iteration, 'kind': kind, 'agent': agent,
                           'completed': False, 'statusPollCount': 0, 'statusCommandSeconds': 0,
                           'workerObservedSeconds': None, 'threadObservedSeconds': None,
                           'firstAssistantObservedSeconds': None}
                    evidence['runs'].append(row)
                    options = ['--agent', agent, '--message', 'Complete the owned local performance fixture.']
                    if kind == 'initial':
                        options += ['--role', 'work', '--codex', codex, '--model', 'fixture-model',
                                    '--sandbox', args.sandbox, '--max-attempts', '1',
                                    '--start-timeout', '15', '--turn-timeout', '20']
                    ack, elapsed = public('submit' if kind == 'initial' else 'send', *options)
                    row.update({'runId': ack['runId'], 'acceptanceSeconds': elapsed})
                    while True:
                        status, cost = public('status', '--agent', agent, '--run-id', ack['runId'])
                        observed = time.monotonic() - began
                        row['statusPollCount'] += 1
                        row['statusCommandSeconds'] += cost
                        state = status['run']
                        row['state'] = state
                        if state.get('workerIdentity') and row['workerObservedSeconds'] is None:
                            row['workerObservedSeconds'] = observed
                        events_path = Path(state['eventsPath'])
                        events = []
                        if events_path.exists():
                            for line in events_path.read_text().splitlines():
                                try:
                                    events.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass  # A concurrent append can leave the final line incomplete.
                        if any(event.get('type') == 'thread.started' for event in events):
                            if row['threadObservedSeconds'] is None:
                                row['threadObservedSeconds'] = observed
                        assistants = [event for event in events if event.get('type') == 'item.completed'
                                      and event.get('item', {}).get('type') == 'agent_message']
                        if assistants and row['firstAssistantObservedSeconds'] is None:
                            row['firstAssistantObservedSeconds'] = observed
                        if provider.failure:
                            row['events'] = events
                            raise RuntimeError(provider.failure)
                        if state['status'] in TERMINAL:
                            row['terminalObservedSeconds'] = time.monotonic() - began
                            row['events'] = events
                            row['assistantEventCount'] = len(assistants)
                            row['turnCompletedEventCount'] = sum(event.get('type') == 'turn.completed' for event in events)
                            result, cost = public('result', '--agent', agent, '--run-id', ack['runId'])
                            row['resultCommandSeconds'] = cost
                            row['result'] = result
                            calls = [call for call in provider.calls if call['runId'] == ack['runId']]
                            row['providerRequestCount'] = len(calls)
                            row['providerRequestSeconds'] = [call['at'] - began for call in calls]
                            row['firstProviderSeconds'] = row['providerRequestSeconds'][0] if calls else None
                            if state['status'] != 'completed':
                                stderr = Path(ack['statePath']).parent / 'stderr.log'
                                row['workerStderr'] = stderr.read_text()[-12000:] if stderr.exists() else None
                                raise RuntimeError(f'public {kind} failed: {state.get("error")}')
                            expected = {'status': 'completed', 'resultPath': state['resultPath']}
                            if not assistants or json.loads(assistants[-1]['item']['text']) != expected:
                                raise RuntimeError('missing exact completed assistant output')
                            if len(calls) != 2 or row['turnCompletedEventCount'] != 1:
                                raise RuntimeError('unexpected provider request / completed turn counts')
                            if kind == 'resumed' and state['sessionId'] != session_id:
                                raise RuntimeError('resumed turn did not preserve exact session')
                            session_id = state['sessionId']
                            row['completed'] = True
                            break
                        time.sleep(min(args.poll_interval, max(0, deadline - time.monotonic())))
            if provider.errors or provider.finals != args.iterations * 2:
                raise RuntimeError('fixture completion counts/errors disagree')
            evidence['ok'] = True
    except BaseException as error:
        evidence['failure'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        # Runtime helpers retain boot/start-tick and containment binding checks.
        # Keep private state if cleanup cannot prove emptiness; never scan other projects.
        cleanup_ok = True
        cleanup_deadline = start + args.timeout
        if runtime is not None:
            for identity in command_identities:
                try:
                    runtime.terminate_verified_group(identity)
                except BaseException as error:
                    cleanup_ok = False
                    evidence['cleanup'].append({'commandIdentity': identity, 'error': str(error)})
            for path in runtime_home.glob('projects/*/agents/*/runs/*/state.json'):
                try:
                    state = read_json(path)
                    runtime.runtime_paths.bind(state['runtimeBinding'])
                    containment = state.get('containment')
                    for field in ('codexIdentity', 'lastCodexIdentity'):
                        identity = state.get(field)
                        if identity:
                            runtime.terminate_verified_group(identity)
                    if containment:
                        bound = runtime._validate_state_containment(state)
                        if not runtime.containment_is_empty(bound):
                            runtime.request_containment_stop(bound)
                            # Reap adopted owned workers before checking group emptiness.
                            while time.monotonic() < cleanup_deadline:
                                while True:
                                    try:
                                        pid, _ = os.waitpid(-1, os.WNOHANG)
                                    except ChildProcessError:
                                        break
                                    if pid == 0:
                                        break
                                if runtime.containment_is_empty(bound):
                                    break
                                runtime.force_containment_stop(bound)
                                time.sleep(.05)
                            if not runtime.containment_is_empty(bound):
                                raise RuntimeError('owned containment still populated')
                    elif state.get('workerIdentity') or state.get('codexIdentity'):
                        raise RuntimeError('unbound process identity; refusing unsafe cleanup')
                    evidence['cleanup'].append({'runId': state['runId'], 'empty': True})
                except BaseException as error:
                    cleanup_ok = False
                    evidence['cleanup'].append({'statePath': str(path), 'error': str(error)})
        try:
            while True:
                pid, _ = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    cleanup_ok = False
                    evidence['cleanup'].append({'error': 'owned child remains alive'})
                    break
        except ChildProcessError:
            pass
        evidence['provider'] = {'requests': len(provider.requests), 'finals': provider.finals,
                                'tokensReported': provider.total_tokens, 'errors': provider.errors,
                                'failure': provider.failure, 'diagnostics': provider.diagnostics}
        evidence['summary'] = summary(evidence['runs'])
        evidence['ok'] = evidence['ok'] and cleanup_ok
        evidence['cleanupComplete'] = cleanup_ok
        if cleanup_ok:
            shutil.rmtree(directory)
        else:
            evidence['retainedPrivateDirectory'] = str(directory)
        evidence['elapsedSeconds'] = time.monotonic() - start
        output.write_text(json.dumps(evidence, indent=2) + '\n')
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print(json.dumps({'ok': evidence['ok'], 'output': str(output),
                      'completedTurns': sum(row['completed'] for row in evidence['runs']),
                      'terminalSeconds': {kind: values['terminalObservedSeconds']
                                          for kind, values in evidence['summary'].items()},
                      'failure': evidence.get('failure')}, separators=(',', ':')))
    return 0 if evidence['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
