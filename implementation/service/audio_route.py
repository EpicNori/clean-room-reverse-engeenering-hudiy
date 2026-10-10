"""Route the existing equalizer/echo playback chain to one chosen radio receiver."""
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
from bluetooth_devices import ADDRESS
from projection import save_json


def receiver_sink(sinks, address):
    pattern=re.compile(r'bluez_(?:output|sink)\.'+re.escape(address.replace(':','_'))+r'[A-Za-z0-9_.-]*')
    matches=[s for s in sinks if isinstance(s.get('name'),str) and pattern.fullmatch(s['name'])]
    if len(matches)!=1:raise ConnectionError('Connect the chosen receiver with Bluetooth audio enabled')
    return matches[0]


class AudioRoute:
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
        with self.operation_lock:
            receivers=self._receivers()
            with self.lock:address=self.address
            selected=next((d for d in receivers if d['address']==address),None)
            data={'available':True,'address':address,'receivers':receivers,
                  'connected':bool(selected and selected['connected']),'routed':False,'error':''}
            try:
                if address:
                    if not data['connected']:raise ConnectionError('Waiting for the selected radio receiver')
                    sinks=json.loads(self._command('-f','json','list','sinks'))
                    inputs=json.loads(self._command('-f','json','list','sink-inputs'))
                    sink=receiver_sink(sinks,address)
                    eq=[s for s in sinks if s.get('name')=='hudiy_equalizer_sink']
                    echo=[s for s in sinks if s.get('name')=='echo_cancel_sink']
                    if len(eq)!=1 or len(echo)!=1:raise ConnectionError('Hudiy equalizer and echo sinks unavailable')
                    eq_group=eq[0].get('properties',{}).get('node.link-group')
                    echo_group=echo[0].get('properties',{}).get('node.link-group')
                    if not eq_group or not echo_group:raise ConnectionError('Audio chain ownership unavailable')
                    eq_output=[i for i in inputs if str(i.get('properties',{}).get('node.name','')).startswith('output.filter-chain-')
                        and i.get('properties',{}).get('node.link-group')==eq_group]
                    echo_output=[i for i in inputs if i.get('properties',{}).get('node.name')=='echo-cancel-playback'
                        and i.get('properties',{}).get('node.link-group')==echo_group]
                    if any(len(items)!=1 for items in (eq,echo,eq_output,echo_output)):
                        raise ConnectionError('The existing Hudiy equalizer and echo playback chain must be available')
                    default=self._command('get-default-sink').decode().strip()
                    desired=((echo_output[0],sink),(eq_output[0],echo[0]))
                    # All nodes are observed locally, and only our two known chain streams can move.
                    valid=lambda value:type(value) is int and 0<=value<2**32-1
                    if not all(valid(stream.get('index')) and valid(target.get('index')) for stream,target in desired):
                        raise ValueError('Invalid local audio chain identifiers')
                    stable=default=='hudiy_equalizer_sink' and all(stream.get('sink')==target['index'] for stream,target in desired)
                    if not stable:
                        for stream,target in desired:
                            if self.stop.is_set():return
                            if stream.get('sink')!=target['index']:self._command('move-sink-input',str(stream['index']),target['name'])
                        if self.stop.is_set():return
                        if default!='hudiy_equalizer_sink':self._command('set-default-sink','hudiy_equalizer_sink')
                    data['routed']=stable
                    if not stable:data['error']='Checking the new audio route'
            except (ValueError,KeyError,TypeError,ConnectionError) as exc:data['error']=str(exc)
            with self.lock:self.data=data

    def start(self):
        if self.enabled and not self.worker:
            self._load();self.worker=threading.Thread(target=self._run,daemon=True);self.worker.start()

    def _run(self):
        while not self.stop.is_set():
            self._tick();self.stop.wait(5)

    def close(self):
        self.stop.set()
        if self.worker:self.worker.join(timeout=4)
