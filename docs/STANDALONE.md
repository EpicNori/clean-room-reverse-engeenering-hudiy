# Independent engine verification

Checked on the owner's Raspberry Pi 5, aarch64 Debian 12 Bookworm/labwc, Qt 6.4, 1280×720. These checks refer to our native executable, separately from historical tests of the licensed Hudiy bridge.

## Verified on our engine

- Pinned GPL protocol library and our Qt/libusb/FFmpeg executable compile. The initial 640×480 startup bug was corrected using the current screen and delayed fullscreen request.
- Our fullscreen process owns the Python backend and private Unix IPC. Proprietary Hudiy was stopped, its API port 44405 was absent, and our phone session still displayed genuine wireless Android Auto video.
- Thousands of H.264 frames were decoded. PCM audio bytes were received and written; this proves transport/output activity, not audible quality.
- Our taskbar remained below projection. Dashboard and Applications switched to our interface without ending the phone session. An injected single touch opened Android Auto's application launcher.
- With automatic opening off, the connected phone supplied background data. Manual Resume opened projection. Android Auto Quit prevented automatic reopening; later Resume reconnected real video through our handoff.
- Taskbar disabled used full 1280×720 projection. Taskbar enabled restored our bar. Changing this option now schedules one bounded handoff after session shutdown; reconnection was observed.
- Android Auto Night displayed dark Maps. Common was restored. Physical brightness changed the kernel backlight to 25/31 and back to 31/31.
- Phone title, artist, advancing position and cover art reached our dashboard. Unknown duration now displays an em dash; a regression test checks the unknown-timeline distinction.
- A real OS reboot started our independent app. Proprietary Hudiy and its OBD example did not start. Layout, refresh, projection, wireless and OBD preference hashes matched their pre-reboot values.
- The per-paired-phone reconnect switch is separate from automatic opening. Both states were checked through the UI and private saved file. The existing reconnect worker is bounded to one attempt per device per 30 seconds and loads saved choices at startup.
- Real USB projection now decodes H.264 frames and receives PCM bytes, with our taskbar beneath Maps/Spotify. Capture 344 records wired video. The corrected accessory manufacturer/model is Android / Android Open Automotive Protocol.
- Reinstating the audio-input protocol descriptor fixed the phone closing immediately after service discovery on both USB and wireless. Capture 345 records live wireless video after the fix: more than 900 frames and 6 MiB audio received. The Pi has no usable microphone; capture requests return failure rather than sending invented audio.
- USB software reconnect was checked with the hotspot still enabled: pausing the competing wireless bootstrap restored wired projection without a cable unplug. Android Auto Quit then reported disconnected/hidden; Resume produced more than 880 fresh frames. Captures 346–347 record these checks.
- Switching explicitly from USB to Wi-Fi restored more than 940 wireless frames. Dashboard then received Android Auto title/cover art/playing status while projection stayed connected but hidden; unknown duration displayed an em dash (capture 348). Proprietary Hudiy remained absent and port 44405 was not listening.
- Current checks pass 116 backend tests, 16 frontend tests, production frontend build, real Pi native compilation and the native DSP CTest. The same signal check passes AddressSanitizer/UndefinedBehaviorSanitizer on the Pi.

Private captures 325–337 record independent projection, taskbar, theme and artwork checks. Capture 322 is the initial sizing failure; 332 is a disconnected transition, not projection proof. Captures 338 onward record post-reboot investigation. Phone data and screenshot pixels remain outside the public repository.

## Reconnection after the reboot

Our app, hotspot and Bluetooth handoff started, but the phone completed negotiation and closed before video. Its screenshot showed communication error 21 concerning a VPN. The owner disabled the VPN. Subsequent investigation identified two receiver bugs: the USB accessory identity did not launch the phone handler, and omitting the audio-input service when hardware was absent caused the phone to close after service discovery. Both were corrected; real USB and wireless video were observed again. This does not yet establish unattended cold-boot or out-of-range recovery.

## Hardware checks still pending

- Required live ELM327 readings: the owner confirms the powered adapter/vehicle is unavailable. Simulated values are not real vehicle evidence.
- Unattended cold boot, physical multitouch, microphone/audible audio, active guided navigation and wireless out-of-range recovery.
- Optional Bluetooth car-radio receiver and audible music/navigation/conversation/incoming-call audio. No receiver is selected for these tests.
- Fresh provisioning of standard BlueZ/PBAP, oFono and PipeWire services. The reference Pi already had those configured. Independent inactive AP preparation is implemented and checked, but activation on a fresh image and complete standard-service provisioning remain unverified; see [hotspot setup](HOTSPOT_SETUP.md).
- Ignition power-loss protection and controlled shutdown require separate hardware work.

No new real call or explicit Play/Next/Pause command was used during this migration. Phone-side track changes are not a playback-control test.

## Native audio integration check

- Our C++ processor preserves Flat bit for bit, gives approximately ±6 dB at a selected band center, retains filter state across split packets, handles both balance extremes, leaves mono speech intact and bounds peaks. Invalid/nonfinite gains are rejected. CTest and sanitizer checks run synthetic samples without phone playback commands.
- The live Pi acknowledged the Flat settings. Saving produced a 0600 private preference file; an actual app restart reloaded the same settings and the native process acknowledged them again.
- The initial quarter-second pending queue overflowed during a live burst. Draining before admission and bounding the remaining queue to one second per channel corrected that check. Over the subsequent 20-second observation, audioBytes advanced from 2,495,616 to 6,153,344, queued bytes stayed around 35–40 KiB, maximum packet size was 8,192 bytes, and audioDroppedBytes remained zero. Wireless video stayed connected/visible/ready with no runtime error. These numbers show processing/output activity, not an audible-radio or microphone test.

## Hotspot preparation and longer audio observation

Our normal-user installer now prepares its own inactive, protected 5 GHz NetworkManager profile and private configuration. An actual temporary profile was persisted/read/deleted through its D-Bus adapter with active connections unchanged, and private settings roundtripped at 0600/0700. Eleven installer tests pass on both development Windows and the Pi. The existing production profile was bound to the expected wlan0 interface without activation/restart; repeated `--apply` reports installed/unchanged. D-Bus omits the default-true autoconnect value in some replies; this was corrected and regression-tested. See [full setup scope](HOTSPOT_SETUP.md).

A subsequent longer real wireless audio observation reported `audioDroppedBytes: 195456` and `Audio output could not keep up`, while projection still had decoded video. This contradicts any broader inference from the earlier zero-drop 20-second check. Sustained audio buffering and audible hardware output remain incomplete; no new Play/Pause/call command was used to obtain this observation.

## Standalone-only source cleanup — 10 October 2026

The owner requires all official Hudiy dependencies to be removed while retaining standard open-source libraries. The legacy API/configuration/audio bridge and its launcher have been removed from production source. Generic private persistence and handshake encoding are in runtime_support.py; optional audio receiver helpers are in audio_route_support.py. Our direct OBD monitor and owned-PID audio route retain their regression checks. All 92 current backend tests pass. The previous 116-test checkpoint included retired tests of the removed bridge.

This is a source cleanup; the earlier Pi video/audio/frame evidence above remains historical evidence of the independent engine. A new Pi deployment and live projection regression check are still needed for this exact revision. Clean-image provisioning of Bluetooth, HFP and audio remains an acceptance requirement.

## Guided installer checks

The fresh-Pi installer is implemented for 64-bit Bookworm/Trixie Desktop. On the existing Pi: package resolution passed in apt simulation, the piped bootstrap passed syntax/read-only checks, an official Node 22.23.3 ARM64 release was checksum-verified/extracted/run, and all 103 current backend checks passed in a clean source snapshot, including 11 installer checks. On Windows, Linux apply-flow/internal-symlink checks are skipped. The old deployment still contained retired bridge files, so its broad discovery failed; the clean-snapshot check excludes those files according to the maintained repository manifest. No sudo package/service/autologin installation was executed against the running reference app. Full freshly flashed image installation/reboot and Trixie compilation remain pending. See [installation scope and recovery](INSTALL.md).
