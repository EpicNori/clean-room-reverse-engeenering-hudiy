import copy
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from layout import LayoutStore, validate_layout, DEFAULT_LAYOUT


class LayoutTests(unittest.TestCase):
    def test_catalog_upgrade_keeps_existing_shortcuts_and_order(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'layout.json'
            old = copy.deepcopy(DEFAULT_LAYOUT)
            old['taskbar'].insert(2, 'contacts')
            old['menus']['System'] = ['about', 'overlays', 'notification-settings', 'application', 'appearance', 'theme']
            path.write_text(__import__('json').dumps(old))
            restored = LayoutStore(True, path).snapshot()
            self.assertEqual(restored['taskbar'], old['taskbar'])
            self.assertEqual(restored['menus']['System'], old['menus']['System'] + ['music-settings', 'contacts-settings'])

    def test_save_flushes_data_before_reporting_success(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('projection.os.fsync', wraps=os.fsync) as sync:
                LayoutStore(True, Path(folder) / 'layout.json').save(DEFAULT_LAYOUT)
                self.assertEqual(sync.call_count, 2 if os.name == 'posix' else 1)

    def test_saved_layout_survives_new_service_instance_and_is_private(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'preferences/layout.json'
            store = LayoutStore(True, path)
            custom = copy.deepcopy(DEFAULT_LAYOUT)
            custom['taskbar'].insert(2, 'contacts')
            custom['columns'] = ['phone', 'clock-navigation', 'music']
            custom['menus']['Phone'].reverse()
            store.save(custom)
            self.assertEqual(LayoutStore(True, path).snapshot(), custom)
            if os.name != 'nt': self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertFalse(path.with_name('layout.json.tmp').exists())
            result = store.snapshot()
            result['taskbar'].clear()
            self.assertEqual(store.snapshot(), custom)

    def test_invalid_routes_duplicates_and_missing_navigation_are_rejected(self):
        for bad in ('https://example.com', '../contacts', 'shell', [], {}):
            custom = copy.deepcopy(DEFAULT_LAYOUT)
            custom['taskbar'].append(bad)
            with self.assertRaises(ValueError): validate_layout(custom)
        for ids in (['contacts'], ['dashboard', 'apps', 'android-resume', 'apps']):
            custom = copy.deepcopy(DEFAULT_LAYOUT)
            custom['taskbar'] = ids
            with self.assertRaises(ValueError): validate_layout(custom)
        with self.assertRaises(ValueError): validate_layout({**DEFAULT_LAYOUT, 'path': '/etc/passwd'})

    def test_corrupt_storage_falls_back_to_complete_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'layout.json'
            path.write_text('{broken')
            self.assertEqual(LayoutStore(True, path).snapshot(), DEFAULT_LAYOUT)
            path.write_text('x' * 4097)
            self.assertEqual(LayoutStore(True, path).snapshot(), DEFAULT_LAYOUT)
        with self.assertRaises(ConnectionError): LayoutStore(False).save(DEFAULT_LAYOUT)
