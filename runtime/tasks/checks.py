"""Detached integration checks with immutable input and streamed evidence.

The loop polls this operation without holding a repository lock for its duration.
An unknown exit is preserved, never interpreted as success or blindly replayed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from storage.files import atomic_write_json, safe_read_json, file_lock
from storage import paths as runtime_paths
from storage.errors import ContractError
from system import containment


def observe(unit, directory, stage):
    inputs = {"argv": unit["checks"], "workspace": unit["path"], "commit": unit["checkCommit"], "stage": stage,
              "generation": unit.get("checkGeneration", 0)}
    identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:24]
    path = directory / ("check-" + identity + ".json")
    with file_lock(path.with_suffix(".lock"), blocking=False):
        if not path.exists():
            record = {"id": identity, "inputs": inputs, "status": "starting", "results": [],
                      "outputPath": str(path.with_suffix(".log")), "driverOutputPath": str(path.with_suffix(".driver.log")),
                      "runtimeBinding": runtime_paths.resolve(runtime_paths.project_for(directory)),
                      "createdAt": containment.now()}
            atomic_write_json(path, record)
            env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]), "PYTHONDONTWRITEBYTECODE": "1"}
            with Path(record["driverOutputPath"]).open("ab", buffering=0) as output:
                process, owner, release = containment.spawn_contained_process(
                    [sys.executable, "-m", "tasks.checks", str(path)], detach=True,
                    stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, env=env)
            record["owner"] = owner
            atomic_write_json(path, record)
            containment.release_contained_process(process, owner, release)
            # Retain the Popen until its launcher can reap it on a later poll.
            _launchers[identity] = process
        record = safe_read_json(path)
        launcher = _launchers.get(identity)
        if launcher and launcher.poll() is not None:
            _launchers.pop(identity, None)
        if record["status"] in {"starting", "running"}:
            owner_status = containment.process_identity_status(record.get("owner"))
            if not record.get("owner") or owner_status in {"dead", "mismatch"}:
                child_status = containment.process_identity_status(record.get("child"))
                record.update(status="interrupted", nextAction="Inspect stored child identity/output; exit is unconfirmed",
                              childStatus=child_status)
                atomic_write_json(path, record)
        return {**record, "statePath": str(path)}


_launchers = {}


def cancel(path):
    """Separate durable intent so worker progress cannot overwrite cancellation."""
    from storage.files import atomic_write
    atomic_write(Path(path).with_suffix(".cancel"), b"cancel\n")
    record = safe_read_json(Path(path))
    if record.get("status") == "interrupted" and record.get("child"):
        containment.terminate_verified_group(record["child"])
        record.update(status="cancelled", endedAt=containment.now())
        publish(Path(path), record)


def publish(path, record):
    with file_lock(path.with_suffix(".lock")):
        atomic_write_json(path, record)


def worker(path):
    # Distinct lock: observers remain responsive while one owner executes.
    with file_lock(path.with_suffix(".owner.lock"), blocking=False):
        record = safe_read_json(path)
        inputs = record["inputs"]
        runtime_paths.bind(record["runtimeBinding"])
        record.update(status="running", startedAt=containment.now())
        publish(path, record)
        try:
            with Path(record["outputPath"]).open("ab", buffering=0) as output:
                for argv in inputs["argv"]:
                    if path.with_suffix(".cancel").exists():
                        record.update(status="cancelled", endedAt=containment.now())
                        publish(path, record)
                        return
                    output.write(("\n" + json.dumps(argv) + "\n").encode())
                    process, child, release = containment.spawn_contained_process(
                        argv, cwd=inputs["workspace"], stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
                    record.update(child=child, currentArgv=argv)
                    publish(path, record)
                    containment.release_contained_process(process, child, release)
                    while process.poll() is None:
                        if path.with_suffix(".cancel").exists():
                            containment.terminate_attempt_group(process, child)
                            record.update(status="cancelled", endedAt=containment.now())
                            publish(path, record)
                            return
                        record.update(observedAt=containment.now(), outputBytes=output.tell())
                        publish(path, record)
                        time.sleep(1)
                    # Only the containment created for this command is retired.
                    containment.terminate_attempt_group(process, child)
                    record["results"].append({"argv": argv, "exitCode": process.returncode, "outputPath": record["outputPath"]})
                    publish(path, record)
                    if process.returncode:
                        record["status"] = "failed"
                        break
                else:
                    record["status"] = "completed"
            record["endedAt"] = containment.now()
            publish(path, record)
        except (OSError, ValueError, ContractError) as error:
            record.update(status="interrupted", error=str(error), nextAction="Inspect operation evidence before retrying")
            publish(path, record)


if __name__ == "__main__":
    worker(Path(sys.argv[1]))
