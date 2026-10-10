import os
from pathlib import Path
import stat
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from phonebook import Phonebook, parse_vcards, MAX_BYTES
from usb_recovery import USBRecovery


class PhoneTests(unittest.TestCase):
    def test_missing_pbap_session_recovers_while_bluetooth_stays_connected(self):
        book = Phonebook()
        book.session, book.address = '/owned/session1', 'paired-phone'
        book.client = Mock()
        book.client.CreateSession.return_value = '/owned/session2'
        book.data['views']['contacts']['entries'] = [{'name': 'Private', 'numbers': ['123']}]
        manager = Mock()
        # A different client's valid session must not mask our missing session.
        manager.GetManagedObjects.return_value = {'/foreign/session': {'org.bluez.obex.PhonebookAccess1': {}}}
        dbus = SimpleNamespace(Interface=lambda obj, interface: manager, Dictionary=lambda value, **kw: value)
        self.assertTrue(book._ensure_session(Mock(), dbus, 'paired-phone'))
        book.client.RemoveSession.assert_called_once_with('/owned/session1', timeout=3)
        book.client.CreateSession.assert_called_once_with('paired-phone', {'Target': 'pbap'}, timeout=12)
        self.assertEqual(book.session, '/owned/session2')
        self.assertEqual(book.snapshot()['views']['contacts']['entries'], [])
        manager.GetManagedObjects.return_value = {'/owned/session2': {'org.bluez.obex.PhonebookAccess1': {}}}
        self.assertFalse(book._ensure_session(Mock(), dbus, 'paired-phone'))
        self.assertEqual(book.client.CreateSession.call_count, 1)


    def test_fast_phonebook_transfer_uses_completion_signal_before_object_removal(self):
        book = Phonebook()
        book.session = '/session1'
        book.context = SimpleNamespace(pending=lambda: False)
        bus = Mock()
        handler = None
        match = Mock()
        def subscribe(callback, **kwargs):
            nonlocal handler
            handler = callback
            return match
        bus.add_signal_receiver.side_effect = subscribe
        native = Mock()
        def pull(target, filters, **kwargs):
            Path(target).write_bytes(b'BEGIN:VCARD\nFN:Test\nTEL:123\nEND:VCARD\n')
            handler('org.bluez.obex.Transfer1', {'Status': 'complete'}, [], path='/session1/transfer1')
            return '/session1/transfer1', {'Filename': target}
        native.PullAll.side_effect = pull
        properties = Mock()
        properties.GetAll.side_effect = RuntimeError('Object already removed')
        dbus = SimpleNamespace(Interface=lambda obj, interface: native if interface.endswith('PhonebookAccess1') else properties,
            Dictionary=lambda value, **kw: value, Array=lambda value, **kw: value, UInt16=int)
        entries = book._pull(bus, dbus, 'contacts')
        self.assertEqual(entries[0]['numbers'], ['123'])
        properties.GetAll.assert_not_called()
        match.remove.assert_called_once()

    def test_vcards_unicode_folding_numbers_and_no_extra_data(self):
        raw = b'BEGIN:VCARD\r\nFN:Jos\xc3\xa9\\, Test\r\nTEL;TYPE=CELL:tel:+43 (123) 45\r\nTEL:123\r\nTEL:123\r\nEMAIL:private@example.test\r\nPHOTO:secret\r\nEND:VCARD\r\nBEGIN:VCARD\nFN;ENCODING=QUOTED-PRINTABLE:Gr=C3=BC=\n=C3=9Fe\nTEL:456\nEND:VCARD'
        entries = parse_vcards(raw)
        self.assertEqual(entries[0], {'name': 'Jos\u00e9, Test', 'numbers': ['+4312345', '123'], 'date': ''})
        self.assertEqual(entries[1]['name'], 'Gr\u00fc\u00dfe')
        self.assertEqual(len(parse_vcards(raw, 1)), 1)
        with self.assertRaises(ValueError): parse_vcards(b'x' * (MAX_BYTES + 1))

    def test_disconnect_clears_all_private_phonebook_data(self):
        book = Phonebook()
        book.data['views']['contacts']['entries'] = [{'name': 'Private', 'numbers': ['123']}]
        book._forget('Disconnected')
        self.assertFalse(book.snapshot()['connected'])
        self.assertEqual(book.snapshot()['views']['contacts']['entries'], [])
        with self.assertRaises(ValueError): book.refresh('../../file')
        with self.assertRaises(ConnectionError): book.refresh('contacts')



class USBTests(unittest.TestCase):
    def fixture(self, root, name, vendor='18d1', product='2d00', bus='4', number='5'):
        entry = root / name
        entry.mkdir()
        for key, value in {'idVendor': vendor, 'idProduct': product, 'busnum': bus, 'devnum': number}.items():
            (entry / key).write_text(value)

    def test_only_one_android_accessory_is_eligible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 'keyboard', '1234', '0001')
            recovery = USBRecovery(root)
            self.assertIsNone(recovery.accessory())
            self.fixture(root, 'phone')
            self.assertEqual(recovery.accessory(), (4, 5))
            self.fixture(root, 'other-phone', number='6')
            with self.assertRaises(ConnectionError): recovery.accessory()

    def test_reset_validates_character_device_and_rate_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, 'phone')
            recovery = USBRecovery(root)
            ioctl = Mock()
            with patch.dict(sys.modules, {'fcntl': SimpleNamespace(ioctl=ioctl)}), \
                 patch('usb_recovery.os.open', return_value=9) as opened, \
                 patch('usb_recovery.os.close') as closed, \
                 patch('usb_recovery.os.fstat', return_value=SimpleNamespace(st_mode=stat.S_IFCHR, st_rdev=0)), \
                 patch('usb_recovery.os.major', return_value=189, create=True), \
                 patch('usb_recovery.os.minor', return_value=388, create=True), \
                 patch('usb_recovery.time.sleep'):
                self.assertTrue(recovery.reset())
                self.assertFalse(recovery.reset())
                self.assertEqual(opened.call_args.args[0], '/dev/bus/usb/004/005')
                ioctl.assert_called_once_with(9, 0x5514, 0)
                closed.assert_called_once_with(9)


if __name__ == '__main__': unittest.main()
