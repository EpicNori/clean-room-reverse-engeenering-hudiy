import time
import unittest
from unittest.mock import Mock,patch
from obd import OBD


FRAMES={'0104':'41 04 80','0105':'41 05 7D','010C':'41 0C 1A F8',
        '010D':'41 0D 64','0111':'41 11 40','0142':'41 42 37 78'}


class AutomaticOBDTests(unittest.TestCase):
    def projection(self):
        projection=Mock(enabled=True)
        projection.snapshot.return_value={'available':True,'nativeOBDConnected':False,'exitRequested':False}
        projection.query_obd.side_effect=lambda command:FRAMES[command]
        return projection

    def wait_values(self,obd):
        deadline=time.monotonic()+2
        while not obd.snapshot()['values'] and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(obd.snapshot()['values']['rpm'],1726)
        self.assertEqual(obd.snapshot()['values']['speed'],100)

    def test_native_connection_starts_sensor_data_and_drop_recovery_clears_stale_values(self):
        projection=self.projection();obd=OBD()
        try:
            obd.start(projection)
            obd._automatic_tick()
            self.assertTrue(obd.snapshot()['automatic'])
            projection.query_obd.assert_not_called()
            projection.snapshot.return_value['nativeOBDConnected']=True
            obd._automatic_tick();self.wait_values(obd)
            self.assertEqual(obd.snapshot()['port'],'hudiy')
            self.assertTrue(all(command.args[0] in FRAMES for command in projection.query_obd.call_args_list))
            projection.snapshot.return_value['nativeOBDConnected']=False
            obd._automatic_tick()
            self.assertFalse(obd.snapshot()['connected'])
            self.assertEqual(obd.snapshot()['values'],{})
            self.assertEqual(obd.snapshot()['history'],[])
            self.assertIsNone(obd.snapshot()['timestamp'])
            projection.snapshot.return_value['nativeOBDConnected']=True
            obd._automatic_tick();self.wait_values(obd)
            self.assertEqual(len(obd.snapshot()['history']),1)
        finally:obd.close()
        self.assertFalse(obd.supervisor.is_alive())
        self.assertIsNone(obd.worker)

    def test_manual_stop_and_host_shutdown_do_not_reconnect_or_query(self):
        projection=self.projection();obd=OBD()
        try:
            obd.start(projection)
            projection.snapshot.return_value['nativeOBDConnected']=True
            obd._automatic_tick();self.wait_values(obd)
            obd.disconnect();projection.query_obd.reset_mock()
            self.assertFalse(obd.snapshot()['automatic'])
            obd._automatic_tick();projection.query_obd.assert_not_called()
            self.assertFalse(obd.snapshot()['connected'])
            obd.connect('hudiy',projection);self.wait_values(obd)
            projection.snapshot.return_value['exitRequested']=True
            obd._automatic_tick();projection.query_obd.reset_mock()
            obd._automatic_tick();projection.query_obd.assert_not_called()
            self.assertEqual(obd.snapshot()['values'],{})
        finally:obd.close()
        standalone=OBD();standalone.start(Mock(enabled=False))
        self.assertIsNone(standalone.supervisor)

    def test_failed_native_queries_wait_thirty_seconds_before_retry(self):
        projection=self.projection();obd=OBD()
        try:
            obd.start(projection)
            projection.snapshot.return_value['nativeOBDConnected']=True
            projection.query_obd.side_effect=TimeoutError('OBD query timed out')
            with patch('obd.time.monotonic',return_value=1):obd._automatic_tick()
            obd.worker.join(timeout=1)
            self.assertFalse(obd.snapshot()['connected'])
            self.assertEqual(obd.snapshot()['history'],[])
            with patch('obd.time.monotonic',return_value=30):obd._automatic_tick()
            self.assertEqual(projection.query_obd.call_count,1)
            with patch('obd.time.monotonic',return_value=31):obd._automatic_tick()
            obd.worker.join(timeout=1)
            self.assertEqual(projection.query_obd.call_count,2)
        finally:obd.close()

    def test_selected_serial_connection_is_not_replaced_by_native_bluetooth(self):
        projection=self.projection();obd=OBD()
        serial=Mock(native=None)
        serial.query.side_effect=lambda command:'ELM327' if command=='ATZ' else FRAMES.get(command,'OK')
        try:
            obd.start(projection)
            with patch('obd.Transport',return_value=serial):obd.connect('COM2')
            self.wait_values(obd)
            projection.snapshot.return_value['nativeOBDConnected']=True
            obd._automatic_tick()
            self.assertEqual(obd.snapshot()['port'],'COM2')
            self.assertTrue(obd.snapshot()['connected'])
            projection.query_obd.assert_not_called()
        finally:obd.close()


if __name__=='__main__':unittest.main()
