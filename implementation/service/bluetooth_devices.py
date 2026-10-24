"""Bounded BlueZ device list/discovery with explicit confirmed unpairing."""
import copy
import json
from pathlib import Path
import re
import sys
import threading
import time
from runtime_support import save_json

PHONE_UUIDS = frozenset({'0000112f-0000-1000-8000-00805f9b34fb',
    '0000111f-0000-1000-8000-00805f9b34fb', '00001112-0000-1000-8000-00805f9b34fb',
    '4de17a00-52cb-11e6-bdf4-0800200c9a66'})
AA_UUID = '4de17a00-52cb-11e6-bdf4-0800200c9a66'

def is_phone(props):
    uuids = {str(u).lower() for u in props.get('UUIDs', [])}
    device_class = props.get('Class', 0)
    return bool(uuids & PHONE_UUIDS) or (isinstance(device_class, int) and (device_class >> 8) & 31 == 2)

ADDRESS = re.compile(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}')
DEVICE_PATH = re.compile(r'/org/bluez/hci\d+/dev_(?:[0-9A-F]{2}_){5}[0-9A-F]{2}')
ADAPTER_PATH = re.compile(r'/org/bluez/hci\d+')
PLAYER_PATH = re.compile(r'/org/bluez/hci\d+/dev_(?:[0-9A-F]{2}_){5}[0-9A-F]{2}/player\d+')


def addressed_players(objects, devices):
    players = []
    for device in devices:
        if not device['paired'] or not device['connected']: continue
        control = objects.get(device['_path'], {}).get('org.bluez.MediaControl1', {})
        path = str(control.get('Player', ''))
        if not PLAYER_PATH.fullmatch(path) or not path.startswith(device['_path'] + '/'): continue
        props = objects.get(path, {}).get('org.bluez.MediaPlayer1')
        if props and str(props.get('Device')) == device['_path']: players.append((path, props))
    return players


def player_media(players):
    if len(players) != 1: return {}
    props = players[0][1]
    track = props.get('Track', {})
    title = str(track.get('Title', ''))[:512]
    if not title or title == 'Not Provided': return {}
    def clock(value):
        try: seconds = min(86400, max(0, int(value) // 1000))
        except (ValueError, TypeError, OverflowError): seconds = 0
        return f'{seconds // 60:02}:{seconds % 60:02}'
    return {'source': 'bluetooth', 'title': title,
            'artist': str(track.get('Artist', ''))[:512], 'album': str(track.get('Album', ''))[:512],
            'position': clock(props.get('Position', 0)), 'duration': clock(track.get('Duration', 0)),
            'playing': props.get('Status') in ('playing', 'forward-seek', 'reverse-seek')}


def read_devices(objects):
    adapters = [(str(path), props['org.bluez.Adapter1']) for path, props in objects.items()
                if 'org.bluez.Adapter1' in props and ADAPTER_PATH.fullmatch(str(path))]
    powered = [item for item in adapters if item[1].get('Powered')]
    if len(powered) != 1:
        raise ConnectionError('Enable one Bluetooth adapter in the system')
    adapter, info = powered[0]
    devices = []
    for path, interfaces in objects.items():
        props = interfaces.get('org.bluez.Device1')
        if not props or not DEVICE_PATH.fullmatch(str(path)) or str(props.get('Adapter')) != adapter: continue
        address = str(props.get('Address', '')).upper()
        if not ADDRESS.fullmatch(address): continue
        devices.append({'address': address, 'name': str(props.get('Alias', props.get('Name', address)))[:128],
                        'paired': bool(props.get('Paired')), 'connected': bool(props.get('Connected')),
                        'phone': is_phone(props),
                        'serialPort': '00001101-0000-1000-8000-00805f9b34fb' in [str(u).lower() for u in props.get('UUIDs',[])],
                        'audioReceiver': '0000110b-0000-1000-8000-00805f9b34fb' in [str(u).lower() for u in props.get('UUIDs',[])]
                            and not is_phone(props),
                        '_path': str(path)})
        if len(devices) >= 128: break
    devices.sort(key=lambda item: item['address'])
    return adapter, {'name': str(info.get('Alias', info.get('Name', 'coscarOS')))[:128],
                     'discovering': bool(info.get('Discovering'))}, devices


class BluetoothDevices:
    def __init__(self, enabled=False, preferences=None):
        self.enabled = enabled and sys.platform == 'linux'
        self.lock = threading.RLock()
        self.operation_lock = threading.Lock()
        self.stop = threading.Event()
        self.worker = None
        self.bus = self.dbus = self.manager = None
        self.adapter = None
        self.devices = []
        self.media = {}
        self.preferences = preferences or Path.home()/'.local/share/hudiy-recreation/bluetooth-connections.json'
        self.automatic = set()
        self.manual_phones = set()
        self.automatic_phone_allowed = lambda: False
        self.phone_connection_ready = lambda: True
        self.last_attempt = {}
        self.scan_until = 0
        self.data = {'available': False, 'name': 'coscarOS', 'discovering': False,
                     'scanActive': False, 'devices': [], 'error': 'Bluetooth is available on the Pi'}

    def snapshot(self):
        effective=self._automatic_addresses()
        with self.lock: return {**copy.deepcopy(self.data),'autoConnect':sorted(self.automatic), 'manualPhones':sorted(self.manual_phones), 'effectiveAutoConnect':sorted(effective)}

    def connection(self, operation, address, enabled=None, confirmed=False):
        if operation not in ('connect','disconnect','automatic'): raise ValueError('Unknown connection action')
        if not isinstance(address,str) or not ADDRESS.fullmatch(address): raise ValueError('Choose a paired device address')
        if operation=='automatic' and type(enabled) is not bool: raise ValueError('Automatic reconnect must be boolean')
        if operation=='disconnect' and confirmed is not True: raise ValueError('Confirm device disconnection')
        if not self.enabled or not self.bus: raise ConnectionError('Bluetooth service unavailable')
        if not self.operation_lock.acquire(blocking=False): raise ConnectionError('Bluetooth operation in progress')
        try:
            self._refresh()
            with self.lock: selected=next((d for d in self.devices if d['paired'] and d['address']==address),None)
            if not selected: raise ValueError('Choose a currently paired device')
            if operation in ('automatic','disconnect'):
                with self.lock:
                    updated=set(self.automatic)
                    manual=set(self.manual_phones)
                    if selected.get("phone"):
                        if operation=="automatic" and enabled: manual.discard(address)
                        else: manual.add(address)
                    if operation=='automatic' and enabled: updated.add(address)
                    else: updated.discard(address)
                    if len(manual)>128: raise ValueError('Too many saved phone choices')
                    if len(updated)>16: raise ValueError('Choose at most 16 automatic connections')
                    save_json(self.preferences,{'addresses':sorted(updated),'manualPhones':sorted(manual)})
                    self.automatic=updated
                    self.manual_phones=manual
                    self.last_attempt.pop(address,None)
            if operation!='automatic':
                device=self.dbus.Interface(self.bus.get_object('org.bluez',selected['_path']),'org.bluez.Device1')
                self.last_attempt[address]=time.monotonic()
                if operation=='connect': device.Connect(timeout=3)
                elif selected['connected']: device.Disconnect(timeout=3)
            self._refresh()
            return {'accepted':True,'message':'Automatic reconnect saved' if operation=='automatic' else 'Bluetooth connection requested'}
        finally: self.operation_lock.release()

    def _load_connections(self):
        try:
            if self.preferences.stat().st_size>8192:return
            saved=json.loads(self.preferences.read_text())
            addresses=saved.get('addresses') if isinstance(saved,dict) and set(saved) in ({'addresses'}, {'addresses','manualPhones'}) else None
            if isinstance(addresses,list) and len(addresses)<=16 and all(isinstance(a,str) and ADDRESS.fullmatch(a) for a in addresses):
                manual=saved.get('manualPhones',[])
                if not isinstance(manual,list) or len(manual)>128 or not all(isinstance(a,str) and ADDRESS.fullmatch(a) for a in manual):return
                with self.lock:
                    self.automatic=set(addresses)
                    self.manual_phones=set(manual)
        except (OSError,ValueError):pass

    def _automatic_addresses(self):
        allowed=self.automatic_phone_allowed()
        with self.lock:return self._selected_addresses(allowed)

    def _selected_addresses(self, allowed):
        addresses=set(self.automatic)
        if allowed:
            phones=[d for d in self.devices if d['paired'] and d.get('phone')]
            # With several phones require an explicit per-phone choice.
            if len(phones)==1 and phones[0]['address'] not in self.manual_phones:
                addresses.add(phones[0]['address'])
        return addresses

    def retry_android_auto(self, manual=False):
        """Connect the paired phone normally so it can discover our HU service.

        The AA UUID is our server service, not a remote phone client profile.
        Never pair, disconnect a phone, or reset USB to bootstrap wireless.
        """
        if not self.enabled or not self.bus:raise ConnectionError('Bluetooth is not ready')
        if not manual and not self.automatic_phone_allowed():return 'manual'
        if not self.operation_lock.acquire(blocking=False):return 'waiting-for-bluetooth'
        try:
            self._refresh()
            addresses=self._automatic_addresses()
            with self.lock:
                phones=[d for d in self.devices if d['paired'] and d.get('phone')]
                connected=[d for d in phones if d['connected']]
                if len(connected)>1:return 'phone-selection'
                if connected:
                    selected=connected[0]
                    if not manual and selected['address'] not in addresses:return 'phone-selection'
                else:
                    candidates=phones if manual and len(phones)==1 else [d for d in phones if d['address'] in addresses]
                    if len(candidates)!=1:return 'phone-selection'
                    selected=candidates[0]
                now=time.monotonic()
                if now-self.last_attempt.get(selected['address'],float('-inf'))<(5 if manual else 30):
                    return 'waiting-for-phone'
                self.last_attempt[selected['address']]=now
                path=selected['_path']
            try:self.dbus.Interface(self.bus.get_object('org.bluez',path),'org.bluez.Device1').Connect(timeout=3)
            except Exception as error:
                name=getattr(error,'get_dbus_name',lambda:'')()
                if name not in ('org.bluez.Error.AlreadyConnected','org.bluez.Error.InProgress'):
                    raise ConnectionError('The paired phone could not reconnect over Bluetooth') from None
            return 'waiting-for-phone'
        finally:self.operation_lock.release()

    def _reconnect(self):
        now=time.monotonic()
        addresses=self._automatic_addresses()
        phone_ready=self.phone_connection_ready()
        with self.lock:
            selected=next((d for d in self.devices if d['paired'] and not d['connected'] and d['address'] in addresses and (not d.get('phone') or phone_ready) and now-self.last_attempt.get(d['address'],float('-inf'))>=30),None)
        if selected:
            self.last_attempt[selected['address']]=now
            try:self.dbus.Interface(self.bus.get_object('org.bluez',selected['_path']),'org.bluez.Device1').Connect(timeout=3)
            except Exception:pass

    def media_snapshot(self):
        with self.lock: return dict(self.media)

    def _refresh(self):
        objects = self.manager.GetManagedObjects(timeout=3)
        adapter, info, devices = read_devices(objects)
        with self.lock:
            self.adapter, self.devices = adapter, devices
            self.media = player_media(addressed_players(objects, devices))
            self.data = {'available': True, **info, 'scanActive': bool(self.scan_until), 'error': '',
                         'devices': [{k: v for k, v in item.items() if not k.startswith('_')} for item in devices]}

    def _adapter(self):
        if not self.adapter: raise ConnectionError('Bluetooth adapter unavailable')
        return self.dbus.Interface(self.bus.get_object('org.bluez', self.adapter), 'org.bluez.Adapter1')

    def command(self, operation, address=None, confirmed=False):
        if operation not in ('scan', 'stop', 'remove'): raise ValueError('Unknown Bluetooth action')
        if operation == 'remove' and (not isinstance(address, str) or not ADDRESS.fullmatch(address) or confirmed is not True):
            raise ValueError('Unpairing requires a known device address and explicit confirmation')
        if not self.enabled or not self.bus: raise ConnectionError('Bluetooth service unavailable')
        if not self.operation_lock.acquire(blocking=False): raise ConnectionError('Bluetooth operation in progress')
        try:
            self._refresh()
            adapter = self._adapter()
            if operation == 'scan':
                if not self.scan_until: adapter.StartDiscovery(timeout=3)
                self.scan_until = time.monotonic() + 30
                result = {'accepted': True, 'message': 'Scanning for Bluetooth devices'}
            elif operation == 'stop':
                self._stop_scan()
                result = {'accepted': True}
            else:
                with self.lock: selected = next((d for d in self.devices if d['address'] == address and d['paired']), None)
                if not selected: raise ValueError('Choose a currently paired device')
                adapter.RemoveDevice(self.dbus.ObjectPath(selected['_path']), timeout=3)
                result = {'accepted': True, 'message': 'Device unpaired'}
            self._refresh()
            return result
        finally: self.operation_lock.release()

    def _stop_scan(self):
        if self.scan_until:
            try: self._adapter().StopDiscovery(timeout=3)
            finally: self.scan_until = 0

    def playback(self, operation):
        if operation not in ('toggle', 'next', 'previous'): raise ValueError('Unknown Bluetooth playback action')
        if not self.enabled or not self.bus: raise ConnectionError('Bluetooth service unavailable')
        if not self.operation_lock.acquire(blocking=False): raise ConnectionError('Bluetooth operation in progress')
        try:
            objects = self.manager.GetManagedObjects(timeout=3)
            _, _, devices = read_devices(objects)
            players = addressed_players(objects, devices)
            if len(players) != 1: raise ConnectionError('Connect one paired Bluetooth music player')
            path, props = players[0]
            if operation == 'toggle' and props.get('Status') not in ('playing','paused','stopped','forward-seek','reverse-seek'):
                raise ConnectionError('Bluetooth player status unavailable')
            method = {'next':'Next','previous':'Previous'}.get(operation, 'Pause' if props.get('Status') in ('playing','forward-seek','reverse-seek') else 'Play')
            player = self.dbus.Interface(self.bus.get_object('org.bluez', path), 'org.bluez.MediaPlayer1')
            getattr(player, method)(timeout=3)
            return {'accepted': True, 'operation': operation}
        finally: self.operation_lock.release()

    def start(self):
        if self.enabled and not self.worker:
            self._load_connections()
            self.worker = threading.Thread(target=self._run, daemon=True)
            self.worker.start()

    def _run(self):
        while not self.stop.is_set():
            self._run_once()
            self.stop.wait(2)

    def _run_once(self):
        try:
            import dbus
            self.dbus = dbus
            self.bus = dbus.SystemBus(private=True)
            self.manager = dbus.Interface(self.bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
            while not self.stop.is_set():
                try:
                    with self.operation_lock:
                        if self.scan_until and time.monotonic() >= self.scan_until: self._stop_scan()
                        self._refresh()
                        self._reconnect()
                except Exception:
                    with self.lock:
                        self.data.update(available=False, devices=[], error='Bluetooth connection unavailable')
                        self.devices = []
                        self.media = {}
                self.stop.wait(1)
        except Exception:
            with self.lock: self.data.update(available=False, error='BlueZ D-Bus service unavailable')
        finally:
            if self.bus:
                try:
                    with self.operation_lock: self._stop_scan()
                except Exception: pass
                self.bus.close()
                self.bus = None

    def close(self):
        self.stop.set()
        if self.worker: self.worker.join(timeout=4)
