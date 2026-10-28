import test from "node:test";
import assert from "node:assert/strict";
import { createLatestQueue } from "../src/latestQueue.mjs";

const deferred = () => {
  let resolve;
  const promise = new Promise((r) => (resolve = r));
  return { promise, resolve };
};

test("a slider drag sends at most one request in flight and always the final value", async () => {
  const queue = createLatestQueue(),
    sent = [],
    gates = [];
  const send = async (value) => {
    sent.push(value);
    const gate = deferred();
    gates.push(gate);
    await gate.promise;
  };
  let done;
  for (let step = 0; step <= 48; step++)
    done = queue.push({ equalizer: [step / 4], preset: "Custom" }, send);
  assert.equal(sent.length, 1);
  assert.equal(queue.busy, true);
  assert.equal(queue.pending, true);
  gates[0].resolve();
  await new Promise((r) => setTimeout(r));
  assert.equal(sent.length, 2);
  assert.deepEqual(sent[1], { equalizer: [12], preset: "Custom" });
  assert.equal(queue.pending, false);
  gates[1].resolve();
  await done;
  assert.equal(queue.busy, false);
  assert.deepEqual(sent, [
    { equalizer: [0], preset: "Custom" },
    { equalizer: [12], preset: "Custom" },
  ]);
});

test("merges pending patches so different keys are not lost", async () => {
  const queue = createLatestQueue(),
    sent = [],
    gate = deferred();
  const send = async (value) => {
    sent.push(value);
    if (sent.length === 1) await gate.promise;
  };
  queue.push({ balance: 1 }, send);
  queue.push({ equalizer: [1], preset: "Custom" }, send);
  queue.push({ balance: 3 }, send);
  const done = queue.push({ equalizer: [2], preset: "Custom" }, send);
  gate.resolve();
  await done;
  assert.deepEqual(sent, [
    { balance: 1 },
    { equalizer: [2], preset: "Custom", balance: 3 },
  ]);
});

test("a failed request does not stall later values; latest sender is used", async () => {
  const queue = createLatestQueue(),
    calls = [];
  const failing = async (value) => {
    calls.push(["old", value]);
    throw Error("offline");
  };
  const working = async (value) => calls.push(["new", value]);
  queue.push({ preset: "Pop" }, failing);
  const done = queue.push({ preset: "Rock" }, working);
  await done;
  assert.deepEqual(calls, [
    ["old", { preset: "Pop" }],
    ["new", { preset: "Rock" }],
  ]);
  assert.equal(queue.busy, false);
  await queue.push({ preset: "Jazz" }, working);
  assert.deepEqual(calls.at(-1), ["new", { preset: "Jazz" }]);
});
