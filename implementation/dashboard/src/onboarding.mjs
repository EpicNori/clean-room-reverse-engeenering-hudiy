export const GUIDE_VERSION = 1;
export const GUIDE_KEY = "coscaros.onboarding.v1";
export const GUIDE_STEPS = [
  {
    id: "welcome",
    title: "Welcome to coscarOS",
    route: "dashboard",
    body: "Your dashboard brings phone projection, music and vehicle data together. This guided tour shows you where everything lives. Park before setup. Nothing is paired, played, recorded or installed by this tour.",
  },
  {
    id: "dashboard",
    title: "Your everyday dashboard",
    route: "dashboard",
    target: "dashboard",
    body: "Start here for the clock, navigation, music and phone shortcuts. Connected devices supply live information; empty fields mean data is unavailable. The dashboard button always brings you home.",
  },
  {
    id: "taskbar",
    title: "Your shortcuts stay close",
    route: "dashboard",
    target: "taskbar",
    body: "The bottom taskbar opens the dashboard and Applications, adjusts sound and returns to Android Auto. Long-press a shortcut to move it. Long-press an application to pin it. Swipe lists to scroll.",
  },
  {
    id: "apps",
    title: "Find your applications",
    route: "apps",
    category: "Hudiy",
    target: "menu",
    body: "Choose a category on the left, then an application on the right. Vehicle holds My OBD, the gauge and chart views, OBD Logs and OBD settings. coscarOS contains Settings, Extensions and Quit. Back returns to the previous page.",
  },
  {
    id: "studio",
    title: "Build your dashboard",
    route: "dashboard-editor",
    target: "studio",
    body: "Dashboard Studio adds, removes, names and resizes widgets. Drag a grip to move or swap them; use Move controls as an alternative. Choose Appearance for optional glass, colors and spacing. Save applies changes; Cancel keeps your saved dashboard.",
  },
  {
    id: "extensions",
    title: "Choose and share a layout",
    route: "marketplace",
    target: "extensions",
    body: "Preview a bundled layout before saving it. Import and export JSON layout files to share your design. Files contain settings, not phone or vehicle readings. Online community downloads are planned.",
  },
  {
    id: "settings",
    title: "Make it yours in Settings",
    route: "settings",
    category: "System",
    target: "menu",
    body: "Settings groups System, Projections, Audio and Bluetooth. System contains the dashboard editor, appearance, notification controls and software updates. Music refresh is under Audio; Contact sync is under Bluetooth. You can replay this tour in System → Application.",
  },
  {
    id: "theme",
    title: "Appearance and comfortable viewing",
    route: "theme",
    target: "settings",
    body: "Choose your light or dark theme and accent color here. System → Appearance controls the clock, taskbar and black startup screen. Physical screen brightness is a separate display control in the projection settings.",
  },
  {
    id: "pair",
    title: "Pair your phone",
    route: "bluetooth-connections",
    target: "bluetooth",
    body: "After the tour, open Settings → Bluetooth → Pair, enable Bluetooth on the phone and select it. Confirm matching codes on both devices. Allow contact sharing if you want your phonebook. Connections shows paired devices; OBD and optional radio audio are separate devices.",
  },
  {
    id: "android",
    title: "Connect Android Auto",
    route: "android-settings",
    target: "settings",
    body: "USB: use a data-capable cable and approve the phone prompt. Wireless: pair Bluetooth, configure the Pi hotspot and keep Wi-Fi enabled on your phone. Disable a VPN if it blocks connection. Automatic connection and automatic opening are separate switches; keep the taskbar visible if preferred. Apple CarPlay is not currently implemented.",
  },
  {
    id: "contacts",
    title: "Contacts and calls",
    route: "contacts-settings",
    target: "settings",
    body: "Bluetooth contact-sharing permission supplies Contacts, Favorites and Call log. Use touch filters or the dialpad to select a number, then explicitly confirm a call. Set the contact refresh interval here. Phone audio and microphone routing depend on connected hardware.",
  },
  {
    id: "music",
    title: "Music and live information",
    route: "music-settings",
    target: "settings",
    body: "Choose Storage, Bluetooth or Android Auto from Applications → Music. Play/pause and track buttons control the selected source. Music data refresh defaults to one second and can be changed here. Spotify playing on another device may not update the phone's projection metadata.",
  },
  {
    id: "audio",
    title: "Choose sound output",
    route: "sound",
    target: "settings",
    body: "Select the desired output and volume. A Bluetooth receiver connected to the car radio is optional; pair it separately and select it as output. Audio → Equalizer and Presets shape sound. Selecting an output does not start music.",
  },
  {
    id: "microphone",
    title: "Choose your microphone",
    route: "audio-input",
    target: "settings",
    body: "Select an actual audio capture device, adjust gain or mute, then Save. Missing devices stay marked unavailable. This page does not start microphone capture. Android Auto voice input and Bluetooth call audio follow separate routing paths.",
  },
  {
    id: "obd",
    title: "Connect vehicle diagnostics",
    route: "obd-settings",
    target: "settings",
    body: "Use a compatible powered Bluetooth ELM327 adapter for vehicle data. Pair and select the adapter in OBD settings, then connect. Standard readings depend on the vehicle. Disconnected or unsupported values remain unavailable; the tour does not connect an adapter.",
  },
  {
    id: "my-obd",
    title: "Arrange your vehicle readings",
    route: "custom-obd",
    target: "obd",
    body: "My OBD is your configurable vehicle page: blocks, original gauges, charts and messages. Edit the grid to choose positions, sizes and sources. Custom read-only PIDs and formulas depend on your car; validate them before relying on the result. Layout editing is separate from diagnostic recording.",
  },
  {
    id: "logs",
    title: "Record a diagnostic session",
    route: "obd-logs",
    target: "logs",
    body: "OBD Logs records supported readings, custom sensors, raw replies, trouble codes and connection events. Choose manual recording or automatic recording on connection, categories, sample intervals and storage bounds. Stop and save before exporting CSV or JSONL. Exports can contain private vehicle data.",
  },
  {
    id: "updates",
    title: "Keep coscarOS up to date",
    route: "software-update",
    target: "updates",
    body: "Check GitHub for updates here. Choose manual installation or automatic installation while idle. Internet can use Ethernet or a suitable Wi-Fi route; wireless Android Auto may occupy the Pi's Wi-Fi. Updates can restart the application, so follow its readiness and recovery status.",
  },
  {
    id: "finish",
    title: "Ready to make it your own",
    route: "notification-settings",
    target: "settings",
    body: "Enable popup notifications is the master switch; turn it off to silence dashboard popups while keeping your individual choices. You have reached the end. Finish returns home. Replay any time from Settings → System → Application → Replay introduction. Next, pair your phone, select audio, then connect OBD when available.",
  },
];
export function guideState(raw) {
  if (
    !raw ||
    raw.version !== GUIDE_VERSION ||
    !["pending", "completed", "skipped"].includes(raw.outcome) ||
    !Number.isInteger(raw.step) ||
    raw.step < 0 ||
    raw.step >= GUIDE_STEPS.length
  )
    return { version: GUIDE_VERSION, outcome: "pending", step: 0 };
  return { version: GUIDE_VERSION, outcome: raw.outcome, step: raw.step };
}
export function readGuide(storage) {
  try {
    return guideState(JSON.parse(storage.getItem(GUIDE_KEY)));
  } catch {
    return guideState(null);
  }
}
export function guideRect(rect, width, height) {
  if (!rect || rect.width < 1 || rect.height < 1) return null;
  const left = Math.max(8, rect.left - 6),
    top = Math.max(8, rect.top - 6);
  const right = Math.min(width - 8, rect.right + 6),
    bottom = Math.min(height - 8, rect.bottom + 6);
  return right > left && bottom > top
    ? { left, top, width: right - left, height: bottom - top }
    : null;
}
