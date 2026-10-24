# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

The user requests long-press customization: allow pinning shortcuts to the taskbar and repositioning taskbar items, application tiles and dashboard cards. Preserve swipe scrolling and full responsiveness; keep editing usable inside the native taskbar overlay over Android Auto. Persist layout independently of theme preferences.

Shortcut layouts must survive a full Pi reboot with durable backend acknowledgement. Music and Contacts settings must provide separate configurable refresh intervals in seconds and persist them on the Pi. Contact settings govern actual Bluetooth phonebook downloads.

Contacts, Favorites and Call log must be usable without a keyboard: use tappable name groups instead of a search field. Pair must share the other menus' left-aligned title, themed controls and list layout, with one main discovery action and explicit pairing confirmations handled by our own agent. Sound must keep receiver selection concise and omit receiver-specific explanatory paragraphs such as JJ33 instructions. Preserve required Bluetooth OBD independently of optional radio audio.

The default car application must run independently of proprietary Hudiy. Use our owned native Android Auto engine, BlueZ pairing agent, direct Bluetooth ELM327 and private hotspot preferences. Keep the persistent taskbar, automatic-opening choice, touch filters and current visual style. Do not use the legacy compatibility host as an implicit fallback.

Android Auto settings must offer both automatic and manual phone reconnection. Keep the paired-phone Bluetooth reconnect preference separate from automatic projection opening, so the phone can reconnect and supply background data without covering the dashboard. Reuse existing switch styles. Standalone hotspot changes keep the app running; confirmation text must describe that behavior accurately.

All official Hudiy dependencies must be absent from production source. Do not restore the legacy API/configuration/host/audio bridge. Standard open-source libraries, including the pinned GPL Android Auto protocol library, are allowed. Historical reference documentation and startup-line disabling are not runtime dependencies. Keep our private preference keys stable.

The owner requests My OBD: custom read-only sensors/PIDs/formulas and a separate persistent grid for blocks, gauges, charts, range estimates, acceleration statistics and messages. Use drag grips plus touch/keyboard move alternatives, selectable sources/display/size, device-backed persistence, visible missing-data states and touchscreen field editors. Keep original OBD screens and required Bluetooth OBD intact.

The owner requests a dedicated OBD Logs option inside all OBD views. Record the broadest supported read-only diagnostic stream, custom mappings, raw replies, errors and connection lifecycle independently of visible tiles; provide bounded private sessions, clear storage/unsupported-data states, local CSV/JSONL export and explicit manual/automatic recording controls. Never promise every manufacturer signal or fabricate diagnostic data.

The owner wants operating choices to be configurable rather than fixed by the developer. Provide both automatic and manual OBD recording; expose relevant capture categories, refresh/sample intervals and storage limits with durable settings. Apply this preference to future features while retaining strict read-only validation and bounded resource limits.
