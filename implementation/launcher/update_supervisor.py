"""Stable launcher loop: select prepared releases and revert failed startup."""
import os
from pathlib import Path
import subprocess
import time
from ota_state import selection, release_path, read_json, write_json, rollback_failed


def stop_owned(process):
    if process.poll() is None:
        if os.name=="posix" and hasattr(process,"pid"):
            import signal
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        else:process.terminate()
        try:process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            if os.name=="posix" and hasattr(process,"pid"):
                import signal
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            else:process.kill()
            process.wait(timeout=4)


def supervise(baseline,state,launch,clock=time.monotonic,sleep=time.sleep,timeout=90,stability=30):
    """launch(root, environment) returns only our owned child process."""
    baseline=Path(baseline);state=Path(state)
    failures=0
    while failures<3:
        failed=None
        try:selected=selection(state)
        except (OSError,ValueError,TypeError):selected={'active':None,'previous':None,'pending':False,'nonce':None};failed='invalid'
        try:root=release_path(state,selected['active'],baseline)
        except (OSError,ValueError,TypeError):
            failed=selected['active'];previous=selected['previous']
            try:root=release_path(state,previous,baseline)
            except (OSError,ValueError,TypeError):previous=None;root=baseline
            selected={'active':previous,'previous':None,'pending':False,'nonce':None}
        if failed:
            write_json(state/'selection.json',selected)
            cache=read_json(state/'status.json',{})
            write_json(state/'status.json',{**(cache if isinstance(cache,dict) else {}),'phase':'rolled-back','message':'Invalid software selection; previous working application restored.','failedRevision':failed if failed!='invalid' else None})
        environment=dict(os.environ,HUDIY_UPDATE_SUPERVISOR='1',HUDIY_BOOTSTRAP_ROOT=str(baseline))
        environment.pop('HUDIY_UPDATE_NONCE',None);environment.pop('HUDIY_SOURCE_REVISION',None)
        if selected['active']:environment['HUDIY_SOURCE_REVISION']=selected['active']
        if selected['pending']:environment['HUDIY_UPDATE_NONCE']=selected['nonce']
        try:process=launch(root,environment)
        except (OSError,RuntimeError):
            if selected['pending']:
                rollback_failed(state,selected,'New runtime could not be launched; previous version selected.');failures+=1;continue
            raise
        started=clock();confirmed=not selected['pending']
        try:
            while process.poll() is None:
                if not confirmed:
                    health=read_json(state/f"health-{selected['nonce']}.json",{})
                    healthy=isinstance(health,dict) and health.get('nonce')==selected['nonce'] and health.get('revision')==selected['active'] and health.get('ready') is True
                    if healthy and clock()-started>=stability:
                        committed={**selected,'pending':False,'nonce':None}
                        write_json(state/'selection.json',committed)
                        cache=read_json(state/'status.json',{})
                        if not isinstance(cache,dict):cache={}
                        write_json(state/'status.json',{**(cache if isinstance(cache,dict) else {}),'phase':'current' if cache.get('latestRevision') in (None,selected['active']) else 'available','message':'Application startup verified. Previous version is available for rollback.','failedRevision':None if cache.get('latestRevision')==selected['active'] else cache.get('failedRevision')})
                        confirmed=True;failures=0
                    elif clock()-started>=timeout:
                        stop_owned(process)
                        rollback_failed(state,selected,'New version did not pass startup health checks; restored the previous version.')
                        break
                sleep(.25)
            else:
                pass
            if not confirmed:
                # Both a timeout and an early candidate exit return to the old release.
                current=selection(state)
                if current['pending']:rollback_failed(state,selected,'New version exited before startup validation; restored the previous version.')
                failures+=1;continue
            newer=selection(state)
            if newer['pending'] and newer['nonce']!=selected['nonce']:continue
            return process.returncode or 0
        except KeyboardInterrupt:
            stop_owned(process);return process.returncode or 0
        except Exception:
            stop_owned(process)
            if selected['pending']:
                rollback_failed(state,selected,'Startup verification failed; previous version selected.');failures+=1;continue
            raise
    raise RuntimeError('Software restart attempts exhausted; use the baseline launcher for recovery')
