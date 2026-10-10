"""Guard the standalone production boundary against reintroducing Hudiy."""
import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from obd import Transport
from runtime_support import field, read_options, save_json
from standalone_projection import StandaloneProjection

ROOT = Path(__file__).resolve().parents[1]


class IndependenceTests(unittest.TestCase):
    def test_legacy_environment_flag_cannot_select_official_runtime(self):
        import server
        previous = os.environ.copy()
        try:
            with patch.dict(os.environ, {'HUDIY_PROJECTION_HOST': '1', 'HUDIY_STANDALONE': '0'}):
                importlib.reload(server)
                self.assertIsInstance(server.projection, StandaloneProjection)
                self.assertFalse(server.projection.enabled)
                self.assertIsNone(server.agent)
                self.assertEqual(server.native_obd.__class__.__name__, 'IndependentOBDSettings')
                self.assertEqual(server.wireless.__class__.__name__, 'IndependentWireless')
                self.assertEqual(server.radio_output.__class__.__name__, 'IndependentAudioRoute')
        finally:
            with patch.dict(os.environ, previous, clear=True):
                importlib.reload(server)

    def test_no_production_client_reads_official_configuration_or_api(self):
        paths = list((ROOT / 'service').glob('*.py')) + list((ROOT / 'launcher').glob('*.py'))
        for path in paths:
            if path.name.startswith('test_') or path.name == 'install_autostart.py':
                continue
            source = path.read_text(encoding='utf-8')
            for forbidden in ('.hudiy/share', '44405', 'HUDIY_PROJECTION_HOST', 'hudiy_equalizer_sink', 'quit_hudiy'):
                with self.subTest(file=path.name, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)
        for relative in ('launcher/hudiy_host.py', 'service/projection.py', 'service/wireless.py', 'service/obd_settings.py'):
            self.assertFalse((ROOT / relative).exists())

    def test_obd_rejects_the_removed_official_transport(self):
        with patch('obd.socket.create_connection') as tcp:
            with self.assertRaises(ValueError):
                Transport('hudiy')
            tcp.assert_not_called()

    def test_private_options_keep_validated_appearance_and_reconnect_choices(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projection.json'
            save_json(path, {'autostart': False, 'taskbarVisible': True, 'dayNight': 'Night', 'darkMode': True})
            options = read_options(path)
            self.assertEqual(options['dayNight'], 'Night')
            self.assertTrue(options['darkMode'])
            save_json(path, {'autostart': 'yes', 'taskbarVisible': 1, 'dayNight': '../../config', 'darkMode': 0})
            options = read_options(path)
            self.assertFalse(options['autostart'])
            self.assertTrue(options['taskbarVisible'])
            self.assertIsNone(options['dayNight'])
            self.assertIsNone(options['darkMode'])

    def test_wire_encoder_is_generic_and_keeps_bluetooth_handshake_fields(self):
        self.assertEqual(field(1, 1), b'\x08\x01')
        self.assertEqual(field(2, 'AA'), b'\x12\x02AA')


if __name__ == '__main__':
    unittest.main()
