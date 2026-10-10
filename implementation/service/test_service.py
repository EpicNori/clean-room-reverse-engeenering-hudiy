import json
import socketserver
import threading
import time
import unittest
from unittest.mock import Mock, patch
import urllib.request
import urllib.error
from obd import decode,Transport,OBD
import server

class ELM(socketserver.StreamRequestHandler):
    def handle(self):
        buffer=b''
        while True:
            part=self.rfile.read(1)
            if not part:return
            if part!=b'\r':buffer+=part;continue
            command=buffer.decode();buffer=b''
            values={'ATZ':'ELM327 v1.5','010C':'41 0C 1A F8','010D':'41 0D 64','0105':'41 05 7D','0104':'41 04 80','0111':'41 11 40','0142':'41 42 37 78'}
            self.wfile.write((values.get(command,'OK')+'\r>').encode());self.wfile.flush()

class SensorTests(unittest.TestCase):
    def test_real_frames_echo_and_can_header(self):
        self.assertEqual(decode('0C','010C\rSEARCHING...\r7E8 04 41 0C 1A F8\r>'),1726)
        self.assertEqual(decode('05','41057D>'),85)
        self.assertEqual(decode('0D','41 0D 64>'),100)
        self.assertEqual(decode('42','41 42 37 78>'),14.2)
    def test_no_data_and_truncated_frames(self):
        for text in ['NO DATA>','41 0C 1A>','STOPPED>','UNABLE TO CONNECT>']:
            self.assertIsNone(decode('0C',text))
        with self.assertRaises(ValueError):decode('04;shutdown','')
    def test_transport_rejects_files_networks_and_commands(self):
        for port in ['/etc/passwd','/dev/zero','tcp://example.com:5000','tcp://127.0.0.1:22','COM1 & shutdown']:
            with self.assertRaises(ValueError):Transport(port)
    def test_sensor_poll_and_disconnect_clear_stale_values(self):
        simulator=socketserver.ThreadingTCPServer(('127.0.0.1',0),ELM)
        simulator.daemon_threads=True
        thread=threading.Thread(target=simulator.serve_forever,daemon=True);thread.start()
        obd=OBD()
        try:
            obd.connect(f'tcp://127.0.0.1:{simulator.server_address[1]}')
            deadline=time.monotonic()+5
            while time.monotonic()<deadline and not obd.snapshot()['values']:time.sleep(.05)
            state=obd.snapshot()
            self.assertEqual(state['values']['rpm'],1726)
            self.assertEqual(state['values']['speed'],100)
            self.assertEqual(state['mode'],'simulator')
            with self.assertRaises(ValueError):obd.transport.query('04')
            obd.disconnect()
            self.assertFalse(obd.snapshot()['connected'])
            self.assertEqual(obd.snapshot()['values'],{})
        finally:obd.disconnect();simulator.shutdown();simulator.server_close()

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.port=cls.http.server_address[1]
        server.ALLOWED_PORTS.add(cls.port)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();server.ALLOWED_PORTS.remove(cls.port)
    def request(self,path,body=None,headers=None):
        req=urllib.request.Request(f'http://127.0.0.1:{self.port}'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
        try:return urllib.request.urlopen(req,timeout=3)
        except urllib.error.HTTPError as e:return e
    def test_status_does_not_claim_disconnected_hardware(self):
        with self.request('/api/status') as r:
            data=json.load(r);self.assertFalse(data['capabilities']['projection']);self.assertFalse(data['phone']['connected'])
            self.assertEqual(r.headers['X-Content-Type-Options'],'nosniff')
    def test_dns_rebinding_and_cross_origin_rejected(self):
        with self.request('/api/status',headers={'Host':'attacker.example'}) as r:self.assertEqual(r.status,403)
        with self.request('/api/action',{'action':'obd-disconnect'},headers={'Origin':'https://attacker.example'}) as r:self.assertEqual(r.status,403)
    def test_path_traversal_and_command_injection_rejected(self):
        with self.request('/%2e%2e/service/server.py') as r:self.assertEqual(r.status,403)
        with self.request('/api/action',{'action':'shell','command':'whoami'}) as r:self.assertEqual(r.status,400)
        with self.request('/api/action',{'action':'obd-connect','port':'/etc/passwd'}) as r:self.assertEqual(r.status,400)
    def test_false_integration_success_never_returned(self):
        with self.request('/api/action',{'action':'projection'}) as r:self.assertEqual(r.status,501)
        with self.request('/api/action',[]) as r:self.assertEqual(r.status,400)
    def test_standalone_taskbar_change_retriggers_owned_wireless_only_after_save(self):
        projection=Mock(enabled=True)
        projection.snapshot.return_value={'options':{'taskbarVisible':True}}
        projection.settings.return_value={'options':{'taskbarVisible':False}}
        agent=Mock()
        with patch.object(server,'STANDALONE',True),patch.object(server,'projection',projection),patch.object(server,'agent',agent):
            with self.request('/api/action',{'action':'projection-settings','taskbarVisible':False}) as response:
                self.assertEqual(response.status,200)
            agent.reconnect_after_layout.assert_called_once_with()
            agent.reset_mock()
            projection.settings.return_value={'options':{'taskbarVisible':True}}
            with self.request('/api/action',{'action':'projection-settings','autostart':True}) as response:
                self.assertEqual(response.status,200)
            agent.reconnect_after_layout.assert_not_called()
            projection.settings.side_effect=ValueError('Invalid settings')
            with self.request('/api/action',{'action':'projection-settings','taskbarVisible':'false'}) as response:
                self.assertEqual(response.status,400)
            agent.reconnect_after_layout.assert_not_called()
    def test_phone_actions_cannot_accept_caller_supplied_paths_or_missing_confirmation(self):
        with self.request('/api/action',{'action':'phone-call','number':'123456','confirmed':True}) as r:self.assertEqual(r.status,501)
        fake=Mock(enabled=True);fake.command.return_value={'accepted':True}
        with patch.object(server,'calls',fake):
            for body in ({'action':'phone-call','number':'123456'}, {'action':'phone-end','path':'/arbitrary'}, {'action':'phone-answer','method':'Dial'}):
                with self.request('/api/action',body) as r:self.assertEqual(r.status,400)
            fake.command.assert_not_called()
            with self.request('/api/action',{'action':'phone-call','number':'123456','confirmed':True}) as r:self.assertEqual(r.status,200)
            fake.command.assert_called_once_with('dial','123456',True,None)
    def test_wireless_and_radio_actions_reject_paths_and_require_pi_host(self):
        with self.request('/api/action',{'action':'wireless-hotspot','enabled':True,'confirmed':True}) as r:self.assertEqual(r.status,501)
        with self.request('/api/action',{'action':'audio-radio-output','address':''}) as r:self.assertEqual(r.status,501)
        fake=Mock(enabled=True);fake.snapshot.return_value={'available':True}
        wireless=Mock();radio=Mock(enabled=True);calls=Mock();calls.snapshot.return_value={'call':{'state':0}}
        wireless.save.return_value={'saved':True};radio.save.return_value={'saved':True}
        with patch.object(server,'projection',fake),patch.object(server,'wireless',wireless),patch.object(server,'radio_output',radio),patch.object(server,'calls',calls):
            for body in ({'action':'wireless-hotspot','enabled':True}, {'action':'wireless-hotspot','enabled':True,'confirmed':True,'passphrase':'secret'}, {'action':'audio-radio-output','address':'','sink':'shell'}):
                with self.request('/api/action',body) as r:self.assertEqual(r.status,400)
            wireless.save.assert_not_called();radio.save.assert_not_called()
            with self.request('/api/action',{'action':'wireless-hotspot','enabled':True,'confirmed':True}) as r:self.assertEqual(r.status,200)
            calls.snapshot.return_value={'call':{'state':3}}
            with self.request('/api/action',{'action':'audio-radio-output','address':''}) as r:self.assertEqual(r.status,503)
            radio.save.assert_not_called()
    def test_brightness_is_host_only_and_cannot_accept_device_paths(self):
        with self.request('/api/action',{'action':'display-brightness','brightness':50}) as r:self.assertEqual(r.status,501)
        fake=Mock(enabled=True)
        fake.set.return_value={'saved':True,'brightness':52,'available':True}
        with patch.object(server,'display',fake):
            with self.request('/api/action',{'action':'display-brightness','brightness':50,'path':'/etc/passwd'}) as r:self.assertEqual(r.status,400)
            fake.set.assert_not_called()
            with self.request('/api/action',{'action':'display-brightness','brightness':50}) as r:self.assertEqual(r.status,200)
            fake.set.assert_called_once_with(50)
    def test_application_quit_is_host_only_and_rejects_arbitrary_process_arguments(self):
        with self.request('/api/action',{'action':'application-quit'}) as r:self.assertEqual(r.status,501)
        fake=Mock(enabled=True)
        fake.request_exit.return_value={'accepted':True}
        with patch.object(server,'projection',fake):
            for extra in ({'pid':1},{'command':'shutdown'},{'restart':True}):
                with self.request('/api/action',{'action':'application-quit',**extra}) as r:self.assertEqual(r.status,400)
            fake.request_exit.assert_not_called()
            with self.request('/api/action',{'action':'application-quit'}) as r:
                self.assertEqual(r.status,200)
                self.assertTrue(json.load(r)['accepted'])
            fake.request_exit.assert_called_once_with()
    def test_bluetooth_actions_reject_extra_arguments_and_disabled_host(self):
        with self.request('/api/action',{'action':'bluetooth-media','operation':'toggle'}) as r:self.assertEqual(r.status,501)
        with self.request('/api/action',{'action':'bluetooth-scan'}) as r:self.assertEqual(r.status,501)
        fake=Mock(enabled=True)
        with patch.object(server,'bluetooth',fake):
            for body in ({'action':'bluetooth-scan','adapter':'/org/bluez/hci1'},
                         {'action':'bluetooth-remove','address':'AA:BB:CC:DD:EE:01','confirmed':True,'command':'shell'},
                         {'action':'bluetooth-media','operation':'next','path':'/arbitrary/player0'}):
                with self.request('/api/action',body) as r:self.assertEqual(r.status,400)
            fake.command.assert_not_called()
            fake.playback.assert_not_called()
if __name__=='__main__':unittest.main()
