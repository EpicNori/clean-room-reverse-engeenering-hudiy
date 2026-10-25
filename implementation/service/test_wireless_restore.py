"""Saved car-mode recovery uses fixed, mocked NetworkManager commands."""
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from independent_wireless import IndependentWireless, CONNECTION


class WirelessRestoreTests(unittest.TestCase):
    def settings(self, folder, enabled=True, host=True):
        path=Path(folder)/'wireless.json'
        path.write_text(json.dumps({'enabled':enabled,'ssid':'Test car','passphrase':'test-private-key',
                                    'ipAddress':'192.168.12.1','port':5277}),encoding='utf-8')
        return IndependentWireless(Mock(enabled=host),path)

    def test_disabled_or_preview_never_queries_or_activates_network(self):
        with tempfile.TemporaryDirectory() as folder, patch('independent_wireless.subprocess.run') as run:
            self.settings(folder,enabled=False).restore_enabled()
            self.settings(folder,host=False).restore_enabled()
            run.assert_not_called()

    def test_call_interlock_waits_without_consuming_retry_budget(self):
        with tempfile.TemporaryDirectory() as folder,patch('independent_wireless.subprocess.run') as run:
            settings=self.settings(folder);settings.recovery_allowed=lambda:False
            settings.restore_enabled();run.assert_not_called()
            self.assertEqual(settings.last_restore,float('-inf'))

    def test_active_saved_profile_is_not_restarted(self):
        with tempfile.TemporaryDirectory() as folder, patch('independent_wireless.subprocess.run',return_value=Mock(returncode=0,stdout='activated\n')) as run:
            settings=self.settings(folder)
            settings.restore_enabled()
            run.assert_called_once_with(['nmcli','-g','GENERAL.STATE','connection','show',CONNECTION],capture_output=True,text=True,timeout=5)
            self.assertEqual(settings.snapshot()['error'],'')

    def test_inactive_profile_restores_saved_mode_without_changing_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            settings=self.settings(folder);before=settings.path.read_bytes()
            with patch('independent_wireless.subprocess.run',return_value=Mock(returncode=0,stdout='')) as run:
                settings.restore_enabled()
            self.assertEqual([call.args[0] for call in run.call_args_list],[
                ['nmcli','-g','GENERAL.STATE','connection','show',CONNECTION],
                ['nmcli','connection','modify',CONNECTION,'connection.autoconnect','yes'],
                ['nmcli','connection','up',CONNECTION]])
            self.assertEqual(settings.path.read_bytes(),before)
            settings.projection.reload_wireless.assert_not_called()

    def test_missing_profile_or_late_networkmanager_retries_with_a_bound(self):
        for failure in (OSError('not ready'),subprocess.TimeoutExpired('nmcli',5),None):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as folder:
                settings=self.settings(folder)
                with patch('independent_wireless.time.monotonic',side_effect=[100,129,130]),patch('independent_wireless.subprocess.run') as run:
                    if failure is not None:run.side_effect=failure
                    else:run.return_value=Mock(returncode=10,stdout='')
                    settings.restore_enabled();self.assertTrue(settings.snapshot()['error'])
                    settings.restore_enabled();self.assertEqual(run.call_count,1)
                    run.side_effect=None;run.return_value=Mock(returncode=0,stdout='activated')
                    settings.restore_enabled();self.assertEqual(run.call_count,2)
                self.assertEqual(settings.snapshot()['error'],'')

    def test_status_remains_available_during_activation_and_disable_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            settings=self.settings(folder);entered=threading.Event();release=threading.Event()
            def mode(enabled):
                if enabled:entered.set();release.wait(3)
            with patch.object(settings,'_network_mode',side_effect=mode),patch('independent_wireless.subprocess.run',return_value=Mock(returncode=0,stdout='')):
                restore=threading.Thread(target=settings.restore_enabled);restore.start()
                self.assertTrue(entered.wait(2))
                self.assertTrue(settings.snapshot()['enabled'])
                disable=threading.Thread(target=lambda:settings.save(False,True));disable.start()
                release.set();restore.join(3);disable.join(3)
                self.assertFalse(restore.is_alive());self.assertFalse(disable.is_alive())
                self.assertFalse(settings.snapshot()['enabled'])
                with patch('independent_wireless.subprocess.run') as run:
                    settings.restore_enabled();run.assert_not_called()

    def test_preview_does_not_start_worker_and_close_signals_stop(self):
        with tempfile.TemporaryDirectory() as folder,patch('independent_wireless.threading.Thread') as thread:
            settings=self.settings(folder,host=False);settings.start();thread.assert_not_called()
            settings.close();self.assertTrue(settings.stop.is_set())


if __name__=='__main__':unittest.main()
