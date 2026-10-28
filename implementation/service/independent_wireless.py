"""Our protected NetworkManager car hotspot, independent of Hudiy config."""
import json
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from runtime_support import save_json

CONNECTION='hudiy-recreation-car'


class IndependentWireless:
    def __init__(self,projection,path=None,recovery_allowed=None):
        self.projection=projection
        self.recovery_allowed=recovery_allowed or (lambda:True)
        self.path=path or Path.home()/'.local/share/hudiy-recreation/wireless.json'
        self.lock=threading.RLock()
        self.mode_lock=threading.RLock()
        self.stop=threading.Event()
        self.worker=None
        self.last_restore=float("-inf")
        self.restore_error=""
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
        with self.lock:return {'available':self.projection.enabled,'enabled':self.data['enabled'],'ssid':self.data['ssid'],'bandwidth':'A','error':self.restore_error}

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

    def start(self):
        if self.projection.enabled and self.worker is None:
            self.worker=threading.Thread(target=self._restore_loop,daemon=True)
            self.worker.start()

    def restore_enabled(self):
        # NetworkManager may prefer an older client profile before graphical
        # login makes our user-restricted AP available. Restore only the owner's
        # saved car-mode choice; never create profiles or enable a disabled AP.
        with self.mode_lock:
            with self.lock:
                if not self.projection.enabled or not self.data['enabled']:return
            if not self.recovery_allowed():return
            now=time.monotonic()
            if now-self.last_restore<30:return
            self.last_restore=now
            try:
                state=subprocess.run(['nmcli','-g','GENERAL.STATE','connection','show',CONNECTION],
                                     capture_output=True,text=True,timeout=5)
                if state.returncode:raise ConnectionError('Car hotspot profile unavailable')
                if state.stdout.strip()!='activated':self._network_mode(True)
                with self.lock:self.restore_error=''
            except (OSError,subprocess.SubprocessError,ConnectionError):
                with self.lock:self.restore_error='Car hotspot unavailable; retrying the saved mode'

    def _restore_loop(self):
        while not self.stop.is_set():
            self.restore_enabled()
            self.stop.wait(5)

    def close(self):
        self.stop.set()
        if self.worker:self.worker.join(timeout=1)

    def save(self,enabled,confirmed):
        if type(enabled) is not bool or confirmed is not True:raise ValueError('Confirm the Wi-Fi mode change')
        if not self.projection.enabled:raise ConnectionError('Car Wi-Fi requires the Pi application')
        # Serialize mode recovery and manual changes without holding the data
        # lock during NetworkManager calls, so status polling stays responsive.
        with self.mode_lock:
            with self.lock:
                previous=dict(self.data)
            updated={**previous,'enabled':enabled}
            updated.setdefault('passphrase',secrets.token_urlsafe(24))
            self.validate(updated)
            try:
                self._network_mode(enabled)
                save_json(self.path,updated)
            except (OSError,ConnectionError):
                try:self._network_mode(previous['enabled'])
                except ConnectionError:raise ConnectionError('Could not restore the previous Wi-Fi mode after a settings failure') from None
                raise
            with self.lock:
                self.data=updated
                self.restore_error=''
            self.last_restore=float('-inf')
            # NetworkManager and the preference file already hold the new mode; the
            # runtime re-reads it on start and while its Wi-Fi listener is unbound.
            try:self.projection.reload_wireless()
            except (OSError,ConnectionError) as exc:print(f'Car Wi-Fi saved; runtime reload deferred: {exc}',file=sys.stderr,flush=True)
        return {'saved':True,'message':'Car Wi-Fi enabled' if enabled else 'Car Wi-Fi disabled'}
