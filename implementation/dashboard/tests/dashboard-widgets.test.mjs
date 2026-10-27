import test from "node:test";
import assert from "node:assert/strict";
import {
  defaultDashboard,
  validateDashboard,
  addWidget,
  placeWidget,
  PRESETS,
  dashboardPack,
  parseDashboardPack,
  sensorReading,
  readDashboard,
} from "../src/dashboardWidgets.mjs";

test("original appearance is default; every bundled layout is valid and independently editable", () => {
  assert.equal(defaultDashboard().enabled, false);
  assert.equal(defaultDashboard().appearance.surface, "classic");
  for (const preset of PRESETS)
    assert.deepEqual(validateDashboard(preset.config), preset.config);
  const copy = validateDashboard(PRESETS[2].config);
  copy.appearance.blur = 0;
  assert.equal(PRESETS[2].config.appearance.blur, 12);
});
test("dragging swaps equal cards, refuses overlaps and preserves original configuration", () => {
  const original = defaultDashboard(),
    swapped = placeWidget(original.widgets, "clock", 4, 0);
  assert.equal(swapped.find((w) => w.id === "clock").x, 4);
  assert.equal(swapped.find((w) => w.id === "phone").x, 0);
  assert.equal(original.widgets[0].x, 0);
  assert.equal(placeWidget(original.widgets, "clock", 2, 0), null);
  assert.equal(placeWidget(original.widgets, "clock", 6, 0), null);
  assert.equal(placeWidget(original.widgets, "clock", 0, 0, { w: 6 }), null);
});
test("adding finds free grid cells and refuses exhaustion without overwriting another widget", () => {
  let config = defaultDashboard();
  config.enabled = true;
  const next = addWidget(config, "sensor");
  assert.equal(next.widgets.length, 7);
  assert.equal(next.widgets.at(-1).y, 3);
  validateDashboard(next);
  assert.equal(addWidget(config, "arbitrary"), null);
  while (config.widgets.length < 16) {
    const next = addWidget(config, "clock");
    if (!next) break;
    config = next;
  }
  assert.equal(config.widgets.length, 16);
  assert.equal(addWidget(config, "clock"), null);
});
test("shared packs round-trip only known configuration and reject active content or unbounded input", () => {
  const config = PRESETS[2].config;
  assert.deepEqual(
    parseDashboardPack(JSON.stringify(dashboardPack(config))).config,
    config,
  );
  for (const extra of [
    { script: "alert(1)" },
    { url: "https://evil.example/layout" },
    { html: "<script/>" },
  ])
    assert.throws(() =>
      parseDashboardPack(
        JSON.stringify({ ...dashboardPack(config), ...extra }),
      ),
    );
  assert.throws(() => parseDashboardPack(" ".repeat(16385)));
  assert.throws(() =>
    parseDashboardPack(
      JSON.stringify({
        ...dashboardPack(config),
        config: { ...config, readings: { speed: 100 } },
      }),
    ),
  );
});
test("validation rejects duplicate/unknown widgets, unsafe colors, bad bounds and control characters", () => {
  for (const patch of [
    { x: true },
    { x: 6 },
    { w: 7 },
    { type: "script" },
    { source: "url" },
    { title: "bad\nlabel" },
  ]) {
    const config = defaultDashboard();
    Object.assign(config.widgets[0], patch);
    assert.throws(() => validateDashboard(config));
  }
  const config = defaultDashboard();
  config.appearance.accent = "url(javascript:alert(1))";
  assert.throws(() => validateDashboard(config));
});
test("disconnected, stale and missing sensors stay unavailable rather than becoming zero", () => {
  const now = 1_000_000;
  assert.equal(
    sensorReading({ connected: false, values: { speed: 100 } }, "speed", now)
      .value,
    null,
  );
  assert.equal(
    sensorReading(
      { connected: true, timestamp: 900, values: { speed: 100 } },
      "speed",
      now,
    ).value,
    null,
  );
  assert.equal(
    sensorReading(
      { connected: true, timestamp: 1000, values: { speed: NaN } },
      "speed",
      now,
    ).value,
    null,
  );
  assert.equal(
    sensorReading(
      { connected: true, timestamp: 1000, values: { speed: 0 } },
      "speed",
      now,
    ).value,
    0,
  );
  assert.equal(
    sensorReading(
      {
        connected: true,
        timestamp: 1000,
        mode: "simulator",
        values: { speed: 12 },
      },
      "speed",
      now,
    ).reason,
    "Simulator",
  );
});
test("saved browser dashboard survives hydration without changing original taskbar/layout keys", () => {
  const previous = globalThis.localStorage;
  try {
    globalThis.localStorage = {
      getItem: (key) =>
        key === "coscaros.dashboard.v1"
          ? JSON.stringify(PRESETS[2].config)
          : null,
    };
    assert.deepEqual(readDashboard(), PRESETS[2].config);
    globalThis.localStorage = { getItem: () => "{broken" };
    assert.deepEqual(readDashboard(), defaultDashboard());
  } finally {
    if (previous === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = previous;
  }
});
