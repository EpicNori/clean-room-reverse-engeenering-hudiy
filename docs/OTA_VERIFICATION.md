# OTA acceptance test — 25 October 2026

This records successive real reference-Pi tests, separately from mocked/UI-fixture
checks. The later fresh-Trixie run **passed managed activation, native/UI health,
manual rollback, reinstallation and managed-release reboot**. Automatic activation
with actual vehicle data and interruption acceptance remain open. Earlier sections
retain their historical results; see [the current README acceptance report](README_TEST_RESULTS.md).

## Failure reproduced and repair

The installed baseline was `ce71dc0599185d4607ddd114ce8271709db041f1`. Its updater still requested `EpicNori/clean-room-reverse-engeenering-hudiy`. After the repository became `EpicNori/coscarOS`, the old strict redirect handler refused the changed repository path with **Unexpected update download redirect**. The repository rename had been published without migrating that installed updater.

The current public source already uses the new fixed repository/archive root. On this Pi, a reversible backport changed the old updater's exact repository name, archive root and display user-agent. The original file and private settings were backed up, then the owned app was restarted. The independent native baseline and other source files were retained; this was a one-time migration repair, not an OTA acceptance result in itself. Strict HTTPS/host/repository/extraction restrictions remain enabled. The next Check succeeded.

The owner authorized stopping/saving the existing disconnected OBD recording for restart tests. Automatic recording was temporarily disabled to prevent a new connection-attempt recording from blocking each restart; its original settings were saved and restored while activation awaits parked confirmation. Original update preferences were also restored. No diagnostic sessions were deleted. No phone call, playback, pairing, hotspot reconfiguration or OS package installation was performed.

## Real release preparation

The running updater fetched GitHub revision `834903f862fe5be7461a923d230c6dc72f678eff`, extracted it into a separate final managed release directory, ran the real build/test commands and created its ready manifest. It did not build over the running source or borrow the old native executable.

| Check | Observed result |
| --- | --- |
| Fixed GitHub check after migration | Passed; current main revision discovered |
| Source download and extraction | Passed; exact coscarOS archive root accepted |
| Downloaded archive SHA-256 | `09d22c5f5634d8ae864e2ee7f18fa2b5671a8a74e63942077ac2214ebb6f36038` |
| Locked frontend install and production build | Passed on the Pi |
| Frontend tests inside the OTA build | 35 passed |
| Backend tests inside the OTA build | 237 passed on Linux |
| Native Release build | Passed on the Pi; one compile job |
| Native CTest | All six passed |
| Ready manifest | Created only after the checks; incomplete marker removed |
| Preference integrity before activation | All 13 top-level JSON preference files matched backup hashes |
| Actual settings UI | Shows real build/ready status, source revisions and Ethernet route |
| Automatic-idle preference | Saved through the real UI; correctly waits for fresh stationary OBD data when no adapter is connected |
| Manual preference | Restored through the real UI before requesting activation |
| Invalid requests | Actual API rejected missing parked confirmation (400), unknown update action (400), and foreign Origin (403) |
| Installation and renderer health | **Not yet run**; owner subsequently selected clean installer testing |
| Manual rollback and reinstallation | **Not yet run** |
| Persistence through controlled Pi reboot | **Not yet run** |

Ethernet supplied Internet access. `wlan0` was in AP/shared mode for the car hotspot; a GitHub request explicitly bound to it had no Internet route. This is not a client Wi-Fi update test, and the test did not switch off the car hotspot or alter network profiles. Client Wi-Fi and Ethernet policy alternatives retain automated coverage.

## Recovery and regression checks

The local Windows suite passed **241 backend tests with four platform skips**, all **35 frontend/packaging tests**, the production build and the runtime dependency audit (zero known advisories at this check). No coverage percentage was measured.

Four additional [real child-process recovery tests](../implementation/service/test_ota_process_recovery.py) passed on both Windows and the Pi. They use isolated temporary selection/release fixtures and actual owned subprocesses to verify successful health confirmation, early-exit recovery, stopping an unresponsive candidate, and rejection of the wrong health token. They verify process/supervisor behavior, not the real native renderer or vehicle hardware. Existing OTA regressions also cover failed preparation, strict archives, parked/call/recording interlocks, metering and network policy, nonce matching, repeated updates and previous-version selection.

## Subsequent installer test

The owner subsequently confirmed that the vehicle was parked and requested a
clean application uninstall/reinstall before further OTA testing. That test
archived the old baseline/staged release in private recovery storage and installed
a fresh baseline. Its successful boot does not verify managed OTA activation or
rollback. See [installer acceptance](INSTALL_VERIFICATION.md). The checklist below records the later managed-release retest; parked confirmation is established.

## Later fresh-Trixie retest

The updater on the freshly installed `51e0f57` baseline first exposed an unrelated
headless-test SIGHUP failure. The terminal helpers were repaired with `O_NOCTTY`
and real session-leading subprocess regressions. GitHub revision `152596f` then
built with 252 Linux backend tests, 35 frontend tests and six native CTests,
activated and passed normal UI/native health and process-stability gates.

The actual native executable was under that exact managed release. Manual rollback
started the real baseline executable, preserved preference hashes and paused
immediate automatic reapplication. Reinstallation passed health again. Enabling
both Android Auto switches caused wireless projection to open after that restart;
opening Off was restored afterward. A normal Pi reboot selected the managed release
and preserved all seven current top-level preference files. The owner reported no
visual boot flashes. The initial wireless cold boot exposed inactive car mode;
its separate recovery repair and retest are documented in the README report.

Preparation cancellation retained the installed app and ready UI. Automatic-idle
mode waited for fresh stationary OBD evidence when no adapter was available.
A later real active call also caused manual OTA activation to be refused; the test
did not hang up or bypass that interlock. Ethernet carried the actual downloads.

## Remaining acceptance

- [x] Confirm the vehicle is parked.
- [x] Prepare/activate a release through the real app on the newly installed baseline.
- [x] Verify the native process comes from the managed release, reports the exact installed SHA, reaches UI readiness and leaves pending verification only after the normal stability gate.
- [x] Restore the previous baseline, verify its actual process/source identity, then reinstall the prepared release.
- [x] Reboot normally and verify that boot startup selects the managed release and retains preferences.
- [x] Restore the original automatic recording and update preferences while waiting for activation; no sessions were deleted.
- [x] Compare current fresh-image preferences across activation/rollback and all seven top-level JSON files across reboot; no saved recording was deleted. Live vehicle recording remains untested.
- [ ] Test actual automatic activation with fresh real zero-speed/zero-RPM data when vehicle hardware is available.
- [ ] Test a client Wi-Fi Internet route separately from car-hotspot mode, and controlled network/power interruption recovery. No abrupt power cut or corruption of the working installation is justified by the current results.

The install-dialog action was blocked by automatic approval review because the parked state had not yet been explicitly confirmed. The earlier authorization to save the recording did not establish that prerequisite. No bypass or alternate activation path was used. See [OTA operation and recovery](OTA_UPDATES.md) for the normal behavior and [backend rules](backend-rules.md) for trust boundaries.


## Hotspot repair power-on retest

The owner explained that the final unreachable interval was a switched-off Pi.
After power-on, `e479050` started through the normal car session, was current with
no pending restart, restored the enabled protected hotspot and connected wireless
Android Auto with decoded video ready and no error. Only USB root hubs were present.
All seven private preference hashes matched. The owner confirmed automatic opening,
then manually returned to the dashboard. Temporary settings/layouts were restored;
music refresh follows the later one-second request. See [the device report](README_TEST_RESULTS.md).
