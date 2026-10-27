# Dashboard Studio and layout packs

The original dashboard remains the default. Open **Customize dashboard** on its
lower-right corner, long-press a dashboard card and choose **Dashboard Studio**,
or open **Settings → System → Dashboard**.

## Build a dashboard in the GUI

1. Choose **Add widget**: Clock, Navigation, Now playing, Phone, Connections,
   Quick access, Vehicle reading or Diagnostics. Up to 16 widgets are supported.
2. Drag a widget by its grip. Equal-size widgets can swap places; overlapping or
   out-of-bounds placements are refused. Ordinary touch and mouse scrolling still
   work outside the grips.
3. Select a widget to edit its title, width and height. An on-screen title keyboard
   is included. Move buttons, arrow keys on a focused grip and **Swap position**
   provide alternatives to dragging.
4. Vehicle reading widgets offer speed, RPM, coolant temperature, engine load,
   throttle and control-module voltage, using a block, chart or either original
   arc/tick gauge. Unsupported, disconnected and stale data remain unavailable.
   Custom manufacturer mappings continue to live in [My OBD](CUSTOM_OBD.md).
5. Choose **Appearance** for Classic or optional Glass. Set the backdrop, accent,
   panel opacity, blur, rounding, spacing and motion. Glass affects the dashboard;
   ordinary application/taskbar theme settings remain independent. Reduced-motion
   and reduced-transparency preferences are respected where supported.
6. **Save layout** applies the preview. **Cancel** leaves the saved layout intact.
   Browsing Extensions and returning with Back retains the unsaved preview.
   Playback/navigation controls do not operate while selecting widgets in the editor.

The grid has six logical columns and eight rows. Narrow screens reflow into two
visual columns with shorter cards; saved positions and dimensions are retained.
On compact screens, use the move/swap controls rather than free-position dragging.
The persistent taskbar remains available below the dashboard/editor.

## Layouts in Extensions

Open **Applications → coscarOS → Extensions**, or **Explore layouts** in the editor.
There are four actual bundled packs: Original, Daily drive, Aurora glass and Driver
focus. **Preview layout** opens the editor; a pack changes the saved dashboard only
when Save is selected. Original restores the existing dashboard and its independent
shortcut/card-order settings.

**Export saved layout** exports configuration only. In a browser it downloads
`coscaros-dashboard.json`; in the native app it saves a uniquely named JSON file in
`~/Downloads/coscarOS-Layouts/`. Live readings, media artwork, contacts, credentials
and taskbar settings are not included. Custom titles are included, so review your
own text before sharing a pack. At most 100 native export files are created before
the user must move older exports; files are never silently removed.

**Import layout** reads a selected JSON file, validates it and opens a preview.
The file must be a `coscaros.dashboard` version-1 pack of at most 16 KiB. Only
allowlisted widget types, sources and appearance values are accepted. Arbitrary
HTML, CSS, scripts, asset URLs and commands are not part of the format.

An online community catalog/download service is **planned**, not connected in this
revision. These bundled layouts and the import/export format provide the first
working distribution path. Community downloads should use the same preview,
validation and explicit Save flow.

## Persistence and backend boundary

The native app saves `~/.local/share/hudiy-recreation/dashboard-widgets.json` through
private atomic/fsync storage. It is independent of the existing taskbar layout and
appearance preferences. A revision hash prevents an older editor from overwriting
a newer save. A save failure leaves the previous configuration intact. Cancel and
reopen the editor if another window has changed the saved layout.

The standalone browser preview uses `coscaros.dashboard.v1` in localStorage and is
labelled **Saved in this browser**. It does not pretend to write Pi preferences.
Native web views wait for widget configuration before acknowledging startup.

- `GET /api/dashboard-widgets`: availability, validated configuration and revision.
- `POST /api/dashboard-widgets`: exact `revision`/`config` save, or
  `{"action":"export"}` for a native file export.
- The endpoint reuses loopback Host/Origin protections, accepts at most 16 KiB,
  returns 400 for invalid configuration, 409 for a stale revision and a sanitized
  503 for unavailable/failed device storage. It has no arbitrary path/URL argument.

See [backend rules](backend-rules.md) for the complete local API/security boundary.
No new dependencies, cloud rules or system privileges are required.

## Verification and next device checks

- [x] Production build and 45 frontend/packaging tests pass.
- [x] Backend suite: 271 tests run on Windows, with ten platform skips and no failures.
- [x] Browser: drag/swap, widget addition, original tick-gauge selection, resizing,
  save/reload persistence, narrow-screen scrolling, Original restoration and bundled
  pack preview/save checked.
- [x] Actual JSON export decoded by the backend validator; file import with an
  executable field was rejected in the browser.
- [x] Automated tests cover invalid/oversized packs, duplicate/out-of-grid widgets,
  private durable storage/reload, stale revisions, disk errors, export limits,
  API origin/body boundaries and unavailable sensor values.
- [x] Deploy backend and frontend together to the Pi via OTA and verify native startup.
- [ ] Verify cross-view saves, reboot persistence, real finger drag/scroll and the title keyboard.
- [ ] Check actual phone/OBD data, both gauge variants and audible playback outside
  edit mode. Profile optional blur with projection active on the target display.
- [ ] Add a versioned community catalog/download path and contributor workflow.

The widget feature was deployed to the reference Pi in `e4cca11` by the repaired
OTA flow. Native startup passed health/stability checks; the remaining interaction
and hardware checks above are still open. The release also includes the earlier
notification controls.
