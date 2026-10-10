import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from audio_settings import AudioSettings, DEFAULTS, validate_audio

class Runtime:
    enabled=True
    audio_options=None
    def __init__(self): self.commands=[]; self.applied=None
    def apply_audio(self,data): self.commands.append(copy.deepcopy(data)); self.applied=copy.deepcopy(data)
    def snapshot(self): return {'available':True,'audioDSP':self.applied}

class AudioTests(unittest.TestCase):
    def test_invalid_bands_and_nonfinite_values_are_rejected(self):
        for value in [[0]*14,[0]*16,[True]*15,[float('nan')]*15,[float('inf')]*15,[13]*15,['0']*15]:
            with self.subTest(value=str(value[:1])):
                with self.assertRaises(ValueError): validate_audio({'equalizer':value})

    def test_unknown_fields_presets_and_invalid_balance_are_rejected(self):
        for value in [{},{'command':'sh'},{'volume':90},{'preset':'../x'},{'preset':[]},{'balance':True},{'balance':1.2},{'balance':101}]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError): validate_audio(value)

    def test_settings_survive_reload_and_preserve_untouched_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'audio.json'; runtime=Runtime(); settings=AudioSettings(runtime,file)
            result=settings.save({'equalizer':[6]*15,'preset':'Rock'})
            self.assertTrue(result['saved']); self.assertTrue(result['applied'])
            settings.save({'balance':-25})
            reopened=AudioSettings(Runtime(),file)
            self.assertEqual(reopened.data,{'equalizer':[6]*15,'balance':-25,'preset':'Rock'})
            self.assertEqual(runtime.audio_options,reopened.data)

    def test_manual_band_adjustment_becomes_custom(self):
        with tempfile.TemporaryDirectory() as directory:
            settings=AudioSettings(Runtime(),Path(directory)/'audio.json')
            self.assertEqual(settings.save({'equalizer':[0]*15})['settings']['preset'],'Custom')

    def test_save_failure_rolls_back_runtime_and_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime=Runtime(); settings=AudioSettings(runtime,Path(directory)/'audio.json')
            with patch('audio_settings.save_json',side_effect=OSError('disk full')):
                with self.assertRaises(OSError): settings.save({'balance':100})
            self.assertEqual(runtime.commands[-1],DEFAULTS)
            self.assertEqual(settings.data,DEFAULTS)

    def test_unavailable_runtime_cannot_acknowledge_or_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'audio.json'; runtime=Runtime(); settings=AudioSettings(runtime,file)
            with patch.object(runtime,'apply_audio',side_effect=ConnectionError('offline')):
                with self.assertRaises(ConnectionError): settings.save({'balance':25})
            self.assertFalse(file.exists()); self.assertEqual(settings.data,DEFAULTS)

    def test_invalid_or_oversized_saved_data_defaults_to_flat(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'audio.json'
            for text in ['{"equalizer":[true]}','x'*2049]:
                file.write_text(text)
                self.assertEqual(AudioSettings(Runtime(),file).data,DEFAULTS)

    def test_snapshot_isolated_from_mutation_and_confirmation_is_real(self):
        runtime=Runtime(); settings=AudioSettings(runtime,Path('missing-audio-preferences'))
        snapshot=settings.snapshot(); self.assertFalse(snapshot['applied'])
        snapshot['settings']['equalizer'][0]=12
        self.assertEqual(settings.data['equalizer'][0],0)

if __name__=='__main__': unittest.main()
