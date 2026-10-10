"""Reset only a uniquely identified Android USB accessory, without root."""
import os
from pathlib import Path
import stat
import threading
import time


class USBRecovery:
    def __init__(self, sysfs=Path('/sys/bus/usb/devices')):
        self.sysfs = sysfs
        self.lock = threading.Lock()
        self.last_reset = -100.0

    def accessory(self):
        devices = []
        if not self.sysfs.exists():
            return None
        for entry in self.sysfs.iterdir():
            try:
                if (entry / 'idVendor').read_text().strip().lower() != '18d1':
                    continue
                if (entry / 'idProduct').read_text().strip().lower() not in {'2d00', '2d01', '2d04', '2d05'}:
                    continue
                bus, device = int((entry / 'busnum').read_text()), int((entry / 'devnum').read_text())
                if 1 <= bus <= 999 and 1 <= device <= 127:
                    devices.append((bus, device))
            except (OSError, ValueError):
                continue
        if len(devices) > 1:
            raise ConnectionError('Several Android USB accessories found; connect one phone')
        return devices[0] if devices else None

    def reset(self):
        import fcntl
        with self.lock:
            device = self.accessory()
            if device is None:
                return False
            if time.monotonic() - self.last_reset < 15:
                return False
            bus, number = device
            path = f'/dev/bus/usb/{bus:03d}/{number:03d}'
            fd = os.open(path, os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0))
            try:
                info = os.fstat(fd)
                if (not stat.S_ISCHR(info.st_mode) or os.major(info.st_rdev) != 189 or
                        os.minor(info.st_rdev) != (bus - 1) * 128 + number - 1 or
                        self.accessory() != device):
                    raise ConnectionError('Android USB device changed; try again')
                fcntl.ioctl(fd, 0x5514, 0)  # USBDEVFS_RESET
                self.last_reset = time.monotonic()
            finally:
                os.close(fd)
            # Let the device re-enumerate before asking Hudiy to connect.
            time.sleep(.8)
            return True
