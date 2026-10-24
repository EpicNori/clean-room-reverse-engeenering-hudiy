"""Guided fresh Raspberry Pi OS Desktop setup for our independent application."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = (
    'build-essential cmake pkg-config git curl ca-certificates xz-utils '
    'qt6-base-dev qt6-multimedia-dev qt6-webengine-dev qt6-connectivity-dev '
    'libprotobuf-dev protobuf-compiler libssl-dev libusb-1.0-0-dev '
    'libavcodec-dev libavutil-dev libswscale-dev python3-serial python3-dbus python3-gi '
    'bluez bluez-obexd ofono network-manager dnsmasq-base '
    'pipewire pipewire-pulse wireplumber libspa-0.2-bluetooth dbus-user-session '
    'android-sdk-platform-tools-common swaybg plymouth plymouth-themes'
).split()
NODE_RELEASE = 'https://nodejs.org/dist/latest-v22.x/'
MAX_ARCHIVE = 80 * 1024 * 1024


class InstallError(ValueError): pass


def run(arguments, **kwargs):
    print('+ ' + ' '.join(map(str, arguments)), flush=True)
    return subprocess.run(list(map(str, arguments)), check=True, **kwargs)


def os_release(text):
    result = {}
    for line in text.splitlines():
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1); result[key] = value.strip().strip('"')
    return result


def validate_platform(release, architecture, model, desktop, uid):
    if uid == 0: raise InstallError('Run as the desktop user, without sudo.')
    if architecture != 'aarch64' or 'Raspberry Pi' not in model:
        raise InstallError('Use a Raspberry Pi with a 64-bit OS.')
    if release.get('VERSION_CODENAME') not in ('bookworm', 'trixie'):
        raise InstallError('Use Raspberry Pi OS Bookworm or Trixie.')
    if not desktop: raise InstallError('Use Raspberry Pi OS with Desktop/labwc; OS Lite is not supported.')


def jobs_for_memory(memory_kib):
    # Qt/protocol compilation is memory intensive on small boards.
    return 1 if memory_kib < 3 * 1024 * 1024 else 2


def choose_node(manifest):
    matches = []
    for line in manifest.splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})\s+(node-v22\.\d+\.\d+-linux-arm64\.tar\.xz)', line)
        if match: matches.append((match[2], match[1]))
    if len(matches) != 1: raise InstallError('Official Node checksum manifest did not identify one ARM64 release.')
    return matches[0]


def verify_archive(path, expected):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
    if digest.hexdigest() != expected: raise InstallError('Node archive checksum mismatch; nothing was extracted.')


def extract_node(archive, target, prefix):
    # Bookworm's Python may not provide tarfile.data_filter. Explicitly validate
    # the entire trusted official archive before extracting any file.
    with tarfile.open(archive, 'r:xz') as source:
        members = source.getmembers()
        if len(members) > 15000 or sum(m.size for m in members) > 500 * 1024 * 1024:
            raise InstallError('Node archive exceeds extraction limits.')
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or not name.parts or name.parts[0] != prefix or '..' in name.parts:
                raise InstallError('Node archive has an unsafe path.')
            if not (member.isfile() or member.isdir() or member.issym()):
                raise InstallError('Node archive has an unsupported entry.')
            if member.issym():
                link = PurePosixPath(member.linkname)
                if link.is_absolute(): raise InstallError('Node archive has an unsafe link.')
                destination = (target / member.name).parent.joinpath(*link.parts).resolve()
                if not destination.is_relative_to((target / prefix).resolve()):
                    raise InstallError('Node archive link escapes its release directory.')
            member.mode &= 0o777  # Never restore setuid/setgid bits or archive ownership.
        if len({m.name for m in members}) != len(members):
            raise InstallError('Node archive repeats a path.')
        # Reject paths traversing an archive symlink, even when the link itself is
        # inside the root, so later members cannot write through it.
        links = {PurePosixPath(m.name) for m in members if m.issym()}
        if any(any(parent in links for parent in PurePosixPath(m.name).parents) for m in members):
            raise InstallError('Node archive writes through a symlink.')
        if (target / prefix).exists(): raise InstallError('Extraction requires a fresh release directory.')
        # Files precede links. No extraction write can follow an archive link,
        # independent of Python's version-specific tarfile filtering defaults.
        for member in members:
            path = target / member.name
            if member.isdir(): path.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                path.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as data, path.open('xb') as output:
                    shutil.copyfileobj(data, output)
                path.chmod(member.mode)
        for member in members:
            if member.issym():
                path = target / member.name; path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(member.linkname)
        for member in members:
            if member.issym():
                try: resolved = (target / member.name).resolve()
                except RuntimeError: raise InstallError('Node archive has a cyclic link.') from None
                if not resolved.is_relative_to((target / prefix).resolve()):
                    raise InstallError('Node archive link chain escapes its release directory.')


def node_runtime():
    directory = Path.home() / '.local/share/hudiy-recreation/node'
    if directory.is_symlink(): raise InstallError('Managed Node directory cannot be a symlink.')
    directory.mkdir(parents=True, exist_ok=True); directory.chmod(0o700)
    with urllib.request.urlopen(NODE_RELEASE + 'SHASUMS256.txt', timeout=30) as response:
        manifest = response.read(65537)
    if len(manifest) > 65536: raise InstallError('Node manifest exceeds size limit.')
    filename, checksum = choose_node(manifest.decode('ascii'))
    prefix = filename.removesuffix('.tar.xz'); installed = directory / prefix
    if installed.is_symlink(): raise InstallError('Managed Node release cannot be a symlink.')
    if not (installed / 'bin/node').is_file():
        with tempfile.TemporaryDirectory(prefix='.node-', dir=directory) as temporary:
            staging = Path(temporary); archive = staging / filename
            with urllib.request.urlopen(NODE_RELEASE + filename, timeout=60) as response, archive.open('wb') as stream:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_ARCHIVE: raise InstallError('Node download exceeds size limit.')
                    stream.write(chunk)
            verify_archive(archive, checksum)
            extract_node(archive, staging, prefix)
            if installed.exists(): raise InstallError('Incomplete managed Node release already exists; inspect it before retrying.')
            (staging / prefix).rename(installed)
    # Every build explicitly uses this user-private runtime; system Node stays unchanged.
    environment = dict(os.environ, PATH=str(installed / 'bin') + os.pathsep + os.environ.get('PATH', ''))
    run([installed / 'bin/node', '--version'])
    return environment


def write_user_file(path, content):
    if path.is_symlink() or path.parent.is_symlink(): raise InstallError('Configuration cannot be a symlink.')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == content: return
    if path.exists():
        import datetime
        backup = path.with_name(path.name + '.backup-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
        shutil.copy2(path, backup)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.hudiy-')
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def audio_configuration(version):
    match = re.search(r'(?:WirePlumber|libwireplumber)\s+(0\.[45])\.', version, re.I)
    if not match: raise InstallError('Supported WirePlumber configuration versions are 0.4 and 0.5.')
    if match[1] == '0.4':
        return ('bluetooth.lua.d/90-hudiy-recreation.lua',
                '-- Our HFP call control uses oFono.\nbluez_monitor.properties["bluez5.hfphsp-backend"] = "ofono"\n')
    return ('wireplumber.conf.d/90-hudiy-recreation.conf',
            '# Our HFP call control uses oFono.\nmonitor.bluez.properties = {\n  bluez5.hfphsp-backend = "ofono"\n}\n')


def preflight():
    if sys.platform != 'linux': raise InstallError('Run this installer on Raspberry Pi OS.')
    if subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip() != 'arm64':
        raise InstallError('Install the 64-bit arm64 OS image; a 64-bit kernel alone is insufficient.')
    release = os_release(Path('/etc/os-release').read_text())
    model_path = Path('/proc/device-tree/model')
    validate_platform(release, platform.machine(), model_path.read_text() if model_path.exists() else '',
                      Path('/etc/xdg/labwc/rc.xml').is_file() and shutil.which('labwc'), os.geteuid())
    if shutil.disk_usage(ROOT).free < 4 * 1024 ** 3:
        raise InstallError('At least 4 GiB free disk space is required for dependencies and the build.')
    from provision_hotspot import app_running
    return release, app_running()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Print/check prerequisites without changing the system.')
    parser.add_argument('--yes', action='store_true', help='Accept the printed installation plan.')
    parser.add_argument('--skip-black-boot', action='store_true', help='Keep the existing OS boot theme and graphical session selection.')
    parser.add_argument('--no-autologin', action='store_true', help='Keep OS login authentication unchanged.')
    parser.add_argument('--skip-hotspot', action='store_true', help='Install without preparing wireless projection.')
    args = parser.parse_args()
    try:
        release, running = preflight()
        print('Hudiy recreation — independent Raspberry Pi car software')
        print('OS:', release['VERSION_CODENAME'], '| source:', ROOT)
        print('Black startup: quiet boot and a panel-free car session (unless --skip-black-boot).')
        print('Plan: install OS dependencies; verified user-private Node 22; build/test frontend and native receiver;')
        print('      enable Bluetooth/oFono; configure user audio/device access; back up and select labwc startup;')
        print('      ' + ('keep login settings' if args.no_autologin else 'enable desktop autologin for this user') + '; ' +
              ('skip car hotspot' if args.skip_hotspot else 'prepare protected car hotspot, without activating it') + '.')
        print('The app stays an ordinary-user process. No automatic reboot or Wi-Fi activation.')
        if args.check:
            print(json.dumps({'platformSupported': True, 'appRunning': running, 'packages': PACKAGES,
                              'autologin': not args.no_autologin, 'prepareHotspot': not args.skip_hotspot}))
            return 0
        if running: raise InstallError('Quit the running car app before installation; --check can run while it is open.')
        if not args.yes:
            with open('/dev/tty', 'r+') as terminal:
                terminal.write('Apply this installation plan? [y/N] '); terminal.flush()
                if terminal.readline().strip().lower() not in ('y', 'yes'):
                    print('Installation cancelled.'); return 1
        import fcntl
        state = Path.home() / '.local/share/hudiy-recreation'
        from provision_hotspot import private_directory
        private_directory(state)
        descriptor = os.open(state / 'install.lock', os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run(['sudo', '-v'])
            run(['sudo', 'apt-get', 'update'])
            run(['sudo', 'apt-get', 'install', '-y', *PACKAGES])
            environment = node_runtime()
            dashboard = ROOT / 'implementation/dashboard'
            run(['npm', 'ci'], cwd=dashboard, env=environment)
            run(['npm', 'run', 'build'], cwd=dashboard, env=environment)
            tests = sorted(str(p.relative_to(dashboard)) for p in (dashboard / 'tests').glob('*.test.mjs'))
            run(['node', '--test', *tests], cwd=dashboard, env=environment)
            run(['/usr/bin/python3', '-m', 'unittest', 'discover', '-s', 'implementation/service', '-p', 'test_*.py'], cwd=ROOT)
            native = ROOT / 'implementation/native'; build = native / 'build'
            memory = int(re.search(r'MemTotal:\s+(\d+)', Path('/proc/meminfo').read_text())[1])
            run(['cmake', '-S', native, '-B', build, '-DCMAKE_BUILD_TYPE=Release'])
            run(['cmake', '--build', build, '--parallel', jobs_for_memory(memory)])
            run(['ctest', '--test-dir', build, '--output-on-failure', '--no-tests=error'])
            version = subprocess.check_output(['wireplumber', '--version'], text=True)
            relative, content = audio_configuration(version)
            write_user_file(Path.home() / '.config/wireplumber' / relative, content)
            run([sys.executable, ROOT / 'implementation/launcher/install_autostart.py'])
            import pwd
            user = pwd.getpwuid(os.geteuid()).pw_name
            system = [sys.executable, ROOT / 'implementation/launcher/install_pi_system.py', '--user', user]
            if args.no_autologin: system.append('--no-autologin')
            if args.skip_black_boot: system.append('--skip-black-boot')
            run(['sudo', *system])
            sys.path.insert(0,str(ROOT/'implementation/service'))
            from ota_state import select_rebuilt_baseline
            select_rebuilt_baseline(state/'software-updates')
            run([sys.executable, ROOT / 'implementation/launcher/install_autostart.py', '--apply'])
            hotspot_error = None
            if not args.skip_hotspot:
                # Soft failure retains a usable USB/dashboard install on boards
                # without 5 GHz, or with an existing conflicting car profile.
                try:
                    from provision_hotspot import NetworkManager, prepare, setup_lock, STATE
                    with setup_lock(STATE.parent): print(json.dumps(prepare(NetworkManager())))
                except Exception:
                    hotspot_error = 'Car hotspot was not prepared. Inspect it with provision_hotspot.py; USB remains available.'
            print('\nApplication installed. Reboot when convenient to apply groups, audio configuration and startup.')
            print('First start: pair your phone and powered ELM327 in Connections. Enable Car Wi-Fi when ready.')
            print('Our normal Quit returns to the desktop. See docs/INSTALL.md for recovery and current hardware limits.')
            if hotspot_error: print(hotspot_error)
            print('Unattended reboot, fresh phone services and audible car audio still require hardware verification.')
        return 0
    except (InstallError, OSError, subprocess.SubprocessError, ValueError) as error:
        print('Installation stopped:', str(error), file=sys.stderr)
        print('Completed package/build steps are retained; no automatic reboot. Correct the failure before retrying.', file=sys.stderr)
        return 1


if __name__ == '__main__': sys.exit(main())
