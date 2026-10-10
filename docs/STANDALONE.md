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
- All 96 backend tests, 14 frontend tests, production frontend build and real Pi native compilation pass.

Private captures 325–337 record independent projection, taskbar, theme and artwork checks. Capture 322 is the initial sizing failure; 332 is a disconnected transition, not projection proof. Captures 338 onward record post-reboot investigation. Phone data and screenshot pixels remain outside the public repository.

## Reconnection after the reboot

Our app, hotspot and Bluetooth handoff started, but the phone completed negotiation and closed before video. Its screenshot showed communication error 21 concerning a VPN. The owner disabled the VPN. Subsequent investigation identified two receiver bugs: the USB accessory identity did not launch the phone handler, and omitting the audio-input service when hardware was absent caused the phone to close after service discovery. Both were corrected; real USB and wireless video were observed again. This does not yet establish unattended cold-boot or out-of-range recovery.

## Hardware checks still pending

- Required live ELM327 readings: the owner confirms the powered adapter/vehicle is unavailable. Simulated values are not real vehicle evidence.
- Unattended cold boot, physical multitouch, microphone/audible audio, active guided navigation and wireless out-of-range recovery.
- Optional Bluetooth car-radio receiver and audible music/navigation/conversation/incoming-call audio. No receiver is selected for these tests.
- Fresh provisioning of standard BlueZ/PBAP, oFono and PipeWire services. The reference Pi already had those configured. Fresh protected AP setup is a documented prerequisite and is not automated.
- Ignition power-loss protection and controlled shutdown require separate hardware work.

No new real call or explicit Play/Next/Pause command was used during this migration. Phone-side track changes are not a playback-control test.
