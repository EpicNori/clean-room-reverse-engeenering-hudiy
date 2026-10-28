"""Our private settings, screen routes and Android Auto handshake encoding."""
import json
import os
from pathlib import Path

ROUTES = frozenset('''dashboard dashboard-editor apps settings software-update obd-settings custom-obd obd-logs playlist stations
    contacts favorites dialpad call-log active-call
    storage radio a2dp android-music
    obd-charts obd-blocks combined gauges gauges-2 marketplace
    theme appearance application notification-settings about music-settings contacts-settings
    android-settings sound audio-input equalizer presets pair remove bluetooth-connections'''.split())

PREFERENCES = Path.home() / '.local/share/hudiy-recreation/projection.json'

DAY_NIGHT_MODES = {'Common': 1, 'Day': 2, 'Night': 3}

DEFAULT_OPTIONS = {'blackStartup': True, 'autoConnect': True, 'autostart': False, 'taskbarVisible': True, 'restartGeneration': 0,
                   'dayNight': None, 'darkMode': None}

def read_options(path=PREFERENCES):
    result = dict(DEFAULT_OPTIONS)
    try:
        data = json.loads(path.read_text())
        for key in ('blackStartup', 'autoConnect', 'autostart', 'taskbarVisible'):
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
