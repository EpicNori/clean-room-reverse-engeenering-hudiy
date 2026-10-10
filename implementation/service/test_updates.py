from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from threading import Event
from updates import UpdateSettings, validate_updates, DEFAULTS


class UpdateTests(unittest.TestCase):
    def test_intervals_apply_live_and_survive_service_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'updates.json'
            music = SimpleNamespace(enabled=True)
            contacts = SimpleNamespace(wake=Event())
            settings = UpdateSettings(music, contacts, path)
            settings.save({'musicRefreshSeconds': 2})
            settings.save({'contactsRefreshSeconds': 120})
            self.assertEqual(music.refresh_interval, 2)
            self.assertEqual(contacts.refresh_interval, 120)
            self.assertTrue(contacts.wake.is_set())
            self.assertEqual(UpdateSettings(music, contacts, path).snapshot(),
                             {'musicRefreshSeconds': 2, 'contactsRefreshSeconds': 120})

    def test_invalid_values_and_unexpected_fields_are_rejected(self):
        for key, invalid in [('musicRefreshSeconds', v) for v in (0, 61, True, '5', 2.5, None)] + [('contactsRefreshSeconds', v) for v in (4, 3601)]:
            with self.assertRaises(ValueError): validate_updates({key: invalid})
        for value in ({}, [], {'path': '/etc/passwd'}, {'musicRefreshSeconds': 5, 'shell': 'reboot'}):
            with self.assertRaises(ValueError): validate_updates(value)

    def test_corrupt_storage_defaults_and_disabled_host_cannot_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'updates.json'
            path.write_text('{broken')
            settings = UpdateSettings(SimpleNamespace(enabled=True), SimpleNamespace(wake=Event()), path)
            self.assertEqual(settings.snapshot(), DEFAULTS)
        disabled = UpdateSettings(SimpleNamespace(enabled=False), SimpleNamespace(wake=Event()))
        with self.assertRaises(ConnectionError): disabled.save({'musicRefreshSeconds': 1})
