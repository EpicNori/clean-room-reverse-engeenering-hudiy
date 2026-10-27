# coscarOS styles

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

Settings → System includes Music and Contacts tiles with existing library_music/contacts icons. Each page has a themed numeric field, seconds unit, touchscreen plus/minus buttons, explicit Save button, current interval and allowed range. Controls wrap on compact screens with 48 px touch targets and existing accent/surface/text tokens. Gear icons in music players and contact lists link directly to these settings. Music defaults to 1 second (1–60); phonebook downloads default to 60 seconds (5–3600). Contact screens check completed results every 5 seconds and keep immediate Refresh. New refresh pages reserve the scroll-arrow gutter; compact displays place content below Back.

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


## Notification behavior and theme — 10 October 2026

Preserve the original Notifications rows, switches, duration sliders, Roboto typography, scroll arrows and responsive taskbar. Transient popups retain the existing centered rounded rectangle, 32 scaled-pixel text, 20/30 scaled-pixel padding and 12 scaled-pixel radius. Replace the fixed peach background/brown foreground with --active/--primary-text so both themes and every accent apply. Native popups use the same palette, wrap inside the screen, remain above the taskbar or above Android Auto when its taskbar is hidden, and pass touches to the application underneath. No icons, images or screenshot backgrounds are added.

Output, input and track notices respect their individual switches and Notification duration (1–15 seconds). Action/error toasts use Toast duration (1–15 seconds). Only one notice is visible; new volume/action notices replace the previous notice, and tracks cannot displace them. Music position/cover changes, pause/resume and reconnecting the same track do not repeat announcements. Disabling a switch clears its active notice. Theme changes recolor a native notice without extending its timer. Input controls still represent the saved preference; microphone gain is not yet integrated.


Notifications reference alignment: on landscape views above 640px, move toggle content down 4 scaled pixels and its right inset to 2 scaled pixels. Extend the slider control group 27 scaled pixels, reduce its output column to 40 scaled pixels, move the controls down 2 scaled pixels and use 80 scaled-pixel arrow symbols. At 1280×720 this aligns the observed switch centers (approximately 1086/90), slider track end (approximately 1020), thumb at value 8 (approximately 606) and right arrow (approximately 1127). Apply these corrections only to Notifications; keep compact controls and other settings pages unchanged. Persistent extra shortcuts are intentional personal layout differences from the original capture.

Compact Notifications switches use a 64×48px pill with 24px off/36px on thumbs and 6px/4px side insets, ensuring a 48px touch target while retaining the theme. Row labels wrap within the existing 196px content area at a 320px viewport; controls stay above the horizontally scrollable taskbar.


## My OBD editor — 24 October 2026

Add My OBD to the Hudiy applications category as an independent custom-data page; retain all original OBD pages. Use inherited --bg/--surface/--text/--muted/--primary/--active/--primary-text/--track/--outline tokens, local Roboto, and the existing Material Symbols library. No new palette, gradients or raster assets. The page scrolls above the persistent taskbar and starts 96px from the left on landscape to preserve Back.

The landscape editor uses a four-column, eight-row coordinate grid with 180px rows and 16px gaps. Rounded 16px tiles can be 1×1, 2×1, 1×2 or 2×2. Source chips can be tapped or dragged to empty cells; each tile has a dedicated grip and previous/next/up/down alternatives. Only grips capture touch; surrounding swipes retain normal scrolling. Layout changes save independently of the theme and acknowledge Pi storage or browser-only preview. Drops outside the grid or into incompatible occupied space preserve the prior layout. Live values have no fabricated fallbacks; Demo and Simulator states are visibly labeled. Charts/gauges use canvas-rendered telemetry and refresh inherited colors.

Below 1100px the same saved positions flow into two columns; below 640px or in portrait they flow into one. The source library stacks and move buttons provide precise positioning when drag targets are not shown. View-mode values use 28–52px text and secondary metadata 13–18px. Editors use a focused, scrollable themed dialog, labeled 48px fields, touchscreen keyboards for text/hex/formulas/numbers, Escape/Cancel and focus return. Range estimates and acceleration timings are labeled as estimates; missing inputs show dashes and concise setup guidance.

My OBD view rows adapt between 140–180px to fit three rows above the taskbar at 1280×720; desktop edit rows expand to 220px for controls. Use 100vh for Qt 6.4 compatibility. Its action group uses the scoped obd-page-actions class so the existing OBD settings action styles cannot enlarge the new header.

Editing starts with the data-source library collapsed behind Add data, keeping placement controls visible. Landscape edit rows are 260px to fit 48px move/configure/remove targets without clipping; source grips retain independent pointer capture. Normal view remains compact and uses the saved grid unchanged.

Sensor editors provide a clearly labeled sample-byte formula test when the local service is available; sample results are never presented as live vehicle values. Saved layout acknowledgement says Saved on device to describe the actual durable backend rather than assuming a particular platform.

Chart horizontal positions use the recorded sample timestamps, retaining gaps when mappings change. The library includes last/best 0–100 and average consumption estimates. On 320px screens, the touch keyboard uses five columns to preserve 48px-wide keys and shows the currently edited value.


## OBD diagnostic logging — 24 October 2026

OBD Logs is a dedicated scrollable page reached from My OBD, every existing OBD telemetry view, connection settings and the Hudiy application menu. Retain inherited Roboto/Material Symbols, current background/surface/primary/active/text/muted/track/outline tokens and existing taskbar. No images imitate readings; screenshots are documentation only.

Use a 36px regular title, 24px section titles, 17px text and 14px supporting text. Landscape gutter is 96px, top/right padding 24px; compact/portrait uses 70px top and 12px side gutters. Surfaces have 16px corners, controls 12px corners and at least 48px targets, with visible theme-colored focus rings. A static primary-color recording dot plus text indicates recording; no flashing/red-only status or animation is needed. The primary Record/Stop button uses the active theme. Four numerical status cells reflow into two columns on compact screens. Session rows and action groups wrap below 1000px; compact cards use 16px padding.

Capture coverage and recent structured/raw events use native details controls with wrapped text and selectable diagnostic payloads. The automatic-recording switch has a 64×48px hit target, explicit label and saved-device meaning. Log removal uses a labelled focus-trapped confirmation dialog with Keep recording focused first. Export buttons state CSV/JSONL and show the saved local destination. Error, interrupted, simulator, waiting and storage-limit states are written as text. Preserve normal finger/mouse drag scrolling above the taskbar.

Recording settings use a native details section with two-column capture checkboxes and interval/storage controls, reflowing to one column below 700px. Each numerical control has presets plus 48px decrement/increment buttons, and unsaved choices have explicit Save/Discard actions. Capture changes apply to the next session; automatic/manual mode stays separately available. Use inherited theme colors and focus styles throughout.


## My OBD original gauges and drag motion

My OBD shares the actual code-rendered arc and tick gauge components from Gauges/Gauges 2, including the original 270-degree geometry, Roboto labels, numeric value, units, ticks/indicator and current theme palette. Sensor-specific min/max/decimals apply to custom readings. Both original variants are selectable per tile; existing saved Gauge tiles use the arc variant. Scale gauge typography to tile space, retaining the existing reference sizing on the dedicated screens.

Dragging lifts a themed text/card preview with an 18px radius, primary border, soft shadow and slight two-degree rotation. Keep the source card as a faint dashed placeholder and highlight the actual drop cell. Accepted moves/swaps use a 280ms position animation with cubic-bezier(.2,.8,.2,1); added tiles enter over 220ms. The grip remains the only drag-capture area, so page swipes continue scrolling. Reduced-motion disables lift/position animations and rotation. No data animation invents readings.


## Software update settings

Use the established left gutter, regular Roboto titles (36px/30px compact), themed surface cards with 16px corners, Material Symbols and 48px minimum touch controls. A status card shows real update phase, installed/latest commit, network route and last check. Preparation phases have a subtle opacity pulse only when reduced motion is off; no invented completion percentage. Preferences expose notify versus idle installation, automatic checks, check interval with preset/step controls, Android Auto preparation, metered networks and retained versions. Switches are 64×48px and use current primary/outline colors.

Stack the route/version summary and setting controls on compact screens; the page scrolls above the permanent taskbar. Installation/rollback use a focus-trapped parked/restart dialog. Its safe first action keeps using the app. Error, offline, unsupported launcher, busy, verifying and rolled-back states are written in text. Current theme tokens apply to every surface/control.

Small custom gauges retain at least 28px numeric values, 12px units and 10px endpoint labels. Shared reference screens retain their original typography. Software-update notifications use the existing themed notice overlay and configurable toast duration; a separate update-notification switch controls them.


## My OBD maximum usable area

The owner wants My OBD to fill the screen like the other OBD views. Use an 8px outer gutter, 8px tile gaps, 12px tile padding/corners, and a compact 72px landscape header. Reserve the Back-button space inside the header only; there is no persistent 96px left gutter beside the grid. A ResizeObserver measures the actual remaining height below the header/controls, and desktop rows share that space down to the taskbar with a 120px minimum. Edit rows keep their 260px tool area and scrolling. On compact/portrait displays the title alone reserves 56px for Back, controls wrap using 48px touch targets, and the Logs text becomes an accessible icon button to fit the header. Saved positions/spans and responsive single/two-column behavior remain intact.

Scale only the My OBD header’s Back reservation with the existing --unit variable on larger displays; the grid keeps its 8px full-width gutters at every resolution.


## Android Auto automatic connection

Place Connect Android Auto automatically before per-phone Bluetooth reconnect and Open Android Auto automatically in Android Auto settings. Reuse the existing themed switch rows, touch targets, focus styling and scroll container. Connection and screen opening are separate persistent choices. Short supporting text explains manual mode, existing-session preservation and Quit pausing retries. No new colors, images or animation.


## Complete screenshot refresh — 24 October 2026

Retake all public documentation images from the current production build; replace the earlier JPEG gallery with unedited 1280×720 native JPEG viewport captures. Retain the light purple/pink palette and show dark amber with contrast 0. Use descriptive alt text, full-size image links and paired Markdown gallery tables. Include both original gauge variants, the full-area My OBD grid, logging, OTA and the separate automatic Android Auto connection/opening controls. Mark synthetic/demo/local-only views clearly in captions and preserve hardware acceptance limits. The capture preview is isolated/read-only and never changes the owner's app settings or contacts. No production UI style changes were made for these pictures.


## Black startup and readiness recovery

Use solid #000000 for normal boot, compositor background, native window/page background and an opaque full-window cover. No logo, spinner, progress text, animation or dashboard fragment appears until both dashboard/taskbar views are loaded and painted. Match any display geometry on resize. Hide the pointer over the startup cover. A 60-second failure state uses white text, 24px wrapped explanation and 20px Retry/Return to desktop buttons on #222 with at least 48px targets; safe desktop return receives initial keyboard focus. Use the existing themed Appearance switch for Black screen during startup, with a concise next-start note. Preserve normal touch scrolling and theme controls once ready.


## Direct wireless connection feedback

Keep the existing Android Auto settings layout, theme and controls. State explicitly that pairing over Bluetooth and connecting to the Pi hotspot does not require USB. Show sanitized live setup progress in an existing setting-note with role=status, refreshing every five seconds without interrupting a hotspot confirmation/save. Use plain phone/Bluetooth/Wi-Fi wording; do not expose credentials, addresses or raw protocol errors, or call a completed handoff a connected projection. No new colors or animation.


## Audio input settings

The Audio category gains an `Audio input` tile using the existing rounded `mic` Material Symbol. Sound links to the same page instead of displaying browser-only input controls. The page uses Roboto, existing theme tokens (`--selected`, `--active`, `--primary`, `--primary-text`, `--text`, `--muted`), the existing switch and rounded settings buttons. No fixed pink accents, new bitmap assets or external fonts are introduced.

Device selector, Refresh and Save/Discard controls wrap within the settings scroll region and reserve its existing scroll-button gutter. Selects/buttons/range controls keep 48px touch targets. The slider uses a visible percentage and accessible label/value; mute exposes a labeled switch. Native status and unsaved drafts use polite status text. Missing/unsupported devices are named explicitly; a disabled preview/offline state never resembles active capture. Focus has a visible theme-colored outline. No new animation or motion is added.


## About-page provenance and licenses

The existing About screen adds one plain non-affiliation paragraph and an expandable local viewer for the complete browser license notices, using its current text/link styling and theme. No name, logo, layout, palette, font, image or other screen is redesigned. The notice text ships locally with the assets and does not require an external website.

## coscarOS product identity

Display the name exactly as **coscarOS**, including the lowercase initial c and uppercase OS. Use it in About, the application menu, OTA settings, native window title and fresh Bluetooth/Wi-Fi defaults. The extension screen is “coscarOS Extensions”. Existing Roboto typography, Material Symbols, responsive dimensions, themes and accent colors remain the style system; no original Hudiy logo is used. Historical source attribution may still name Hudiy. Stable stored menu IDs and application IDs are compatibility identifiers, not displayed branding.

All 11 public gallery screenshots were retaken after the rename using the production build and isolated synthetic fixtures. The gallery cover illustration now reads coscarOS; the application menu and OTA screenshots show the new name.

## Diagnostic capture coverage and fault markers — 24 October 2026

OBD Logs adds a **Mark fault / power loss** button using the existing themed
button, Material Symbols `flag` icon, text sizing and focus/touch styles. It is
shown only for an active recording and disabled during finishing or an action.
Coverage uses existing paragraph/details styles for queried/scheduled counts,
discovered ECUs, incomplete captures and unavailable responses. Saved sessions
show a concise capture summary, including an explicit no-vehicle-response state.
No new colors, fonts, images, spacing system, motion or external assets are added.
Labels describe automatic discovery without asking for a vehicle model and
state the limits of exposed diagnostics instead of promising every vehicle signal.


## Scrollbar visibility — 25 October 2026

Hide native scrollbar tracks, thumbs and their occupied width/height throughout
all application web views, including settings, contacts, Bluetooth lists, My OBD,
OBD Logs, software updates, license notices, customization panels and nested
edit dialogs. Use global `scrollbar-width: none` plus the Chromium/Qt WebEngine
`::-webkit-scrollbar` fallback. Keep existing `overflow: auto/scroll` behavior,
touch panning, mouse-drag scrolling, wheel/trackpad input, keyboard scrolling and
explicit scroll arrows. Do not use `overflow: hidden` to conceal scrollbars.
This policy applies in both themes and to horizontal scrolling on compact screens.
No colors, assets, typography, focus indicators or animation are changed.


## Product README and current gallery — 25 October 2026

Lead with the product, supported workflows and installation link. Keep paired
image tables, descriptive alt text and full-size links. The current gallery uses
six unedited 2048×983 JPEG captures of the production frontend with its real local
Python service, demo mode off and no phone/vehicle attached. Show actual missing
data rather than inventing values or media. Use the existing light pink and dark
blue themes; preserve the production UI without retouching screenshots. Keep
older fixture captures and their historical provenance intact. Link detailed
revision/test methods from a concise current acceptance table. Preserve the full
source tree, installation/orientation guide and remaining-work checkboxes. No
application colors, layout, behavior or backend rules change in this revision.

The capability table uses the existing Markdown table style, with current status
and evidence/next milestone in separate columns. The daily-use roadmap uses P1/P2
checkboxes and measurable completion criteria; no badges or comparative ratings.


## Popup notification controls — 27 October 2026

Settings → System → Notifications begins with an Enable popup notifications
master switch and a concise supporting note. Add General messages before the
existing volume/input/track switches. Reuse the existing themed toggle rows,
setting-note typography, touch targets, scrolling and focus states. The master
switch retains all category choices and immediately dismisses any popup; the
individual general-message switch also dismisses a visible toast. Both browser
and native overlays follow the same policy. No colors, fonts, images or motion
are added. Confirmation dialogs and inline page status remain available.


## Dashboard Studio and optional glass — 27 October 2026

Preserve the original dashboard and theme by default. A 48px Customize dashboard
button and System → Dashboard entry open a separate editor. Use an explicit
Save/Cancel workflow, a compact toolbar, a widget library, a live six-column grid,
and a selected-widget inspector. Native layouts save through a private versioned
backend document; preview layouts are labelled as browser-local. Keep the taskbar
visible and never store live phone/vehicle content in shared layout packs.

Classic widgets inherit existing theme tokens, Roboto and Material Symbols.
Optional glass uses static original CSS aurora/midnight/sunrise/graphite backdrops,
light text, a theme/custom accent, translucent panels, subtle 1px edges and bounded
0–24px backdrop blur. Offer opacity, rounding, gap and motion controls. No external
wallpaper, copied shell assets or new font is required. Provide an opaque fallback
for unsupported/reduced-transparency environments. Motion is short (180ms), stops
for reduced-motion preferences and never animates the backdrop continuously.

Drag only from dedicated grips; ordinary touch/mouse scrolling stays available.
Show a clear target preview, reject overlaps, and provide move/resize controls and
keyboard alternatives. Reflow to two/one columns on compact displays without
rewriting saved coordinates. All editor controls retain 48px touch targets, focus
outlines and hidden scrollbar chrome. Extensions presents real bundled layouts
and JSON import/export; future community download support must not be represented
as an existing online catalog.
