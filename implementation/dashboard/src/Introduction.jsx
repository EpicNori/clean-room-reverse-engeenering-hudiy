import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  GUIDE_STEPS,
  guidePathLabel,
  guidePlacement,
  guideRect,
  guideRoute,
  unionRect,
} from "./onboarding.mjs";
import "./introduction.css";

const area = (r) => (r ? r.width * r.height : 0);
// Part of an element that is not cut off by scrolling ancestors or the viewport.
function clippedRect(element) {
  const r = element.getBoundingClientRect();
  let left = Math.max(r.left, 0),
    top = Math.max(r.top, 0),
    right = Math.min(r.right, innerWidth),
    bottom = Math.min(r.bottom, innerHeight);
  for (let p = element.parentElement; p && p !== document.body; p = p.parentElement) {
    const style = getComputedStyle(p);
    if (style.overflowX === "visible" && style.overflowY === "visible") continue;
    const c = p.getBoundingClientRect();
    left = Math.max(left, c.left);
    top = Math.max(top, c.top);
    right = Math.min(right, c.right);
    bottom = Math.min(bottom, c.bottom);
  }
  return { left, top, right, bottom, width: right - left, height: bottom - top };
}
const visibleMatches = (selector) =>
  [...document.querySelectorAll(selector)].filter(
    (element) =>
      !element.closest(".introduction-layer") &&
      element.getClientRects().length > 0,
  );
// Boxes around each target selector that is mostly visible, in preference order.
// The preferred target is scrolled into view; the app may reset its list to the top
// right after a screen change, so retry a few times but never endlessly, and never
// once the viewer scrolls or edits there themselves. Any target that stays cut off by
// its scroll area is skipped.
function targetBoxes(step, state) {
  const boxes = [];
  for (const selector of step.target || []) {
    const found = visibleMatches(selector);
    if (!found.length) continue;
    const measure = () => [
      unionRect(found.map((e) => e.getBoundingClientRect())),
      unionRect(found.map(clippedRect)),
    ];
    let [full, box] = measure();
    const tries = state.scrolled.get(found[0]) || 0;
    if (!boxes.length && !state.frozen && tries < 3 && area(box) < area(full) * 0.9) {
      state.scrolled.set(found[0], tries + 1);
      found[0].scrollIntoView({
        block: "nearest",
        inline: "nearest",
        behavior: "instant",
      });
      [full, box] = measure();
    }
    if (box && area(box) >= area(full) * 0.6) boxes.push(box);
  }
  return boxes;
}
// The part of the screen the viewer may use during this step, e.g. its settings.
function handsOnArea(step) {
  for (const selector of step.interactive || []) {
    const found = visibleMatches(selector);
    if (found.length) return { elements: found, box: unionRect(found.map(clippedRect)) };
  }
  return { elements: [], box: null };
}
// An app dialog such as a pairing confirmation; the guide steps aside for it and
// leaves only the dialog (with its backdrop) usable.
function appModal() {
  const modal = [...document.querySelectorAll('[aria-modal="true"]')].find(
    (element) => !element.closest(".introduction-layer"),
  );
  return modal ? (modal.closest(".customize-backdrop") || modal).getBoundingClientRect() : null;
}
const appModalOpen = () => Boolean(appModal());

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const frames = () =>
  new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)),
  );
// Showing the way is unhurried so each tap can be followed: the finger glides to a
// button, presses it, and the next screen opens out of it.
const GLIDE = 850,
  PRESS = 550,
  OPEN = 400,
  SETTLE = 450,
  STILL = 1300;
const isTaskbarTap = (tap) => tap.target[0].startsWith("[data-tour=taskbar]");
// The visible element for a tap, waiting briefly while a screen renders.
async function findTap(tap, alive) {
  for (let tries = 0; tries < 16 && alive(); tries++) {
    const element = tap.target
      .map((selector) => document.querySelector(selector))
      .find((found) => found && found.getClientRects().length > 0);
    if (element) {
      element.scrollIntoView({
        block: "nearest",
        inline: "nearest",
        behavior: "instant",
      });
      return element;
    }
    await wait(50);
  }
  return null;
}
const FOCUSABLE =
  'button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex]:not([tabindex="-1"])';

export function Introduction({
  guide,
  onNavigate,
  onDone,
  onRelease,
  native,
  screen,
  category,
}) {
  const index = guide.progress.step,
    step = GUIDE_STEPS[index],
    last = index === GUIDE_STEPS.length - 1,
    dialog = useRef(null),
    next = useRef(null),
    keys = useRef({}),
    shownAt = useRef(0),
    shownIndex = useRef(null),
    walkRun = useRef(0),
    here = useRef({}),
    handsOnElements = useRef([]),
    touched = useRef(false);
  here.current = { route: screen, category };
  const [skip, setSkip] = useState(false),
    [rect, setRect] = useState(null),
    [hole, setHole] = useState(null),
    [place, setPlace] = useState(null),
    // While showing the taps that lead to this step: { taps, at, pressed }.
    [walk, setWalk] = useState(null),
    [pointer, setPointer] = useState(null),
    [opening, setOpening] = useState(null),
    // The card shrinks to a bar while the viewer sets things up.
    [mini, setMini] = useState(false),
    // The open app dialog's box while the guide steps aside, otherwise null.
    [paused, setPaused] = useState(null),
    [offRoute, setOffRoute] = useState(false);
  const handsOn = Boolean(step.interactive) && !walk && !skip && !offRoute;
  const stopWalk = () => {
    walkRun.current++;
    setWalk(null);
    setPointer(null);
    setOpening(null);
  };
  // Ends the walk-through and shows the step itself, e.g. when it is skipped.
  const endWalk = () => {
    stopWalk();
    onNavigate(step);
    shownAt.current = performance.now();
  };
  // Highlights each tap in turn and navigates as if it were pressed. The guide
  // never presses the real buttons, so no device action runs.
  function showWay(taps) {
    const run = ++walkRun.current,
      alive = () => run === walkRun.current,
      still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    (async () => {
      let route = here.current.route;
      for (let at = 0; at < taps.length && alive(); at++) {
        // Never navigate away under an open app dialog, e.g. a pairing code.
        while (appModalOpen() && alive()) await wait(200);
        if (!alive()) return;
        const tap = taps[at];
        setWalk({ taps, at, pressed: false });
        if (native && isTaskbarTap(tap)) {
          // The native taskbar is a separate view; the card says where to tap.
          await wait(STILL);
          if (!alive()) return;
          onNavigate(tap.to);
          route = tap.to.route;
          continue;
        }
        const element = await findTap(tap, alive);
        if (!alive()) return;
        const box = element?.getBoundingClientRect();
        if (box && !still) {
          // The finger starts at the guide card, then glides to each button.
          if (!at) {
            const card = dialog.current?.getBoundingClientRect();
            if (card)
              setPointer({
                x: card.left + card.width / 2,
                y: card.top + card.height / 2,
              });
            await frames();
            if (!alive()) return;
          }
          setPointer({ x: box.left + box.width / 2, y: box.top + box.height / 2 });
          await wait(GLIDE);
          if (!alive()) return;
          setWalk({ taps, at, pressed: true });
          await wait(PRESS);
          if (!alive()) return;
          if (tap.to.route !== route) {
            // The next screen grows out of the tapped button.
            setOpening({
              left: box.left,
              top: box.top,
              width: box.width,
              height: box.height,
            });
            await frames();
            if (!alive()) return;
            setOpening({ left: 0, top: 0, width: innerWidth, height: innerHeight, full: true });
            await wait(OPEN);
          }
        } else await wait(still ? STILL : 250);
        if (!alive()) return;
        onNavigate(tap.to);
        route = tap.to.route;
        await wait(still ? 150 : SETTLE);
        if (!alive()) return;
        setOpening((open) => open && { ...open, fading: true });
        setTimeout(() => alive() && setOpening((open) => (open?.fading ? null : open)), 260);
      }
      if (alive()) endWalk();
    })();
  }
  useEffect(() => {
    const from = shownIndex.current;
    shownIndex.current = index;
    setSkip(false);
    setMini(false);
    touched.current = false;
    shownAt.current = performance.now();
    // Moving forward walks through the real taps from wherever the viewer is now,
    // e.g. the Bluetooth screen they opened themselves; Back or resuming jumps.
    let taps = [];
    if (from === index - 1) {
      const previous = GUIDE_STEPS[from],
        now = here.current;
      const origin =
        now.route === previous.route
          ? {
              ...previous,
              category: ["apps", "settings"].includes(now.route)
                ? now.category
                : previous.category,
            }
          : {
              route: now.route,
              path: [...(previous.path || []), { to: { route: now.route } }],
            };
      taps = guideRoute(origin, step);
    }
    if (taps.length) showWay(taps);
    else endWalk();
    return () => {
      walkRun.current++;
    };
  }, [step.id]);
  // App dialogs, e.g. a pairing code to confirm, keep focus and input until closed.
  useEffect(() => {
    const check = () => {
      const box = appModal();
      setPaused((old) =>
        JSON.stringify(old) === JSON.stringify(box) ? old : box && {
          left: box.left,
          top: box.top,
          width: box.width,
          height: box.height,
        },
      );
    };
    check();
    const timer = setInterval(check, 300);
    return () => clearInterval(timer);
  }, []);
  // Leaving the step's screen through a link inside the usable area blocks it again
  // until the viewer returns or moves on.
  useEffect(() => {
    const away =
      !walk &&
      Boolean(step.interactive) &&
      screen !== step.route &&
      !(step.follow || []).includes(screen);
    setOffRoute(away);
    if (away) setMini(false);
  }, [screen, step.id, Boolean(walk)]);
  // The app screen stays inert except while the viewer may use part of it or an app
  // dialog is open; then everything outside the usable part is made inert instead.
  const released = Boolean(paused) || (handsOn && Boolean(hole));
  useEffect(() => {
    onRelease?.(released);
    return () => onRelease?.(false);
  }, [released]);
  useEffect(() => {
    if (!released || paused) return;
    const keep = handsOnElements.current,
      marked = [];
    for (const element of keep) {
      for (let node = element; node?.parentElement; node = node.parentElement) {
        if (node.matches("section.screen")) break;
        for (const sibling of node.parentElement.children)
          if (
            !sibling.inert &&
            !keep.some((k) => sibling.contains(k) || k.contains(sibling))
          ) {
            sibling.inert = true;
            marked.push(sibling);
          }
      }
    }
    return () => marked.forEach((element) => (element.inert = false));
  }, [released, paused, hole, screen]);
  // Touching the settings during a hands-on step tucks the card away.
  useEffect(() => {
    if (!handsOn) return;
    const down = (e) => {
      if (handsOnElements.current.some((element) => element.contains(e.target))) {
        touched.current = true;
        setMini(true);
      }
    };
    const focus = (e) => {
      if (handsOnElements.current.some((element) => element.contains(e.target)))
        touched.current = true;
    };
    document.addEventListener("pointerdown", down, true);
    document.addEventListener("focusin", focus, true);
    document.addEventListener("wheel", focus, true);
    return () => {
      document.removeEventListener("pointerdown", down, true);
      document.removeEventListener("focusin", focus, true);
      document.removeEventListener("wheel", focus, true);
    };
  }, [handsOn, step.id]);
  const active = walk ? { target: walk.taps[walk.at].target } : step;
  useLayoutEffect(() => {
    let frame,
      ticks = 0;
    const state = { scrolled: new Map(), frozen: false };
    const measure = () => {
      const card = dialog.current;
      if (!card) return;
      state.frozen = touched.current;
      const size = { width: card.offsetWidth, height: card.offsetHeight };
      const usable = handsOn ? handsOnArea(step) : { elements: [], box: null };
      handsOnElements.current = usable.elements;
      const usableSpot = guideRect(usable.box, innerWidth, innerHeight);
      const options = (skip ? [] : targetBoxes(active, state)).map((box) => {
        const spot = guideRect(box, innerWidth, innerHeight);
        return [spot, spot && guidePlacement(spot, size, innerWidth, innerHeight)];
      }).filter(([spot]) => spot);
      // Keep the whole usable area free when the card fits beside it; otherwise use
      // the first target the card fits beside without covering it.
      const free =
        usableSpot && guidePlacement(usableSpot, size, innerWidth, innerHeight);
      const [spot, nextPlace] =
        (free && !free.side.endsWith("overlap") && [options[0]?.[0] || null, free]) ||
        options.find(([, p]) => !p.side.endsWith("overlap")) ||
        options[0] || [null, guidePlacement(usableSpot, size, innerWidth, innerHeight)];
      const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
      setRect((old) => (same(old, spot) ? old : spot));
      setHole((old) => (same(old, usableSpot) ? old : usableSpot));
      setPlace((old) => {
        // While showing the way, the card stays put as long as it leaves the
        // current button free, instead of sliding across the screen at every tap.
        const keep =
          walk &&
          old &&
          spot &&
          old.left + size.width <= innerWidth &&
          old.top + size.height <= innerHeight &&
          (old.left + size.width + 8 <= spot.left ||
            spot.left + spot.width + 8 <= old.left ||
            old.top + size.height + 8 <= spot.top ||
            spot.top + spot.height + 8 <= old.top);
        if (keep) return old;
        return same(old, nextPlace) ? old : nextPlace;
      });
    };
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    // Measure after the step's screen has rendered, not the previous one.
    schedule();
    // Screens load lazily and settle after navigation: re-measure quickly for the
    // first seconds, then only occasionally in case their content changes.
    const timer = setInterval(() => (++ticks < 10 || ticks % 4 === 0) && schedule(), 400);
    const resize = new ResizeObserver(schedule);
    dialog.current && resize.observe(dialog.current);
    const viewport = () => {
      // A new window size may need the target scrolled into view again.
      state.scrolled.clear();
      schedule();
    };
    addEventListener("resize", viewport);
    addEventListener("scroll", schedule, true);
    return () => {
      cancelAnimationFrame(frame);
      clearInterval(timer);
      resize.disconnect();
      removeEventListener("resize", viewport);
      removeEventListener("scroll", schedule, true);
    };
  }, [step.id, skip, walk ? walk.at : -1, handsOn, screen, category]);
  async function finish(outcome) {
    if (await guide.finish(outcome)) onDone();
  }
  const forward = () => {
    // Ignore a second tap that lands on the same button right after a change.
    if (performance.now() - shownAt.current < 350) return;
    if (walk) return endWalk();
    last ? finish("completed") : guide.move(index + 1);
  };
  const backward = async () => {
    const walking = Boolean(walk);
    stopWalk();
    if (!(await guide.move(index - 1)) && walking) onNavigate(step);
  };
  const askSkip = () => {
    if (walk) endWalk();
    setMini(false);
    setSkip(true);
  };
  const showAgain = () => {
    setMini(false);
    showWay(step.path);
  };
  keys.current = {
    forward: () => !skip && !guide.busy && forward(),
    back: () => !skip && !guide.busy && index > 0 && backward(),
    toggleSkip: () => !guide.busy && (skip ? setSkip(false) : askSkip()),
  };
  useEffect(() => {
    const previous = document.activeElement;
    const key = (e) => {
      if (appModalOpen()) return;
      const inside = handsOnElements.current.some((element) =>
        element.contains(document.activeElement),
      );
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        keys.current.toggleSkip();
        return;
      }
      // Arrow keys keep working in sliders and lists the viewer is setting up.
      if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && !inside) {
        e.preventDefault();
        e.stopPropagation();
        if (!e.repeat) keys.current[e.key === "ArrowRight" ? "forward" : "back"]();
        return;
      }
      if (e.key !== "Tab") return;
      // Tab moves between the usable settings and the guide's own buttons.
      const items = [
        ...handsOnElements.current.flatMap((element) => [
          ...element.querySelectorAll(FOCUSABLE),
        ]),
        ...dialog.current.querySelectorAll("button:not(:disabled)"),
      ].filter((element) => element.getClientRects().length > 0);
      const i = items.indexOf(document.activeElement);
      e.preventDefault();
      items.at(e.shiftKey ? (i <= 0 ? -1 : i - 1) : (i + 1) % items.length)?.focus();
    };
    document.addEventListener("keydown", key, true);
    return () => {
      document.removeEventListener("keydown", key, true);
      previous?.isConnected && previous.focus();
    };
  }, []);
  const focusedFor = useRef("");
  useEffect(() => {
    if (paused) return;
    const view = `${step.id}:${skip}:${mini}`;
    const frame = requestAnimationFrame(() => {
      const current = document.activeElement;
      // Keep focus where the viewer put it: a guide button or a setting.
      const chosen =
        focusedFor.current === view &&
        current !== next.current &&
        !current.disabled &&
        (dialog.current?.contains(current) ||
          handsOnElements.current.some((element) => element.contains(current)));
      focusedFor.current = view;
      if (chosen) return;
      if (skip) dialog.current?.querySelector("[data-keep-guide]")?.focus();
      else next.current?.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [skip, step.id, guide.busy, Boolean(walk), Boolean(paused), mini]);
  const path = walk ? walk.taps : step.path || [];
  const nextLabel = guide.busy
    ? "Saving…"
    : walk
      ? "Skip animation"
      : last
        ? "Finish"
        : index === 0
          ? "Start tour"
          : "Next";
  // Outside the usable area the screen stays blocked; inside it, taps reach the app.
  const gap = paused || hole;
  const shields = gap
    ? [
        { left: 0, top: 0, width: "100%", height: gap.top },
        { left: 0, top: gap.top + gap.height, width: "100%", bottom: 0 },
        { left: 0, top: gap.top, width: gap.left, height: gap.height },
        { left: gap.left + gap.width, top: gap.top, right: 0, height: gap.height },
      ]
    : [{ inset: 0 }];
  const dim = hole || rect;
  return (
    <div
      className={`introduction-layer ${paused ? "is-paused" : ""}`}
      data-no-drag-scroll="true"
    >
      {shields.map((style, i) => (
        <div
          key={i}
          className={`introduction-shield ${dim || paused ? "" : "is-dimmed"}`}
          aria-hidden="true"
          style={style}
        />
      ))}
      {dim && (
        <div
          className={`introduction-spotlight ${hole ? "is-usable" : "has-ring"} ${walk ? "is-walking" : ""}`}
          aria-hidden="true"
          style={dim}
        />
      )}
      {hole && rect && (
        <div className="introduction-ring" aria-hidden="true" style={rect} />
      )}
      {opening && (
        <div
          className={`introduction-opening ${opening.full ? "is-open" : ""} ${opening.fading ? "is-fading" : ""}`}
          aria-hidden="true"
          style={opening}
        />
      )}
      {walk && pointer && (
        <div
          className={`introduction-finger ${walk.pressed ? "is-pressed" : ""}`}
          aria-hidden="true"
          style={{ left: pointer.x, top: pointer.y }}
        />
      )}
      <section
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="introduction-title"
        aria-describedby="introduction-description"
        className={`introduction-card ${mini ? "is-mini" : ""}`}
        data-side={mini ? "mini" : place?.side || "center"}
        style={
          mini
            ? undefined
            : place
              ? { left: place.left, top: place.top }
              : { left: 12, top: 12, visibility: "hidden" }
        }
      >
        {mini ? (
          <>
            <span className="introduction-count">
              {index + 1}/{GUIDE_STEPS.length}
            </span>
            <h1 id="introduction-title">{step.title}</h1>
            <p id="introduction-description" className="introduction-sr">
              {step.body}
            </p>
            <button className="introduction-secondary" onClick={() => setMini(false)}>
              Show tip
            </button>
            <button
              ref={next}
              className="introduction-primary"
              disabled={guide.busy}
              onClick={forward}
            >
              {nextLabel}
            </button>
          </>
        ) : (
          <>
            <header className="introduction-top">
              <span className="introduction-count">
                Step {index + 1} of {GUIDE_STEPS.length}
              </span>
              {!skip && (
                <button
                  className="introduction-skip"
                  disabled={guide.busy}
                  onClick={askSkip}
                >
                  Skip
                  <span className="material-symbols-rounded" aria-hidden="true">
                    close
                  </span>
                </button>
              )}
            </header>
            <div
              className="introduction-progress"
              role="progressbar"
              aria-label="Introduction progress"
              aria-valuemin={1}
              aria-valuemax={GUIDE_STEPS.length}
              aria-valuenow={index + 1}
            >
              <span style={{ width: `${((index + 1) / GUIDE_STEPS.length) * 100}%` }} />
            </div>
            <h1 id="introduction-title">
              {skip ? "Skip the introduction?" : step.title}
            </h1>
            {!skip && path.length > 0 && (
              <p className="introduction-path">
                <span className="material-symbols-rounded" aria-hidden="true">
                  touch_app
                </span>
                <span className="introduction-sr">
                  Way here: {guidePathLabel({ path })}
                </span>
                <span aria-hidden="true">
                  {path.map((tap, i) => (
                    <React.Fragment key={i}>
                      {i > 0 && <span className="introduction-path-arrow"> › </span>}
                      <span
                        className={
                          walk && i === walk.at
                            ? "is-current"
                            : walk && i > walk.at
                              ? "is-later"
                              : ""
                        }
                      >
                        {tap.label}
                      </span>
                    </React.Fragment>
                  ))}
                </span>
                {!walk && step.path && (
                  <button
                    className="introduction-again"
                    aria-label="Show the way again"
                    onClick={showAgain}
                  >
                    <span className="material-symbols-rounded" aria-hidden="true">
                      replay
                    </span>
                    <span className="introduction-again-label">Show again</span>
                  </button>
                )}
              </p>
            )}
            <p id="introduction-description" aria-live="polite">
              {skip
                ? "You can replay it any time in Settings → System → Application."
                : walk
                  ? native && isTaskbarTap(walk.taps[walk.at])
                    ? `Tap ${walk.taps[walk.at].label} in the taskbar below.`
                    : `Tap ${walk.taps[walk.at].label}.`
                  : step.body}
            </p>
            {handsOn && hole && (
              <p className="introduction-hint introduction-try">
                <span className="material-symbols-rounded" aria-hidden="true">
                  edit
                </span>
                You can set this up right now.
              </p>
            )}
            {offRoute && !skip && (
              <p className="introduction-hint introduction-try introduction-away">
                <span className="material-symbols-rounded" aria-hidden="true">
                  info
                </span>
                This screen is not part of this step.
                <button className="introduction-again" onClick={() => onNavigate(step)}>
                  Return
                </button>
              </p>
            )}
            {!skip && native && step.id === "taskbar" && (
              <p className="introduction-hint">
                The taskbar sits just below this screen and is paused during the
                tour.
              </p>
            )}
            {guide.error && (
              <p role="alert" className="introduction-error">
                {guide.error}
              </p>
            )}
            <div className="introduction-actions">
              {skip ? (
                <>
                  <button
                    className="introduction-secondary"
                    disabled={guide.busy}
                    onClick={() => finish("skipped")}
                  >
                    Skip tour
                  </button>
                  <button
                    data-keep-guide
                    className="introduction-primary"
                    disabled={guide.busy}
                    onClick={() => setSkip(false)}
                  >
                    Keep going
                  </button>
                </>
              ) : (
                <>
                  <button
                    className="introduction-secondary"
                    disabled={guide.busy || index === 0}
                    onClick={backward}
                  >
                    Back
                  </button>
                  <button
                    ref={next}
                    className="introduction-primary"
                    disabled={guide.busy}
                    onClick={forward}
                  >
                    {nextLabel}
                  </button>
                </>
              )}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
