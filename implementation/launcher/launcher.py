"""Launch our independently owned native car app, backend and Android Auto."""
import os
import argparse
from pathlib import Path
import socket
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    if sys.platform!='linux':sys.exit('Run the native car application on the Raspberry Pi; use Vite for desktop UI development.')
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',action='store_true',help='Start the original installed copy for offline maintenance recovery.')
    args=parser.parse_args()
    import fcntl
    directory=Path.home()/'.local/share/hudiy-recreation'
    directory.mkdir(parents=True,exist_ok=True)
    directory.chmod(0o700)
    lock=(directory/'standalone.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:sys.exit('The independent car application is already running.')
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1',8766))==0:
            sys.exit('Another dashboard service owns port 8766. Quit it before starting the independent application.')
    sys.path.insert(0,str(ROOT/'service'))
    from update_supervisor import supervise
    if args.baseline:
        from ota_state import select_rebuilt_baseline
        select_rebuilt_baseline(directory/'software-updates',reason='Baseline selected for maintenance recovery.')
    def launch(release,environment):
        implementation=release/'implementation'
        executable=implementation/'native/build/hudiy-car-runtime'
        if not executable.is_file():raise RuntimeError('Selected native runtime is missing')
        return subprocess.Popen([str(executable),str(implementation)],cwd=implementation,env=environment,start_new_session=True)
    try:return supervise(ROOT.parent,directory/'software-updates',launch)
    finally:lock.close()

if __name__=='__main__':sys.exit(main())
