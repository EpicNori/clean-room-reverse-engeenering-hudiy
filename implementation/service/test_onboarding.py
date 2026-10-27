import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from onboarding import OnboardingStore,STEP_COUNT

class OnboardingTests(unittest.TestCase):
    def test_new_device_resume_complete_and_replay_preserves_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'guide.json';hold=Mock();store=OnboardingStore(True,path,hold=hold)
            self.assertEqual(store.snapshot()['outcome'],'pending')
            store.command({'action':'begin'});self.assertTrue(store.snapshot()['active']);hold.assert_called_with(True)
            store.command({'action':'progress','step':5})
            self.assertEqual(OnboardingStore(True,path).snapshot()['step'],5)
            store.command({'action':'finish','outcome':'completed','confirmed':True})
            self.assertFalse(store.snapshot()['active']);hold.assert_called_with(False)
            again=OnboardingStore(True,path,hold=hold)
            self.assertEqual(again.snapshot()['outcome'],'completed')
            again.command({'action':'begin'})
            self.assertEqual(OnboardingStore(True,path).snapshot()['outcome'],'completed')
    def test_skip_requires_exact_confirmation_and_bounded_body(self):
        store=OnboardingStore(True,Path('/unused'))
        for data in ({'action':'finish','outcome':'skipped'}, {'action':'finish','outcome':'skipped','confirmed':1}, {'action':'begin','path':'/tmp/a'}, {'action':'progress','step':True}, {'action':'progress','step':STEP_COUNT}, {'action':'progress','step':-1}):
            with self.assertRaises(ValueError):store.command(data)
    def test_failed_disk_write_keeps_progress_and_guide_open(self):
        hold=Mock();store=OnboardingStore(True,Path('/unused'),hold=hold)
        store.command({'action':'begin'});before=store.snapshot()
        with patch('onboarding.save_json',side_effect=OSError('private path')):
            with self.assertRaises(OSError):store.command({'action':'finish','outcome':'skipped','confirmed':True})
        self.assertEqual(store.snapshot(),before);hold.assert_called_once_with(True)
    def test_lease_expires_after_renderer_crash_and_heartbeat_renews(self):
        now=[0];store=OnboardingStore(True,clock=lambda:now[0])
        store.command({'action':'begin'});now[0]=20
        store.command({'action':'heartbeat'});now[0]=35
        self.assertTrue(store.snapshot()['active']);now[0]=51
        self.assertFalse(store.snapshot()['active'])
    def test_corrupt_oversized_and_disabled_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'guide.json'
            for text in ('broken','{"version":1,"outcome":"completed","step":true}','x'*1025):
                path.write_text(text)
                self.assertEqual(OnboardingStore(True,path).snapshot()['outcome'],'pending')
            with self.assertRaises(ConnectionError):OnboardingStore(False,path).command({'action':'begin'})
if __name__=='__main__':unittest.main()
