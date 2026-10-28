# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

The user requests long-press customization: allow pinning shortcuts to the taskbar and repositioning taskbar items, application tiles and dashboard cards. Preserve swipe scrolling and full responsiveness; keep editing usable inside the native taskbar overlay over Android Auto. Persist layout independently of theme preferences.

Shortcut layouts must survive a full Pi reboot with durable backend acknowledgement. Music and Contacts settings must provide separate configurable refresh intervals in seconds and persist them on the Pi. Contact settings govern actual Bluetooth phonebook downloads. Music refresh defaults to one second across the frontend and backend; preserve explicitly saved custom intervals.

Contacts, Favorites and Call log must be usable without a keyboard: use tappable name groups instead of a search field. Pair must share the other menus' left-aligned title, themed controls and list layout, with one main discovery action and explicit pairing confirmations handled by our own agent. Sound must keep receiver selection concise and omit receiver-specific explanatory paragraphs such as JJ33 instructions. Preserve required Bluetooth OBD independently of optional radio audio.

The default car application must run independently of proprietary Hudiy. Use our owned native Android Auto engine, BlueZ pairing agent, direct Bluetooth ELM327 and private hotspot preferences. Keep the persistent taskbar, automatic-opening choice, touch filters and current visual style. Do not use the legacy compatibility host as an implicit fallback.

Android Auto settings must offer both automatic and manual phone reconnection. Keep the paired-phone Bluetooth reconnect preference separate from automatic projection opening, so the phone can reconnect and supply background data without covering the dashboard. Reuse existing switch styles. Standalone hotspot changes keep the app running; confirmation text must describe that behavior accurately.

All official Hudiy dependencies must be absent from production source. Do not restore the legacy API/configuration/host/audio bridge. Standard open-source libraries, including the pinned GPL Android Auto protocol library, are allowed. Historical reference documentation and startup-line disabling are not runtime dependencies. Keep our private preference keys stable.

The owner requests My OBD: custom read-only sensors/PIDs/formulas and a separate persistent grid for blocks, gauges, charts, range estimates, acceleration statistics and messages. Use drag grips plus touch/keyboard move alternatives, selectable sources/display/size, device-backed persistence, visible missing-data states and touchscreen field editors. Keep original OBD screens and required Bluetooth OBD intact.

The owner requests a dedicated OBD Logs option inside all OBD views. Record the broadest supported read-only diagnostic stream, custom mappings, raw replies, errors and connection lifecycle independently of visible tiles; provide bounded private sessions, clear storage/unsupported-data states, local CSV/JSONL export and explicit manual/automatic recording controls. Never promise every manufacturer signal or fabricate diagnostic data.

The owner wants operating choices to be configurable rather than fixed by the developer. Provide both automatic and manual OBD recording; expose relevant capture categories, refresh/sample intervals and storage limits with durable settings. Apply this preference to future features while retaining strict read-only validation and bounded resource limits.

The owner requests selectable notify/manual and automatic-idle OTA updates from our GitHub repository, with durable preferences in Hudiy settings. Use existing Ethernet/Wi-Fi routes without switching away from wireless Android Auto; stage/build separately and preserve a previous runtime for startup rollback. My OBD must use the original arc/tick gauge renderers and modern drag/drop motion while preserving touch scrolling and reduced-motion accessibility.

OTA notification preference is separate from check/install policy; notify through the existing themed notice system once per new version/prepared state. Keep original gauge values legible even in small custom tiles while retaining the reference typography on dedicated gauge screens.

My OBD must maximize usable display area like the existing OBD pages. Keep outer gutters and gaps small, reserve Back space only in the header, and size rows from the actual available content area above the taskbar. Do not leave a wide empty gutter around the custom grid. Preserve readable gauges, touch targets, edit controls and responsive scrolling.

Android Auto needs a visible persistent automatic-connection master switch, separate from automatic screen opening and per-phone Bluetooth selection. Do not require contact-sharing permission to recognize phones for reconnect controls. Respect explicit Quit/manual disconnect and avoid stealing focus during background reconnection.

The owner requests a black startup instead of exposing the operating-system desktop. Keep the native cover until saved layout/fonts and both native web views are painted; acknowledge only the current generation token. Startup behavior must have a persistent Appearance switch. Keep recovery/normal Quit back to the desktop, and do not claim hardware boot acceptance while the Pi is unavailable.

Wireless Android Auto must have a direct no-USB bootstrap from a paired phone. Connect Wi-Fi must initiate a missing Bluetooth handoff in manual mode as well as retry an existing one. Wait for the actual listener/profile, preserve automatic-opening and phone reconnect choices, and show concise live setup progress. Keep USB-unplugged cold-start acceptance unchecked while the Pi is unavailable.


Microphone preferences belong to the native capture service, not localStorage placeholders. Keep Audio input device selection, gain/mute and explicit Save/Discard in the existing settings design. Enumerate real Qt devices; never invent a microphone or start capture from a settings page. Specific missing inputs stay selected, and saved mute must apply before capture at startup. Android Auto voice capture and HFP call routing are separate; document all native/hardware checks still pending while the Pi is off. See docs/AUDIO_INPUT.md and docs/backend-rules.md.


Hide native scrollbar chrome in every application view and nested scrollable
panel/dialog, in both themes and at all viewport sizes. Preserve touch, mouse-drag,
wheel/trackpad, keyboard and explicit-arrow scrolling; never disable overflow just
to remove a visible scrollbar. Keep this policy in the shared global stylesheet.


Provide a persistent master switch for popup notifications and an independent
General messages switch in System → Notifications. Master Off suppresses all
coscarOS popup categories, including toast errors/update notices, and clears
already-visible browser/native notices. Preserve individual category choices,
shared-profile synchronization and ordinary confirmation dialogs/inline status.


The owner requests a GUI dashboard widget system. Keep the original dashboard as
its default and provide optional glass styling inspired by configurable Linux
shells. Dashboard Studio must support add/remove/rename/resize, drag/swap plus
keyboard/touch alternatives, live preview and explicit Save/Cancel. Keep taskbar
preferences independent, and persist native layouts through revision-checked
private backend storage. Extensions supports bundled layouts and validated JSON
import/export as the foundation for later community downloads; do not fabricate
an online catalog or execute downloaded widget code. Preserve popup master mute,
real missing-data states, responsive scrolling and startup readiness.


Provide a first-launch spotlight introduction covering navigation, customization,
phone/projection, audio, diagnostics, recording, notifications and OTA. Save native
progress privately across restarts, keep browser-preview progress separate, require
explicit skip confirmation, and offer Replay introduction in System → Application.
Tour navigation must not execute device actions or steal focus from a modal; prevent
projection auto-opening while its temporary renewable guide lease is active.


Bluetooth Connections must offer Use as audio device for paired audio receivers,
using the existing durable Sound/radio-output preference and explicit connection
when needed. Do not treat a phone's audio-source profile or serial ELM327 as an
output receiver. Keep selected/actual route/error status inline when popups are off.


Customizing the dashboard must preserve the original clock/navigation/music/phone
widget appearance. Reuse shared content components with the original dashboard;
keep original icons, typography hierarchy, album/metadata/playback anatomy and all
four phone shortcuts. Avoid extra dashboard headings/default widget title bars.
Keep resizing/arrangement, editor grips and explicitly optional glass surfaces.
