# Hudiy recreation styles

Visual reference: the user's Hudiy 1.24 installation, captured on 2026-10-03 at 1280 × 720.

## Layout

- Reference proportions: 1280 × 720. The application fills the actual viewport without scaling a fixed canvas or letterboxing. Fluid grid tracks fill available width and height; typography and controls use a viewport-derived unit with minimum sizes. Portrait and narrow layouts reflow, and overflow screens scroll above the persistent bottom bar.
- Bottom bar: y=639, height=81; shortcuts centered at x=40, 121, 202, 284, 366.
- Dashboard padding: 16px horizontally, 14px vertically; three approximately 408px columns with 13px gaps.
- Dashboard cards: 12px radius. Left clock 196px high, left navigation 404px high, center media 613px high, right phone 196px high.
- Menu sidebar: x=85, width=384; rows 112px high. Active row is a 104px-high pill with 52px radius.
- Menu grid: x=512, three 205px tiles spaced 54px apart; rows 178px high.
- Back control: centered at (43,43), 64px hit area.
- Settings content starts at x=102. Standard switch rows are 128px high; radio and slider rows 187px high. Scrollable content ends above the bottom bar.
- Switch: 98 × 60px, 30px radius. Slider: 8px track, 30px thumb.

## Colors

Sampled light palette: background #fff8f9; card and bottom bar #f8eaf0; selected menu pill #fadaec; media art #ffd7ee; primary #844c73; primary foreground #69345a; main text #201a1e; muted text #574b53; slider track #d4c3cd; outline #342b31.

Observed default dark palette: background #000000, surface #111318, selected pill #a6c3fc, text #ffffff, selected foreground #00152e. Dark mode stores its own accent and contrast independently from light mode.

User-requested extension: changing the accent changes the full palette in every window, including marketplace and OBD canvases. `implementation/dashboard/src/theme.js` owns all palette tokens: background, surface, selected, active, primary, primary foreground, text, muted text, tracks, outlines and switch parts. Default light purple and dark blue preserve sampled colors. Other accents tint light backgrounds 3%, panels 10%, selected pills 20% and active panels 24% with the chosen seed. Text uses darker tones for readability; dark mode uses a black background, subtly tinted panels and light accent selections. Screens must consume these tokens instead of hard-coded pink colors. Call/hang-up and warning colors retain their semantic roles. The marketplace's observed amber palette is replaced by the global theme at the user's explicit request; its German copy remains translated into English.

## Typography and icons

Use locally packaged Roboto regular. Reference sizes: dashboard time 48px, date 40px, menu labels 34px, settings labels 40px, menu icons 48px, bottom icons 36px, clock in bottom bar 28px. Material Symbols Rounded at weight 600 provides scalable icons; no copied proprietary icons or assets. Scrollable settings reserve 129px at the right for arrow controls; standard non-scrolling settings reserve 21px.

## Images

The observed initial dashboard contains no photograph or album art. Show the reference music-note tile when cover art is unavailable. Research screenshots remain evidence and are never rendered as application backgrounds. No proprietary executable, source code, or brand image is used.

## Interaction and states

Match reference menu selection, back navigation, settings controls, phone keypad, equalizer, and media controls. Provide visible keyboard focus. Persist UI preferences locally. Distinguish demo telemetry, disconnected hardware, and actual sensor values. Match light mode first; verify dark mode and screen scaling separately.
## Responsive and touch behavior

The viewport fills the available window; 1280 x 720 is a reference proportion, not a fixed canvas. Landscape dashboards use fractional columns and heights. Below 640px width or in portrait, dashboards stack, category menus become a horizontally scrollable row, settings scroll, gauges stack, and the equalizer scrolls horizontally. Maintain minimum touch targets and keep the footer reachable. Hide the duplicate footer clock below 360px to prevent overlapping controls.

Interface labels disable text selection. Text inputs remain selectable. Native touch uses browser panning; labwc mouse-emulated touch uses pointer-drag scrolling with an 8px threshold and suppresses clicks after a scroll gesture. Sliders, text inputs, selectors and editable fields are excluded from drag interception.
# Android Auto and persistent taskbar

The recreation uses two supported Hudiy web views on the Pi: the dashboard application above the bottom bar and an always-visible taskbar overlay. Android Auto renders directly in Hudiy in the same upper area; no screenshot stream or fabricated Android Auto screen is used. The taskbar remains at 11.25% of screen height, with a 56 px minimum, and uses the same theme tokens, typography and touch controls as the dashboard. The host derives projection and overlay dimensions from the current screen at launch. USB stream margins reserve that space rather than cropping Android Auto controls.

The navigation icon on the taskbar resumes Android Auto. Its selected background uses the active theme only when Hudiy reports projection visible. Dashboard and Applications return to the recreation without requesting Android Auto quit. Preferences synchronize between the two web views so changing theme updates the taskbar as well. The standalone localhost preview keeps a single responsive canvas and displays an honest unavailable message when no projection host exists.

Android Auto settings contain separate switches for **Open Android Auto automatically** and **Keep Hudiy taskbar visible**. The latter selects the reserved upper area or the original fullscreen projection. A saved geometry change exposes **Apply projection layout**, with explanatory text that applying it restarts Hudiy. The taskbar overlay uses ALWAYS visibility in the reserved layout and NATIVE_UI_ONLY in the fullscreen layout, so it returns on the dashboard.

Live music title, artist, album, duration, playback status and album art replace the empty dashboard placeholders when Android Auto supplies them. Navigation instructions and remaining maneuver distance replace the waiting state. These fields are checked every five seconds independently of automatic opening; no fabricated track or navigation data appears. Album art comes from the runtime's current media metadata, with the same rounded tile shape and cover fitting. Settings help text uses the current muted theme token and scales with the viewport.


Native Android Auto settings verification: the scroll container reserves a 129-unit right gutter for the separate arrow controls. Use the combined .settings-scroll.settings-android-settings selector so the general settings rule cannot override this gutter. Compact screens retain the documented 52px gutter.


Live phonebook views: Contacts, Favorites and Call log use themed panel rows with a selected-tone person/history badge, name, phone numbers and optional call timestamp. A 48px Refresh control and search field sit above a scrolling list; rows are at least 80px. Text wraps on compact displays. At widths up to 700px the list begins below the Back button. Phone entries remain selectable only through explicit row taps; names/numbers are not copied into browser preferences. No new fixed colors or external avatars are introduced. Album art continues to use the existing rounded cover tiles and native media metadata.


Live phone status now uses reported Bluetooth connection and battery level. Missing signal/battery data displays unavailable icons rather than fabricated values. Phonebook row/search surfaces use the existing --surface token; badges and controls use --selected and --primary-text, so light/dark accent changes apply throughout.


Long connected-phone names use an ellipsis before the Bluetooth icon, preserving the original card dimensions. Signal icons show the reported strength in four steps; battery icons use the reported level rather than a fixed placeholder.

## Bluetooth devices

Bluetooth music uses the existing player and dashboard card proportions, palette tokens and Material Symbols. Reported title/artist/album replace placeholder text; PNG/JPEG cover art replaces the player symbol when supplied. The Bluetooth player gains the same small metadata line as Android Auto, including the source's artist/album. The position slider displays the reported timeline and remains read-only because the bridge does not offer remote seeking. Missing metadata keeps the existing Not Provided title and empty timeline; no track or cover art is invented.

Native music comparison 237: title settings control reserves only 48×48 so it does not enlarge the title row. Timeline inputs are block elements to remove the text baseline's extra vertical gap; Bluetooth's read-only timeline hides its thumb. At 1280×720 the Bluetooth controls centre at x=420/640/860, matching the original player. Compact layouts keep their responsive footer controls.

The desktop icon column reserves 68 px so glyph width cannot push names to the right; name blocks sit 4 px lower to match the native text baseline. Scroll arrows use 80 px symbols with centres at y=173 and y=479 at the reference size; compact screens use 36 px arrows distributed within the screen. Unpair confirmation initially focuses Cancel, traps keyboard focus, closes on Escape, and returns focus to its originating device button.

The paired-device screen follows the current native reference (228): a vertical list beginning at x=85/y=30 with 148 px rows at 1280×720, 80 px Bluetooth symbols, 45 px accent names, 40 px addresses, thin surface dividers and a 64 px right-side link_off symbol. Rows sort by Bluetooth address, matching the observed native order. The list hides the scrollbar in Chromium and Qt WebEngine, retaining the arrow gutter and action alignment. Existing persistent user taskbar shortcuts remain visible. Compact layouts reflow text and retain 48 px actions without horizontal overflow; the list and arrow controls scroll independently of the taskbar.

The pairing view uses the shared left-aligned Pair heading, a live discovery list and one themed Pair device action in the header. This opens the installed runtime's Bluetooth agent, which handles discovery and PIN confirmation. Any current scan is reported as status text. There are no separate Scan/Stop scanning or duplicate per-device pairing buttons. Unpairing uses a themed, focused confirmation dialog naming the device; Cancel/Escape leaves its pairing untouched. Icons use the existing Material Symbols font; no raster assets or fixed colors are introduced.

## Refresh settings

Settings → System includes Music and Contacts tiles with existing library_music/contacts icons. Each page has a themed numeric field, seconds unit, touchscreen plus/minus buttons, explicit Save button, current interval and allowed range. Controls wrap on compact screens with 48 px touch targets and existing accent/surface/text tokens. Gear icons in music players and contact lists link directly to these settings. Music defaults to 5 seconds (1–60); phonebook downloads default to 60 seconds (5–3600). Contact screens check completed results every 5 seconds and keep immediate Refresh. New refresh pages reserve the scroll-arrow gutter; compact displays place content below Back.

Layout changes report Layout saved after the Pi backend confirms its durable save. Edits before hydration report that the layout has not been saved. New settings tiles extend existing ordering without discarding saved shortcuts. No new images or fixed colors.

## Long press and personal layout

A stationary 650 ms press, right-click or keyboard context-menu key opens customization for app/settings tiles, dashboard cards and taskbar items. Movement of 8 px cancels the hold so swipes remain scroll gestures. Releasing a long press does not activate the original button. Inputs and sliders retain their own interactions.

The themed customization panel offers Add to taskbar and previous/next position controls. Dashboard columns retain their original card dimensions when reordered; the clock/navigation pair moves as a column and can swap its top/bottom cards. Tile ordering is independent for each category. No arbitrary pixel placement or fixed-width canvas is introduced.

Taskbar items occupy a horizontally scrollable single row with at least 44 px touch targets. Its long-press editor fits inside the existing 81 px native overlay, including over Android Auto, with the item label, left/right controls, remove and Done. Dashboard, Applications and Android Auto remain available. All surfaces, controls and focus outlines use existing theme tokens. Layout is stored separately from appearance preferences and synchronizes between the content and taskbar web views. The Pi uses durable backend storage so web-view storage cleanup does not reset the arrangement; desktop preview uses local browser storage. Appearance includes Restore default layout.

OBD touchscreen controls (2026-10-10): retain the existing themed settings rows, typography, arrow gutter and taskbar. Add native Bluetooth/serial transport selection, a paired serial-device chooser and RFCOMM channel minus/plus controls (1–30), plus a clearly labeled save/reconnect action. Common serial paths and COM1/COM2 must be selectable by touch without a keyboard. Every action/select remains at least 48 px tall and uses existing --active/--selected/--primary-text colors in both themes; compact settings stack controls and never overflow horizontally. Preserve the optional serial text field for uncommon ports.
Physical brightness (2026-10-10): add a real backlight slider with numeric percentage and a 48 px Save button to Appearance and Android Auto settings. Use the existing slider/selected surfaces and inherited theme colors; compact layouts stack the range and action. The backlight affects the licensed projection surface as well as the recreation. Keep a minimum of 5% and show Pi-only unavailability in desktop previews; theme contrast remains independent.
Android Auto Day/Night integration retains the original Common/Day/Night radio controls and their existing responsive themed layout. On the Pi these select the real native projection mode. Common follows the Pi's Dark mode switch; Day and Night force the projection appearance independently of physical backlight brightness. The desktop preview's own theme remains local. No new icons, images, colors or screens are introduced.
Compact radio labels, including Day/Night and time format, have a 48px minimum touch height and width. Existing 20px radio circles, typography, wrapping and theme colors are preserved; the 1280×720 reference layout is unchanged.
Bluetooth Connections adds a tile to the existing Bluetooth settings grid. Its paired-device rows use the current theme and show connection status, a 48px minimum Connect/Disconnect button, and a labeled automatic reconnect switch. Rows wrap on narrow displays. Disconnect asks for confirmation because phone media and calls can stop; it also disables automatic reconnect for that device.
The dialpad keeps its native green call icon. Calling opens a themed confirmation panel showing the selected number, Cancel and Call; buttons have a 48px minimum touch target. Active call controls show Answer for an incoming call and use real HFP mute/hangup state. Unavailable controls are disabled using the existing theme.
OBD settings reserve the same right-side scroll-button gutter as Android Auto settings: 129 scaled pixels on the native landscape view and 52px on compact screens. Selectors and channel controls wrap inside that gutter so arrows cannot cover them.
# Car hotspot and radio output (2026-10-10)

Android Auto settings include a protected car Wi-Fi hotspot section using the existing refresh-setting layout, theme text/surface/accent variables, wrapped labels and 48px minimum touch controls. An Enable/Disable action opens the existing themed confirmation dialog with Cancel and Apply and restart. The dialog describes interruption of the current Wi-Fi connection and retains keyboard Escape/focus trapping. It does not display the Wi-Fi password. Physical brightness and hotspot controls share the Android settings scroll gutter.

Sound settings include a Bluetooth radio output selector, Save radio output and a Bluetooth Connections link. The select uses active background, primary text, selected border, 12px corner radius, 8px/12px padding and 48px minimum height. Names and notes wrap at compact sizes. Sound reserves the same 129 scaled-pixel arrow gutter as Android/OBD settings, reduced to 52px on compact screens, without extra duplicate right padding. Connection/routing states are reported as text; selecting a receiver does not start music. All colors follow the selected light/dark theme; no screenshot assets or fixed pink colors are introduced.

OBD gauge fidelity (reference captures 069/071): at 1280×720 the simple gauge arc has approximately 183px radius and center y≈348; the tick gauge retains its approximately 190px radius. Both canvas containers use top calc(22% - 2 * var(--unit)) and 57% height; simple gauges use 22 scaled-pixel side insets, tick gauges use 10. Roboto 400 and 700 fonts are bundled locally; canvases redraw after fonts load. Simple-gauge value/label/range baselines follow the reference. Tick-gauge headings use bold 32px text with 3.5px tracking, values use bold 86px and units use 38px below the value. Both position indicators follow the clamped reading: a round marker for simple gauges and a radial accent tick for tick gauges. Indicators appear only for a finite reading or explicitly enabled Demo telemetry; disconnected readings remain dashes without an indicator. All colors use the active theme palette. Charts remain code-rendered telemetry with no screenshot backgrounds or additional raster assets. Existing responsive stacked gauges and persistent taskbar are preserved.


Touchscreen menu corrections (2026-10-10): Contacts, Favorites and Call log replace their search input with six tappable name groups: All, A–F, G–L, M–R, S–Z and # (other names/numbers). Buttons use the existing surface/selected/text tokens, 24px pill corners, 48px minimum targets and a primary inset border for the selected state. Six equal columns become three equal columns below 700px. Counts report filtered and total entries, accents normalize for grouping, phone order is preserved, and a filter/view change resets list scrolling. The shared header wraps when necessary; the remaining area scrolls above the taskbar. Refresh and Settings stay reachable.

Pair uses the same title typography, top/left inset, themed header action and status line as Contacts. The discovered-device list keeps native row geometry and the arrow gutter; compact content flows below Back with 48px controls. Its single Pair device action delegates actual scanning/pairing to the installed agent. Sound retains receiver selection, Save radio output and Bluetooth Connections. Remove the JJ33-specific instructions and the explanatory playback/equalizer paragraph; only a short actual receiver/error status appears when applicable. No new fixed colors, raster assets or backend permissions.

Standalone integration (2026-10-10): preserve existing theme tokens and row geometry. Pair uses Find devices/Stop scanning as its single discovery action and one Pair icon per discovered device. Numeric comparison or ELM327 PIN selection appears in the existing themed modal, with explicit confirmation/cancel and 48px controls. OBD labels describe direct Bluetooth ELM327 and Save and connect ELM327. The native surface derives its size from the current screen, keeps the responsive web taskbar beneath projection, and can hide that taskbar only in Android Auto when selected. No upstream dashboard or raster assets are adopted.

Android Auto reconnection choices (2026-10-10): show an Automatically reconnect switch for each paired phone advertising phonebook support, using the existing setting-row, toggle-row and switch styles. On/Off governs durable Bluetooth reconnection independently of the Open Android Auto automatically switch. Preserve inherited theme colors, responsive text wrapping, at least 48px controls, taskbar and scroll geometry. A brief shared note explains manual mode and the 30-second retry interval. The standalone hotspot confirmation uses Apply and describes connection changes while the dashboard remains running. Unknown phone track duration is shown as an em dash. No new colors, icons or image assets.

Standalone wireless guidance uses the Connect Wi-Fi action and does not require a cable unplug, matching the verified software transport switch. Existing note typography and spacing are retained; the legacy host keeps its separate instructions.


## Public README and gallery

- Keep the README in English, with a linked contents list, the existing Mermaid architecture and ordinary GitHub Markdown tables/task lists.
- Lead with a real screenshot of our light dashboard; present the dark dashboard, application menu, theme controls and demo gauges in two paired gallery tables. Every image opens its full-size local repository asset and has descriptive alt text and a caption.
- Capture the actual application at its browser viewport (1280×720 for this gallery). Save unedited JPEG screenshots under `docs/images/`; do not use screenshots as application backgrounds or alter them to claim features work.
- The light reference palette stays purple/pink; the second gallery palette uses dark mode with accent seed #ff8700. Existing theme tokens determine amber controls, surfaces and gauges. No production UI styling was changed for the README.
- The gallery cover is an original geometric SVG illustration with purple/blue hills and an amber sun, visibly labeled DEMO MEDIA. It is sample artwork, not downloaded phone artwork or a proprietary Hudiy asset.
- Public captures use synthetic music/navigation/phone fixtures in a separate read-only loopback preview. No contact details, precise location, device IDs or credentials. OBD screenshots must visibly show DEMO when using simulated readings.
- Captions distinguish UI illustration from genuine device verification. Comparison text separates original Hudiy observations from our additions and fixes. Remaining work uses unchecked GitHub task boxes until implementation or hardware evidence supports completion.

## Native projection equalizer behavior

Preserve the observed 15 vertical bands, existing labels, control shapes, theme tokens and preset-menu layout. Frequencies are 25, 40, 63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300, 10000 and 16000 Hz. Our own curves are declared in `audioPresets.mjs`: Flat has zero gain, Bass boost raises the low bands without changing the treble, and Voice cuts low bass while emphasizing the speech bands. These replace arbitrary placeholder sine curves; exact proprietary preset values remain unknown. The preview bars continue using the existing `118 + gain × 8` height rule. Manual changes save as Custom; named presets and Restore update all bands atomically. On the standalone Pi the saved native curve hydrates the same controls, while the local-file Web Audio processor uses that curve separately. No new theme colors, assets or geometry were introduced.

## Standalone-only wording — 10 October 2026

The taskbar option reads “Keep taskbar visible”. Layout help states that changing the layout reconnects Android Auto while the dashboard stays running. It must not describe restarting the proprietary runtime. Bluetooth OBD selection uses our direct transport and its connected message follows actual local OBD state. Existing colors, fonts, spacing, icons, imagery and layout are preserved. Hudiy remains named as the observed visual reference, not as a running dependency.
