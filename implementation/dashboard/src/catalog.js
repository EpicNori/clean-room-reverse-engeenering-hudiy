export const appCategories = [
  ["Phone", "call"],
  ["Music", "library_music"],
  ["Android Auto", "navigation"],
  ["Vehicle", "directions_car"],
  ["Hudiy", "apps"],
];
export const settingCategories = [
  ["System", "settings"],
  ["Projections", "cast"],
  ["Audio", "volume_up"],
  ["Bluetooth", "bluetooth"],
];
export const menus = {
  Phone: [
    ["Contacts", "contacts", "contacts"],
    ["Favorites", "star", "favorites"],
    ["Dialpad", "dialpad", "dialpad"],
    ["Call log", "history", "call-log"],
    ["Active call", "phone_in_talk", "active-call"],
  ],
  Music: [
    ["Storage Music", "audio_file", "storage"],
    ["FM Radio", "cell_tower", "radio"],
    ["A2DP", "bluetooth_audio", "a2dp"],
    ["Android Auto", "navigation", "android-music"],
  ],
  "Android Auto": [
    ["Connect USB", "usb", "android-usb"],
    ["Connect WiFi", "wifi", "android-wifi"],
    ["Resume", "redo", "android-resume"],
    ["Quit", "close", "android-quit"],
  ],
  // Every vehicle view and its adapter settings live together.
  Vehicle: [
    ["My OBD", "dashboard_customize", "custom-obd"],
    ["Gauges", "speed", "gauges"],
    ["Gauges 2", "speed", "gauges-2"],
    ["Combined", "speed", "combined"],
    ["OBD Charts", "show_chart", "obd-charts"],
    ["OBD Blocks", "more_horiz", "obd-blocks"],
    ["OBD Logs", "description", "obd-logs"],
    ["OBD settings", "settings_input_component", "obd-settings"],
  ],
  Hudiy: [
    ["Settings", "settings", "settings"],
    ["Extensions", "storefront", "marketplace"],
    ["Quit", "disabled_by_default", "quit"],
  ],
  System: [
    ["Dashboard", "dashboard_customize", "dashboard-editor"],
    ["Theme", "palette", "theme"],
    ["Appearance", "design_services", "appearance"],
    ["Notifications", "notifications", "notification-settings"],
    ["Application", "settings_applications", "application"],
    ["Software updates", "system_update", "software-update"],
    ["About", "info", "about"],
  ],
  Projections: [
    ["Android Auto", "navigation", "android-settings"],
  ],
  Audio: [
    ["Sound", "spatial_audio", "sound"],
    ["Audio input", "mic", "audio-input"],
    ["Equalizer", "tune", "equalizer"],
    ["Presets", "equalizer", "presets"],
    ["Music refresh", "library_music", "music-settings"],
  ],
  Bluetooth: [
    ["Bluetooth", "bluetooth", "bluetooth-connections"],
    ["Contact sync", "contacts", "contacts-settings"],
  ],
};
export const defaults = {
  dark: false,
  accent: 1,
  contrast: 0,
  opacity: 100,
  timeFormat: "24h",
  showClock: true,
  barHeight: 81,
  hotspot: false,
  showCursor: false,
  notificationsEnabled: true,
  toastNotice: true,
  outputNotice: true,
  inputNotice: true,
  nowPlayingNotice: true,
  notificationDuration: 8,
  toastDuration: 2,
  darkAccent: 0,
  darkContrast: 1,
  navigationOverlay: "None",
  volumeOverlay: "None",
  xStep: 1,
  yStep: 1,
  blackStartup: true,
  androidAutoConnect: true,
  androidAutostart: false,
  androidTaskbar: true,
  musicRefreshSeconds: 1,
  contactsRefreshSeconds: 60,
  androidDayNight: "Common",
  autoboxWireless: true,
  autoboxDayNight: "Common",
  mute: false,
  volume: 80,
  balance: 0,
  fade: 0,
  subwoofer: 0,
  equalizer: Array(15).fill(0),
  preset: "Flat",
  demo: false,
};
export const frequencies = [
  "25",
  "40",
  "63",
  "100",
  "160",
  "250",
  "400",
  "630",
  "1",
  "1.6",
  "2.5",
  "4",
  "6.3",
  "10",
  "16",
];
export const colors = [
  "#799ee4",
  "#872274",
  "#dce1bc",
  "#ff8700",
  "#e5dc3d",
  "#2eeb59",
  "#ec1628",
  "#43d34a",
];
export function readPreferences() {
  try {
    const raw = JSON.parse(localStorage.getItem("hudiy.preferences") || "{}"),
      result = { ...defaults };
    for (const [key, value] of Object.entries(raw)) {
      if (!(key in result)) continue;
      if (key === "equalizer") {
        if (
          Array.isArray(value) &&
          value.length === 15 &&
          value.every((v) => Number.isFinite(v) && Math.abs(v) <= 12)
        )
          result[key] = value;
      } else if (typeof value === typeof result[key]) result[key] = value;
    }
    result.volume = Math.max(0, Math.min(100, result.volume));
    result.barHeight = Math.max(65, Math.min(100, result.barHeight));
    result.accent = Math.max(0, Math.min(7, Math.round(result.accent)));
    for (const [key, low, high] of [['musicRefreshSeconds', 1, 60], ['contactsRefreshSeconds', 5, 3600], ['notificationDuration', 1, 15], ['toastDuration', 1, 15]]) {
      if (!Number.isInteger(result[key]) || result[key] < low || result[key] > high) result[key] = defaults[key];
    }
    return result;
  } catch {
    return { ...defaults };
  }
}
