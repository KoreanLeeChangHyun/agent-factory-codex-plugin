"""Owned loopback Responses fixture. Test-only; never uses production credentials."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class MockResponsesProvider:
    def __init__(self, result_path):
        self.result_path = result_path
        self.requests = []
        self.errors = []
        self.mode = 'complete'
        self.goal_tool_sent = False
        self.sequence = 0
        self.total_tokens = 0
        self.lock = threading.Lock()
        self.release_response = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not self.path.endswith('/responses') or length > 8 * 1024 * 1024:
                        raise ValueError('unexpected route or oversized request')
                    request = json.loads(self.rfile.read(length))
                    with owner.lock:
                        owner.requests.append(request)
                        if len(owner.requests) > 16:
                            raise ValueError('mock provider request cap exceeded')
                        owner.sequence += 1
                        n = owner.sequence
                        output = owner.output(request, n)
                        owner.total_tokens += 110
                    if owner.mode == 'hold' and n >= 2:
                        owner.release_response.wait(timeout=5)
                    response_id = f'resp_fixture_{n}'
                    usage = {'input_tokens': 100, 'output_tokens': 10, 'total_tokens': 110,
                             'input_tokens_details': {'cached_tokens': 0}, 'output_tokens_details': {'reasoning_tokens': 0}}
                    events = [
                        {'type': 'response.created', 'response': {'id': response_id, 'object': 'response', 'status': 'in_progress', 'output': []}},
                        {'type': 'response.output_item.added', 'output_index': 0, 'item': {**output, 'status': 'in_progress', **({'content': []} if output['type'] == 'message' else {'arguments': ''})}},
                    ]
                    if output['type'] == 'message':
                        events.extend([
                            {'type': 'response.content_part.added', 'item_id': output['id'], 'output_index': 0, 'content_index': 0, 'part': {'type': 'output_text', 'text': '', 'annotations': []}},
                            {'type': 'response.output_text.delta', 'item_id': output['id'], 'output_index': 0, 'content_index': 0, 'delta': output['content'][0]['text']},
                            {'type': 'response.output_text.done', 'item_id': output['id'], 'output_index': 0, 'content_index': 0, 'text': output['content'][0]['text']},
                        ])
                    if output['type'] == 'function_call':
                        events.append({'type': 'response.function_call_arguments.delta', 'item_id': output['id'], 'output_index': 0, 'delta': output['arguments']})
                    events.extend([
                        {'type': 'response.output_item.done', 'output_index': 0, 'item': output},
                        {'type': 'response.completed', 'response': {'id': response_id, 'object': 'response', 'status': 'completed', 'output': [output], 'usage': usage}},
                    ])
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    for event in events:
                        self.wfile.write(('event: ' + event['type'] + '\ndata: ' + json.dumps(event) + '\n\n').encode())
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as error:
                    owner.errors.append(str(error))
                    self.send_error(500, 'owned fixture failure')

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.release_response.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    @property
    def base_url(self):
        return f'http://127.0.0.1:{self.server.server_port}/v1'

    def reset(self, mode='complete'):
        with self.lock:
            self.mode, self.goal_tool_sent, self.sequence = mode, False, 0
            self.release_response.clear()

    def output(self, request, n):
        if n >= 2 and not self.goal_tool_sent and self.mode == 'complete':
            tool = self.goal_tool(request.get('tools', []))
            if tool is None:
                raise ValueError('installed Codex did not advertise a native Goal completion tool')
            self.goal_tool_sent = True
            schema = tool.get('parameters', {})
            args = self.arguments(schema)
            args['status'] = 'complete'
            return {'id': f'fc_{n}', 'type': 'function_call', 'call_id': f'call_goal_{n}',
                    'name': tool['name'], 'arguments': json.dumps(args), 'status': 'completed'}
        text = 'invalid terminal output' if self.mode == 'invalid' else json.dumps({'status': 'completed', 'resultPath': self.result_path, 'resultText': 'Native answer'})
        return {'id': f'msg_{n}', 'type': 'message', 'role': 'assistant', 'status': 'completed', 'phase': 'final_answer',
                'content': [{'type': 'output_text', 'text': text, 'annotations': []}]}

    @classmethod
    def goal_tool(cls, tools):
        for tool in tools:
            if tool.get('type') == 'namespace':
                nested = cls.goal_tool(tool.get('tools', []))
                if nested:
                    return {**nested, 'name': tool['name'] + '.' + nested['name']}
            function = tool.get('function', tool)
            if 'goal' in function.get('name', '').lower() and 'status' in function.get('parameters', {}).get('properties', {}):
                return function
        return None

    @classmethod
    def arguments(cls, schema):
        values = {}
        for key in schema.get('required', []):
            prop = schema.get('properties', {}).get(key, {})
            if key == 'status': value = 'complete'
            elif key in ('objective',): value = 'Owned deterministic scheduler exercise'
            elif prop.get('enum'): value = prop['enum'][0]
            elif prop.get('type') in ('number', 'integer'): value = 4000 if 'budget' in key.lower() else 1
            elif prop.get('type') == 'boolean': value = True
            elif prop.get('type') == 'object': value = cls.arguments(prop)
            else: value = 'Controlled local fixture completion'
            values[key] = value
        return values
