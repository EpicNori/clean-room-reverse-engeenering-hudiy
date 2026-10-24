"""Private IPC client for our own Android Auto process; no Hudiy API calls."""
import copy
import json
import re
from pathlib import Path
import socket
import sys
import threading
import time
from runtime_support import DEFAULT_OPTIONS, DAY_NIGHT_MODES, PREFERENCES, ROUTES, read_options, save_json

STATE_DIR = Path.home() / '.local/share/hudiy-recreation'
MAX_MESSAGE = 65536


class StandaloneProjection:
    def __init__(self, enabled=False, socket_path=None, preferences=None):
        self.enabled = enabled and sys.platform == 'linux'
        self.preferences = preferences or PREFERENCES
        self.socket_path = socket_path or STATE_DIR / 'native.sock'
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.worker = None
        self.sock = None
        self.options = read_options(self.preferences) if self.enabled else dict(DEFAULT_OPTIONS)
        self.state = {}
        self.available = False
        self.exit_requested = False
        self.updated = None
        self.refresh_interval = 5
        self.wireless_default = False
        self.audio_options = None
        self.input_options = None

    def start(self):
        if self.enabled and not self.worker:
            self.worker = threading.Thread(target=self._run, daemon=True)
            self.worker.start()

    def _run(self):
        while not self.stop.is_set():
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                connection.settimeout(12)
                connection.connect(str(self.socket_path))
                with self.lock:
                    self.sock = connection
                    self.available = True
                    self._send({'operation': 'options', 'options': self.options})
                    if self.audio_options is not None:
                        self._send({'operation': 'audio-dsp', 'settings': self.audio_options})
                    if self.input_options is not None:
                        self._send({'operation': 'audio-input', 'settings': self.input_options})
                pending = bytearray()
                while not self.stop.is_set():
                    part = connection.recv(8192)
                    if not part: raise ConnectionError('Independent runtime closed')
                    pending.extend(part)
                    while b'\n' in pending:
                        line, _, remainder = pending.partition(b'\n')
                        if len(line) > MAX_MESSAGE: raise ValueError('Native event exceeds size limit')
                        pending = bytearray(remainder)
                        self._event(json.loads(line))
                    if len(pending) > MAX_MESSAGE: raise ValueError('Native event exceeds size limit')
            except (OSError, ValueError, TypeError):
                pass
            finally:
                with self.lock:
                    if self.sock is connection:
                        self.sock = None
                        self.available = False
                        self.state = {}
                        self.updated = None
                connection.close()
            self.stop.wait(1)

    def _event(self, value):
        if not isinstance(value, dict) or value.get('event') != 'state':
            raise ValueError('Invalid native event')
        if type(value.get('connected')) is not bool or type(value.get('visible')) is not bool:
            raise ValueError('Invalid native connection state')
        for field in ('media', 'navigation'):
            if not isinstance(value.get(field, {}), dict): raise ValueError('Invalid native data')
        with self.lock:
            self.state = copy.deepcopy(value)
            self.updated = time.time()

    def _send(self, command):
        if not self.available or not self.sock or self.exit_requested:
            raise ConnectionError('Independent car runtime is unavailable or closing')
        payload = json.dumps(command, allow_nan=False, separators=(',', ':')).encode() + b'\n'
        if len(payload) > MAX_MESSAGE: raise ValueError('Native command exceeds size limit')
        self.sock.sendall(payload)

    def snapshot(self):
        with self.lock:
            return {'enabled': self.enabled, 'available': self.available,
                    'renderer': 'standalone' if self.enabled else None,
                    'connected': self.state.get('connected', False),
                    'visible': self.state.get('visible', False),
                    'route': self.state.get('route', 'dashboard'),
                    'revision': self.state.get('revision', 0),
                    'error': self.state.get('error', ''), 'options': dict(self.options),
                    'layoutPending': False, 'checkIntervalSeconds': 5,
                    'exitRequested': self.exit_requested, 'exitError': '', 'nativeOBDConnected': False,
                    'transport': self.state.get('transport'), 'decodedFrames': self.state.get('frames', 0),
                    'audioBytes': self.state.get('audioBytes', 0),
                    'audioDSP': copy.deepcopy(self.state.get('audioDSP', {})),
                    'audioInput': copy.deepcopy(self.state.get('audioInput', {})),
                    'audioQueuedBytes': self.state.get('audioQueuedBytes',0),
                    'audioDroppedBytes': self.state.get('audioDroppedBytes',0),
                    'maximumAudioPacket': self.state.get('maximumAudioPacket',0),
                    'audioChannels': copy.deepcopy(self.state.get('audioChannels',[])),
                    'maximumAudioFeedGapMs': self.state.get('maximumAudioFeedGapMs',0),
                    'runtimePid': self.state.get('runtimePid'),
                    'microphoneAvailable': self.state.get('microphoneAvailable') is True,
                    'videoReady': self.state.get('connected') is True and self.state.get('frames', 0) > 0,
                    'wirelessListening': self.state.get('wirelessListening', False),
                    'usbRecoveryRunning': self.state.get('usbRecoveryRunning') is True,
                    'uiReady': self.state.get('uiReady') is True,
                    'connectionAllowed': self.state.get('connectionAllowed') is True,
                    'automaticConnectionAllowed': self.state.get('automaticConnectionAllowed') is True,
                    'sessionStarting': self.state.get('sessionStarting') is True}

    def data_snapshot(self):
        with self.lock:
            return {**self.snapshot(), 'media': copy.deepcopy(self.state.get('media', {})),
                    'navigation': copy.deepcopy(self.state.get('navigation', {})), 'updatedAt': self.updated}

    def phone_snapshot(self):
        with self.lock:
            signal = self.state.get('signal', -1)
            return {'connected': self.state.get('connected', False), 'name': '',
                    'levels': {'signal': signal} if isinstance(signal, int) and signal >= 0 else {}, 'call': {}}

    def image_snapshot(self):
        if not self.state.get('connected') or not self.state.get('media', {}).get('coverartVersion'):
            return b'', ''
        try:
            path = self.socket_path.parent / 'native-cover.png'
            if path.is_symlink() or path.stat().st_size > 2*1024*1024: return b'', ''
            image = path.read_bytes()
            if image.startswith(b'\x89PNG\r\n\x1a\n'): return image, 'image/png'
            if image.startswith(b'\xff\xd8\xff'): return image, 'image/jpeg'
        except OSError: pass
        return b'', ''

    def settings(self, data, path=None):
        if not self.enabled: raise ConnectionError('Settings require the independent Pi application')
        if not isinstance(data, dict) or not data or set(data) - {'blackStartup', 'autoConnect', 'autostart', 'taskbarVisible', 'dayNight', 'darkMode'}:
            raise ValueError('Unexpected projection settings')
        for key, value in data.items():
            if key == 'dayNight':
                if not isinstance(value, str) or value not in DAY_NIGHT_MODES: raise ValueError('Choose Common, Day or Night')
            elif type(value) is not bool: raise ValueError('Projection switches must be boolean')
        with self.lock:
            updated = {**self.options, **data}
            self._send({'operation': 'options', 'options': updated})
            try: save_json(path or self.preferences, updated)
            except OSError:
                self._send({'operation': 'options', 'options': self.options})
                raise
            self.options = updated
            return self.snapshot()

    def action(self, operation):
        allowed = {'usb', 'wifi', 'resume', 'quit', 'media-toggle', 'media-next', 'media-previous'}
        with self.lock:
            if operation in ROUTES: command = {'operation': 'route', 'route': operation}
            elif isinstance(operation, str) and operation in allowed: command = {'operation': operation}
            else: raise ValueError('Unsupported independent runtime action')
            if operation.startswith('media-') and not self.state.get('connected'):
                raise ConnectionError('Android Auto is not connected')
            self._send(command)
            return {'accepted': True, 'message': 'Android Auto connection requested' if operation in {'usb', 'wifi', 'resume'} else ''}

    def startup_ready(self, surface, token):
        if surface not in ('content', 'taskbar') or not isinstance(token, str) or not re.fullmatch(r'[a-f0-9]{32}', token):
            raise ValueError('Invalid native startup acknowledgement')
        with self.lock:self._send({'operation': 'startup-ready', 'surface': surface, 'token': token})
        return {'accepted': True}

    def notification(self, data):
        if not isinstance(data, dict): raise ValueError('Notification must be an object')
        kind = data.get('kind')
        expected = {'kind', 'background', 'foreground'} if kind == 'theme' else {'kind', 'message', 'duration', 'background', 'foreground'}
        if set(data) != expected or kind not in {'theme', 'toast', 'output', 'input', 'track'}:
            raise ValueError('Unexpected notification arguments')
        for key in ('background', 'foreground'):
            if not isinstance(data[key], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', data[key]):
                raise ValueError('Notification colors must be hex RGB')
        if kind != 'theme':
            if not isinstance(data['message'], str) or len(data['message']) > 256:
                raise ValueError('Notification text exceeds limit')
            if type(data['duration']) is not int or not 1 <= data['duration'] <= 15:
                raise ValueError('Notification duration must be 1–15 seconds')
        with self.lock: self._send({'operation': 'notification', **data})
        return {'accepted': True}

    def set_wireless_default(self, enabled): self.wireless_default = enabled is True

    def apply_input(self, settings):
        with self.lock: self._send({'operation': 'audio-input', 'settings': settings})

    def apply_audio(self, settings):
        with self.lock: self._send({'operation': 'audio-dsp', 'settings': settings})

    def request_layout(self, path=None):
        with self.lock:
            self._send({'operation': 'options', 'options': self.options})
        return {'accepted': True, 'message': 'Projection layout applied'}

    def reload_wireless(self):
        with self.lock: self._send({'operation': 'wireless-reload'})

    def request_exit(self):
        with self.lock:
            if not self.exit_requested:
                self._send({'operation': 'exit'})
                self.exit_requested = True
        return {'accepted': True, 'message': 'Returning to the desktop'}

    def stop_runtime(self): return self.request_exit()

    def close(self):
        self.stop.set()
        with self.lock:
            if self.sock:
                try: self.sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass
        if self.worker: self.worker.join(timeout=3)
