"""Real child-process OTA recovery checks in isolated temporary state."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ota_state import activate, read_json, selection, write_json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'launcher'))
from update_supervisor import supervise

REVISION = 'd'*40


class RealProcessRecoveryTests(unittest.TestCase):
    def scenario(self, behavior):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)/'state'
            baseline = Path(temporary)/'baseline'
            baseline.mkdir()
            candidate = state/'releases'/REVISION
            for name in ('implementation/native/build/hudiy-car-runtime',
                         'implementation/dashboard/dist/client/index.html',
                         'implementation/service/server.py'):
                path = candidate/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('isolated process fixture')
            write_json(candidate/'.ota-release.json', {'revision':REVISION, 'ready':True})
            _, pending = activate(state, REVISION, baseline)
            children = []
            roots = []
            environments = []

            def launch(root, environment):
                roots.append(root)
                environments.append(environment)
                script = 'raise SystemExit(0)'
                if root == candidate:
                    if behavior == 'early-exit':
                        script = 'raise SystemExit(7)'
                    elif behavior == 'no-health':
                        script = 'import time; time.sleep(30)'
                    else:
                        marker = state/('health-'+pending['nonce']+'.json')
                        data = {'nonce':pending['nonce'], 'revision':REVISION, 'ready':True}
                        if behavior == 'wrong-token': data['nonce'] = '0'*32
                        script = ('from pathlib import Path; import time; '
                                  'Path('+repr(str(marker))+').write_text('+repr(json.dumps(data))+'); '
                                  'time.sleep('+('30' if behavior == 'wrong-token' else '1.2')+')')
                process = subprocess.Popen([sys.executable, '-c', script], env=environment,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                children.append(process)
                return process

            try:
                result = supervise(baseline, state, launch, timeout=1.5, stability=.25)
                self.assertEqual(result, 0)
                self.assertTrue(all(child.poll() is not None for child in children))
                self.assertEqual(environments[0]['HUDIY_SOURCE_REVISION'], REVISION)
                self.assertEqual(environments[0]['HUDIY_UPDATE_NONCE'], pending['nonce'])
                saved = selection(state)
                self.assertFalse(saved['pending'])
                if behavior == 'healthy':
                    self.assertEqual(roots, [candidate])
                    self.assertEqual(saved['active'], REVISION)
                    self.assertEqual(read_json(state/'status.json')['phase'], 'current')
                else:
                    self.assertEqual(roots, [candidate, baseline])
                    self.assertIsNone(saved['active'])
                    self.assertNotIn('HUDIY_UPDATE_NONCE', environments[1])
                    self.assertNotIn('HUDIY_SOURCE_REVISION', environments[1])
                    self.assertEqual(read_json(state/'status.json')['phase'], 'rolled-back')
                    self.assertEqual(read_json(state/'status.json')['failedRevision'], REVISION)
            finally:
                from update_supervisor import stop_owned
                for child in children:
                    if child.poll() is None: stop_owned(child)

    def test_real_healthy_child_is_confirmed_and_reaps_normally(self):
        self.scenario('healthy')

    def test_real_early_exit_restores_baseline(self):
        self.scenario('early-exit')

    def test_real_unresponsive_child_is_stopped_and_baseline_restored(self):
        self.scenario('no-health')

    def test_real_wrong_token_cannot_confirm_activation(self):
        self.scenario('wrong-token')


if __name__ == '__main__': unittest.main()
