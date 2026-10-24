"""Select our panel-free labwc session, or the ordinary desktop when opted out."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def session_command(home, options, environment):
    config = Path(home) / '.config/hudiy-recreation/labwc'
    if options.get('blackStartup', True):
        if not (config / 'autostart').is_file() or not (config / 'rc.xml').is_file():
            raise RuntimeError('Black startup session is not prepared; run install_autostart.py --apply first')
        command = ['/usr/bin/labwc', '--config-dir', str(config)]
    else:
        command = ['/usr/bin/labwc', '-m']
    if not environment.get('DBUS_SESSION_BUS_ADDRESS'):
        command = ['/usr/bin/dbus-run-session', '--', *command]
    return command


def main():
    if sys.platform != 'linux': raise RuntimeError('The graphical startup session requires Raspberry Pi OS')
    sys.path.insert(0, str(ROOT / 'service'))
    from runtime_support import read_options
    command = session_command(Path.home(), read_options(), os.environ)
    os.execv(command[0], command)


if __name__ == '__main__': main()
