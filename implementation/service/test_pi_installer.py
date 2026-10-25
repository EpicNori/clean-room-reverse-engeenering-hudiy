"""Fresh-install checks use fixtures/mocks; no privileged operations are run."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
import subprocess
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('pi_installer', Path(__file__).resolve().parents[1] / 'launcher/install_pi.py')
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)


class PiInstallerTests(unittest.TestCase):
    def test_accepts_supported_desktop_and_rejects_root_lite_and_wrong_platforms(self):
        for codename in ('bookworm', 'trixie'):
            installer.validate_platform({'VERSION_CODENAME': codename}, 'aarch64', 'Raspberry Pi 5', True, 1000)
        cases = [('bookworm', 'aarch64', 'Raspberry Pi 5', True, 0),
                 ('bookworm', 'armv7l', 'Raspberry Pi 4', True, 1000),
                 ('bookworm', 'aarch64', 'Other board', True, 1000),
                 ('trixie', 'aarch64', 'Raspberry Pi 5', False, 1000),
                 ('bullseye', 'aarch64', 'Raspberry Pi 5', True, 1000)]
        for version, arch, model, desktop, uid in cases:
            with self.assertRaises(installer.InstallError):
                installer.validate_platform({'VERSION_CODENAME': version}, arch, model, desktop, uid)

    @unittest.skipUnless(hasattr(os, 'openpty'), 'Real terminal regression requires a POSIX pseudo-terminal')
    def test_confirmation_reads_a_real_non_seekable_terminal_without_standard_input(self):
        import contextlib
        for answer, expected in ((b'yes\n', True), (b'y\n', True), (b'no\n', False), (b'\n', False)):
            with self.subTest(answer=answer):
                master, slave = os.openpty()
                try:
                    os.write(master, answer)
                    with contextlib.redirect_stdout(io.StringIO()) as output:
                        actual = installer.confirm_installation(os.ttyname(slave))
                    self.assertIs(actual, expected)
                    self.assertIn('Apply this installation plan?', output.getvalue())
                finally:
                    os.close(master); os.close(slave)

    def test_unavailable_terminal_explains_the_explicit_noninteractive_option(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(installer.InstallError, '--yes'):
                installer.confirm_installation(str(Path(folder)/'no-terminal'))

    def test_memory_limit_avoids_high_parallelism_on_small_boards(self):
        self.assertEqual(installer.jobs_for_memory(2 * 1024 ** 2), 1)
        self.assertEqual(installer.jobs_for_memory(4 * 1024 ** 2), 2)
        self.assertEqual(installer.jobs_for_memory(16 * 1024 ** 2), 2)

    def test_manifest_selects_one_official_arm64_release(self):
        digest = 'a' * 64
        manifest = digest + '  node-v22.1.2-linux-arm64.tar.xz\n' + 'b' * 64 + '  node-v22.1.2-linux-x64.tar.xz\n'
        self.assertEqual(installer.choose_node(manifest), ('node-v22.1.2-linux-arm64.tar.xz', digest))
        for invalid in ('', 'a' * 63 + '  node-v22.1.2-linux-arm64.tar.xz',
                        digest + '  ../../node-v22.1.2-linux-arm64.tar.xz', manifest + manifest):
            with self.assertRaises(installer.InstallError): installer.choose_node(invalid)

    def test_checksum_failure_prevents_using_the_download(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'archive'; path.write_bytes(b'fixture')
            installer.verify_archive(path, hashlib.sha256(b'fixture').hexdigest())
            with self.assertRaises(installer.InstallError): installer.verify_archive(path, 'a' * 64)

    def archive(self, folder, entries):
        path = Path(folder) / 'fixture.tar.xz'
        with tarfile.open(path, 'w:xz') as target:
            for name, kind, value in entries:
                entry = tarfile.TarInfo(name); entry.mode = 0o755
                if kind == 'symlink': entry.type = tarfile.SYMTYPE; entry.linkname = value; target.addfile(entry)
                elif kind == 'device': entry.type = tarfile.CHRTYPE; target.addfile(entry)
                else:
                    entry.size = len(value); target.addfile(entry, io.BytesIO(value))
        return path

    def test_valid_archive_preserves_internal_npm_link(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = 'node-v22.1.2-linux-arm64'
            archive = self.archive(folder, [(prefix + '/bin/node', 'file', b'fixture'),
                (prefix + '/lib/node_modules/npm/bin/npm-cli.js', 'file', b'npm'),
                (prefix + '/bin/npm', 'symlink', '../lib/node_modules/npm/bin/npm-cli.js')])
            target = Path(folder) / 'output'; target.mkdir()
            try: installer.extract_node(archive, target, prefix)
            except OSError as error:
                if os.name == 'nt' and getattr(error, 'winerror', None) == 1314: self.skipTest('Windows lacks symlink permission')
                raise
            self.assertEqual((target / prefix / 'bin/npm').read_bytes(), b'npm')

    def test_malicious_archive_cannot_escape_or_write_through_links(self):
        prefix = 'node-v22.1.2-linux-arm64'
        cases = [[('../outside', 'file', b'bad')], [('/absolute', 'file', b'bad')],
                 [(prefix + '/escape', 'symlink', '/outside')],
                 [(prefix + '/bin/escape', 'symlink', '../../../outside')],
                 [(prefix + '/device', 'device', '')],
                 [(prefix + '/link', 'symlink', 'inside'), (prefix + '/link/file', 'file', b'bad')]]
        for entries in cases:
            with tempfile.TemporaryDirectory() as folder:
                archive = self.archive(folder, entries); target = Path(folder) / 'output'; target.mkdir()
                with self.assertRaises(installer.InstallError): installer.extract_node(archive, target, prefix)
                self.assertEqual(list(target.iterdir()), [])

    def test_wireplumber_versions_get_their_own_configuration_format(self):
        lua, content = installer.audio_configuration('Compiled with libwireplumber 0.4.13')
        self.assertIn('bluetooth.lua.d', lua); self.assertIn('bluez_monitor.properties', content)
        conf, content = installer.audio_configuration('WirePlumber 0.5.8')
        self.assertIn('wireplumber.conf.d', conf); self.assertIn('monitor.bluez.properties', content)
        self.assertIn('"ofono"', content)
        with self.assertRaises(installer.InstallError): installer.audio_configuration('unknown')

    def test_user_configuration_is_idempotent_and_keeps_a_previous_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'configuration.conf'
            path.write_text('old')
            installer.write_user_file(path, 'new'); installer.write_user_file(path, 'new')
            self.assertEqual(path.read_text(), 'new')
            backups = list(Path(folder).glob('*.backup-*'))
            self.assertEqual(len(backups), 1); self.assertEqual(backups[0].read_text(), 'old')

    def test_check_and_running_app_cannot_run_install_commands(self):
        with patch.object(installer, 'preflight', return_value=({'VERSION_CODENAME': 'trixie'}, True)), \
             patch.object(installer, 'run') as run, patch.object(installer.sys, 'argv', ['installer', '--check']):
            self.assertEqual(installer.main(), 0); run.assert_not_called()
        with patch.object(installer, 'preflight', return_value=({'VERSION_CODENAME': 'trixie'}, True)), \
             patch.object(installer, 'run') as run, patch.object(installer.sys, 'argv', ['installer', '--yes']):
            self.assertEqual(installer.main(), 1); run.assert_not_called()

    @unittest.skipUnless(os.name == 'posix', 'Apply-flow fixtures need Linux file locks')
    def test_mocked_install_keeps_builds_unprivileged_and_respects_options(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(installer, 'preflight', return_value=({'VERSION_CODENAME': 'bookworm'}, False)), \
             patch.object(installer.Path, 'home', return_value=Path(folder)), \
             patch.object(installer, 'node_runtime', return_value=dict(os.environ)), \
             patch.object(installer.subprocess, 'check_output', return_value='WirePlumber 0.4.13'), \
             patch.object(installer, 'run') as run, \
             patch.object(installer.sys, 'path', [str(Path(__file__).resolve().parents[1] / 'launcher'), *installer.sys.path]), \
             patch.object(installer.sys, 'argv', ['installer', '--yes', '--skip-hotspot', '--no-autologin']):
            self.assertEqual(installer.main(), 0)
            commands = [list(map(str, call.args[0])) for call in run.call_args_list]
            build = next(command for command in commands if command[:2] == ['cmake', '--build'])
            self.assertNotIn('sudo', build)
            system = next(command for command in commands if any(part.endswith('/install_pi_system.py') for part in command))
            self.assertEqual(system[0], 'sudo'); self.assertIn('--no-autologin', system)
            self.assertTrue((Path(folder) / '.config/wireplumber/bluetooth.lua.d/90-hudiy-recreation.lua').is_file())
            self.assertFalse((Path(folder) / '.local/share/hudiy-recreation/wireless.json').exists())

    @unittest.skipUnless(os.name == 'posix', 'Apply-flow fixtures need Linux file locks')
    def test_failed_native_build_does_not_select_startup_or_change_system_configuration(self):
        def command(arguments, **kwargs):
            if list(map(str, arguments))[:2] == ['cmake', '--build']:
                raise subprocess.CalledProcessError(2, ['cmake', '--build'])
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(installer, 'preflight', return_value=({'VERSION_CODENAME': 'bookworm'}, False)), \
             patch.object(installer.Path, 'home', return_value=Path(folder)), \
             patch.object(installer, 'node_runtime', return_value=dict(os.environ)), \
             patch.object(installer, 'run', side_effect=command) as run, \
             patch.object(installer.sys, 'path', [str(Path(__file__).resolve().parents[1] / 'launcher'), *installer.sys.path]), \
             patch.object(installer.sys, 'argv', ['installer', '--yes']):
            self.assertEqual(installer.main(), 1)
            commands = [list(map(str, call.args[0])) for call in run.call_args_list]
            self.assertFalse(any(any(part.endswith('/install_pi_system.py') for part in command) for command in commands))
            self.assertFalse(any(any(part.endswith('/install_autostart.py') for part in command) for command in commands))
            self.assertFalse((Path(folder) / '.config').exists())


if __name__ == '__main__': unittest.main()
