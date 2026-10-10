# Backend rules

These rules describe the default independent application. HUDIY_STANDALONE=1 is set by our native launcher. Compatibility modules for an explicitly selected licensed Hudiy bridge remain in the tree; their installed-runtime commands/configuration are not used by this mode.

## API boundary

- HTTP binds to 127.0.0.1:8766. Host/origin values are limited to the configured local app/preview ports. Action bodies are at most 4096 bytes; unexpected fields, arbitrary commands/URLs/paths and unsupported actions are rejected. The same-user local application is the trust boundary, not a public web account.
- GET status/projection/bluetooth/phonebook/display/wireless/audio-route exposes bounded local status. A running renderer is distinguished from a connected phone and decoded video frames. Wi-Fi keys, pairing keys and arbitrary D-Bus object paths are not HTTP data.
- The native command channel is user-only Unix IPC under the private state directory, at most 65536 bytes per newline JSON message. Only allowlisted screen routes, connection/media actions, options, wireless reload and application exit are accepted.
- Static responses set CSP, nosniff and no-referrer. Selected local files use browser blob URLs. There is no cloud database, login provider or external backend policy to update.

## Preferences and projection

- Private JSON preferences use atomic replacement, 0600 mode and fsync before acknowledgement on Linux. Layout contains only known shortcut/order IDs and retains Dashboard, Applications and Android Auto. Browser edits wait for Pi hydration. Appearance preferences remain local to the web profile.
- refresh-settings accepts integer musicRefreshSeconds 1–60 and contactsRefreshSeconds 5–3600, rejecting booleans/fractions/strings/extra keys. Values persist in updates.json and apply to actual refresh work. Native connection checks run every five seconds independently of the UI interval.
- projection-settings accepts only boolean autostart/taskbarVisible/darkMode and Common/Day/Night. Options are sent to our process, then saved; disk failure resends previous options. Manual opening and automatic opening remain separate from phone background data.
- Changing taskbarVisible stops the current session to renegotiate video/touch geometry. The app remains running. One bounded handoff is scheduled after disconnect; failed saves or unrelated appearance changes do not trigger it. Fullscreen AA hides only our taskbar while projection is visible.
- Android Auto Quit stops admission until manual USB/Wi-Fi/Resume. Resume can retrigger our existing Bluetooth wireless connection. These requests do not pair phones, start media playback or prove a successful projection; later connected/frame status and screenshots provide that evidence.
- Explicit USB/Wi-Fi chooses that transport rather than reusing an unrelated active session. USB reconnect resets only a uniquely identified Android accessory, never an arbitrary hub or device; it runs in one owned worker, waits for phone initialization, and has a 15-second cooldown. It may interrupt that phone's projection.
- Explicit USB closes only our wireless bootstrap socket and rejects new wireless handoffs until Wi-Fi is selected. Other Bluetooth phone/OBD services and the saved hotspot preference remain available.
- The audio-input protocol descriptor remains stable when microphone hardware is absent. Actual capture requests return failure unless a real supported device opens. Status exposes microphoneAvailable and videoReady; a protocol handshake alone does not establish decoded video.
- application-quit accepts no arguments, asks our owned native process to exit and prevents further IPC commands while closing. Native teardown closes session/audio/pages and its owned Python backend. It does not reboot the Pi, erase settings or disable autostart. Outside the Pi application, unavailable hardware actions return 501.
- Physical brightness accepts 5–100%, uses the single actual kernel backlight with existing user permission and saves the choice. Day/Night controls the AA sensor independently of physical brightness.

## Bluetooth and phone

- Device discovery uses one powered adapter, validated current BlueZ paths and at most 128 entries. Discovery is explicitly requested, bounded to 30 seconds and released on stop/shutdown. Public device flags include paired, connected, SPP, A2DP receiver and PBAP phone support.
- Our Agent1 handles fresh numeric confirmation/cancel or explicit 0000/1234 PIN selection, with a 30-second prompt timeout. One pairing worker runs at a time. Successful explicitly requested pairing sets Trusted; automatic reconnect never pairs or trusts devices.
- Connect/Disconnect accepts only a currently paired address. Disconnect requires confirmation and removes its reconnect preference. Remove requires confirmation and a known currently paired device; real pairings are not removed during automated tests.
- bluetooth-autoconnect accepts a paired uppercase address and boolean enabled. At most 16 selected addresses persist privately. Retries are bounded to once per device every 30 seconds. Android Auto settings expose this same choice for PBAP phones independently of automatic projection opening.
- Wireless Profile1 owns only its registered profile and connection, requires a paired device plus enabled hotspot, and limits handoff frames to 4096 bytes. The protected AA listener binds to 192.168.12.1:5277. Bluetooth setup in the native protocol confirms only devices already paired through BlueZ; no silent AA pairing is performed.
- Phonebook uses owned BlueZ PBAP/OBEX sessions with bounded downloads, temporary files, RAM cache and disconnect invalidation. Contacts, Favorites and Call log keep phone order and use touch filters. No contact export is persisted to Git/cloud.
- Bluetooth media controls target exactly one current connected paired phone's addressed AVRCP player, with bounded D-Bus calls. Android Auto media uses our input channel only while connected. Caller-supplied paths, URLs and arbitrary media methods are rejected. Reported metadata is not proof that an external Spotify playback device updates the phone live.
- Calls use the matched oFono HFP service, fixed Dial/Answer/Hangup/Mute methods and validated number/call state. Dial requires confirmation. Device/network/audio changes refuse active calls where implemented. Automated tests use mocks; new real call or playback tests need explicit authorization.

## Required OBD and optional audio/network

- OBD selection accepts only a currently paired Serial Port adapter and RFCOMM channel 1–30. Our worker owns the direct socket; failed connections retry at most every 30 seconds. Fixed ELM initialization and read-only Mode 01 PIDs supply load, coolant, RPM, speed, throttle and voltage. Stale readings/history clear on disconnect. BLE-only adapters and arbitrary ECU commands are unsupported.
- Manual Bluetooth reading retains required automatic reconnection. Manual Stop suppresses that worker for the current session; serial/USB selection takes precedence. Simulated data is explicitly marked and never counted as vehicle evidence.
- wireless-hotspot requires boolean enabled and confirmed true, and waits until calls end. It switches only the fixed hudiy-recreation-car NetworkManager profile, updates next-boot autoconnect, privately saves our SSID/key/gateway settings and reloads our listener. Commands are argument arrays with timeouts; network/save failure attempts the previous mode. The app stays running. First-time protected AP provisioning is still an installation prerequisite; a home router is not needed for car use.
- Optional audio-radio-output saves only a current paired A2DP receiver address or an empty choice, excludes PBAP phones and refuses active calls. Selecting it neither pairs nor starts playback. The route worker manages only our native PID or the single connected phone's playback streams, can set the default sink and never moves unrelated active streams. It waits during calls and verifies the route on a subsequent poll.
- Local-file equalizer/balance affect that browser file. Native AA equalizer presets, FM, CarPlay/Autobox and multichannel vehicle audio remain incomplete. No audible-radio success is claimed without hardware evidence.

Native process/BlueZ profile registration and fixed NetworkManager switching replace the old runtime API integration. These are local OS integrations; no new external backend rules are needed. Standard OS service provisioning and privileges remain prerequisites on a fresh Pi. See SECURITY.md and STANDALONE.md for verified limits.
