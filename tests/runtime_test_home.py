"""One isolated runtime home for test processes and their fixture children."""
import atexit
import os
import tempfile
from pathlib import Path

_temporary = tempfile.TemporaryDirectory(prefix='af-test-home-')
os.environ['AGENT_FACTORY_HOME'] = str(Path(_temporary.name) / 'runtime')
atexit.register(_temporary.cleanup)
