import copy
from contextlib import nullcontext
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import Mock,patch

from ota_state import selection,activate,write_json,read_json,release_path
from software_update import SoftwareUpdate,DEFAULTS,validate_settings,unpack,network_status,HTTPSOnly
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'launcher'))
from update_supervisor import supervise

A='a'*40;B='b'*40
REF=json.dumps({'object':{'type':'commit','sha':B}}).encode()


def ready(root,revision):
    directory=root/'releases'/revision
    for name in ('implementation/native/build/hudiy-car-runtime','implementation/dashboard/dist/client/index.html','implementation/service/server.py'):
        path=directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
    write_json(directory/'.ota-release.json',{'revision':revision,'ready':True})
    return directory


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.base=Path(self.temporary.name);self.root=self.base/'ota';self.baseline=self.base/'baseline'
        self.projection=Mock(enabled=True);self.projection.snapshot.return_value={'available':True,'connected':False,'uiReady':True}
        self.obd=Mock();self.obd.snapshot.return_value={'connected':True,'timestamp':time.time(),'values':{'speed':0,'rpm':0}}
        self.calls=Mock();self.calls.snapshot.return_value={'call':{'state':0}}
        self.recorder=Mock();self.recorder.snapshot.return_value={'recording':False}
        self.update=SoftwareUpdate(self.projection,self.obd,self.calls,self.recorder,root=self.root,baseline=self.baseline,enabled=True)
        self.update.installed=A
        self.update.operation_lock=lambda:nullcontext()

    def test_settings_are_strict_durable_and_failed_save_does_not_acknowledge(self):
        value={**DEFAULTS,'mode':'idle','checkIntervalHours':24,'prepareDuringAndroidAuto':False}
        self.update.save(value)
        other=SoftwareUpdate(self.projection,self.obd,self.calls,self.recorder,root=self.root,baseline=self.baseline,enabled=True)
        self.assertEqual(other.settings,value)
        for bad in ({'url':'http://evil'},{'mode':'always'},{'autoCheck':1},{'checkIntervalHours':True},{'checkIntervalHours':0},{'keepVersions':8}):
            with self.assertRaises(ValueError):validate_settings({**DEFAULTS,**bad})
        with patch('software_update.write_json',side_effect=OSError('full')):
            with self.assertRaises(OSError):self.update.save(DEFAULTS)
        self.assertEqual(self.update.settings,value)

    def test_check_uses_small_fixed_main_reference_and_validates_the_commit(self):
        with patch('software_update.download',side_effect=[REF,json.dumps({'status':'ahead','files':[{'filename':'implementation/service/server.py'}]}).encode()]) as get:
            self.update._check()
            self.assertEqual(get.call_args_list[0].args[0],'https://api.github.com/repos/desquerteur/coscarOS/git/ref/heads/main')
            self.assertEqual(get.call_args_list[1].args[0],f'https://api.github.com/repos/desquerteur/coscarOS/compare/{A}...{B}')
        self.assertEqual(self.update.cache['latestRevision'],B)
        for data in ({'sha':B},{'object':{'type':'tag','sha':B}},{'object':{'type':'commit','sha':'../escape'}}):
            with patch('software_update.download',return_value=json.dumps(data).encode()):
                with self.assertRaises(ValueError):self.update._check()

    def test_manual_install_requires_confirmation_and_refuses_motion_calls_or_recording(self):
        ready(self.root,B);self.update.cache['preparedRevision']=B
        with self.assertRaises(ValueError):self.update.install(False)
        self.obd.snapshot.return_value['values']['speed']=12
        with self.assertRaises(ValueError):self.update.install(True)
        self.obd.snapshot.return_value['values']['speed']=0
        self.calls.snapshot.return_value={'call':{'state':2}}
        with self.assertRaises(ValueError):self.update.install(True)
        self.calls.snapshot.return_value={'call':{'state':0}};self.recorder.snapshot.return_value={'recording':True}
        with self.assertRaises(ValueError):self.update.install(True)
        self.assertFalse(selection(self.root)['pending'])

    def test_install_selection_is_atomic_and_reverted_when_native_exit_fails(self):
        ready(self.root,B);self.update.cache['preparedRevision']=B
        self.projection.request_exit.side_effect=ConnectionError('closed')
        with self.assertRaises(ConnectionError):self.update.install(True)
        self.assertEqual(selection(self.root)['active'],None);self.assertFalse(selection(self.root)['pending'])
        self.assertEqual(self.update.cache['phase'],'failed');self.assertIn('could not be requested',self.update.cache['message'])
        self.assertEqual(read_json(self.root/'status.json')['phase'],'failed');self.assertIsNone(self.update.activation)
        self.projection.request_exit.side_effect=None
        self.assertTrue(self.update.install(True)['accepted'])
        self.projection.request_exit.assert_called_with(force=True)
        selected=selection(self.root);self.assertEqual(selected['active'],B);self.assertEqual(len(selected['nonce']),32)

    def activation_fixture(self):
        ready(self.root,B);self.update.cache.update(preparedRevision=B,latestRevision=B)
        with patch('software_update.time.monotonic',return_value=1000):self.update.install(True)
        self.projection.request_exit.reset_mock()
        return selection(self.root)

    def tick_at(self,now,nonce='0'*32):
        with patch('software_update.time.monotonic',return_value=now),patch.dict(os.environ,{'HUDIY_UPDATE_NONCE':nonce}),patch('software_update.network_status',return_value={'allowed':False}):self.update._tick()

    def test_old_process_resends_exit_every_thirty_seconds_while_activation_is_pending(self):
        pending=self.activation_fixture()
        self.tick_at(1020);self.projection.request_exit.assert_not_called()
        self.tick_at(1031);self.projection.request_exit.assert_called_once_with(force=True)
        self.tick_at(1045);self.assertEqual(self.projection.request_exit.call_count,1)
        self.projection.request_exit.side_effect=ConnectionError('closed')
        self.tick_at(1062);self.assertEqual(self.projection.request_exit.call_count,2)
        self.assertEqual(selection(self.root),pending);self.assertEqual(self.update.cache['phase'],'activating')

    def test_old_process_restores_selection_when_no_restart_follows_within_ninety_seconds(self):
        self.activation_fixture()
        self.tick_at(1091)
        self.assertEqual(selection(self.root),{'active':None,'previous':None,'pending':False,'nonce':None})
        self.assertEqual(self.update.cache['phase'],'failed');self.assertIn('did not restart',self.update.cache['message'])
        self.assertEqual(read_json(self.root/'status.json')['phase'],'failed');self.assertIsNone(self.update.activation)
        self.assertFalse(self.update.snapshot()['pendingRestart'])

    def test_new_process_or_foreign_activation_is_never_reverted_by_the_watchdog(self):
        pending=self.activation_fixture()
        self.tick_at(1200,nonce=pending['nonce'])
        self.projection.request_exit.assert_not_called();self.assertEqual(selection(self.root),pending)
        self.update.activation=None
        self.tick_at(1200)
        self.projection.request_exit.assert_not_called();self.assertEqual(selection(self.root),pending)

    def test_auto_install_waits_for_engine_projection_and_fresh_standstill(self):
        self.assertIsNone(self.update.parked_reason(True))
        self.obd.snapshot.return_value['values']['rpm']=850
        self.assertIn('engine',self.update.parked_reason(True))
        self.obd.snapshot.return_value['values']['rpm']=0
        self.projection.snapshot.return_value['connected']=True
        self.assertIn('Android Auto',self.update.parked_reason(True))
        self.projection.snapshot.return_value['connected']=False
        self.obd.snapshot.return_value['timestamp']=time.time()-20
        self.assertIsNotNone(self.update.parked_reason(True))
        self.assertIsNone(self.update.parked_reason(False))

    def test_idle_automation_keeps_waiting_thirty_seconds_and_honors_notify_mode(self):
        ready(self.root,B);self.update.cache.update(latestRevision=B,preparedRevision=B,checkedAt=time.time(),phase='ready')
        self.update.settings={**DEFAULTS,'mode':'notify'}
        with patch('software_update.network_status',return_value={'allowed':True,'metered':False}),patch.object(self.update,'install') as install:
            self.update._tick();install.assert_not_called()
            self.update.settings['mode']='idle';self.update.idle_since=time.monotonic()-31
            self.update._tick();install.assert_called_once_with(True,automatic=True)

    def test_health_requires_the_new_launch_token_native_ipc_and_startup_delay(self):
        ready(self.root,B);_,pending=activate(self.root,B,self.baseline)
        with patch.dict(os.environ,{'HUDIY_UPDATE_NONCE':pending['nonce']}):
            self.assertFalse(self.update.healthy()['healthy'])
            self.update.started=time.monotonic()-15
            self.projection.snapshot.return_value['available']=False
            self.assertFalse(self.update.healthy()['healthy'])
            self.projection.snapshot.return_value['available']=True
            self.projection.snapshot.return_value['uiReady']=False
            self.assertFalse(self.update.healthy()['healthy'])
            self.projection.snapshot.return_value['uiReady']=True
            self.assertTrue(self.update.healthy()['healthy'])
        self.assertTrue(read_json(self.root/f"health-{pending['nonce']}.json")['ready'])

    def test_offline_wait_does_not_consume_the_next_online_check_interval(self):
        with patch('software_update.network_status',return_value={'allowed':False}),patch.object(self.update,'request') as request:
            self.update._tick();self.assertEqual(self.update.last_attempt,0);request.assert_not_called()
        with patch('software_update.network_status',return_value={'allowed':True,'metered':False}),patch.object(self.update,'request') as request:
            self.update._tick();request.assert_called_once_with('check')

    def test_cancel_after_worker_finishes_still_pauses_automatic_activation(self):
        self.update.cache.update(latestRevision=B,preparedRevision=B,phase='ready')
        self.update.request('cancel')
        self.assertEqual(self.update.cache['failedRevision'],B)
        self.assertEqual(self.update.cache['phase'],'cancelled')

    def test_shutdown_interruption_can_resume_without_a_false_user_cancel(self):
        self.update.cache['latestRevision']=B;self.update.stop_event.set();self.update.cancel_event.set()
        with patch.object(self.update,'_network'),patch.object(self.update,'_prepare',side_effect=InterruptedError('shutdown')):
            self.update._job('prepare')
        self.assertIsNone(self.update.cache['failedRevision'])
        self.assertIn('shutdown',self.update.cache['message'])

    def test_ui_leaves_verification_phase_when_the_launcher_commits_health(self):
        ready(self.root,B)
        write_json(self.root/'selection.json',{'active':B,'previous':None,'pending':False,'nonce':None})
        self.update.installed=B;self.update.cache.update(phase='verifying',latestRevision=B)
        write_json(self.root/'status.json',{**self.update.cache,'phase':'current','message':'Verified'})
        self.assertEqual(self.update.snapshot()['phase'],'current')

    def test_new_reference_invalidates_an_older_prepared_candidate(self):
        self.update.cache['preparedRevision']=A
        with patch('software_update.download',side_effect=[REF,json.dumps({'status':'ahead'}).encode()]):self.update._check()
        self.assertIsNone(self.update.cache['preparedRevision']);self.assertEqual(self.update.cache['phase'],'available')

    def test_compare_offers_only_newer_application_changes(self):
        app=[{'filename':'implementation/service/server.py'}];docs=[{'filename':'docs/OTA_UPDATES.md'},{'filename':'README.md'}]
        cases=(({'status':'identical'},'current',A,'matches'),({'status':'behind','files':[]},'current',A,'no downgrade'),
               ({'status':'ahead','files':docs},'current',A,'documentation'),({'status':'ahead','files':docs+app},'available',B,'available'),
               ({'status':'ahead','files':[{'filename':'implementation/x','previous_filename':'docs/x'}]},'available',B,'available'),
               ({'status':'ahead','files':[{'filename':'docs/x','previous_filename':'implementation/x'}]},'available',B,'available'),
               ({'status':'ahead','files':[{'filename':f'docs/{i}.md'} for i in range(300)]},'available',B,'available'),
               ({'status':'ahead'},'available',B,'available'),({'status':'diverged','files':docs},'available',B,'diverged'),
               ({'unexpected':True},'available',B,'available'),([],'available',B,'available'))
        for reply,phase,latest,message in cases:
            with self.subTest(reply=reply):
                self.update.cache.update(phase='idle',latestRevision=None,preparedRevision=B,failedRevision=None)
                with patch('software_update.download',side_effect=[REF,json.dumps(reply).encode()]) as get:self.update._check()
                self.assertEqual(get.call_count,2);self.assertEqual(get.call_args_list[1].kwargs['limit'],8*1024*1024)
                self.assertEqual((self.update.cache['phase'],self.update.cache['latestRevision']),(phase,latest))
                self.assertIn(message,self.update.cache['message']);self.assertIsNotNone(self.update.cache['checkedAt'])
                self.assertEqual(self.update.cache['preparedRevision'],B if latest==B else None)
        self.update.cache.update(latestRevision=None,failedRevision=B)
        with patch('software_update.download',side_effect=[REF,ConnectionError('The configured GitHub update source or revision was not found.')]):self.update._check()
        self.assertEqual((self.update.cache['phase'],self.update.cache['latestRevision'],self.update.cache['failedRevision']),('available',B,B))
        with patch('software_update.download',side_effect=[REF,InterruptedError('Update cancelled')]):
            with self.assertRaises(InterruptedError):self.update._check()
        self.update.installed=None
        with patch('software_update.download',side_effect=[REF]) as get:self.update._check()
        self.assertEqual(get.call_count,1);self.assertEqual(self.update.cache['phase'],'available')

    def test_behind_or_docs_only_main_never_prepares_or_installs_an_older_build(self):
        self.update.settings={**DEFAULTS,'mode':'idle'};self.update.cache['checkedAt']=time.time()
        with patch('software_update.download',side_effect=[REF,json.dumps({'status':'behind'}).encode()]):self.update._check()
        with patch('software_update.network_status',return_value={'allowed':True,'metered':False}),patch.object(self.update,'request') as request,patch.object(self.update,'install') as install:
            self.update._tick();request.assert_not_called();install.assert_not_called()
        with self.assertRaisesRegex(ValueError,'already current'):self.update._prepare()

    def test_offline_due_check_still_installs_a_prepared_release_when_idle(self):
        self.update.settings={**DEFAULTS,'mode':'idle','autoCheck':True}
        self.update.cache.update(latestRevision=B,preparedRevision=B,checkedAt=1,phase='ready');self.update.last_attempt=0
        self.update.idle_since=time.monotonic()-31
        with patch('software_update.network_status',return_value={'allowed':False,'message':'offline'}),patch.object(self.update,'request') as request,patch.object(self.update,'install') as install:
            self.update._tick()
        request.assert_not_called();install.assert_called_once_with(True,automatic=True)

    def test_prune_removes_only_unprotected_incomplete_builds_and_stage_leftovers(self):
        C,D,E,F='c'*40,'d'*40,'e'*40,'f'*40;releases=self.root/'releases'
        ready(self.root,B)
        for revision,marker in ((C,C),(D,'d'*39+'0'),(E,E),(F,F)):
            (releases/revision).mkdir(parents=True,exist_ok=True);write_json(releases/revision/'.ota-incomplete.json',{'revision':marker})
        (releases/'.stage-abc123/source').mkdir(parents=True);(releases/'.stage-file').write_text('not a directory')
        (releases/'other').mkdir();write_json(releases/'other/.ota-incomplete.json',{'revision':'other'})
        (releases/('0'*40)).mkdir();(releases/('0'*40)/'notes.txt').write_text('no marker')
        write_json(self.root/'selection.json',{'active':E,'previous':None,'pending':False,'nonce':None});self.update.cache['preparedRevision']=F
        self.update.settings={**DEFAULTS,'keepVersions':3}
        self.update._prune()
        remaining={path.name for path in releases.iterdir()}
        self.assertEqual(remaining,{B,D,E,F,'.stage-file','other','0'*40})
        self.assertEqual(release_path(self.root,B,self.baseline),releases/B)

    def test_rollback_pauses_automatic_reinstallation_of_the_same_new_revision(self):
        ready(self.root,A);ready(self.root,B)
        write_json(self.root/'selection.json',{'active':B,'previous':A,'pending':False,'nonce':None})
        self.update.installed=B;self.update.cache['latestRevision']=B
        self.update.install(True,rollback=True)
        self.assertEqual(self.update.cache['failedRevision'],B)
        self.assertEqual(selection(self.root)['active'],A)

    def test_candidate_is_built_at_its_final_path_before_becoming_ready(self):
        archive=self.base/'fixture.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            for name,body in {'implementation/OTA_PROTOCOL':'1','implementation/service/server.py':'# fixture','implementation/dashboard/package.json':'{}','implementation/dashboard/tests/a.test.mjs':'','implementation/native/CMakeLists.txt':''}.items():
                member=tarfile.TarInfo('coscarOS-'+B+'/'+name);encoded=body.encode();member.size=len(encoded);tar.addfile(member,io.BytesIO(encoded))
        self.update.cache['latestRevision']=B;commands=[]
        def get(url,stream,limit,cancel):stream.write(archive.read_bytes());return 'c'*64
        def run(args,cwd,env,timeout=3600):
            commands.append(list(map(str,args)))
            self.assertTrue(Path(cwd).is_relative_to(self.root/'releases'/B))
            directory=self.root/'releases'/B
            if args[:3]==['npm','run','build']:
                path=directory/'implementation/dashboard/dist/client/index.html';path.parent.mkdir(parents=True);path.write_text('built')
            if args[:2]==['cmake','--build']:
                path=directory/'implementation/native/build/hudiy-car-runtime';path.parent.mkdir(parents=True);path.write_text('built')
        with patch('software_update.download',side_effect=get),patch('software_update.shutil.disk_usage',return_value=Mock(free=5*1024**3)),patch.object(self.update,'_environment',return_value={}),patch.object(self.update,'_run',side_effect=run):
            self.update._prepare()
        self.assertEqual(self.update.cache['preparedRevision'],B)
        self.assertEqual(release_path(self.root,B,self.baseline),self.root/'releases'/B)
        self.assertTrue(any(command[0]=='ctest' for command in commands));self.assertFalse(selection(self.root)['pending'])

    def test_an_incomplete_release_cannot_be_activated_even_with_a_ready_manifest(self):
        path=ready(self.root,B);write_json(path/'.ota-incomplete.json',{'revision':B})
        with self.assertRaises(ValueError):release_path(self.root,B,self.baseline)
        self.assertFalse(selection(self.root)['pending'])

    def test_normal_reinstallation_selects_rebuilt_baseline_and_preserves_previous_copy(self):
        from ota_state import select_rebuilt_baseline
        ready(self.root,B);write_json(self.root/'selection.json',{'active':B,'previous':None,'pending':False,'nonce':None})
        preferences=self.root.parent/'custom-obd.json';preferences.write_text('{"keep":"my sensors"}')
        select_rebuilt_baseline(self.root)
        self.assertIsNone(selection(self.root)['active']);self.assertEqual(selection(self.root)['previous'],B)
        self.assertEqual(preferences.read_text(),'{"keep":"my sensors"}')

    def test_failed_build_never_selects_or_overwrites_the_running_version(self):
        ready(self.root,B);write_json(self.root/'selection.json',{'active':B,'previous':None,'pending':False,'nonce':None})
        self.update.cache['latestRevision']=A
        with patch('software_update.shutil.disk_usage',return_value=Mock(free=0)):
            with self.assertRaises(ValueError):self.update._prepare()
        self.assertEqual(selection(self.root)['active'],B)


class ArchiveAndNetworkTests(unittest.TestCase):
    def test_archive_rejects_escape_links_and_wrong_revision_before_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,link in (('wrong/file',False),('coscarOS-'+B+'/../escape',False),('coscarOS-'+B+'/link',True)):
                archive=root/'source.tgz'
                with tarfile.open(archive,'w:gz') as tar:
                    member=tarfile.TarInfo(name)
                    if link:member.type=tarfile.SYMTYPE;member.linkname='/etc/passwd'
                    tar.addfile(member)
                with self.assertRaises(ValueError):unpack(archive,root/'destination',B)
            self.assertFalse((root/'escape').exists())

    def test_renamed_repository_archive_extracts_and_old_or_foreign_root_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for prefix in ('coscarOS-', 'clean-room-reverse-engeenering-hudiy-', 'other-'):
                archive = root/'source.tgz'
                with tarfile.open(archive, 'w:gz') as tar:
                    member = tarfile.TarInfo(prefix+B+'/README.md'); member.size = 7
                    tar.addfile(member, io.BytesIO(b'fixture'))
                target = root/prefix; target.mkdir()
                if prefix == 'coscarOS-':
                    unpack(archive, target, B)
                    self.assertEqual((target/'README.md').read_bytes(), b'fixture')
                else:
                    with self.assertRaises(ValueError): unpack(archive, target, B)
                    self.assertEqual(list(target.iterdir()), [])

    def test_download_errors_explain_network_or_github_failure_without_claiming_a_build_failed(self):
        import urllib.error
        from software_update import download,API
        for failure,expected in ((urllib.error.HTTPError(API,404,'missing',{},None),'not found'),(urllib.error.HTTPError(API,429,'limited',{},None),'rate limit'),(urllib.error.HTTPError(API,500,'error',{},None),'HTTP 500'),(urllib.error.URLError('private/path'),'Internet access')):
            opener=Mock();opener.open.side_effect=failure
            with patch('software_update.urllib.request.build_opener',return_value=opener):
                with self.assertRaisesRegex(ConnectionError,expected):download(API)

    def test_new_repository_redirect_is_allowed_but_prefix_spoofing_is_not(self):
        import urllib.request
        handler = HTTPSOnly(); request = urllib.request.Request('https://api.github.com/repos/desquerteur/coscarOS/git/ref/heads/main')
        for url in ('https://api.github.com/repos/desquerteur/coscarOS/git/ref/heads/main', 'https://codeload.github.com/desquerteur/coscarOS/tar.gz/'+B, f'https://api.github.com/repos/desquerteur/coscarOS/compare/{A}...{B}'):
            self.assertEqual(handler.redirect_request(request, None, 302, '', {}, url).full_url, url)
        for url in ('https://codeload.github.com/desquerteur/coscarOS-evil/tar.gz/'+B, 'https://api.github.com/repos/desquerteur/coscarOS-evil/git/ref/heads/main', 'https://api.github.com/repositories/1389318512/git/ref/heads/main', 'https://api.github.com/repos/EpicNori/coscarOS/git/ref/heads/main'):
            with self.assertRaises(ValueError): handler.redirect_request(request, None, 302, '', {}, url)

    def test_wired_route_is_allowed_during_wireless_projection_but_shared_wifi_is_not(self):
        projection={'connected':True,'transport':'wifi'}
        def output(args,**kwargs):
            if args[0]=='ip':return '[{"dev":"eth0","metric":10}]'
            return 'ethernet' if 'GENERAL.TYPE' in args else 'no'
        with patch('software_update.subprocess.check_output',side_effect=output):self.assertTrue(network_status(projection)['allowed'])
        def wifi(args,**kwargs):
            if args[0]=='ip':return '[{"dev":"wlan0","metric":10}]'
            return 'wifi' if 'GENERAL.TYPE' in args else 'no'
        with patch('software_update.subprocess.check_output',side_effect=wifi):
            self.assertFalse(network_status(projection)['allowed']);self.assertTrue(network_status({'connected':False})['allowed'])

    def test_redirects_cannot_change_the_update_trust_domain(self):
        import urllib.request
        redirect=HTTPSOnly();request=urllib.request.Request('https://api.github.com/example')
        for url in ('http://codeload.github.com/archive','https://evil.example/archive','file:///etc/passwd','https://codeload.github.com/other/repo/tar.gz/'+B,'https://api.github.com/repos/other/repo/git/ref/heads/main'):
            with self.assertRaises(ValueError):redirect.redirect_request(request,None,302,'',{},url)


class SupervisorTests(unittest.TestCase):
    def fixture(self,health=False,early_exit=False,timeout=False,launch_error=False):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)/'ota';baseline=Path(temporary.name)/'baseline';candidate=ready(root,B)
        _,pending=activate(root,B,baseline);now=[0];launched=[]
        class Process:
            def __init__(self,lifetime):self.until=now[0]+lifetime;self.returncode=None;self.terminated=False
            def poll(self):
                if self.returncode is None and now[0]>=self.until:self.returncode=0
                return self.returncode
            def terminate(self):self.terminated=True;self.returncode=-15
            def kill(self):self.returncode=-9
            def wait(self,timeout=None):return self.returncode
        def launch(path,env):
            launched.append(path)
            if path==candidate:
                if launch_error:raise OSError('bad executable')
                if health:write_json(root/f"health-{pending['nonce']}.json",{'nonce':pending['nonce'],'revision':B,'ready':True})
                return Process(.5 if early_exit else 100 if timeout else 2)
            return Process(.5)
        result=supervise(baseline,root,launch,clock=lambda:now[0],sleep=lambda seconds:now.__setitem__(0,now[0]+seconds),timeout=3,stability=1)
        return root,baseline,candidate,launched,result

    def test_successful_updates_do_not_exhaust_a_lifetime_restart_counter(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'ota';baseline=Path(folder)/'baseline'
            revisions=[character*40 for character in 'bcde']
            for revision in revisions:ready(root,revision)
            now=[0];launched=[]
            class Process:
                def __init__(self):self.until=now[0]+2;self.returncode=None
                def poll(self):
                    if self.returncode is None and now[0]>=self.until:
                        self.returncode=0
                        if len(launched)<=len(revisions):activate(root,revisions[len(launched)-1],baseline)
                    return self.returncode
            def launch(path,env):
                launched.append(path)
                state=selection(root)
                if state['pending']:write_json(root/f"health-{state['nonce']}.json",{'nonce':state['nonce'],'revision':state['active'],'ready':True})
                return Process()
            supervise(baseline,root,launch,clock=lambda:now[0],sleep=lambda seconds:now.__setitem__(0,now[0]+seconds),timeout=3,stability=1)
            self.assertEqual(len(launched),5);self.assertEqual(selection(root)['active'],revisions[-1])

    def test_successful_start_is_committed_and_retains_the_previous_version(self):
        root,base,candidate,launched,result=self.fixture(health=True)
        self.assertEqual(launched,[candidate]);self.assertFalse(selection(root)['pending']);self.assertEqual(selection(root)['active'],B)

    def test_early_crash_restores_baseline(self):
        root,base,candidate,launched,result=self.fixture(early_exit=True)
        self.assertEqual(launched,[candidate,base]);self.assertEqual(selection(root)['active'],None);self.assertEqual(read_json(root/'status.json')['phase'],'rolled-back')

    def test_missing_renderer_health_times_out_and_restores_baseline(self):
        root,base,candidate,launched,result=self.fixture(timeout=True)
        self.assertEqual(launched,[candidate,base]);self.assertEqual(selection(root)['active'],None)

    def test_unlaunchable_candidate_restores_baseline(self):
        root,base,candidate,launched,result=self.fixture(launch_error=True)
        self.assertEqual(launched,[candidate,base]);self.assertFalse(selection(root)['pending'])


if __name__=='__main__':unittest.main()
