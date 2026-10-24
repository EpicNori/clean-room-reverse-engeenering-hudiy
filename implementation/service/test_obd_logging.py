import copy
import csv
import io
import json
import os
from pathlib import Path
import socketserver
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from obd_logging import OBDRecorder, DEFAULT_SETTINGS, validate_settings
from diagnostic_sweep import DiagnosticSweep, supported, observation
from custom_obd import CustomOBDStore, DEFAULT_CONFIG
from obd import OBD, Transport


def wait_for(predicate, timeout=4):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        result=predicate()
        if result:return result
        time.sleep(.01)
    raise AssertionError('Diagnostic state did not arrive')


class RecorderTests(unittest.TestCase):
    def test_complete_private_session_preserves_structured_and_raw_data_and_exports_safely(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rec=OBDRecorder(root/'logs',export_root=root/'exports')
            identifier=rec.start({'mode':'simulator'})['active']['id']
            rec.exchange('010D','410D3C\r>')
            rec.record('diagnostic',{'source':'custom:oil','value':'=1+1','unit':'°C'})
            rec.record('sample',{'values':{'speed':60,'derived:acceleration':-1.25}})
            rec.stop()
            raw,ctype=rec.export(identifier,'jsonl')
            events=[json.loads(line) for line in raw.splitlines()]
            self.assertEqual(events[0]['type'],'session');self.assertEqual(events[-1]['type'],'end')
            self.assertTrue(any(e['data'].get('response')=='410D3C\r>' for e in events))
            text,_=rec.export(identifier,'csv');rows=list(csv.DictReader(io.StringIO(text.decode('utf-8-sig'))))
            self.assertIn("'=1+1",[row['value'] for row in rows])
            self.assertTrue(any(row["source"]=="builtin:speed" and row["value"]=="60" for row in rows))
            self.assertTrue(any(row["source"]=="derived:acceleration" and row["value"]=="-1.25" for row in rows))
            exported=rec.save_export(identifier,'jsonl')
            self.assertEqual((root/'exports'/exported['filename']).read_bytes(),raw)
            self.assertTrue(rec.preview(identifier)['events'])
            restored=OBDRecorder(root/'logs').snapshot()['sessions'][0]
            self.assertEqual(restored['state'],'complete');self.assertEqual(restored['bytes'],len(raw))
            if os.name!='nt':self.assertEqual((root/'logs'/(identifier+'.jsonl')).stat().st_mode&0o777,0o600)

    def test_idle_recording_is_flushed_before_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);identifier=rec.start()['active']['id']
            try:wait_for(lambda:(Path(folder)/(identifier+'.jsonl')).stat().st_size>0,timeout=2.5)
            finally:rec.stop()

    def test_limits_stop_recording_visibly_and_never_replace_previous_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder,max_file=4096,max_total=8192,max_sessions=1)
            identifier=rec.start()['active']['id']
            for i in range(20):rec.record('diagnostic',{'response':'A'*500,'index':i})
            wait_for(lambda:not rec.snapshot()['recording'])
            state=rec.snapshot();self.assertEqual(state['sessions'][0]['state'],'interrupted')
            self.assertIn('limit',state['error'].lower());self.assertLessEqual(state['sessions'][0]['bytes'],4096)
            before=(Path(folder)/(identifier+'.jsonl')).read_bytes()
            with self.assertRaises(ValueError):rec.start()
            self.assertEqual((Path(folder)/(identifier+'.jsonl')).read_bytes(),before)

    def test_path_active_export_and_deletion_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder)
            identifier=rec.start()['active']['id']
            try:
                for name in ('../settings','x','20261024T123456Z-000000000000/../../x',[]):
                    with self.assertRaises(ValueError):rec.export(name,'jsonl')
                with self.assertRaises(ValueError):rec.export(identifier,'jsonl')
                with self.assertRaises(ValueError):rec.remove(identifier,True)
            finally:rec.stop()
            with self.assertRaises(ValueError):rec.remove(identifier,False)
            with self.assertRaises(ValueError):rec.export(identifier,'sh')
            rec.remove(identifier,True);self.assertEqual(rec.snapshot()['sessions'],[])

    def test_interrupted_session_recovery_keeps_incomplete_raw_records(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);identifier='20261024T120000Z-000000000001'
            path=root/(identifier+'.jsonl');path.write_bytes(b'{"timestamp":1,"type":"sample","data":{}}\n{"partial":')
            rec=OBDRecorder(root)
            self.assertEqual(rec.snapshot()['sessions'][0]['state'],'interrupted')
            raw,_=rec.export(identifier,'jsonl');self.assertTrue(raw.endswith(b'{"partial":'))
            csvdata,_=rec.export(identifier,'csv');self.assertIn(b'Truncated or invalid record',csvdata)
            self.assertEqual(len(rec.preview(identifier)['events']),1)

    def test_settings_are_durable_strict_and_apply_to_the_next_session(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder)
            settings={**DEFAULT_SETTINGS,'autoRecord':True,'rawReplies':False,'sampleIntervalSeconds':7,'maxSessions':4}
            rec.set_settings(settings)
            restored=OBDRecorder(folder)
            self.assertEqual(restored.settings,settings)
            rec.begin_connection('simulator');self.assertTrue(rec.active)
            rec.exchange('010D','410D40>')
            rec.set_settings({**settings,'rawReplies':True})
            rec.exchange('010D','410D40>')
            identifier=rec.active['id'];rec.stop()
            self.assertNotIn(b'"type":"exchange"',rec.export(identifier,'jsonl')[0])
            rec.start();rec.exchange('010D','410D40>');second=rec.active['id'];rec.stop()
            self.assertIn(b'"type":"exchange"',rec.export(second,'jsonl')[0])
            for patch in ({'autoRecord':1},{'scanIntervalSeconds':0},{'maxSessionMiB':65},{'rawReplies':'true'},{'path':'x'},{'maxSessionMiB':64,'maxTotalMiB':16}):
                with self.assertRaises(ValueError):validate_settings({**DEFAULT_SETTINGS,**patch})

    def test_queue_overload_stops_visibly_instead_of_dropping_silently(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);release=threading.Event();original=rec._write
            def delayed(*args):release.wait(2);original(*args)
            with patch.object(rec,'_write',side_effect=delayed):
                identifier=rec.start()['active']['id']
                for _ in range(260):rec.record('diagnostic',{'value':1})
                self.assertTrue(rec.finishing);self.assertIn('queue',rec.error)
                release.set();rec.stop()
            self.assertEqual(rec.snapshot()['sessions'][0]['state'],'interrupted')
            self.assertIn(b'queue',rec.export(identifier,'jsonl')[0])

    def test_disk_failure_is_not_acknowledged_as_a_complete_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);rec.start();rec.record('diagnostic',{'value':1})
            with patch('obd_logging.os.fsync',side_effect=OSError('disk full')):rec.stop()
            self.assertFalse(rec.active);self.assertTrue(rec.error)
            self.assertEqual(OBDRecorder(folder).snapshot()['sessions'][0]['state'],'interrupted')

    def test_write_and_close_failures_still_release_the_active_recording(self):
        import queue
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder)
            item={'id':'20261024T120000Z-000000000002','bytes':0,'events':0,'startedAt':1,'state':'recording','mode':'simulator','reason':None}
            rec.active=item;jobs=queue.Queue();jobs.put(b'{}\n')
            stream=Mock();stream.write.side_effect=OSError('disk full');stream.close.side_effect=OSError('close failed')
            rec._write(stream,jobs,item,4096)
            self.assertIsNone(rec.active);self.assertFalse(rec.finishing)
            self.assertIn('Storage',rec.error);self.assertEqual(item['state'],'interrupted')

    def test_lowering_the_session_limit_keeps_all_older_recordings_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder)
            for _ in range(2):rec.start();rec.stop()
            rec.set_settings({**DEFAULT_SETTINGS,'maxSessions':1})
            self.assertEqual(len(rec.snapshot()['sessions']),2)
            with self.assertRaises(ValueError):rec.start()

    def test_raw_and_sample_filters_and_sample_interval(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);rec.set_settings({**DEFAULT_SETTINGS,'sampleIntervalSeconds':5})
            identifier=rec.start()['active']['id']
            with patch('obd_logging.time.monotonic',return_value=100):
                rec.record('sample',{'values':{'speed':1}});rec.record('sample',{'values':{'speed':2}})
            with patch('obd_logging.time.monotonic',return_value=106):rec.record('sample',{'values':{'speed':3}})
            rec.stop();events=[json.loads(line) for line in rec.export(identifier,'jsonl')[0].splitlines()]
            self.assertEqual([e['data']['values']['speed'] for e in events if e['type']=='sample'],[1,3])

    @unittest.skipIf(os.name=='nt','Symlinks require Windows privilege')
    def test_symlinked_log_or_export_paths_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);other=root/'outside';other.mkdir();(root/'logs').symlink_to(other,target_is_directory=True)
            rec=OBDRecorder(root/'logs')
            with self.assertRaises(ValueError):rec.start()


class SweepTests(unittest.TestCase):
    def test_support_bits_multiple_ecus_and_headered_freeze_frame(self):
        self.assertEqual(supported('0100','410080000001\r410000100000>'),{1,12,32})
        self.assertEqual(supported('020000','42000000100000>'),{12})
        self.assertEqual(observation('020C00','420C001AF8>')['value'],1726)
        self.assertEqual(observation('07','47010147>')['codes'],['P0147'])
        self.assertEqual(observation('0A','4A010133>')['codes'],['P0133'])
        self.assertTrue(observation('0101','410181000000>')['mil'])
        self.assertIn('error',observation('010D','NO DATA>'))
        self.assertEqual(supported('0100','4100FF>'),set())

    def test_discovery_queries_only_advertised_readings_and_respects_disabled_modes(self):
        class Adapter:
            def __init__(self):self.commands=[]
            def select_header(self,header):pass
            def query(self,command):
                self.commands.append(command)
                return {'03':'43010133>','07':'47000000>','0A':'4A000000>','0100':'410000180001>','0120':'412000000000>','010C':'410C1AF8>','010D':'410D3C>','020000':'NO DATA>','0900':'490000000000>','ATDPN':'A3\r>'}.get(command,'NO DATA>')
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);rec.set_settings({**DEFAULT_SETTINGS,'vehicleInfo':False,'freezeFrame':False,'monitorTests':False})
            rec.start();sweep=DiagnosticSweep(rec);adapter=Adapter()
            for _ in range(12):sweep.next_at=0;sweep.step(adapter)
            rec.stop()
            self.assertIn('010C',adapter.commands);self.assertIn('010D',adapter.commands);self.assertIn('0120',adapter.commands)
            self.assertNotIn('020000',adapter.commands);self.assertNotIn('ATDPN',adapter.commands);self.assertNotIn('0900',adapter.commands)
            self.assertEqual(rec.coverage['supported']['01'],['0C','0D'])

    def test_no_writes_or_arbitrary_payloads_enter_transport(self):
        adapter=Transport.__new__(Transport)
        for command in ('04','08','2E123400','060001','090002','020C01','010D\r04','ATSHFFF','22000100'):
            with self.assertRaises(ValueError):adapter.query(command)

    def test_real_transport_records_hidden_custom_sensor_and_disconnect_errors(self):
        class ELM(socketserver.StreamRequestHandler):
            def handle(self):
                buffer=bytearray()
                while True:
                    part=self.rfile.read(1)
                    if not part:return
                    if part!=b'\r':buffer.extend(part);continue
                    command=buffer.decode();buffer.clear()
                    frames={'ATZ':'ELM327 logger fixture','ATDPN':'A6','0104':'410480','0105':'41057D','010C':'410C1AF8','010D':'410D3C','0111':'411138','0142':'41423714','015C':'415C64','03':'43010133','07':'47010147','0A':'4A000000'}
                    response=frames.get(command,'OK' if command.startswith('AT') else 'NO DATA')
                    self.wfile.write((response+'\r>').encode());self.wfile.flush()
        fake=socketserver.ThreadingTCPServer(('127.0.0.1',0),ELM);fake.daemon_threads=True
        thread=threading.Thread(target=fake.serve_forever,daemon=True);thread.start()
        obd=OBD()
        try:
            with tempfile.TemporaryDirectory() as folder:
                from test_custom_obd import sensor
                root=Path(folder);rec=OBDRecorder(root/'logs');rec.set_auto(True);obd.recorder=rec
                store=CustomOBDStore(True,root/'config.json');cfg=copy.deepcopy(DEFAULT_CONFIG);cfg['sensors']=[sensor()]
                store.save({'revision':0,'config':cfg});obd.custom_dashboard=store
                obd.connect(f'tcp://127.0.0.1:{fake.server_address[1]}')
                wait_for(lambda:obd.snapshot()['custom'].get('oil',{}).get('value')==60)
                identifier=rec.active['id'];self.assertEqual(rec.active['mode'],'simulator')
                obd.disconnect();obd.connect(f'tcp://127.0.0.1:{fake.server_address[1]}')
                self.assertEqual(rec.active['id'],identifier)
                wait_for(lambda:obd.snapshot()['custom'].get('oil',{}).get('value')==60)
                obd.disconnect();rec.stop()
                events=[json.loads(line) for line in rec.export(identifier,'jsonl')[0].splitlines()]
                self.assertTrue(any(e['type']=='exchange' and e['data']['command']=='ATZ' for e in events))
                self.assertTrue(any(e['type']=='sample' and e['data']['custom'].get('oil',{}).get('value')==60 for e in events))
                self.assertTrue(any(e['type']=='connection' and not e['data']['connected'] for e in events))
                self.assertFalse(any(e['data'].get('command') in ('04','08') for e in events))
        finally:obd.close();fake.shutdown();fake.server_close()


if __name__=='__main__':unittest.main()
