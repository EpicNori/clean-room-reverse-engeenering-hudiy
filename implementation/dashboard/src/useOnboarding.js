import { useEffect, useRef, useState } from "react";
import { GUIDE_KEY, guideState, readGuide } from "./onboarding.mjs";

export function useOnboarding(native, taskbar) {
  const [progress, setProgress] = useState(() => guideState(null));
  const [ready, setReady] = useState(false),
    [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [remoteActive, setRemoteActive] = useState(false);
  const mounted = useRef(true),
    pending = useRef(false),
    current = useRef(progress);
  current.current = progress;
  async function request(data) {
    const controller = new AbortController(),
      timer = setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetch("/api/onboarding", {
        ...(data
          ? {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(data),
            }
          : {}),
        signal: controller.signal,
      });
      const result = await response.json();
      if (!response.ok || !result.available)
        throw Error(
          result.error || "Pi guide storage is unavailable. Please retry.",
        );
      return result;
    } finally {
      clearTimeout(timer);
    }
  }
  useEffect(() => {
    mounted.current = true;
    let cancelled = false,
      initialized = false,
      loading = false;
    async function load() {
      if (loading || (!taskbar && initialized)) return;
      loading = true;
      try {
        const data = native ? await request() : readGuide(localStorage);
        if (cancelled) return;
        setError("");
        setProgress(guideState(data));
        if (taskbar) {
          setRemoteActive(data.active === true);
          return;
        }
        if (data.outcome === "pending") {
          if (native) await request({ action: "begin" });
          if (!cancelled) setOpen(true);
        }
        initialized = true;
      } catch {
        if (!cancelled)
          setError(
            "Introduction could not load. Replay it in Settings → System → Application.",
          );
      } finally {
        loading = false;
        if (!cancelled) setReady(true);
      }
    }
    load();
    const interval = native ? setInterval(load, 2000) : null;
    return () => {
      cancelled = true;
      mounted.current = false;
      clearInterval(interval);
    };
  }, [native, taskbar]);
  useEffect(() => {
    if (!native || !open) return;
    const timer = setInterval(() => {
      request({ action: "heartbeat" })
        .then(() => {
          if (mounted.current) setError("");
        })
        .catch(() => {
          if (mounted.current)
            setError(
              "Device connection interrupted. Keep the guide open and retry before continuing.",
            );
        });
    }, 10000);
    return () => clearInterval(timer);
  }, [native, open]);
  async function run(job) {
    if (pending.current) return false;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await job();
      return true;
    } catch (e) {
      if (mounted.current)
        setError(
          e.name === "AbortError"
            ? "Saving timed out. Please retry."
            : e.message,
        );
      return false;
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  const start = () =>
    run(async () => {
      if (native) await request({ action: "begin" });
      // Replaying does not erase a previous completion if the guide is interrupted.
      if (mounted.current) {
        setProgress((p) => ({ ...p, step: 0 }));
        setOpen(true);
      }
    });
  const move = (step) =>
    run(async () => {
      const next = guideState({ ...current.current, step });
      if (next.step !== step) throw Error("Invalid guide section");
      if (native) {
        await request({ action: "heartbeat" });
        await request({ action: "progress", step });
      } else localStorage.setItem(GUIDE_KEY, JSON.stringify(next));
      if (mounted.current) setProgress(next);
    });
  const finish = (outcome) =>
    run(async () => {
      if (!["completed", "skipped"].includes(outcome))
        throw Error("Invalid guide outcome");
      const next = { ...current.current, outcome };
      if (native) await request({ action: "finish", outcome, confirmed: true });
      else localStorage.setItem(GUIDE_KEY, JSON.stringify(next));
      if (mounted.current) {
        setProgress(next);
        setOpen(false);
      }
    });
  return {
    progress,
    ready,
    open,
    busy,
    error,
    remoteActive,
    start,
    move,
    finish,
  };
}
