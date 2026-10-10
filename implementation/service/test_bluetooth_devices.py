import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from bluetooth_devices import BluetoothDevices, read_devices
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
        objects[DEVICE]['org.bluez.Device1']['UUIDs'].append('0000112f-0000-1000-8000-00805f9b34fb')
        service._refresh();self.assertFalse(service.snapshot()['devices'][0]['audioReceiver'])

    def test_connection_actions_are_paired_only_and_disconnect_disables_reconnect(self):
        with tempfile.TemporaryDirectory() as folder:
            service,device,objects=self.service()
            service.preferences=Path(folder)/'connections.json'
            for address in ('../hci0','00:00:00:00:00:00',None):
                with self.assertRaises(ValueError):service.connection('connect',address)
            device.Connect.assert_not_called()
            service.connection('connect',ADDRESS)
            device.Connect.assert_called_once_with(timeout=3)
            service.connection('automatic',ADDRESS,True)
            self.assertEqual(service.snapshot()['autoConnect'],[ADDRESS])
            restored=BluetoothDevices(preferences=service.preferences)
            restored._load_connections()
            self.assertEqual(restored.automatic,{ADDRESS})
            with self.assertRaises(ValueError):service.connection('automatic',ADDRESS,'true')
            with self.assertRaises(ValueError):service.connection('disconnect',ADDRESS)
            device.Disconnect.assert_not_called()
            service.connection('disconnect',ADDRESS,confirmed=True)
            device.Disconnect.assert_called_once_with(timeout=3)
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
        service._refresh()
        return service,adapter,objects

    def test_list_is_bounded_and_exposes_only_device_metadata(self):
        service,_,objects=self.service()
        objects[DEVICE]['org.bluez.Device1']['LinkKey']='secret'
        objects['/unexpected/path']={'org.bluez.Device1':{'Address':ADDRESS,'Adapter':ADAPTER}}
        service._refresh()
        data=service.snapshot()
        self.assertEqual(data['devices'],[{'name':'Phone','address':ADDRESS,'paired':True,'connected':True,'serialPort':False,'audioReceiver':False}])
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
