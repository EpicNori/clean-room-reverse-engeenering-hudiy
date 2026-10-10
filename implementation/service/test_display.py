from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from display import DisplayBrightness


class DisplayTests(unittest.TestCase):
    def fixture(self,folder):
        root=Path(folder)/'backlight'
        device=root/'panel';device.mkdir(parents=True)
        (device/'brightness').write_text('31')
        (device/'max_brightness').write_text('31')
        return DisplayBrightness(True,root,Path(folder)/'saved.json'),device

    @patch('display.sys.platform','linux')
    def test_physical_write_bounds_and_saved_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            display,device=self.fixture(folder)
            self.assertEqual(display.snapshot()['brightness'],100)
            for value in (0,4,101,True,'50',50.5):
                with self.assertRaises(ValueError):display.set(value)
            self.assertEqual((device/'brightness').read_text(),'31')
            result=display.set(50)
            self.assertEqual((device/'brightness').read_text(),'16')
            self.assertEqual(result['brightness'],52)
            (device/'brightness').write_text('31')
            display.start()
            self.assertEqual((device/'brightness').read_text(),'16')
            display.set(5)
            self.assertGreater(int((device/'brightness').read_text()),0)

    @patch('display.sys.platform','linux')
    def test_unavailable_or_ambiguous_devices_never_write(self):
        with tempfile.TemporaryDirectory() as folder:
            display,device=self.fixture(folder)
            display.enabled=False
            self.assertFalse(display.snapshot()['available'])
            with self.assertRaises(ConnectionError):display.set(50)
            display.enabled=True
            other=device.parent/'other';other.mkdir()
            (other/'brightness').write_text('20');(other/'max_brightness').write_text('31')
            self.assertFalse(display.snapshot()['available'])
            with self.assertRaises(ConnectionError):display.set(50)
            self.assertEqual((device/'brightness').read_text(),'31')
