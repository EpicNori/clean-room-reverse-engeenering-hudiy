import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from obd_settings import NativeOBDSettings
from obd import Transport

ADDRESS='AA:BB:CC:DD:EE:02'


class NativeOBDTests(unittest.TestCase):
    def test_settings_preserve_unrelated_config_and_request_bounded_runtime_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'main.json'
            original={'hotspot':{'passphrase':'test-placeholder'},'obd':{'startupSequence':['ATZ'],'rfcommChannel':1}}
            path.write_text(json.dumps(original))
            projection=Mock(enabled=True)
            projection.snapshot.return_value={'available':True}
            projection.phone_snapshot.return_value={'call':{}}
            bluetooth=Mock()
            bluetooth.snapshot.return_value={'devices':[{'address':ADDRESS,'name':'OBDII','paired':True,'serialPort':True}]}
            settings=NativeOBDSettings(projection,bluetooth,path)
            self.assertTrue(settings.save(ADDRESS,2)['saved'])
            changed=json.loads(path.read_text())
            self.assertEqual(changed['hotspot'],original['hotspot'])
            self.assertEqual(changed['obd']['startupSequence'],['ATZ'])
            self.assertEqual(changed['obd']['rfcommChannel'],2)
            projection.request_layout.assert_called_once_with()
            self.assertNotIn('hotspot',settings.snapshot())
            for channel in (0,31,True,'2'):
                with self.assertRaises(ValueError):settings.save(ADDRESS,channel)
            with self.assertRaises(ValueError):settings.save('00:00:00:00:00:00',2)
            projection.phone_snapshot.return_value={'call':{'state':3}}
            with self.assertRaises(ConnectionError):settings.save(ADDRESS,2)
            projection.phone_snapshot.return_value={'call':{}}
            projection.request_layout.side_effect=OSError('Disk failure')
            with self.assertRaises(OSError):settings.save(ADDRESS,3)
            self.assertEqual(json.loads(path.read_text()),changed)

    def test_native_transport_never_initializes_or_owns_another_bluetooth_connection(self):
        with self.assertRaises(ConnectionError):Transport('hudiy')
        projection=Mock(enabled=True)
        projection.snapshot.return_value={'nativeOBDConnected':True}
        projection.query_obd.return_value='41 0D 64'
        transport=Transport('hudiy',projection)
        self.assertEqual(transport.query('010D'),'41 0D 64')
        projection.query_obd.assert_called_once_with('010D')
        with self.assertRaises(ValueError):transport.query('ATD123')
        transport.close()
        with self.assertRaises(ConnectionError):transport.query('010D')
