import test from "node:test";
import assert from "node:assert/strict";
import {
  defaultConfig,
  place,
  firstSpace,
  validateSensor,
  validateLocal,
  sample,
  reading,
} from "../src/customOBD.mjs";

const sensor = {
  id: "oil",
  label: "Oil",
  unit: "°C",
  mode: "01",
  pid: "5C",
  header: null,
  bytes: 1,
  formula: "A-40",
  min: -40,
  max: 180,
  decimals: 1,
  interval: 5,
};
test("dragging swaps compatible tiles and rejects collisions or outside coordinates", () => {
  const original = defaultConfig().widgets;
  const moved = place(original, "speed", 1, 0);
  assert.equal(moved.find((w) => w.id === "rpm").x, 0);
  assert.equal(moved.find((w) => w.id === "speed").x, 1);
  assert.equal(place(original, "speed", 4, 0), original);
  assert.equal(place(original, "speed", 0, 7, { h: 2 }), original);
  assert.equal(place(original, "speed", 0, 1), original);
  assert.deepEqual(firstSpace(original), { x: 3, y: 0 });
  assert.equal(validateLocal({ ...defaultConfig(), widgets: moved }), true);
});
test("grid persistence keeps logical positions independent of responsive presentation", () => {
  const cfg = defaultConfig();
  cfg.widgets = place(cfg.widgets, "speed", 3, 0);
  const saved = JSON.parse(JSON.stringify(cfg));
  assert.deepEqual(saved, cfg);
  assert.equal(validateLocal(saved), true);
  saved.widgets[1].x = 3;
  assert.equal(validateLocal(saved), false);
});
test("sensor editor validates PID size, bounded byte formulas and read-only modes", () => {
  assert.equal(validateSensor(sensor), null);
  assert.equal(
    validateSensor({ ...sensor, bytes: 2, formula: "(A*256+B)/4" }),
    null,
  );
  assert.equal(validateSensor({ ...sensor, formula: "(A&128)//128" }), null);
  for (const patch of [
    { mode: "04" },
    { pid: "221234" },
    { pid: "5C\r04" },
    { header: "FFF" },
    { formula: '__import__("os")' },
    { formula: "A+" },
    { formula: "A**8" },
    { formula: "A<<9" },
    { formula: "B" },
    { formula: "1e300" },
    { interval: 0 },
    { bytes: true },
    { min: NaN },
  ]) {
    assert.ok(validateSensor({ ...sensor, ...patch }), JSON.stringify(patch));
  }
});
test("new, missing, disconnected or stale sensor readings never become invented zeroes", () => {
  const config = { ...defaultConfig(), sensors: [sensor] };
  const telemetry = {
    connected: true,
    timestamp: 100,
    customRevision: 3,
    custom: { oil: { value: 92, error: null, timestamp: 100 } },
    values: { speed: 50 },
  };
  assert.equal(sample(config, "custom:oil", telemetry, 3, 102).value, 92);
  assert.equal(sample(config, "custom:oil", telemetry, 4, 102).value, null);
  assert.equal(sample(config, "custom:oil", telemetry, 3, 120).value, null);
  assert.equal(
    sample(config, "builtin:speed", { ...telemetry, connected: false }, 3, 102)
      .value,
    null,
  );
  assert.equal(sample(config, "derived:range", telemetry, 3, 102).value, null);
  assert.equal(reading(config, "custom:oil").unit, "°C");
});
