"""Configure the existing licensed head unit's protected car Wi-Fi hotspot."""
import json
from pathlib import Path
import threading
from projection import save_json


class WirelessSettings:
    def __init__(self, projection, path=None):
        self.projection = projection
        self.path = path or Path.home()/'.hudiy/share/config/main_configuration.json'
        self.lock = threading.Lock()
        if projection.enabled:
            try: projection.set_wireless_default(self._read()['hotspot'].get('enabled') is True)
            except (OSError, ValueError): pass

    def _read(self):
        if self.path.stat().st_size > 1024*1024: raise ValueError('Native configuration exceeds size limit')
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or not isinstance(data.get('hotspot'),dict): raise ValueError('Hotspot configuration unavailable')
        return data

    def snapshot(self):
        if not self.projection.enabled:return {'available':False,'enabled':False}
        with self.lock:
            hotspot=self._read()['hotspot']
            # Passwords stay inside the existing protected native configuration.
            return {'available':True,'enabled':hotspot.get('enabled') is True,
                    'ssid':str(hotspot.get('ssid',''))[:32],'bandwidth':hotspot.get('bandwidth')}

    def save(self, enabled, confirmed):
        if type(enabled) is not bool or confirmed is not True:raise ValueError('Confirm the Wi-Fi mode change')
        if not self.projection.enabled or not self.projection.snapshot()['available']:
            raise ConnectionError('Car hotspot settings require the running Pi host')
        if self.projection.phone_snapshot().get('call',{}).get('state') in (1,2,3):
            raise ConnectionError('Finish the phone call before restarting Hudiy')
        with self.lock:
            original=self._read(); hotspot=original['hotspot']
            if enabled:
                ssid,secret=hotspot.get('ssid'),hotspot.get('passphrase')
                if not isinstance(ssid,str) or not 1<=len(ssid.encode('utf-8'))<=32 or any(ord(c)<32 for c in ssid):
                    raise ValueError('Configure a valid hotspot name in Hudiy first')
                if not isinstance(secret,str) or not 8<=len(secret)<=63 or not secret.isascii() or any(ord(c)<32 for c in secret):
                    raise ValueError('Configure a protected hotspot password in Hudiy first')
            updated={**original,'hotspot':{**hotspot,'enabled':enabled}}
            if enabled:updated['hotspot'].update(bandwidth='A',hardwareAddress='',ipAddress='192.168.12.1')
            if updated==original:
                self.projection.set_wireless_default(enabled)
                return {'saved':True,'message':'Wi-Fi mode is already configured'}
            save_json(self.path,updated)
            try:self.projection.request_layout()
            except Exception:
                save_json(self.path,original)
                raise
            self.projection.set_wireless_default(enabled)
        return {'saved':True,'message':'Wi-Fi mode saved; Hudiy is restarting'}
