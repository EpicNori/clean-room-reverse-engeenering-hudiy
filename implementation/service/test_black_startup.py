import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from runtime_support import read_options
from standalone_projection import StandaloneProjection

LAUNCHER=Path(__file__).resolve().parents[1]/'launcher'
def module(name):
    spec=importlib.util.spec_from_file_location('test_boot_'+name,LAUNCHER/(name+'.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
boot=module('install_black_boot');session=module('session');startup=module('install_autostart');launcher=module('launcher')

class Runner:
    def __init__(self):self.theme='pix';self.commands=[];self.fail=False
    def __call__(self,command):
        self.commands.append(command)
        if len(command)>1:
            if self.fail:self.fail=False;raise RuntimeError('initramfs failed')
            self.theme=command[-1]
        return self.theme

class BlackStartupTests(unittest.TestCase):
    def fixture(self,folder):
        root=Path(folder);firmware=root/'boot/firmware';firmware.mkdir(parents=True)
        (firmware/'config.txt').write_text('[all]\ndtoverlay=vc4-kms-v3d\n')
        (firmware/'cmdline.txt').write_text('root=PARTUUID=fixture console=serial0,115200 console=tty1 rootwait video=HDMI-A-1:1280x720@60\n')
        runner=Runner();manager=boot.BlackBoot(root,runner)
        return manager,runner,firmware

    def test_quiet_cmdline_preserves_root_serial_and_display_and_is_single_line_idempotent(self):
        source='root=PARTUUID=fixture console=serial0,115200 console=tty1 rootwait quiet loglevel=7 video=HDMI-A-1:1280x720@60\n'
        result=boot.quiet_cmdline(source)
        for value in ('root=PARTUUID=fixture','console=serial0,115200','console=tty3','rootwait','video=HDMI-A-1:1280x720@60','loglevel=3','logo.nologo'):
            self.assertIn(value,result)
        self.assertNotIn('console=tty1',result);self.assertNotIn('loglevel=7',result)
        self.assertEqual(result,boot.quiet_cmdline(result));self.assertEqual(result.count('\n'),1)
        for source in ('root=fixture\nsecond=line\n','console=tty1\n',''):
            with self.assertRaises(ValueError):boot.quiet_cmdline(source)

    def test_firmware_block_does_not_replace_display_overlays_and_is_idempotent(self):
        result=boot.firmware_config('[pi5]\ndtoverlay=example\n')
        self.assertIn('[pi5]\ndtoverlay=example',result)
        self.assertIn('[all]\ndisable_splash=1',result)
        self.assertEqual(result,boot.firmware_config(result))
        with self.assertRaises(ValueError):boot.firmware_config(boot.BEGIN)

    def test_apply_backup_idempotence_and_restore_recover_exact_originals(self):
        with tempfile.TemporaryDirectory() as folder:
            manager,runner,firmware=self.fixture(folder)
            original={p.name:p.read_bytes() for p in firmware.iterdir()}
            self.assertTrue(manager.apply(Path('/home/driver/source/implementation/launcher/session.py')))
            self.assertEqual(runner.theme,boot.THEME)
            count=len(runner.commands)
            self.assertFalse(manager.apply(Path('/home/driver/source/implementation/launcher/session.py')))
            self.assertEqual(count,len(runner.commands))
            self.assertTrue(manager.restore());self.assertEqual(runner.theme,'pix')
            self.assertFalse(manager.manifest.exists())
            for name,data in original.items():self.assertEqual((firmware/name).read_bytes(),data)
            self.assertFalse((Path(folder)/'etc/lightdm/lightdm.conf.d/99-hudiy-recreation-session.conf').exists())
            self.assertTrue(manager.manifest.with_name('black-boot.restored.json').exists())

    def legacy_branding(self, manager):
        import hashlib
        state = manager._load()
        for name, saved in state['files'].items():
            path = manager.root/name
            data = path.read_bytes().replace(b'Name=coscarOS black startup', b'Name=Hudiy black startup').replace(b'Name=coscarOS', b'Name=Hudiy recreation').replace(b'# coscarOS dedicated session;', b'# Hudiy dedicated session;')
            path.write_bytes(data)
            saved['installed'] = hashlib.sha256(data).hexdigest()
        boot.atomic(manager.manifest, json.dumps(state).encode(), 0o600)
        return state

    def test_branding_upgrade_retains_restore_backups_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            manager, runner, firmware = self.fixture(folder)
            original = (firmware/'config.txt').read_bytes()
            launcher = Path('/source/session.py')
            manager.apply(launcher)
            before = self.legacy_branding(manager)
            self.assertTrue(manager.apply(launcher))
            after = manager._load()
            for name in before['files']:
                self.assertEqual(before['files'][name]['before'], after['files'][name]['before'])
                self.assertEqual(before['files'][name]['mode'], after['files'][name]['mode'])
            self.assertIn('Name=coscarOS', (manager.root/'usr/share/wayland-sessions/hudiy-recreation.desktop').read_text())
            self.assertFalse(manager.apply(launcher))
            manager.restore()
            self.assertEqual((firmware/'config.txt').read_bytes(), original)
            self.assertEqual(runner.theme, 'pix')

    def test_branding_upgrade_failure_restores_old_install_and_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            manager, runner, _ = self.fixture(folder)
            launcher = Path('/source/session.py'); manager.apply(launcher)
            self.legacy_branding(manager)
            manifest = manager.manifest.read_bytes()
            before = {name: (manager.root/name).read_bytes() for name in manager._load()['files']}
            runner.fail = True
            with self.assertRaises(RuntimeError): manager.apply(launcher)
            self.assertEqual(manager.manifest.read_bytes(), manifest)
            for name, data in before.items(): self.assertEqual((manager.root/name).read_bytes(), data)
            manager._verify(manager._load())

    def test_branding_upgrade_refuses_admin_changes_and_new_launcher(self):
        with tempfile.TemporaryDirectory() as folder:
            manager, _, firmware = self.fixture(folder)
            launcher = Path('/source/session.py'); manager.apply(launcher)
            self.legacy_branding(manager)
            with self.assertRaises(ValueError): manager.apply(Path('/other/session.py'))
            path = firmware/'config.txt'; path.write_text(path.read_text()+'# admin change\n')
            before = path.read_bytes()
            with self.assertRaises(ValueError): manager.apply(launcher)
            self.assertEqual(path.read_bytes(), before)

    def test_failed_initramfs_update_rolls_back_system_files_and_theme(self):
        with tempfile.TemporaryDirectory() as folder:
            manager,runner,firmware=self.fixture(folder)
            original=(firmware/'cmdline.txt').read_bytes();runner.fail=True
            with self.assertRaises(RuntimeError):manager.apply(Path('/source/session.py'))
            self.assertEqual((firmware/'cmdline.txt').read_bytes(),original)
            self.assertEqual(runner.theme,'pix');self.assertFalse(manager.manifest.exists())

    def test_restore_refuses_admin_changes_in_files_or_theme(self):
        with tempfile.TemporaryDirectory() as folder:
            manager,runner,firmware=self.fixture(folder);manager.apply(Path('/source/session.py'))
            path=firmware/'cmdline.txt';saved=path.read_bytes();path.write_text('root=admin\n')
            with self.assertRaises(ValueError):manager.restore()
            self.assertEqual(path.read_text(),'root=admin\n')
            path.write_bytes(saved);runner.theme='admin-theme'
            with self.assertRaises(ValueError):manager.restore()
            self.assertTrue(manager.manifest.exists())

    def test_changed_install_target_requires_explicit_restore_and_manual_login_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            manager,_,_=self.fixture(folder);manager.apply(Path('/source/session.py'),False)
            self.assertFalse((Path(folder)/'etc/lightdm/lightdm.conf.d/99-hudiy-recreation-session.conf').exists())
            with self.assertRaises(ValueError):manager.apply(Path('/different/session.py'),False)

    def test_fixed_session_entry_keeps_special_paths_out_of_shell_arguments(self):
        files=boot.managed_files('[all]\n','root=fixture\n',Path('/home/driver/car software/100%/session.py'))
        entry=files['usr/share/wayland-sessions/hudiy-recreation.desktop']
        self.assertIn('Exec=/usr/bin/python3 /usr/lib/coscaros/session.py\n',entry)
        self.assertNotIn('car software',entry)
        self.assertIn(repr('/home/driver/car software/100%/session.py'),files[boot.SESSION_WRAPPER])
        with self.assertRaises(ValueError):boot.desktop_quote('/source\nExec=bad')
        with self.assertRaises(ValueError):boot.checked_path(Path('/fixture'),'../../outside')

    def legacy_session(self, manager, target):
        import hashlib
        state=manager._load()
        (manager.root/boot.SESSION_WRAPPER).unlink()
        del state['files'][boot.SESSION_WRAPPER]
        name='usr/share/wayland-sessions/hudiy-recreation.desktop'
        path=manager.root/name
        path.write_bytes(path.read_text().replace('Exec=/usr/bin/python3 /'+boot.SESSION_WRAPPER,
            'Exec=/usr/bin/python3 '+boot.desktop_quote(target.as_posix())).encode())
        state['files'][name]['installed']=hashlib.sha256(path.read_bytes()).hexdigest()
        boot.atomic(manager.manifest,json.dumps(state).encode(),0o600)

    def test_legacy_session_upgrade_preserves_originals_and_restores_added_wrapper(self):
        with tempfile.TemporaryDirectory() as folder:
            manager,_,_=self.fixture(folder);target=Path('/source with spaces/100%/session.py')
            manager.apply(target);self.legacy_session(manager,target)
            before=manager._load()
            with self.assertRaises(ValueError):manager.apply(Path('/other/session.py'))
            self.assertTrue(manager.apply(target));self.assertFalse(manager.apply(target))
            for name,saved in before['files'].items():
                self.assertEqual(saved['before'],manager._load()['files'][name]['before'])
            manager.restore();self.assertFalse((manager.root/boot.SESSION_WRAPPER).exists())

    def test_legacy_session_upgrade_failure_rolls_back_and_refuses_unmanaged_wrapper(self):
        with tempfile.TemporaryDirectory() as folder:
            manager,runner,_=self.fixture(folder);target=Path('/source/session.py')
            manager.apply(target);self.legacy_session(manager,target)
            before=manager.manifest.read_bytes();runner.fail=True
            with self.assertRaises(RuntimeError):manager.apply(target)
            self.assertEqual(before,manager.manifest.read_bytes())
            self.assertFalse((manager.root/boot.SESSION_WRAPPER).exists())
            manager._verify(manager._load())
            wrapper=manager.root/boot.SESSION_WRAPPER;wrapper.write_text('administrator')
            with self.assertRaises(ValueError):manager.apply(target)
            self.assertEqual(wrapper.read_text(),'administrator')

    @unittest.skipUnless(__import__('os').name=='posix','Debian Xsession uses POSIX shell word splitting')
    def test_session_entry_survives_real_xsession_word_splitting(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'source with spaces'/'100%'/'session.py'
            target.parent.mkdir(parents=True)
            target.write_text('print("SESSION_STARTED")')
            files=boot.managed_files('[all]\n','root=fixture\n',target)
            wrapper=root/'wrapper.py';wrapper.write_text(files[boot.SESSION_WRAPPER])
            entry=files['usr/share/wayland-sessions/hudiy-recreation.desktop']
            command=next(line[5:] for line in entry.splitlines() if line.startswith('Exec='))
            command=command.replace('/usr/bin/python3',sys.executable).replace('/'+boot.SESSION_WRAPPER,str(wrapper))
            result=subprocess.run(['/bin/sh','-c','STARTUP=$1; exec $STARTUP','xsession',command],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),'SESSION_STARTED')

    def test_lightdm_main_config_overrides_only_session_and_delay_preserving_authentication(self):
        source='[LightDM]\nlogind-check-graphical=true\n[Seat:*]\nautologin-user=driver\nautologin-session=LXDE-pi-labwc\nautologin-user-timeout=5\n[Seat:seat1]\nautologin-session=other\n'
        result=boot.lightdm_session(source)
        self.assertIn('autologin-user=driver',result)
        self.assertIn('autologin-session=hudiy-recreation',result)
        self.assertIn('autologin-user-timeout=0',result)
        self.assertIn('[Seat:seat1]\nautologin-session=other',result)
        self.assertEqual(result,boot.lightdm_session(result))

    def test_panel_free_session_and_opt_out_choose_separate_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'.config/hudiy-recreation/labwc';config.mkdir(parents=True)
            with self.assertRaises(RuntimeError):session.session_command(folder,{}, {})
            (config/'autostart').write_text('');(config/'rc.xml').write_text('<labwc_config/>')
            command=session.session_command(folder,{}, {'DBUS_SESSION_BUS_ADDRESS':'fixture'})
            self.assertEqual(command[:2],['/usr/bin/labwc','--config-dir']);self.assertNotIn('-m',command)
            command=session.session_command(folder,{'blackStartup':False},{})
            self.assertEqual(command,['/usr/bin/dbus-run-session','--','/usr/bin/labwc','-m'])

    def test_generated_car_startup_has_no_panel_or_desktop_and_recovery_does_not_restart_hudiy(self):
        launch=Path('/home/driver/car software/launcher.py');log=Path('/home/driver/app.log')
        original='#!/bin/sh\nnetwork-agent &\n'
        entry=startup.replace_startup(original,launch,log)
        car=startup.car_session_startup(launch,log)
        self.assertIn('--boot-session',car);self.assertNotIn('wf-panel-pi',car);self.assertNotIn('pcmanfm',car)
        recovery=startup.recovery_startup(entry,'#!/bin/sh\nwf-panel-pi &\npcmanfm --desktop &\n')
        self.assertIn('network-agent &',recovery);self.assertIn('wf-panel-pi &',recovery)
        self.assertNotIn('launcher.py',recovery);self.assertNotIn(startup.BEGIN,recovery)

    def test_desktop_recovery_runs_only_our_saved_user_script(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(launcher.subprocess,'Popen') as popen:
            self.assertFalse(launcher.restore_desktop(folder));popen.assert_not_called()
            path=Path(folder)/'.config/hudiy-recreation/labwc/desktop-recovery';path.parent.mkdir(parents=True);path.write_text('#!/bin/sh\n')
            self.assertTrue(launcher.restore_desktop(folder))
            self.assertEqual(popen.call_args.args[0],['/bin/sh',str(path)])

    def test_projection_ready_command_and_preference_are_validated_and_durable(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'projection.json';projection=StandaloneProjection(preferences=path)
            projection.enabled=projection.available=True;projection.sock=Mock()
            projection.settings({'blackStartup':False})
            self.assertFalse(read_options(path)['blackStartup'])
            for value in ('yes',0,None):
                with self.assertRaises(ValueError):projection.settings({'blackStartup':value})
            projection.startup_ready('content','a'*32)
            self.assertEqual(json.loads(projection.sock.sendall.call_args.args[0]),{'operation':'startup-ready','surface':'content','token':'a'*32})
            for surface,token in [('other','a'*32),('content','../file'),('taskbar',None)]:
                with self.assertRaises(ValueError):projection.startup_ready(surface,token)
            self.assertFalse(projection.snapshot()['uiReady'])

if __name__=='__main__':unittest.main()
