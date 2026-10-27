"""GitHub OTA staging with fixed source, normal-user builds and parked activation."""
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import urllib.error

from ota_state import SHA, private_directory, read_json, write_json, selection, release_path, activate

REPOSITORY='desquerteur/coscarOS'
API=f'https://api.github.com/repos/{REPOSITORY}/git/ref/heads/main'
DEFAULTS={'autoCheck':True,'notifyUpdates':True,'mode':'notify','checkIntervalHours':6,'prepareDuringAndroidAuto':True,'allowMetered':False,'keepVersions':2}


def validate_settings(value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULTS):raise ValueError('Provide the complete software-update settings')
    for key in ('autoCheck','notifyUpdates','prepareDuringAndroidAuto','allowMetered'):
        if type(value[key]) is not bool:raise ValueError(f'{key} must be boolean')
    if value['mode'] not in ('notify','idle'):raise ValueError('Select notify or idle installation')
    if type(value['checkIntervalHours']) is not int or not 1<=value['checkIntervalHours']<=168:raise ValueError('Check interval must be 1–168 hours')
    if type(value['keepVersions']) is not int or not 2<=value['keepVersions']<=4:raise ValueError('Keep 2–4 managed versions')
    return dict(value)


def current_revision(root):
    revision=os.environ.get('HUDIY_SOURCE_REVISION','')
    if SHA.fullmatch(revision):return revision
    try:
        value=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True,timeout=3,stderr=subprocess.DEVNULL).strip()
        return value if SHA.fullmatch(value) else None
    except (OSError,subprocess.SubprocessError):return None


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        from urllib.parse import urlsplit
        url=urlsplit(newurl)
        expected='/repos/'+REPOSITORY+'/' if url.hostname=='api.github.com' else '/'+REPOSITORY+'/tar.gz/'
        if url.scheme!='https' or url.hostname not in ('api.github.com','codeload.github.com') or url.username or url.password or url.port not in (None,443) or not url.path.lower().startswith(expected.lower()):raise ValueError('Unexpected update download redirect')
        return super().redirect_request(request,fp,code,msg,headers,newurl)


def download(url,target=None,limit=65536,cancel=None):
    opener=urllib.request.build_opener(HTTPSOnly)
    request=urllib.request.Request(url,headers={'User-Agent':'coscarOS-Updater','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10'})
    result=bytearray();digest=hashlib.sha256();total=0
    try:
        with opener.open(request,timeout=30) as response:
            while True:
                if cancel and cancel.is_set():raise InterruptedError('Update cancelled')
                block=response.read(65536)
                if not block:break
                total+=len(block)
                if total>limit:raise ValueError('Update download exceeds its size limit')
                digest.update(block)
                if target:target.write(block)
                else:result.extend(block)
    except urllib.error.HTTPError as exc:
        if exc.code in (403,429):raise ConnectionError('GitHub refused the request or its rate limit was reached. Wait, then check again.') from None
        if exc.code==404:raise ConnectionError('The configured GitHub update source or revision was not found.') from None
        raise ConnectionError('GitHub update request failed (HTTP '+str(exc.code)+'). Try again later.') from None
    except (urllib.error.URLError,TimeoutError):
        raise ConnectionError('Cannot reach GitHub. Check Internet access, DNS and the Pi clock, then retry.') from None
    return digest.hexdigest() if target else bytes(result)


def unpack(archive,target,revision):
    prefix='coscarOS-'+revision
    with tarfile.open(archive,'r:gz') as tar:
        members=[];total=0
        for member in tar:
            members.append(member);total+=member.size
            if len(members)>10000 or total>120*1024*1024:raise ValueError('Source archive exceeds extraction limits')
        names=set()
        for member in members:
            path=PurePosixPath(member.name)
            if path.is_absolute() or not path.parts or path.parts[0]!=prefix or '..' in path.parts or '\\' in member.name or any(':' in part for part in path.parts) or not (member.isfile() or member.isdir()) or member.name in names or any(part in ('.ota-release.json','.ota-incomplete.json') for part in path.parts):raise ValueError('Unsafe source archive entry')
            names.add(member.name)
        for member in members:
            parts=PurePosixPath(member.name).parts[1:]
            if not parts:continue
            path=target.joinpath(*parts)
            if member.isdir():path.mkdir(parents=True,exist_ok=True)
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(member) as source,path.open('xb') as output:shutil.copyfileobj(source,output)
                path.chmod(member.mode&0o755)


def network_status(projection):
    try:
        route=json.loads(subprocess.check_output(['ip','-j','route','show','default'],text=True,timeout=3))
        route=sorted((r for r in route if isinstance(r,dict) and re.fullmatch(r'[a-zA-Z0-9_.:-]{1,32}',r.get('dev',''))),key=lambda r:r.get('metric',0))
        if not route:return {'allowed':False,'message':'No Internet default route. Connect Ethernet or a Wi-Fi Internet network.'}
        device=route[0]['dev']
        kind=subprocess.check_output(['nmcli','-g','GENERAL.TYPE','device','show',device],text=True,timeout=3).strip()
        metered=subprocess.check_output(['nmcli','-g','GENERAL.METERED','device','show',device],text=True,timeout=3).strip().lower()
        if kind not in ('ethernet','wifi'):return {'allowed':False,'interface':device,'message':'Updates require an Ethernet or Wi-Fi Internet route.'}
        if kind=='wifi' and projection.get('connected') and projection.get('transport')=='wifi' and device=='wlan0':return {'allowed':False,'interface':device,'message':'Wireless Android Auto uses this Wi-Fi adapter. Connect Ethernet or a separate Internet Wi-Fi adapter.'}
        return {'allowed':True,'interface':device,'type':kind,'metered':False if metered.startswith('no') else True if metered.startswith('yes') else None,'message':'Ethernet Internet route' if kind=='ethernet' else 'Wi-Fi Internet route'}
    except (OSError,ValueError,TypeError,subprocess.SubprocessError):return {'allowed':False,'message':'Network route information is unavailable.'}


class SoftwareUpdate:
    def __init__(self,projection,obd,calls,recorder,root=None,baseline=None,enabled=None):
        self.projection,self.obd,self.calls,self.recorder=projection,obd,calls,recorder
        self.root=Path(root) if root else Path.home()/'.local/share/hudiy-recreation/software-updates'
        self.baseline=Path(baseline or os.environ.get('HUDIY_BOOTSTRAP_ROOT',Path(__file__).resolve().parents[2]))
        self.enabled=bool(projection.enabled and os.environ.get('HUDIY_UPDATE_SUPERVISOR')=='1' and sys.platform=='linux') if enabled is None else enabled
        self.installed=current_revision(Path(__file__).resolve().parents[2])
        self.lock=threading.RLock();self.worker=None;self.scheduler=None;self.stop_event=threading.Event();self.cancel_event=threading.Event();self.cancelled_by_user=False
        self.settings=dict(DEFAULTS);self.cache={'phase':'idle','message':'Ready to check GitHub.','latestRevision':None,'checkedAt':None,'preparedRevision':None,'failedRevision':None}
        self.network={'allowed':False,'message':'Checking network…' if self.enabled else 'OTA installation requires our supervised Pi launcher.'}
        self.last_attempt=0;self.started=time.monotonic();self.idle_since=None;self.idle_reason=None
        if self.enabled:
            try:
                private_directory(self.root)
                saved=read_json(self.root/'settings.json')
                if isinstance(saved,dict) and set(saved)==set(DEFAULTS)-{'notifyUpdates'}:saved={**DEFAULTS,**saved}
                if saved is not None:self.settings=validate_settings(saved)
                cache=read_json(self.root/'status.json',{})
                if isinstance(cache,dict):self.cache.update({k:cache[k] for k in self.cache if k in cache})
                selected=selection(self.root)
                if selected['pending']:self.cache.update(phase='verifying',message='Validating the new application before confirming the update.')
                elif self.cache['phase'] in ('checking','downloading','building','testing','activating','verifying'):self.cache.update(phase='idle',message='Previous update work was interrupted; installed software remains available.')
                if self.cache['latestRevision']==self.installed and not selected['pending']:self.cache.update(phase='current',message='Installed version matches the last GitHub check.')
            except (OSError,ValueError,TypeError):self.cache.update(phase='failed',message='Update state needs inspection; the installed application is unchanged.')

    def _state(self,phase,message,**fields):
        with self.lock:
            self.cache.update(phase=phase,message=message,**fields)
            write_json(self.root/'status.json',self.cache)

    def snapshot(self):
        with self.lock:
            try:selected=selection(self.root) if self.enabled else {'active':None,'previous':None,'pending':False}
            except (OSError,ValueError,TypeError):selected={'active':None,'previous':None,'pending':False}
            if self.cache['phase']=='verifying' and not selected['pending']:
                try:
                    saved=read_json(self.root/'status.json',{})
                    if isinstance(saved,dict):self.cache.update({key:saved[key] for key in self.cache if key in saved})
                    if self.cache.get('latestRevision')==self.installed:self.cache.update(phase='current',message='Application startup verified; the installed version is current.')
                except (OSError,ValueError,TypeError):pass
            return {'available':self.enabled,'repository':REPOSITORY,'installedRevision':self.installed,'settings':dict(self.settings),'network':dict(self.network),**copy.deepcopy(self.cache),'busy':bool(self.worker and self.worker.is_alive()),'pendingRestart':selected['pending'],'idleWaitReason':self.idle_reason,'canRollback':selected['previous'] is not None or selected['active'] is not None}

    def save(self,settings):
        if not self.enabled:raise ConnectionError('OTA settings require the supervised Pi application')
        value=validate_settings(settings)
        with self.lock:write_json(self.root/'settings.json',value);self.settings=value
        return self.snapshot()

    @contextmanager
    def operation_lock(self):
        import fcntl
        private_directory(self.root)
        fd=os.open(self.root/'operation.lock',os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            yield

    def start(self):
        if self.enabled and not self.scheduler:
            self.scheduler=threading.Thread(target=self._schedule_loop,daemon=True);self.scheduler.start()

    def close(self):
        self.stop_event.set();self.cancel_event.set()
        if self.scheduler:self.scheduler.join(timeout=4)
        if self.worker:self.worker.join(timeout=5)

    def _network(self):
        self.network=network_status(self.projection.snapshot())
        if not self.network.get('allowed'):raise ConnectionError(self.network['message'])
        if self.network.get('metered') is not False and not self.settings['allowMetered']:raise ConnectionError('This route is metered or unclassified. Enable metered updates to use it.')

    def request(self,operation):
        if not self.enabled:raise ConnectionError('OTA installation requires our supervised Pi launcher')
        if operation not in ('check','prepare','cancel'):raise ValueError('Unknown software-update operation')
        with self.lock:
            if operation=='cancel':
                self.cancelled_by_user=True;self.cancel_event.set()
                self._state('cancelled','Update preparation cancelled; automatic retry of this revision is paused.',failedRevision=self.cache.get('latestRevision'))
                return self.snapshot()
            if self.worker and self.worker.is_alive():raise ValueError('An update operation is already running')
            self.cancel_event.clear();self.cancelled_by_user=False
            if operation=='prepare':self.cache['failedRevision']=None
            self.worker=threading.Thread(target=self._job,args=(operation,),daemon=True);self.worker.start()
        return self.snapshot()

    def _job(self,operation):
        try:
            with self.operation_lock():
                self._network()
                if operation=='check':self._check()
                else:self._prepare()
                if self.cancel_event.is_set():raise InterruptedError('Update cancelled')
        except InterruptedError:self._state('cancelled','Update preparation cancelled. Installed software is unchanged.' if self.cancelled_by_user else 'Update preparation interrupted by application shutdown; it can resume next start.',failedRevision=self.cache.get('latestRevision') if self.cancelled_by_user else None)
        except Exception as exc:
            self._state('failed',str(exc)[:240] if isinstance(exc,(ValueError,ConnectionError)) else 'Update check or build failed. Installed software is unchanged; inspect software-updates/build.log.')

    def _check(self):
        self.last_attempt=time.time();self._state('checking','Checking the project’s GitHub main branch…')
        data=json.loads(download(API,cancel=self.cancel_event))
        revision=data.get('object',{}).get('sha') if isinstance(data,dict) and isinstance(data.get('object'),dict) and data['object'].get('type')=='commit' else None
        if not isinstance(revision,str) or not SHA.fullmatch(revision):raise ValueError('GitHub returned an invalid revision')
        self._state('current' if revision==self.installed else 'available','The installed version is current.' if revision==self.installed else 'A GitHub update is available.',latestRevision=revision,checkedAt=time.time(),preparedRevision=self.cache.get('preparedRevision') if self.cache.get('preparedRevision')==revision else None,failedRevision=revision if self.cache.get('failedRevision')==revision else None)

    def _run(self,args,cwd,env,timeout=3600):
        if self.cancel_event.is_set():raise InterruptedError('Update cancelled')
        command=(['/usr/bin/nice','-n','10'] if Path('/usr/bin/nice').is_file() else [])+list(map(str,args))
        output=self.root/'build.log'
        if output.is_symlink():raise ValueError('Invalid build log')
        process=subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
        exceeded=threading.Event()
        def drain():
            total=0
            with output.open('ab') as log:
                if os.name=='posix':os.chmod(output,0o600)
                while block:=process.stdout.read1(4096):
                    total+=len(block)
                    if total<=2*1024*1024:log.write(block)
                    else:exceeded.set()
        reader=threading.Thread(target=drain,daemon=True);reader.start();deadline=time.monotonic()+timeout
        try:
            while process.poll() is None:
                if self.cancel_event.is_set() or self.stop_event.is_set():raise InterruptedError('Update cancelled')
                if shutil.disk_usage(self.root).free<512*1024*1024:raise ValueError('Build stopped to preserve free disk space')
                if exceeded.is_set() or time.monotonic()>deadline:raise ValueError('Build exceeded its time/output limit')
                time.sleep(.2)
            if process.returncode:raise ValueError('Build/test failed. Existing software is unchanged; inspect software-updates/build.log.')
        finally:
            if process.poll() is None:
                import signal
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)
            reader.join(timeout=3)
            process.stdout.close()

    def _environment(self):
        env=dict(os.environ)
        for key in ('HUDIY_STANDALONE','HUDIY_UPDATE_SUPERVISOR','HUDIY_UPDATE_NONCE','HUDIY_SOURCE_REVISION','HUDIY_BOOTSTRAP_ROOT'):env.pop(key,None)
        managed=Path.home()/'.local/share/hudiy-recreation/node'
        candidates=sorted((p for p in managed.glob('node-v22.*-linux-arm64') if not p.is_symlink() and (p/'bin/node').is_file()),key=lambda p:tuple(map(int,re.findall(r'\d+',p.name))))
        if candidates:env['PATH']=str(candidates[-1]/'bin')+os.pathsep+env.get('PATH','')
        if not shutil.which('npm',path=env.get('PATH')):raise ValueError('Node/npm is missing. Run the normal Pi installer first.')
        return env

    def _prepare(self):
        revision=self.cache.get('latestRevision')
        if not isinstance(revision,str) or not SHA.fullmatch(revision):raise ValueError('Check GitHub before preparing an update')
        if revision==self.installed:raise ValueError('The installed version is already current')
        if self.projection.snapshot().get('connected') and not self.settings['prepareDuringAndroidAuto']:raise ValueError('Background preparation is disabled while Android Auto is connected')
        releases=private_directory(self.root/'releases')
        self._prune()
        if shutil.disk_usage(releases).free<4*1024**3:raise ValueError('At least 4 GiB free space is required to build an update')
        target=releases/revision
        if target.exists():
            marker=read_json(target/'.ota-incomplete.json',{})
            selected=selection(self.root)
            if isinstance(marker,dict) and marker.get('revision')==revision and revision not in (selected['active'],selected['previous']) and target.resolve().parent==releases.resolve() and not target.is_symlink():shutil.rmtree(target)
            else:
                release_path(self.root,revision,self.baseline)
                self._state('ready','Update is built and tested. Install when parked.',preparedRevision=revision);return
        self._state('downloading','Downloading the checked GitHub revision…',preparedRevision=None)
        log=self.root/'build.log'
        if log.is_symlink():raise ValueError('Invalid build log')
        log.write_text('',encoding='utf-8');log.chmod(0o600)
        with tempfile.TemporaryDirectory(prefix='.stage-',dir=releases) as temporary:
            work=Path(temporary);source=work/'source';source.mkdir()
            archive=work/'source.tar.gz'
            with archive.open('xb') as stream:digest=download(f'https://codeload.github.com/{REPOSITORY}/tar.gz/{revision}',stream,20*1024*1024,self.cancel_event)
            unpack(archive,source,revision)
            protocol=source/'implementation/OTA_PROTOCOL'
            if not protocol.is_file() or protocol.read_text().strip()!='1':raise ValueError('This GitHub version needs the normal installer before OTA can be used')
            # Build at the final path: native libraries may embed absolute RPATHs.
            write_json(source/'.ota-incomplete.json',{'revision':revision})
            source.rename(target);source=target
            dashboard=source/'implementation/dashboard';native=source/'implementation/native';env=self._environment()
            self._state('building','Building the new interface in a separate release directory…')
            self._run(['npm','ci'],dashboard,env);self._run(['npm','run','build'],dashboard,env)
            self._state('testing','Testing the new interface and Python service…')
            self._run(['node','--test',*[str(p.relative_to(dashboard)) for p in sorted((dashboard/'tests').glob('*.test.mjs'))]],dashboard,env)
            self._run(['/usr/bin/python3','-m','unittest','discover','-s','implementation/service','-p','test_*.py'],source,env)
            self._state('building','Building the independent Android Auto runtime…')
            self._run(['cmake','-S',native,'-B',native/'build','-DCMAKE_BUILD_TYPE=Release'],source,env)
            self._run(['cmake','--build',native/'build','--parallel','1'],source,env,7200)
            self._state('testing','Running native runtime checks…')
            self._run(['ctest','--test-dir',native/'build','--output-on-failure','--no-tests=error'],source,env)
            write_json(source/'.ota-release.json',{'revision':revision,'ready':True,'archiveSHA256':digest,'builtAt':time.time()})
            (source/'.ota-incomplete.json').unlink()
        release_path(self.root,revision,self.baseline)
        self._state('ready','Update is built and tested. Install when parked.',preparedRevision=revision)

    def _prune(self):
        selected=selection(self.root);protected={selected['active'],selected['previous'],self.cache.get('preparedRevision')}
        releases=private_directory(self.root/'releases')
        candidates=[]
        for path in releases.iterdir():
            if path.is_symlink() or not path.is_dir() or not SHA.fullmatch(path.name):continue
            try:release_path(self.root,path.name,self.baseline)
            except (OSError,ValueError,TypeError):continue
            candidates.append(path)
        keep=set(protected)
        for path in sorted(candidates,key=lambda p:p.stat().st_mtime,reverse=True):
            if len([item for item in keep if item])<self.settings['keepVersions']:keep.add(path.name)
        for path in candidates:
            if path.name not in keep and path.resolve().parent==releases.resolve():shutil.rmtree(path)

    def parked_reason(self,automatic=False):
        if self.calls.snapshot().get('call',{}).get('state') in (1,2,3):return 'Wait until the phone call ends.'
        if self.recorder.snapshot().get('recording'):return 'Stop and save OBD recording before restarting the application.'
        status=self.obd.snapshot();speed=status.get('values',{}).get('speed');stamp=status.get('timestamp')
        fresh=status.get('connected') and type(stamp) in (int,float) and 0<=time.time()-stamp<=5
        if fresh and type(speed) in (int,float) and speed>0:return 'Updates cannot be activated while vehicle speed is above zero.'
        if automatic:
            if self.projection.snapshot().get('connected'):return 'Waiting for Android Auto to disconnect before automatic installation.'
            if not fresh or type(speed) not in (int,float) or speed!=0:return 'Automatic installation needs fresh OBD confirmation that the vehicle is stationary.'
            rpm=status.get('values',{}).get('rpm')
            if type(rpm) not in (int,float) or rpm!=0:return 'Automatic installation waits for the engine to be stopped.'
        return None

    def install(self,parked,rollback=False,automatic=False):
        if not self.enabled:raise ConnectionError('OTA activation requires the supervised Pi launcher')
        if parked is not True:raise ValueError('Confirm that the car is parked and the application may restart')
        if self.worker and self.worker.is_alive():raise ValueError('Wait for update preparation to finish')
        reason=self.parked_reason(automatic)
        if reason:raise ValueError(reason)
        with self.operation_lock():
            selected=selection(self.root)
            revision=selected['previous'] if rollback else self.cache.get('preparedRevision')
            if not rollback and (not isinstance(revision,str) or not SHA.fullmatch(revision)):raise ValueError('Prepare and test an update before installation')
            if rollback and selected['active'] is None and selected['previous'] is None:raise ValueError('No previous managed version is available')
            before,pending=activate(self.root,revision,self.baseline)
            try:
                self._state('activating','Restarting into the selected version. The launcher will verify it and roll back if startup fails.',failedRevision=self.cache.get('latestRevision') if rollback else None)
                self.projection.request_exit()
            except Exception:write_json(self.root/'selection.json',before);raise
        return {'accepted':True,'message':'Application restart requested. Reconnect to the interface shortly.'}

    def healthy(self):
        if not self.enabled:return {'healthy':False}
        with self.lock:
            selected=selection(self.root);nonce=os.environ.get('HUDIY_UPDATE_NONCE')
            state=self.projection.snapshot()
            if selected['pending'] and selected['nonce']==nonce and time.monotonic()-self.started>=10 and state.get('available') and state.get('uiReady') is True:
                write_json(self.root/f'health-{nonce}.json',{'nonce':nonce,'revision':selected['active'],'ready':True})
                return {'healthy':True}
            return {'healthy':not selected['pending']}

    def _schedule_loop(self):
        while not self.stop_event.wait(10):
            try:self._tick()
            except Exception:pass

    def _tick(self):
        self.network=network_status(self.projection.snapshot())
        if self.worker and self.worker.is_alive():return
        if selection(self.root)['pending']:return
        if self.settings['autoCheck'] and time.time()-max(self.last_attempt,self.cache.get('checkedAt') or 0)>=self.settings['checkIntervalHours']*3600:
            if self.network.get('allowed') and (self.network.get('metered') is False or self.settings['allowMetered']):
                self.last_attempt=time.time();self.request('check')
            return
        if self.settings['mode']!='idle':self.idle_reason=None;return
        latest=self.cache.get('latestRevision')
        if not latest or latest==self.installed or latest==self.cache.get('failedRevision') or self.cache['phase']=='failed':return
        if self.cache.get('preparedRevision')!=latest:
            if self.network.get('allowed') and (self.network.get('metered') is False or self.settings['allowMetered']) and (self.settings['prepareDuringAndroidAuto'] or not self.projection.snapshot().get('connected')):self.request('prepare')
            return
        reason=self.parked_reason(True);self.idle_reason=reason
        if reason:self.idle_since=None;return
        if self.idle_since is None:self.idle_since=time.monotonic()
        if time.monotonic()-self.idle_since>=30:self.install(True,automatic=True)
