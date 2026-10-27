export const DASHBOARD_KEY = "coscaros.dashboard.v1";
export const WIDGETS = {
  clock: { label: "Clock", icon: "schedule", w: 2, h: 1 },
  navigation: { label: "Navigation", icon: "navigation", w: 2, h: 2 },
  music: { label: "Now playing", icon: "music_note", w: 2, h: 2 },
  phone: { label: "Phone", icon: "call", w: 2, h: 1 },
  connections: { label: "Connections", icon: "sensors", w: 2, h: 1 },
  shortcuts: { label: "Quick access", icon: "apps", w: 2, h: 1 },
  sensor: { label: "Vehicle reading", icon: "speed", w: 2, h: 1 },
  diagnostics: { label: "Diagnostics", icon: "monitor_heart", w: 2, h: 1 },
};
export const SENSOR_DEFINITIONS = {
  speed: {
    label: "Vehicle speed",
    unit: "km/h",
    min: 0,
    max: 255,
    decimals: 0,
  },
  rpm: { label: "Engine speed", unit: "rpm", min: 0, max: 8000, decimals: 0 },
  coolant: {
    label: "Coolant temperature",
    unit: "°C",
    min: -40,
    max: 150,
    decimals: 0,
  },
  load: { label: "Engine load", unit: "%", min: 0, max: 100, decimals: 1 },
  throttle: {
    label: "Throttle position",
    unit: "%",
    min: 0,
    max: 100,
    decimals: 1,
  },
  voltage: {
    label: "Control module voltage",
    unit: "V",
    min: 0,
    max: 20,
    decimals: 2,
  },
};
const create = (id, type, x, y, w = 2, h = 1) => ({
  id,
  type,
  title: WIDGETS[type].label,
  source: type === "sensor" ? "speed" : "",
  display: "block",
  x,
  y,
  w,
  h,
});
export const defaultDashboard = () => ({
  version: 1,
  enabled: false,
  appearance: {
    surface: "classic",
    backdrop: "aurora",
    accent: "theme",
    opacity: 84,
    blur: 12,
    radius: 22,
    gap: 12,
    motion: true,
  },
  widgets: [
    create("clock", "clock", 0, 0),
    create("navigation", "navigation", 0, 1, 2, 2),
    create("music", "music", 2, 0, 2, 3),
    create("phone", "phone", 4, 0),
    create("connections", "connections", 4, 1),
    create("shortcuts", "shortcuts", 4, 2),
  ],
});
const keys = (value, expected) =>
  value &&
  typeof value === "object" &&
  !Array.isArray(value) &&
  Object.keys(value).length === expected.length &&
  expected.every((k) => Object.hasOwn(value, k));
const integer = (v, low, high) => Number.isInteger(v) && v >= low && v <= high;
export const overlap = (a, b) =>
  a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
export const fitsWidget = (item, others) =>
  integer(item.x, 0, 5) &&
  integer(item.y, 0, 7) &&
  integer(item.w, 1, 6) &&
  integer(item.h, 1, 4) &&
  item.x + item.w <= 6 &&
  item.y + item.h <= 8 &&
  !others.some((other) => overlap(item, other));
export function validateDashboard(value) {
  if (
    !keys(value, ["version", "enabled", "appearance", "widgets"]) ||
    value.version !== 1 ||
    typeof value.enabled !== "boolean"
  )
    throw Error("Unsupported dashboard layout format");
  const a = value.appearance;
  if (
    !keys(a, [
      "surface",
      "backdrop",
      "accent",
      "opacity",
      "blur",
      "radius",
      "gap",
      "motion",
    ]) ||
    !["classic", "glass"].includes(a.surface) ||
    !["aurora", "midnight", "sunrise", "graphite"].includes(a.backdrop) ||
    typeof a.accent !== "string" ||
    !(a.accent === "theme" || /^#[0-9a-fA-F]{6}$/.test(a.accent)) ||
    typeof a.motion !== "boolean"
  )
    throw Error("Invalid dashboard appearance");
  for (const [key, low, high] of [
    ["opacity", 55, 100],
    ["blur", 0, 24],
    ["radius", 0, 36],
    ["gap", 4, 24],
  ])
    if (!integer(a[key], low, high))
      throw Error("Invalid appearance value: " + key);
  if (!Array.isArray(value.widgets) || value.widgets.length > 16)
    throw Error("Use at most 16 widgets");
  const seen = new Set();
  for (const [index, w] of value.widgets.entries()) {
    if (
      !keys(w, [
        "id",
        "type",
        "title",
        "source",
        "display",
        "x",
        "y",
        "w",
        "h",
      ]) ||
      typeof w.id !== "string" ||
      !/^[a-z][a-z0-9-]{0,31}$/.test(w.id) ||
      seen.has(w.id) ||
      !Object.hasOwn(WIDGETS, w.type) ||
      typeof w.title !== "string" ||
      Array.from(w.title).length > 48 ||
      /[\u0000-\u001f\u007f-\u009f]/.test(w.title)
    )
      throw Error("Invalid widget definition");
    seen.add(w.id);
    if (
      w.type === "sensor"
        ? !Object.hasOwn(SENSOR_DEFINITIONS, w.source) ||
          !["block", "arc", "ticks", "chart"].includes(w.display)
        : w.source !== "" || w.display !== "block"
    )
      throw Error("Invalid widget source/display");
    if (!fitsWidget(w, value.widgets.slice(0, index)))
      throw Error("Widgets overlap or exceed the grid");
  }
  return JSON.parse(JSON.stringify(value));
}
export function firstWidgetSpace(items, w = 2, h = 1) {
  for (let y = 0; y < 8; y++)
    for (let x = 0; x < 6; x++)
      if (fitsWidget({ x, y, w, h }, items)) return { x, y };
  return null;
}
export function placeWidget(items, id, x, y, size = {}) {
  const before = items.find((w) => w.id === id);
  if (!before) return null;
  let next = { ...before, ...size, x, y };
  const others = items.filter((w) => w.id !== id);
  if (fitsWidget(next, others))
    return items.map((w) => (w.id === id ? next : w));
  const collisions = others.filter((w) => overlap(w, next));
  if (collisions.length !== 1 || size.w || size.h) return null;
  const other = collisions[0];
  if (other.w !== before.w || other.h !== before.h) return null;
  next = { ...before, x: other.x, y: other.y };
  const swapped = { ...other, x: before.x, y: before.y };
  const rest = others.filter((w) => w.id !== other.id);
  if (
    !fitsWidget(next, [...rest, swapped]) ||
    !fitsWidget(swapped, [...rest, next])
  )
    return null;
  return items.map((w) =>
    w.id === id ? next : w.id === other.id ? swapped : w,
  );
}
export function addWidget(config, type) {
  const meta = WIDGETS[type];
  if (!meta || config.widgets.length >= 16) return null;
  const space = firstWidgetSpace(config.widgets, meta.w, meta.h);
  if (!space) return null;
  const id = "w-" + crypto.randomUUID().slice(0, 24);
  return {
    ...config,
    enabled: true,
    widgets: [
      ...config.widgets,
      create(id, type, space.x, space.y, meta.w, meta.h),
    ],
  };
}
export function readDashboard() {
  try {
    return validateDashboard(
      JSON.parse(localStorage.getItem(DASHBOARD_KEY) || "null"),
    );
  } catch {
    return defaultDashboard();
  }
}
export function dashboardPack(config) {
  return {
    format: "coscaros.dashboard",
    version: 1,
    name: "My dashboard",
    config: validateDashboard(config),
  };
}
export function parseDashboardPack(text) {
  if (typeof text !== "string" || new TextEncoder().encode(text).length > 16384)
    throw Error("Layout files must be 16 KiB or smaller");
  const pack = JSON.parse(text);
  if (
    !keys(pack, ["format", "version", "name", "config"]) ||
    pack.format !== "coscaros.dashboard" ||
    pack.version !== 1 ||
    typeof pack.name !== "string" ||
    Array.from(pack.name).length > 64 ||
    /[\u0000-\u001f\u007f-\u009f]/.test(pack.name)
  )
    throw Error("Choose a coscarOS dashboard layout file");
  return { ...pack, config: validateDashboard(pack.config) };
}
export function sensorReading(telemetry, source, now = Date.now()) {
  if (!telemetry?.connected) return { value: null, reason: "OBD disconnected" };
  if (
    !Number.isFinite(telemetry.timestamp) ||
    now / 1000 - telemetry.timestamp > 15
  )
    return { value: null, reason: "Waiting for fresh data" };
  const value = telemetry.values?.[source];
  return Number.isFinite(value)
    ? {
        value,
        reason: telemetry.mode === "simulator" ? "Simulator" : "Live OBD",
      }
    : { value: null, reason: "Not available" };
}
export const PRESETS = [
  {
    id: "original",
    name: "Original",
    description: "Keep the familiar four-card dashboard.",
    config: defaultDashboard(),
  },
  {
    id: "daily",
    name: "Daily drive",
    description: "Phone, music, navigation and connection status.",
    config: { ...defaultDashboard(), enabled: true },
  },
  {
    id: "glass",
    name: "Aurora glass",
    description: "Translucent panels with a calm aurora backdrop.",
    config: {
      ...defaultDashboard(),
      enabled: true,
      appearance: {
        ...defaultDashboard().appearance,
        surface: "glass",
        accent: "#b9a0ff",
      },
    },
  },
  {
    id: "focus",
    name: "Driver focus",
    description: "Large navigation, a clock and live vehicle readings.",
    config: {
      ...defaultDashboard(),
      enabled: true,
      widgets: [
        create("clock", "clock", 0, 0),
        create("nav", "navigation", 2, 0, 4, 2),
        { ...create("speed", "sensor", 0, 1, 2, 2), display: "arc" },
        create("music", "music", 2, 2, 4, 1),
      ],
    },
  },
];
