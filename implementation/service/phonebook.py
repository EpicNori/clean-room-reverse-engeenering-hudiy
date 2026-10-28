"""Read paired phone contacts using the public BlueZ PBAP API; cache in RAM."""
import copy
import os
from pathlib import Path
import quopri
import re
import sys
import tempfile
import threading
import time

MAX_BYTES = 2 * 1024 * 1024
VIEWS = {'contacts': ('pb', 1000), 'favorites': ('fav', 100), 'call-log': ('cch', 100)}
PHONEBOOK_UUID = '0000112f-0000-1000-8000-00805f9b34fb'
# Errors meaning BlueZ/obexd left the bus or our connection died; proxies must be rebuilt.
LOST = ('org.freedesktop.DBus.Error.ServiceUnknown', 'org.freedesktop.DBus.Error.NameHasNoOwner',
        'org.freedesktop.DBus.Error.Disconnected')
MAX_FAILURES = 6
UNAVAILABLE = 'Bluetooth phonebook service unavailable; install python3-dbus and bluez-obexd'


def service_lost(error):
    name = getattr(error, 'get_dbus_name', None)
    return callable(name) and name() in LOST


def parse_vcards(payload, limit=1000):
    if len(payload) > MAX_BYTES:
        raise ValueError('Phonebook exceeds the local size limit')
    text = payload.decode('utf-8', 'replace').replace('\r\n', '\n')
    text = re.sub(r'=\n', '', text)
    text = re.sub(r'\n[ \t]', '', text)
    entries, current = [], None
    for line in text.split('\n'):
        if line.strip().upper() == 'BEGIN:VCARD':
            current = {'name': '', 'numbers': [], 'date': ''}
            continue
        if line.strip().upper() == 'END:VCARD':
            if current and current['numbers']:
                current['name'] = current['name'] or current['numbers'][0]
                entries.append(current)
                if len(entries) >= limit:
                    break
            current = None
            continue
        if current is None or ':' not in line:
            continue
        header, value = line.split(':', 1)
        name = header.split(';', 1)[0].split('.')[-1].upper()
        if 'ENCODING=QUOTED-PRINTABLE' in header.upper():
            value = quopri.decodestring(value.encode('utf-8')).decode('utf-8', 'replace')
        value = re.sub(r'\\([nN,;\\])', lambda m: '\n' if m[1].lower() == 'n' else m[1], value)
        if name == 'FN':
            current['name'] = value.strip()[:160]
        elif name == 'N' and not current['name']:
            parts = value.split(';')
            current['name'] = ' '.join(parts[1:2] + parts[:1]).strip()[:160]
        elif name == 'TEL':
            value = re.sub(r'^tel:', '', value, flags=re.I)
            number = re.sub(r'[^0-9+*#]', '', value)[:32]
            if number and number not in current['numbers'] and len(current['numbers']) < 8:
                current['numbers'].append(number)
        elif name == 'X-IRMC-CALL-DATETIME':
            current['date'] = value.strip()[:32]
    return entries


class Phonebook:
    def __init__(self, enabled=False):
        self.enabled = enabled and sys.platform == 'linux'
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.worker = None
        self.pending = set()
        self.data = {'available': False, 'connected': False, 'name': '',
                     'source': 'bluetooth-pbap', 'syncing': False, 'updatedAt': None,
                     'error': 'Connect your phone by Bluetooth and allow contact sharing',
                     'views': {key: {'entries': [], 'error': '', 'updatedAt': None} for key in VIEWS}}
        self.address = ''
        self.session = None
        self.client = None
        self.refresh_interval = 60
        self.retry_interval = 3

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.data)

    def status(self):
        with self.lock:
            return {key: self.data[key] for key in ('available', 'connected', 'name')}

    def refresh(self, view):
        if view not in VIEWS:
            raise ValueError('Unknown phonebook view')
        if not self.enabled:
            raise ConnectionError('Live contacts require Bluetooth PBAP on the Pi')
        with self.lock:
            self.pending.add(view)
        self.wake.set()
        return {'accepted': True, 'message': 'Refreshing phone contacts'}

    def start(self):
        if self.enabled and not self.worker:
            self.worker = threading.Thread(target=self._run, daemon=True)
            self.worker.start()

    def _forget(self, error):
        if self.session and self.client:
            try:
                self.client.RemoveSession(self.session, timeout=3)
            except Exception:
                pass
        self.session, self.address = None, ''
        with self.lock:
            self.data.update(available=False, connected=False, name='', syncing=False,
                             updatedAt=None, error=error)
            self.data['views'] = {key: {'entries': [], 'error': '', 'updatedAt': None} for key in VIEWS}

    def _ensure_session(self, bus, dbus, address):
        # Bluetooth can remain connected after obexd removes its PBAP session.
        # Check only our own session; never reuse/remove another client's session.
        present = False
        if self.session and address == self.address:
            objects = dbus.Interface(bus.get_object('org.bluez.obex', '/'),
                'org.freedesktop.DBus.ObjectManager').GetManagedObjects(timeout=3)
            present = 'org.bluez.obex.PhonebookAccess1' in objects.get(self.session, {})
        if present:
            return False
        self._forget('Connecting phonebook')
        self.session = self.client.CreateSession(address,
            dbus.Dictionary({'Target': 'pbap'}, signature='sv'), timeout=12)
        self.address = address
        return True

    def _run(self):
        # BlueZ/obexd may start after us or restart; rebuild buses and proxies each round.
        while not self.stop.is_set():
            self._run_once()
            self.stop.wait(self.retry_interval)

    def _run_once(self):
        system = session_bus = None
        error = 'Phonebook service stopped'
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib
            system = dbus.SystemBus(private=True)
            session_bus = dbus.SessionBus(private=True, mainloop=DBusGMainLoop())
            self.context = GLib.MainContext.default()
            manager = dbus.Interface(system.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
            self.client = dbus.Interface(session_bus.get_object('org.bluez.obex', '/org/bluez/obex'), 'org.bluez.obex.Client1')
            self._poll(manager, session_bus, dbus)
        except Exception:
            error = UNAVAILABLE
        finally:
            # Remove our own PBAP session while the old client proxy still works.
            self._forget(error)
            self.client = None
            for bus in (system, session_bus):
                if bus:
                    try:
                        bus.close()
                    except Exception:
                        pass

    def _poll(self, manager, session_bus, dbus):
        last_sync = None
        failures = 0
        while not self.stop.is_set():
            try:
                objects = manager.GetManagedObjects(timeout=3)
                phones = [props['org.bluez.Device1'] for props in objects.values()
                          if 'org.bluez.Device1' in props and
                          props['org.bluez.Device1'].get('Paired') and
                          props['org.bluez.Device1'].get('Connected') and
                          PHONEBOOK_UUID in props['org.bluez.Device1'].get('UUIDs', [])]
                if len(phones) != 1:
                    self._forget('Connect one paired phone by Bluetooth and allow contact sharing')
                else:
                    device = phones[0]
                    address = str(device['Address'])
                    if self._ensure_session(session_bus, dbus, address):
                        last_sync = None
                    with self.lock:
                        self.data.update(available=True, connected=True, name=str(device.get('Alias', 'Phone'))[:128], error='')
                        views = set(self.pending)
                        self.pending.clear()
                    if last_sync is None or time.monotonic() - last_sync >= self.refresh_interval:
                        views.update(VIEWS)
                    for view in sorted(views):
                        if self.stop.is_set():
                            break
                        with self.lock:
                            self.data['syncing'] = True
                        try:
                            entries = self._pull(session_bus, dbus, view)
                            now = time.time()
                            with self.lock:
                                self.data['views'][view] = {'entries': entries, 'error': '', 'updatedAt': now}
                                self.data['updatedAt'] = now
                        except Exception:
                            with self.lock:
                                self.data['views'][view] = {'entries': [], 'error': 'Phone did not provide this phonebook; check contact sharing permission', 'updatedAt': None}
                    if views:
                        last_sync = time.monotonic()
                    with self.lock:
                        self.data['syncing'] = False
                failures = 0
            except Exception as exc:
                self._forget('Phonebook connection unavailable; unlock the phone and allow contact sharing')
                failures += 1
                # Leave so _run rebuilds buses and proxies for a restarted BlueZ/obexd.
                if service_lost(exc) or failures >= MAX_FAILURES:
                    raise
            self.wake.wait(5)
            self.wake.clear()

    def _pull(self, bus, dbus, view):
        folder, limit = VIEWS[view]
        book = dbus.Interface(bus.get_object('org.bluez.obex', self.session), 'org.bluez.obex.PhonebookAccess1')
        book.Select('int', folder, timeout=5)
        with tempfile.TemporaryDirectory(prefix='hudiy-phonebook-') as directory:
            target = Path(directory) / 'phonebook.vcf'
            target.touch(mode=0o600)
            filters = dbus.Dictionary({'Format': 'vcard30', 'MaxCount': dbus.UInt16(limit),
                'Fields': dbus.Array(['FN', 'N', 'TEL', 'X-IRMC-CALL-DATETIME'], signature='s')}, signature='sv')
            # obexd may remove a completed transfer before GetAll can read it.
            # Subscribe before PullAll so fast transfers retain terminal status.
            updates = {}
            def changed(interface, values, invalidated, path=None):
                if interface == 'org.bluez.obex.Transfer1' and path and str(path).startswith(str(self.session) + '/'):
                    updates.setdefault(str(path), {}).update(values)
            match = bus.add_signal_receiver(changed, signal_name='PropertiesChanged',
                dbus_interface='org.freedesktop.DBus.Properties', bus_name='org.bluez.obex', path_keyword='path')
            try:
                transfer, props = book.PullAll(str(target), filters, timeout=5)
                props = dict(props)
                properties = dbus.Interface(bus.get_object('org.bluez.obex', transfer), 'org.freedesktop.DBus.Properties')
                deadline = time.monotonic() + 12
                while not self.stop.is_set() and time.monotonic() < deadline:
                    for _ in range(20):
                        if not self.context.pending(): break
                        self.context.iteration(False)
                    props.update(updates.get(str(transfer), {}))
                    if int(props.get('Size', 0)) > MAX_BYTES or int(props.get('Transferred', 0)) > MAX_BYTES:
                        break
                    if props.get('Status') == 'complete':
                        if Path(str(props.get('Filename', target))).resolve() != target.resolve():
                            raise ValueError('Unexpected phonebook transfer location')
                        with target.open('rb') as handle:
                            return parse_vcards(handle.read(MAX_BYTES + 1), limit)
                    if props.get('Status') == 'error': break
                    try:
                        props.update(properties.GetAll('org.bluez.obex.Transfer1', timeout=3))
                    except dbus.DBusException:
                        # Dispatch the terminal signal queued with object removal.
                        for _ in range(20):
                            if not self.context.pending(): break
                            self.context.iteration(False)
                        if updates.get(str(transfer), {}).get('Status') != 'complete': raise
                    self.stop.wait(.1)
                dbus.Interface(bus.get_object('org.bluez.obex', transfer), 'org.bluez.obex.Transfer1').Cancel(timeout=3)
                raise ConnectionError('Phonebook transfer failed or timed out')
            finally:
                match.remove()

    def close(self):
        self.stop.set()
        self.wake.set()
        if self.worker:
            self.worker.join(timeout=4)
