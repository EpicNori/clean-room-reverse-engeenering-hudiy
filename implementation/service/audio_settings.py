"""Validated, durable EQ/balance for our native projection PCM output."""
import copy
import json
import math
from pathlib import Path
import sys
import threading
from runtime_support import save_json

PRESETS = {'Flat','Pop','Rock','Jazz','Classical','Bass boost','Voice','Custom'}
DEFAULTS = {'equalizer': [0]*15, 'balance': 0, 'preset': 'Flat'}

def validate_audio(data):
    if not isinstance(data,dict) or not data or set(data)-set(DEFAULTS):
        raise ValueError('Choose equalizer, balance or preset')
    if 'equalizer' in data:
        bands=data['equalizer']
        if not isinstance(bands,list) or len(bands)!=15 or any(
                type(x) not in (int,float) or not math.isfinite(x) or not -12<=x<=12 for x in bands):
            raise ValueError('Equalizer requires 15 finite gains from -12 to 12 dB')
    if 'balance' in data and (type(data['balance']) is not int or not -100<=data['balance']<=100):
        raise ValueError('Balance must be an integer from -100 to 100')
    if 'preset' in data and (not isinstance(data['preset'],str) or data['preset'] not in PRESETS):
        raise ValueError('Unknown audio preset')
    return copy.deepcopy(data)

class AudioSettings:
    def __init__(self,projection,path=None):
        self.projection=projection
        self.enabled=projection.enabled and hasattr(projection,'apply_audio')
        self.path=path or Path.home()/'.local/share/hudiy-recreation/audio.json'
        self.lock=threading.RLock()
        self.data=copy.deepcopy(DEFAULTS)
        if self.enabled:
            try:
                if self.path.is_symlink() or self.path.stat().st_size>2048: raise ValueError('Invalid audio preference file')
                self.data.update(validate_audio(json.loads(self.path.read_text(encoding='utf-8'))))
            except (OSError,ValueError,TypeError): pass
            projection.audio_options=copy.deepcopy(self.data)

    def snapshot(self):
        with self.lock:
            state=self.projection.snapshot() if self.enabled else {}
            return {'enabled':self.enabled,'settings':copy.deepcopy(self.data),
                'available':state.get('available',False),
                'applied':state.get('audioDSP')==self.data}

    def save(self,patch):
        if not self.enabled: raise ConnectionError('Projection equalizer requires the independent Pi application')
        validated=validate_audio(patch)
        with self.lock:
            previous=copy.deepcopy(self.data)
            updated={**previous,**validated}
            if 'equalizer' in patch and 'preset' not in patch: updated['preset']='Custom'
            self.projection.apply_audio(updated)
            try: save_json(self.path,updated)
            except OSError:
                # Report the storage failure, not a rollback hiccup it may cause.
                try: self.projection.apply_audio(previous)
                except (OSError,ValueError) as exc: print(f'Audio rollback failed: {exc}',file=sys.stderr,flush=True)
                raise
            self.data=updated
            self.projection.audio_options=copy.deepcopy(updated)
            return {**self.snapshot(),'saved':True,'message':'Audio settings saved'}
