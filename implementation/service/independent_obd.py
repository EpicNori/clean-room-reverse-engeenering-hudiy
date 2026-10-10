"""Durable ELM327 Bluetooth Serial Port selection owned by our backend."""
import json
from pathlib import Path
import threading
from bluetooth_devices import ADDRESS
from runtime_support import save_json


class IndependentOBDSettings:
    def __init__(self, bluetooth, obd, path=None):
        self.bluetooth, self.obd = bluetooth, obd
        self.path = path or Path.home()/'.local/share/hudiy-recreation/obd.json'
        self.lock = threading.RLock()
        self.data = {'address':'','channel':2,'enabled':True}
        try:
            if self.path.stat().st_size > 1024: raise ValueError('OBD preferences exceed limit')
            data = json.loads(self.path.read_text())
            if (isinstance(data,dict) and isinstance(data.get('address'),str) and
                    ADDRESS.fullmatch(data['address']) and type(data.get('channel')) is int and 1<=data['channel']<=30):
                self.data.update(address=data['address'], channel=data['channel'])
        except (OSError, ValueError, TypeError): pass

    def snapshot(self):
        with self.lock:
            devices=[d for d in self.bluetooth.snapshot()['devices'] if d['paired'] and d.get('serialPort')]
            return {'available':self.bluetooth.enabled,'deviceType':'RFCOMM',**self.data,'devices':devices}

    def port(self):
        data=self.snapshot()
        if not any(d['address']==data['address'] for d in data['devices']): return None
        return f"bluetooth://{data['address']}/{data['channel']}"

    def save(self,address,channel):
        if not isinstance(address,str) or not ADDRESS.fullmatch(address) or type(channel) is not int or not 1<=channel<=30:
            raise ValueError('Choose a paired serial adapter and RFCOMM channel 1–30')
        if not any(d['address']==address for d in self.snapshot()['devices']):
            raise ValueError('Choose a currently paired Bluetooth Serial Port adapter')
        with self.lock:
            updated={'address':address,'channel':channel,'enabled':True}
            save_json(self.path,updated)
            self.data=updated
        self.obd.reconnect_independent()
        return {'saved':True,'message':'ELM327 settings saved; connecting directly'}
