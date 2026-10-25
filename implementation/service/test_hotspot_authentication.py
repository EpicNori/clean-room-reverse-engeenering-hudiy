"""Real owned-process checks for the installer's scoped terminal auth agent."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE=Path(__file__).resolve().parents[1]/'launcher/provision_hotspot.py'
spec=importlib.util.spec_from_file_location('hotspot_terminal_auth',MODULE)
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

class HotspotAuthenticationTests(unittest.TestCase):
    def test_missing_terminal_never_starts_an_agent(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup.shutil,'which',return_value='/usr/bin/pkttyagent'), patch.object(setup.subprocess,'Popen') as start:
            with setup.terminal_authentication(str(Path(folder)/'missing')) as active:
                self.assertFalse(active)
            start.assert_not_called()

    def test_missing_agent_keeps_existing_authorization_behavior(self):
        with patch.object(setup.shutil,'which',return_value=None), patch.object(setup.subprocess,'Popen') as start:
            with setup.terminal_authentication() as active:self.assertFalse(active)
            start.assert_not_called()

    @unittest.skipUnless(os.name=='posix','Process notification uses POSIX inherited descriptors')
    def test_real_agent_is_reaped_when_provisioning_raises(self):
        self.agent_lifecycle(True)

    @unittest.skipUnless(os.name=='posix','Process notification uses POSIX inherited descriptors')
    def test_unresponsive_real_agent_times_out_and_is_reaped(self):
        self.agent_lifecycle(False)

    def agent_lifecycle(self, notify):
        real_popen=subprocess.Popen;children=[];commands=[]
        def start(command,**kwargs):
            commands.append(command)
            fd=int(command[command.index('--notify-fd')+1])
            script=('import os,time; '+('os.close('+str(fd)+'); ' if notify else '')+'time.sleep(30)')
            child=real_popen([sys.executable,'-c',script],**kwargs)
            children.append(child);return child
        master,slave=os.openpty()
        try:
            with patch.object(setup.shutil,'which',return_value='/usr/bin/pkttyagent'),patch.object(setup.subprocess,'Popen',side_effect=start):
                if notify:
                    with self.assertRaisesRegex(RuntimeError,'provision failed'):
                        with setup.terminal_authentication(os.ttyname(slave)) as active:
                            self.assertTrue(active);self.assertIsNone(children[0].poll())
                            raise RuntimeError('provision failed')
                else:
                    with self.assertRaisesRegex(setup.SetupError,'did not become ready'):
                        with setup.terminal_authentication(os.ttyname(slave),startup_timeout=.1):
                            self.fail('Unregistered agent must not allow provisioning')
            self.assertEqual(len(children),1)
            self.assertIsNotNone(children[0].poll())
            self.assertIn('--fallback',commands[0])
            self.assertEqual(commands[0][commands[0].index('--process')+1],str(os.getpid()))
        finally:
            os.close(master);os.close(slave)
            for child in children:
                if child.poll() is None:child.kill();child.wait(timeout=3)

if __name__=='__main__':unittest.main()
