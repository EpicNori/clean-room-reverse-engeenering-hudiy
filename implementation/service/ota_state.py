"""Private release selection shared by the stable launcher and OTA service."""
import json
import os
from pathlib import Path
import re
import secrets
from runtime_support import save_json

SHA=re.compile(r'[0-9a-f]{40}')
NONCE=re.compile(r'[0-9a-f]{32}')


def private_directory(root):
    root=Path(root)
    if any(path.is_symlink() for path in (root,*root.parents)):raise ValueError('Update storage cannot contain symlinks')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name=='posix':root.chmod(0o700)
    return root


def read_json(path,default=None):
    try:
        if path.is_symlink() or path.stat().st_size>65536:raise ValueError('Invalid update file')
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:return default


def write_json(path,data):
    private_directory(path.parent)
    if path.is_symlink() or path.with_name(path.name+'.tmp').is_symlink():raise ValueError('Invalid update file')
    save_json(path,data)


def selection(root):
    private_directory(root)
    data=read_json(root/'selection.json',{'active':None,'previous':None,'pending':False,'nonce':None})
    if not isinstance(data,dict) or set(data)!={'active','previous','pending','nonce'}:raise ValueError('Invalid software selection')
    for key in ('active','previous'):
        if data[key] is not None and (not isinstance(data[key],str) or not SHA.fullmatch(data[key])):raise ValueError('Invalid selected revision')
    if type(data['pending']) is not bool:raise ValueError('Invalid activation state')
    if data['pending']:
        if not isinstance(data['nonce'],str) or not NONCE.fullmatch(data['nonce']):raise ValueError('Invalid activation token')
    elif data['nonce'] is not None:raise ValueError('Unexpected activation token')
    return data


def release_path(root,revision,baseline):
    if revision is None:return Path(baseline)
    if not isinstance(revision,str) or not SHA.fullmatch(revision):raise ValueError('Invalid release revision')
    directory=root/'releases'/revision
    if any(p.is_symlink() for p in (directory,directory.parent)):raise ValueError('Invalid release path')
    incomplete=directory/'.ota-incomplete.json'
    if incomplete.exists() or incomplete.is_symlink():raise ValueError('Release is still being built')
    manifest=read_json(directory/'.ota-release.json')
    if not isinstance(manifest,dict) or manifest.get('revision')!=revision or manifest.get('ready') is not True:raise ValueError('Release has not passed its build checks')
    for relative in ('implementation/native/build/hudiy-car-runtime','implementation/dashboard/dist/client/index.html','implementation/service/server.py'):
        path=directory/relative
        if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents) if p.is_relative_to(directory)):raise ValueError('Release files are missing')
        if path.is_symlink():raise ValueError('Release files cannot be symlinks')
    return directory


def activate(root,revision,baseline):
    before=selection(root)
    if before['pending']:raise ValueError('A software activation is already pending')
    release_path(root,revision,baseline)
    if revision==before['active']:raise ValueError('That version is already selected')
    pending={'active':revision,'previous':before['active'],'pending':True,'nonce':secrets.token_hex(16)}
    write_json(root/'selection.json',pending)
    return before,pending


def rollback_failed(root,pending,message):
    restored={'active':pending['previous'],'previous':None,'pending':False,'nonce':None}
    write_json(root/'selection.json',restored)
    cache=read_json(root/'status.json',{})
    if not isinstance(cache,dict):cache={}
    write_json(root/'status.json',{**cache,'phase':'rolled-back','message':message,'failedRevision':pending['active']})
    return restored


def select_rebuilt_baseline(root,reason="Normal installer selected the rebuilt baseline application."):
    """Normal installer has built/tested baseline; do not boot an older OTA copy."""
    try:before=selection(root)
    except (OSError,ValueError,TypeError):before={'active':None,'previous':None}
    previous=before['active'] or before['previous']
    if previous:
        try:release_path(root,previous,Path('.'))
        except (OSError,ValueError,TypeError):previous=None
    write_json(root/'selection.json',{'active':None,'previous':previous,'pending':False,'nonce':None})
    write_json(root/'status.json',{'phase':'idle','message':reason,'latestRevision':None,'checkedAt':None,'preparedRevision':None,'failedRevision':None})
