# Asset and dependency provenance

Recorded 24 October 2026 for the coscarOS source distribution. This is an inventory of the browser packages, public gallery and identified native dependency chain, not a complete bill of materials for every possible OS image or proof of GUI clearance.

## Browser libraries, fonts and icons

Packages are installed from npm through the committed lockfile. Fonts/icons are obtained from their open-license packages rather than extracted from Hudiy. The visible interface imports Roboto and the Material Symbols Rounded font-600 package. The installed but unused font-400 package is not an additional font embedded by these imports. The Vite entry covers its browser helper and bundled license inventory, not an assertion that all build-time tools ship in the UI.

| Package | Recorded installed version | License | Source |
| --- | --- | --- | --- |
| `react` | 19.2.0 | MIT | [Upstream](https://github.com/facebook/react) |
| `react-dom` | 19.2.0 | MIT | [Upstream](https://github.com/facebook/react) |
| `scheduler` | 0.27.0 | MIT | [Upstream](https://github.com/facebook/react) |
| `chart.js` | 4.5.1 | MIT | [Upstream](https://github.com/chartjs/Chart.js) |
| `@kurkle/color` | 0.3.4 | MIT | [Upstream](https://github.com/kurkle/color) |
| `@fontsource/roboto` | 5.3.0 | OFL-1.1 | [Upstream](https://github.com/fontsource/font-files) |
| `@material-symbols/font-600` | 0.47.6 | Apache-2.0 | [Upstream](https://github.com/marella/material-symbols) |
| `vite` | 6.4.5 | MIT plus bundled third-party notices | [Upstream](https://github.com/vitejs/vite) |

The [complete notice artifact](../implementation/dashboard/public/THIRD_PARTY_NOTICES.txt) contains the installed copyright/license texts and available NOTICE files. [The build generator](../implementation/dashboard/scripts/licenses.mjs) fails if a required license file is missing. [The artifact test](../implementation/dashboard/tests/distribution-licenses.test.mjs) compares versions and full texts with installed packages and production output. The lockfile and build output, rather than this dated table, determine the versions of a later release. Preserve licenses and attribution when redistributing or modifying these materials.

## Public screenshots and gallery artwork

### Current README captures — 25 October 2026

The six `*-current.jpg` files below are unedited 2048×983 viewport captures of our production frontend from source revision `4b39e1c42e2968e61466b75e2dc1059ec4b03860`, served by the real local Python service at loopback port 8766. The native Pi host was not attached. Demo mode remained off; no API fixtures, generated sensor readings, synthetic phone/media/navigation data or injected update status were used. Missing hardware is shown as disconnected/unavailable. Only this local browser's appearance was changed for the dark views; the owner's Pi was not modified.

| Path under `docs/images/` | Captured state |
| --- | --- |
| `dashboard-current.jpg` | Light dashboard; no connected phone or destination. |
| `dashboard-dark-current.jpg` | Dark dashboard with the existing blue accent. |
| `theme-settings-current.jpg` | Actual local appearance controls. |
| `my-obd-current.jpg` | Default custom OBD layout with unavailable readings. |
| `my-obd-editor-current.jpg` | The same layout in edit mode. |
| `obd-logs-current.jpg` | Idle recorder, no adapter and no saved recordings. |

These are interface captures, not vehicle measurements or proof of hardware compatibility. They contain no real phonebook, album cover, map location, Wi-Fi key or device address. The project's license covers its own contributions, subject to the independently applicable font/icon/dependency licenses and any unresolved rights in reproduced GUI expression.

### Earlier gallery assets

The earlier JPEG captures without the `-current` filename suffix were made on 24 October 2026 from our rendered application with synthetic media/phone/navigation fixtures and local ELM/OTA simulators. The demo album illustration was created for that gallery. They remain historical assets and are no longer the main README gallery; their test method has not changed. They are not captures of the original Hudiy software or evidence of live vehicle measurements.

The [style specification](../style.md) describes the reference observations and intentional changes. The visual layout and gauge inspiration are disclosed in the [README comparison](../README.md#what-we-rebuilt-and-corrected-from-hudiy). Creating screenshot pixels from our own code does not establish originality of the arrangement. Raw reference captures remain private; a raw capture is not licensed merely because it is kept private.

## Native code and protocol dependencies

Our native source is GPL-3.0-or-later. The capability builder adapts the identified upstream ServiceDiscoveryBuilder; it is not represented as an entirely original protocol implementation. [Native notices](../implementation/native/THIRD_PARTY.md) identify OpenAuto Prodigy `3afc5dd8bbacb5ce68e109189b18b14b251fabef` and Open Android Auto protobuf submodule `5ff4aa218dd33913237993f2968bf70e16dc464e`. The [CMake configuration](../implementation/native/CMakeLists.txt) pins the protocol dependency. Preserve upstream notices and provide applicable corresponding source when conveying binaries.

Qt, FFmpeg, libusb, OpenSSL, Protobuf and installed OS/device packages keep their respective terms. Their actual versions, build options, linked components and license files must be inventoried for a redistributed binary/image. The browser notice artifact does not purport to cover them. The mathematical EQ reference is the W3C Audio EQ Cookbook as recorded in native notices.

## Names and external references

coscarOS is the chosen project name, not a cleared registered mark. Hudiy is named only as the historical observation target/attribution and in stable compatibility identifiers. Android Auto and upstream project names identify relevant external products or technologies; this repository does not claim their endorsement, trademark ownership or certification. See [the legal assessment](LEGAL_REVIEW_AT_EU.md) and [branding notes](BRANDING.md).

## Future contributions

For every new visual/media asset, record the path, author/creator, original source, license and any changes; include the required license/NOTICE files. Do not add original product captures, phone media, logos or external artwork merely because they can be viewed publicly. Review source provenance and the license obligations for each new dependency. Update this inventory and the actual notice generator when the shipped browser assets change.


## Dashboard widget captures — 27 October 2026

`docs/images/widgets-glass.jpg`, `dashboard-studio.jpg` and
`extensions-layouts.jpg` are unedited 1280×720 captures of the local production
widget revision, based on `4b39e1c` plus the uncommitted dashboard work. Phone/OBD
hardware was disconnected; no generated live values or phone/media fixtures were
injected. The widget surfaces/backdrops and pack thumbnails are original CSS
and code using the existing licensed font/icon packages. The before/after local
captures are not native Pi hardware acceptance. No Hyprland/Celestia shell code,
assets or compositor configuration is shipped by this feature.


### First-launch introduction — 27 October 2026

`docs/images/introduction.jpg` is an unedited 1280×720 capture of the local production
frontend, based on commit `7fdd228` with the new introduction changes. The real local
service is disconnected from phone/vehicle hardware and telemetry demo mode is off.
The spotlight, wording, SVG mask and themed card are our own HTML/CSS/React work;
no external illustration or shell assets are used. It demonstrates the browser
workflow, not native Pi acceptance.


### OTA repair acceptance — 27 October 2026

`docs/images/ota-verified-current.jpg` is an unedited 1280×720 capture of the
production Software updates view served by the reference Pi through a loopback-only
SSH tunnel. Its API data is real: `e4cca11` installed/current after manual rollback
and reinstallation, no pending restart, native startup verified. The browser's
existing profile supplies its dark yellow appearance. It is a Pi-backed browser
capture, not proof of a physical screen, audible output or live vehicle data.


### Intro video and demo page — 28 October 2026

`docs/videos/coscaros-intro.mp4` (0:42, 1920×1080, no audio) and the posters
`docs/images/coscaros-intro-poster.jpg` / `coscaros-intro-poster-play.jpg` are
rendered from our own HTML/CSS animation in `docs/videos/source/` with
Playwright and ffmpeg. The only screen content is the existing unedited captures
listed above (`docs/images/*-current.jpg`, `widgets-glass.jpg`,
`dashboard-studio.jpg`, `android-auto-connection.jpg`,
`ota-verified-current.jpg`). Text, particles, glass cards and grain are our own
code. Fonts: Inter Tight, Instrument Serif and Geist Mono (SIL Open Font License
1.1), also loaded from Google Fonts by `docs/demo/index.html`. No external
footage, music, logos or stock assets are used.

### Full demo video v2 — 30 October 2026

`docs/videos/coscaros-demo-v2.mp4` (1:47, 1920×1080, AAC stereo) and its poster
`docs/images/coscaros-demo-v2-poster.jpg` combine our own HTML/CSS titles (same
look and OFL fonts as the intro video) with screen recordings of the local
coscarOS frontend and Python service, captured on 30 October 2026 in a fresh
browser profile with no phone, Bluetooth adapter or vehicle attached. OBD
values come from the app's built-in, on-screen labeled demo telemetry; the
Bluetooth and Android Auto screens show their real desktop "available on the
Pi" states. Stills reused: `android-auto-connection.jpg` and
`ota-verified-current.jpg` (see above). All sound effects and the music bed
were synthesized by our own script (Python/ffmpeg); no external audio, footage,
logos or stock assets are used.
