import json
import io
from types import SimpleNamespace
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from unittest.mock import Mock
import sys

from projection import Projection, field, fields, receive_exact, MAX_FRAME, read_options

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
from hudiy_host import configure, exit_state
import hudiy_host


class ProjectionTests(unittest.TestCase):
    def test_day_night_sends_native_modes_and_restores_private_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'projection.json'
            bridge=Projection(True)
            bridge.available,bridge.api_minor,bridge.sock=True,3,Mock()
            for mode,number in [('Day',2),('Night',3),('Common',1)]:
                result=bridge.settings({'dayNight':mode},path)
                frame=bridge.sock.sendall.call_args.args[0]
                self.assertEqual(struct.unpack('<III',frame[:12])[1],50)
                self.assertEqual(fields(frame[12:]),{1:number})
                self.assertEqual(result['options']['dayNight'],mode)
                self.assertEqual(read_options(path)['dayNight'],mode)
            bridge.settings({'darkMode':True},path)
            frame=bridge.sock.sendall.call_args.args[0]
            self.assertEqual(struct.unpack('<III',frame[:12])[1],37)
            self.assertEqual(fields(frame[12:]),{1:1})
            restored=read_options(path)
            bridge.sock.reset_mock()
            bridge._apply_visual_options(restored,{'dayNight','darkMode'})
            frames=[c.args[0] for c in bridge.sock.sendall.call_args_list]
            self.assertEqual([(struct.unpack('<III',f[:12])[1],fields(f[12:])) for f in frames],[(37,{1:1}),(50,{1:1})])
            if sys.platform != 'win32':self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_invalid_unavailable_and_older_day_night_settings_never_send_or_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'projection.json'
            bridge=Projection(True)
            bridge.sock=Mock();bridge.api_minor=3
            for data in ({'dayNight':'NIGHT;shutdown'},{'dayNight':{}},{'dayNight':3},{'darkMode':1},{'nativeAction':'shell'},[]):
                with self.assertRaises(ValueError):bridge.settings(data,path)
            with self.assertRaises(ConnectionError):bridge.settings({'dayNight':'Night'},path)
            bridge.available=True;bridge.api_minor=2
            with self.assertRaises(ConnectionError):bridge.settings({'dayNight':'Night'},path)
            bridge.api_minor=3;bridge.exit_requested=True
            with self.assertRaises(ConnectionError):bridge.settings({'darkMode':True},path)
            bridge.sock.sendall.assert_not_called()
            self.assertFalse(path.exists())

    def test_day_night_save_failure_never_changes_native_mode(self):
        bridge=Projection(True)
        bridge.available,bridge.api_minor,bridge.sock=True,3,Mock()
        bridge.options['dayNight']='Day'
        with patch('projection.save_json',side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):bridge.settings({'dayNight':'Night'})
        self.assertEqual(bridge.options['dayNight'],'Day')
        bridge.sock.sendall.assert_not_called()

    def test_day_night_send_failure_restores_saved_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'projection.json'
            bridge=Projection(True)
            bridge.available,bridge.api_minor,bridge.sock=True,3,Mock()
            bridge.options['dayNight']='Day'
            bridge.sock.sendall.side_effect=OSError('Connection lost')
            with self.assertRaises(OSError):bridge.settings({'dayNight':'Night'},path)
            self.assertEqual(read_options(path)['dayNight'],'Day')
            self.assertEqual(bridge.options['dayNight'],'Day')

    def test_wireless_quit_requires_manual_resume_and_reconnects_over_wifi(self):
        bridge=Projection(True)
        bridge.available,bridge.sock=True,Mock()
        bridge.usb=Mock();bridge.usb.accessory.return_value=None
        bridge.action('wifi')
        bridge.action('quit')
        bridge.sock.reset_mock()
        bridge._retry_usb()
        bridge.sock.sendall.assert_not_called()
        self.assertTrue(bridge.quit_requested)
        bridge.action('resume')
        self.assertEqual(fields(bridge.sock.sendall.call_args.args[0][12:]),{1:b'connect_android_auto_wifi'})
        bridge.usb.reset.assert_not_called()
        self.assertFalse(bridge.quit_requested)
        self.assertFalse(bridge.options['autostart'])

    def test_car_hotspot_resume_after_boot_and_usb_accessory_priority(self):
        bridge=Projection(True)
        bridge.available,bridge.sock=True,Mock()
        bridge.usb=Mock();bridge.usb.accessory.return_value=None;bridge.usb.last_reset=0
        bridge.set_wireless_default(True)
        bridge.action('resume')
        self.assertEqual(fields(bridge.sock.sendall.call_args.args[0][12:]),{1:b'connect_android_auto_wifi'})
        bridge.visible=True
        bridge.action('resume')
        self.assertEqual(fields(bridge.sock.sendall.call_args.args[0][12:]),{1:b'resume_android_auto_projection'})
        bridge.action('quit');bridge.visible=False
        bridge.usb.accessory.return_value='phone';bridge.usb.reset.return_value=True
        bridge.action('resume')
        bridge.usb.reset.assert_called_once()
        self.assertEqual(fields(bridge.sock.sendall.call_args.args[0][12:]),{1:b'connect_android_auto_usb'})
        self.assertEqual(bridge.last_transport,'usb')

    def test_native_obd_query_uses_read_only_command_and_correlated_response(self):
        bridge=Projection(True)
        bridge.available,bridge.obd_connected,bridge.sock=True,True,Mock()
        def reply(frame):
            self.assertEqual(struct.unpack('<III',frame[:12])[1],24)
            request=fields(frame[12:])
            self.assertEqual(request[1],b'010D')
            bridge._obd_response(fields(field(1,1)+field(2,'41 0D 64')+field(3,request[2])))
        bridge.sock.sendall.side_effect=reply
        self.assertEqual(bridge.query_obd('010D'),'41 0D 64')
        self.assertEqual(bridge.obd_pending,{})
        bridge.sock.reset_mock()
        for command in ('ATZ','ATD123','04','010C;shutdown'):
            with self.assertRaises(ValueError):bridge.query_obd(command)
        bridge.sock.sendall.assert_not_called()
        bridge.obd_connected=False
        with self.assertRaises(ConnectionError):bridge.query_obd('010D')

    def test_native_obd_timeout_clears_pending_query_and_ignores_unrelated_reply(self):
        bridge=Projection(True)
        bridge.available,bridge.obd_connected,bridge.sock=True,True,Mock()
        with patch.object(bridge.obd_condition,'wait_for',return_value=False) as wait:
            with self.assertRaises(TimeoutError):bridge.query_obd('010C')
            self.assertEqual(wait.call_args.kwargs['timeout'],3)
        self.assertEqual(bridge.obd_pending,{})
        bridge._obd_response({1:1,2:b'old response',3:999})
        self.assertEqual(bridge.obd_pending,{})

    def test_quit_ends_owning_host_and_service_without_a_second_runtime_start(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            runtime = home / '.hudiy/share/hudiy_run.sh'
            runtime.parent.mkdir(parents=True)
            runtime.write_text('# Test runtime; never executed\n')
            app = Mock()
            app.primaryScreen.return_value.size.return_value = SimpleNamespace(width=lambda:1280, height=lambda:720)
            qt = SimpleNamespace(QApplication=lambda _:app)
            service = Mock()
            service.poll.return_value = None
            ready = {'projection': {'available':True, 'visible':False}}
            waiting = {'projection': {'available':True, 'exitRequested':True}}
            closed = {'projection': {'available':False, 'exitRequested':True}}
            response = Mock()
            response.__enter__ = Mock(return_value=io.BytesIO(b'{}'))
            response.__exit__ = Mock(return_value=False)
            with patch.dict(sys.modules, {'PyQt6.QtWidgets':qt}), \
                 patch('hudiy_host.sys.platform','linux'), \
                 patch('hudiy_host.sys.argv',['hudiy_host.py','--apply']), \
                 patch('hudiy_host.Path.home',return_value=home), \
                 patch('hudiy_host.status',side_effect=[None,ready,ready,ready,waiting,closed]), \
                 patch('hudiy_host.configure',return_value={}), \
                 patch('hudiy_host.read_options',return_value={'taskbarVisible':True,'restartGeneration':0}), \
                 patch('hudiy_host.save_json'), \
                 patch('hudiy_host.signal.signal'), \
                 patch('hudiy_host.time.sleep'), \
                 patch('hudiy_host.urllib.request.urlopen',return_value=response), \
                 patch('hudiy_host.subprocess.Popen',return_value=service), \
                 patch('hudiy_host.subprocess.run') as start:
                hudiy_host.main()
                start.assert_called_once()
                service.terminate.assert_called_once_with()
                service.wait.assert_called_once_with(timeout=5)

    def test_application_quit_exits_host_after_fixed_runtime_quit_without_restarting(self):
        bridge = Projection(True)
        bridge.available, bridge.sock = True, Mock()
        bridge.manual_projection, bridge.usb_retry_at = True, 20
        options = dict(bridge.options)
        bridge.request_exit()
        bridge.request_exit()
        bridge.sock.sendall.assert_called_once()
        self.assertEqual(fields(bridge.sock.sendall.call_args.args[0][12:]), {1: b'quit_hudiy'})
        self.assertFalse(bridge.manual_projection)
        self.assertEqual(bridge.usb_retry_at, 0)
        self.assertEqual(exit_state({'projection': bridge.snapshot()}), 'waiting')
        bridge.sock.reset_mock()
        with self.assertRaises(ConnectionError): bridge.action('dashboard')
        bridge._media_status(fields(field(1,'00:01')+field(2,1)+field(3,3)))
        bridge.sock.sendall.assert_not_called()
        bridge.available = False
        self.assertEqual(exit_state({'projection': bridge.snapshot()}), 'stopped')
        self.assertEqual(bridge.options, options)

    def test_failed_or_ignored_application_quit_preserves_working_service_and_allows_retry(self):
        bridge = Projection(True)
        bridge.available, bridge.sock = True, Mock()
        bridge.sock.sendall.side_effect = OSError('Connection lost')
        with self.assertRaises(OSError): bridge.request_exit()
        self.assertFalse(bridge.snapshot()['exitRequested'])
        bridge.sock.sendall.side_effect = None
        with patch('projection.time.monotonic', return_value=10): bridge.request_exit()
        with patch('projection.time.monotonic', return_value=26):
            data = bridge.snapshot()
            self.assertFalse(data['exitRequested'])
            self.assertIn('try Quit again', data['exitError'])
            self.assertEqual(exit_state({'projection': data}), 'running')
            bridge.request_exit()
            self.assertTrue(bridge.snapshot()['exitRequested'])
            self.assertEqual(bridge.snapshot()['exitError'], '')

    def test_bluetooth_playback_retains_recreation_route_without_stealing_explicit_native_or_projection_views(self):
        bridge=Projection(True)
        bridge.available,bridge.sock=True,Mock()
        bridge.route='contacts'
        playing=fields(field(1,'00:01')+field(2,1)+field(3,3))
        bridge._media_status(playing)
        frame=bridge.sock.sendall.call_args.args[0]
        self.assertEqual(fields(frame[12:]),{1:b'hudiy_recreation'})
        self.assertEqual(bridge.route,'contacts')
        bridge.sock.reset_mock()
        bridge._media_status(playing)
        bridge.sock.sendall.assert_not_called()
        for attribute in ('native_menu_requested','visible'):
            bridge._media_status(fields(field(1,'')+field(2,0)+field(3,0)))
            setattr(bridge,attribute,True)
            bridge._media_status(playing)
            bridge.sock.sendall.assert_not_called()
            setattr(bridge,attribute,False)

    def test_bluetooth_source_switch_never_retains_android_metadata_or_artwork(self):
        bridge = Projection()
        bridge._media_status(fields(field(1,'00:10') + field(2,1) + field(3,1)))
        bridge._media_metadata(fields(field(1,'Android album') + field(3,'Android song') + field(5,b'\xff\xd8\xffart')))
        old_version = bridge.data_snapshot()['media']['coverartVersion']
        bridge._media_status(fields(field(1,'01:23') + field(2,1) + field(3,3)))
        self.assertEqual(bridge.data_snapshot()['media'],{'source':'bluetooth','playing':True,'position':'01:23'})
        self.assertEqual(bridge.image_snapshot(),(b'',''))
        bridge._media_metadata(fields(field(1,'Bluetooth album') + field(2,'Artist') + field(3,'Phone song') + field(4,'04:56') + field(5,b'\x89PNG\r\n\x1a\nart')))
        self.assertEqual(bridge.data_snapshot()['media']['title'],'Phone song')
        self.assertGreater(bridge.data_snapshot()['media']['coverartVersion'],old_version)
        bridge._media_status(fields(field(1,'01:24') + field(2,0) + field(3,3)))
        self.assertEqual(bridge.data_snapshot()['media']['title'],'Phone song')
        self.assertFalse(bridge.data_snapshot()['media']['playing'])
        bridge._media_status(fields(field(1,'') + field(2,0) + field(3,0)))
        self.assertEqual(bridge.data_snapshot()['media'],{})
        self.assertEqual(bridge.image_snapshot(),(b'',''))

    def test_android_quit_preserves_independent_bluetooth_and_fixed_playback_commands(self):
        bridge = Projection(True)
        bridge.available, bridge.sock = True, Mock()
        bridge._media_status(fields(field(1,'00:42') + field(2,0) + field(3,3)))
        bridge._media_metadata(fields(field(3,'Phone song') + field(5,b'\xff\xd8\xffart')))
        bridge.action('quit')
        self.assertTrue(bridge.quit_requested)
        self.assertEqual(bridge.data_snapshot()['media']['title'],'Phone song')
        self.assertEqual(bridge.image_snapshot()[1],'image/jpeg')
        for operation, native in [('media-toggle','now_playing_toggle_play'),('media-next','now_playing_next_track'),('media-previous','now_playing_previous_track')]:
            bridge.action(operation)
            frame = bridge.sock.sendall.call_args.args[0]
            self.assertEqual(struct.unpack('<III',frame[:12])[1],43)
            self.assertEqual(fields(frame[12:]),{1:native.encode()})
        bridge._media_status(fields(field(1,'00:43') + field(2,1) + field(3,3)))
        bridge._media_metadata(fields(field(3,'Next phone song') + field(5,b'<svg/>')))
        self.assertEqual(bridge.data_snapshot()['media']['title'],'Next phone song')
        self.assertEqual(bridge.image_snapshot(),(b'',''))
        bridge._media_status(fields(field(1,'00:44') + field(2,1) + field(3,1)))
        self.assertEqual(bridge.data_snapshot()['media'],{})
        bridge.sock.reset_mock()
        with self.assertRaises(ConnectionError): bridge.action('media-toggle')
        bridge.sock.sendall.assert_not_called()

    def test_native_pairing_opens_fixed_agent_and_cancels_pending_projection(self):
        bridge = Projection(True)
        bridge.available, bridge.sock = True, Mock()
        bridge.manual_projection, bridge.usb_retry_at = True, 20
        bridge.action('pair-native')
        frame = bridge.sock.sendall.call_args.args[0]
        self.assertEqual(struct.unpack('<III', frame[:12])[1], 43)
        self.assertEqual(fields(frame[12:]), {1: b'pairing_menu'})
        self.assertFalse(bridge.manual_projection)
        self.assertEqual(bridge.usb_retry_at, 0)
        self.assertEqual(bridge.route, 'dashboard')

    def test_music_refresh_uses_changed_interval(self):
        client, receiver = socket.socketpair()
        receiver.settimeout(3)
        bridge = Projection(True)
        bridge.sock, bridge.available, bridge.refresh_interval = client, True, 1
        checker = threading.Thread(target=bridge._check, daemon=True)
        started = time.monotonic()
        checker.start()
        try:
            size, mid, _ = struct.unpack('<III', receive_exact(receiver, 12))
            receive_exact(receiver, size)
            self.assertEqual(mid, 3)
            self.assertLess(time.monotonic() - started, 3)
        finally:
            bridge.stop.set(); checker.join(1); client.close(); receiver.close()

    def test_pinned_route_opens_only_recreation_and_cancels_pending_projection(self):
        bridge = Projection(True)
        bridge.available = True
        bridge.sock = Mock()
        bridge.manual_projection = True
        bridge.usb_retry_at = time.monotonic() + 5
        bridge.media = {'source': 'android', 'title': 'Live song'}
        bridge.action('contacts')
        frame = bridge.sock.sendall.call_args.args[0]
        self.assertEqual(struct.unpack('<III', frame[:12])[1], 43)
        self.assertEqual(fields(frame[12:]), {1: b'hudiy_recreation'})
        self.assertEqual(bridge.snapshot()['route'], 'contacts')
        self.assertFalse(bridge.manual_projection)
        self.assertEqual(bridge.usb_retry_at, 0)
        self.assertEqual(bridge.data_snapshot()['media']['title'], 'Live song')
        for invalid in ('https://example.com', '../contacts', 'contacts;shutdown', [], {}):
            with self.assertRaises(ValueError): bridge.action(invalid)

    def test_status_refresh_is_sent_after_five_seconds(self):
        client, receiver = socket.socketpair()
        receiver.settimeout(6)
        bridge = Projection(True)
        bridge.sock = client
        bridge.available = True
        checker = threading.Thread(target=bridge._check, daemon=True)
        started = time.monotonic()
        checker.start()
        try:
            size, message_id, flags = struct.unpack('<III', receive_exact(receiver, 12))
            payload = receive_exact(receiver, size)
            self.assertGreaterEqual(time.monotonic() - started, 4.8)
            self.assertEqual((message_id, flags, payload), (3, 0, b'\x08\x01\x08\x02\x08\x03\x08\x04\x08\x05'))
        finally:
            bridge.stop.set(); checker.join(1); client.close(); receiver.close()

    def test_malformed_wire_data_is_bounded(self):
        for data in (b'\x80' * 11, b'\x0a\xff\x01a', b'\x00', b'\x0e'):
            with self.assertRaises(ValueError):
                fields(data)
        self.assertEqual(fields(field(1, 300) + field(2, 'Android Auto')), {1: 300, 2: b'Android Auto'})

    def test_real_framing_visibility_navigation_and_disconnect(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        endpoint = listener.getsockname()
        received = []
        finished = threading.Event()
        drop = threading.Event()

        def runtime():
            with listener.accept()[0] as sock:
                def read():
                    n, mid, _ = struct.unpack('<III', receive_exact(sock, 12))
                    return mid, fields(receive_exact(sock, n))

                received.append(read())
                hello = field(1, field(1, 1) + field(2, 24)) + field(2, field(1, 1) + field(2, 3)) + field(3, 1)
                frame = struct.pack('<III', len(hello), 2, 0) + hello
                # Exercise split TCP headers and bodies.
                for b in frame:
                    sock.sendall(bytes([b]))
                received.append(read())
                received.append(read())  # Saved native dark mode on reconnect.
                received.append(read())  # Saved Android Auto day/night mode.
                for mid, payload in [(5, field(1, 1)), (33, field(1, 1) + field(2, 'Test phone')),
                                     (34, field(1, 1) + field(2, '123') + field(3, 'Test caller')),
                                     (35, field(1, 4) + field(2, 75)),
                                     (6, field(1, '01:23') + field(2, 0) + field(3, 1)),
                                     (7, field(1, 'Album') + field(2, 'Artist') + field(3, 'Track') + field(4, '04:56') + field(5, '<svg/>')),
                                     (8, field(1, 1) + field(2, 1)),
                                     (9, field(1, 'Turn left') + field(2, b'') + field(3, 1)),
                                     (10, field(1, '200 m'))]:
                    sock.sendall(struct.pack('<III', len(payload), mid, 0) + payload)
                received.append(read())
                drop.wait(3)
            finished.set()

        threading.Thread(target=runtime, daemon=True).start()
        connect = socket.create_connection
        bridge = Projection(True)
        bridge.options['autostart'] = True
        bridge.options.update(dayNight='Night',darkMode=False)
        try:
            with patch('projection.socket.create_connection', side_effect=lambda addr, timeout: connect(endpoint, timeout)):
                bridge.start()
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and not bridge.data_snapshot()['navigation'].get('distance'):
                    time.sleep(.02)
                self.assertTrue(bridge.snapshot()['available'])
                self.assertTrue(bridge.snapshot()['visible'])
                self.assertEqual(bridge.phone_snapshot()['name'], 'Test phone')
                self.assertEqual(bridge.phone_snapshot()['levels'], {'battery': 4, 'signal': 75})
                self.assertEqual(bridge.phone_snapshot()['call']['name'], 'Test caller')
                self.assertEqual(bridge.data_snapshot()['media']['title'], 'Track')
                self.assertEqual(bridge.data_snapshot()['media']['position'], '01:23')
                self.assertEqual(bridge.data_snapshot()['navigation']['distance'], '200 m')
                self.assertEqual(bridge.image_snapshot(), (b'', ''))
                for op in ['shell', 'resume;shutdown', None]:
                    with self.assertRaises(ValueError):
                        bridge.action(op)
                result = bridge.action('dashboard')
                self.assertTrue(result['accepted'])
                self.assertEqual(bridge.snapshot()['revision'], 1)
                drop.set()
                self.assertTrue(finished.wait(2))
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and bridge.snapshot()['available']:
                    time.sleep(.02)
                self.assertFalse(bridge.snapshot()['available'])
                self.assertFalse(bridge.phone_snapshot()['connected'])
                with self.assertRaises(ConnectionError):
                    bridge.action('resume')
                self.assertEqual(received[0][0], 1)
                self.assertEqual(received[1][0], 3)
                self.assertEqual(received[2], (37, {1: 0}))
                self.assertEqual(received[3], (50, {1: 3}))
                self.assertEqual(received[4], (43, {1: b'hudiy_recreation'}))
        finally:
            bridge.close()
            listener.close()

    def test_automatic_opening_off_hides_projection_and_preserves_route(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0)); listener.listen()
        endpoint = listener.getsockname()
        hidden = threading.Event()
        drop = threading.Event()
        received = []
        def runtime():
            with listener.accept()[0] as sock:
                def read():
                    n, mid, _ = struct.unpack('<III', receive_exact(sock, 12))
                    return mid, fields(receive_exact(sock, n))
                read()
                hello = field(1, field(1, 1) + field(2, 24)) + field(2, field(1, 1) + field(2, 3)) + field(3, 1)
                sock.sendall(struct.pack('<III', len(hello), 2, 0) + hello)
                read()
                sock.sendall(struct.pack('<III', 2, 5, 0) + b'\x08\x01')
                received.append(read())
                sock.sendall(struct.pack('<III', 2, 5, 0) + b'\x08\x00')
                hidden.set()
                drop.wait(2)
        threading.Thread(target=runtime, daemon=True).start()
        connect = socket.create_connection
        bridge = Projection(True)
        bridge.options['autostart'] = False
        bridge.route = 'obd-settings'
        try:
            with patch('projection.socket.create_connection', side_effect=lambda addr, timeout: connect(endpoint, timeout)):
                bridge.start()
                self.assertTrue(hidden.wait(2))
                self.assertEqual(received, [(43, {1: b'hudiy_recreation'})])
                self.assertEqual(bridge.snapshot()['revision'], 0)
                self.assertEqual(bridge.snapshot()['route'], 'obd-settings')
        finally:
            drop.set(); bridge.close(); listener.close()

    def test_configuration_preserves_originals_and_reserves_bar(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            original = {'application': {'touchscreen': True}, 'androidAuto': {'resolution': '720p'}, 'unrelated': 42}
            (config / 'main_configuration.json').write_text(json.dumps(original))
            (config / 'applications.json').write_text('{"applications":[{"action":"existing"}]}')
            (config / 'overlays.json').write_text('{"overlays":[{"identifier":"existing"}]}')
            preview = configure(config, 1280, 720)
            self.assertEqual(preview['taskbar'], 81)
            self.assertEqual(json.loads((config / 'main_configuration.json').read_text()), original)
            configure(config, 1280, 720, True)
            configure(config, 1920, 1080, True)
            main = json.loads((config / 'main_configuration.json').read_text())
            self.assertEqual(main['unrelated'], 42)
            self.assertTrue(main['application']['touchscreen'])
            self.assertEqual(main['androidAuto']['height'], 958)
            self.assertEqual(json.loads((config / 'main_configuration.json.recreation-original').read_text()), original)
            apps = json.loads((config / 'applications.json').read_text())['applications']
            overlays = json.loads((config / 'overlays.json').read_text())['overlays']
            self.assertEqual(len(apps), 2)
            self.assertEqual(len(overlays), 2)
            self.assertEqual(overlays[-1]['y'] + overlays[-1]['height'], 1080)
            self.assertEqual(overlays[-1]['visibility'], 'ALWAYS')
            configure(config, 1280, 720, True, False)
            main = json.loads((config / 'main_configuration.json').read_text())
            overlays = json.loads((config / 'overlays.json').read_text())['overlays']
            self.assertEqual(main['androidAuto']['height'], 720)
            self.assertEqual(main['androidAuto']['heightMargin'], 0)
            self.assertEqual(overlays[-1]['visibility'], 'NATIVE_UI_ONLY')

    def test_settings_are_persistent_boolean_and_allowlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'projection.json'
            bridge = Projection(True)
            bridge.available = True
            for data in ({'taskbarVisible': 'false'}, {'autostart': 1}, {'host': 'attacker'}, {}):
                with self.assertRaises(ValueError):
                    bridge.settings(data, path)
            bridge.settings({'autostart': True, 'taskbarVisible': False}, path)
            bridge.request_layout(path)
            result = json.loads(path.read_text())
            self.assertTrue(result['autostart'])
            self.assertFalse(result['taskbarVisible'])
            self.assertEqual(result['restartGeneration'], 1)


if __name__ == '__main__':
    unittest.main()
