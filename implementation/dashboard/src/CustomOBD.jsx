import React, { useEffect, useRef, useState } from "react";
import {
  KEY,
  STOCK,
  DERIVED,
  TEMPLATES,
  id,
  defaultConfig,
  reading,
  sources,
  firstSpace,
  place,
  sample,
  readLocal,
  validateLocal,
  validateSensor,
} from "./customOBD.mjs";
import "./customOBD.css";

const Icon = ({ name }) => (
  <span className="material-symbols-rounded" aria-hidden="true">
    {name}
  </span>
);
async function request(body) {
  const controller = new AbortController(),
    timer = setTimeout(() => controller.abort(), 4000);
  try {
    const response = await fetch(
      "/api/obd-dashboard",
      body === undefined
        ? { signal: controller.signal }
        : {
            method: "POST",
            signal: controller.signal,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
    );
    const data = await response.json();
    if (!response.ok) {
      const error = Error(data.error || "Dashboard service unavailable");
      error.status = response.status;
      throw error;
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}

function Plot({ values, times, definition, gauge = false, palette }) {
  const clean = values.map((v) => (Number.isFinite(v) ? v : null)),
    finite = clean.filter((v) => v !== null);
  const latest = clean.at(-1),
    min = definition.min ?? 0,
    max = definition.max ?? 100;
  const start = times?.[0],
    end = times?.at(-1);
  const points = clean.map((v, i) =>
    v === null
      ? null
      : [
          Number.isFinite(start) && Number.isFinite(end) && end > start
            ? ((times[i] - start) / (end - start)) * 100
            : (i * 100) / Math.max(clean.length - 1, 1),
          82 - Math.max(0, Math.min(1, (v - min) / (max - min))) * 70,
        ],
  );
  const segments = [];
  let current = [];
  for (const point of points) {
    if (point) current.push(point);
    else if (current.length) {
      segments.push(current);
      current = [];
    }
  }
  if (current.length) segments.push(current);
  const fraction = Number.isFinite(latest)
    ? Math.max(0, Math.min(1, (latest - min) / (max - min)))
    : 0;
  // Code-rendered telemetry, not an image or a decorative substitute asset.
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const paint = () => {
      const rect = canvas.getBoundingClientRect(),
        dpr = devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      const ctx = canvas.getContext("2d");
      ctx.scale(dpr, dpr);
      const style = getComputedStyle(canvas),
        color = style.getPropertyValue("--primary").trim(),
        track = style.getPropertyValue("--track").trim();
      ctx.lineCap = "round";
      if (gauge) {
        const cx = rect.width / 2,
          cy = rect.height * 0.68,
          r = Math.min(rect.width * 0.38, rect.height * 0.55);
        const arc = (end, stroke) => {
          ctx.beginPath();
          ctx.strokeStyle = stroke;
          ctx.lineWidth = 12;
          ctx.arc(cx, cy, r, Math.PI * 0.8, end);
          ctx.stroke();
        };
        arc(Math.PI * 2.2, track);
        if (Number.isFinite(latest))
          arc(Math.PI * (0.8 + 1.4 * fraction), color);
      } else {
        ctx.strokeStyle = track;
        ctx.lineWidth = 1;
        for (const y of [12, 47, 82]) {
          ctx.beginPath();
          ctx.moveTo(0, (y * rect.height) / 100);
          ctx.lineTo(rect.width, (y * rect.height) / 100);
          ctx.stroke();
        }
        ctx.strokeStyle = color;
        ctx.lineWidth = 3;
        for (const segment of segments) {
          ctx.beginPath();
          segment.forEach(([x, y], i) => {
            const xy = [(x * rect.width) / 100, (y * rect.height) / 100];
            i ? ctx.lineTo(...xy) : ctx.moveTo(...xy);
          });
          ctx.stroke();
        }
      }
    };
    const observer = new ResizeObserver(paint);
    observer.observe(canvas);
    paint();
    return () => observer.disconnect();
  }, [values.join(","), times?.join(","), min, max, gauge, palette]);
  return (
    <canvas
      ref={ref}
      role="img"
      aria-label={`${definition.label} ${gauge ? "gauge" : "history"}${!finite.length ? ", no data" : ""}`}
    />
  );
}

function Keyboard({ editor, close }) {
  const root = useRef(null);
  useEffect(() => {
    if (editor) root.current?.scrollIntoView({ block: "nearest" });
  }, [editor?.label]);
  if (!editor) return null;
  const chars =
    editor.mode === "hex"
      ? "0123456789ABCDEF"
      : editor.mode === "number"
        ? "1234567890.-"
        : editor.mode === "formula"
          ? "ABCDEFGH0123456789()+-*/.&|%^"
          : "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/%.°";
  return (
    <div
      ref={root}
      className="obd-keyboard"
      aria-label={`Keyboard for ${editor.label}`}
    >
      <div>
        <strong>{editor.label}</strong>
        <button type="button" onClick={close}>
          Done typing
        </button>
      </div>
      <output className="obd-keyboard-value" aria-live="polite">
        {String(editor.value ?? "") || "Empty"}
      </output>
      <div className="obd-key-grid">
        {[...chars].map((c) => (
          <button
            type="button"
            key={c}
            onClick={() =>
              editor.set(
                (String(editor.value ?? "") + c).slice(0, editor.max || 96),
              )
            }
          >
            {c}
          </button>
        ))}
        {editor.mode === "text" && (
          <button
            type="button"
            onClick={() =>
              editor.set(
                (String(editor.value || "") + " ").slice(0, editor.max || 96),
              )
            }
          >
            Space
          </button>
        )}
        <button
          type="button"
          onClick={() =>
            editor.set(
              Array.from(String(editor.value ?? ""))
                .slice(0, -1)
                .join(""),
            )
          }
          aria-label="Delete character"
        >
          <Icon name="backspace" />
        </button>
        <button type="button" onClick={() => editor.set("")}>
          Clear
        </button>
      </div>
    </div>
  );
}

function Dialog({ label, children, close }) {
  const ref = useRef(null),
    opener = useRef(document.activeElement);
  useEffect(
    () => () => {
      if (opener.current?.isConnected) opener.current.focus();
    },
    [],
  );
  useEffect(() => {
    (
      ref.current.querySelector("input,select") ||
      ref.current.querySelector("button")
    )?.focus();
  }, [label]);
  return (
    <div
      className="obd-dialog-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <section
        ref={ref}
        className="obd-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={label}
        onKeyDown={(e) => {
          e.stopPropagation();
          if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            close();
          }
          if (e.key === "Tab") {
            const controls = [
              ...ref.current.querySelectorAll(
                "button:not(:disabled),input,select,textarea",
              ),
            ].filter((e) => e.getClientRects().length);
            const first = controls[0],
              last = controls.at(-1);
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first.focus();
            }
          }
        }}
      >
        <header>
          <h2>{label}</h2>
          <button type="button" onClick={close} aria-label="Close editor">
            <Icon name="close" />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

export function CustomOBD({
  telemetry,
  now,
  demo,
  onSettings,
  onLogs,
  native = false,
  palette,
}) {
  const [config, setConfig] = useState(defaultConfig),
    [loaded, setLoaded] = useState(false),
    [editing, setEditing] = useState(false),
    [libraryOpen, setLibraryOpen] = useState(false),
    [status, setStatus] = useState("Loading dashboard…"),
    [error, setError] = useState(""),
    [dialog, setDialog] = useState(null),
    [keyboard, setKeyboard] = useState(null),
    [drag, setDrag] = useState(null),
    [sampleBytes, setSampleBytes] = useState("00"),
    [preview, setPreview] = useState(null),
    [loadAttempt, setLoadAttempt] = useState(0);
  const state = useRef({
      revision: 0,
      mappingRevision: 0,
      appliedSensors: "[]",
      backend: false,
      pending: null,
      busy: false,
      alive: true,
      service: false,
    }),
    current = useRef(config),
    grid = useRef(null),
    dragRef = useRef(null),
    suppressClick = useRef(0),
    recovered = useRef(null);
  current.current = config;
  useEffect(() => {
    state.current.alive = true;
    request()
      .then((data) => {
        if (!state.current.alive) return;
        if (native && !data.enabled)
          throw Error("Device dashboard storage is unavailable");
        state.current.backend = data.enabled;
        state.current.service = true;
        state.current.revision = data.revision;
        state.current.mappingRevision = data.mappingRevision ?? data.revision;
        state.current.appliedSensors = JSON.stringify(data.config.sensors);
        setConfig(data.enabled ? data.config : readLocal());
        setLoaded(true);
        setStatus(data.enabled ? "Saved on device" : "Saved in this browser");
        try {
          const cache = JSON.parse(localStorage.getItem(KEY + ".pending"));
          if (data.enabled && cache && validateLocal(cache.config)) {
            if (JSON.stringify(cache.config) === JSON.stringify(data.config))
              localStorage.removeItem(KEY + ".pending");
            else {
              recovered.current = cache.config;
              setError(
                "Unsaved local edits were recovered. You can restore them or keep the saved dashboard.",
              );
            }
          }
        } catch {}
      })
      .catch(() => {
        if (!state.current.alive) return;
        if (native) {
          setError("Could not load the saved device dashboard.");
          return;
        }
        setConfig(readLocal());
        setLoaded(true);
        setStatus("Saved in this browser");
      });
    return () => {
      state.current.alive = false;
    };
  }, [native, loadAttempt]);
  const announce = (message) => {
    if (state.current.alive) setStatus(message);
  };
  async function flush() {
    const s = state.current;
    if (s.busy || !s.pending) return;
    s.busy = true;
    try {
      while (s.pending) {
        const next = s.pending;
        s.pending = null;
        announce("Saving…");
        try {
          const result = await request({ revision: s.revision, config: next });
          s.revision = result.revision;
          s.mappingRevision = result.mappingRevision ?? result.revision;
          s.appliedSensors = JSON.stringify(result.config.sensors);
          if (s.alive) setError("");
          try {
            if (s.pending)
              localStorage.setItem(
                KEY + ".pending",
                JSON.stringify({ config: s.pending, revision: s.revision }),
              );
            else localStorage.removeItem(KEY + ".pending");
          } catch {}
          announce(s.pending ? "Saving…" : "Saved on device");
        } catch (e) {
          if (e.status === 409) {
            try {
              const saved = await request();
              if (JSON.stringify(saved.config) === JSON.stringify(next)) {
                s.revision = saved.revision;
                s.mappingRevision = saved.mappingRevision ?? saved.revision;
                s.appliedSensors = JSON.stringify(saved.config.sensors);
                if (!s.pending) {
                  try {
                    localStorage.removeItem(KEY + ".pending");
                  } catch {}
                  announce("Saved on device");
                }
                continue;
              }
            } catch {}
          }
          s.pending = s.pending || next;
          if (s.alive) {
            setError(e.message);
            announce("Not saved — retry before leaving");
          }
          break;
        }
      }
    } finally {
      s.busy = false;
    }
  }
  function change(next) {
    current.current = next;
    setConfig(next);
    setError("");
    if (state.current.backend) {
      state.current.pending = next;
      try {
        localStorage.setItem(
          KEY + ".pending",
          JSON.stringify({ config: next, revision: state.current.revision }),
        );
      } catch {}
      flush();
    } else
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
        announce("Saved in this browser");
      } catch {
        setError("Could not save this dashboard.");
      }
  }
  function updateWidgets(widgets) {
    if (widgets === current.current.widgets) {
      announce("That space is occupied or outside the grid");
      return;
    }
    change({ ...current.current, widgets });
  }
  function add(source, position) {
    const cfg = current.current;
    if (cfg.widgets.length >= 16) {
      announce("The dashboard holds up to 16 tiles");
      return;
    }
    const cell = position || firstSpace(cfg.widgets);
    if (!cell) {
      announce("No free space. Remove or move a tile first.");
      return;
    }
    const widget = {
      id: id(),
      source,
      title: "",
      view: "value",
      ...cell,
      w: 1,
      h: 1,
    };
    // A library drop must not overlap an existing tile.
    if (
      cfg.widgets.some(
        (w) =>
          cell.x >= w.x &&
          cell.x < w.x + w.w &&
          cell.y >= w.y &&
          cell.y < w.y + w.h,
      )
    ) {
      announce("Drop into an empty cell");
      return;
    }
    change({ ...cfg, widgets: [...cfg.widgets, widget] });
  }
  function cellAt(x, y) {
    const rect = grid.current?.getBoundingClientRect();
    if (
      !rect ||
      x < rect.left ||
      x > rect.right ||
      y < rect.top ||
      y > rect.bottom
    )
      return null;
    const columns =
      Number(
        getComputedStyle(grid.current).getPropertyValue("--obd-columns"),
      ) || 4;
    if (columns !== 4) {
      const card = document
        .elementFromPoint(x, y)
        ?.closest("[data-obd-widget-id]");
      const widget = current.current.widgets.find(
        (w) => w.id === card?.dataset.obdWidgetId,
      );
      return widget ? { x: widget.x, y: widget.y } : null;
    }
    const gap = parseFloat(getComputedStyle(grid.current).rowGap) || 16,
      rowHeight =
        grid.current.querySelector(".obd-drop-cell")?.getBoundingClientRect()
          .height || 180;
    return {
      x: Math.max(
        0,
        Math.min(3, Math.floor((x - rect.left) / ((rect.width + gap) / 4))),
      ),
      y: Math.max(
        0,
        Math.min(7, Math.floor((y - rect.top) / (rowHeight + gap))),
      ),
    };
  }
  const handle = (kind, identifier) => ({
    "data-obd-drag-handle": "true",
    onPointerDown: (e) => {
      if (e.button !== 0 || !e.isPrimary) return;
      e.preventDefault();
      e.stopPropagation();
      e.currentTarget.setPointerCapture(e.pointerId);
      const d = {
        kind,
        id: identifier,
        px: e.clientX,
        py: e.clientY,
        startX: e.clientX,
        startY: e.clientY,
        moved: false,
        cell: null,
      };
      dragRef.current = d;
      setDrag(d);
    },
    onPointerMove: (e) => {
      let d = dragRef.current;
      if (!d) return;
      e.preventDefault();
      e.stopPropagation();
      const moved =
        d.moved || Math.hypot(e.clientX - d.startX, e.clientY - d.startY) > 8;
      d = {
        ...d,
        moved,
        px: e.clientX,
        py: e.clientY,
        cell: cellAt(e.clientX, e.clientY),
      };
      dragRef.current = d;
      setDrag(d);
      const scroll = grid.current?.closest(".custom-obd");
      if (scroll && moved) {
        const r = scroll.getBoundingClientRect();
        if (e.clientY > r.bottom - 60) scroll.scrollTop += 12;
        else if (e.clientY < r.top + 100) scroll.scrollTop -= 12;
      }
    },
    onPointerUp: (e) => {
      const d = dragRef.current;
      dragRef.current = null;
      setDrag(null);
      if (!d) return;
      suppressClick.current = performance.now() + 500;
      e.stopPropagation();
      if (d.moved && d.cell) {
        if (d.kind === "widget")
          updateWidgets(
            place(current.current.widgets, d.id, d.cell.x, d.cell.y),
          );
        else add(d.id, d.cell);
      } else if (!d.moved && d.kind === "source") add(d.id);
    },
    onPointerCancel: () => {
      dragRef.current = null;
      setDrag(null);
    },
  });
  function field(label, key, mode = "text", max = 40) {
    const value = dialog.value[key] ?? "";
    const set = (update) =>
      setDialog((d) => ({
        ...d,
        value: {
          ...d.value,
          [key]:
            typeof update === "function" ? update(d.value[key] ?? "") : update,
        },
      }));
    return (
      <label className="obd-field">
        <span>{label}</span>
        <div>
          <input
            aria-label={label}
            value={value}
            maxLength={max}
            inputMode={mode === "number" ? "decimal" : "text"}
            onChange={(e) =>
              set(
                mode === "hex" ? e.target.value.toUpperCase() : e.target.value,
              )
            }
          />
          <button
            type="button"
            aria-label={`Keyboard for ${label}`}
            onClick={() => setKeyboard({ label, set, mode, max, key })}
          >
            <Icon name="keyboard" />
          </button>
        </div>
      </label>
    );
  }
  function closeEditor() {
    state.current.editorVersion = (state.current.editorVersion || 0) + 1;
    setDialog(null);
    setKeyboard(null);
  }
  function open(type, value) {
    state.current.editorVersion = (state.current.editorVersion || 0) + 1;
    setDialog({ type, value: structuredClone(value) });
    setKeyboard(null);
    setError("");
    setSampleBytes("00".repeat(Number(value.bytes) || 1));
    setPreview(null);
  }
  async function saveSensor(e) {
    e.preventDefault();
    const version = state.current.editorVersion,
      sensor = { ...dialog.value };
    for (const key of ["bytes", "min", "max", "decimals", "interval"])
      sensor[key] = Number(sensor[key]);
    sensor.pid = sensor.pid.toUpperCase().trim();
    sensor.header = sensor.header?.toUpperCase().trim() || null;
    const validation = validateSensor(sensor);
    if (validation) {
      setError(validation);
      return;
    }
    if (state.current.service) {
      const controller = new AbortController(),
        timer = setTimeout(() => controller.abort(), 4000);
      try {
        const response = await fetch("/api/obd-formula", {
          method: "POST",
          signal: controller.signal,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sensor }),
        });
        const result = await response.json();
        if (!response.ok)
          throw Error(result.error || "Could not validate this mapping");
      } catch (e) {
        if (state.current.editorVersion === version && state.current.alive)
          setError(
            e.name === "AbortError"
              ? "Mapping validation timed out"
              : e.message,
          );
        return;
      } finally {
        clearTimeout(timer);
      }
    }
    if (state.current.editorVersion !== version) return;
    const cfg = current.current;
    const existing = cfg.sensors.some((s) => s.id === sensor.id);
    if (!existing && cfg.sensors.length >= 8) {
      setError("Use up to 8 custom sensors.");
      return;
    }
    change({
      ...cfg,
      sensors: existing
        ? cfg.sensors.map((s) => (s.id === sensor.id ? sensor : s))
        : [...cfg.sensors, sensor],
    });
    closeEditor();
  }
  function newSensor(template) {
    open("sensor", { ...template, id: "s_" + id().slice(2) });
  }
  async function testSample() {
    const version = state.current.editorVersion;
    const sensor = {
      ...dialog.value,
      pid: dialog.value.pid.trim().toUpperCase(),
      header: dialog.value.header?.trim().toUpperCase() || null,
    };
    for (const key of ["bytes", "min", "max", "decimals", "interval"])
      sensor[key] = Number(sensor[key]);
    const validation = validateSensor(sensor);
    if (validation) {
      setPreview(validation);
      return;
    }
    const controller = new AbortController(),
      timer = setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetch("/api/obd-formula", {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sensor,
          sample: sampleBytes.trim().toUpperCase(),
        }),
      });
      const result = await response.json();
      if (!response.ok) throw Error(result.error);
      if (state.current.editorVersion !== version || !state.current.alive)
        return;
      setPreview(
        result.sampleError ||
          `Sample result: ${result.sampleValue} ${sensor.unit}`,
      );
    } catch (e) {
      if (state.current.editorVersion !== version || !state.current.alive)
        return;
      setPreview(e.name === "AbortError" ? "Sample test timed out" : e.message);
    } finally {
      clearTimeout(timer);
    }
  }

  const dataRevision =
    JSON.stringify(config.sensors) === state.current.appliedSensors
      ? (state.current.mappingRevision ?? state.current.revision)
      : -1;
  const displayValue = (source) => {
    if (demo) {
      const key = source.split(":")[1];
      const value = {
        speed: 60 + 20 * Math.sin(now.getTime() / 4000),
        rpm: 1800,
        coolant: 89,
        load: 32,
        throttle: 22,
        voltage: 14.1,
        acceleration: 1.2,
      }[key];
      return {
        value: Number.isFinite(value) ? value : null,
        error: source.startsWith("custom:")
          ? "Custom sensors need a vehicle response"
          : null,
      };
    }
    return sample(
      config,
      source,
      telemetry,
      dataRevision,
      now.getTime() / 1000,
    );
  };
  const rows = Math.min(
    8,
    Math.max(3, ...config.widgets.map((w) => w.y + w.h)) + (editing ? 1 : 0),
  );
  return (
    <div className={`custom-obd ${editing ? "obd-editing" : ""}`}>
      <header className="obd-page-header">
        <div>
          <h1>My OBD</h1>
          <p>
            {demo
              ? "DEMO · simulated readings"
              : telemetry?.mode === "simulator"
                ? "SIMULATOR · test readings"
                : telemetry?.connected
                  ? "ELM327 connected"
                  : "OBD disconnected"}{" "}
            <span>· {status}</span>
          </p>
        </div>
        <div className="obd-page-actions">
          {editing && (
            <button
              onClick={() => setLibraryOpen((v) => !v)}
              aria-expanded={libraryOpen}
            >
              <Icon name="add" />
              {libraryOpen ? "Hide data sources" : "Add data"}
            </button>
          )}
          <button onClick={onLogs}>
            <Icon name="description" />
            Logs
          </button>
          <button onClick={onSettings} aria-label="OBD connection settings">
            <Icon name="settings" />
          </button>
          <button
            onClick={() => {
              setEditing((v) => !v);
              setKeyboard(null);
            }}
            disabled={!loaded}
          >
            <Icon name={editing ? "check" : "dashboard_customize"} />
            {editing ? "Done" : "Edit dashboard"}
          </button>
        </div>
      </header>
      {error && (
        <div className="obd-error" role="alert">
          {error}{" "}
          {!loaded && (
            <button
              onClick={() => {
                setError("");
                setLoadAttempt((v) => v + 1);
              }}
            >
              Retry loading
            </button>
          )}{" "}
          {recovered.current && (
            <>
              <button
                onClick={() => {
                  const cfg = recovered.current;
                  recovered.current = null;
                  change(cfg);
                }}
              >
                Restore recovered edits
              </button>
              <button
                onClick={() => {
                  recovered.current = null;
                  localStorage.removeItem(KEY + ".pending");
                  setError("");
                }}
              >
                Keep saved layout
              </button>
            </>
          )}{" "}
          {state.current.pending && (
            <>
              <button onClick={flush}>Retry save</button>
              <button onClick={() => location.reload()}>
                Reload saved layout
              </button>
            </>
          )}
        </div>
      )}
      {editing && libraryOpen && (
        <section className="obd-library" aria-label="Available data sources">
          <div>
            <h2>Add data</h2>
            <p>
              Drag a reading into an empty cell, or tap it to add. Use a tile’s
              arrows on smaller screens.
            </p>
          </div>
          <div className="obd-source-list">
            {sources(config).map((s) => (
              <div className="obd-source" key={s.source}>
                <button
                  {...handle("source", s.source)}
                  onClick={() => {
                    if (performance.now() > suppressClick.current)
                      add(s.source);
                  }}
                  aria-label={`Add ${s.label}`}
                >
                  <Icon name="drag_indicator" />
                  {s.label}
                </button>
                {s.source.startsWith("custom:") && (
                  <button
                    aria-label={`Edit ${s.label} mapping`}
                    onClick={() =>
                      open(
                        "sensor",
                        config.sensors.find((v) => v.id === s.id),
                      )
                    }
                  >
                    <Icon name="tune" />
                  </button>
                )}
              </div>
            ))}
          </div>
          <div className="obd-page-actions">
            <button onClick={() => open("templates", {})}>
              <Icon name="add" />
              Custom sensor
            </button>
            <button onClick={() => open("range", config.range)}>
              Range inputs
            </button>
          </div>
        </section>
      )}
      {!config.widgets.length && !editing && (
        <div className="obd-empty">
          <h2>Your dashboard, your data</h2>
          <p>Choose Edit dashboard to add readings and arrange your layout.</p>
        </div>
      )}
      <section
        ref={grid}
        className="obd-grid"
        style={{ "--obd-rows": rows }}
        aria-label="Custom OBD dashboard"
      >
        {editing &&
          Array.from({ length: rows * 4 }, (_, i) => (
            <div
              key={"cell" + i}
              className={`obd-drop-cell ${drag?.cell?.x === i % 4 && drag?.cell?.y === Math.floor(i / 4) ? "obd-drop-active" : ""}`}
              style={{
                gridColumn: (i % 4) + 1,
                gridRow: Math.floor(i / 4) + 1,
              }}
              aria-hidden="true"
            />
          ))}
        {[...config.widgets]
          .sort((a, b) => a.y - b.y || a.x - b.x)
          .map((widget) => {
            const def = reading(config, widget.source) || {
                label: "Missing sensor",
                unit: "",
              },
              data = displayValue(widget.source);
            const title = widget.title || def.label,
              valid = Number.isFinite(data.value),
              value = valid ? data.value.toFixed(def.decimals || 0) : "—";
            const historyRows = (telemetry?.history || []).slice(-60);
            const history = historyRows.map((row) =>
              widget.source.startsWith("custom:") &&
              row.customRevision !== dataRevision
                ? null
                : row[
                    widget.source.startsWith("builtin:")
                      ? widget.source.split(":")[1]
                      : widget.source
                  ],
            );
            const values = demo ? [data.value] : [...history, data.value];
            return (
              <article
                key={widget.id}
                data-obd-widget-id={widget.id}
                className={`obd-widget obd-view-${widget.view} ${drag?.id === widget.id ? "obd-moving" : ""}`}
                style={{
                  gridColumn: `${widget.x + 1} / span ${widget.w}`,
                  gridRow: `${widget.y + 1} / span ${widget.h}`,
                  "--obd-span": widget.w,
                }}
                aria-label={title}
              >
                <header>
                  <h2>{title}</h2>
                  {editing && (
                    <button
                      {...handle("widget", widget.id)}
                      aria-label={`Drag ${title}`}
                    >
                      <Icon name="drag_indicator" />
                    </button>
                  )}
                </header>
                {widget.source === "errors" ? (
                  <div className="obd-messages">
                    {!telemetry?.connected ? (
                      <p>Connect the OBD adapter to read vehicle messages.</p>
                    ) : (
                      <>
                        {telemetry.error && <p>{telemetry.error}</p>}
                        {Object.entries(telemetry.custom || {})
                          .filter(([, v]) => v.error)
                          .map(([key, v]) => (
                            <p key={key}>
                              {config.sensors.find((s) => s.id === key)?.label}:{" "}
                              {v.error}
                            </p>
                          ))}
                        {telemetry.diagnostics?.codes?.map((code) => (
                          <strong key={code}>{code}</strong>
                        ))}
                        <p>
                          {telemetry.diagnostics?.error ||
                            (!telemetry.diagnostics?.timestamp
                              ? "Waiting for trouble-code scan"
                              : telemetry.diagnostics.codes.length
                                ? "Stored trouble codes"
                                : "No stored codes reported")}
                        </p>
                      </>
                    )}
                  </div>
                ) : (
                  <div className="obd-reading">
                    {widget.view !== "value" && (
                      <Plot
                        values={values}
                        times={
                          demo
                            ? undefined
                            : [
                                ...historyRows.map((row) => row.timestamp),
                                telemetry?.timestamp,
                              ]
                        }
                        definition={def}
                        gauge={widget.view === "gauge"}
                        palette={palette}
                      />
                    )}
                    <div className="obd-number">
                      <strong>{value}</strong>
                      <span>{def.unit}</span>
                    </div>
                    {data.error && <small>{data.error}</small>}
                    {widget.source.startsWith("derived:") && (
                      <small>
                        {widget.source === "derived:range" && !valid
                          ? config.range.tankLitres &&
                            config.range.fuelLevel &&
                            config.range.fuelRate
                            ? "Collecting valid fuel and speed samples (0.1 km needed)"
                            : "Set tank capacity, fuel level (%) and fuel rate (L/h)"
                          : widget.source.includes("ZeroToHundred") ||
                              widget.source === "derived:zeroToHundred"
                            ? !valid
                              ? "Waiting for a complete 0–100 sample"
                              : "Estimated from OBD samples"
                            : "Estimated from continuous OBD samples"}
                      </small>
                    )}
                  </div>
                )}
                {editing && (
                  <footer className="obd-widget-tools">
                    <div>
                      {[
                        ["west", -1, 0],
                        ["east", 1, 0],
                        ["north", 0, -1],
                        ["south", 0, 1],
                      ].map(([icon, dx, dy]) => (
                        <button
                          key={icon}
                          aria-label={`Move ${title} ${icon}`}
                          disabled={
                            widget.x + dx < 0 ||
                            widget.x + dx + widget.w > 4 ||
                            widget.y + dy < 0 ||
                            widget.y + dy + widget.h > 8
                          }
                          onClick={() =>
                            updateWidgets(
                              place(
                                current.current.widgets,
                                widget.id,
                                widget.x + dx,
                                widget.y + dy,
                              ),
                            )
                          }
                        >
                          <Icon name={icon} />
                        </button>
                      ))}
                    </div>
                    <button
                      aria-label={`Configure ${title}`}
                      onClick={() => open("widget", widget)}
                    >
                      <Icon name="tune" />
                    </button>
                    <button
                      aria-label={`Remove ${title}`}
                      onClick={() =>
                        change({
                          ...current.current,
                          widgets: current.current.widgets.filter(
                            (w) => w.id !== widget.id,
                          ),
                        })
                      }
                    >
                      <Icon name="delete_outline" />
                    </button>
                  </footer>
                )}
              </article>
            );
          })}
      </section>
      {drag?.moved && (
        <div
          className="obd-drag-label"
          style={{ left: drag.px + 12, top: drag.py + 12 }}
        >
          {drag.kind === "source"
            ? reading(config, drag.id)?.label
            : "Move tile"}
        </div>
      )}
      {dialog && (
        <Dialog
          label={
            dialog.type === "templates"
              ? "Add custom sensor"
              : dialog.type === "sensor"
                ? "Sensor mapping"
                : dialog.type === "range"
                  ? "Range inputs"
                  : dialog.type === "remove-sensor"
                    ? "Remove sensor mapping"
                    : "Configure tile"
          }
          close={() => {
            closeEditor();
          }}
        >
          {error && (
            <p role="alert" className="obd-error">
              {error}
            </p>
          )}
          {dialog.type === "remove-sensor" ? (
            <>
              <p>Remove {dialog.value.label} and its tiles?</p>
              <div className="obd-dialog-actions">
                <button onClick={closeEditor}>Cancel</button>
                <button
                  onClick={() => {
                    const cfg = current.current,
                      source = "custom:" + dialog.value.id;
                    change({
                      ...cfg,
                      sensors: cfg.sensors.filter(
                        (s) => s.id !== dialog.value.id,
                      ),
                      widgets: cfg.widgets.filter((w) => w.source !== source),
                      range: {
                        ...cfg.range,
                        fuelLevel:
                          cfg.range.fuelLevel === source
                            ? null
                            : cfg.range.fuelLevel,
                        fuelRate:
                          cfg.range.fuelRate === source
                            ? null
                            : cfg.range.fuelRate,
                      },
                    });
                    closeEditor();
                  }}
                >
                  Remove mapping
                </button>
              </div>
            </>
          ) : dialog.type === "templates" ? (
            <div className="obd-template-list">
              {TEMPLATES.map((t) => (
                <button key={t.label} onClick={() => newSensor(t)}>
                  <strong>{t.label}</strong>
                  <span>
                    Mode {t.mode} · PID {t.pid}
                  </span>
                </button>
              ))}
              <p>
                Templates require ECU support. For manufacturer sensors, enter
                the PID, response bytes and formula supplied for your vehicle.
              </p>
            </div>
          ) : (
            <form
              onSubmit={
                dialog.type === "sensor"
                  ? saveSensor
                  : (e) => {
                      e.preventDefault();
                      const cfg = current.current;
                      if (dialog.type === "widget") {
                        const widget = dialog.value;
                        const [w, h] = String(
                          widget.size || `${widget.w}x${widget.h}`,
                        )
                          .split("x")
                          .map(Number);
                        let items = place(
                          cfg.widgets,
                          widget.id,
                          widget.x,
                          widget.y,
                          { w, h },
                        );
                        if (
                          items === cfg.widgets &&
                          (w !== widget.w || h !== widget.h)
                        ) {
                          setError(
                            "There is not enough free space for that size.",
                          );
                          return;
                        }
                        if (widget.source === "errors") widget.view = "value";
                        items = items.map((v) =>
                          v.id === widget.id
                            ? {
                                ...v,
                                source: widget.source,
                                title: widget.title,
                                view: widget.view,
                              }
                            : v,
                        );
                        change({ ...cfg, widgets: items });
                      } else {
                        const range = {
                          ...dialog.value,
                          tankLitres:
                            dialog.value.tankLitres === "" ||
                            dialog.value.tankLitres === null
                              ? null
                              : Number(dialog.value.tankLitres),
                        };
                        if (
                          range.tankLitres !== null &&
                          (!Number.isFinite(range.tankLitres) ||
                            range.tankLitres < 1 ||
                            range.tankLitres > 250)
                        ) {
                          setError("Enter a tank capacity of 1–250 litres.");
                          return;
                        }
                        change({ ...cfg, range });
                      }
                      closeEditor();
                    }
              }
            >
              {dialog.type === "sensor" && (
                <>
                  {field("Sensor name", "label", "text", 40)}
                  {field("Unit", "unit", "text", 16)}
                  <label className="obd-field">
                    Read mode
                    <select
                      aria-label="Read mode"
                      value={dialog.value.mode}
                      onChange={(e) =>
                        setDialog((d) => ({
                          ...d,
                          value: { ...d.value, mode: e.target.value, pid: "" },
                        }))
                      }
                    >
                      <option value="01">01 · standard OBD sensor</option>
                      <option value="22">
                        22 · manufacturer data identifier
                      </option>
                    </select>
                  </label>
                  {field("PID / identifier", "pid", "hex", 4)}
                  {field("ECU CAN header (optional)", "header", "hex", 8)}
                  <label className="obd-field">
                    Response bytes
                    <select
                      aria-label="Response bytes"
                      value={dialog.value.bytes}
                      onChange={(e) =>
                        setDialog((d) => ({
                          ...d,
                          value: { ...d.value, bytes: Number(e.target.value) },
                        }))
                      }
                    >
                      {Array.from({ length: 8 }, (_, i) => (
                        <option key={i} value={i + 1}>
                          {i + 1}
                        </option>
                      ))}
                    </select>
                  </label>
                  {field("Formula", "formula", "formula", 96)}
                  {state.current.service && (
                    <div className="obd-sample">
                      <label className="obd-field">
                        <span>Sample bytes (hex, not live data)</span>
                        <div>
                          <input
                            aria-label="Sample bytes"
                            value={sampleBytes}
                            maxLength={16}
                            onChange={(e) => {
                              setSampleBytes(e.target.value.toUpperCase());
                              setPreview(null);
                            }}
                          />
                          <button
                            type="button"
                            aria-label="Keyboard for sample bytes"
                            onClick={() =>
                              setKeyboard({
                                label: "Sample bytes",
                                set: setSampleBytes,
                                mode: "hex",
                                max: 16,
                                key: "sampleBytes",
                              })
                            }
                          >
                            <Icon name="keyboard" />
                          </button>
                        </div>
                      </label>
                      <button type="button" onClick={testSample}>
                        Test formula
                      </button>
                      {preview && <p role="status">{preview}</p>}
                    </div>
                  )}
                  <p className="obd-help">
                    A is the first data byte, B the second, through H. Example:
                    (A*256+B)/4. Arithmetic and bitwise &amp;, |, ^ are
                    supported.
                  </p>
                  <div className="obd-field-pair">
                    {field("Minimum", "min", "number", 12)}
                    {field("Maximum", "max", "number", 12)}
                  </div>
                  <div className="obd-field-pair">
                    <label className="obd-field">
                      Decimals
                      <select
                        aria-label="Decimals"
                        value={dialog.value.decimals}
                        onChange={(e) =>
                          setDialog((d) => ({
                            ...d,
                            value: {
                              ...d.value,
                              decimals: Number(e.target.value),
                            },
                          }))
                        }
                      >
                        {[0, 1, 2, 3].map((v) => (
                          <option key={v}>{v}</option>
                        ))}
                      </select>
                    </label>
                    {field("Poll interval (seconds)", "interval", "number", 2)}
                  </div>
                  <p className="obd-help">
                    Read-only requests. No ECU writes or code clearing. CAN
                    headers apply to CAN protocols only.
                  </p>
                </>
              )}
              {dialog.type === "widget" && (
                <>
                  <label className="obd-field">
                    Data source
                    <select
                      aria-label="Data source"
                      value={dialog.value.source}
                      onChange={(e) =>
                        setDialog((d) => ({
                          ...d,
                          value: { ...d.value, source: e.target.value },
                        }))
                      }
                    >
                      {sources(config).map((s) => (
                        <option key={s.source} value={s.source}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {field("Tile title (optional)", "title", "text", 40)}
                  <label className="obd-field">
                    Display
                    <select
                      aria-label="Display"
                      value={
                        dialog.value.source === "errors"
                          ? "value"
                          : dialog.value.view
                      }
                      disabled={dialog.value.source === "errors"}
                      onChange={(e) =>
                        setDialog((d) => ({
                          ...d,
                          value: { ...d.value, view: e.target.value },
                        }))
                      }
                    >
                      <option value="value">Block</option>
                      <option value="gauge">Gauge</option>
                      <option value="graph">Chart</option>
                    </select>
                  </label>
                  <label className="obd-field">
                    Tile size
                    <select
                      aria-label="Tile size"
                      value={
                        dialog.value.size ||
                        `${dialog.value.w}x${dialog.value.h}`
                      }
                      onChange={(e) =>
                        setDialog((d) => ({
                          ...d,
                          value: { ...d.value, size: e.target.value },
                        }))
                      }
                    >
                      <option value="1x1">Small · 1 × 1</option>
                      <option value="2x1">Wide · 2 × 1</option>
                      <option value="1x2">Tall · 1 × 2</option>
                      <option value="2x2">Large · 2 × 2</option>
                    </select>
                  </label>
                </>
              )}
              {dialog.type === "range" && (
                <>
                  {field("Tank capacity (litres)", "tankLitres", "number", 5)}
                  {[
                    ["Fuel level (%)", "fuelLevel"],
                    ["Fuel rate (L/h)", "fuelRate"],
                  ].map(([label, key]) => (
                    <label className="obd-field" key={key}>
                      {label}
                      <select
                        aria-label={label}
                        value={dialog.value[key] || ""}
                        onChange={(e) =>
                          setDialog((d) => ({
                            ...d,
                            value: {
                              ...d.value,
                              [key]: e.target.value || null,
                            },
                          }))
                        }
                      >
                        <option value="">Not configured</option>
                        {sources(config)
                          .filter(
                            (s) =>
                              s.source.startsWith("builtin:") ||
                              s.source.startsWith("custom:"),
                          )
                          .map((s) => (
                            <option key={s.source} value={s.source}>
                              {s.label} {s.unit && `[${s.unit}]`}
                            </option>
                          ))}
                      </select>
                    </label>
                  ))}
                  <p className="obd-help">
                    Range uses fuel level, tank capacity and average consumption
                    from valid speed/fuel-rate samples. At least 0.1 km of
                    continuous readings is needed. Update fuel inputs at least
                    every 10 seconds. These are estimates, not manufacturer
                    range predictions.
                  </p>
                </>
              )}
              <div className="obd-dialog-actions">
                {dialog.type === "sensor" &&
                  config.sensors.some((s) => s.id === dialog.value.id) && (
                    <button
                      type="button"
                      onClick={() => {
                        state.current.editorVersion =
                          (state.current.editorVersion || 0) + 1;
                        setDialog((d) => ({ ...d, type: "remove-sensor" }));
                        setKeyboard(null);
                        setPreview(null);
                      }}
                    >
                      Delete mapping
                    </button>
                  )}
                <button
                  type="button"
                  onClick={() => {
                    closeEditor();
                  }}
                >
                  Cancel
                </button>
                <button type="submit">
                  Save{" "}
                  {dialog.type === "sensor"
                    ? "mapping"
                    : dialog.type === "widget"
                      ? "tile"
                      : "inputs"}
                </button>
              </div>
            </form>
          )}
          <Keyboard
            editor={
              keyboard
                ? {
                    ...keyboard,
                    value:
                      keyboard.key === "sampleBytes"
                        ? sampleBytes
                        : dialog?.value[keyboard.key],
                  }
                : null
            }
            close={() => setKeyboard(null)}
          />
        </Dialog>
      )}
    </div>
  );
}
