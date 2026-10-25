# README acceptance on the real Pi — 25 October 2026

This records device tests requested by the owner, separately from gallery fixtures
and historical bridge tests. The machine was a Raspberry Pi 5 with 4 GiB RAM,
fresh 64-bit Raspberry Pi OS Desktop Trixie, Qt 6.8.2 and a 1280×720 DSI display.
The paired test phone was the owner's Galaxy Z Fold4. No powered ELM327, external
microphone or optional radio receiver was available. The vehicle was confirmed
parked. No real call was placed during this run.

## Source and fixes

The public installer had installed baseline
`51e0f57fddb6126666de8f7786322bd48fe04c60`. Subsequent builds and activations used
immutable GitHub source revisions, with the actual native executable path checked
on the device. The proprietary Hudiy runtime is not part of this installation.

Three failures were found and repaired:

1. **Missing `pactl` on the fresh image.** The installer now includes
   `pulseaudio-utils`, needed for existing PipeWire/radio-route diagnostics and
   controls. The package was installed on the Pi; no PulseAudio daemon was added.
   Repair: `3bbca162e25c7a0bf8178661a32f79253485a89a`.
2. **Headless OTA backend tests died from SIGHUP.** Opening a PTY slave made the
   session-leading runner acquire a controlling terminal; closing its test master
   killed it. Both affected helpers now use `O_NOCTTY`. Real child-process
   regressions recreate the updater's `start_new_session=True` context. Before the
   repair both isolated tests exited with signal 1; afterward the complete Linux
   suite passed. Repair: `152596f0e6fa2b72a8ad3457f4ca403b91a471ee`.
3. **An enabled car hotspot stayed inactive after boot.** NetworkManager initially
   tried an older client profile before the user-restricted AP was available. The
   app had saved car mode but relied entirely on NetworkManager autoconnect. An
   owned worker now restores only the enabled fixed car profile, leaves an active
   profile alone, waits during calls and retries at most every 30 seconds. Disabled
   car mode stays disabled. Manual changes serialize with recovery while status
   remains responsive. Normal NetworkManager permissions are retained.
   Repair: `e47905062bf687bc1613dd4b52d076b09dbbdf53`.

## Automated verification

| Check | Result and limit |
| --- | --- |
| Final backend suite inside actual Pi OTA preparation | **259 passed**, no skips, in a headless Linux runner |
| Frontend/packaging tests | **35 passed**; production frontend build passed |
| Native ARM64 Release build | Passed; all **six CTests** passed, including in the final hotspot revision's actual OTA build |
| Windows backend | 258 tests run, 10 platform skips, before the final call-interlock regression; all seven new hotspot regressions passed afterward |
| Runtime dependency audit | Zero known advisories at the check; this is not a whole-project security guarantee |
| Silent-sink audio stress | Worker received/wrote 5,819,712 bytes, dropped 0, final queue 0; old diagnostic path dropped 394,368 bytes. Sink underrun diagnostic code 3 was present; no audible-hardware claim |
| Existing isolated process recovery tests | Actual owned subprocess checks cover health success, early exit, timeout cleanup and wrong-token rejection; they do not emulate a physical power cut |

## Real OTA operations

The real updater downloaded, built and prepared `152596f`, then:

- activated it and passed native/UI health and normal process-stability gates;
- verified the running native executable came from that exact managed release;
- compared saved preference hashes successfully;
- rolled back to the actual `51e0f57` baseline executable, with hashes matching;
- verified automatic immediate reapplication of the rolled-back revision was paused;
- reinstalled the prepared release and passed health again;
- rebooted through the normal dedicated car session and selected the managed release.

A real active call correctly blocked a later manual installation until the owner
confirmed it had ended; no call control or interlock bypass was used.
Cancellation during a separate real preparation retained the installed revision and
ready UI. With automatic-idle mode selected and no OBD adapter, installation waited
for fresh stationary OBD evidence. No fake speed/RPM was injected into the real app.
Real automatic activation with fresh vehicle samples remains pending.

The final hotspot repair was published and prepared through the same updater.
Its complete build passed 259 backend tests, 35 frontend tests and six native
CTests. Real activation reported exact revision `e479050`, `current`, no pending
restart, UI readiness and connected/visible decoded wireless video. The normal
Quit test then returned to the desktop. **The final cold reboot has not returned
to the network**: pinned-host SSH to the hostname and last Ethernet address timed
out, and the owner was asked for the physical screen/link state. Therefore the
cold-boot hotspot repair is **not yet accepted**, despite its passing regressions
and successful application activation. It must be repeated when the Pi is reachable.

## Phone, display and interface

| Test | Observed result |
| --- | --- |
| First wireless setup on this fresh image | Paired Fold4, Bluetooth/Wi-Fi, VPN off; USB absent until after successful wireless projection |
| Real projection | Decoded phone video and actual forwarded pointer input into the Android Auto launcher |
| USB projection | After the owner attached USB, the native engine reported USB transport, decoded frames and ready video with no session error |
| Projection geometry | Fullscreen mode hides the coscarOS bar; restoring the setting leaves projection above the bar |
| Background opening policy | Connection On/opening Off kept the dashboard visible while phone data arrived; taskbar Resume opened projection |
| Automatic foreground opening | Connection and opening On survived a real OTA app restart and opened wireless projection automatically; opening Off restored afterward |
| Manual policy | Master Off did not drop an existing session; Quit suppressed retries for 35 observed seconds; opening On alone did not connect; manual Wi-Fi/Resume worked with master Off |
| Bluetooth phonebook | 97 contacts and 100 call-log entries, no favorites; native A–F filter showed 38 of 97, then All restored |
| Spotify | Phone was controlling playback on another Spotify Connect device; changing projected UI and stale phone metadata is not a definitive phone-local media test |
| Notifications/theme | Real volume popup appeared above projection; orange accent propagated across native popup and the two web views; light/dark controls checked; original dark/pink restored |
| Physical brightness | During visible projection, a 50% request reached the quantized panel level (52%); original 97% restored and sysfs inspected |
| Taskbar layout | Context-menu reorder on the actual native taskbar saved on the backend and survived a full reboot |
| My OBD | Actual drag handle swapped speed/RPM tiles; private saved layout survived reboot; missing readings stayed unavailable |
| Logs page | Correct disconnected state and recording/configuration controls; this is not vehicle logging acceptance |
| Microphone without hardware | No-device message, idle capture, saved 70%/muted test preferences applied natively and survived reboot; unsaved edit/Discard checked |
| Refresh intervals | Test values of 3 seconds music and 120 seconds contacts survived reboot |
| Saved configuration | All seven top-level JSON preference hashes matched across the managed-release reboot, including layout, custom OBD, input and refresh settings |
| Normal Quit | Native app/backend exited, owned black background stopped, exactly one desktop panel and file manager started |
| Startup visuals | Owner watched the real reboot and reported “no flashes”; no complete boot video was captured |
| Display orientation | Existing owner's rotation retained; no remote screenshot claim about finger alignment |

The final network loss prevented restoration of temporary acceptance settings.
Pending restoration: automatic opening **On → Off**, music refresh **3 → 5 seconds**,
contacts **120 → 60 seconds**, microphone **70%/muted → 100%/unmuted**, original
OBD Logs/My OBD shortcut order, and original speed/RPM tile order. Private originals
remain in the Pi's test directory. Volume was already restored to 80, brightness
to 97%, and the original dark/pink theme restored. The newly paired phone and
explicitly enabled protected hotspot are intended to remain available.

## Security and privacy checks

The live HTTP API rejected an unknown action (400), foreign Origin (403), foreign
Host (403), oversized body (413), wrong content type (415), and path traversal
(403). Wireless HTTP status omitted password/passphrase. New restoration commands
use a fixed existing profile, ordinary-user authorization, bounded timeouts/retries
and an active-call interlock; they create no new network rule or privileged service.

Remote GUI viewing used a temporary user-private Unix VNC socket reached through
pinned-host SSH and a loopback-only viewer. The screen service was transient and not installed for autostart; the final reboot stops it. The local viewer is closed after testing. Raw phonebook, map/phone screenshots, Wi-Fi credentials and private
preference backups are not committed. Public evidence contains only summarized
counts, source revisions and safe UI state. See [backend rules](backend-rules.md).

## Remaining acceptance and implementation

The following README groups cannot honestly be marked complete by this run:

- **Powered vehicle/ELM327:** required live values, custom PIDs/formulas against the
  actual car, recorder coverage/exports, disconnect/reconnect/staleness and automatic
  OTA activation with fresh stationary evidence. No powered adapter was available.
- **Audio/phone hardware:** USB/Bluetooth mic formats, hotplug, real voice requests,
  incoming calls/conversation audio, optional radio receiver, extended audible
  playback/drift and navigation speech. No suitable external hardware was available.
- **Physical touch:** finger long-press, scrolling/selection, alignment and multitouch.
  Remote mouse drag/input is useful device evidence but cannot replace finger tests.
- **Phone permutations:** USB at boot, full USB switch matrix, multiple/disabled
  phones, contact-sharing denied, range loss and late Bluetooth service recovery.
- **Final recovery:** regain access after the last reboot, accept the hotspot fix across a cold boot and restore the temporary settings listed above.
- **Boot/recovery:** complete recorded power-on sequence, slow/failed native web-view
  loads with Retry/desktop recovery, helper restore and multiple monitors. Existing
  automated checks do not establish the entire physical sequence.
- **Installation/network:** fresh Bookworm, client Wi-Fi Internet rather than the car
  hotspot, controlled network/power interruption and actual ignition power hardware.
- **Unimplemented features:** CarPlay/Autobox, supported FM tuner playback, phone
  notification import and a real marketplace are development tasks, not passed tests.
- **Legal distribution review:** GUI expression, name/terms and dependency/binary
  obligations still need independent review; successful technical tests do not give
  legal clearance.

The [README checklist](../README.md#remaining-work) preserves these limits.
[Installer acceptance](INSTALL_VERIFICATION.md), [OTA acceptance](OTA_VERIFICATION.md)
and [black startup](BLACK_STARTUP.md) provide the separate historical evidence.
