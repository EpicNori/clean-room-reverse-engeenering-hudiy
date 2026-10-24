"""Regression cases for missing evidence, ECU attribution and read-only bounds."""
import json
import csv
import io
from datetime import datetime, timezone
from pathlib import Path
import socket
import socketserver
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from elm_frames import response_frames, response_payloads, physical_request_header
from diagnostic_sweep import DiagnosticSweep, observation
from obd import Transport, decode
from obd_logging import OBDRecorder, DEFAULT_SETTINGS


class FramingTests(unittest.TestCase):
    def test_interleaved_ecus_reassemble_separately_and_remove_can_padding(self):
        raw=('7E8 10 0B 59 02 FF 01 23 45\r7E9 04 41 0C 10 00 00 00 00\r'
             '7E8 21 A8 04 56 78 08 00 00>')
        frames=response_frames(raw)
        self.assertEqual([(f['ecu'],f['payload']) for f in frames],
                         [('7E9','410C1000'),('7E8','5902FF012345A804567808')])
        self.assertEqual(decode('0C',raw),1024)
        result=observation('1902FF',raw)
        self.assertEqual(result['readings'][0]['ecu'],'7E8')
        self.assertEqual(result['records'][0]['dtc'],'012345')
        self.assertIn('warningIndicatorRequested',result['records'][0]['flags'])

    def test_malformed_or_missing_frames_never_become_values(self):
        for raw in ('7E8 04 41 0C 1A>',
                    '7E8 10 0B 59 02 FF 01 23 45\r7E8 22 A8 04 56 78 08 00 00>',
                    '008\r0:6212341122\r1:3344>',
                    '00B\r0:5902FF012345\r2:A804567808>'):
            with self.subTest(raw=raw):
                self.assertTrue(any(not frame['complete'] for frame in response_frames(raw)))
                self.assertEqual(response_payloads(raw,'5902'),[])
        self.assertIsNone(decode('0C','7E8 04 41 0C 1A>'))

    def test_real_monitor_layout_respects_elm_declared_length(self):
        # Same layout as the vehicle capture; test data is non-identifying.
        raw=('013\r0:4685FDFCF95C\r1:F4477FFF85FAFC\r2:F95C80000FA100>')
        result=observation('0685',raw)
        self.assertNotIn('error',result)
        self.assertEqual(len(result['tests']),2)
        self.assertEqual(result['tests'][0]['rawValue'],'F95C')
        self.assertEqual(len(response_frames(raw)[0]['payload']),19*2)

    def test_headered_and_legacy_replies_keep_identity(self):
        self.assertEqual(decode('0C','7E804410C1AF8>'),1726)
        self.assertEqual(decode('0C','18DAF11004410C1AF8>'),1726)
        self.assertEqual(decode('0C','48 6B 10 41 0C 1A F8 22>'),1726)
        self.assertEqual(decode('0C','84 F1 10 41 0C 1A F8 22>'),1726)
        self.assertEqual(physical_request_header('7E9'),'7E1')
        self.assertEqual(physical_request_header('18DAF110'),'18DA10F1')
        self.assertIsNone(physical_request_header('legacy:10'))
        self.assertIsNone(physical_request_header('123'))

    def test_values_from_multiple_ecus_are_not_collapsed(self):
        result=observation('0105','7E8 03 41 05 82\r7E9 03 41 05 80>')
        self.assertEqual([(r['ecu'],r['value']) for r in result['readings']],[('7E8',90),('7E9',88)])
        self.assertEqual(observation('0123','41231114>')['value'],43720)

    def test_uds_negative_and_empty_responses_are_distinct(self):
        self.assertEqual(observation('1902FF','5902FF>')['records'],[])
        denied=observation('1902FF','7F1933>')
        self.assertIn('error',denied)
        self.assertEqual(denied['readings'][0]['negativeResponseCode'],'33')
        self.assertIn('error',observation('1902FF','NO DATA>'))
        self.assertIn('error',observation('1902FF','5902FF0123>'))


class EvidenceTests(unittest.TestCase):
    def test_long_raw_and_structured_responses_reconstruct_without_loss(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);identifier=rec.start()['active']['id']
            raw='A'*9000+'\r>'
            data={'records':[{'dtc':f'{i:06X}','status':'AF'} for i in range(1500)]}
            rec.exchange('1902FF',raw,header='7E0',started=1)
            rec.record('diagnostic',data)
            rec.stop()
            events=[json.loads(line) for line in rec.export(identifier,'jsonl')[0].splitlines()]
            parts=[e['data'] for e in events if e['type']=='exchange']
            self.assertEqual(''.join(p['response'] for p in parts),raw)
            self.assertEqual(len({p['exchangeId'] for p in parts}),1)
            self.assertTrue(all(p['responseComplete'] for p in parts))
            structured=[e['data'] for e in events if e['type']=='diagnostic-part']
            self.assertEqual(json.loads(''.join(p['content'] for p in structured)),data)

    def test_partial_transport_reply_is_retained_before_timeout(self):
        t=Transport.__new__(Transport);t.closed=False;t.serial=None;t.sock=Mock()
        t.sock.recv.side_effect=[b'7E8 10 0B 59 02',socket.timeout()]
        t.observer=Mock();t.header=None
        with patch('obd.time.monotonic',side_effect=[0,0,0,4]):
            with self.assertRaises(TimeoutError):t.query('03')
        self.assertEqual(t.observer.exchange.call_args.args[1],'7E8 10 0B 59 02')

    def test_long_incoming_reply_gets_an_idle_timeout_not_a_three_second_total_limit(self):
        t=Transport.__new__(Transport);t.closed=False;t.serial=None;t.sock=Mock()
        t.sock.recv.side_effect=[b'7E8 10 0B 59 02',b' FF 01 23 45\r',b'7E8 21 A8 04 56 78 08 00 00\r>']
        with patch('obd.time.monotonic',side_effect=[0,0,2,4,6,8]):
            response=t._query('1902FF')
        self.assertEqual(observation('1902FF',response)['records'][1]['dtc'],'045678')

    def test_csv_uses_reading_acquisition_time_instead_of_batch_time(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);identifier=rec.start()['active']['id']
            rec.record('sample',{'values':{'speed':30},'acquiredAt':{'speed':1700000000}})
            rec.stop()
            data=rec.export(identifier,'csv')[0].decode('utf-8-sig')
            rows=list(csv.DictReader(io.StringIO(data)))
            speed=next(row for row in rows if row['source']=='builtin:speed')
            self.assertEqual(speed['timestamp_utc'],datetime.fromtimestamp(1700000000,timezone.utc).isoformat())
            self.assertTrue(rec.snapshot()['sessions'][0]['captureSummary']['hasVehicleData'])

    def test_empty_capture_is_labelled_and_coverage_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);identifier=rec.start()['active']['id']
            rec.stop()
            self.assertFalse(OBDRecorder(folder).snapshot()['sessions'][0]['captureSummary']['hasVehicleData'])
            rec.start();rec.set_coverage({'hasVehicleData':True,'scheduledReadings':5,'queriedReadings':3,
                'successfulReadings':2,'firstSweepComplete':False,'unavailable':{'0A':'NO DATA'},'ecuHeaders':['7E0']})
            second=rec.active['id'];rec.mark();rec.stop()
            restored=OBDRecorder(folder).snapshot()['sessions'][0]['captureSummary']
            self.assertTrue(restored['hasVehicleData']);self.assertFalse(restored['firstSweepComplete'])
            events=[json.loads(line) for line in rec.export(second,'jsonl')[0].splitlines()]
            self.assertTrue(any(e['type']=='marker' for e in events))
            self.assertEqual(events[-1]['data']['captureSummary']['queriedReadings'],3)
            with self.assertRaises(ValueError):rec.mark()


class DiscoveryTests(unittest.TestCase):
    def test_real_socket_auto_discovers_ecus_and_reads_uds_without_a_vehicle_profile(self):
        traffic=[]
        class ELM(socketserver.StreamRequestHandler):
            def handle(self):
                header='7DF'
                while True:
                    line=bytearray()
                    while True:
                        char=self.rfile.read(1)
                        if not char:return
                        if char==b'\r':break
                        line.extend(char)
                    command=line.decode();traffic.append((header,command))
                    if command.startswith('ATSH'):header=command[4:];reply='OK'
                    elif command=='ATDPN':reply='A6'
                    elif command.startswith('AT'):reply='ELM327 fixture' if command=='ATZ' else 'OK'
                    elif command=='0100':reply='7E8 06 41 00 08 00 00 00\r7E9 06 41 00 08 00 00 00'
                    elif command=='0105':reply='7E8 03 41 05 82\r7E9 03 41 05 80'
                    elif command=='03':reply='7E8 02 43 00'
                    elif command=='07':reply='7E8 02 47 00'
                    elif command=='1901FF':reply=('7E8' if header=='7E0' else '7E9')+' 06 59 01 FF 01 00 01'
                    elif command=='1902FF':reply=('7E8' if header=='7E0' else '7E9')+' 07 59 02 FF 01 23 45 A8'
                    elif command.startswith(('1904','1906')):reply='7E8 03 7F 19 31'
                    else:reply='NO DATA'
                    self.wfile.write((reply+'\r>').encode());self.wfile.flush()
        server=socketserver.ThreadingTCPServer(('127.0.0.1',0),ELM);server.daemon_threads=True
        threading.Thread(target=server.serve_forever,daemon=True).start()
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);identifier=rec.start({'mode':'simulator'})['active']['id']
            transport=Transport(f'tcp://127.0.0.1:{server.server_address[1]}');transport.observer=rec
            try:
                sweep=DiagnosticSweep(rec)
                for _ in range(30):sweep.next_at=0;sweep.step(transport)
                self.assertIn(('7E0','1902FF'),traffic);self.assertIn(('7E1','1902FF'),traffic)
                self.assertIn(('7E0','1904012345FF'),traffic)
                self.assertIsNone(transport.header)
                rec.stop()
                events=[json.loads(line) for line in rec.export(identifier,'jsonl')[0].splitlines()]
                statuses=[e for e in events if e['type']=='diagnostic' and e['data'].get('source')=='uds-dtc-status']
                self.assertEqual({e['data']['readings'][0]['ecu'] for e in statuses},{'7E8','7E9'})
                self.assertTrue(rec.snapshot()['sessions'][0]['captureSummary']['hasVehicleData'])
                self.assertFalse(any(cmd.startswith(('14','27','2E','31')) for _,cmd in traffic))
            finally:transport.close();rec.stop();server.shutdown();server.server_close()

    def test_model_free_uds_discovery_and_details_use_only_observed_ecus(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);rec.start();sweep=DiagnosticSweep(rec)
            try:
                sweep.ingest('0105','7E8 03 41 05 82>',1,2)
                self.assertIn(('7E0','1902FF'),sweep.pending)
                self.assertNotIn(('7E1','1902FF'),sweep.pending)
                sweep.ingest('1902FF','5902FF012345A8>',1,2,'7E0')
                self.assertIn(('7E0','1904012345FF'),sweep.pending)
                self.assertIn(('7E0','1906012345FF'),sweep.pending)
                before=len(sweep.pending)
                sweep.ingest('1902FF','5902FF012345A8>',1,2,'7E0')
                self.assertEqual(len(sweep.pending),before)
            finally:rec.stop()

    def test_fault_deadlines_preempt_a_long_discovery_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);rec.start();sweep=DiagnosticSweep(rec)
            transport=Mock();transport.query.return_value='4300>'
            sweep.commands[(None,'03')]=0;sweep.next_at=999999999999
            sweep.pending.extend((None,'0100') for _ in range(50))
            try:
                sweep.step(transport)
                transport.query.assert_called_once_with('03')
            finally:rec.stop()

    def test_disabled_fault_capture_never_queues_uds(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);rec.set_settings({**DEFAULT_SETTINGS,'faultCodes':False});rec.start()
            try:
                sweep=DiagnosticSweep(rec);sweep.ingest('0105','7E8 03 41 05 82>')
                self.assertFalse(any(cmd.startswith('19') for _,cmd in sweep.pending))
            finally:rec.stop()

    def test_marker_expedites_fault_codes_and_only_known_live_identifiers(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);rec.start();sweep=DiagnosticSweep(rec)
            sweep.commands[(None,'03')]=999999999999;sweep.discovered={'01':{0x0B,0x23}}
            t=Mock();t.query.return_value='4300>'
            try:
                rec.mark();sweep.step(t)
                t.query.assert_called_once_with('03')
                self.assertIn((None,'0123'),sweep.pending)
                self.assertNotIn((None,'0170'),sweep.pending)
            finally:rec.stop()

    def test_transport_blocks_mutations_and_functional_uds_requests(self):
        t=Transport.__new__(Transport);t.protocol='6';t.header=None
        for command in ('1902FF','1904012345FF','14FFFFFF','1003','2701','2E123400','31010001','04','1906FFFFFF00'):
            with self.subTest(command=command),self.assertRaises(ValueError):t.query(command)
        t.header='7E0';t._query=Mock(return_value='5902FF>');t.observer=None
        self.assertEqual(t.query('1902FF'),'5902FF>')
        self.assertEqual(t.query('1904012345FF'),'5902FF>')
        t.header='7DF'
        with self.assertRaises(ValueError):t.query('1902FF')

    def test_rejected_enhanced_address_does_not_abort_generic_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            rec=OBDRecorder(folder);rec.start();sweep=DiagnosticSweep(rec)
            sweep.pending.clear();sweep.pending.append(('7E0','1902FF'))
            t=Mock();t.select_header.side_effect=lambda header: (_ for _ in ()).throw(ValueError('Header unavailable')) if header else None
            try:
                result=sweep.step(t)
                self.assertIn('error',result)
                self.assertIn('7E0:1902FF',rec.coverage['unavailable'])
                self.assertTrue(rec.snapshot()['recording'])
            finally:rec.stop()


if __name__=='__main__':unittest.main()
