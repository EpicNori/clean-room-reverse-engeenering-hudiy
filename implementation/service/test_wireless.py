import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from wireless import WirelessSettings


class WirelessTests(unittest.TestCase):
    def test_confirmed_car_profile_preserves_credentials_and_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'main.json'
            original={'hotspot':{'enabled':False,'ssid':'Car','passphrase':'test-only-secret','bandwidth':'BG','hardwareAddress':'external-bssid','ipAddress':'external-ip'},'sound':{'volume':27}}
            path.write_text(json.dumps(original))
            projection=Mock(enabled=True);projection.snapshot.return_value={'available':True};projection.phone_snapshot.return_value={'call':{}}
            settings=WirelessSettings(projection,path)
            self.assertNotIn('passphrase',settings.snapshot())
            for enabled,confirmed in ((True,False),('true',True),(1,True)):
                with self.assertRaises(ValueError):settings.save(enabled,confirmed)
            projection.request_layout.assert_not_called()
            settings.save(True,True)
            actual=json.loads(path.read_text())
            self.assertEqual(actual['sound'],original['sound'])
            self.assertEqual(actual['hotspot']['passphrase'],original['hotspot']['passphrase'])
            self.assertEqual(actual['hotspot']['bandwidth'],'A')
            self.assertEqual(actual['hotspot']['ipAddress'],'192.168.12.1')
            self.assertEqual(actual['hotspot']['hardwareAddress'],'')
            settings.save(True,True)
            self.assertEqual(projection.request_layout.call_count,1)
            projection.request_layout.side_effect=OSError('Disk error')
            with self.assertRaises(OSError):settings.save(False,True)
            self.assertEqual(json.loads(path.read_text()),actual)
            projection.phone_snapshot.return_value={'call':{'state':3}}
            with self.assertRaises(ConnectionError):settings.save(False,True)

    def test_unprotected_or_invalid_native_hotspot_cannot_be_enabled(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'main.json'
            projection=Mock(enabled=True);projection.snapshot.return_value={'available':True};projection.phone_snapshot.return_value={'call':{}}
            settings=WirelessSettings(projection,path)
            for ssid,secret in (('','protected-test'),('x'*33,'protected-test'),('Car','short'),('Car','with\nnewline')):
                path.write_text(json.dumps({'hotspot':{'ssid':ssid,'passphrase':secret,'enabled':False}}))
                with self.assertRaises(ValueError):settings.save(True,True)
            projection.request_layout.assert_not_called()

if __name__=='__main__':unittest.main()
