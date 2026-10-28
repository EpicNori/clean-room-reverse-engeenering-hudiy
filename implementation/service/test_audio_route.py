import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock
from audio_route_support import receiver_sink
from independent_audio_route import IndependentAudioRoute

ADDRESS='11:22:33:44:55:66'
SINK='bluez_output.11_22_33_44_55_66.1'


class FastStop(threading.Event):
    def wait(self,timeout=None):return self.is_set()


class AudioRouteTests(unittest.TestCase):
    def service(self,path=None):
        bluetooth=Mock();bluetooth.snapshot.return_value={'devices':[{'address':ADDRESS,'name':'JJ33','paired':True,'connected':True,'audioReceiver':True}]}
        projection=Mock();projection.snapshot.return_value={'runtimePid':123}
        calls=Mock();calls.snapshot.return_value={'call':{'state':0}}
        service=IndependentAudioRoute(bluetooth,projection,calls,preferences=path);service.enabled=True
        return service,bluetooth

    def test_selection_is_paired_receiver_only_private_and_restored(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'output.json';service,bt=self.service(path)
            for address in ('shell','00:00:00:00:00:00',None):
                with self.assertRaises(ValueError):service.save(address)
            service.save(ADDRESS)
            self.assertEqual(json.loads(path.read_text()),{'address':ADDRESS})
            restored,_=self.service(path);restored._load();self.assertEqual(restored.address,ADDRESS)
            bt.snapshot.return_value['devices'][0]['audioReceiver']=False
            with self.assertRaises(ValueError):service.save(ADDRESS)
            service.save('');self.assertEqual(service.address,'')

    def test_routes_only_owned_streams_and_verifies_on_next_poll(self):
        service,_=self.service();service.address=ADDRESS
        sinks=[{'name':SINK,'index':90},{'name':'local-speakers','index':71}]
        streams=[{'index':72,'sink':71,'properties':{'application.process.id':'123'}},
                 {'index':99,'sink':71,'properties':{'application.process.id':'456'}}]
        default='local-speakers'
        mutations=[]
        def command(*args):
            nonlocal default
            if args==('-f','json','list','sinks'):return json.dumps(sinks).encode()
            if args==('-f','json','list','sink-inputs'):return json.dumps(streams).encode()
            if args==('get-default-sink',):return default.encode()
            mutations.append(args)
            if args[0]=='move-sink-input':
                stream=next(i for i in streams if str(i['index'])==args[1]);stream['sink']=next(s['index'] for s in sinks if s['name']==args[2])
            if args[0]=='set-default-sink':default=args[1]
            return b''
        service._command=Mock(side_effect=command)
        service._tick()
        self.assertFalse(service.snapshot()['routed'])
        self.assertEqual(mutations,[('move-sink-input','72',SINK),('set-default-sink',SINK)])
        self.assertEqual(streams[1]['sink'],71)
        service._tick();self.assertTrue(service.snapshot()['routed']);self.assertEqual(len(mutations),2)
        service.bluetooth.snapshot.return_value['devices'][0]['connected']=False
        service._command.reset_mock();service._tick();service._command.assert_not_called();self.assertFalse(service.snapshot()['routed'])

    def test_missing_or_ambiguous_receiver_never_changes_routes(self):
        service,_=self.service();service.address=ADDRESS
        with self.assertRaises(ConnectionError):receiver_sink([{'name':'bluez_output.00_00_00_00_00_00.1'}],ADDRESS)
        with self.assertRaises(ConnectionError):receiver_sink([{'name':SINK},{'name':SINK}],ADDRESS)
        service._command=Mock(side_effect=[b'[]',b'[]'])
        service._tick()
        self.assertFalse(service.snapshot()['routed'])
        self.assertEqual(service._command.call_count,2)
        self.assertNotIn('move-sink-input',str(service._command.call_args_list))

    def test_unexpected_tick_error_keeps_routing_thread_alive(self):
        service,_=self.service();service.address=ADDRESS
        service.stop=FastStop()
        # An error type the routing tick does not expect must not end the thread.
        def command(*args):
            if args[-1]=='sink-inputs':raise AttributeError('unexpected pactl data')
            return json.dumps([{'name':SINK,'index':90}]).encode()
        service._command=Mock(side_effect=command)
        original,ticks=service._tick,[]
        def tick():
            ticks.append(1)
            if len(ticks)==2:service.stop.set()
            original()
        service._tick=tick
        service._run()
        self.assertEqual(len(ticks),2)
        self.assertEqual(service.snapshot()['error'],'Radio output check failed; retrying')
        self.assertFalse(service.snapshot()['routed'])
        self.assertTrue(service.operation_lock.acquire(blocking=False))

    def test_null_stream_properties_from_pactl_are_tolerated(self):
        service,_=self.service();service.address=ADDRESS
        streams=[{'index':72,'sink':71,'properties':None}]
        service._command=Mock(side_effect=lambda *args:json.dumps([{'name':SINK,'index':90}] if args[-1]=='sinks' else streams).encode())
        service._tick()
        self.assertNotEqual(service.snapshot()['error'],'Radio output check failed; retrying')

if __name__=='__main__':unittest.main()
