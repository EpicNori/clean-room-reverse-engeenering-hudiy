"""Bounded physical backlight control using existing Pi user permissions."""
import json
from pathlib import Path
import sys
import threading
from projection import save_json


class DisplayBrightness:
    def __init__(self, enabled=False, root=None, preferences=None):
        self.enabled = enabled and sys.platform == 'linux'
        self.root = root or Path('/sys/class/backlight')
        self.preferences = preferences or Path.home()/'.local/share/hudiy-recreation/brightness.json'
        self.lock = threading.Lock()

    def _device(self):
        if not self.enabled: raise ConnectionError('Physical brightness is available on the Pi')
        devices = [p for p in self.root.iterdir() if (p/'brightness').is_file() and (p/'max_brightness').is_file()]
        if len(devices)!=1: raise ConnectionError('One physical backlight is required')
        device = devices[0]
        maximum = int((device/'max_brightness').read_text().strip())
        if not 1<=maximum<=1000000: raise ConnectionError('Invalid backlight range')
        return device, maximum

    def snapshot(self):
        try:
            with self.lock:
                device,maximum=self._device()
                current=int((device/'brightness').read_text().strip())
                return {'available':True,'brightness':max(0,min(100,round(current*100/maximum))),'minimum':5}
        except (OSError,ValueError,ConnectionError):
            return {'available':False,'brightness':None,'minimum':5}

    def set(self, percent):
        if type(percent) is not int or not 5<=percent<=100: raise ValueError('Brightness must be an integer from 5 to 100')
        with self.lock:
            device,maximum=self._device()
            value=max(1,round(maximum*percent/100))
            (device/'brightness').write_text(str(value))
            save_json(self.preferences,{'brightness':percent})
        return {'saved':True,'message':'Display brightness saved',**self.snapshot()}

    def start(self):
        if not self.enabled: return
        try:
            if self.preferences.stat().st_size>128: return
            saved=json.loads(self.preferences.read_text())
            if isinstance(saved,dict) and set(saved)=={'brightness'}: self.set(saved['brightness'])
        except (OSError,ValueError,ConnectionError): pass
