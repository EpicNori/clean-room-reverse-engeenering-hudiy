import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from input_settings import InputSettings, DEFAULTS, validate_input
from standalone_projection import StandaloneProjection
from layout import validate_layout, DEFAULT_LAYOUT

class Runtime:
    enabled=True
    input_options=None
    def __init__(self):
        self.available=True; self.commands=[]
        self.native={'configured':True,'settings':dict(DEFAULTS),'devices':[
            {'id':'dXNiLW1pYw','name':'USB microphone','supported':True,'isDefault':True},
            {'id':'YmFk','name':'Unsupported microphone','supported':False,'isDefault':False}],
            'captureActive':False,'microphoneAvailable':True}
    def snapshot(self):return {'available':self.available,'audioInput':copy.deepcopy(self.native)}
    def apply_input(self,data):self.commands.append(dict(data))

class InputTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'input.json';self.runtime=Runtime()
        self.settings=InputSettings(self.runtime,self.path)

    def test_rejects_invalid_fields_commands_types_ranges_and_paths(self):
        for value in ({},[],None,{'device':'/dev/audio'},{'device':'x;shutdown'},{'device':'x'*257},
                      {'device':False},{'volume':True},{'volume':50.5},{'volume':-1},{'volume':101},
                      {'volume':float('nan')},{'muted':1},{'command':'shell'}):
            with self.subTest(value=value),self.assertRaises(ValueError):validate_input(value)

    def test_persistence_reload_and_partial_save_preserve_selected_device(self):
        self.settings.save({'device':'dXNiLW1pYw','volume':65})
        self.settings.save({'muted':True})
        expected={'device':'dXNiLW1pYw','volume':65,'muted':True}
        self.assertEqual(json.loads(self.path.read_text()),expected)
        reopened=InputSettings(Runtime(),self.path)
        self.assertEqual(reopened.snapshot()['settings'],expected)
        self.assertEqual(reopened.projection.input_options,expected)

    def test_saved_missing_microphone_stays_selected_and_can_be_muted(self):
        self.settings.save({'device':'dXNiLW1pYw'})
        self.runtime.native.update(devices=[],microphoneAvailable=False,error='Selected microphone unavailable')
        result=self.settings.save({'muted':True})
        self.assertEqual(result['settings']['device'],'dXNiLW1pYw')
        self.assertFalse(result['microphoneAvailable']);self.assertFalse(result['captureActive'])
        self.assertEqual(self.settings.save({'device':'default'})['settings']['device'],'default')

    def test_unknown_or_unsupported_device_rejected_without_sending_or_saving(self):
        for identifier in ('unknown','YmFk'):
            with self.assertRaises(ValueError):self.settings.save({'device':identifier})
        self.assertFalse(self.path.exists());self.assertEqual(self.runtime.commands,[])

    def test_save_is_not_capture_and_only_native_echo_is_applied(self):
        result=self.settings.save({'volume':20,'muted':True})
        self.assertFalse(result['applied']);self.assertFalse(result['captureActive'])
        self.runtime.native['settings']=dict(result['settings'])
        self.assertTrue(self.settings.snapshot()['applied'])
        snapshot=self.settings.snapshot();snapshot['devices'][0]['name']='tampered'
        self.assertEqual(self.settings.snapshot()['devices'][0]['name'],'USB microphone')

    def test_offline_or_unconfigured_native_cannot_persist_or_claim_capture(self):
        self.runtime.native['captureActive']=True
        self.runtime.available=False
        self.assertFalse(self.settings.snapshot()['captureActive'])
        with self.assertRaises(ConnectionError):self.settings.save({'muted':True})
        self.runtime.available=True;self.runtime.native['configured']=False
        with self.assertRaises(ConnectionError):self.settings.save({'muted':True})
        self.assertFalse(self.path.exists())

    def test_disk_failure_restores_previous_runtime_and_memory(self):
        with patch('input_settings.save_json',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.settings.save({'volume':10})
        self.assertEqual(self.runtime.commands[-1],DEFAULTS)
        self.assertEqual(self.settings.data,DEFAULTS);self.assertEqual(self.runtime.input_options,DEFAULTS)

    def test_runtime_send_failure_never_acknowledges_or_writes(self):
        with patch.object(self.runtime,'apply_input',side_effect=ConnectionError('offline')):
            with self.assertRaises(ConnectionError):self.settings.save({'volume':10})
        self.assertFalse(self.path.exists());self.assertEqual(self.settings.data,DEFAULTS)

    def test_corrupt_or_oversized_preferences_load_defaults(self):
        for text in ('x'*2049,'{"muted":1}','[]','{"device":"/dev/audio"}'):
            self.path.write_text(text)
            self.assertEqual(InputSettings(Runtime(),self.path).data,DEFAULTS)

    def test_native_input_commands_and_snapshot_are_separate_from_output_dsp(self):
        projection=StandaloneProjection(socket_path=Path(self.folder.name)/'native.sock',preferences=Path(self.folder.name)/'projection.json')
        projection.enabled=True;projection.available=True;projection.sock=Mock()
        projection.apply_input(DEFAULTS)
        self.assertEqual(json.loads(projection.sock.sendall.call_args.args[0]),{'operation':'audio-input','settings':DEFAULTS})
        projection._event({'event':'state','connected':False,'visible':False,'audioInput':self.runtime.native})
        snapshot=projection.snapshot();snapshot['audioInput']['settings']['muted']=True
        self.assertFalse(projection.snapshot()['audioInput']['settings']['muted'])
        self.assertEqual(projection.snapshot()['audioDSP'],{})

    def test_audio_menu_migration_preserves_personal_layout_order(self):
        old=copy.deepcopy(DEFAULT_LAYOUT);old['menus']['Audio']=['presets','sound','equalizer']
        old['taskbar'].insert(2,'sound')
        migrated=validate_layout(old)
        self.assertEqual(migrated['menus']['Audio'],['presets','sound','equalizer','audio-input','music-settings'])
        self.assertEqual(migrated['taskbar'],old['taskbar'])

if __name__=='__main__':unittest.main()
