"""Durable, allowlisted personal layout for our native web views."""
import copy
import json
from pathlib import Path
import threading
from runtime_support import save_json

MENU_IDS = {
    'Phone': ['contacts', 'favorites', 'dialpad', 'call-log', 'active-call'],
    'Music': ['storage', 'radio', 'a2dp', 'android-music'],
    'Android Auto': ['android-usb', 'android-wifi', 'android-resume', 'android-quit'],
    'Vehicle': ['custom-obd', 'gauges', 'gauges-2', 'combined', 'obd-charts', 'obd-blocks', 'obd-logs', 'obd-settings'],
    'Hudiy': ['settings', 'marketplace', 'quit'],
    'System': ['dashboard-editor', 'theme', 'appearance', 'notification-settings', 'application', 'software-update', 'about'],
    'Projections': ['android-settings'],
    'Audio': ['sound', 'audio-input', 'equalizer', 'presets', 'music-settings'],
    'Bluetooth': ['pair', 'remove', 'bluetooth-connections', 'contacts-settings'],
}
# Earlier catalogs offered these placeholders; saved layouts drop them instead of failing validation.
RETIRED_GROUPS = {'Autobox'}
RETIRED_IDS = {'notifications', 'active-apps', 'overlays', 'autobox-wifi', 'autobox-resume', 'autobox-music', 'autobox-settings'}
ADDED_GROUPS = {'Vehicle'}
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
    taskbar = value['taskbar']
    if isinstance(taskbar, list): taskbar = [id for id in taskbar if not (isinstance(id, str) and id in RETIRED_IDS)]
    taskbar = items(taskbar, SHORTCUTS)
    if not REQUIRED.issubset(taskbar):
        raise ValueError('Keep Dashboard, Applications and Android Auto shortcuts')
    groups = value['menus']
    if (not isinstance(groups, dict) or not set(MENU_IDS) - ADDED_GROUPS <= set(groups) <= set(MENU_IDS) | RETIRED_GROUPS
            or any(not isinstance(group, list) for group in groups.values())):
        raise ValueError('Invalid application categories')
    # Upgrade a previous catalog without discarding its personal taskbar/order: known
    # tiles keep their relative order, moved tiles join their new group, new tiles append.
    known = SHORTCUTS | RETIRED_IDS
    for group in groups.values():
        items(group, known)
    previous = [id for group in groups.values() for id in group]
    def upgrade(key, allowed):
        source = groups.get(key, previous)
        kept = [id for id in source if id in allowed]
        return kept + [id for id in allowed if id not in kept]
    return {'taskbar': taskbar,
            'columns': items(value['columns'], DEFAULT_LAYOUT['columns'], True),
            'leftCards': items(value['leftCards'], DEFAULT_LAYOUT['leftCards'], True),
            'menus': {key: items(upgrade(key, allowed), allowed, True) for key, allowed in MENU_IDS.items()}}


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
