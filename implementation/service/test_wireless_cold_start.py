import json
import socket
import struct
import threading
import unittest
from unittest.mock import Mock,patch

from bluez_agent import BluezAgent
import test_bluetooth_devices as bluetooth_fixture
from test_bluetooth_devices import ADDRESS,DEVICE

CONFIG={'enabled':True,'ssid':'Demo car','passphrase':'sample-secret','ipAddress':'192.168.12.1','port':5277}

def packet(connection):
    def exact(size):
        result=b''
        while len(result)<size:
            part=connection.recv(size-len(result))
            if not part:raise ConnectionError('Short fixture frame')
            result+=part
        return result
    header=exact(4);size,kind=struct.unpack('>HH',header)
    return kind,exact(size)

class WirelessColdStartTests(unittest.TestCase):
    def agent(self,automatic=True):
        projection=Mock();projection.snapshot.return_value={'available':True,'connected':False,
            'connectionAllowed':automatic,'automaticConnectionAllowed':automatic,
            'wirelessListening':True,'sessionStarting':False,'transport':None,'options':{'autoConnect':automatic}}
        wireless=Mock();wireless.credentials.return_value=dict(CONFIG)
        bluetooth=Mock();bluetooth.retry_android_auto.return_value='waiting-for-phone'
        agent=BluezAgent(bluetooth,wireless,projection);agent.ready=True
        return agent,projection,bluetooth

    def service(self):
        service,device,objects=bluetooth_fixture.BluetoothTests().service()
        objects[DEVICE]['org.bluez.Device1'].update(Connected=False,Class=0x020c)
        service._refresh();return service,device,objects

    def test_manual_wifi_without_usb_or_existing_handoff_starts_paired_phone_with_automatic_off(self):
        agent,projection,bluetooth=self.agent(False)
        self.assertIsNone(agent.connection)
        agent.request_connection();agent.select_transport('wifi');agent.retrigger()
        bluetooth.retry_android_auto.assert_called_once_with(manual=True)
        projection.action.assert_not_called()
        self.assertEqual(agent.snapshot()['wirelessHandshake']['stage'],'waiting-for-phone')

    def test_automatic_waits_for_listener_and_registration_without_consuming_retry_budget(self):
        agent,projection,bluetooth=self.agent()
        projection.snapshot.return_value['wirelessListening']=False
        agent.automatic_reconnect();bluetooth.retry_android_auto.assert_not_called()
        self.assertEqual(agent.last_reconnect,float('-inf'))
        projection.snapshot.return_value['wirelessListening']=True;agent.ready=False
        agent.automatic_reconnect();bluetooth.retry_android_auto.assert_not_called()
        agent.ready=True;agent.automatic_reconnect()
        bluetooth.retry_android_auto.assert_called_once_with(manual=False)

    def test_waits_for_usb_recovery_and_never_requests_a_usb_reset_or_foreground_open(self):
        agent,projection,bluetooth=self.agent()
        projection.snapshot.return_value['usbRecoveryRunning']=True
        agent.automatic_reconnect();bluetooth.retry_android_auto.assert_not_called()
        projection.snapshot.return_value['usbRecoveryRunning']=False
        agent.automatic_reconnect();bluetooth.retry_android_auto.assert_called_once_with(manual=False)
        projection.action.assert_not_called()

    def test_actual_paired_phone_connection_is_standard_bluez_connect_and_never_remote_aa_profile(self):
        service,device,_=self.service()
        service.manual_phones={ADDRESS};service.automatic_phone_allowed=lambda:False
        self.assertEqual(service.retry_android_auto(manual=True),'waiting-for-phone')
        device.Connect.assert_called_once_with(timeout=3)
        device.ConnectProfile.assert_not_called();device.Disconnect.assert_not_called()
        device.Pair.assert_not_called();device.Set.assert_not_called()

    def test_explicit_phone_autoreconnect_also_waits_for_wireless_profile_and_listener(self):
        service,device,_=self.service();service.automatic={ADDRESS}
        service.phone_connection_ready=lambda:False
        service._reconnect();device.Connect.assert_not_called()
        service.phone_connection_ready=lambda:True
        service._reconnect();device.Connect.assert_called_once_with(timeout=3)

    def test_manual_retry_is_rate_limited_and_does_not_modify_saved_choices(self):
        service,device,_=self.service();service.manual_phones={ADDRESS}
        with patch('bluetooth_devices.time.monotonic',return_value=100) as clock:
            service.retry_android_auto(manual=True);service.retry_android_auto(manual=True)
            self.assertEqual(device.Connect.call_count,1)
            clock.return_value=105;service.retry_android_auto(manual=True)
            self.assertEqual(device.Connect.call_count,2)
        self.assertEqual(service.manual_phones,{ADDRESS});self.assertEqual(service.automatic,set())

    def test_socket_exchange_supplies_complete_wifi_credentials_without_any_usb_state(self):
        agent,projection,bluetooth=self.agent(False);agent.request_connection()
        receiver,phone=socket.socketpair();receiver.settimeout(1);phone.settimeout(2)
        agent.connection=receiver
        with patch('bluez_agent.Path.read_text',return_value='02:00:00:00:00:01\n'):
            worker=threading.Thread(target=agent._handshake,args=(receiver,));worker.start()
            try:
                kind,payload=packet(phone)
                self.assertEqual(kind,1)
                self.assertEqual(payload,b'\x0a\x0c192.168.12.1\x10\x9d\x29')
                phone.sendall(b'\x00\x00');phone.sendall(b'\x00\x02') # split header
                kind,payload=packet(phone)
                self.assertEqual(kind,3)
                self.assertEqual(payload,b'\x0a\x08Demo car\x12\x0dsample-secret\x1a\x1102:00:00:00:00:01\x20\x08\x28\x01')
            finally:
                phone.close();worker.join(timeout=3)
                if worker.is_alive():agent.stop.set();receiver.close();worker.join(timeout=2)
        self.assertFalse(worker.is_alive());self.assertEqual(agent.snapshot()['wirelessHandshake']['credentialRequests'],1)
        self.assertNotIn('sample-secret',json.dumps(agent.snapshot()))
        self.assertFalse(projection.snapshot.return_value['connected']) # Handoff is not proof of projected video.
        projection.action.assert_not_called()

    def test_early_handoff_waits_for_hotspot_instead_of_sending_an_unreachable_endpoint(self):
        agent,_,_=self.agent();connection=Mock();connection.recv.return_value=b'';agent.connection=connection
        agent._wireless_ready=Mock(side_effect=[False,False,True]);agent.stop=Mock()
        agent.stop.wait.return_value=False;agent.stop.is_set.return_value=False
        agent._handshake(connection)
        self.assertEqual(agent.stop.wait.call_count,2)
        connection.sendall.assert_called_once()

    def test_manual_resume_can_leave_stale_usb_preference_and_quit_cancels_wireless_work(self):
        agent,_,bluetooth=self.agent(False)
        agent.select_transport('usb');agent.request_connection();agent.select_transport('auto');agent.retrigger()
        bluetooth.retry_android_auto.assert_called_once_with(manual=True)
        agent.pause_connection();agent.last_reconnect=float('-inf');agent.automatic_reconnect()
        self.assertEqual(bluetooth.retry_android_auto.call_count,1)

    def test_disconnected_manual_session_never_leaves_a_false_connected_status(self):
        agent,projection,_=self.agent(False)
        projection.snapshot.return_value.update(connected=True,transport='wifi')
        agent.automatic_reconnect()
        self.assertEqual(agent.snapshot()['wirelessHandshake']['stage'],'connected')
        projection.snapshot.return_value['connected']=False
        agent.automatic_reconnect()
        self.assertNotEqual(agent.snapshot()['wirelessHandshake']['stage'],'connected')

    def test_invalid_hotspot_bssid_never_sends_credentials(self):
        agent,_,_=self.agent()
        with patch('bluez_agent.Path.read_text',return_value='00:00:00:00:00:00'):
            with self.assertRaises(ConnectionError):agent._credential_frame()
        agent.wireless.credentials.return_value={**CONFIG,'passphrase':''}
        with self.assertRaises(ValueError):agent._credential_frame()

if __name__=='__main__':unittest.main()
