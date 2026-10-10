"""Installer tests use fake NetworkManager; no real network is activated."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'launcher/provision_hotspot.py'
spec = importlib.util.spec_from_file_location('hotspot_setup', MODULE)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class FakeNetwork:
    def __init__(self):
        self.saved = []
        self.created = []
        self.deleted = []
        self.supported = True
        self.fail_add = False
        self.fail_delete = False

    def hardware(self):
        if not self.supported: raise setup.SetupError('Unsupported hardware')
        return {'interface': 'wlan0', 'protected5GHzAP': True}

    def profiles(self): return copy.deepcopy(self.saved)

    def profile_secret(self, key):
        return next(profile['802-11-wireless-security']['psk'] for name, profile in self.saved if name == key)

    def add(self, profile):
        if self.fail_add: raise RuntimeError('Denied')
        self.created.append(copy.deepcopy(profile))
        self.saved.append(('/new/profile', copy.deepcopy(profile)))
        return '/new/profile'

    def delete_owned(self, key, profile_uuid):
        if self.fail_delete: raise RuntimeError('Denied')
        actual = next(profile for name, profile in self.saved if name == key)
        if actual['connection']['uuid'] != profile_uuid: raise setup.SetupError('Wrong owner')
        self.deleted.append(profile_uuid)
        self.saved = [(name, profile) for name, profile in self.saved if name != key]


class HotspotSetupTests(unittest.TestCase):
    def prepare(self, network, path):
        return setup.prepare(network, path, ssid='Test car', user='driver', running=lambda: False)

    def test_dry_run_is_read_only_and_does_not_leak_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            network = FakeNetwork(); path = Path(folder) / 'not-created/wireless.json'
            result = setup.inspect(network, path)
            self.assertFalse(result['installed'])
            self.assertFalse(path.parent.exists())
            self.assertEqual(network.created, [])
            self.assertNotIn('passphrase', result)

    def test_fresh_profile_is_inactive_protected_and_matches_private_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            network = FakeNetwork(); path = Path(folder) / 'private/wireless.json'
            result = self.prepare(network, path)
            self.assertTrue(result['changed']); self.assertFalse(result['enabled'])
            data = json.loads(path.read_text()); profile = network.created[0]
            self.assertFalse(profile['connection']['autoconnect'])
            self.assertEqual(profile['connection']['permissions'], ['user:driver:'])
            self.assertEqual(profile['802-11-wireless']['channel'], 36)
            self.assertEqual(profile['802-11-wireless']['band'], 'a')
            self.assertEqual(profile['802-11-wireless-security']['proto'], ['rsn'])
            self.assertEqual(profile['802-11-wireless-security']['pairwise'], ['ccmp'])
            self.assertEqual(profile['802-11-wireless-security']['psk'], data['passphrase'])
            self.assertGreaterEqual(len(data['passphrase']), 24)
            self.assertNotIn(data['passphrase'], json.dumps(result))
            self.assertTrue(setup.inspect(network, path)['installed'])
            if os.name == 'posix':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_repeat_setup_preserves_installed_profile_and_private_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            network = FakeNetwork(); path = Path(folder) / 'wireless.json'
            self.prepare(network, path); original = path.read_bytes()
            result = setup.prepare(network, path, ssid='Another name', running=lambda: True)
            self.assertFalse(result['changed']); self.assertEqual(result['ssid'], 'Test car')
            self.assertEqual(path.read_bytes(), original); self.assertEqual(len(network.created), 1)
            self.assertEqual(network.deleted, [])

    def test_networkmanager_omitted_autoconnect_means_its_true_default(self):
        with tempfile.TemporaryDirectory() as folder:
            network = FakeNetwork(); path = Path(folder) / 'wireless.json'
            self.prepare(network, path)
            data = json.loads(path.read_text()); data['enabled'] = True
            path.write_text(json.dumps(data))
            del network.saved[0][1]['connection']['autoconnect']
            self.assertTrue(setup.inspect(network, path)['enabled'])

    def test_existing_or_duplicate_profile_without_state_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            network = FakeNetwork(); path = Path(folder) / 'wireless.json'
            profile = setup.build_profile('Other car', 'test-password', 'driver', 'c744bcaf-fd21-46c7-891e-a09ce85f022b')
            network.saved = [('/existing', profile)]
            for duplicates in (False, True):
                if duplicates: network.saved.append(('/duplicate', copy.deepcopy(profile)))
                with self.assertRaises(setup.SetupError): self.prepare(network, path)
            self.assertFalse(path.exists()); self.assertEqual(network.created, [])
            self.assertEqual(network.deleted, [])

    def test_missing_profile_and_mismatched_secrets_do_not_change_existing_state(self):
        with tempfile.TemporaryDirectory() as folder:
            network = FakeNetwork(); path = Path(folder) / 'wireless.json'
            self.prepare(network, path); original = path.read_bytes(); profiles = network.saved
            network.saved = []
            with self.assertRaises(setup.SetupError): self.prepare(network, path)
            network.saved = profiles
            network.saved[0][1]['802-11-wireless-security']['psk'] = 'different-password'
            with self.assertRaises(setup.SetupError): self.prepare(network, path)
            self.assertEqual(path.read_bytes(), original); self.assertEqual(len(network.created), 1)

    def test_app_running_or_unsupported_hardware_cannot_create_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            network = FakeNetwork(); path = Path(folder) / 'wireless.json'
            with self.assertRaises(setup.SetupError): setup.prepare(network, path, running=lambda: True)
            network.supported = False
            with self.assertRaises(setup.SetupError): self.prepare(network, path)
            self.assertEqual(network.created, []); self.assertFalse(path.exists())

    def test_save_failure_removes_only_new_uuid_and_reports_failed_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            network = FakeNetwork(); path = Path(folder) / 'wireless.json'
            with patch.object(setup, 'write_state', side_effect=OSError('full')):
                with self.assertRaisesRegex(setup.SetupError, 'removed'): self.prepare(network, path)
                self.assertEqual(network.deleted, [network.created[0]['connection']['uuid']])
                self.assertEqual(network.saved, [])
                network.fail_delete = True
                with self.assertRaisesRegex(setup.SetupError, 'rollback failed'): self.prepare(network, path)
            self.assertFalse(path.exists())

    def test_network_permission_failure_does_not_write_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            network = FakeNetwork(); network.fail_add = True
            path = Path(folder) / 'wireless.json'
            with self.assertRaises(RuntimeError): self.prepare(network, path)
            self.assertFalse(path.exists()); self.assertEqual(network.deleted, [])

    def test_existing_files_are_not_replaced_and_public_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'wireless.json'; path.write_text('keep me')
            with self.assertRaises(setup.SetupError): setup.write_state(path, {})
            self.assertEqual(path.read_text(), 'keep me')
            with self.assertRaises(setup.SetupError): setup.read_state(path)
            path.write_text('x' * 2049)
            with self.assertRaises(setup.SetupError): setup.read_state(path)

    def test_invalid_names_and_keys_cannot_become_settings_or_commands(self):
        for ssid in ('', 'x' * 33, 'ü' * 17, 'bad\nname', 'bad\x7fname', None):
            with self.assertRaises(setup.SetupError): setup.validate_ssid(ssid)
        for secret in ('short', 'x' * 64, 'ü' * 8, 'test\npassword', None):
            with self.assertRaises(setup.SetupError): setup.build_profile('Car', secret, 'driver', 'c744bcaf-fd21-46c7-891e-a09ce85f022b')
        # Punctuation is data over D-Bus, never interpolated into shell commands.
        profile = setup.build_profile('Car;$(whoami)', 'test-password', 'driver', 'c744bcaf-fd21-46c7-891e-a09ce85f022b')
        self.assertEqual(profile['802-11-wireless']['ssid'], b'Car;$(whoami)')


if __name__ == '__main__': unittest.main()
