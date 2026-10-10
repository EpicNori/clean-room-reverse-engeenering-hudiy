"""Fixed privileged OS steps; invoked by the normal-user Pi installer."""
import argparse
import datetime
import grp
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import tempfile

RULES = Path('/etc/udev/rules.d/70-hudiy-recreation-backlight.rules')
BACKLIGHT_RULE = ('# Hudiy recreation: allow the video group to change panel brightness.\n'
                  'ACTION=="add", SUBSYSTEM=="backlight", RUN+="/bin/chgrp video /sys%p/brightness", RUN+="/bin/chmod g+w /sys%p/brightness"\n')


def backup(path):
    if path.is_symlink(): raise ValueError('Refusing a symlinked system configuration: ' + str(path))
    if path.exists():
        stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
        shutil.copy2(path, path.with_name(path.name + '.backup-' + stamp))


def install_rule():
    if RULES.is_symlink(): raise ValueError('Backlight rule cannot be a symlink.')
    if RULES.exists() and RULES.read_text() == BACKLIGHT_RULE: return
    backup(RULES); RULES.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=RULES.parent, prefix='.hudiy-')
    try:
        with os.fdopen(descriptor, 'w') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(BACKLIGHT_RULE); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, RULES)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def system_commands(user, autologin):
    commands = [['usermod', '-a', '-G', 'dialout,video,plugdev', user],
                ['systemctl', 'enable', '--now', 'bluetooth.service', 'ofono.service'],
                ['udevadm', 'control', '--reload-rules']]
    if autologin: commands.append(['raspi-config', 'nonint', 'do_boot_behaviour', 'B4'])
    return commands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', required=True)
    parser.add_argument('--no-autologin', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0: parser.error('This helper requires sudo from the ordinary-user installer.')
    account = pwd.getpwnam(args.user)
    if account.pw_uid < 1000 or os.environ.get('SUDO_USER') != args.user:
        parser.error('System setup must target the ordinary user who invoked sudo.')
    for group in ('dialout', 'video', 'plugdev'):
        try: grp.getgrnam(group)
        except KeyError: subprocess.run(['groupadd', '--system', group], check=True)
    install_rule()
    if not args.no_autologin:
        for path in (Path('/etc/lightdm/lightdm.conf'), Path('/etc/systemd/system/getty@tty1.service.d/autologin.conf')):
            backup(path)
    for command in system_commands(args.user, not args.no_autologin):
        subprocess.run(command, check=True)
    video_gid = grp.getgrnam('video').gr_gid
    for device in Path('/sys/class/backlight').iterdir():
        brightness = device / 'brightness'
        if brightness.is_file():
            os.chown(brightness, -1, video_gid)
            os.chmod(brightness, stat.S_IMODE(brightness.stat().st_mode) | stat.S_IWGRP)
    # Do not restart the display manager, the user's audio stack or active Wi-Fi.


if __name__ == '__main__': main()
