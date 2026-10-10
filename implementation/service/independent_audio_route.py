"""Optional direct radio routing for our native audio and the paired phone."""
import json
from audio_route_support import AudioRouteBase,receiver_sink


class IndependentAudioRoute(AudioRouteBase):
    def __init__(self,bluetooth,projection,calls,**kwargs):
        super().__init__(bluetooth,**kwargs)
        self.projection,self.calls=projection,calls

    def _tick(self):
        with self.operation_lock:
            receivers=self._receivers()
            with self.lock:address=self.address
            selected=next((d for d in receivers if d['address']==address),None)
            data={'available':True,'address':address,'receivers':receivers,'connected':bool(selected and selected['connected']),'routed':False,'error':''}
            try:
                if address:
                    if not data['connected']:raise ConnectionError('Waiting for the selected radio receiver')
                    if self.calls.snapshot().get('call',{}).get('state') in (1,2,3):raise ConnectionError('Audio routing waits until the phone call ends')
                    sinks=json.loads(self._command('-f','json','list','sinks'))
                    inputs=json.loads(self._command('-f','json','list','sink-inputs'))
                    sink=receiver_sink(sinks,address)
                    pid=self.projection.snapshot().get('runtimePid')
                    if type(pid) is not int or pid<=0:raise ConnectionError('Independent audio owner is unavailable')
                    phones=[d for d in self.bluetooth.snapshot()['devices'] if d['paired'] and d['connected'] and not d.get('audioReceiver') and not d.get('serialPort')]
                    phone_prefix='bluez_input.'+phones[0]['address'].replace(':','_')+'.' if len(phones)==1 else None
                    owned=[stream for stream in inputs if
                        str(stream.get('properties',{}).get('application.process.id',''))==str(pid) or
                        phone_prefix and str(stream.get('properties',{}).get('node.name','')).startswith(phone_prefix)]
                    valid=lambda value:type(value) is int and 0<=value<2**32-1
                    if not valid(sink.get('index')) or not all(valid(stream.get('index')) for stream in owned):raise ValueError('Invalid local audio identifiers')
                    default=self._command('get-default-sink').decode().strip()
                    stable=default==sink['name'] and all(stream.get('sink')==sink['index'] for stream in owned)
                    if not stable:
                        for stream in owned:
                            if self.stop.is_set():return
                            if stream.get('sink')!=sink['index']:self._command('move-sink-input',str(stream['index']),sink['name'])
                        if default!=sink['name']:self._command('set-default-sink',sink['name'])
                    data['routed']=stable
                    if not stable:data['error']='Checking the new audio route'
            except (ValueError,KeyError,TypeError,ConnectionError) as exc:data['error']=str(exc)
            with self.lock:self.data=data
