import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from custom_obd import CustomOBDStore, DEFAULT_CONFIG, RevisionConflict, calculate, decode_codes, decode_sensor, validate_config
from driving_stats import DrivingStats
from obd import Transport, OBD


def sensor(**changes):
    return {'id':'oil','label':'Oil temperature','unit':'°C','mode':'01','pid':'5C','header':None,'bytes':1,'formula':'A-40','min':-40,'max':180,'decimals':1,'interval':5,**changes}


class CustomOBDTests(unittest.TestCase):
    def test_byte_formulas_and_frame_identity(self):
        self.assertEqual(calculate('(A*256+B)/4',bytes.fromhex('1AF8')),1726)
        self.assertEqual(calculate('(A&128)//128',bytes([128])),1)
        self.assertEqual(decode_sensor(sensor(),'015C\r7E8 03 41 5C 64\r>'),60)
        self.assertEqual(decode_sensor(sensor(mode='22',pid='1234',formula='A'),'221234\r0:62123464\r>'),100)
        for raw in ('NO DATA>','41 05 64>','41 5C>'):
            with self.assertRaises(ValueError):decode_sensor(sensor(),raw)
    def test_formula_never_executes_code_and_bounds_resources(self):
        for formula in ('__import__("os")','A.__class__','[A]','A**999','1e300','1/0','H','A<<999','A+'*80):
            with self.subTest(formula=formula),self.assertRaises(ValueError):calculate(formula,bytes([1]))
        for patch_data in ({'mode':'04'},{'pid':'0C\r04'},{'header':'7E0\r04'},{'bytes':True},{'interval':0},{'formula':'B'},{'max':float('nan')}):
            config=copy.deepcopy(DEFAULT_CONFIG); config['sensors']=[sensor(**patch_data)]
            with self.assertRaises(ValueError):validate_config(config)
    def test_layout_changes_preserve_mapping_identity_but_formula_changes_invalidate_it(self):
        with tempfile.TemporaryDirectory() as folder:
            store=CustomOBDStore(True,Path(folder)/'dashboard.json')
            cfg=copy.deepcopy(DEFAULT_CONFIG);cfg['sensors']=[sensor()]
            first=store.save({'revision':0,'config':cfg})
            cfg['widgets'][0]['title']='Speed in my car'
            second=store.save({'revision':first['revision'],'config':cfg})
            self.assertEqual(first['mappingRevision'],second['mappingRevision'])
            cfg['sensors'][0]['formula']='A-50'
            third=store.save({'revision':second['revision'],'config':cfg})
            self.assertNotEqual(second['mappingRevision'],third['mappingRevision'])
            self.assertEqual(CustomOBDStore(True,store.path).snapshot()['mappingRevision'],third['mappingRevision'])

    def test_positions_and_references_are_validated(self):
        for change in ({'x':4},{'w':True},{'source':'custom:missing'},{'view':'html'},{'title':'x'*41}):
            config=copy.deepcopy(DEFAULT_CONFIG); config['widgets'][0].update(change)
            with self.assertRaises(ValueError):validate_config(config)
        config=copy.deepcopy(DEFAULT_CONFIG); config['widgets'][1].update(x=0,y=0)
        with self.assertRaises(ValueError):validate_config(config)
    def test_durable_save_conflict_and_failed_write_leave_original_intact(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'dashboard.json'; store=CustomOBDStore(True,path)
            config=copy.deepcopy(DEFAULT_CONFIG); config['widgets'][0]['title']='My speed'
            store.save({'revision':0,'config':config})
            reopened=CustomOBDStore(True,path)
            self.assertEqual(reopened.snapshot()['config'],config); self.assertEqual(reopened.revision,1)
            with self.assertRaises(RevisionConflict):store.save({'revision':0,'config':config})
            with patch('custom_obd.save_json',side_effect=OSError('Full disk')):
                with self.assertRaises(OSError):store.save({'revision':1,'config':DEFAULT_CONFIG})
            self.assertEqual(store.snapshot(),reopened.snapshot())
            snapshot=store.snapshot(); snapshot['config']['widgets'].clear()
            self.assertTrue(store.snapshot()['config']['widgets'])
            if __import__('os').name!='nt':self.assertEqual(path.stat().st_mode&0o777,0o600)
    def test_corrupt_storage_and_preview_cannot_overwrite_device_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'dashboard.json'
            for raw in ('{','[]','x'*16385):
                path.write_text(raw)
                self.assertEqual(CustomOBDStore(True,path).snapshot()['config'],DEFAULT_CONFIG)
            with self.assertRaises(ConnectionError):CustomOBDStore(False,path).save({'revision':0,'config':DEFAULT_CONFIG})
    def test_read_only_queries_headers_and_restoration(self):
        t=Transport.__new__(Transport); t.header=None; t.protocol=None
        t.query=Mock(side_effect=['A6\r>','OK>','62123464>','OK>'])
        self.assertEqual(t.query_sensor(sensor(mode='22',pid='1234',header='7E0')),'62123464>')
        t.select_header(None)
        self.assertEqual([call.args[0] for call in t.query.call_args_list],['ATDPN','ATSH7E0','221234','ATSH7DF'])
        t=Transport.__new__(Transport); t.closed=True
        for command in ('04','08','2E123400','ATSHFFF','ATSH20000000','010C\r04','ATWR'):
            with self.assertRaises(ValueError):t.query(command)
    def test_diagnostic_codes_preserve_identity_and_do_not_clear_them(self):
        self.assertEqual(decode_codes('43 01 33 04 20 00 00>'),['P0133','P0420'])
        self.assertEqual(decode_codes('43 02 01 33 04 20>'),['P0133','P0420'])
        self.assertEqual(decode_codes('43 00 00 00 00 00 00>'),[])
        self.assertEqual(decode_codes('43 01 33 00 00 00 00\r43 04 20 00 00 00 00>'),['P0133','P0420'])
        self.assertEqual(decode_sensor(sensor(mode='22',pid='1234',bytes=4,formula='D'),'007\r0: 62 12 34 11 22\r1: 33 44>'),68)
        with self.assertRaises(ValueError):decode_codes('NO DATA>')


class PollingIntegrationTests(unittest.TestCase):
    def test_custom_sensor_polling_layout_updates_and_disconnect_use_the_real_transport(self):
        import socketserver
        import threading
        import time
        from test_obd_automatic import FRAMES
        commands=[]
        class Fixture(socketserver.StreamRequestHandler):
            def handle(self):
                line=bytearray()
                while True:
                    part=self.rfile.read(1)
                    if not part:return
                    if part!=b'\r':line.extend(part);continue
                    command=line.decode();line.clear();commands.append(command)
                    value='ELM327 fixture' if command=='ATZ' else '415C64' if command=='015C' else '43010133' if command=='03' else FRAMES.get(command,'OK')
                    self.wfile.write((value+'\r>').encode());self.wfile.flush()
        fake=socketserver.ThreadingTCPServer(('127.0.0.1',0),Fixture);fake.daemon_threads=True
        thread=threading.Thread(target=fake.serve_forever,daemon=True);thread.start()
        obd=OBD()
        def await_state(predicate):
            deadline=time.monotonic()+4
            while time.monotonic()<deadline:
                value=obd.snapshot()
                if predicate(value):return value
                time.sleep(.01)
            self.fail('Custom OBD state was not updated')
        try:
            with tempfile.TemporaryDirectory() as folder:
                store=CustomOBDStore(True,Path(folder)/'dashboard.json');cfg=copy.deepcopy(DEFAULT_CONFIG)
                cfg['sensors']=[sensor()];cfg['widgets'].append({'id':'oil_tile','source':'custom:oil','title':'','view':'value','x':3,'y':0,'w':1,'h':1})
                first=store.save({'revision':0,'config':cfg});obd.custom_dashboard=store
                obd.connect(f'tcp://127.0.0.1:{fake.server_address[1]}')
                initial=await_state(lambda st:st['custom'].get('oil',{}).get('value')==60)
                self.assertEqual(initial['mode'],'simulator');self.assertEqual(initial['diagnostics']['codes'],['P0133'])
                original_stamp=initial['custom']['oil']['timestamp'];scans=commands.count('03')
                cfg['widgets'][0]['title']='My speed'
                second=store.save({'revision':first['revision'],'config':cfg})
                updated=await_state(lambda st:st['timestamp'] and st['timestamp']>initial['timestamp'])
                self.assertEqual(updated['custom']['oil']['timestamp'],original_stamp)
                self.assertEqual(updated['customRevision'],first['mappingRevision']);self.assertEqual(commands.count('03'),scans)
                cfg['sensors'][0]['formula']='A-50'
                third=store.save({'revision':second['revision'],'config':cfg})
                changed=await_state(lambda st:st['customRevision']==third['mappingRevision'] and st['custom'].get('oil',{}).get('value')==50)
                self.assertTrue(any(row.get('custom:oil')==50 for row in changed['history']))
                self.assertNotIn('04',commands)
                cfg['widgets']=[w for w in cfg['widgets'] if not w['source'].startswith('custom:')]
                store.save({'revision':third['revision'],'config':cfg})
                await_state(lambda st:not st['custom'])
                obd.disconnect();state=obd.snapshot()
                self.assertEqual(state['custom'],{});self.assertEqual(state['derived'],{});self.assertEqual(state['diagnostics']['codes'],[])
        finally:obd.close();fake.shutdown();fake.server_close()


class GaugeVariantTests(unittest.TestCase):
    def test_original_arc_and_tick_gauges_are_accepted_without_breaking_old_layouts(self):
        cfg=copy.deepcopy(DEFAULT_CONFIG)
        for view in ('gauge','gauge2'):
            cfg['widgets'][0]['view']=view
            self.assertEqual(validate_config(cfg)['widgets'][0]['view'],view)


class StatisticsTests(unittest.TestCase):
    def test_acceleration_requires_continuous_valid_speed_and_gaps_reset(self):
        stats=DrivingStats(); opts=DEFAULT_CONFIG['range']
        self.assertIsNone(stats.update(1,{'speed':0},{},opts)['acceleration'])
        self.assertEqual(stats.update(2,{'speed':36},{},opts)['acceleration'],10)
        self.assertIsNone(stats.update(20,{'speed':90},{},opts)['acceleration'])
        self.assertIsNone(stats.update(21,{'speed':None},{},opts)['acceleration'])
    def test_zero_to_hundred_requires_standstill_and_aborts_after_gap(self):
        stats=DrivingStats(); opts=DEFAULT_CONFIG['range']
        for t in range(3):stats.update(t,{'speed':0},{},opts)
        stats.update(3,{'speed':20},{},opts)
        for t,speed in ((4,40),(5,60),(6,80),(7,100)):result=stats.update(t,{'speed':speed},{},opts)
        self.assertEqual(result['zeroToHundred'],5)
        stats.reset(); stats.update(0,{'speed':0},{},opts); stats.update(1,{'speed':0},{},opts); stats.update(2,{'speed':0},{},opts)
        stats.update(3,{'speed':30},{},opts)
        self.assertIsNone(stats.update(20,{'speed':100},{},opts)['zeroToHundred'])
    def test_implausible_speed_jumps_do_not_complete_a_performance_run(self):
        stats=DrivingStats();opts=DEFAULT_CONFIG['range']
        for t in range(3):stats.update(t,{'speed':0},{},opts)
        result=stats.update(3,{'speed':200},{},opts)
        self.assertIsNone(result['acceleration']);self.assertIsNone(result['zeroToHundred'])

    def test_coasting_counts_distance_and_missing_fuel_samples_clear_estimates(self):
        stats=DrivingStats();settings={'tankLitres':50,'fuelLevel':'custom:level','fuelRate':'custom:rate'}
        for t in range(11):
            custom={'level':{'value':50,'timestamp':t},'rate':{'value':5 if t<=5 else 0,'timestamp':t}}
            result=stats.update(t,{'speed':100},custom,settings)
        self.assertEqual(result['averageConsumption'],2.5)
        missing=stats.update(11,{'speed':100},{},settings)
        self.assertIsNone(missing['range']);self.assertIsNone(missing['averageConsumption'])
        stats.update(12,{'speed':None},{},settings)
        self.assertEqual(stats.distance,0)

    def test_range_requires_units_inputs_capacity_and_sufficient_distance(self):
        stats=DrivingStats(); settings={'tankLitres':50,'fuelLevel':'custom:level','fuelRate':'custom:rate'}
        result=None
        for t in range(12):
            custom={'level':{'value':50,'timestamp':t},'rate':{'value':5,'timestamp':t}}
            result=stats.update(t,{'speed':100},custom,settings)
        self.assertAlmostEqual(result['range'],500,places=1)
        self.assertEqual(result['averageConsumption'],5)
        self.assertIsNone(stats.update(12,{'speed':100},{},settings)['range'])
        self.assertIsNone(stats.update(30,{'speed':100},custom,settings)['range'])


if __name__=='__main__':unittest.main()
