"""Reversible fixed-path black boot and dedicated LightDM session configuration."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

BEGIN = '# BEGIN HUDIY BLACK BOOT'
END = '# END HUDIY BLACK BOOT'
THEME = 'hudiy-black'
SESSION_WRAPPER = 'usr/lib/coscaros/session.py'
MANIFEST = 'var/lib/hudiy-recreation/black-boot.json'
PLYMOUTH = '''[Plymouth Theme]
Name=coscarOS black startup
Description=Black startup until the car application is ready
ModuleName=script
[script]
ImageDir=/usr/share/plymouth/themes/hudiy-black
ScriptFile=/usr/share/plymouth/themes/hudiy-black/hudiy-black.script
'''
SCRIPT = '''Window.SetBackgroundTopColor (0, 0, 0);
Window.SetBackgroundBottomColor (0, 0, 0);
# Authentication prompts remain visible; normal startup contains no text/logo.
prompt_sprite = Sprite ();
fun prompt (text) {
    image = Image.Text (text, 1, 1, 1);
    prompt_sprite.SetImage (image);
    prompt_sprite.SetX (Window.GetWidth () / 2 - image.GetWidth () / 2);
    prompt_sprite.SetY (Window.GetHeight () / 2 - image.GetHeight () / 2);
    prompt_sprite.SetZ (100);
    prompt_sprite.SetOpacity (1);
}
fun password (text, bullets) { prompt (text + " (password required)"); }
fun question (text, entry) { prompt (text); }
fun normal () { prompt_sprite.SetOpacity (0); }
Plymouth.SetDisplayPasswordFunction (password);
Plymouth.SetDisplayQuestionFunction (question);
Plymouth.SetDisplayNormalFunction (normal);
'''


def quiet_cmdline(text):
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1 or len(text) > 65536: raise ValueError('Expected one bounded kernel command line')
    managed = {'quiet', 'splash', 'logo.nologo', 'loglevel', 'systemd.show_status',
               'rd.systemd.show_status', 'vt.global_cursor_default', 'fullscreen_logo', 'fullscreen_logo_name'}
    words = []
    for word in lines[0].split():
        if word == 'console=tty1': word = 'console=tty3'
        if word.partition('=')[0] not in managed: words.append(word)
    if not any(word.startswith('root=') for word in words): raise ValueError('Kernel root device must be preserved')
    return ' '.join(words + ['quiet', 'splash', 'logo.nologo', 'loglevel=3',
        'systemd.show_status=false', 'rd.systemd.show_status=false', 'vt.global_cursor_default=0']) + '\n'


def firmware_config(text):
    if BEGIN in text or END in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
            raise ValueError('Malformed black boot configuration block')
        before, tail = text.split(BEGIN, 1)
        _, after = tail.split(END, 1)
        text = before.rstrip() + '\n' + after.lstrip('\n')
    return text.rstrip() + '\n\n' + BEGIN + '\n[all]\ndisable_splash=1\n' + END + '\n'


def desktop_quote(value):
    if any(ord(char) < 32 for char in value): raise ValueError('Invalid session launcher path')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'


def lightdm_session(text):
    # lightdm.conf is read after conf.d; update only these keys in Seat:*.
    desired={'autologin-session':'hudiy-recreation','autologin-user-timeout':'0'}
    lines=[];inside=False;found=False;seen=set()
    def append_missing():
        for key,value in desired.items():
            if key not in seen:lines.append(key+'='+value)
    for line in text.splitlines():
        stripped=line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            if inside:append_missing()
            inside=stripped=='[Seat:*]'
            if inside:found=True;seen=set()
        if inside and not stripped.startswith(('#',';')) and '=' in stripped:
            key=stripped.partition('=')[0].strip()
            if key in desired:line=key+'='+desired[key];seen.add(key)
        lines.append(line)
    if inside:append_missing()
    if not found:lines+=['','[Seat:*]',*[key+'='+value for key,value in desired.items()]]
    return '\n'.join(lines)+'\n'


def managed_files(config, cmdline, launcher, select_session=True, lightdm=''):

    # Debian Xsession flattens argv and uses exec $STARTUP: quoted paths break.
    desktop_quote(launcher.as_posix())  # Reject control characters before generating a literal Python path.
    files = {
        SESSION_WRAPPER: 'import runpy\nrunpy.run_path(' + repr(launcher.as_posix()) + ', run_name="__main__")\n',
        'boot/firmware/config.txt': firmware_config(config),
        'boot/firmware/cmdline.txt': quiet_cmdline(cmdline),
        'usr/share/plymouth/themes/hudiy-black/hudiy-black.plymouth': PLYMOUTH,
        'usr/share/plymouth/themes/hudiy-black/hudiy-black.script': SCRIPT,
        'usr/share/wayland-sessions/hudiy-recreation.desktop':
            '[Desktop Entry]\nName=coscarOS\nComment=Black startup and independent car dashboard\n'
            'Type=Application\nDesktopNames=labwc\nExec=/usr/bin/python3 /' + SESSION_WRAPPER + '\n',
    }
    if select_session:
        files['etc/lightdm/lightdm.conf']=lightdm_session(lightdm)
        files['etc/lightdm/lightdm.conf.d/99-hudiy-recreation-session.conf'] = (
            '# coscarOS dedicated session; login authentication is configured separately.\n'
            '[Seat:*]\nautologin-session=hudiy-recreation\n')
    return files


def checked_path(root, name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts: raise ValueError('Unsafe system configuration path')
    path = root / relative
    for item in (path, *path.parents):
        if item == root.parent: break
        if item.is_symlink(): raise ValueError('Refusing symlinked startup configuration')
    return path


def atomic(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.hudiy-boot-')
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            os.chmod(temporary, mode); stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


class BlackBoot:
    def __init__(self, root=Path('/'), run=None):
        self.root = Path(root)
        self.run = run or (lambda arguments: subprocess.check_output(arguments, text=True, timeout=180).strip())
        self.manifest = checked_path(self.root, MANIFEST)

    def apply(self, launcher, select_session=True):
        config = checked_path(self.root, 'boot/firmware/config.txt')
        cmdline = checked_path(self.root, 'boot/firmware/cmdline.txt')
        lightdm=checked_path(self.root,'etc/lightdm/lightdm.conf')
        files = managed_files(config.read_text(), cmdline.read_text(), launcher, select_session, lightdm.read_text() if lightdm.exists() else '')
        if self.manifest.exists():
            state=self._load()
            self._verify(state)
            migrating_wrapper = set(files) == set(state['files']) | {SESSION_WRAPPER} and SESSION_WRAPPER not in state['files']
            if migrating_wrapper and checked_path(self.root, SESSION_WRAPPER).exists():
                raise ValueError('Session wrapper already exists outside the managed installation')
            if set(files)!=set(state['files']) and not migrating_wrapper:
                raise ValueError('Black boot target changed; restore the saved setup before applying a different target')
            previous = {name: checked_path(self.root, name).read_bytes() if checked_path(self.root, name).exists() else None for name in files}
            replacements = {
                'usr/share/plymouth/themes/hudiy-black/hudiy-black.plymouth': (b'Name=Hudiy black startup', b'Name=coscarOS black startup'),
                'usr/share/wayland-sessions/hudiy-recreation.desktop': (b'Name=Hudiy recreation', b'Name=coscarOS'),
                'etc/lightdm/lightdm.conf.d/99-hudiy-recreation-session.conf': (b'# Hudiy dedicated session;', b'# coscarOS dedicated session;'),
            }
            for name, content in files.items():
                allowed = previous[name]
                if migrating_wrapper and name == SESSION_WRAPPER: continue
                if name in replacements: allowed = allowed.replace(*replacements[name])
                if migrating_wrapper and name == 'usr/share/wayland-sessions/hudiy-recreation.desktop':
                    allowed = allowed.replace(('Exec=/usr/bin/python3 ' + desktop_quote(launcher.as_posix()) + '\n').encode(), ('Exec=/usr/bin/python3 /' + SESSION_WRAPPER + '\n').encode())
                if allowed != content.encode():
                    raise ValueError('Black boot target changed; restore the saved setup before applying a different target')
            if all(previous[name] == content.encode() for name, content in files.items()): return False
            if self.run(['plymouth-set-default-theme']) != THEME:
                raise ValueError('The boot theme was changed after installation; preserve it before upgrading')
            manifest_before = self.manifest.read_bytes()
            try:
                for name, content in files.items():
                    atomic(checked_path(self.root, name), content.encode())
                    if name not in state['files']:
                        state['files'][name] = {'before': None, 'mode': 0o644}
                    state['files'][name]['installed'] = hashlib.sha256(content.encode()).hexdigest()
                self.run(['plymouth-set-default-theme', '-R', THEME])
                atomic(self.manifest, json.dumps(state).encode(), 0o600)
            except Exception:
                for name, data in previous.items():
                    path = checked_path(self.root, name)
                    if data is None:
                        if path.exists(): path.unlink()
                    else: atomic(path, data)
                atomic(self.manifest, manifest_before, 0o600)
                self.run(['plymouth-set-default-theme', '-R', THEME])
                raise
            return True
        previous_theme = self.run(['plymouth-set-default-theme'])
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', previous_theme): raise ValueError('Unknown previous Plymouth theme')
        state = {'theme': previous_theme, 'files': {}}
        for name, content in files.items():
            path = checked_path(self.root, name)
            original = path.read_bytes() if path.exists() else None
            if original is not None and len(original) > 262144: raise ValueError('Startup configuration exceeds limit')
            data = content.encode()
            state['files'][name] = {'before': base64.b64encode(original).decode() if original is not None else None,
                'mode': (path.stat().st_mode & 0o777) if path.exists() else 0o644,
                'installed': hashlib.sha256(data).hexdigest()}
        atomic(self.manifest, json.dumps(state).encode(), 0o600)
        try:
            for name, content in files.items(): atomic(checked_path(self.root, name), content.encode())
            self.run(['plymouth-set-default-theme', '-R', THEME])
        except Exception:
            self._restore(state, verify=False)
            raise
        return True

    def _load(self):
        if self.manifest.stat().st_size > 1048576: raise ValueError('Backup manifest exceeds limit')
        state = json.loads(self.manifest.read_text())
        allowed = set(managed_files('[all]\n', 'root=fixture\n', Path('/fixture')))
        if (not isinstance(state, dict) or set(state) != {'theme', 'files'} or
            not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', state.get('theme', '')) or
            not isinstance(state['files'], dict) or not set(state['files']) <= allowed):
            raise ValueError('Invalid black boot backup manifest')
        for name, saved in state['files'].items():
            checked_path(self.root, name)
            if not isinstance(saved, dict) or set(saved) != {'before', 'mode', 'installed'}:
                raise ValueError('Invalid startup file backup')
            if not isinstance(saved['installed'], str) or not re.fullmatch(r'[0-9a-f]{64}', saved['installed']):
                raise ValueError('Invalid startup file digest')
            if type(saved['mode']) is not int or saved['mode'] & ~0o777: raise ValueError('Invalid startup backup mode')
            if saved['before'] is not None:
                if not isinstance(saved['before'], str): raise ValueError('Invalid startup backup data')
                base64.b64decode(saved['before'], validate=True)
        return state

    def _verify(self, state):
        for name, saved in state['files'].items():
            path = checked_path(self.root, name)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != saved['installed']:
                raise ValueError('Startup file was changed after installation; preserve it before restoring: ' + name)

    def _restore(self, state, verify=True):
        if verify:
            self._verify(state)
            if self.run(['plymouth-set-default-theme']) != THEME:
                raise ValueError('The boot theme was changed after installation; preserve it before restoring')
        # Restore the selected theme while our theme files still exist.
        self.run(['plymouth-set-default-theme', '-R', state['theme']])
        for name, saved in state['files'].items():
            path = checked_path(self.root, name)
            if saved['before'] is None:
                if path.exists(): path.unlink()
            else: atomic(path, base64.b64decode(saved['before']), saved['mode'])
        self.manifest.replace(self.manifest.with_name('black-boot.restored.json'))

    def restore(self):
        if not self.manifest.exists(): return False
        self._restore(self._load())
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--restore', action='store_true')
    parser.add_argument('--no-session-selection', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'linux': parser.error('Run on Raspberry Pi OS')
    launcher = Path(__file__).resolve().with_name('session.py')
    print('Black Plymouth/quiet boot and dedicated panel-free car session; backups retained. No reboot or display-manager restart.')
    if not (args.apply or args.restore): return
    if os.geteuid() != 0: parser.error('Apply/restore requires sudo; inspection does not')
    import pwd
    if os.environ.get('SUDO_USER'):
        account = pwd.getpwnam(os.environ['SUDO_USER'])
        if account.pw_uid < 1000: parser.error('Target the ordinary desktop user')
    manager = BlackBoot()
    if args.restore: manager.restore()
    else: manager.apply(launcher, not args.no_session_selection)


if __name__ == '__main__': main()
