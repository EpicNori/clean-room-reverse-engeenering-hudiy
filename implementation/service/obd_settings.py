"""Touch-editable native RFCOMM settings; preserve unrelated Hudiy config."""
import json
from pathlib import Path
import threading
from bluetooth_devices import ADDRESS
from projection import save_json


class NativeOBDSettings:
    def __init__(self, projection, bluetooth, path=None):
        self.projection, self.bluetooth = projection, bluetooth
        self.path = path or Path.home() / '.hudiy/share/config/main_configuration.json'
        self.lock = threading.Lock()

    def _read(self):
        if self.path.stat().st_size > 1024 * 1024: raise ValueError('Native configuration exceeds size limit')
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or not isinstance(data.get('obd',{}),dict): raise ValueError('Invalid native OBD configuration')
        return data

    def snapshot(self):
        if not self.projection.enabled: return {'available':False, 'devices':[]}
        with self.lock:
            obd = self._read().get('obd',{})
            devices = [device for device in self.bluetooth.snapshot()['devices'] if device['paired'] and device.get('serialPort')]
            return {'available':True, 'deviceType':obd.get('deviceType','NONE'),
                    'address':obd.get('rfcommAddress',''), 'channel':obd.get('rfcommChannel',1),
                    'devices':devices}

    def save(self, address, channel):
        if not self.projection.enabled or not self.projection.snapshot()['available']:
            raise ConnectionError('Native Hudiy OBD settings require the running Pi host')
        if not isinstance(address,str) or not ADDRESS.fullmatch(address) or type(channel) is not int or not 1<=channel<=30:
            raise ValueError('Choose a paired serial adapter and an RFCOMM channel from 1 to 30')
        devices = self.bluetooth.snapshot()['devices']
        if not any(d['address']==address and d['paired'] and d.get('serialPort') for d in devices):
            raise ValueError('Choose a currently paired Bluetooth Serial Port adapter')
        if self.projection.phone_snapshot()['call'].get('state') in (1,2,3):
            raise ConnectionError('Finish the phone call before reconnecting Hudiy')
        with self.lock:
            original = self._read()
            updated = {**original, 'obd':{**original.get('obd',{}), 'deviceType':'RFCOMM',
                       'rfcommAddress':address, 'rfcommChannel':channel}}
            save_json(self.path, updated)
            try: self.projection.request_layout()
            except Exception:
                save_json(self.path, original)
                raise
        return {'saved':True, 'message':'OBD settings saved; Hudiy is reconnecting'}
