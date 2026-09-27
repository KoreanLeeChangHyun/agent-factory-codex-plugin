"""Model-free filesystem readiness evidence shared by local providers."""
# argv carries paths and expectations; no shell interpolation or project code.
CANARY = r'''
import errno,json,os,sys
from pathlib import Path
request,project,run,marker,mode=sys.argv[1:]
with open(request,'rb') as stream:
    stream.read(1)
with os.scandir(project) as entries:
    next(entries,None)

def write_canary(directory):
    path=Path(directory)/marker
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        os.write(descriptor,b'agent-factory-preflight\n')
    finally:
        os.close(descriptor)
        path.unlink()

write_canary(run)
try:
    write_canary(project)
    project_write='allowed'
except OSError as error:
    if error.errno not in (errno.EACCES,errno.EPERM,errno.EROFS):
        raise
    project_write='denied'
expected='denied' if mode=='read-only' else 'allowed'
if project_write!=expected:
    raise RuntimeError('project write policy mismatch: expected '+expected+', observed '+project_write)
print(json.dumps({'schemaVersion':1,'passed':True,'checks':{
    'requestRead':True,'projectDirectoryRead':True,'runWrite':True,'projectWrite':project_write}}))
'''

