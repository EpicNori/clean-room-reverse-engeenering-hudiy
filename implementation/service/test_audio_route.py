import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from audio_route import AudioRoute,receiver_sink

ADDRESS='11:22:33:44:55:66'
SINK='bluez_output.11_22_33_44_55_66.1'


class AudioRouteTests(unittest.TestCase):
    def service(self,path=None):
        bluetooth=Mock();bluetooth.snapshot.return_value={'devices':[{'address':ADDRESS,'name':'JJ33','paired':True,'connected':True,'audioReceiver':True}]}
        service=AudioRoute(bluetooth,preferences=path);service.enabled=True
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

    def test_chain_moves_only_its_owned_streams_and_verifies_on_next_poll(self):
        service,_=self.service();service.address=ADDRESS
        sinks=[{'name':SINK,'index':90},{'name':'hudiy_equalizer_sink','index':71,'properties':{'node.link-group':'owned-eq'}},
               {'name':'echo_cancel_sink','index':82,'properties':{'node.link-group':'owned-echo'}}]
        streams=[{'index':72,'sink':71,'properties':{'node.name':'output.filter-chain-123','node.link-group':'owned-eq'}},
                 {'index':83,'sink':71,'properties':{'node.name':'echo-cancel-playback','node.link-group':'owned-echo'}},
                 {'index':99,'sink':71,'properties':{'node.name':'output.filter-chain-foreign','node.link-group':'foreign'}}]
        mutations=[]
        def command(*args):
            if args==('-f','json','list','sinks'):return json.dumps(sinks).encode()
            if args==('-f','json','list','sink-inputs'):return json.dumps(streams).encode()
            if args==('get-default-sink',):return b'hudiy_equalizer_sink\n'
            mutations.append(args)
            if args[0]=='move-sink-input':
                stream=next(i for i in streams if str(i['index'])==args[1]);stream['sink']=next(s['index'] for s in sinks if s['name']==args[2])
            return b''
        service._command=Mock(side_effect=command)
        service._tick()
        self.assertFalse(service.snapshot()['routed'])
        self.assertEqual(mutations,[('move-sink-input','83',SINK),('move-sink-input','72','echo_cancel_sink')])
        self.assertEqual(streams[2]['sink'],71)
        service._tick();self.assertTrue(service.snapshot()['routed']);self.assertEqual(len(mutations),2)
        service.bluetooth.snapshot.return_value['devices'][0]['connected']=False
        service._command.reset_mock();service._tick();service._command.assert_not_called();self.assertFalse(service.snapshot()['routed'])

    def test_missing_or_ambiguous_chain_never_routes_other_devices_or_streams(self):
        service,_=self.service();service.address=ADDRESS
        with self.assertRaises(ConnectionError):receiver_sink([{'name':'bluez_output.00_00_00_00_00_00.1'}],ADDRESS)
        with self.assertRaises(ConnectionError):receiver_sink([{'name':SINK},{'name':SINK}],ADDRESS)
        service._command=Mock(side_effect=[json.dumps([{'name':SINK,'index':90}]).encode(),b'[]'])
        service._tick()
        self.assertFalse(service.snapshot()['routed'])
        self.assertEqual(service._command.call_count,2)
        self.assertNotIn('move-sink-input',str(service._command.call_args_list))

if __name__=='__main__':unittest.main()
