import copy
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from calls import MAX_FAILURES,PhoneCalls,dial_number
from test_bluetooth_devices import OBJECTS,DEVICE

MODEM='/hfp'+DEVICE
CALL=MODEM+'/voicecall01'


class FastStop(threading.Event):
    def wait(self,timeout=None):return self.is_set()


class LostError(Exception):
    def __init__(self,name):super().__init__(name);self.name=name
    def get_dbus_name(self):return self.name


def fake_modules(system_bus):
    """Stand-ins for python3-dbus and GLib so the worker loop runs without D-Bus."""
    glib=SimpleNamespace(DBusGMainLoop=Mock())
    context=SimpleNamespace(pending=lambda:False,iteration=Mock())
    repository=SimpleNamespace(GLib=SimpleNamespace(MainContext=SimpleNamespace(default=lambda:context)))
    dbus=SimpleNamespace(SystemBus=system_bus,Interface=lambda obj,name:Mock(),Boolean=bool,mainloop=SimpleNamespace(glib=glib))
    return {'dbus':dbus,'dbus.mainloop':dbus.mainloop,'dbus.mainloop.glib':glib,'gi':SimpleNamespace(repository=repository),'gi.repository':repository}


class CallTests(unittest.TestCase):
    def fixture(self):
        service=PhoneCalls();service.enabled=True;service.bus=Mock()
        service.dbus=SimpleNamespace(Boolean=bool)
        objects=copy.deepcopy(OBJECTS)
        service.bluez=Mock();service.bluez.GetManagedObjects.side_effect=lambda **_:objects
        service.modems=Mock();service.modems.GetModems.return_value=[(MODEM,{'Powered':True,'Online':True,'Type':'hfp','Interfaces':['org.ofono.VoiceCallManager']})]
        manager=Mock();manager.GetCalls.return_value=[]
        call=Mock();volume=Mock();volume.GetProperties.return_value={'Muted':False}
        service._interface=lambda path,name:{'org.ofono.VoiceCallManager':manager,'org.ofono.VoiceCall':call,'org.ofono.CallVolume':volume}[name]
        return service,manager,call,volume,objects

    def test_dial_validates_number_confirmation_pairing_and_existing_calls(self):
        service,manager,_,_,objects=self.fixture()
        for number in ('123;shutdown','*123#','+','1',None,'1'*65):
            with self.assertRaises(ValueError):service.command('dial',number,True)
        with self.assertRaises(ValueError):service.command('dial','+49 123456',False)
        manager.Dial.assert_not_called()
        service.command('dial','+49 (123)-456',True)
        manager.Dial.assert_called_once_with('+49123456','default',timeout=3)
        manager.GetCalls.return_value=[(CALL,{'State':'active'})]
        with self.assertRaises(ConnectionError):service.command('dial','123456',True)
        self.assertEqual(manager.Dial.call_count,1)
        objects[DEVICE]['org.bluez.Device1']['Paired']=False
        with self.assertRaises(ConnectionError):service.command('dial','123456',True)

    def test_call_actions_target_only_one_valid_current_call(self):
        service,manager,call,volume,_=self.fixture()
        with self.assertRaises(ConnectionError):service.command('end')
        manager.GetCalls.return_value=[('/arbitrary/voicecall01',{'State':'incoming'})]
        with self.assertRaises(ConnectionError):service.command('answer')
        call.Answer.assert_not_called()
        manager.GetCalls.return_value=[(CALL,{'State':'incoming'})]
        service.command('answer');call.Answer.assert_called_once_with(timeout=3)
        service.command('end');call.Hangup.assert_called_once_with(timeout=3)
        manager.GetCalls.return_value=[(CALL,{'State':'active'})]
        with self.assertRaises(ConnectionError):service.command('answer')
        service.command('mute',muted=True)
        volume.SetProperty.assert_called_once_with('Muted',True,timeout=3)
        manager.GetCalls.return_value=[(CALL,{'State':'held'}),(MODEM+'/voicecall02',{'State':'waiting'})]
        with self.assertRaises(ConnectionError):service.command('end')
        manager.HangupAll.assert_not_called()

    def test_end_with_call_waiting_hangs_up_only_the_call_in_progress(self):
        service,manager,call,_,_=self.fixture()
        targets=[];original=service._interface
        def interface(path,name):
            if name=='org.ofono.VoiceCall':targets.append(path)
            return original(path,name)
        service._interface=interface
        waiting=MODEM+'/voicecall02'
        manager.GetCalls.return_value=[(waiting,{'State':'waiting'}),(CALL,{'State':'active'})]
        with self.assertRaises(ConnectionError):service.command('answer')
        call.Answer.assert_not_called()
        service.command('end')
        self.assertEqual(targets,[CALL]);call.Hangup.assert_called_once_with(timeout=3)
        manager.GetCalls.return_value=[(CALL,{'State':'held'}),(waiting,{'State':'dialing'})]
        targets.clear();service.command('end');self.assertEqual(targets,[waiting])
        # A conference (two active calls) stays ambiguous; never fall back to HangupAll.
        manager.GetCalls.return_value=[(CALL,{'State':'active'}),(waiting,{'State':'active'})]
        with self.assertRaises(ConnectionError):service.command('end')
        self.assertEqual(call.Hangup.call_count,2);manager.HangupAll.assert_not_called()

    def test_command_waits_briefly_for_background_refresh(self):
        service,manager,call,_,_=self.fixture()
        manager.GetCalls.return_value=[(CALL,{'State':'incoming'})]
        held=threading.Event();release=threading.Event()
        def refresh():
            with service.operation_lock:held.set();release.wait(3)
        worker=threading.Thread(target=refresh);worker.start();held.wait(1)
        service.command_wait=.05
        with self.assertRaisesRegex(ConnectionError,'in progress'):service.command('answer')
        call.Answer.assert_not_called()
        service.command_wait=3;threading.Timer(.1,release.set).start()
        service.command('answer');call.Answer.assert_called_once_with(timeout=3)
        worker.join(1)
        # A rebuild that dropped the bus while we waited must not reach a closed connection.
        held.clear();release.clear();worker=threading.Thread(target=refresh);worker.start();held.wait(1)
        def rebuild():service.bus=None;release.set()
        threading.Timer(.1,rebuild).start()
        with self.assertRaisesRegex(ConnectionError,'unavailable'):service.command('answer')
        self.assertEqual(call.Answer.call_count,1);worker.join(1)

    def test_worker_retries_startup_and_rebuilds_after_ofono_restart(self):
        service=PhoneCalls();service.enabled=True;service.stop=FastStop();service.refresh_interval=0
        bus=Mock();attempts=[];seen=[]
        def system_bus(**_):
            attempts.append(1)
            if len(attempts)==1:raise LostError('org.freedesktop.DBus.Error.ServiceUnknown')
            return bus
        def refresh():
            seen.append((service.snapshot()['error'],service.bus,service.modem))
            service.modem=MODEM
            if len(attempts)==2:raise LostError('org.freedesktop.DBus.Error.NameHasNoOwner')
            service.stop.set()
        service._refresh=refresh
        with patch.dict(sys.modules,fake_modules(system_bus)):service._run()
        self.assertEqual(len(attempts),3)
        self.assertEqual(seen,[('The installed oFono calling service is unavailable',bus,None)]*2)
        self.assertEqual(bus.close.call_count,2)
        self.assertEqual(bus.add_signal_receiver.call_count,6)
        self.assertEqual(bus.add_signal_receiver.return_value.remove.call_count,6)
        self.assertIsNone(service.bus);self.assertIsNone(service.modem)

    def test_repeated_dbus_failures_leave_loop_but_missing_phone_does_not(self):
        service=PhoneCalls();service.enabled=True;service.stop=FastStop();service.refresh_interval=0
        bus=Mock();errors=[ConnectionError('no phone')]*10+[RuntimeError('stale proxy')]*MAX_FAILURES
        def refresh():
            if not errors:service.stop.set();self.fail('loop did not restart')
            raise errors.pop(0)
        service._refresh=refresh
        with patch.dict(sys.modules,fake_modules(lambda **_:bus)):service._run_once()
        self.assertEqual(errors,[]);self.assertFalse(service.stop.is_set())
        self.assertEqual(service.snapshot()['error'],'The installed oFono calling service is unavailable')
        bus.close.assert_called_once_with();self.assertIsNone(service.bus)

    def test_call_signals_are_scoped_and_snapshot_clears_on_removal(self):
        service,manager,_,_,_=self.fixture()
        service._refresh();service._refresh()
        manager.GetCalls.assert_called_once_with(timeout=3)
        service._added(CALL,{'State':'incoming','LineIdentification':'123456'},path='/other/modem')
        self.assertEqual(service.snapshot()['call']['count'],0)
        service._added(CALL,{'State':'incoming','LineIdentification':'123456'},path=MODEM)
        self.assertEqual(service.snapshot()['call']['status'],'incoming')
        service._changed('State','active',path=CALL)
        self.assertEqual(service.snapshot()['call']['state'],3)
        service._removed(CALL,path=MODEM)
        self.assertEqual(service.snapshot()['call']['number'],'')
        self.assertEqual(service.snapshot()['call']['count'],0)

    def test_disabled_service_never_dials_and_multiple_modems_are_rejected(self):
        with self.assertRaises(ConnectionError):PhoneCalls().command('dial','123456',True)
        service,manager,_,_,_=self.fixture()
        service.modems.GetModems.return_value*=2
        with self.assertRaises(ConnectionError):service.command('dial','123456',True)
        manager.Dial.assert_not_called()
