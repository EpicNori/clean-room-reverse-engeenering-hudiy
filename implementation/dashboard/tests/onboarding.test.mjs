import test from "node:test";
import assert from "node:assert/strict";
import {
  GUIDE_KEY,
  GUIDE_STEPS,
  guideState,
  readGuide,
  guideRect,
  guidePlacement,
  unionRect,
} from "../src/onboarding.mjs";

const overlaps = (a, b) =>
  a.left < b.left + b.width &&
  b.left < a.left + a.width &&
  a.top < b.top + b.height &&
  b.top < a.top + a.height;

test("guide card sits beside the spotlight on the side with room", () => {
  const card = { width: 310, height: 190 };
  const cases = [
    // taskbar along the bottom of an 800×480 display → card above
    [{ left: 8, top: 418, width: 784, height: 54 }, "top"],
    // left dashboard column → card to its right
    [{ left: 8, top: 8, width: 262, height: 410 }, "right"],
    // header across the top → card below
    [{ left: 8, top: 8, width: 784, height: 84 }, "bottom"],
    // right-hand panel → card to its left
    [{ left: 460, top: 8, width: 332, height: 410 }, "left"],
  ];
  for (const [spot, side] of cases) {
    const place = guidePlacement(spot, card, 800, 480);
    assert.equal(place.side, side);
    assert.equal(overlaps({ ...place, ...card }, spot), false);
    assert.ok(place.left >= 12 && place.left + card.width <= 788);
    assert.ok(place.top >= 12 && place.top + card.height <= 468);
  }
});
test("guide card stays on screen when nothing fits or nothing is highlighted", () => {
  const card = { width: 310, height: 190 };
  const centered = guidePlacement(null, card, 800, 480);
  assert.deepEqual(centered, { side: "center", left: 245, top: 145 });
  const full = guidePlacement(
    { left: 8, top: 8, width: 784, height: 464 },
    card,
    800,
    480,
  );
  assert.match(full.side, /overlap$/);
  assert.ok(full.left >= 12 && full.left + card.width <= 788);
  assert.ok(full.top >= 12 && full.top + card.height <= 468);
  // A card larger than a tiny viewport is pinned to the margin, not pushed off.
  const tiny = guidePlacement(null, { width: 400, height: 300 }, 320, 240);
  assert.deepEqual([tiny.left, tiny.top], [12, 12]);
});
test("highlight joins several elements and ignores hidden ones", () => {
  assert.equal(unionRect([]), null);
  assert.deepEqual(
    unionRect([
      { left: 10, top: 20, right: 110, bottom: 60, width: 100, height: 40 },
      { left: 50, top: 70, right: 200, bottom: 90, width: 150, height: 20 },
      { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 },
    ]),
    { left: 10, top: 20, right: 200, bottom: 90, width: 190, height: 70 },
  );
});

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
    assert.ok(
      typeof step.target === "undefined" ||
        (Array.isArray(step.target) &&
          step.target.length > 0 &&
          step.target.every((s) => typeof s === "string" && s)),
    );
    // Short steps keep the card small enough to sit beside its target.
    assert.ok(step.title.length <= 32, step.id);
    assert.ok(step.body.length <= 110, step.id);
  }
});
test("pairing step stays on the settings menu instead of a device screen", () => {
  const pair = GUIDE_STEPS.find((s) => s.id === "pair");
  assert.equal(pair.route, "settings");
  assert.equal(pair.category, "Bluetooth");
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
