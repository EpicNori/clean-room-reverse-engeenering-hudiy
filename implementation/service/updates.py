"""Bounded, durable refresh preferences, independent of browser storage."""
import json
from pathlib import Path
import threading
from projection import save_json

DEFAULTS = {'musicRefreshSeconds': 5, 'contactsRefreshSeconds': 60}
LIMITS = {'musicRefreshSeconds': (1, 60), 'contactsRefreshSeconds': (5, 3600)}


def validate_updates(value):
    if not isinstance(value, dict) or not value or set(value) - set(LIMITS):
        raise ValueError('Choose musicRefreshSeconds or contactsRefreshSeconds')
    for key, number in value.items():
        low, high = LIMITS[key]
        if type(number) is not int or not low <= number <= high:
            raise ValueError(f'{key} must be an integer from {low} to {high}')
    return dict(value)


class UpdateSettings:
    def __init__(self, projection, phonebook, path=None):
        self.projection, self.phonebook = projection, phonebook
        self.enabled = projection.enabled
        self.path = path or Path.home() / '.local/share/hudiy-recreation/updates.json'
        self.lock = threading.RLock()
        self.data = dict(DEFAULTS)
        if self.enabled:
            try:
                if self.path.stat().st_size > 512: raise ValueError('Refresh file exceeds size limit')
                self.data.update(validate_updates(json.loads(self.path.read_text(encoding='utf-8'))))
            except (OSError, ValueError, TypeError): pass
        self._apply()

    def _apply(self):
        self.projection.refresh_interval = self.data['musicRefreshSeconds']
        self.phonebook.refresh_interval = self.data['contactsRefreshSeconds']

    def snapshot(self):
        with self.lock: return dict(self.data)

    def save(self, value):
        if not self.enabled: raise ConnectionError('Live refresh settings require the Pi host')
        validated = validate_updates(value)
        with self.lock:
            data = {**self.data, **validated}
            save_json(self.path, data)
            self.data = data
            self._apply()
            self.phonebook.wake.set()
            return {'updates': self.snapshot(), 'saved': True, 'message': 'Refresh interval saved'}
