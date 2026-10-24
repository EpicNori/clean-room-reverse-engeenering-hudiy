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


## Latest local Notifications check — 10 October 2026

Fresh browser captures covered the disabled output switch, enabled popup, accent change, matching original light theme at 1280×720 and compact controls at 320×568. The original source was capture 012; private before/after captures 01–09 are retained in the local notification-audit archive, outside the published repository. The scoped slider/arrow alignment was compared against the source again after correction. At 320×568 the page width was 320px, all three switches were 64×48px, and pointer-drag scrolling moved the settings viewport with an empty text selection. Physical finger input is not established by this browser check.

The frontend test suite and production build pass. The Windows backend suite ran 106 tests with three platform-specific skips, including the new private IPC and HTTP notification validation cases. A browser timer-binding error discovered during real interaction was corrected and covered by a regression test. Existing native audio-worker operation and actual wireless media/video were observed after reconnecting to the rebooted Pi; these observations precede the new notification code.

The Pi powered off during the session. Notification upload, new native compilation/CTest, visibility above live Android Auto, input microphone gain and real touchscreen pass-through remain unverified. Deployment was interrupted before any upload operation. See design-qa.md for the local visual scope; no complete 1:1 or hardware acceptance is claimed.


## Custom OBD dashboard — local check, 24 October 2026

The new My OBD page was checked through the running browser and real local service using a loopback ELM fixture with isolated storage. Actual UI interactions created oil-temperature, fuel-level and fuel-rate mappings, evaluated sample hex bytes, selected range inputs, changed a tile to Gauge, dragged a source into an empty cell, and swapped speed into the upper-left position. Definitions, positions and view choices survived a browser reload and a cold service restart. The constant-speed fixture produced 60 km/h, 60 °C oil temperature, stored code P0133 and an estimated 301 km range; it correctly left 0–100 unavailable. These are labelled synthetic simulator readings.

The 1280×720 landscape view and 320×568 compact view were inspected. Compact page width was 320px without horizontal overflow; the on-screen mapping keyboard fit the modal. Light/pink and dark/yellow palettes updated tile surfaces, controls and code-rendered plots. Original light/pink appearance and normal viewport were restored. Only drag handles capture movement; standard page scrolling remains enabled.

Production build and all 28 frontend/packaging tests passed. The Windows backend suite ran 123 tests with three platform-specific skips. Coverage includes formula/schema abuse, command injection/write rejection, sensor-frame matching, CAN header restoration, durable revision conflicts, actual loopback polling, removed-source invalidation, disconnect clearing, layout migration, sampling gaps, coasting fuel calculations and synthetic performance runs. npm audit reported zero known vulnerabilities on 24 October 2026; this is not a guarantee of no security defects.

No vehicle, Bluetooth adapter, phone playback/call or real acceleration run was used for this feature. This revision has not been deployed or accepted on the physical Pi. Manufacturer PID support, physical touch input and live vehicle reconnect remain outstanding. The new local API/ELM boundaries are documented in backend-rules.md and CUSTOM_OBD.md; no cloud rules or new privileges are required.


## Configurable OBD logging — local check, 24 October 2026

The new Logs option was exercised through the browser and real HTTP/ELM socket services using an isolated synthetic fixture. The fixture advertised 12 live PIDs, four freeze-frame PIDs, three information PIDs and one CAN monitor ID. Manual recording retained codes including P0133/P0147, raw exchanges, hidden custom mappings and numerical samples. The recording continued while navigating to My OBD. Recent-event expansion displayed the decoded stored fault code.

Automatic recording and a two-second sample interval were selected through the UI. After a cold service restart, a new session started without another UI action and retained that capture configuration. Recorded sample timestamps were at least 2.014 seconds apart in the checked segment. Stop finalized both sessions. CSV export created a local file with 5,434 rows, including 996 plottable numeric reading rows and 157 diagnostic events in the first checked session. JSONL remains the complete stream. These are simulator checks, not a real vehicle diagnosis.

At 320×568, page and viewport widths were both 320px, with no horizontal overflow. A pointer drag moved the settings scroll position from 617px to 867px; numerical increment controls measured 48×48px. The normal viewport was restored. The interface shows stored choices, unsaved drafts, data coverage, automatic/manual mode and the next-session effect of capture changes. A synthetic screenshot is included in the logging guide.

Automated checks cover read-only command/schema boundaries, actual loopback capture/reconnect, settings persistence, idle flush, raw/sample filters, full-storage/queue/disk failures, incomplete-session recovery, safe local export and quota reduction without hidden/deleted older logs. Hardware Pi deployment, physical finger input, powered-vehicle discovery, manufacturer ECU support and real ignition power-cut behavior remain outstanding. No private raw recording or export is published.

Final publication checks for the combined custom OBD/logger revision: 140 backend tests ran successfully with four platform-specific skips; all 28 frontend/packaging tests and the production build passed. The complete npm dependency audit returned zero known vulnerabilities. Browser console checks showed no new errors or warnings. Physical Pi/vehicle acceptance is unchanged and remains pending.


## OTA and My OBD refinements — local check, 24 October 2026

All 167 Python/backend tests completed with four platform-specific skips. All 29 frontend/packaging tests and the production frontend build passed. The full npm audit reported zero known vulnerabilities. New tests cover GitHub reference parsing, route policy, malformed archives/redirect scope, staging at final native-library paths, incomplete/ready markers, installation guards, health-token timing, startup crash/timeout/exec rollback, repeated successful updates, cancellation versus shutdown, offline check scheduling, normal-installer baseline selection and both gauge variants.

A real unauthenticated GitHub lookup returned main revision 7e02f918e61bd948e36bee02a44b96a6f68c3ec5. The 561,991-byte archive downloaded and extracted with the real bounded source loader; no downloaded code was executed. The source archive SHA256 was 2404602e855ec7d2644827c1fcf8c002d526df9618919e9a9f4c6e60cc0e06ed. That published revision predates the OTA protocol marker; this new revision still needs initial deployment before real OTA can be used.

Browser QA used an explicitly simulated OTA provider with no real software installation/restart. It verified settings navigation, selectable notify/idle modes, a saved seven-hour interval, persistence after full reload, check/prepare stages, themed notices, and the parked restart dialog with its safe action focused. Real source/build workflow and launcher process transitions are covered by fixtures/mocks, not an ARM64 hardware run.

My OBD reuses the actual original arc/tick gauge component and accepts/persists both display types. A pointer drag swapped tiles; arrow movement restored their positions. The code uses a lifted preview and bounded FLIP move animations, with reduced-motion suppression. At 1280×720, its grid measured x=8, width=1264, y=88, height≈543 and bottom≈631 inside a 639px-high content area: eight-pixel side/bottom gutters above the taskbar. The Back reservation is confined to the header. At 320×568, both the My OBD and OTA page/document widths were 320px without horizontal overflow. Original dedicated gauge geometry/typography remains unchanged; small custom gauges retain readable minimum font sizes.

Native ARM64 build, real Pi application update/rollback, AA/network concurrency, physical touch and power-cut behavior remain pending. New code and documentation are local changes; no Pi deployment, OS update or new publication occurred during these checks. See OTA_UPDATES.md and backend-rules.md for the operational boundaries.


## Android Auto connection control — 24 October 2026

Local verification: full service suite **177 tests, 4 platform skips**, **29 frontend tests**, production frontend build, and npm audit with **zero known vulnerabilities**. New checks cover separate durable connection/opening preferences and write-failure rollback, boolean validation, HFP/class phone recognition without contact sharing, single-phone default/manual overrides, multiple-phone selection, bounded existing/new wireless handoff requests, active/starting/off/Quit/USB/hotspot suppression, transient retry failures, fail-closed missing admission state and the guarded HTTP action. The browser showed independent connection/opening switches using the existing theme; its ordinary local preview is not a real phone connection.

The small native admission policy has a new CTest executable covering startup On/Off, Quit, manual requests, consuming a manual session and re-enabling automatic mode. **Native compilation/CTest and Pi/phone acceptance were not run**: the owner confirmed the Pi was powered off and unavailable. No Pi software/settings or phone connection was changed in this turn. See the detailed unchecked [README acceptance checklist](../README.md#android-auto-automatic-connection-acceptance) for cold boot, persistence, all switch combinations, wireless range/handoff recovery, USB, contact-sharing-independent phone recognition, Quit/Resume, device selection and service startup.


## Complete documentation image refresh — 24 October 2026

All nine existing public screenshot assets were retaken from the current production build; all Markdown references were checked and use the native JPEG format returned by the capture tool. New Android Auto connection/opening and original tick-gauge images bring the set to eleven assets. Each was inspected after capture, including explicit DEMO/SIMULATOR labels on telemetry, simulated OTA status and the latest My OBD gutters/header. The README embeds the refreshed assets, and custom OBD/logging/OTA/standalone documents reference the same current files. No photograph from the powered-off Pi was reused as current verification. All capture activity used synthetic/local fixtures in an isolated read-only browser preview.
