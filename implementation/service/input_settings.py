"""Private microphone preferences; enumeration and capture belong to our native runtime."""
import copy
import json
from pathlib import Path
import re
import threading
from runtime_support import save_json

DEFAULTS = {'device': 'default', 'volume': 100, 'muted': False}

def validate_input(data):
    if not isinstance(data, dict) or not data or set(data) - set(DEFAULTS):
        raise ValueError('Choose microphone, volume or mute')
    if 'device' in data and (not isinstance(data['device'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', data['device'])):
        raise ValueError('Choose an enumerated microphone')
    if 'volume' in data and (type(data['volume']) is not int or not 0 <= data['volume'] <= 100):
        raise ValueError('Microphone volume must be a whole number from 0 to 100')
    if 'muted' in data and type(data['muted']) is not bool:
        raise ValueError('Microphone mute must be boolean')
    return copy.deepcopy(data)

class InputSettings:
    def __init__(self, projection, path=None):
        self.projection = projection
        self.enabled = projection.enabled and hasattr(projection, 'apply_input')
        self.path = path or Path.home()/'.local/share/hudiy-recreation/input.json'
        self.lock = threading.RLock()
        self.data = dict(DEFAULTS)
        if self.enabled:
            try:
                if self.path.is_symlink() or self.path.stat().st_size > 2048:
                    raise ValueError('Invalid input preference file')
                self.data.update(validate_input(json.loads(self.path.read_text(encoding='utf-8'))))
            except (OSError, ValueError, TypeError):
                pass
            projection.input_options = dict(self.data)

    def snapshot(self):
        with self.lock:
            projection = self.projection.snapshot() if self.enabled else {}
            native = projection.get('audioInput', {})
            available = projection.get('available') is True and isinstance(native, dict) and native.get('configured') is True and isinstance(native.get('settings'), dict)
            return {'enabled': self.enabled, 'available': available,
                    'settings': dict(self.data), 'applied': available and native.get('settings') == self.data,
                    'devices': copy.deepcopy(native.get('devices', [])) if available else [],
                    'resolvedDevice': native.get('resolvedDevice', '') if available else '',
                    'captureActive': available and native.get('captureActive') is True,
                    'microphoneAvailable': available and native.get('microphoneAvailable') is True,
                    'error': native.get('error', '') if available else 'Microphone controls require the native Pi receiver'}

    def save(self, patch):
        validated = validate_input(patch)
        with self.lock:
            state = self.snapshot()
            if not self.enabled or not state['available']:
                raise ConnectionError('Microphone controls require the native Pi receiver')
            updated = {**self.data, **validated}
            if updated['device'] not in ('default', self.data['device']) and not any(
                    item.get('id') == updated['device'] and item.get('supported') is True for item in state['devices']):
                raise ValueError('Microphone is unavailable or does not support Android Auto voice input')
            # Do not follow a substituted preferences file or temporary-file symlink.
            if self.path.is_symlink() or self.path.with_name(self.path.name+'.tmp').is_symlink():
                raise OSError('Unsafe input preferences path')
            previous = dict(self.data)
            self.projection.apply_input(updated)
            try:
                save_json(self.path, updated)
            except OSError:
                try: self.projection.apply_input(previous)
                except (OSError, ConnectionError): pass
                raise
            self.data = updated
            self.projection.input_options = dict(updated)
            return {**self.snapshot(), 'saved': True, 'message': 'Microphone settings saved'}
