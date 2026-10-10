import time
import unittest
from unittest.mock import Mock, patch
from obd import OBD

PORT = 'bluetooth://11:22:33:44:55:66/2'
FRAMES = {'0104': '41 04 80', '0105': '41 05 7D', '010C': '41 0C 1A F8',
          '010D': '41 0D 64', '0111': '41 11 40', '0142': '41 42 37 78'}


def transport():
    result = Mock()
    result.query.side_effect = lambda command: 'ELM327' if command == 'ATZ' else FRAMES.get(command, 'OK')
    return result


class AutomaticOBDTests(unittest.TestCase):
    def wait_values(self, obd):
        deadline = time.monotonic() + 2
        while not obd.snapshot()['values'] and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(obd.snapshot()['values']['rpm'], 1726)
        self.assertEqual(obd.snapshot()['values']['speed'], 100)

    def test_owned_transport_reads_and_disconnect_clears_stale_data(self):
        settings = Mock()
        settings.port.return_value = ''
        obd = OBD()
        with patch('obd.Transport', side_effect=lambda port: transport()) as opened:
            try:
                obd.start_independent(settings)
                obd._automatic_tick()
                opened.assert_not_called()
                settings.port.return_value = PORT
                obd._automatic_tick()
                self.wait_values(obd)
                opened.assert_called_once_with(PORT)
                settings.port.return_value = ''
                obd._automatic_tick()
                state = obd.snapshot()
                self.assertFalse(state['connected'])
                self.assertEqual(state['values'], {})
                self.assertEqual(state['history'], [])
                self.assertIsNone(state['timestamp'])
                settings.port.return_value = PORT
                obd.retry_at = 0
                obd._automatic_tick()
                self.wait_values(obd)
                self.assertEqual(opened.call_count, 2)
            finally:
                obd.close()
        self.assertFalse(obd.supervisor.is_alive())
        self.assertIsNone(obd.worker)

    def test_stop_suppresses_reconnect_and_manual_bluetooth_read_restores_it(self):
        settings = Mock()
        settings.port.return_value = ''
        obd = OBD()
        with patch('obd.Transport', side_effect=lambda port: transport()) as opened:
            try:
                obd.start_independent(settings)
                settings.port.return_value = PORT
                obd._automatic_tick()
                self.wait_values(obd)
                obd.disconnect()
                opened.reset_mock()
                obd._automatic_tick()
                opened.assert_not_called()
                self.assertFalse(obd.snapshot()['automatic'])
                obd.connect(PORT)
                self.wait_values(obd)
                self.assertTrue(obd.snapshot()['automatic'])
                obd.close()
                opened.reset_mock()
                obd._automatic_tick()
                opened.assert_not_called()
            finally:
                obd.close()

    def test_failed_direct_connection_retries_at_most_every_thirty_seconds(self):
        obd = OBD()
        obd.independent_settings = Mock()
        obd.independent_settings.port.return_value = PORT
        obd.automatic = True
        with patch('obd.Transport', side_effect=ConnectionError('Adapter unavailable')) as opened:
            try:
                with patch('obd.time.monotonic', return_value=0):
                    obd._automatic_tick()
                with patch('obd.time.monotonic', return_value=29):
                    obd._automatic_tick()
                self.assertEqual(opened.call_count, 1)
                with patch('obd.time.monotonic', return_value=31):
                    obd._automatic_tick()
                self.assertEqual(opened.call_count, 2)
                self.assertEqual(obd.snapshot()['values'], {})
            finally:
                obd.close()

    def test_selected_serial_transport_has_priority_over_automatic_bluetooth(self):
        settings = Mock()
        settings.port.return_value = ''
        obd = OBD()
        with patch('obd.Transport', side_effect=lambda port: transport()) as opened:
            try:
                obd.start_independent(settings)
                obd.connect('COM2')
                self.wait_values(obd)
                settings.port.return_value = PORT
                obd._automatic_tick()
                opened.assert_called_once_with('COM2')
                self.assertEqual(obd.snapshot()['port'], 'COM2')
                self.assertFalse(obd.snapshot()['automatic'])
            finally:
                obd.close()


if __name__ == '__main__':
    unittest.main()
