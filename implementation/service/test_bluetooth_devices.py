import copy
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from bluetooth_devices import BluetoothDevices, CONNECT_TIMEOUT, DISCONNECT_TIMEOUT, MAX_FAILURES, friendly_error, read_devices
from live_media import with_bluetooth_media

ADAPTER='/org/bluez/hci0'
ADDRESS='AA:BB:CC:DD:EE:01'
DEVICE=ADAPTER+'/dev_'+ADDRESS.replace(':','_')
OBJECTS={ADAPTER:{'org.bluez.Adapter1':{'Powered':True,'Alias':'Hudiy','Discovering':False}},
         DEVICE:{'org.bluez.Device1':{'Adapter':ADAPTER,'Address':ADDRESS,'Alias':'Phone','Paired':True,'Connected':True}}}


class BluetoothTests(unittest.TestCase):
    def test_radio_receiver_classification_excludes_a_phone_with_phonebook_access(self):
        service,_,objects=self.service()
        objects[DEVICE]['org.bluez.Device1']['UUIDs']=['0000110b-0000-1000-8000-00805f9b34fb']
        service._refresh();self.assertTrue(service.snapshot()['devices'][0]['audioReceiver'])
        self.assertFalse(service.snapshot()['devices'][0]['phone'])
        objects[DEVICE]['org.bluez.Device1']['UUIDs'].append('0000112f-0000-1000-8000-00805f9b34fb')
        service._refresh();self.assertFalse(service.snapshot()['devices'][0]['audioReceiver'])
        self.assertTrue(service.snapshot()['devices'][0]['phone'])

    def test_connection_actions_are_paired_only_and_disconnect_disables_reconnect(self):
        with tempfile.TemporaryDirectory() as folder:
            service,device,objects=self.service()
            service.preferences=Path(folder)/'connections.json'
            for address in ('../hci0','00:00:00:00:00:00',None):
                with self.assertRaises(ValueError):service.connection('connect',address)
            device.Connect.assert_not_called()
            service.connection('connect',ADDRESS)
            device.Connect.assert_called_once_with(timeout=CONNECT_TIMEOUT)
            service.connection('automatic',ADDRESS,True)
            self.assertEqual(service.snapshot()['autoConnect'],[ADDRESS])
            restored=BluetoothDevices(preferences=service.preferences)
            restored._load_connections()
            self.assertEqual(restored.automatic,{ADDRESS})
            with self.assertRaises(ValueError):service.connection('automatic',ADDRESS,'true')
            with self.assertRaises(ValueError):service.connection('disconnect',ADDRESS)
            device.Disconnect.assert_not_called()
            service.connection('disconnect',ADDRESS,confirmed=True)
            device.Disconnect.assert_called_once_with(timeout=DISCONNECT_TIMEOUT)
            self.assertEqual(service.automatic,set())
            objects[DEVICE]['org.bluez.Device1']['Paired']=False
            with self.assertRaises(ValueError):service.connection('connect',ADDRESS)

    def test_automatic_reconnect_is_bounded_and_never_pairs_or_trusts(self):
        service,device,objects=self.service()
        service.automatic={ADDRESS}
        objects[DEVICE]['org.bluez.Device1']['Connected']=False
        service._refresh()
        service._reconnect();service._reconnect()
        device.Connect.assert_called_once_with(timeout=3)
        device.Pair.assert_not_called()
        device.Set.assert_not_called()
        service.last_attempt.clear()
        objects[DEVICE]['org.bluez.Device1']['Paired']=False
        service._refresh();service._reconnect()
        self.assertEqual(device.Connect.call_count,1)
    def test_addressed_track_metadata_is_live_bounded_and_clears_on_disconnect(self):
        service,_,objects=self.service()
        path=DEVICE+'/player0'
        objects[DEVICE]['org.bluez.MediaControl1']={'Player':path}
        objects[path]={'org.bluez.MediaPlayer1':{'Device':DEVICE,'Status':'paused','Position':6344,
                       'Track':{'Title':'Dance With Me','Artist':'ASTRE','Album':'Freedom EP','Duration':229000}}}
        service._refresh()
        media=service.media_snapshot()
        self.assertEqual((media['title'],media['position'],media['duration'],media['playing']),
                         ('Dance With Me','00:06','03:49',False))
        objects[path]['org.bluez.MediaPlayer1']['Track']['Title']='x'*1000
        objects[path]['org.bluez.MediaPlayer1']['Position']=-10
        service._refresh()
        self.assertEqual(len(service.media_snapshot()['title']),512)
        self.assertEqual(service.media_snapshot()['position'],'00:00')
        objects[DEVICE]['org.bluez.Device1']['Connected']=False
        service._refresh()
        self.assertEqual(service.media_snapshot(),{})

    def test_bluetooth_fallback_preserves_android_and_only_matching_native_artwork(self):
        bluetooth={'source':'bluetooth','title':'Song','artist':'Artist','album':'Album','position':'00:06'}
        android={'media':{'source':'android','title':'Android song','coverart':True}}
        self.assertIs(with_bluetooth_media(android,bluetooth),android)
        stale={'media':{'source':'bluetooth','title':'Old song','coverart':True,'coverartVersion':5}}
        merged=with_bluetooth_media(stale,bluetooth)
        self.assertEqual(merged['media'],bluetooth)
        same={'media':{**bluetooth,'coverart':True,'coverartVersion':6}}
        self.assertTrue(with_bluetooth_media(same,bluetooth)['media']['coverart'])
        self.assertIs(with_bluetooth_media(same,{}),same)
    def test_playback_selects_only_one_connected_paired_addressed_player(self):
        service,player,objects=self.service()
        path=DEVICE+'/player0'
        objects[DEVICE]['org.bluez.MediaControl1']={'Player':path}
        objects[path]={'org.bluez.MediaPlayer1':{'Device':DEVICE,'Status':'stopped'}}
        service.playback('toggle'); player.Play.assert_called_once_with(timeout=3)
        objects[path]['org.bluez.MediaPlayer1']['Status']='playing'
        service.playback('toggle'); player.Pause.assert_called_once_with(timeout=3)
        service.playback('next'); player.Next.assert_called_once_with(timeout=3)
        service.playback('previous'); player.Previous.assert_called_once_with(timeout=3)
        player.reset_mock()
        for invalid in ('Seek','shell',[],None):
            with self.assertRaises(ValueError): service.playback(invalid)
        objects[DEVICE]['org.bluez.Device1']['Connected']=False
        with self.assertRaises(ConnectionError):service.playback('toggle')
        player.Play.assert_not_called()
        objects[DEVICE]['org.bluez.Device1']['Connected']=True
        objects[DEVICE]['org.bluez.MediaControl1']['Player']='/arbitrary/player0'
        with self.assertRaises(ConnectionError):service.playback('next')
        player.Next.assert_not_called()

    def service(self):
        objects=copy.deepcopy(OBJECTS)
        adapter=Mock()
        service=BluetoothDevices()
        service.enabled=True
        service.bus=Mock()
        service.dbus=SimpleNamespace(Interface=lambda *_:adapter, ObjectPath=lambda path:path)
        service.manager=Mock()
        service.manager.GetManagedObjects.side_effect=lambda **_:objects
        service.start_worker=lambda target:target()
        service._refresh()
        return service,adapter,objects

    def test_list_is_bounded_and_exposes_only_device_metadata(self):
        service,_,objects=self.service()
        objects[DEVICE]['org.bluez.Device1']['LinkKey']='secret'
        objects['/unexpected/path']={'org.bluez.Device1':{'Address':ADDRESS,'Adapter':ADAPTER}}
        service._refresh()
        data=service.snapshot()
        self.assertEqual(data['devices'],[{'name':'Phone','address':ADDRESS,'paired':True,'connected':True,'phone':False,'serialPort':False,'audioReceiver':False}])
        data['devices'].clear()
        self.assertEqual(len(service.snapshot()['devices']),1)
        objects['/org/bluez/hci1']={'org.bluez.Adapter1':{'Powered':True}}
        with self.assertRaises(ConnectionError): read_devices(objects)

    def test_remove_requires_confirmation_and_current_paired_device(self):
        service,adapter,objects=self.service()
        for address,confirmation in ((ADDRESS,False),(ADDRESS,'true'),('../hci0',True),([],True),('00:00:00:00:00:00',True)):
            with self.assertRaises(ValueError): service.command('remove',address,confirmation)
        adapter.RemoveDevice.assert_not_called()
        adapter.RemoveDevice.side_effect=lambda path,**_:objects.pop(path)
        self.assertTrue(service.command('remove',ADDRESS,True)['accepted'])
        adapter.RemoveDevice.assert_called_once_with(DEVICE,timeout=3)
        self.assertEqual(service.snapshot()['devices'],[])

    def test_scan_owns_only_one_bounded_session_and_stop_is_idempotent(self):
        service,adapter,_=self.service()
        service.command('scan'); service.command('scan')
        adapter.StartDiscovery.assert_called_once_with(timeout=3)
        self.assertTrue(service.snapshot()['scanActive'])
        service.command('stop'); service.command('stop')
        adapter.StopDiscovery.assert_called_once_with(timeout=3)
        self.assertFalse(service.snapshot()['scanActive'])
        with self.assertRaises(ValueError): service.command('shell')

    def test_disabled_service_cannot_change_bluetooth(self):
        with self.assertRaises(ConnectionError): BluetoothDevices(False).command('scan')


class BluezError(Exception):
    def __init__(self,name,text=''):
        super().__init__(text);self.name=name
    def get_dbus_name(self):return self.name


class BluetoothScreenTests(unittest.TestCase):
    service=BluetoothTests.service

    def test_single_powered_off_adapter_is_reported_instead_of_failing(self):
        service,device,objects=self.service()
        objects[ADAPTER]['org.bluez.Adapter1']['Powered']=False
        objects[DEVICE]['org.bluez.Device1']['Connected']=False
        service._refresh()
        data=service.snapshot()
        self.assertTrue(data['available']);self.assertFalse(data['powered'])
        self.assertEqual(data['devices'][0]['address'],ADDRESS)
        with self.assertRaises(ConnectionError):service.connection('connect',ADDRESS)
        with self.assertRaises(ConnectionError):service.command('scan')
        service.automatic={ADDRESS};service._reconnect()
        device.Connect.assert_not_called();device.StartDiscovery.assert_not_called()
        objects['/org/bluez/hci1']={'org.bluez.Adapter1':{'Powered':False}}
        with self.assertRaises(ConnectionError):read_devices(objects)
        with self.assertRaises(ConnectionError):read_devices({})

    def test_power_toggle_stops_scan_and_sets_only_the_adapter_property(self):
        service,adapter,objects=self.service()
        adapter.Set.side_effect=lambda interface,key,value,**_:objects[ADAPTER][interface].__setitem__(key,value)
        for invalid in ('false',0,None,[]):
            with self.assertRaises(ValueError):service.power(invalid)
        service.command('scan')
        result=service.power(False)
        self.assertEqual((result['accepted'],result['powered']),(True,False))
        adapter.StopDiscovery.assert_called_once_with(timeout=3)
        adapter.Set.assert_called_once_with('org.bluez.Adapter1','Powered',False,timeout=5)
        self.assertFalse(service.snapshot()['powered']);self.assertFalse(service.snapshot()['scanActive'])
        service.power(True)
        self.assertTrue(service.snapshot()['powered'])
        adapter.Set.side_effect=BluezError('org.bluez.Error.Blocked')
        with self.assertRaisesRegex(ConnectionError,'blocked'):service.power(False)

    def test_rename_is_bounded_printable_and_paired_only(self):
        service,device,objects=self.service()
        device.Set.side_effect=lambda interface,key,value,**_:objects[DEVICE][interface].__setitem__(key,value)
        for name in ('','   ','x'*65,'bad\nname','tab\tname',None,7):
            with self.assertRaises(ValueError):service.rename(ADDRESS,name)
        with self.assertRaises(ValueError):service.rename('../hci0','Car')
        device.Set.assert_not_called()
        self.assertEqual(service.rename(ADDRESS,'  My phone ')['name'],'My phone')
        device.Set.assert_called_once_with('org.bluez.Device1','Alias','My phone',timeout=3)
        self.assertEqual(service.snapshot()['devices'][0]['name'],'My phone')
        objects[DEVICE]['org.bluez.Device1']['Paired']=False
        with self.assertRaises(ValueError):service.rename(ADDRESS,'Other')

    def test_connect_runs_in_a_worker_and_reports_state_and_friendly_errors(self):
        service,device,objects=self.service()
        objects[DEVICE]['org.bluez.Device1']['Connected']=False
        jobs=[];service.start_worker=jobs.append
        result=service.connection('connect',ADDRESS)
        self.assertEqual(result['state'],'connecting')
        self.assertEqual(service.snapshot()['operations'],{ADDRESS:{'state':'connecting','message':''}})
        device.Connect.assert_not_called()
        # The long request holds no lock: other actions keep working, duplicates are refused.
        self.assertTrue(service.command('scan')['accepted'])
        with self.assertRaises(ConnectionError):service.connection('connect',ADDRESS)
        device.Connect.side_effect=BluezError('org.bluez.Error.Failed','br-connection-page-timeout')
        jobs.pop()()
        self.assertEqual(service.snapshot()['operations'][ADDRESS],
            {'state':'failed','message':"Couldn't connect. Make sure the device is on and in range."})
        service.operations[ADDRESS]['at']-=31
        self.assertEqual(service.snapshot()['operations'],{})
        device.Connect.side_effect=lambda **_:objects[DEVICE]['org.bluez.Device1'].__setitem__('Connected',True)
        service.connection('connect',ADDRESS);jobs.pop()()
        data=service.snapshot()
        self.assertEqual(data['operations'],{});self.assertTrue(data['devices'][0]['connected'])
        service.connection('disconnect',ADDRESS,confirmed=True)
        self.assertEqual(service.snapshot()['operations'][ADDRESS]['state'],'disconnecting')

    def test_common_bluez_errors_have_short_english_messages(self):
        cases={('org.bluez.Error.Failed','Host is down'):"Couldn't connect. Make sure the device is on and in range.",
               ('org.bluez.Error.AuthenticationFailed',''):"Couldn't connect. Remove the device and pair it again.",
               ('org.bluez.Error.InProgress',''):'The device is still busy with a previous request. Please wait.',
               ('org.bluez.Error.NotReady',''):'Bluetooth is not ready yet. Try again in a moment.',
               ('org.freedesktop.DBus.Error.NoReply','Did not receive a reply'):"Couldn't connect. The device didn't answer. Make sure it is on and in range.",
               ('org.bluez.Error.AlreadyConnected',''):''}
        for (name,text),expected in cases.items():
            self.assertEqual(friendly_error(BluezError(name,text)),expected)
        self.assertEqual(friendly_error(BluezError('org.bluez.Error.AuthenticationRejected'),'pair'),
                         'Pairing was cancelled or the codes did not match.')
        self.assertNotIn('org.bluez',friendly_error(BluezError('org.bluez.Error.Failed','weird'),'disconnect'))
        self.assertEqual(friendly_error(BluezError('org.freedesktop.DBus.Error.ServiceUnknown')),
                         'Bluetooth is not ready yet. Try again in a moment.')


class Stop:
    """Stands in for the stop event: ends the background loop after a fixed number of waits."""
    def __init__(self,ticks):self.ticks=ticks;self.waits=0
    def is_set(self):return self.waits>=self.ticks
    def wait(self,_):self.waits+=1


def fake_dbus(managers,device):
    """Minimal dbus module; every SystemBus() call is a new connection with the next manager."""
    buses=[]
    def system_bus(**_):
        buses.append(Mock());return buses[-1]
    def interface(_,name):return managers[len(buses)-1] if name=='org.freedesktop.DBus.ObjectManager' else device
    return SimpleNamespace(SystemBus=system_bus,Interface=interface,ObjectPath=str),buses


class BluetoothLockAndRecoveryTests(unittest.TestCase):
    service=BluetoothTests.service

    def test_user_actions_wait_briefly_for_the_background_refresh(self):
        service,device,objects=self.service()
        with patch('bluetooth_devices.LOCK_WAIT',2):
            service.operation_lock.acquire()
            threading.Timer(.1,service.operation_lock.release).start()
            self.assertTrue(service.command('scan')['accepted'])
        with patch('bluetooth_devices.LOCK_WAIT',.05):
            service.operation_lock.acquire()
            try:
                for action in (lambda:service.power(True),lambda:service.rename(ADDRESS,'Car'),lambda:service.playback('next'),
                               lambda:service.command('stop'),lambda:service.connection('connect',ADDRESS)):
                    with self.assertRaisesRegex(ConnectionError,'in progress'):action()
                self.assertEqual(service.retry_android_auto(manual=True),'waiting-for-bluetooth')
            finally:service.operation_lock.release()
        device.Connect.assert_not_called()
        # The Android Auto bootstrap connect also runs without holding the operation lock.
        objects[DEVICE]['org.bluez.Device1'].update(Connected=False,UUIDs=['0000111f-0000-1000-8000-00805f9b34fb'])
        locked=[];device.Connect.side_effect=lambda **_:locked.append(service.operation_lock.locked())
        self.assertEqual(service.retry_android_auto(manual=True),'waiting-for-phone')
        self.assertEqual(locked,[False])

    def test_background_reconnect_runs_without_the_operation_lock(self):
        objects=copy.deepcopy(OBJECTS);objects[DEVICE]['org.bluez.Device1']['Connected']=False
        manager=Mock();manager.GetManagedObjects.side_effect=lambda **_:objects
        device=Mock();service=BluetoothDevices();service.enabled=True
        service.automatic={ADDRESS};service.stop=Stop(1)
        locked=[];device.Connect.side_effect=lambda **_:locked.append(service.operation_lock.locked())
        module,buses=fake_dbus([manager],device)
        with patch.dict(sys.modules,{'dbus':module}):service._run_once()
        device.Connect.assert_called_once_with(timeout=3)
        self.assertEqual(locked,[False])
        self.assertTrue(service.snapshot()['available'])
        buses[0].close.assert_called_once();self.assertIsNone(service.bus)

    def test_bus_is_rebuilt_after_bluetoothd_restart_or_repeated_failures(self):
        objects=copy.deepcopy(OBJECTS)
        gone=Mock();gone.GetManagedObjects.side_effect=BluezError('org.freedesktop.DBus.Error.ServiceUnknown','The name :1.4 was not provided')
        fresh=Mock();fresh.GetManagedObjects.side_effect=lambda **_:objects
        flaky=Mock();flaky.GetManagedObjects.side_effect=[TimeoutError()]*(MAX_FAILURES-1)+[objects]+[TimeoutError()]*MAX_FAILURES
        module,buses=fake_dbus([gone,fresh,flaky],Mock())
        service=BluetoothDevices();service.enabled=True;service.stop=Stop(50)
        service.scan_until=time.monotonic()+30
        with patch.dict(sys.modules,{'dbus':module}):
            service._run_once()
            # A vanished bluetoothd ends the loop at once instead of retrying stale proxies forever.
            self.assertEqual(gone.GetManagedObjects.call_count,1)
            buses[0].close.assert_called_once();self.assertIsNone(service.bus)
            data=service.snapshot()
            self.assertEqual((data['available'],data['scanActive'],service.scan_until),(False,False,0))
            service.stop=Stop(1);service._run_once()
            self.assertTrue(service.snapshot()['available'])
            service.stop=Stop(50);service._run_once()
        # Only consecutive failures count; a good refresh resets the counter.
        self.assertEqual(flaky.GetManagedObjects.call_count,2*MAX_FAILURES)
        self.assertEqual(service.stop.waits,2*MAX_FAILURES-1)
        self.assertEqual(len(buses),3)

    def test_connect_worker_fails_cleanly_while_the_bus_is_rebuilt(self):
        service,_,_=self.service()
        service.bus=None
        service._device_request(ADDRESS,DEVICE,'connect')
        self.assertEqual(service.snapshot()['operations'][ADDRESS],
                         {'state':'failed','message':'Bluetooth is not ready yet. Try again in a moment.'})
