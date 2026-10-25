# OTA acceptance test — 25 October 2026

This records a real reference-Pi test, separately from mocked/UI-fixture checks. The test is **incomplete** until activation, native startup health and rollback have been exercised. A successfully built release is not proof of a successful installation.

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
rollback. See [installer acceptance](INSTALL_VERIFICATION.md). The checklist below
retains the actual incomplete OTA status; parked confirmation is now established.

## Remaining acceptance

- [x] Confirm the vehicle is parked.
- [ ] Prepare/activate a release through the real app on the newly installed baseline.
- [ ] Verify the native process comes from the managed release, reports the exact installed SHA, reaches UI readiness and leaves pending verification only after the normal stability gate.
- [ ] Restore the previous baseline, verify its actual process/source identity, then reinstall the prepared release.
- [ ] Reboot normally and verify that boot startup selects the managed release and retains preferences.
- [x] Restore the original automatic recording and update preferences while waiting for activation; no sessions were deleted.
- [ ] Recheck recording/settings integrity after installation, rollback and reboot.
- [ ] Test actual automatic activation with fresh real zero-speed/zero-RPM data when vehicle hardware is available.
- [ ] Test a client Wi-Fi Internet route separately from car-hotspot mode, and controlled network/power interruption recovery. No abrupt power cut or corruption of the working installation is justified by the current results.

The install-dialog action was blocked by automatic approval review because the parked state had not yet been explicitly confirmed. The earlier authorization to save the recording did not establish that prerequisite. No bypass or alternate activation path was used. See [OTA operation and recovery](OTA_UPDATES.md) for the normal behavior and [backend rules](backend-rules.md) for trust boundaries.
