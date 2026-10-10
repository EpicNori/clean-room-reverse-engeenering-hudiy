"""Host the recreation in licensed Hudiy, with a persistent taskbar overlay.

Changes only documented JSON configuration, preserving originals in backups.
Render dimensions are derived from the current screen at every startup.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'service'))
from projection import PREFERENCES, HOST_STATE, read_options, save_json
ACTION = 'hudiy_recreation'
OVERLAY = 'hudiy_recreation_taskbar'


def configure(config, width, height, apply=False, taskbar_visible=True):
    if width < 320 or height < 240:
        raise ValueError('Screen too small for Android Auto')
    # The same 11.25% baseline as the recreation taskbar (81/720).
    bar = max(56, round(height * .1125))
    content = height - bar
    changes = {}
    for name in ('main_configuration.json', 'applications.json', 'overlays.json'):
        path = config / name
        changes[name] = json.loads(path.read_text()) if path.exists() else {}
    main = changes['main_configuration.json']
    main.setdefault('application', {}).update(defaultAction=ACTION, useWebCache=False)
    # Reserve exactly the content area; native bottom bar is covered by our overlay.
    # Hudiy 1.24 uses a bar scale of 73 for the observed 81/720 baseline.
    # This keeps the native application web view aligned with our overlay.
    main.setdefault('appearance', {})['bottomBarHeight'] = 73
    android = main.setdefault('androidAuto', {})
    video_height = {'480p': 480, '720p': 720, '1080p': 1080}.get(android.get('resolution', '720p'))
    if video_height is None:
        raise ValueError('Projection host supports 480p, 720p or 1080p streams')
    android.update(width=width, height=content if taskbar_visible else height, x=0, y=0,
                   heightMargin=round(video_height * bar / height / 2) * 2 if taskbar_visible else 0,
                   autostart=True)
    apps = changes['applications.json'].setdefault('applications', [])
    apps[:] = [a for a in apps if a.get('action') != ACTION]
    apps.append({'action': ACTION, 'url': 'http://127.0.0.1:8766/?host=content',
                 'allowBackground': True, 'controlAudioFocus': True,
                 'audioStreamCategory': 'ENTERTAINMENT', 'zoomFactor': 1})
    overlays = changes['overlays.json'].setdefault('overlays', [])
    overlays[:] = [a for a in overlays if a.get('identifier') != OVERLAY]
    overlays.append({'identifier': OVERLAY, 'width': width, 'height': bar,
                     'x': 0, 'y': content, 'visibility': 'ALWAYS' if taskbar_visible else 'NATIVE_UI_ONLY',
                     'url': 'http://127.0.0.1:8766/?host=taskbar',
                     'controlAudioFocus': False, 'audioStreamCategory': 'NONE',
                     'visibleOnActions': [], 'staticPosition': True})
    if apply:
        stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
        for name, data in changes.items():
            path = config / name
            if path.exists() and not path.with_name(name + '.recreation-original').exists():
                path.with_name(name + '.recreation-original').write_bytes(path.read_bytes())
            # Atomic replacement; do not leave partial config if startup is interrupted.
            tmp = path.with_name(name + '.recreation-' + stamp)
            tmp.write_text(json.dumps(data, indent=4) + '\n', encoding='utf-8')
            tmp.replace(path)
    return {'width': width, 'height': height, 'taskbar': bar,
            'projection': content if taskbar_visible else height,
            'taskbarVisible': taskbar_visible}


def status():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766/api/status', timeout=2) as r:
            return json.load(r)
    except (OSError, ValueError):
        return None


def exit_state(data):
    """Wait for the runtime to disconnect before ending the owning host."""
    projection = (data or {}).get('projection', {})
    if not projection.get('exitRequested'):
        return 'running'
    return 'waiting' if projection.get('available') else 'stopped'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--configure-only', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Run the projection host on the Raspberry Pi')
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    size = app.primaryScreen().size()
    home = Path.home() / '.hudiy/share'
    if not (home / 'hudiy_run.sh').is_file():
        parser.error('Installed licensed Hudiy runtime is required')
    if status():
        parser.error('A dashboard service is already running; stop it before starting the projection host')
    options = read_options()
    geometry = configure(home / 'config', size.width(), size.height(), args.apply, options['taskbarVisible'])
    print('Projection host layout:', geometry, flush=True)
    if not args.apply or args.configure_only:
        return
    save_json(HOST_STATE, {'taskbarVisible': options['taskbarVisible']})
    env = dict(os.environ, HUDIY_PROJECTION_HOST='1')
    service = subprocess.Popen([sys.executable, str(ROOT / 'service/server.py')], env=env)
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for _ in range(50):
            if status():
                break
            if service.poll() is not None:
                raise RuntimeError('Dashboard service failed to start')
            time.sleep(.1)
        else:
            raise RuntimeError('Dashboard service did not become ready')
        def request(payload):
            req = urllib.request.Request('http://127.0.0.1:8766/api/action',
                data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=3) as response:
                return json.load(response)

        while not stopped and service.poll() is None:
            closing = exit_state(status())
            if closing == 'stopped':
                stopped = True
                break
            if closing == 'waiting':
                time.sleep(.1)
                continue
            subprocess.run([str(home / 'hudiy_run.sh')], check=True, env=env)
            for _ in range(150):
                data = status()
                closing = exit_state(data)
                if closing == 'stopped':
                    stopped = True
                    break
                if closing == 'waiting':
                    time.sleep(.2)
                    continue
                if data and data.get('projection', {}).get('available'):
                    if not data['projection']['visible']:
                        request({'action': 'projection', 'operation': 'dashboard'})
                    break
                if stopped:
                    break
                time.sleep(.2)
            else:
                raise RuntimeError('Hudiy API did not start')
            print('Projection runtime ready; layout:', geometry, flush=True)
            while not stopped and service.poll() is None:
                closing = exit_state(status())
                if closing == 'stopped':
                    stopped = True
                    break
                if closing == 'waiting':
                    time.sleep(.1)
                    continue
                current = read_options()
                if current['restartGeneration'] != options['restartGeneration']:
                    request({'action': 'projection-host-stop'})
                    for _ in range(100):
                        data = status()
                        if data and not data['projection']['available']:
                            break
                        time.sleep(.1)
                    else:
                        raise RuntimeError('Hudiy did not stop; projection layout was not applied')
                    options = read_options()
                    geometry = configure(home / 'config', size.width(), size.height(), True, options['taskbarVisible'])
                    save_json(HOST_STATE, {'taskbarVisible': options['taskbarVisible']})
                    break
                time.sleep(.5)
    finally:
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()


if __name__ == '__main__':
    main()
