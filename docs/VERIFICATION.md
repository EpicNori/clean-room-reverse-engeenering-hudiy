# Verification record

This is a public summary of checks completed during development through 2026-10-10. Raw evidence remains local because screenshots and runtime responses can contain contact details, phone metadata, locations and device identifiers.

## Reference environment

- Raspberry Pi, Debian 12 Bookworm, labwc/Wayland and a 1280×720 touchscreen.
- Installed Hudiy 1.24, native API 1.3.
- Android test phone with USB Android Auto, Bluetooth PBAP/HFP/AVRCP and later wireless projection.
- A paired classic Bluetooth Serial Port ELM327 adapter, unreachable during the live-reading checks.

The OS was not upgraded to Raspberry Pi OS 13. There is no claim that other runtime/OS combinations have passed these hardware checks.

## Software checks

The publication source passes 79 Python backend tests and 13 JavaScript frontend/packaging tests. The frontend production build passes. The production npm audit reports zero known vulnerabilities at the time of the check.

Backend tests cover native protocol framing, negotiation/replay, media source changes, read-only sensor decoding/automatic recovery, bounded retries, serial precedence, Host/origin/traversal/injection rejection, exact action validation, durable private preferences, native configuration preservation, save/send rollback, layout geometry, USB recovery, PBAP session ownership, HFP controls with mocks, receiver stream ownership and backlight validation.

Frontend checks cover layout normalization/pinning/reordering, essential navigation retention, active-media ownership and source changes, unknown timelines, static hosting behavior/build output and name filtering. Filter tests cover accented, unnamed, numeric and non-Latin entries, complete partitioning and preservation of the source order and number data. Offline audio checks exercise the same Web Audio graph used for local-file playback.

Software tests do not establish a real ELM327 connection, vehicle readings, projection video, an actual conversation or audible receiver output.

## Actual device/UI checks

| Area | Observed result | Limit |
| --- | --- | --- |
| Launch | Native fullscreen dashboard on the Pi | Tested reference environment only |
| Boot | An actual OS reboot started the configured host, restored the hotspot and reconnected background wireless Android Auto | Ignition power loss/cold start not tested |
| Persistence | Layout, refresh, projection, brightness and Bluetooth reconnect file hashes matched before/after restart; shortcuts survived the reboot | Does not simulate sudden power loss during a write |
| Quit | Application Quit returned to the desktop and ended the owning runtime/host without losing saved preferences | Standalone Qt has a separate maintenance shortcut |
| Touch/layout | Scrolling did not mark text; compact/portrait layouts and long-press pin/reorder were usable | Further hardware/display combinations need checks |
| Contacts | 94 contacts, 100 recent calls, zero favorites from the phone; recovery after the worker's OBEX session disappeared | Empty Favorites is the phone's result, not invented data |
| Filters | A–F 37, G–L 18, M–R 21, S–Z 18, # zero; All 94. Search removed from Contacts/Favorites/Call log | Counts belong to one test phone, not a bundled dataset |
| Pair | One main Pair device action opened the installed agent and automatic discovery | No real new pairing/unpairing was performed in final menu QA |
| Sound | Receiver controls remained visible with the long accessory-specific paragraphs removed | No optional receiver was selected for the final checks |
| Phone call | One explicitly authorized outgoing call reached dialing/alerting, was hung up, and no call remained | Incoming call, active conversation and conversation audio unverified |
| Bluetooth music | Real title/artist/album and playback-state changes; authorized short Play/Pause check | Bluetooth artwork and audible car output unverified |
| Android Auto data | Real titles/artwork/timelines on the recreated dashboard with automatic opening off | Phone/runtime must actually supply fresh metadata |
| Wireless Android Auto | Actual maps/music video above the taskbar, using a 5 GHz Pi hotspot and no USB accessory | Out-of-range/repeated driving reconnect unverified |
| Quit/Resume | Wireless socket closed on Quit; corrected Resume restored a connection and actual video | A splash or connection request alone was not counted as successful projection |
| Day/Night | Native Day/Night changed real maps to light/dark; Common followed the Pi theme; restoration survived app restart | Requires compatible native API |
| Physical brightness | Existing kernel backlight changed from 31/31 to 24/31, then restored/saved at 100%, including during real projection | Panel backlight support and existing permissions required |
| OBD settings | Native adapter/channel selection and read-only automatic-monitor waiting state | Adapter stayed disconnected; no live sensor proof |
| Gauges | Corrected code-rendered geometry/fonts and moving indicators with explicit Demo data; Demo off afterward | Demo verification is not vehicle evidence |

Browser layouts were inspected between 320×568 and 1920×720. The latest contact filters have six equal columns at the reference width and three columns on compact screens, with 48px minimum targets and no horizontal page overflow. Both dark preview and light native menus were checked; final state returned to Dashboard.

## Outstanding acceptance checks

1. Required live Bluetooth ELM327 readings, supported PID availability and drop/reconnect with the adapter powered.
2. Actual fullscreen projection video with the taskbar disabled, active navigation instructions, wireless out-of-range recovery and ignition/power lifecycle.
3. Optional receiver music/navigation/call audio, incoming/conversation HFP controls and native equalizer control.

CarPlay/Autobox, tuner playback, phone notifications, marketplace catalog, multichannel fade/subwoofer hardware and a safe ignition shutdown controller remain incomplete. Full visual/hardware acceptance has not been declared.

## Publication checks

Only independent source, dependency manifests, technical documentation and tests are included. Runtime binaries/configuration, raw captures, local phonebooks, SSH credentials, generated dependencies/builds and device-specific deployment scripts are excluded. Real-device Bluetooth addresses in test fixtures were replaced with synthetic addresses; those tests still pass. The existing repository license and branch history are retained.
