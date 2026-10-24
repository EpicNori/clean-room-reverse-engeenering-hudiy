import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from bluez_agent import BluezAgent
from bluetooth_devices import AA_UUID, BluetoothDevices
from runtime_support import read_options, save_json
from standalone_projection import StandaloneProjection
import test_bluetooth_devices as bluetooth_fixture
from test_bluetooth_devices import ADDRESS, DEVICE, ADAPTER


class AutomaticConnectionTests(unittest.TestCase):
    def service(self):
        service, device, objects=bluetooth_fixture.BluetoothTests().service()
        objects[DEVICE]['org.bluez.Device1']['UUIDs']=['0000111f-0000-1000-8000-00805f9b34fb']
        service._refresh()
        return service, device, objects

    def agent(self):
        projection=Mock()
        projection.snapshot.return_value={'available':True, 'connectionAllowed':True,
            'automaticConnectionAllowed':True, 'connected':False, 'sessionStarting':False}
        wireless=Mock()
        wireless.credentials.return_value={'enabled':True,'ipAddress':'192.168.12.1','port':5277}
        bluetooth=Mock()
        agent=BluezAgent(bluetooth,wireless,projection)
        agent.ready=True
        return agent, projection, wireless, bluetooth

    def test_master_choice_survives_restart_and_invalid_values_keep_legacy_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'projection.json'
            self.assertTrue(read_options(path)['autoConnect'])
            bridge=StandaloneProjection(preferences=path)
            bridge.enabled=bridge.available=True
            bridge.sock=Mock()
            bridge.settings({'autoConnect':False})
            self.assertFalse(read_options(path)['autoConnect'])
            self.assertFalse(read_options(path)['autostart'])
            bridge.settings({'autostart':True})
            self.assertFalse(read_options(path)['autoConnect'])
            self.assertTrue(read_options(path)['autostart'])
            with patch('standalone_projection.save_json',side_effect=OSError('Full')):
                with self.assertRaises(OSError):bridge.settings({'autoConnect':True})
            self.assertFalse(bridge.options['autoConnect'])
            self.assertFalse(json.loads(bridge.sock.sendall.call_args.args[0])['options']['autoConnect'])
            for value in (1, 'true', None, [], {}):
                with self.assertRaises(ValueError):bridge.settings({'autoConnect':value})
            save_json(path,{'autoConnect':'false'})
            self.assertTrue(read_options(path)['autoConnect'])

    def test_phone_detection_does_not_require_phonebook_and_excludes_obd_audio_receiver(self):
        service, _, objects=self.service()
        self.assertTrue(service.snapshot()['devices'][0]['phone'])
        for uuid in ('00001101-0000-1000-8000-00805f9b34fb','0000110b-0000-1000-8000-00805f9b34fb'):
            objects[DEVICE]['org.bluez.Device1']['UUIDs']=[uuid]
            service._refresh()
            self.assertFalse(service.snapshot()['devices'][0]['phone'])
        objects[DEVICE]['org.bluez.Device1']['Class']=0x020c
        service._refresh()
        self.assertTrue(service.snapshot()['devices'][0]['phone'])

    def test_only_phone_default_manual_override_and_bounded_boot_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            service, device, objects=self.service()
            service.preferences=Path(directory)/'bluetooth.json'
            service.automatic_phone_allowed=lambda:True
            objects[DEVICE]['org.bluez.Device1']['Connected']=False
            service._refresh()
            self.assertEqual(service.snapshot()['effectiveAutoConnect'],[ADDRESS])
            service._reconnect();service._reconnect()
            device.Connect.assert_called_once_with(timeout=3)
            service.connection('automatic',ADDRESS,False)
            self.assertEqual(service.snapshot()['effectiveAutoConnect'],[])
            restored=BluetoothDevices(preferences=service.preferences)
            restored._load_connections()
            self.assertEqual(restored.manual_phones,{ADDRESS})
            service.connection('automatic',ADDRESS,True)
            self.assertEqual(service.manual_phones,set())
            service.connection('disconnect',ADDRESS,confirmed=True)
            self.assertEqual(service.snapshot()['effectiveAutoConnect'],[])

    def test_multiple_phones_require_selection_never_choose_obd_or_another_connected_phone(self):
        service, device, objects=self.service()
        service.automatic_phone_allowed=lambda:True
        other=ADAPTER+'/dev_AA_BB_CC_DD_EE_02'
        objects[other]=copy.deepcopy(objects[DEVICE])
        objects[other]['org.bluez.Device1']['Address']='AA:BB:CC:DD:EE:02'
        service._refresh()
        self.assertEqual(service.snapshot()['effectiveAutoConnect'],[])
        service.automatic={ADDRESS}
        service.retry_android_auto()
        device.ConnectProfile.assert_not_called()
        objects[other]['org.bluez.Device1']['Connected']=False
        service.retry_android_auto()
        device.ConnectProfile.assert_called_once_with(AA_UUID,timeout=3)
        device.Disconnect.assert_not_called()
        device.Pair.assert_not_called()
        device.Set.assert_not_called()

    def test_wireless_retries_existing_handoff_at_most_every_thirty_seconds(self):
        agent, projection, _, bluetooth=self.agent()
        connection=Mock();agent.connection=connection
        with patch('bluez_agent.time.monotonic',return_value=100) as clock:
            agent.automatic_reconnect();agent.automatic_reconnect()
            self.assertEqual(connection.sendall.call_count,1)
            clock.return_value=130
            agent.automatic_reconnect()
            self.assertEqual(connection.sendall.call_count,2)
        bluetooth.retry_android_auto.assert_not_called()
        projection.action.assert_not_called() # No foreground/open request.

    def test_missing_handoff_uses_targeted_profile_and_does_not_interrupt_active_or_starting_session(self):
        agent, projection, _, bluetooth=self.agent()
        agent.automatic_reconnect()
        bluetooth.retry_android_auto.assert_called_once_with()
        for state in ({'connected':True},{'sessionStarting':True},
                      {'automaticConnectionAllowed':False},{'options':{'autoConnect':False}},{'available':False}):
            agent.last_reconnect=float('-inf')
            projection.snapshot.return_value.update(state)
            agent.automatic_reconnect()
            self.assertEqual(bluetooth.retry_android_auto.call_count,1)
            projection.snapshot.return_value={'available':True,'connectionAllowed':True,
                'automaticConnectionAllowed':True,'connected':False,'sessionStarting':False}

    def test_quit_usb_and_disabled_hotspot_suppress_retries_manual_works_when_master_off(self):
        agent, projection, wireless, bluetooth=self.agent()
        agent.pause_connection()
        agent.automatic_reconnect()
        bluetooth.retry_android_auto.assert_not_called()
        agent.connection_settings(True)
        agent.select_transport('usb')
        agent.automatic_reconnect()
        bluetooth.retry_android_auto.assert_not_called()
        agent.select_transport('wifi')
        wireless.credentials.return_value['enabled']=False
        agent.automatic_reconnect()
        bluetooth.retry_android_auto.assert_not_called()
        wireless.credentials.return_value['enabled']=True
        projection.snapshot.return_value.update(connectionAllowed=False,automaticConnectionAllowed=False)
        self.assertFalse(agent.wireless_allowed())
        agent.request_connection()
        self.assertTrue(agent.wireless_allowed())
        agent.automatic_reconnect()
        bluetooth.retry_android_auto.assert_not_called()
        agent.connection_settings(False)
        self.assertFalse(agent.wireless_allowed())

    def test_background_retry_recovers_from_transient_bluetooth_errors(self):
        agent, _, _, _=self.agent()
        agent.automatic_reconnect=Mock(side_effect=ConnectionError('BlueZ starting'))
        agent.stop=Mock()
        agent.stop.is_set.side_effect=[False,False,True]
        agent._reconnect_loop()
        self.assertEqual(agent.automatic_reconnect.call_count,2)

    def test_missing_native_admission_status_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            projection=StandaloneProjection(preferences=Path(directory)/'projection.json')
            self.assertFalse(projection.snapshot()['automaticConnectionAllowed'])
            projection._event({'event':'state','connected':False,'visible':False,
                'connectionAllowed':True,'automaticConnectionAllowed':True,'sessionStarting':True})
            self.assertTrue(projection.snapshot()['automaticConnectionAllowed'])
            self.assertTrue(projection.snapshot()['sessionStarting'])

if __name__=='__main__':unittest.main()
