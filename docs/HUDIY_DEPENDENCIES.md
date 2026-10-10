# Hudiy dependency inventory — 10 October 2026

The owner's requirement is to remove all official Hudiy dependencies while retaining standard open-source libraries. This inventory describes the maintained standalone source, not the older private research snapshot.

| Component | Source and current ownership |
| --- | --- |
| Dashboard, taskbar, menus, settings and gauges | Our React/CSS implementation, based on observed appearance and behavior. Reference screenshots are not application backgrounds. |
| Local API, persistence, lifecycle and fullscreen application | Our Python service and Qt native host. |
| Android Auto receiver | Our native host, USB transport, private IPC, video/audio/input integration and lifecycle, linked to pinned GPL `prodigy-oaa-protocol` from OpenAuto Prodigy. Its service-discovery construction includes an explicitly attributed upstream adaptation. This is open-source third-party code, not official Hudiy. |
| Bluetooth pairing, phonebook, media and calls | Our adapters/agent using standard BlueZ/PBAP/AVRCP and oFono HFP services. |
| OBD | Our direct RFCOMM/serial ELM327 polling and read-only Mode 01 allowlist. |
| Hotspot | Our private NetworkManager profile/settings and provisioning tool. The reference Pi originally migrated its existing AP credentials/profile; current operation reads our private settings only. |
| Audio DSP and receiver routing | Our DSP implementation and owned-PID audio route; no proprietary equalizer/echo sink chain. |
| Fonts/icons/frameworks | Roboto and Material Symbols npm packages, React, Chart.js, Qt, FFmpeg, libusb, OpenSSL and Protobuf. They retain their own licenses. |

## Removed production paths

- `implementation/launcher/hudiy_host.py`: explicitly selected official-runtime launcher.
- `implementation/service/projection.py`: official loopback TCP/Protobuf API client.
- `implementation/service/obd_settings.py` and `wireless.py`: official JSON configuration editors.
- `implementation/service/audio_route.py`: original equalizer/echo sink routing. Generic helpers now live separately.
- The OBD `hudiy` transport and environment-controlled official runtime selection.

The boot installer still recognizes exact old official startup lines to disable them. Historical verification/public-documentation links, compatibility observations, project naming, storage keys and private research remain as reference material. They do not start or require the official runtime.

## What is still inherited on the reference Pi

The existing Debian/labwc installation and standard BlueZ, oFono and PipeWire service configuration predate our standalone app. Hotspot/OBD preferences were migrated to our private files. Those system packages are open source, but complete reproducible installation on a clean OS image remains unverified. Removing the licensed application directory alone would not prove clean-image independence.

The Android Auto Maps/Spotify interface is rendered from the connected phone. Those pixels are not our dashboard or official Hudiy assets. Android Auto phone software remains necessary for projection.

## Verification and limits

The source scan found no exact file matches between the inspected application source and the official public repository (excluding generated dependencies/build output and PNG evidence). This is a narrow byte-for-byte check, not a formal provenance or legal audit. The native dependency and adapted construction are disclosed in `implementation/native/THIRD_PARTY.md`.

All 92 current backend tests pass, including environment-selection, removed-transport, official-path, private-persistence, direct OBD recovery and owned-audio-routing guards. Bridge-specific tests were retired; current hardware checks still require the Pi/phone. Prior independent USB/wireless video was observed with the proprietary process stopped and its API port absent. This cleanup has not yet been deployed to the Pi.

No cloud/backend permissions changed. Local API changes and boundaries are recorded in `docs/backend-rules.md`. No branch, commit or push is part of this cleanup.
