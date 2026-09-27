"""Exact-run named permissions; never grant the read-only code root write access."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def profile(run_directory, *, network=False):
    directory = Path(run_directory)
    if not directory.is_absolute() or '..' in directory.parts:
        raise ValueError('managed permission target must be absolute')
    name = 'agent_factory_run_' + hashlib.sha256(str(directory).encode()).hexdigest()[:24]
    policy = {'filesystem': {'/': 'read', str(directory): 'write'}, 'network': {'enabled': network}}
    return name, policy


def config(run_directory, *, network=False):
    name, policy = profile(run_directory, network=network)
    return {'default_permissions': name, 'permissions.' + name: policy}


def toml(value):
    if isinstance(value, dict):
        return '{' + ', '.join(json.dumps(k) + '=' + toml(v) for k, v in value.items()) + '}'
    return json.dumps(value)


def arguments(run_directory, *, network=False):
    result = []
    for key, value in config(run_directory, network=network).items():
        result.extend(['-c', key + '=' + toml(value)])
    return result
