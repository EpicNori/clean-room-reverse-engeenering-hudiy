"""Our protected NetworkManager car hotspot, independent of Hudiy config."""
import json
from pathlib import Path
import secrets
import subprocess
import threading
from runtime_support import save_json

CONNECTION='hudiy-recreation-car'


class IndependentWireless:
    def __init__(self,projection,path=None):
        self.projection=projection
        self.path=path or Path.home()/'.local/share/hudiy-recreation/wireless.json'
        self.lock=threading.RLock()
        self.data={'enabled':False,'ssid':'coscarOS','ipAddress':'192.168.12.1','port':5277}
        try:
            if self.path.stat().st_size>2048:raise ValueError('Wireless preferences exceed limit')
            data=json.loads(self.path.read_text())
            self.validate(data)
            self.data=data
        except (OSError,ValueError,TypeError):pass

    @staticmethod
    def validate(data):
        if not isinstance(data,dict) or type(data.get('enabled')) is not bool:raise ValueError('Invalid wireless preferences')
        ssid,key=data.get('ssid'),data.get('passphrase')
        if not isinstance(ssid,str) or not 1<=len(ssid.encode())<=32 or any(ord(c)<32 for c in ssid):raise ValueError('Invalid hotspot name')
        if not isinstance(key,str) or not 8<=len(key)<=63 or not key.isascii() or any(ord(c)<32 for c in key):raise ValueError('Protected hotspot password required')
        if data.get('ipAddress')!='192.168.12.1' or data.get('port')!=5277:raise ValueError('Unsupported car network')

    def snapshot(self):
        with self.lock:return {'available':self.projection.enabled,'enabled':self.data['enabled'],'ssid':self.data['ssid'],'bandwidth':'A'}

    def credentials(self):
        with self.lock:return dict(self.data)

    @staticmethod
    def _network_mode(enabled):
        # The saved choice must govern both this session and the next boot.
        for command in (['nmcli','connection','modify',CONNECTION,'connection.autoconnect','yes' if enabled else 'no'],
                        ['nmcli','connection','up' if enabled else 'down',CONNECTION]):
            try:result=subprocess.run(command,capture_output=True,text=True,timeout=15)
            except (OSError,subprocess.SubprocessError):raise ConnectionError('NetworkManager did not complete the Wi-Fi mode change') from None
            if result.returncode:raise ConnectionError('The car hotspot is not installed or NetworkManager denied the change')

    def save(self,enabled,confirmed):
        if type(enabled) is not bool or confirmed is not True:raise ValueError('Confirm the Wi-Fi mode change')
        if not self.projection.enabled:raise ConnectionError('Car Wi-Fi requires the Pi application')
        with self.lock:
            updated={**self.data,'enabled':enabled}
            updated.setdefault('passphrase',secrets.token_urlsafe(24))
            self.validate(updated)
            try:
                self._network_mode(enabled)
                save_json(self.path,updated)
            except (OSError,ConnectionError):
                try:
                    self._network_mode(self.data['enabled'])
                except ConnectionError:raise ConnectionError('Could not restore the previous Wi-Fi mode after a settings failure') from None
                raise
            self.data=updated
            self.projection.reload_wireless()
        return {'saved':True,'message':'Car Wi-Fi enabled' if enabled else 'Car Wi-Fi disabled'}
