import test from "node:test";
import assert from "node:assert/strict";
import {
  GUIDE_KEY,
  GUIDE_STEPS,
  guideState,
  readGuide,
  guideRect,
} from "../src/onboarding.mjs";

test("guide covers the user journey with unique bounded sections", () => {
  assert.equal(GUIDE_STEPS.length, 19);
  assert.equal(new Set(GUIDE_STEPS.map((s) => s.id)).size, 19);
  for (const id of [
    "dashboard",
    "taskbar",
    "studio",
    "extensions",
    "pair",
    "android",
    "music",
    "audio",
    "microphone",
    "obd",
    "my-obd",
    "logs",
    "updates",
    "finish",
  ])
    assert.ok(GUIDE_STEPS.some((s) => s.id === id));
  for (const step of GUIDE_STEPS) {
    assert.ok(step.title && step.body && step.route);
    assert.equal(
      typeof step.target === "undefined" || typeof step.target === "string",
      true,
    );
  }
});
test("saved completion and skip persist but corrupt or old progress restarts", () => {
  for (const outcome of ["completed", "skipped", "pending"])
    assert.deepEqual(guideState({ version: 1, outcome, step: 18 }), {
      version: 1,
      outcome,
      step: 18,
    });
  for (const value of [
    null,
    {},
    { version: 0, outcome: "completed", step: 0 },
    { version: 1, outcome: "pending", step: true },
    { version: 1, outcome: "pending", step: 19 },
  ])
    assert.deepEqual(guideState(value), {
      version: 1,
      outcome: "pending",
      step: 0,
    });
  assert.deepEqual(
    readGuide({
      getItem() {
        throw Error();
      },
    }),
    guideState(null),
  );
  assert.deepEqual(
    readGuide({
      getItem(key) {
        assert.equal(key, GUIDE_KEY);
        return "{broken";
      },
    }),
    guideState(null),
  );
});
test("spotlight clips visible targets safely and tolerates missing content", () => {
  assert.equal(guideRect(null, 390, 844), null);
  assert.equal(
    guideRect(
      { left: 0, top: 900, right: 50, bottom: 950, width: 50, height: 50 },
      390,
      844,
    ),
    null,
  );
  assert.deepEqual(
    guideRect(
      { left: -10, top: 20, right: 500, bottom: 400, width: 510, height: 380 },
      390,
      844,
    ),
    { left: 8, top: 14, width: 374, height: 392 },
  );
});
