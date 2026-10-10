# Security boundaries

The default application uses our native GPL Android Auto engine and Python service. It neither starts proprietary Hudiy nor connects to its API. The old bridge remains an explicitly selected compatibility/recovery path and is not an automatic fallback.

## Local interfaces

The backend binds to 127.0.0.1:8766, accepts only allowed loopback Host/origin values, limits action JSON to 4096 bytes and validates fixed actions. Static responses set CSP, nosniff and no-referrer. It is intended for a local desktop/car app, not a public authenticated web service. Processes running as the same OS user remain within the same trust boundary.

The native Unix socket is user-only inside a 0700 directory. Commands/events use bounded newline JSON, at most 65536 bytes. The launcher/native locks prevent duplicate owners. Quit terminates our window and owned backend; API callers cannot supply process IDs, commands, hosts or paths.

Wireless Android Auto listens only on the protected car AP's fixed address, not every interface. Our authenticated BlueZ profile accepts paired devices with wireless enabled; handoff payloads are bounded to 4096 bytes. Wi-Fi credentials remain private and are not returned through HTTP or logged. Native protocol debug/info logs are disabled because upstream logs can contain phone metadata or payloads. Numeric lifecycle diagnostics contain no phone identity or content.

## Devices, actions and private data

Our pairing agent requires a fresh confirmation request or an explicit supported ELM327 PIN, with a 30-second prompt timeout. Only one pairing worker runs at a time. A completed explicit pairing is marked trusted; background reconnect neither pairs devices nor grants trust. Disconnect and removal are confirmed in the UI. Device paths are obtained from validated current BlueZ objects.

ELM327 is required and uses a direct owned RFCOMM socket or validated serial transport. Only fixed initialization and read-only Mode 01 sensor PIDs are accepted. No arbitrary CAN commands, fault clearing or caller-supplied network destinations are offered. BLE-only adapters are not supported.

Contacts/recent calls remain in bounded memory. PBAP transfers use owned sessions and temporary files; transfers are deleted and stale caches clear on disconnect. Calls use the matched standard oFono HFP service. Real calls/playback need explicit test authorization; tests use mocks/simulators by default.

Optional radio output accepts only a current paired A2DP receiver, excludes PBAP phones and waits during calls. Routing can change the default output and move only streams owned by our native PID or the single connected paired phone; unrelated active streams remain untouched. A later poll verifies the route. This does not prove audible output quality.

Private Linux preferences are saved atomically with 0600 permissions, fsync before acknowledgement and a private parent directory. Supported choices include layout, refresh, projection, backlight, paired-device reconnect, OBD, hotspot and optional receiver. Wi-Fi changes update both current activation and next-boot autoconnect; failures attempt restoration of the previous network mode. The first AP provisioning still requires standard NetworkManager setup.

Artwork is bounded to 2 MiB and checked for dimensions before native decoding, saved privately and served only as recognized PNG/JPEG. Video packets/dimensions and USB buffers are bounded. The linked protocol library still processes untrusted phone traffic; a passing suite is not a security guarantee.

## Repository and deployment

Credentials, real contacts, precise map locations, raw screenshots/research, dependencies and generated builds are excluded from Git. Proprietary source/assets are not included. The native executable and linked protocol dependency are GPL-3.0-or-later; dashboard/backend remain separately licensed MIT. Pins and notices are in implementation/native/THIRD_PARTY.md.

The boot installer retains backups and changes only the managed app startup block, exact old dashboard/OBD-example lines and our labwc window rule. It does not add an ignition controller or a safe power-cut circuit.

USB reconnect selects exactly one Android accessory, uses bounded identification transfers and one owned worker with a 15-second cooldown. Explicit wired selection suspends only our wireless bootstrap, leaving other Bluetooth services intact. A protocol handshake does not claim decoded video or microphone hardware; actual unavailable capture requests fail explicitly.

Current verification: 96 backend tests, 14 frontend tests, production build and actual Pi compilation pass. The production dependency audit was rerun on 10 October 2026 and reported no known vulnerabilities. Full audible audio, powered vehicle data and unattended wireless recovery remain unverified. See docs/STANDALONE.md and docs/backend-rules.md.

No external Firebase/Supabase permissions or cloud rules are required. Fresh Pi installation still needs standard OS Bluetooth/audio/call services and a protected NetworkManager AP. Review OS privileges and deployment exposure when changing those boundaries.
