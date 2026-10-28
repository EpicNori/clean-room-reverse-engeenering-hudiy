// Pure helpers for the unified Bluetooth screen (sections, row status, icons, messages).

export const CONNECT_FAILED = "Couldn't connect. Make sure the device is on and in range.";

const byName = (a, b) => {
  // Devices that only report their address go last, like on a phone.
  const unnamed = (d) => !d.name || d.name === d.address;
  return unnamed(a) - unnamed(b) || String(a.name).localeCompare(String(b.name)) || a.address.localeCompare(b.address);
};

export function deviceIcon(device) {
  if (device?.phone) return "smartphone";
  if (device?.audioReceiver) return "headphones";
  if (device?.serialPort) return "directions_car";
  return "bluetooth";
}

export function deviceKind(device) {
  if (device?.phone) return "Phone";
  if (device?.audioReceiver) return "Audio device";
  if (device?.serialPort) return "OBD adapter";
  return "Bluetooth device";
}

// Paired devices (connected first) and discovered unpaired devices.
export function splitDevices(devices = []) {
  const list = Array.isArray(devices) ? devices.filter((d) => d && typeof d.address === "string") : [];
  const paired = list.filter((d) => d.paired).sort((a, b) => Boolean(b.connected) - Boolean(a.connected) || byName(a, b));
  const available = list.filter((d) => !d.paired).sort(byName);
  return { paired, available };
}

// Returns {text, tone, busy}; tone is "busy", "connected", "error" or "idle".
export function deviceStatus(device, { operations = {}, pairingProgress = null } = {}) {
  const progress = pairingProgress?.address === device.address ? pairingProgress : null;
  const operation = operations?.[device.address];
  if (progress?.state === "pairing") return { text: "Pairing…", tone: "busy", busy: true };
  if (progress?.state === "connecting" || operation?.state === "connecting") return { text: "Connecting…", tone: "busy", busy: true };
  if (operation?.state === "disconnecting") return { text: "Disconnecting…", tone: "busy", busy: true };
  if (device.connected) return { text: "Connected", tone: "connected", busy: false };
  if (progress?.state === "failed") return { text: progress.message || "Pairing did not complete. Try again.", tone: "error", busy: false };
  if (operation?.state === "failed") return { text: operation.message || CONNECT_FAILED, tone: "error", busy: false };
  if (device.paired) return { text: "Not connected", tone: "idle", busy: false };
  return { text: "", tone: "idle", busy: false };
}

export function isAudioOutput(device, audioRoute) {
  return Boolean(device?.address && audioRoute?.address === device.address);
}

const MESSAGES = [
  [/operation in progress|still busy/i, "Bluetooth is busy. Try again in a moment."],
  [/pending pairing/i, "Finish the current pairing first."],
  [/pairing agent is unavailable|requires our bluez agent|independent pairing requires/i, "Pairing is not ready yet. Try again in a moment."],
  [/turn on bluetooth|turned off/i, "Turn on Bluetooth first."],
  [/service unavailable|requires? the pi|available on the pi|not running|action unavailable|failed to fetch|networkerror/i, "Bluetooth is not available right now."],
  [/currently paired|discovered unpaired/i, "The device is no longer in the list. Search again."],
];

// Backend errors are already short English; map the technical ones to friendlier text.
export function friendlyBluetoothError(message) {
  const text = typeof message === "string" ? message.trim() : "";
  if (!text) return "Something went wrong. Please try again.";
  for (const [pattern, friendly] of MESSAGES) if (pattern.test(text)) return friendly;
  return text.length > 160 ? `${text.slice(0, 157)}…` : text;
}

export function validDeviceName(value) {
  const name = typeof value === "string" ? value.trim() : "";
  // Printable text only (no control characters), like the backend check.
  return name.length >= 1 && name.length <= 64 && !/[\u0000-\u001f\u007f-\u009f]/.test(name);
}
