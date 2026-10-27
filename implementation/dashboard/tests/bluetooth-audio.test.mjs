import test from "node:test";
import assert from "node:assert/strict";
import {
  canUseBluetoothAudio,
  useBluetoothAudio,
} from "../src/bluetoothAudio.mjs";
const receiver = {
  name: "Receiver",
  address: "AA:BB:CC:DD:EE:01",
  paired: true,
  audioReceiver: true,
  connected: false,
};
test("only paired audio output receivers qualify, not phones or OBD serial devices", () => {
  assert.equal(canUseBluetoothAudio(receiver), true);
  for (const device of [
    null,
    {},
    { ...receiver, paired: false },
    { paired: true, audioSource: true },
    { paired: true, serialPort: true },
  ])
    assert.equal(canUseBluetoothAudio(device), false);
});
test("saves the shared audio selection before connecting; never starts playback", async () => {
  const calls = [];
  const action = async (name, args) => {
    calls.push([name, args]);
    return name === "audio-radio-output" ? { saved: true } : { accepted: true };
  };
  assert.equal((await useBluetoothAudio(receiver, action)).saved, true);
  assert.deepEqual(calls, [
    ["audio-radio-output", { address: receiver.address }],
    ["bluetooth-connect", { address: receiver.address }],
  ]);
  calls.length = 0;
  await useBluetoothAudio({ ...receiver, connected: true }, action);
  assert.equal(calls.length, 1);
});
test("failed saving leaves connection untouched; failed connection reports saved selection accurately", async () => {
  const calls = [];
  const failed = await useBluetoothAudio(receiver, async (name) => {
    calls.push(name);
    return null;
  });
  assert.equal(failed.saved, false);
  assert.deepEqual(calls, ["audio-radio-output"]);
  const partial = await useBluetoothAudio(receiver, async (name) =>
    name === "audio-radio-output" ? { saved: true } : null,
  );
  assert.equal(partial.saved, true);
  assert.match(partial.message, /connection failed/);
  await assert.rejects(
    useBluetoothAudio({ paired: true, serialPort: true }, () => {
      throw Error("must not run");
    }),
    /paired audio output/,
  );
});
