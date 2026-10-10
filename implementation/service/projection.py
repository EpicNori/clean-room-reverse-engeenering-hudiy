"""Small independent client for Hudiy's documented TCP/Protobuf API.

Only projection visibility, phone connection and an action allowlist are exposed.
No video capture: the installed, licensed Hudiy runtime renders Android Auto.
Protocol reference: https://github.com/wiboma/hudiy/blob/main/api/Api.proto
"""
import socket
import struct
import threading
import time
import json
import os
from pathlib import Path
from usb_recovery import USBRecovery

MAX_FRAME = 1024 * 1024
MEDIA_SOURCES = {1: 'android', 3: 'bluetooth'}
ACTIONS = {
    'usb': 'connect_android_auto_usb',
    'wifi': 'connect_android_auto_wifi',
    'resume': 'resume_android_auto_projection',
    'quit': 'quit_android_auto',
    'dashboard': 'hudiy_recreation',
    'apps': 'hudiy_recreation',
    'obd-settings': 'hudiy_recreation',
    'media-toggle': 'now_playing_toggle_play',
    'media-next': 'now_playing_next_track',
    'media-previous': 'now_playing_previous_track',
    'pair-native': 'pairing_menu',
}
ROUTES = frozenset('''dashboard apps settings obd-settings playlist stations
    contacts favorites dialpad call-log active-call notifications
    storage radio a2dp autobox-music android-music active-apps
    obd-charts obd-blocks combined gauges gauges-2 marketplace
    theme appearance application notification-settings overlays about music-settings contacts-settings
    android-settings autobox-settings sound equalizer presets pair remove bluetooth-connections'''.split())
ACTIONS.update({route: 'hudiy_recreation' for route in ROUTES})

PREFERENCES = Path.home() / '.local/share/hudiy-recreation/projection.json'
HOST_STATE = Path.home() / '.local/share/hudiy-recreation/projection-host.json'
DAY_NIGHT_MODES = {'Common': 1, 'Day': 2, 'Night': 3}
DEFAULT_OPTIONS = {'autostart': False, 'taskbarVisible': True, 'restartGeneration': 0,
                   'dayNight': None, 'darkMode': None}


def read_options(path=PREFERENCES):
    result = dict(DEFAULT_OPTIONS)
    try:
        data = json.loads(path.read_text())
        for key in ('autostart', 'taskbarVisible'):
            if isinstance(data.get(key), bool):
                result[key] = data[key]
        if isinstance(data.get('dayNight'), str) and data['dayNight'] in DAY_NIGHT_MODES:
            result['dayNight'] = data['dayNight']
        if type(data.get('darkMode')) is bool:
            result['darkMode'] = data['darkMode']
        value = data.get('restartGeneration')
        if type(value) is int and 0 <= value < 2 ** 31:
            result['restartGeneration'] = value
    except (OSError, ValueError, AttributeError):
        pass
    return result


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as stream:
        os.chmod(tmp, 0o600)
        stream.write(json.dumps(data) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)
    if os.name == 'posix':
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)


def varint(value):
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def field(number, value):
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    if isinstance(value, str):
        value = value.encode('utf-8')
    return varint((number << 3) | 2) + varint(len(value)) + value


def fields(payload):
    """Parse bounded wire fields, including unknown fields for compatibility."""
    result, offset = {}, 0

    def read_varint():
        nonlocal offset
        value = 0
        for shift in range(0, 70, 7):
            if offset >= len(payload):
                raise ValueError('Truncated protobuf')
            b = payload[offset]
            offset += 1
            value |= (b & 127) << shift
            if not b & 128:
                return value
        raise ValueError('Oversized protobuf integer')

    while offset < len(payload):
        tag = read_varint()
        number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError('Invalid protobuf field')
        if wire == 0:
            value = read_varint()
        elif wire in (1, 2, 5):
            size = read_varint() if wire == 2 else (8 if wire == 1 else 4)
            if size > len(payload) - offset:
                raise ValueError('Truncated protobuf field')
            value = payload[offset:offset + size]
            offset += size
        else:
            raise ValueError('Unsupported protobuf wire type')
        result[number] = value
    return result


def receive_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise ConnectionError('Hudiy API disconnected')
        data.extend(part)
    return bytes(data)


class Projection:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.lock = threading.RLock()
        self.sock = None
        self.stop = threading.Event()
        self.available = False
        self.api_minor = None
        self.visible = False
        self.phone = {'connected': False, 'name': '', 'levels': {}, 'call': {}}
        self.route = 'dashboard'
        self.revision = 0
        self.error = ''
        self.worker = None
        self.checker = None
        self.options = read_options() if enabled else dict(DEFAULT_OPTIONS)
        self.manual_projection = False
        self.manual_deadline = 0
        self.media = {}
        self.coverart = b''
        self.coverart_type = ''
        self.coverart_version = 0
        self.navigation = {}
        self.updated = None
        self.usb = USBRecovery()
        self.connect_lock = threading.Lock()
        self.quit_requested = False
        self.usb_retry_at = 0
        self.connection_intent = 0
        self.last_transport = None
        self.wireless_default = False
        self.refresh_interval = 5
        self.native_menu_requested = False
        self.exit_requested = False
        self.exit_deadline = 0
        self.exit_error = ''
        self.obd_connected = False
        self.obd_pending = {}
        self.obd_code = 0
        self.obd_condition = threading.Condition(self.lock)

    def start(self):
        if self.enabled and not self.worker:
            self.worker = threading.Thread(target=self._run, daemon=True)
            self.worker.start()
            self.checker = threading.Thread(target=self._check, daemon=True)
            self.checker.start()

    def snapshot(self):
        with self.lock:
            if self.exit_requested and self.available and time.monotonic() >= self.exit_deadline:
                self.exit_requested = False
                self.exit_error = 'Hudiy did not exit; try Quit again'
            applied = True
            if self.enabled:
                try:
                    applied = json.loads(HOST_STATE.read_text()).get('taskbarVisible', True)
                except (OSError, ValueError, AttributeError):
                    pass
            return {'enabled': self.enabled, 'available': self.available,
                    'visible': self.visible, 'renderer': 'hudiy' if self.enabled else None,
                    'route': self.route, 'revision': self.revision, 'error': self.error,
                    'options': dict(self.options), 'layoutPending': applied != self.options['taskbarVisible'],
                    'checkIntervalSeconds': 5, 'exitRequested': self.exit_requested,
                    'exitError': self.exit_error, 'nativeOBDConnected': self.obd_connected}

    def data_snapshot(self):
        with self.lock:
            return {'media': dict(self.media), 'navigation': dict(self.navigation),
                    'updatedAt': self.updated, **self.snapshot()}

    def image_snapshot(self):
        with self.lock:
            return self.coverart, self.coverart_type

    def settings(self, data, path=PREFERENCES):
        if not self.enabled:
            raise ConnectionError('Android Auto settings require the Pi projection host')
        if not isinstance(data, dict) or not data or set(data) - {'autostart', 'taskbarVisible', 'dayNight', 'darkMode'}:
            raise ValueError('Unexpected projection settings')
        for key, value in data.items():
            if key == 'dayNight':
                if not isinstance(value, str) or value not in DAY_NIGHT_MODES:
                    raise ValueError('Day/Night must be Common, Day or Night')
            elif type(value) is not bool:
                raise ValueError('Projection switches must be boolean')
        with self.lock:
            visual = set(data) & {'dayNight', 'darkMode'}
            if visual and (not self.available or self.exit_requested):
                raise ConnectionError('Hudiy is unavailable or closing; appearance was not changed')
            if 'dayNight' in visual and (self.api_minor is None or self.api_minor < 3):
                raise ConnectionError('Day/Night control requires Hudiy API 1.3 or newer')
            options = {**self.options, **data}
            save_json(path, options)
            try:
                if visual:
                    self._apply_visual_options(options, visual)
            except OSError:
                save_json(path, self.options)
                if visual:
                    try: self._apply_visual_options(self.options, visual)
                    except OSError: pass
                raise
            self.options = options
        return self.snapshot()

    def _apply_visual_options(self, options, keys):
        if 'darkMode' in keys and type(options.get('darkMode')) is bool:
            self._send(37, field(1, int(options['darkMode'])))
        if ('dayNight' in keys and options.get('dayNight') in DAY_NIGHT_MODES and
                self.api_minor is not None and self.api_minor >= 3):
            self._send(50, field(1, DAY_NIGHT_MODES[options['dayNight']]))

    def request_layout(self, path=PREFERENCES):
        with self.lock:
            if not self.enabled or not self.available:
                raise ConnectionError('Hudiy projection host is unavailable')
            options = {**self.options, 'restartGeneration': self.options['restartGeneration'] + 1}
            save_json(path, options)
            self.options = options
        return {'message': 'Applying projection layout; Hudiy will restart', 'accepted': True}

    def stop_runtime(self):
        """Host-only lifecycle operation; never accepts a caller-supplied action."""
        self._send(43, field(1, 'quit_hudiy'))

    def request_exit(self):
        """Exit the current host session without changing the next boot's startup."""
        with self.lock:
            if not self.enabled or not self.available:
                raise ConnectionError('Hudiy runtime is unavailable; Quit was not performed')
            if not self.exit_requested:
                self.stop_runtime()
                self.exit_requested = True
                self.exit_deadline = time.monotonic() + 15
                self.exit_error = ''
                self.connection_intent += 1
                self.manual_projection = False
                self.manual_deadline = 0
                self.usb_retry_at = 0
            return {'accepted': True, 'message': 'Closing Hudiy and returning to the desktop'}

    def _subscriptions(self):
        return field(1, 1) + field(1, 2) + field(1, 3) + field(1, 4) + field(1, 5)

    def query_obd(self, command):
        from obd import PIDS
        if command not in {'01' + pid for pid in PIDS}:
            raise ValueError('Only supported read-only Mode 01 sensor queries are allowed')
        with self.obd_condition:
            if not self.enabled or not self.available or not self.obd_connected or self.exit_requested:
                raise ConnectionError('Turn on the paired ELM327 and connect it in Hudiy')
            if self.obd_pending: raise ConnectionError('An OBD query is already running')
            self.obd_code = self.obd_code % (2 ** 31 - 1) + 1
            code = self.obd_code
            self.obd_pending[code] = None
            try:
                self._send(24, field(1, command) + field(2, code))
                if not self.obd_condition.wait_for(lambda: self.obd_pending[code] is not None or not self.available, timeout=3):
                    raise TimeoutError('Hudiy OBD query timed out')
                result = self.obd_pending[code]
                if not result or not result.get(1): raise ConnectionError('Hudiy OBD query failed')
                return self._text(result.get(2))
            finally: self.obd_pending.pop(code, None)

    def _obd_response(self, data):
        with self.obd_condition:
            code = data.get(3)
            if code in self.obd_pending:
                self.obd_pending[code] = data
                self.obd_condition.notify_all()

    def _check(self):
        last_media = last_connection = time.monotonic()
        while not self.stop.wait(1):
            try:
                if self.snapshot()['available']:
                    now = time.monotonic()
                    if now - last_media >= self.refresh_interval:
                        self._send(3, self._subscriptions())
                        last_media = now
                    if now - last_connection >= 5:
                        self._retry_usb()
                        last_connection = now
            except OSError:
                pass

    def _retry_usb(self):
        with self.lock:
            due = self.usb_retry_at
            if (not due or time.monotonic() < due or not self.manual_projection or
                    self.quit_requested or self.visible or self.media.get('source') == 'android'):
                return
            self.usb_retry_at = 0
            intent = self.connection_intent
        if not self.connect_lock.acquire(blocking=False):
            with self.lock:
                self.usb_retry_at = due
            return
        try:
            if self.usb.reset():
                with self.lock:
                    if (intent == self.connection_intent and self.manual_projection and
                            not self.quit_requested and time.monotonic() < self.manual_deadline):
                        self._send(43, field(1, ACTIONS['usb']))
        finally:
            self.connect_lock.release()

    def phone_snapshot(self):
        with self.lock:
            return dict(self.phone)

    def set_wireless_default(self, enabled):
        """Use the configured car hotspot for a manual reconnect after boot."""
        with self.lock:
            self.wireless_default = enabled is True

    def _send(self, message_id, payload=b''):
        with self.lock:
            if not self.sock:
                raise ConnectionError('Hudiy projection runtime is unavailable')
            self.sock.sendall(struct.pack('<III', len(payload), message_id, 0) + payload)

    def action(self, operation):
        if not isinstance(operation, str) or operation not in ACTIONS:
            raise ValueError('Unsupported Android Auto operation')
        with self.lock:
            if self.exit_requested:
                raise ConnectionError('Hudiy is closing')
        if operation in ('usb', 'wifi', 'resume'):
            if not self.connect_lock.acquire(blocking=False):
                return {'accepted': True, 'operation': operation, 'message': 'Android Auto connection is already starting'}
            try:
                with self.lock:
                    if not self.available:
                        raise ConnectionError('Hudiy projection runtime is unavailable')
                    live = not self.quit_requested and (self.visible or self.media.get('source') == 'android')
                    wireless = self.last_transport == 'wifi' or (self.last_transport is None and self.wireless_default)
                    self.connection_intent += 1
                    intent = self.connection_intent
                # Quit leaves the phone in AOA mode. Hudiy's original USB discovery
                # cannot reopen that stale accessory; reset only this phone first.
                recovered = False
                if operation != 'wifi' and not live and self.usb.accessory() is not None:
                    recovered = self.usb.reset()
                    native = 'usb'
                else:
                    native = 'wifi' if operation == 'wifi' else 'resume' if live else 'wifi' if operation == 'resume' and wireless else operation
                with self.lock:
                    if intent != self.connection_intent:
                        return {'accepted': False, 'operation': operation, 'message': 'Android Auto connection canceled'}
                    self.manual_projection = True
                    self.manual_deadline = time.monotonic() + 30
                    self.quit_requested = False
                    self.usb_retry_at = self.usb.last_reset + 15 if native == 'usb' and not recovered and self.usb.last_reset > 0 else 0
                    try:
                        self._send(43, field(1, ACTIONS[native]))
                    except OSError:
                        self.manual_projection = False
                        raise
                    if native in ('usb', 'wifi'):
                        self.last_transport = native
                return {'accepted': True, 'operation': operation,
                        'message': 'Android USB connection recovered' if recovered else 'Android Auto connection requested'}
            finally:
                self.connect_lock.release()
        with self.lock:
            if self.exit_requested:
                raise ConnectionError('Hudiy is closing')
            if not self.available:
                raise ConnectionError('Hudiy projection runtime is unavailable')
            if operation.startswith('media-') and self.media.get('source') not in MEDIA_SOURCES.values():
                raise ConnectionError('Live media is unavailable')
            # Send before changing navigation: a failed write must not report success.
            self._send(43, field(1, ACTIONS[operation]))
            if operation in ('usb', 'wifi', 'resume'):
                self.connection_intent += 1
                self.manual_projection = True
                self.manual_deadline = time.monotonic() + 30
                self.quit_requested = False
            if operation == 'quit':
                self.connection_intent += 1
                self.quit_requested = True
                self.manual_projection = False
                self.manual_deadline = 0
                self.usb_retry_at = 0
                self.navigation = {}
                if self.media.get('source') != 'bluetooth':
                    self.media = {}
                    self.coverart, self.coverart_type = b'', ''
                    self.updated = None
            if operation in ROUTES or operation == 'pair-native':
                self.native_menu_requested = operation == 'pair-native'
                self.connection_intent += 1
                self.manual_projection = False
                self.manual_deadline = 0
                self.usb_retry_at = 0
                if operation in ROUTES:
                    self.route = operation
                    self.revision += 1
        return {'message': 'Android Auto request sent' if operation in ('usb', 'wifi', 'quit') else '',
                'operation': operation, 'accepted': True}

    def _run(self):
        while not self.stop.is_set():
            sock = None
            try:
                sock = socket.create_connection(('127.0.0.1', 44405), timeout=3)
                sock.settimeout(30)
                with self.lock:
                    self.sock = sock
                self._send(1, field(1, 'hudiy-recreation') + field(2, field(1, 1) + field(2, 0)))
                while not self.stop.is_set():
                    size, message_id, _ = struct.unpack('<III', receive_exact(sock, 12))
                    if size > MAX_FRAME:
                        raise ValueError('Hudiy API frame too large')
                    payload = receive_exact(sock, size)
                    if message_id == 47:
                        self._send(48)
                    elif message_id == 49:
                        raise ConnectionError('Hudiy runtime closed the connection')
                    elif message_id == 2:
                        data = fields(payload)
                        version = fields(data.get(2, b''))
                        if data.get(3) != 1 or version.get(1) != 1:
                            raise ConnectionError('Incompatible Hudiy API version')
                        self._send(3, self._subscriptions())
                        with self.lock:
                            self.api_minor = version.get(2, 0)
                            self._apply_visual_options(self.options, {'darkMode', 'dayNight'})
                            self.available, self.error = True, ''
                    elif message_id == 5:
                        data = fields(payload)
                        if data.get(1) not in (0, 1):
                            raise ValueError('Invalid projection visibility')
                        with self.lock:
                            previous = self.visible
                            self.visible = bool(data[1])
                            manual = self.manual_projection and (previous or time.monotonic() < self.manual_deadline)
                            if self.visible and not self.options['autostart'] and not manual and not self.exit_requested:
                                # Connect in the background; preserve the recreation's current route.
                                self._send(43, field(1, 'hudiy_recreation'))
                            elif not self.visible and previous:
                                self.manual_projection = False
                    elif message_id == 6:
                        self._media_status(fields(payload))
                    elif message_id == 7:
                        self._media_metadata(fields(payload))
                    elif message_id == 23:
                        with self.lock: self.obd_connected = fields(payload).get(1) == 1
                    elif message_id == 25:
                        self._obd_response(fields(payload))
                    elif message_id == 8:
                        data = fields(payload)
                        with self.lock:
                            if data.get(1) == 1 and data.get(2) == 1 and not self.quit_requested:
                                self.navigation['active'] = True
                                self.updated = time.time()
                            else:
                                self.navigation = {}
                    elif message_id in (9, 10):
                        data = fields(payload)
                        with self.lock:
                            if self.navigation.get('active'):
                                self.navigation['description' if message_id == 9 else 'distance'] = self._text(data.get(1))
                                if message_id == 9:
                                    self.navigation['side'] = data.get(3, 0)
                                self.updated = time.time()
                    elif message_id == 33:
                        data = fields(payload)
                        with self.lock:
                            self.phone.update(connected=data.get(1) == 1,
                                              name=self._text(data.get(2))[:128])
                            if not self.phone['connected']:
                                self.phone['levels'], self.phone['call'] = {}, {}
                    elif message_id == 34:
                        data = fields(payload)
                        with self.lock:
                            self.phone['call'] = {'state': data.get(1, 0),
                                'number': self._text(data.get(2))[:32],
                                'name': self._text(data.get(3))[:128]} if data.get(1) in (1, 2, 3) else {}
                    elif message_id == 35:
                        data = fields(payload)
                        with self.lock:
                            self.phone['levels'] = {'battery': max(0, min(5, data.get(1, 0))),
                                                   'signal': max(0, min(100, data.get(2, 0)))}
            except (OSError, ValueError, TypeError, struct.error) as exc:
                with self.lock:
                    self.available, self.visible = False, False
                    self.api_minor = None
                    self.phone = {'connected': False, 'name': '', 'levels': {}, 'call': {}}
                    self.media, self.navigation = {}, {}
                    self.coverart, self.coverart_type = b'', ''
                    self.updated = None
                    self.manual_projection = False
                    self.usb_retry_at = 0
                    self.error = str(exc)
            finally:
                with self.obd_condition:
                    self.sock = None
                    self.obd_connected = False
                    self.obd_condition.notify_all()
                if sock:
                    sock.close()
            self.stop.wait(2)

    @staticmethod
    def _text(value):
        return value.decode('utf-8', 'replace')[:512] if isinstance(value, bytes) else ''

    def _media_status(self, data):
        with self.lock:
            source = MEDIA_SOURCES.get(data.get(3))
            previous_source, previous_playing = self.media.get('source'), self.media.get('playing')
            if source == 'android' and self.quit_requested: source = None
            if self.media.get('source') != source or source is None:
                self.media = {}
                if self.coverart: self.coverart_version += 1
                self.coverart, self.coverart_type = b'', ''
            if source:
                self.media.update(source=source, playing=bool(data.get(2)), position=self._text(data.get(1)))
                if (source == 'bluetooth' and self.media['playing'] and
                        (previous_source != source or not previous_playing) and
                        self.available and not self.visible and not self.native_menu_requested and not self.exit_requested):
                    self._send(43, field(1, ACTIONS['dashboard']))
            self.updated = time.time()

    def _media_metadata(self, data):
        with self.lock:
            source = self.media.get('source')
            if source not in MEDIA_SOURCES.values() or (source == 'android' and self.quit_requested): return
            self.media.update(album=self._text(data.get(1)), artist=self._text(data.get(2)),
                              title=self._text(data.get(3)), duration=self._text(data.get(4)))
            image = data.get(5, b'')
            mime = ('image/png' if isinstance(image, bytes) and image.startswith(b'\x89PNG\r\n\x1a\n') else
                    'image/jpeg' if isinstance(image, bytes) and image.startswith(b'\xff\xd8\xff') else '')
            if not mime: image = b''
            if image != self.coverart: self.coverart_version += 1
            self.coverart, self.coverart_type = image, mime
            self.media.update(coverart=bool(image), coverartVersion=self.coverart_version)
            self.updated = time.time()

    def close(self):
        self.stop.set()
        with self.lock:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        if self.worker:
            self.worker.join(timeout=4)
        if self.checker:
            self.checker.join(timeout=1)
