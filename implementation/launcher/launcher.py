"""Launch our independently owned native car app, backend and Android Auto."""
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    if sys.platform!='linux':sys.exit('Run the native car application on the Raspberry Pi; use Vite for desktop UI development.')
    import fcntl
    directory=Path.home()/'.local/share/hudiy-recreation'
    directory.mkdir(parents=True,exist_ok=True)
    directory.chmod(0o700)
    lock=(directory/'standalone.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:sys.exit('The independent car application is already running.')
    binary=ROOT/'native/build/hudiy-car-runtime'
    if not binary.is_file():sys.exit('Build the native runtime first: cmake -S implementation/native -B implementation/native/build; cmake --build implementation/native/build -j3')
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1',8766))==0:
            sys.exit('Another dashboard service owns port 8766. Quit it before starting the independent application.')
    process=subprocess.Popen([str(binary),str(ROOT)],cwd=ROOT)
    try:return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        try:return process.wait(timeout=8)
        except subprocess.TimeoutExpired:process.kill();return process.wait()
    finally:lock.close()

if __name__=='__main__':sys.exit(main())
