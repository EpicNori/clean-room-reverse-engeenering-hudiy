"""Private first-run guide progress; no device configuration or live data."""
import json
import sys
import threading
import time
from pathlib import Path
from runtime_support import save_json

GUIDE_VERSION = 1
STEP_COUNT = 19

class OnboardingStore:
    def __init__(self, enabled=False, path=None, clock=time.monotonic, hold=None):
        self.enabled = enabled
        self.path = Path(path) if path else Path.home()/'.local/share/hudiy-recreation/onboarding.json'
        self.clock, self.hold = clock, hold or (lambda active: None)
        self.lock = threading.RLock()
        self.until = 0
        self.state = {'version':GUIDE_VERSION, 'outcome':'pending', 'step':0}
        if enabled:
            try:
                if self.path.stat().st_size > 1024: raise ValueError()
                self.state = self.validate(json.loads(self.path.read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError): pass
    @staticmethod
    def validate(data):
        if (not isinstance(data,dict) or set(data)!={'version','outcome','step'}
            or type(data['version']) is not int or data['version']!=GUIDE_VERSION
            or data['outcome'] not in ('pending','completed','skipped')
            or type(data['step']) is not int or not 0<=data['step']<STEP_COUNT):
            raise ValueError('Invalid guide progress')
        return dict(data)
    def snapshot(self):
        with self.lock:
            return {'available':self.enabled, **self.state, 'active':self.clock()<self.until}
    def command(self,data):
        if not self.enabled: raise ConnectionError('Guide storage requires the Pi application')
        if not isinstance(data,dict): raise ValueError('Invalid guide action')
        action=data.get('action')
        with self.lock:
            if action in ('begin','heartbeat') and set(data)=={'action'}:
                self.hold(True)
                self.until=self.clock()+30
            elif action=='progress' and set(data)=={'action','step'}:
                next_state=self.validate({**self.state,'step':data['step']})
                save_json(self.path,next_state)
                self.state=next_state
            elif action=='finish' and set(data)=={'action','outcome','confirmed'}:
                if data['confirmed'] is not True or data['outcome'] not in ('completed','skipped'):
                    raise ValueError('Confirm finishing or skipping the guide')
                next_state={**self.state,'outcome':data['outcome']}
                save_json(self.path,next_state)
                self.state=next_state
                self.until=0
                # Progress is saved; releasing the native lease is best effort and
                # the runtime's own 30 s lease expiry covers a missed release.
                try:self.hold(False)
                except (OSError,ConnectionError) as exc:print(f'Guide finished; native hold release failed: {exc}',file=sys.stderr,flush=True)
            else: raise ValueError('Unsupported guide action')
            return {**self.snapshot(),'saved':True}
