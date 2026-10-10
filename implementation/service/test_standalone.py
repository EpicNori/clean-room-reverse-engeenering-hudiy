import json
import importlib.util
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
from standalone_projection import StandaloneProjection
from independent_obd import IndependentOBDSettings
from independent_wireless import IndependentWireless
from bluez_agent import BluezAgent,wifi_frame
from obd import Transport,OBD
from independent_audio_route import IndependentAudioRoute

ADDRESS='AA:BB:CC:DD:EE:02'


class StandaloneTests(unittest.TestCase):
    def projection(self,folder):
        bridge=StandaloneProjection(socket_path=Path(folder)/'native.sock',preferences=Path(folder)/'projection.json')
        bridge.enabled=True;bridge.available=True;bridge.sock=Mock()
        return bridge

    def test_native_events_drive_live_data_and_renderer_without_legacy_api(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge=self.projection(directory)
            bridge._event({'event':'state','connected':True,'visible':False,'frames':91,'media':{'title':'Test track','source':'android'},'navigation':{}})
            state=bridge.snapshot()
            self.assertEqual(state['renderer'],'standalone')
            self.assertEqual(state['decodedFrames'],91)
            self.assertFalse(state['visible'])
            self.assertEqual(bridge.data_snapshot()['media']['title'],'Test track')
            self.assertTrue(bridge.phone_snapshot()['connected'])
            for event in ([],{}, {'event':'state','connected':'yes','visible':False}):
                with self.assertRaises(ValueError):bridge._event(event)

    def test_quit_routes_and_media_use_only_private_bounded_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge=self.projection(directory)
            for operation in ('shell','pair-native','quit_hudiy','dashboard;reboot'):
                with self.assertRaises(ValueError):bridge.action(operation)
            bridge.action('contacts')
            self.assertEqual(json.loads(bridge.sock.sendall.call_args.args[0]),{'operation':'route','route':'contacts'})
            with self.assertRaises(ConnectionError):bridge.action('media-next')
            bridge.request_exit()
            self.assertEqual(json.loads(bridge.sock.sendall.call_args.args[0]),{'operation':'exit'})
            with self.assertRaises(ConnectionError):bridge.action('resume')

    def test_handshake_alone_does_not_claim_video_or_a_real_microphone(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge=self.projection(directory)
            bridge._event({'event':'state','connected':True,'visible':False,'frames':0,'microphoneAvailable':False})
            self.assertFalse(bridge.snapshot()['videoReady'])
            self.assertFalse(bridge.snapshot()['microphoneAvailable'])
            bridge._event({'event':'state','connected':True,'visible':True,'frames':1,'microphoneAvailable':True})
            self.assertTrue(bridge.snapshot()['videoReady'])
            self.assertTrue(bridge.snapshot()['microphoneAvailable'])
            bridge._event({'event':'state','connected':False,'visible':False,'frames':1})
            self.assertFalse(bridge.snapshot()['videoReady'])

    def test_usb_selection_suppresses_competing_wireless_bootstrap(self):
        wireless=Mock();wireless.credentials.return_value={'enabled':True}
        agent=BluezAgent(Mock(),wireless,Mock())
        connection=Mock();agent.connection=connection
        agent.select_transport('usb')
        self.assertFalse(agent.wireless_allowed())
        connection.shutdown.assert_called_once()
        agent.retrigger();connection.sendall.assert_not_called()
        agent.select_transport('wifi')
        self.assertTrue(agent.wireless_allowed())
        with self.assertRaises(ValueError):agent.select_transport('shell')

    def test_options_are_durable_and_rollback_native_state_on_write_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge=self.projection(directory)
            bridge.settings({'taskbarVisible':False,'autostart':False,'dayNight':'Night'})
            self.assertFalse(json.loads(bridge.preferences.read_text())['taskbarVisible'])
            with patch('standalone_projection.save_json',side_effect=OSError('Disk full')):
                with self.assertRaises(OSError):bridge.settings({'autostart':True})
            self.assertFalse(bridge.options['autostart'])
            self.assertFalse(json.loads(bridge.sock.sendall.call_args.args[0])['options']['autostart'])
            for value in ({'autostart':1},{'dayNight':'invalid'},{'command':'shell'}):
                with self.assertRaises(ValueError):bridge.settings(value)

    def test_obd_preferences_own_connection_and_reject_unpaired_adapters(self):
        with tempfile.TemporaryDirectory() as directory:
            bluetooth=Mock(enabled=True)
            bluetooth.snapshot.return_value={'devices':[{'address':ADDRESS,'paired':True,'serialPort':True}]}
            obd=Mock()
            settings=IndependentOBDSettings(bluetooth,obd,Path(directory)/'obd.json')
            settings.save(ADDRESS,2)
            self.assertEqual(settings.port(),f'bluetooth://{ADDRESS}/2')
            obd.reconnect_independent.assert_called_once()
            for channel in (0,31,True,'2'):
                with self.assertRaises(ValueError):settings.save(ADDRESS,channel)
            bluetooth.snapshot.return_value={'devices':[]}
            self.assertIsNone(settings.port())
            with self.assertRaises(ValueError):settings.save(ADDRESS,2)

    def test_direct_rfcomm_connection_is_bounded_and_read_only(self):
        fake=Mock();fake.recv.return_value=b'41 0D 64>'
        with patch('obd.socket.AF_BLUETOOTH',31,create=True),patch('obd.socket.BTPROTO_RFCOMM',3,create=True),patch('obd.socket.socket',return_value=fake):
            transport=Transport(f'bluetooth://{ADDRESS}/2')
            fake.connect.assert_called_once_with((ADDRESS,2))
            self.assertEqual(transport.query('010D'),'41 0D 64>')
            with self.assertRaises(ValueError):transport.query('04')
            transport.close();fake.close.assert_called()
        for port in (f'bluetooth://{ADDRESS}/0',f'bluetooth://{ADDRESS}/31','bluetooth://example.com/2'):
            with self.assertRaises(ValueError):Transport(port)

    def test_wifi_secret_never_appears_in_public_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wireless.json'
            config={'enabled':True,'ssid':'Test car','passphrase':'private-test-key','ipAddress':'192.168.12.1','port':5277}
            path.write_text(json.dumps(config))
            settings=IndependentWireless(Mock(enabled=True),path)
            self.assertNotIn('passphrase',settings.snapshot())
            self.assertNotIn('private-test-key',json.dumps(settings.snapshot()))
            with patch('independent_wireless.subprocess.run',return_value=Mock(returncode=1)):
                with self.assertRaises(ConnectionError):settings.save(False,True)
            self.assertTrue(settings.snapshot()['enabled'])
            self.assertTrue(json.loads(path.read_text())['enabled'])

    def test_pairing_requires_fresh_request_and_explicit_pin_or_confirmation(self):
        bluetooth=Mock();bluetooth.snapshot.return_value={'devices':[{'address':ADDRESS,'name':'Adapter'}]}
        agent=BluezAgent(bluetooth,Mock(),Mock())
        results=[]
        thread=threading.Thread(target=lambda:results.append(agent.prompt('/org/bluez/hci0/dev_'+ADDRESS.replace(':','_'),'pin')))
        thread.start()
        with agent.condition:agent.condition.wait_for(lambda:agent.pending is not None,timeout=.2)
        # The condition also guards expiry and duplicate answers.
        pending=agent.snapshot()['pairing']
        with self.assertRaises(ValueError):agent.confirm(pending['id'],True,'9999')
        with self.assertRaises(ValueError):agent.confirm(pending['id']+1,True,'1234')
        agent.confirm(pending['id'],True,'1234');thread.join(timeout=1)
        self.assertEqual(results,['1234'])
        with self.assertRaises(ValueError):agent.confirm(pending['id'],True,'1234')

    def test_wifi_frames_use_length_prefix_and_do_not_accept_unbounded_payloads(self):
        self.assertEqual(wifi_frame(1,b'abc'),struct.pack('>HH',3,1)+b'abc')
        with self.assertRaises(ValueError):wifi_frame(9,b'')
        with self.assertRaises(ValueError):wifi_frame(3,b'x'*4097)

    def test_duplicate_pairing_cannot_start_two_workers_before_pin_prompt(self):
        bluetooth=Mock();bluetooth.snapshot.return_value={'devices':[{'address':ADDRESS,'name':'Adapter','paired':False}]}
        agent=BluezAgent(bluetooth,Mock(),Mock());agent.ready=True
        with patch('bluez_agent.threading.Thread') as thread:
            agent.pair(ADDRESS)
            with self.assertRaises(ConnectionError):agent.pair(ADDRESS)
            thread.assert_called_once()
            self.assertTrue(agent.snapshot()['pairingBusy'])

    def test_wifi_write_failure_restores_the_previous_network_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wireless.json'
            config={'enabled':True,'ssid':'Test car','passphrase':'private-test-key','ipAddress':'192.168.12.1','port':5277}
            path.write_text(json.dumps(config))
            projection=Mock(enabled=True);settings=IndependentWireless(projection,path)
            with patch('independent_wireless.subprocess.run',return_value=Mock(returncode=0)) as command,patch('independent_wireless.save_json',side_effect=OSError('Disk full')):
                with self.assertRaises(OSError):settings.save(False,True)
                self.assertEqual([call.args[0][2] for call in command.call_args_list],['modify','down','modify','up'])
                self.assertEqual(command.call_args_list[0].args[0][-1],'no')
                self.assertEqual(command.call_args_list[2].args[0][-1],'yes')
            self.assertTrue(settings.snapshot()['enabled'])
            self.assertEqual(json.loads(path.read_text()),config)
            projection.reload_wireless.assert_not_called()

    def test_hotspot_disabled_preference_also_disables_next_boot_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wireless.json'
            path.write_text(json.dumps({'enabled':True,'ssid':'Test car','passphrase':'private-test-key','ipAddress':'192.168.12.1','port':5277}))
            projection=Mock(enabled=True);settings=IndependentWireless(projection,path)
            with patch('independent_wireless.subprocess.run',return_value=Mock(returncode=0)) as command:
                settings.save(False,True)
                self.assertEqual(command.call_args_list[0].args[0],['nmcli','connection','modify','hudiy-recreation-car','connection.autoconnect','no'])
                self.assertEqual(command.call_args_list[1].args[0],['nmcli','connection','down','hudiy-recreation-car'])
            self.assertFalse(json.loads(path.read_text())['enabled'])
            projection.reload_wireless.assert_called_once_with()

    def test_radio_routes_only_our_process_and_waits_during_calls(self):
        sink='bluez_output.'+ADDRESS.replace(':','_')+'.1'
        bluetooth=Mock();bluetooth.snapshot.return_value={'devices':[{'address':ADDRESS,'paired':True,'connected':True,'audioReceiver':True}]}
        projection=Mock();projection.snapshot.return_value={'runtimePid':123}
        calls=Mock();calls.snapshot.return_value={'call':{'state':0}}
        route=IndependentAudioRoute(bluetooth,projection,calls);route.address=ADDRESS
        streams=[{'index':10,'sink':1,'properties':{'application.process.id':'123'}},
                 {'index':11,'sink':1,'properties':{'application.process.id':'999'}}]
        mutations=[];default=['other']
        def command(*args):
            if args==('-f','json','list','sinks'):return json.dumps([{'name':sink,'index':2}]).encode()
            if args==('-f','json','list','sink-inputs'):return json.dumps(streams).encode()
            if args==('get-default-sink',):return default[0].encode()
            mutations.append(args)
            if args[0]=='move-sink-input':streams[0]['sink']=2
            if args[0]=='set-default-sink':default[0]=sink
            return b''
        route._command=Mock(side_effect=command)
        route._tick();self.assertFalse(route.snapshot()['routed'])
        self.assertEqual(mutations,[('move-sink-input','10',sink),('set-default-sink',sink)])
        self.assertEqual(streams[1]['sink'],1)
        route._tick();self.assertTrue(route.snapshot()['routed'])
        calls.snapshot.return_value={'call':{'state':2}}
        route._command.reset_mock();route._tick();route._command.assert_not_called()

    def test_manual_bluetooth_obd_read_keeps_required_reconnect_monitor(self):
        obd=OBD();obd.independent_settings=Mock();obd._connect=Mock()
        obd.connect(f'bluetooth://{ADDRESS}/2')
        self.assertTrue(obd.automatic)
        obd.connect('/dev/ttyUSB0')
        self.assertFalse(obd.automatic)

    def test_startup_replacement_is_recoverable_and_preserves_other_services(self):
        source=Path(__file__).resolve().parents[1]/'launcher/install_autostart.py'
        spec=importlib.util.spec_from_file_location('standalone_startup',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        original='#!/bin/sh\nother-service &\n$HOME/.hudiy/share/hudiy_run.sh\npython3 /home/noriel/hudiy-examples/examples/obd_charts/charts.py >> /tmp/chart.log 2>&1 &\n# BEGIN HUDIY RECREATION\nold-host &\n# END HUDIY RECREATION\n'
        updated=module.replace_startup(original,Path('/home/test/launcher.py'),Path('/home/test/app.log'))
        self.assertIn('other-service &',updated)
        self.assertNotIn('\nold-host &',updated)
        self.assertNotIn('\n$HOME/.hudiy/share/hudiy_run.sh',updated)
        self.assertNotIn('\npython3 /home/noriel/hudiy-examples',updated)
        self.assertEqual(updated,module.replace_startup(updated,Path('/home/test/launcher.py'),Path('/home/test/app.log')))
        with self.assertRaises(ValueError):module.replace_startup('# BEGIN HUDIY RECREATION',Path('/tmp/app'),Path('/tmp/log'))

if __name__=='__main__':unittest.main()
