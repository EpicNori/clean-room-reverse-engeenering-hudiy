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
            old['menus']['System'] = ['about', 'notification-settings', 'application', 'appearance', 'theme']
            path.write_text(__import__('json').dumps(old))
            restored = LayoutStore(True, path).snapshot()
            self.assertEqual(restored['taskbar'], old['taskbar'])
            self.assertEqual(restored['menus']['System'], old['menus']['System'] + ['dashboard-editor', 'software-update'])

    def test_previous_catalog_moves_tiles_and_drops_placeholders_without_losing_order(self):
        old = copy.deepcopy(DEFAULT_LAYOUT)
        old['taskbar'][2:2] = ['contacts', 'autobox-wifi', 'notifications']
        old['menus'] = {
            'Phone': ['notifications', 'dialpad', 'contacts', 'favorites', 'call-log', 'active-call'],
            'Music': ['storage', 'radio', 'a2dp', 'autobox-music', 'android-music'],
            'Android Auto': ['android-usb', 'android-wifi', 'android-resume', 'android-quit'],
            'Autobox': ['autobox-wifi', 'autobox-resume'],
            'Hudiy': ['obd-logs', 'custom-obd', 'active-apps', 'settings', 'quit', 'obd-charts', 'obd-blocks', 'combined', 'gauges', 'gauges-2', 'marketplace'],
            'System': ['dashboard-editor', 'theme', 'appearance', 'application', 'notification-settings', 'overlays', 'about', 'music-settings', 'contacts-settings', 'software-update'],
            'Projections': ['android-settings', 'autobox-settings'],
            'Audio': ['sound', 'audio-input', 'equalizer', 'presets'],
            'Bluetooth': ['pair', 'remove', 'bluetooth-connections'],
        }
        result = validate_layout(old)
        self.assertEqual(result['taskbar'][:4], ['dashboard', 'apps', 'contacts', 'mute'])
        self.assertEqual(result['menus']['Phone'], ['dialpad', 'contacts', 'favorites', 'call-log', 'active-call'])
        self.assertEqual(result['menus']['Vehicle'], ['obd-logs', 'custom-obd', 'obd-charts', 'obd-blocks', 'combined', 'gauges', 'gauges-2', 'obd-settings'])
        self.assertEqual(result['menus']['Hudiy'], ['settings', 'quit', 'marketplace'])
        self.assertEqual(result['menus']['Audio'][-1], 'music-settings')
        self.assertEqual(result['menus']['Bluetooth'][-1], 'contacts-settings')
        self.assertNotIn('Autobox', result['menus'])
        old['menus']['Hudiy'].append('shell')
        with self.assertRaises(ValueError): validate_layout(old)

    def test_legacy_pair_and_remove_shortcuts_open_the_unified_bluetooth_screen(self):
        old = copy.deepcopy(DEFAULT_LAYOUT)
        old['taskbar'][2:2] = ['pair', 'remove']
        old['menus']['Bluetooth'] = ['remove', 'pair', 'bluetooth-connections', 'contacts-settings']
        result = validate_layout(old)
        self.assertEqual(result['taskbar'][:3], ['dashboard', 'apps', 'bluetooth-connections'])
        self.assertEqual(result['taskbar'].count('bluetooth-connections'), 1)
        self.assertEqual(result['menus']['Bluetooth'], ['bluetooth-connections', 'contacts-settings'])

    def test_save_flushes_data_before_reporting_success(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('runtime_support.os.fsync', wraps=os.fsync) as sync:
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
