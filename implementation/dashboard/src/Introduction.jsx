import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  GUIDE_STEPS,
  guidePlacement,
  guideRect,
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
// Boxes around each target selector that is mostly visible, in preference order.
// The preferred target is scrolled into view; the app may reset its list to the top
// right after a screen change, so retry a few times but never endlessly. Any target
// that stays cut off by its scroll area is skipped.
function targetBoxes(step, state) {
  const boxes = [];
  for (const selector of step.target || []) {
    const found = [...document.querySelectorAll(selector)].filter(
      (element) =>
        !element.closest(".introduction-layer") &&
        element.getClientRects().length > 0,
    );
    if (!found.length) continue;
    const measure = () => [
      unionRect(found.map((e) => e.getBoundingClientRect())),
      unionRect(found.map(clippedRect)),
    ];
    let [full, box] = measure();
    const tries = state.scrolled.get(found[0]) || 0;
    if (!boxes.length && tries < 3 && area(box) < area(full) * 0.9) {
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

export function Introduction({ guide, onNavigate, onDone, native }) {
  const index = guide.progress.step,
    step = GUIDE_STEPS[index],
    last = index === GUIDE_STEPS.length - 1,
    dialog = useRef(null),
    next = useRef(null),
    keys = useRef({}),
    shownAt = useRef(0);
  const [skip, setSkip] = useState(false),
    [rect, setRect] = useState(null),
    [place, setPlace] = useState(null);
  useEffect(() => {
    onNavigate(step);
    setSkip(false);
    shownAt.current = performance.now();
  }, [step.id]);
  useLayoutEffect(() => {
    let frame,
      ticks = 0;
    const state = { scrolled: new Map() };
    const measure = () => {
      const card = dialog.current;
      if (!card) return;
      const size = { width: card.offsetWidth, height: card.offsetHeight };
      const options = (skip ? [] : targetBoxes(step, state)).map((box) => {
        const spot = guideRect(box, innerWidth, innerHeight);
        return [spot, spot && guidePlacement(spot, size, innerWidth, innerHeight)];
      }).filter(([spot]) => spot);
      // Use the first target the card fits beside without covering it.
      const [spot, nextPlace] = options.find(
        ([, p]) => !p.side.endsWith("overlap"),
      ) ||
        options[0] || [null, guidePlacement(null, size, innerWidth, innerHeight)];
      setRect((old) => (JSON.stringify(old) === JSON.stringify(spot) ? old : spot));
      setPlace((old) =>
        JSON.stringify(old) === JSON.stringify(nextPlace) ? old : nextPlace,
      );
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
  }, [step.id, skip]);
  async function finish(outcome) {
    if (await guide.finish(outcome)) onDone();
  }
  const forward = () => {
    if (performance.now() - shownAt.current < 350) return;
    last ? finish("completed") : guide.move(index + 1);
  };
  keys.current = {
    forward: () => !skip && !guide.busy && forward(),
    back: () => !skip && !guide.busy && index > 0 && guide.move(index - 1),
    toggleSkip: () => !guide.busy && setSkip((value) => !value),
  };
  useEffect(() => {
    const previous = document.activeElement;
    const key = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        keys.current.toggleSkip();
        return;
      }
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        e.stopPropagation();
        if (!e.repeat) keys.current[e.key === "ArrowRight" ? "forward" : "back"]();
        return;
      }
      if (e.key !== "Tab") return;
      const buttons = [
        ...dialog.current.querySelectorAll("button:not(:disabled)"),
      ].filter((element) => element.getClientRects().length > 0);
      const i = buttons.indexOf(document.activeElement);
      if (e.shiftKey && i <= 0) {
        e.preventDefault();
        buttons.at(-1)?.focus();
      } else if (!e.shiftKey && (i === buttons.length - 1 || i < 0)) {
        e.preventDefault();
        buttons[0]?.focus();
      }
    };
    document.addEventListener("keydown", key, true);
    return () => {
      document.removeEventListener("keydown", key, true);
      previous?.isConnected && previous.focus();
    };
  }, []);
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      if (skip) dialog.current?.querySelector("[data-keep-guide]")?.focus();
      else next.current?.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [skip, step.id, guide.busy]);
  return (
    <div className="introduction-layer" data-no-drag-scroll="true">
      <div
        className={`introduction-shield ${rect ? "" : "is-dimmed"}`}
        aria-hidden="true"
      />
      {rect && (
        <div
          className="introduction-spotlight"
          aria-hidden="true"
          style={rect}
        />
      )}
      <section
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="introduction-title"
        aria-describedby="introduction-description"
        className="introduction-card"
        data-side={place?.side || "center"}
        style={
          place
            ? { left: place.left, top: place.top }
            : { left: 12, top: 12, visibility: "hidden" }
        }
      >
        <header className="introduction-top">
          <span className="introduction-count">
            Step {index + 1} of {GUIDE_STEPS.length}
          </span>
          {!skip && (
            <button
              className="introduction-skip"
              disabled={guide.busy}
              onClick={() => setSkip(true)}
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
        <p id="introduction-description">
          {skip
            ? "You can replay it any time in Settings → System → Application."
            : step.body}
        </p>
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
                onClick={() => guide.move(index - 1)}
              >
                Back
              </button>
              <button
                ref={next}
                className="introduction-primary"
                disabled={guide.busy}
                onClick={forward}
              >
                {guide.busy
                  ? "Saving…"
                  : last
                    ? "Finish"
                    : index === 0
                      ? "Start tour"
                      : "Next"}
              </button>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
