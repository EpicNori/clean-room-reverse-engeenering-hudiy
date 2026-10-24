export const KEY = "hudiy.custom-obd.v1";
export const STOCK = {
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
export const DERIVED = {
  acceleration: {
    label: "Acceleration",
    unit: "m/s²",
    min: -10,
    max: 10,
    decimals: 2,
  },
  range: {
    label: "Estimated range",
    unit: "km",
    min: 0,
    max: 1000,
    decimals: 0,
  },
  zeroToHundred: {
    label: "0–100 km/h",
    unit: "s",
    min: 0,
    max: 30,
    decimals: 2,
  },
  bestZeroToHundred: {
    label: "Best 0–100 km/h",
    unit: "s",
    min: 0,
    max: 30,
    decimals: 2,
  },
  averageConsumption: {
    label: "Average consumption",
    unit: "L/100km",
    min: 0,
    max: 30,
    decimals: 1,
  },
};
export const TEMPLATES = [
  {
    label: "Oil temperature",
    unit: "°C",
    mode: "01",
    pid: "5C",
    header: null,
    bytes: 1,
    formula: "A-40",
    min: -40,
    max: 180,
    decimals: 0,
    interval: 5,
  },
  {
    label: "Fuel level",
    unit: "%",
    mode: "01",
    pid: "2F",
    header: null,
    bytes: 1,
    formula: "A*100/255",
    min: 0,
    max: 100,
    decimals: 1,
    interval: 5,
  },
  {
    label: "Fuel rate",
    unit: "L/h",
    mode: "01",
    pid: "5E",
    header: null,
    bytes: 2,
    formula: "(A*256+B)/20",
    min: 0,
    max: 100,
    decimals: 2,
    interval: 5,
  },
  {
    label: "Custom sensor",
    unit: "",
    mode: "22",
    pid: "1234",
    header: null,
    bytes: 1,
    formula: "A",
    min: 0,
    max: 255,
    decimals: 1,
    interval: 5,
  },
];
export const id = () =>
  "w_" + crypto.randomUUID().replaceAll("-", "").slice(0, 12);
export const defaultConfig = () => ({
  sensors: [],
  widgets: [
    {
      id: "speed",
      source: "builtin:speed",
      title: "",
      view: "value",
      x: 0,
      y: 0,
      w: 1,
      h: 1,
    },
    {
      id: "rpm",
      source: "builtin:rpm",
      title: "",
      view: "gauge",
      x: 1,
      y: 0,
      w: 1,
      h: 1,
    },
    {
      id: "coolant",
      source: "builtin:coolant",
      title: "",
      view: "value",
      x: 2,
      y: 0,
      w: 1,
      h: 1,
    },
    {
      id: "errors",
      source: "errors",
      title: "",
      view: "value",
      x: 0,
      y: 1,
      w: 1,
      h: 2,
    },
    {
      id: "acceleration",
      source: "derived:acceleration",
      title: "",
      view: "graph",
      x: 1,
      y: 1,
      w: 2,
      h: 2,
    },
  ],
  range: { tankLitres: null, fuelLevel: null, fuelRate: null },
});
export function reading(config, source) {
  const [kind, key] = source.split(":");
  return kind === "builtin"
    ? STOCK[key]
    : kind === "derived"
      ? DERIVED[key]
      : kind === "custom"
        ? config.sensors.find((s) => s.id === key)
        : { label: "Messages & trouble codes", unit: "" };
}
export const sources = (config) => [
  ...Object.entries(STOCK).map(([key, v]) => ({
    source: "builtin:" + key,
    ...v,
  })),
  ...Object.entries(DERIVED).map(([key, v]) => ({
    source: "derived:" + key,
    ...v,
  })),
  ...config.sensors.map((v) => ({ ...v, source: "custom:" + v.id })),
  { source: "errors", label: "Messages & trouble codes", unit: "" },
];
export const overlaps = (a, b) =>
  a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
export const fits = (a, items) =>
  a.x >= 0 &&
  a.y >= 0 &&
  a.x + a.w <= 4 &&
  a.y + a.h <= 8 &&
  !items.some((b) => b.id !== a.id && overlaps(a, b));
export function firstSpace(items, w = 1, h = 1) {
  for (let y = 0; y < 8; y++)
    for (let x = 0; x < 4; x++)
      if (fits({ id: "", x, y, w, h }, items)) return { x, y };
  return null;
}
export function place(items, identifier, x, y, size = {}) {
  const current = items.find((w) => w.id === identifier);
  if (!current) return items;
  const next = { ...current, x, y, ...size };
  if (fits(next, items))
    return items.map((w) => (w.id === identifier ? next : w));
  const hit = items.filter((w) => w.id !== identifier && overlaps(next, w));
  if (hit.length === 1) {
    const swapped = { ...hit[0], x: current.x, y: current.y };
    const remaining = items.filter(
      (w) => w.id !== identifier && w.id !== swapped.id,
    );
    if (fits(next, remaining) && fits(swapped, [...remaining, next]))
      return items.map((w) =>
        w.id === identifier ? next : w.id === swapped.id ? swapped : w,
      );
  }
  return items;
}
export function sample(
  config,
  source,
  telemetry,
  revision,
  stamp = Date.now() / 1000,
) {
  if (!telemetry?.connected) return { value: null, error: "OBD disconnected" };
  const [kind, key] = source.split(":");
  if (kind === "custom") {
    if (telemetry.customRevision !== revision)
      return { value: null, error: "Waiting for sensor update" };
    const value = telemetry.custom?.[key];
    const definition = reading(config, source);
    if (!value) return { value: null, error: "Waiting for sensor update" };
    if (stamp - value.timestamp > Math.max(3, definition.interval * 2))
      return { value: null, error: "Reading is stale" };
    return value;
  }
  if (!Number.isFinite(telemetry.timestamp) || stamp - telemetry.timestamp > 5)
    return { value: null, error: "Reading is stale" };
  const value =
    kind === "derived" ? telemetry.derived?.[key] : telemetry.values?.[key];
  return { value: Number.isFinite(value) ? value : null, error: null };
}
export function validateLocal(config) {
  if (
    !config ||
    !Array.isArray(config.sensors) ||
    config.sensors.length > 8 ||
    !Array.isArray(config.widgets) ||
    config.widgets.length > 16 ||
    !config.range
  )
    return false;
  const options = new Set(sources(config).map((v) => v.source)),
    ids = new Set();
  return config.widgets.every((w) => {
    if (
      typeof w.id !== "string" ||
      ids.has(w.id) ||
      !options.has(w.source) ||
      !["value", "gauge", "graph"].includes(w.view) ||
      ![w.x, w.y, w.w, w.h].every(Number.isInteger) ||
      ![1, 2].includes(w.w) ||
      ![1, 2].includes(w.h)
    )
      return false;
    ids.add(w.id);
    return fits(w, config.widgets);
  });
}
export function readLocal() {
  try {
    const value = JSON.parse(localStorage.getItem(KEY));
    if (validateLocal(value)) return value;
  } catch {}
  return defaultConfig();
}

export function validateSensor(sensor) {
  if (
    typeof sensor.label !== "string" ||
    !sensor.label.trim() ||
    sensor.label.length > 40 ||
    typeof sensor.unit !== "string" ||
    sensor.unit.length > 16
  )
    return "Enter a sensor name and short unit.";
  if (
    !["01", "22"].includes(sensor.mode) ||
    !(sensor.mode === "01" ? /^[0-9A-F]{2}$/ : /^[0-9A-F]{4}$/).test(sensor.pid)
  )
    return "Use 2 hex digits for Mode 01 or 4 for Mode 22.";
  if (
    sensor.header !== null &&
    (!/^[0-9A-F]{3}$|^[0-9A-F]{8}$/.test(sensor.header) ||
      parseInt(sensor.header, 16) >
        (sensor.header.length === 3 ? 0x7ff : 0x1fffffff))
  )
    return "Enter a valid CAN ECU header or leave it empty.";
  for (const [key, low, high] of [
    ["bytes", 1, 8],
    ["decimals", 0, 3],
    ["interval", 1, 60],
  ])
    if (
      !Number.isInteger(sensor[key]) ||
      sensor[key] < low ||
      sensor[key] > high
    )
      return `Check ${key}.`;
  if (
    !Number.isFinite(sensor.min) ||
    !Number.isFinite(sensor.max) ||
    Math.abs(sensor.min) > 1e9 ||
    Math.abs(sensor.max) > 1e9 ||
    sensor.min >= sensor.max
  )
    return "Check the minimum and maximum.";
  const expression = sensor.formula;
  if (
    typeof expression !== "string" ||
    !expression.trim() ||
    expression.length > 96
  )
    return "Use a formula of up to 96 characters.";
  const tokens = [],
    pattern =
      /\s*(0x[0-9a-fA-F]+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-H]|\/\/|[()+*/%&|^\-])/y;
  let cursor = 0;
  while (cursor < expression.length) {
    if (!expression.slice(cursor).trim()) break;
    pattern.lastIndex = cursor;
    const match = pattern.exec(expression);
    if (!match) return "Use A–H, numbers and arithmetic operators only.";
    tokens.push(match[1]);
    cursor = pattern.lastIndex;
    if (tokens.length > 48) return "Formula is too complex.";
  }
  let index = 0;
  const precedence = {
    "|": 1,
    "^": 2,
    "&": 3,
    "+": 4,
    "-": 4,
    "*": 5,
    "/": 5,
    "//": 5,
    "%": 5,
  };
  function parse(min = 0, depth = 0) {
    if (depth > 20) throw Error("Formula is too deeply nested.");
    const token = tokens[index++];
    if (token === "+" || token === "-") parse(6, depth + 1);
    else if (token === "(") {
      parse(0, depth + 1);
      if (tokens[index++] !== ")") throw Error("Close every parenthesis.");
    } else if (/^[A-H]$/.test(token || "")) {
      if (token.charCodeAt(0) - 65 >= sensor.bytes)
        throw Error("Formula uses a byte beyond the response size.");
    } else if (
      token === undefined ||
      !Number.isFinite(Number(token)) ||
      Math.abs(Number(token)) > 1e9
    )
      throw Error("Check the formula syntax and constants.");
    while (index < tokens.length && precedence[tokens[index]] >= min) {
      const op = tokens[index++];
      parse(precedence[op] + 1, depth + 1);
    }
  }
  try {
    parse();
    if (index !== tokens.length) return "Check the formula syntax.";
  } catch (e) {
    return e.message;
  }
  return null;
}
