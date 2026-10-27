import React, { useEffect, useRef, useState } from "react";
import { GUIDE_STEPS, guideRect } from "./onboarding.mjs";
import "./introduction.css";

export function Introduction({ guide, onNavigate, onDone, native }) {
  const step = GUIDE_STEPS[guide.progress.step],
    dialog = useRef(null),
    next = useRef(null);
  const [skip, setSkip] = useState(false),
    [rect, setRect] = useState(null);
  useEffect(() => {
    onNavigate(step);
    setSkip(false);
  }, [step.id]);
  useEffect(() => {
    let frame;
    const measure = () => {
      const target =
        step.target && document.querySelector(`[data-tour="${step.target}"]`);
      setRect(
        guideRect(target?.getBoundingClientRect(), innerWidth, innerHeight),
      );
    };
    frame = requestAnimationFrame(measure);
    const timer = setInterval(measure, 500);
    addEventListener("resize", measure);
    addEventListener("scroll", measure, true);
    return () => {
      cancelAnimationFrame(frame);
      clearInterval(timer);
      removeEventListener("resize", measure);
      removeEventListener("scroll", measure, true);
    };
  }, [step.id]);
  useEffect(() => {
    const previous = document.activeElement;
    const key = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        setSkip(true);
        return;
      }
      if (e.key !== "Tab") return;
      const buttons = [
        ...dialog.current.querySelectorAll(
          "button:not(:disabled),select:not(:disabled)",
        ),
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
  }, [skip, step.id]);
  async function finish(outcome) {
    if (await guide.finish(outcome)) onDone();
  }
  const cardTop = rect && rect.top > innerHeight * 0.55;
  return (
    <div className="introduction-layer" data-no-drag-scroll="true">
      <div className="introduction-shield" aria-hidden="true" />
      <svg
        className="introduction-mask"
        width="100%"
        height="100%"
        aria-hidden="true"
      >
        <defs>
          <mask id="guide-cutout">
            <rect width="100%" height="100%" fill="white" />
            {rect && !skip && (
              <rect
                x={rect.left}
                y={rect.top}
                width={rect.width}
                height={rect.height}
                rx="18"
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="black"
          fillOpacity=".68"
          mask="url(#guide-cutout)"
        />
      </svg>
      {rect && !skip && (
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
        className={`introduction-card ${cardTop ? "at-top" : ""}`}
      >
        <div className="introduction-eyebrow">
          COSCAROS / INTRODUCTION{" "}
          <span>
            {guide.progress.step + 1} / {GUIDE_STEPS.length}
          </span>
        </div>
        <progress
          aria-label="Introduction progress"
          value={guide.progress.step + 1}
          max={GUIDE_STEPS.length}
        />
        <h1 id="introduction-title">
          {skip ? "Skip the introduction?" : step.title}
        </h1>
        <p id="introduction-description">
          {skip
            ? "You can replay the entire guide from Settings → System → Application. Keep the guide open if you tapped Skip by mistake."
            : step.body}
        </p>
        {!skip && native && step.id === "taskbar" && (
          <p className="introduction-hint">
            The native taskbar sits below this guide. Its shortcuts are paused
            until you finish or confirm Skip.
          </p>
        )}
        {!skip && (
          <label className="introduction-section">
            Jump to section
            <select
              aria-label="Guide section"
              value={guide.progress.step}
              disabled={guide.busy}
              onChange={(e) => guide.move(Number(e.target.value))}
            >
              {GUIDE_STEPS.map((s, i) => (
                <option key={s.id} value={i}>
                  {i + 1}. {s.title}
                </option>
              ))}
            </select>
          </label>
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
                data-keep-guide
                disabled={guide.busy}
                onClick={() => {
                  setSkip(false);
                  next.current?.focus();
                }}
              >
                Keep learning
              </button>
              <button
                className="introduction-secondary"
                disabled={guide.busy}
                onClick={() => finish("skipped")}
              >
                Confirm skip
              </button>
            </>
          ) : (
            <>
              <button
                className="introduction-secondary"
                disabled={guide.busy}
                onClick={() => setSkip(true)}
              >
                Skip guide
              </button>
              <button
                disabled={guide.busy || guide.progress.step === 0}
                onClick={() => guide.move(guide.progress.step - 1)}
              >
                Back
              </button>
              <button
                ref={next}
                className="introduction-primary"
                disabled={guide.busy}
                onClick={() =>
                  guide.progress.step === GUIDE_STEPS.length - 1
                    ? finish("completed")
                    : guide.move(guide.progress.step + 1)
                }
              >
                {guide.busy
                  ? "Saving…"
                  : guide.progress.step === GUIDE_STEPS.length - 1
                    ? "Finish introduction"
                    : guide.progress.step === 0
                      ? "Start tour"
                      : "Next"}
              </button>
            </>
          )}
        </div>
        <p className="introduction-hint">
          {native
            ? "Progress saved on this Pi."
            : "Preview: progress saved in this browser."}{" "}
          Background controls are paused during the guide.
        </p>
      </section>
    </div>
  );
}
