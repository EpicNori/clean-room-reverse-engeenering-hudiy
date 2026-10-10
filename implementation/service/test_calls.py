import copy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from calls import PhoneCalls,dial_number
from test_bluetooth_devices import OBJECTS,DEVICE

MODEM='/hfp'+DEVICE
CALL=MODEM+'/voicecall01'


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
        manager.GetCalls.return_value=[(CALL,{'State':'active'}),(MODEM+'/voicecall02',{'State':'held'})]
        with self.assertRaises(ConnectionError):service.command('end')
        manager.HangupAll.assert_not_called()

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
