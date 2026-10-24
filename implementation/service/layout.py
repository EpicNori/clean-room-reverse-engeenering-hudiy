"""Durable, allowlisted personal layout for our native web views."""
import copy
import json
from pathlib import Path
import threading
from runtime_support import save_json

MENU_IDS = {
    'Phone': ['contacts', 'favorites', 'dialpad', 'call-log', 'active-call', 'notifications'],
    'Music': ['storage', 'radio', 'a2dp', 'autobox-music', 'android-music'],
    'Android Auto': ['android-usb', 'android-wifi', 'android-resume', 'android-quit'],
    'Autobox': ['autobox-wifi', 'autobox-resume'],
    'Hudiy': ['active-apps', 'settings', 'quit', 'obd-charts', 'obd-blocks', 'combined', 'gauges', 'gauges-2', 'custom-obd', 'obd-logs', 'marketplace'],
    'System': ['theme', 'appearance', 'application', 'notification-settings', 'overlays', 'about', 'music-settings', 'contacts-settings'],
    'Projections': ['android-settings', 'autobox-settings'],
    'Audio': ['sound', 'equalizer', 'presets'],
    'Bluetooth': ['pair', 'remove', 'bluetooth-connections'],
}
REQUIRED = {'dashboard', 'apps', 'android-resume'}
DEFAULT_LAYOUT = {
    'taskbar': ['dashboard', 'apps', 'mute', 'volume-down', 'volume-up', 'android-resume', 'connection-status', 'clock'],
    'columns': ['clock-navigation', 'music', 'phone'],
    'leftCards': ['clock', 'navigation'],
    'menus': MENU_IDS,
}
SHORTCUTS = set(DEFAULT_LAYOUT['taskbar']) | {'media-toggle', 'media-next', 'media-previous'} | {id for group in MENU_IDS.values() for id in group}


def validate_layout(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_LAYOUT):
        raise ValueError('Layout requires taskbar, columns, leftCards and menus')
    def items(data, allowed, complete=False):
        if (not isinstance(data, list) or len(data) > len(allowed) or
                any(not isinstance(id, str) or id not in allowed for id in data) or
                len(set(data)) != len(data) or (complete and set(data) != set(allowed))):
            raise ValueError('Layout contains invalid or duplicate items')
        return list(data)
    taskbar = items(value['taskbar'], SHORTCUTS)
    if not REQUIRED.issubset(taskbar):
        raise ValueError('Keep Dashboard, Applications and Android Auto shortcuts')
    groups = value['menus']
    if not isinstance(groups, dict) or set(groups) != set(MENU_IDS):
        raise ValueError('Invalid application categories')
    # Upgrade the previous catalog without discarding its personal taskbar/order.
    groups = dict(groups)
    bluetooth = groups['Bluetooth']
    if isinstance(bluetooth,list) and 'bluetooth-connections' not in bluetooth:
        groups['Bluetooth']=bluetooth+['bluetooth-connections']
    hudiy=groups['Hudiy']
    if isinstance(hudiy,list):groups['Hudiy']=hudiy+[id for id in ('custom-obd','obd-logs') if id not in hudiy]
    system = groups['System']
    if isinstance(system, list):
        groups['System'] = system + [id for id in ('music-settings', 'contacts-settings') if id not in system]
    return {'taskbar': taskbar,
            'columns': items(value['columns'], DEFAULT_LAYOUT['columns'], True),
            'leftCards': items(value['leftCards'], DEFAULT_LAYOUT['leftCards'], True),
            'menus': {key: items(groups[key], allowed, True) for key, allowed in MENU_IDS.items()}}


class LayoutStore:
    def __init__(self, enabled=False, path=None):
        self.enabled = enabled
        self.path = path or Path.home() / '.local/share/hudiy-recreation/layout.json'
        self.lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULT_LAYOUT)
        if enabled:
            try:
                if self.path.stat().st_size > 4096: raise ValueError('Layout file exceeds size limit')
                self.data = validate_layout(json.loads(self.path.read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError): pass

    def snapshot(self):
        with self.lock: return copy.deepcopy(self.data)

    def save(self, value):
        if not self.enabled: raise ConnectionError('Durable layout requires the Pi host')
        validated = validate_layout(value)
        with self.lock:
            save_json(self.path, validated)
            self.data = validated
            return {'layout': self.snapshot(), 'saved': True}
