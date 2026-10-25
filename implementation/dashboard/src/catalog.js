export const appCategories = [
  ["Phone", "call"],
  ["Music", "library_music"],
  ["Android Auto", "navigation"],
  ["Autobox", "smartphone"],
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
    ["Favorites", "contacts", "favorites"],
    ["Dialpad", "dialpad", "dialpad"],
    ["Call log", "phone_in_talk", "call-log"],
    ["Active call", "phone_in_talk", "active-call"],
    ["Notifications", "notifications", "notifications"],
  ],
  Music: [
    ["Storage Music", "audio_file", "storage"],
    ["FM Radio", "cell_tower", "radio"],
    ["A2DP", "bluetooth_audio", "a2dp"],
    ["Autobox Music", "smartphone", "autobox-music"],
    ["Android Auto", "navigation", "android-music"],
  ],
  "Android Auto": [
    ["Connect USB", "usb", "android-usb"],
    ["Connect WiFi", "wifi", "android-wifi"],
    ["Resume", "redo", "android-resume"],
    ["Quit", "close", "android-quit"],
  ],
  Autobox: [
    ["Connect WiFi", "wifi", "autobox-wifi"],
    ["Resume", "redo", "autobox-resume"],
  ],
  Hudiy: [
    ["Active apps", "web_asset", "active-apps"],
    ["Settings", "settings", "settings"],
    ["Quit", "disabled_by_default", "quit"],
    ["OBD Charts", "show_chart", "obd-charts"],
    ["OBD Blocks", "more_horiz", "obd-blocks"],
    ["Combined", "speed", "combined"],
    ["Gauges", "speed", "gauges"],
    ["Gauges 2", "speed", "gauges-2"],
    ["My OBD", "dashboard_customize", "custom-obd"],
    ["OBD Logs", "description", "obd-logs"],
    ["Extensions", "storefront", "marketplace"],
  ],
  System: [
    ["Theme", "palette", "theme"],
    ["Appearance", "design_services", "appearance"],
    ["Application", "settings_applications", "application"],
    ["Notifications", "notifications", "notification-settings"],
    ["Overlays", "picture_in_picture", "overlays"],
    ["About", "info", "about"],
    ["Music", "library_music", "music-settings"],
    ["Contacts", "contacts", "contacts-settings"],
    ["Software updates", "system_update", "software-update"],
  ],
  Projections: [
    ["Android Auto", "navigation", "android-settings"],
    ["Autobox", "smartphone", "autobox-settings"],
  ],
  Audio: [
    ["Sound", "spatial_audio", "sound"],
    ["Audio input", "mic", "audio-input"],
    ["Equalizer", "tune", "equalizer"],
    ["Presets", "equalizer", "presets"],
  ],
  Bluetooth: [
    ["Pair", "add", "pair"],
    ["Remove", "remove", "remove"],
    ["Connections", "bluetooth_connected", "bluetooth-connections"],
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
