"""Shared private receiver preferences and bounded PipeWire commands."""
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
from bluetooth_devices import ADDRESS
from runtime_support import save_json


def receiver_sink(sinks, address):
    pattern=re.compile(r'bluez_(?:output|sink)\.'+re.escape(address.replace(':','_'))+r'[A-Za-z0-9_.-]*')
    matches=[s for s in sinks if isinstance(s.get('name'),str) and pattern.fullmatch(s['name'])]
    if len(matches)!=1:raise ConnectionError('Connect the chosen receiver with Bluetooth audio enabled')
    return matches[0]


class AudioRouteBase:
    def __init__(self, bluetooth, enabled=False, preferences=None):
        self.bluetooth=bluetooth; self.enabled=enabled and sys.platform=='linux'
        self.preferences=preferences or Path.home()/'.local/share/hudiy-recreation/radio-output.json'
        self.lock=threading.RLock();self.operation_lock=threading.Lock();self.stop=threading.Event();self.worker=None
        self.address=''
        self.data={'available':False,'address':'','receivers':[],'connected':False,'routed':False,'error':'Radio output is available on the Pi'}

    def snapshot(self):
        with self.lock:return copy.deepcopy(self.data)

    def _receivers(self):
        return [d for d in self.bluetooth.snapshot()['devices'] if d['paired'] and d.get('audioReceiver')]

    def save(self,address):
        if not self.enabled:raise ConnectionError('Radio output requires the Pi')
        if not isinstance(address,str) or address and not ADDRESS.fullmatch(address):raise ValueError('Choose a paired audio receiver')
        if address and not any(d['address']==address for d in self._receivers()):raise ValueError('Choose a currently paired audio receiver')
        with self.operation_lock:
            save_json(self.preferences,{'address':address})
            with self.lock:self.address=address;self.data.update(address=address,routed=False)
        return {'saved':True,'message':'Radio receiver saved; output follows when it connects'}

    def _load(self):
        try:
            if self.preferences.stat().st_size>2048:return
            data=json.loads(self.preferences.read_text())
            address=data.get('address') if isinstance(data,dict) and set(data)=={'address'} else None
            if isinstance(address,str) and (not address or ADDRESS.fullmatch(address)):self.address=address
        except (OSError,ValueError):pass

    def _command(self,*args):
        try:
            result=subprocess.run(['pactl',*args],capture_output=True,check=True,timeout=3)
            if len(result.stdout)>2*1024*1024:raise ValueError('Audio state exceeds size limit')
            return result.stdout
        except (OSError,subprocess.SubprocessError):raise ConnectionError('PipeWire audio service unavailable') from None


    def _tick(self):
        raise NotImplementedError("Use our owned native audio route")

    def start(self):
        if self.enabled and not self.worker:
            self._load();self.worker=threading.Thread(target=self._run,daemon=True);self.worker.start()

    def _run(self):
        while not self.stop.is_set():
            self._tick();self.stop.wait(5)

    def close(self):
        self.stop.set()
        if self.worker:self.worker.join(timeout=4)
