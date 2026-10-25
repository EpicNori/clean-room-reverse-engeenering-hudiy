"""Terminal helpers must not acquire a controlling PTY in headless OTA tests."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

@unittest.skipUnless(os.name=='posix','Headless POSIX sessions and PTYs are required')
class HeadlessTerminalTests(unittest.TestCase):
    def check_headless(self, selector):
        result=subprocess.run([sys.executable,'-m','unittest',selector],
            cwd=Path(__file__).resolve().parent,start_new_session=True,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=20)
        self.assertEqual(result.returncode,0,
            'Headless child exited '+str(result.returncode)+' (SIGHUP is -1): '+result.stdout)

    def test_installer_confirmation_does_not_acquire_a_controlling_terminal(self):
        self.check_headless('test_pi_installer.PiInstallerTests.test_confirmation_reads_a_real_non_seekable_terminal_without_standard_input')

    def test_hotspot_agent_cleanup_does_not_hang_up_a_headless_runner(self):
        self.check_headless('test_hotspot_authentication.HotspotAuthenticationTests.test_real_agent_is_reaped_when_provisioning_raises')

if __name__=='__main__':unittest.main()
