import test from "node:test";
import assert from "node:assert/strict";
import {
  CONNECT_FAILED,
  deviceIcon,
  deviceStatus,
  friendlyBluetoothError,
  isAudioOutput,
  splitDevices,
  validDeviceName,
} from "../src/bluetoothScreen.mjs";

const phone = { address: "AA:00:00:00:00:01", name: "Pixel", paired: true, connected: true, phone: true };
const speaker = { address: "AA:00:00:00:00:02", name: "JBL Flip", paired: true, connected: false, audioReceiver: true };
const obd = { address: "AA:00:00:00:00:03", name: "OBDII", paired: true, connected: false, serialPort: true };
const nearby = { address: "AA:00:00:00:00:04", name: "Headset", paired: false, connected: false };
const unnamed = { address: "AA:00:00:00:00:05", name: "AA:00:00:00:00:05", paired: false, connected: false };

test("paired devices list connected first; discovered devices list named before unnamed", () => {
  const { paired, available } = splitDevices([unnamed, obd, nearby, speaker, phone, null, { name: "broken" }]);
  assert.deepEqual(paired.map((d) => d.name), ["Pixel", "JBL Flip", "OBDII"]);
  assert.deepEqual(available.map((d) => d.address), [nearby.address, unnamed.address]);
  assert.deepEqual(splitDevices(undefined), { paired: [], available: [] });
});

test("icons distinguish phone, audio receiver, OBD serial adapter and other devices", () => {
  assert.equal(deviceIcon(phone), "smartphone");
  assert.equal(deviceIcon(speaker), "headphones");
  assert.equal(deviceIcon(obd), "directions_car");
  assert.equal(deviceIcon(nearby), "bluetooth");
  assert.equal(deviceIcon(null), "bluetooth");
});

test("row status follows pairing progress, then connection operations, then the live state", () => {
  assert.equal(deviceStatus(phone).text, "Connected");
  assert.equal(deviceStatus(speaker).text, "Not connected");
  assert.equal(deviceStatus(nearby).text, "");
  const operations = {
    [speaker.address]: { state: "connecting", message: "" },
    [phone.address]: { state: "disconnecting", message: "" },
    [obd.address]: { state: "failed", message: "" },
  };
  assert.deepEqual(deviceStatus(speaker, { operations }), { text: "Connecting…", tone: "busy", busy: true });
  assert.equal(deviceStatus(phone, { operations }).text, "Disconnecting…");
  assert.deepEqual(deviceStatus(obd, { operations }), { text: CONNECT_FAILED, tone: "error", busy: false });
  // A later successful connection wins over an old failure.
  assert.equal(deviceStatus({ ...obd, connected: true }, { operations }).text, "Connected");
  const pairing = { address: nearby.address, state: "pairing", message: "" };
  assert.equal(deviceStatus(nearby, { pairingProgress: pairing }).text, "Pairing…");
  assert.equal(deviceStatus(nearby, { pairingProgress: { ...pairing, state: "connecting" } }).text, "Connecting…");
  assert.equal(deviceStatus(phone, { pairingProgress: pairing }).text, "Connected");
  const failed = deviceStatus(nearby, { pairingProgress: { ...pairing, state: "failed", message: "Pairing was cancelled or the codes did not match." } });
  assert.equal(failed.tone, "error");
  assert.match(failed.text, /cancelled/);
});

test("audio output marker only for the selected route address", () => {
  assert.equal(isAudioOutput(speaker, { address: speaker.address }), true);
  assert.equal(isAudioOutput(phone, { address: speaker.address }), false);
  assert.equal(isAudioOutput(speaker, null), false);
  assert.equal(isAudioOutput({}, { address: undefined }), false);
});

test("technical backend errors become short friendly messages", () => {
  assert.equal(friendlyBluetoothError("Bluetooth operation in progress"), "Bluetooth is busy. Try again in a moment.");
  assert.equal(friendlyBluetoothError("Turn on Bluetooth first"), "Turn on Bluetooth first.");
  assert.equal(friendlyBluetoothError("Bluetooth controls require the Pi"), "Bluetooth is not available right now.");
  assert.equal(friendlyBluetoothError("End the phone call before disconnecting Bluetooth"), "End the phone call before disconnecting Bluetooth");
  assert.equal(friendlyBluetoothError(""), "Something went wrong. Please try again.");
  assert.ok(friendlyBluetoothError("x".repeat(500)).length <= 160);
});

test("device names must be 1-64 printable characters", () => {
  assert.equal(validDeviceName("  Car radio "), true);
  assert.equal(validDeviceName("x".repeat(64)), true);
  for (const value of ["", "   ", "x".repeat(65), "bad\nname", null, 7]) assert.equal(validDeviceName(value), false);
});
