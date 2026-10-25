"""Prepare our protected car AP without activating it or reading Hudiy files.

Uses NetworkManager's D-Bus API so the Wi-Fi secret never appears in process
arguments. Run as the graphical-login user; no automatic sudo or Polkit changes.
"""
import argparse
from contextlib import contextmanager
import getpass
import json
import os
from pathlib import Path
import secrets
import select
import shutil
import subprocess
import socket
import sys
import tempfile
import uuid

CONNECTION = 'hudiy-recreation-car'
INTERFACE = 'wlan0'  # Our native and Bluetooth handoff currently use this adapter.
GATEWAY = '192.168.12.1'
TIMEOUT = 15
REQUIRED_WIFI = 0x40 | 0x400 | 0x20 | 0x08  # AP, 5 GHz, WPA2/RSN, CCMP.
STATE = Path.home() / '.local/share/hudiy-recreation/wireless.json'


class SetupError(ValueError):
    pass


@contextmanager
def terminal_authentication(terminal_path='/dev/tty', startup_timeout=5):
    """Offer normal Polkit authentication for this installer process only."""
    executable = shutil.which('pkttyagent')
    if os.name != 'posix' or not executable:
        yield False
        return
    try:
        terminal = open(terminal_path, 'r', encoding='utf-8',
            opener=lambda path, flags: os.open(path, flags | getattr(os, 'O_NOCTTY', 0)))
    except OSError:
        yield False
        return
    with terminal:
        readfd, writefd = os.pipe()
        agent = None
        try:
            # A piped installer has no usable stdin. The agent reads the controlling
            # terminal; credentials never become argv, profile data or Python input.
            agent = subprocess.Popen([executable, '--process', str(os.getpid()),
                '--notify-fd', str(writefd), '--fallback'], stdin=terminal,
                pass_fds=(writefd,))
            os.close(writefd); writefd = None
            if not select.select([readfd], [], [], startup_timeout)[0]:
                raise SetupError('Terminal authentication agent did not become ready; retry from the desktop terminal.')
            os.read(readfd, 1)
            # --fallback preserves an already registered agent instead of replacing it.
            yield agent.poll() is None
        finally:
            os.close(readfd)
            if writefd is not None: os.close(writefd)
            if agent is not None:
                if agent.poll() is None: agent.terminate()
                try: agent.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    agent.kill(); agent.wait(timeout=3)


def validate_ssid(ssid):
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode('utf-8')) <= 32 or any(ord(c) < 32 or ord(c) == 127 for c in ssid):
        raise SetupError('Hotspot name must be 1–32 UTF-8 bytes without control characters.')


def build_profile(ssid, passphrase, user, profile_uuid):
    validate_ssid(ssid)
    if not isinstance(passphrase, str) or not 8 <= len(passphrase) <= 63 or not passphrase.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in passphrase):
        raise SetupError('A protected hotspot key is required.')
    if not user or any(c in user for c in ':\n\r'):
        raise SetupError('Invalid graphical-login user.')
    uuid.UUID(profile_uuid)
    return {
        'connection': {'id': CONNECTION, 'uuid': profile_uuid, 'type': '802-11-wireless',
                       'interface-name': INTERFACE, 'autoconnect': False,
                       'permissions': ['user:' + user + ':']},
        '802-11-wireless': {'ssid': ssid.encode('utf-8'), 'mode': 'ap', 'band': 'a',
                           'channel': 36, 'security': '802-11-wireless-security'},
        '802-11-wireless-security': {'key-mgmt': 'wpa-psk', 'psk': passphrase,
                                    'psk-flags': 0, 'proto': ['rsn'],
                                    'pairwise': ['ccmp'], 'group': ['ccmp']},
        'ipv4': {'method': 'shared', 'address-data': [{'address': GATEWAY, 'prefix': 24}],
                 'never-default': True},
        'ipv6': {'method': 'disabled'},
    }


class NetworkManager:
    def __init__(self):
        import dbus
        self.dbus = dbus
        self.bus = dbus.SystemBus()
        self.manager = self._interface('/org/freedesktop/NetworkManager', 'org.freedesktop.NetworkManager')
        self.settings = self._interface('/org/freedesktop/NetworkManager/Settings', 'org.freedesktop.NetworkManager.Settings')

    def _interface(self, path, name):
        return self.dbus.Interface(self.bus.get_object('org.freedesktop.NetworkManager', path), name)

    def _connection(self, path):
        return self._interface(path, 'org.freedesktop.NetworkManager.Settings.Connection')

    def hardware(self):
        for path in self.manager.GetDevices(timeout=TIMEOUT):
            properties = self._interface(path, 'org.freedesktop.DBus.Properties')
            device = properties.GetAll('org.freedesktop.NetworkManager.Device', timeout=TIMEOUT)
            if str(device.get('Interface')) != INTERFACE:
                continue
            if int(device.get('DeviceType', 0)) != 2 or not device.get('Managed'):
                raise SetupError('wlan0 must be a Wi-Fi adapter managed by NetworkManager.')
            wireless = properties.GetAll('org.freedesktop.NetworkManager.Device.Wireless', timeout=TIMEOUT)
            if int(wireless.get('WirelessCapabilities', 0)) & REQUIRED_WIFI != REQUIRED_WIFI:
                raise SetupError('wlan0 must support AP mode, 5 GHz and WPA2/CCMP.')
            return {'interface': INTERFACE, 'protected5GHzAP': True}
        raise SetupError('No supported wlan0 adapter was found.')

    def profiles(self):
        return [(str(path), self._connection(path).GetSettings(timeout=TIMEOUT))
                for path in self.settings.ListConnections(timeout=TIMEOUT)]

    def profile_secret(self, path):
        with terminal_authentication() as interactive:
            data = self._connection(path).GetSecrets('802-11-wireless-security',
                timeout=120 if interactive else TIMEOUT)
        return str(data.get('802-11-wireless-security', {}).get('psk', ''))

    def add(self, profile):
        d = self.dbus
        typed = {}
        for section, values in profile.items():
            converted = {}
            for key, value in values.items():
                if key == 'ssid': value = d.ByteArray(value)
                elif key == 'address-data':
                    value = d.Array([d.Dictionary({'address': d.String(entry['address']),
                                                  'prefix': d.UInt32(entry['prefix'])}, signature='sv')
                                     for entry in value], signature='a{sv}')
                elif isinstance(value, bool): value = d.Boolean(value)
                elif isinstance(value, int): value = d.UInt32(value)
                elif isinstance(value, list): value = d.Array(value, signature='s')
                else: value = d.String(value)
                converted[key] = value
            typed[section] = d.Dictionary(converted, signature='sv')
        # autoconnect is false: AddConnection saves but cannot activate this AP.
        with terminal_authentication() as interactive:
            return str(self.settings.AddConnection(d.Dictionary(typed, signature='sa{sv}'),
                timeout=120 if interactive else TIMEOUT))

    def delete_owned(self, path, expected_uuid):
        connection = self._connection(path)
        actual = connection.GetSettings(timeout=TIMEOUT).get('connection', {})
        if str(actual.get('uuid')) != expected_uuid:
            raise SetupError('Rollback refused a profile with a different UUID.')
        with terminal_authentication() as interactive:
            connection.Delete(timeout=120 if interactive else TIMEOUT)


def read_state(path):
    if not path.exists() and not path.is_symlink(): return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2048:
        raise SetupError('Existing wireless settings must be a small regular private file.')
    if os.name == 'posix' and (path.stat().st_uid != os.geteuid() or path.stat().st_mode & 0o077):
        raise SetupError('Existing wireless settings must belong to this user with mode 0600.')
    try: data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): raise SetupError('Existing wireless settings cannot be read safely.') from None
    if not isinstance(data, dict) or type(data.get('enabled')) is not bool:
        raise SetupError('Existing wireless settings are invalid.')
    validate_ssid(data.get('ssid'))
    build_profile(data['ssid'], data.get('passphrase'), getpass.getuser(), str(uuid.uuid4()))
    if data.get('ipAddress') != GATEWAY or data.get('port') != 5277:
        raise SetupError('Existing wireless settings use an unsupported car network.')
    return data


def private_directory(directory):
    if directory.is_symlink(): raise SetupError('The private state directory cannot be a symlink.')
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == 'posix' and directory.stat().st_uid != os.geteuid():
        raise SetupError('The private state directory must belong to this user.')
    directory.chmod(0o700)


def write_state(path, data):
    private_directory(path.parent)
    if path.exists() or path.is_symlink(): raise SetupError('Refusing to replace existing wireless settings.')
    descriptor, temporary = tempfile.mkstemp(prefix='.wireless-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            if os.name == 'posix': os.fchmod(stream.fileno(), 0o600)
            stream.write(json.dumps(data) + '\n'); stream.flush(); os.fsync(stream.fileno())
        # Hard-link publication is atomic and fails if another writer created it.
        os.link(temporary, path)
        if os.name == 'posix':
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
    except Exception:
        # If fsync failed after publication, remove only our exact inode.
        if path.exists() and not path.is_symlink() and os.stat(temporary).st_ino == path.stat().st_ino:
            path.unlink()
        raise
    finally: os.unlink(temporary)


def app_running():
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(('127.0.0.1', 8766)) == 0


def inspect(network, path=STATE):
    hardware = network.hardware()
    matches = [(key, value) for key, value in network.profiles()
               if str(value.get('connection', {}).get('id')) == CONNECTION]
    if len(matches) > 1: raise SetupError('Multiple car profiles exist; resolve them before setup.')
    state = read_state(path)
    if not matches and state is None: return {**hardware, 'installed': False}
    if not matches or state is None:
        raise SetupError('Car profile and private settings do not match. Existing data was left unchanged.')
    key, profile = matches[0]
    connection = profile.get('connection', {})
    wifi = profile.get('802-11-wireless', {})
    security = profile.get('802-11-wireless-security', {})
    ipv4 = profile.get('ipv4', {})
    if (str(connection.get('type')) != '802-11-wireless' or
            str(connection.get('interface-name')) != INTERFACE or
            str(wifi.get('mode')) != 'ap' or str(wifi.get('band')) != 'a' or
            bytes(wifi.get('ssid', b'')) != state['ssid'].encode('utf-8') or
            str(security.get('key-mgmt')) != 'wpa-psk' or
            str(ipv4.get('method')) != 'shared' or
            not any(str(entry.get('address')) == GATEWAY and int(entry.get('prefix', 0)) == 24
                    for entry in ipv4.get('address-data', [])) or
            bool(connection.get('autoconnect', True)) != state['enabled'] or
            network.profile_secret(key) != state['passphrase']):
        raise SetupError('Car profile and private settings do not match. Existing data was left unchanged.')
    return {**hardware, 'installed': True, 'enabled': state['enabled'], 'ssid': state['ssid']}


def prepare(network, path=STATE, ssid='coscarOS', user=None, running=app_running):
    validate_ssid(ssid)
    current = inspect(network, path)
    if current['installed']: return {**current, 'changed': False}
    if running(): raise SetupError('Quit our app before first-time setup, then restart it afterward.')
    passphrase = secrets.token_urlsafe(24)
    profile_uuid = str(uuid.uuid4())
    profile = build_profile(ssid, passphrase, user or getpass.getuser(), profile_uuid)
    key = network.add(profile)
    try:
        write_state(path, {'enabled': False, 'ssid': ssid, 'passphrase': passphrase,
                          'ipAddress': GATEWAY, 'port': 5277})
    except Exception:
        try: network.delete_owned(key, profile_uuid)
        except Exception: raise SetupError('Settings save failed and profile rollback failed. Check NetworkManager before retrying.') from None
        raise SetupError('Settings save failed; the newly created profile was removed.') from None
    return {**current, 'installed': True, 'enabled': False, 'ssid': ssid, 'changed': True}


@contextmanager
def setup_lock(directory):
    import fcntl
    private_directory(directory)
    descriptor = os.open(directory / 'hotspot-setup.lock', os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally: os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Prepare an inactive profile; never activate Wi-Fi.')
    parser.add_argument('--ssid', default='coscarOS', help='Name for a fresh installation only.')
    args = parser.parse_args()
    if sys.platform != 'linux': parser.error('Run on the Pi as its graphical-login user.')
    if os.geteuid() == 0: parser.error('Run as the graphical-login user, without sudo.')
    try:
        network = NetworkManager()
        if args.apply:
            with setup_lock(STATE.parent): result = prepare(network, ssid=args.ssid)
        else:
            validate_ssid(args.ssid)
            result = inspect(network)
        print(json.dumps(result))
        if result['installed']:
            print('Private settings and protected car profile match. Setup did not activate or restart Wi-Fi.')
        else:
            print('Ready to prepare a protected 5 GHz car profile. Run with --apply to create it inactive.')
        if result.get('changed'):
            print('Start our app, then enable Car Wi-Fi in Android Auto settings. Keep Ethernet or local recovery access during the first activation.')
        return 0
    except SetupError as error:
        print(str(error), file=sys.stderr)
    except Exception:
        # D-Bus error text can contain settings. Never print it or credentials.
        print('Setup failed. Check python3-dbus, NetworkManager and this user’s permission to manage connections.', file=sys.stderr)
    return 1


if __name__ == '__main__': sys.exit(main())
