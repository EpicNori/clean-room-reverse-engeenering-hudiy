import { useState, useRef, useEffect, useCallback } from "react";
import {
  DASHBOARD_KEY,
  defaultDashboard,
  readDashboard,
  validateDashboard,
  dashboardPack,
} from "./dashboardWidgets.mjs";

export function useDashboardWidgets(native, active = true) {
  const [config, setConfig] = useState(() =>
    native ? defaultDashboard() : readDashboard(),
  );
  const [ready, setReady] = useState(!native),
    [available, setAvailable] = useState(!native),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const revision = useRef(""),
    generation = useRef(0),
    pending = useRef(false),
    mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const read = useCallback(async () => {
    if (!native || !active || pending.current) return;
    const ticket = ++generation.current;
    const controller = new AbortController(),
      timer = setTimeout(() => controller.abort(), 2500);
    try {
      const response = await fetch("/api/dashboard-widgets", {
        signal: controller.signal,
      });
      if (!response.ok) throw Error("Device dashboard storage is unavailable");
      const data = await response.json(),
        valid = validateDashboard(data.config);
      if (!mounted.current || pending.current || ticket !== generation.current)
        return;
      revision.current = data.revision;
      setAvailable(data.available === true);
      setConfig((old) =>
        JSON.stringify(old) === JSON.stringify(valid) ? old : valid,
      );
      setError(data.available ? "" : "Device dashboard storage is unavailable");
      setReady(true);
    } catch {
      if (mounted.current && ticket === generation.current && !pending.current)
        setError(
          "Device dashboard storage is unavailable. Your saved layout has not been replaced.",
        );
    } finally {
      clearTimeout(timer);
    }
  }, [native, active]);
  useEffect(() => {
    if (!active) return;
    if (native) {
      read();
      const timer = setInterval(read, 5000);
      return () => clearInterval(timer);
    }
    const sync = (e) => {
      if (e.key === DASHBOARD_KEY) setConfig(readDashboard());
    };
    addEventListener("storage", sync);
    return () => removeEventListener("storage", sync);
  }, [read, native, active]);
  async function save(next, expectedRevision = revision.current) {
    if (pending.current) return false;
    const valid = validateDashboard(next);
    generation.current++;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      if (native) {
        if (!available || !revision.current)
          throw Error("Wait for device dashboard storage before saving");
        const controller = new AbortController(),
          timer = setTimeout(() => controller.abort(), 5000);
        try {
          const response = await fetch("/api/dashboard-widgets", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ revision: expectedRevision, config: valid }),
            signal: controller.signal,
          });
          const data = await response.json();
          if (!response.ok)
            throw Error(data.error || "Could not save dashboard");
          revision.current = data.revision;
          if (mounted.current) setConfig(validateDashboard(data.config));
        } finally {
          clearTimeout(timer);
        }
      } else {
        localStorage.setItem(DASHBOARD_KEY, JSON.stringify(valid));
        if (mounted.current) setConfig(valid);
      }
      return true;
    } catch (e) {
      if (mounted.current)
        setError(
          e.name === "AbortError"
            ? "Saving timed out. Reload to check the device before retrying."
            : e.message,
        );
      return false;
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  async function exportLayout() {
    if (native) {
      const controller = new AbortController(),
        timer = setTimeout(() => controller.abort(), 5000);
      try {
        const response = await fetch("/api/dashboard-widgets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "export" }),
          signal: controller.signal,
        });
        const data = await response.json();
        if (!response.ok) throw Error(data.error || "Could not export layout");
        return "Saved to Downloads/coscarOS-Layouts/" + data.fileName;
      } finally {
        clearTimeout(timer);
      }
    }
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(dashboardPack(config), null, 2)], {
        type: "application/json",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "coscaros-dashboard.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return "Layout exported. It contains settings only, without phone or vehicle data.";
  }
  return {
    config,
    revision: revision.current,
    ready,
    available,
    busy,
    error,
    save,
    reload: read,
    exportLayout,
    storage: native ? "Saved on Pi" : "Saved in this browser",
  };
}
