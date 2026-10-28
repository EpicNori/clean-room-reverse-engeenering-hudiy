import {
  ORIGINAL_WIDGET_TYPES,
  ClockCardContent,
  NavigationCardContent,
  MusicCardContent,
  PhoneCardContent,
} from "./DashboardCards";
import React, {
  useState,
  useEffect,
  useRef,
  useLayoutEffect,
  useMemo,
} from "react";
import { Gauge } from "./Telemetry";
import {
  WIDGETS,
  SENSOR_DEFINITIONS,
  PRESETS,
  validateDashboard,
  addWidget,
  placeWidget,
  sensorReading,
  parseDashboardPack,
} from "./dashboardWidgets.mjs";
import "./dashboardStudio.css";

const Symbol = ({ name }) => (
  <span className="material-symbols-rounded" aria-hidden="true">
    {name}
  </span>
);
const timeText = (n) =>
  `${String(Math.floor((Number.isFinite(n) ? n : 0) / 60)).padStart(2, "0")}:${String(Math.floor((Number.isFinite(n) ? n : 0) % 60)).padStart(2, "0")}`;
const copy = (value) => JSON.parse(JSON.stringify(value));
function Trend({ telemetry, source, reading }) {
  const values =
    reading.value === null ? [] : (telemetry.history || []).slice(-60);
  const finite = values.map((v) => v[source]).filter(Number.isFinite),
    min = Math.min(...finite),
    range = Math.max(1, Math.max(...finite) - min);
  let path = "",
    joined = false;
  values.forEach((row, i) => {
    if (!Number.isFinite(row[source])) {
      joined = false;
      return;
    }
    path += `${joined ? "L" : "M"}${(i / Math.max(1, values.length - 1)) * 240},${85 - ((row[source] - min) / range) * 70} `;
    joined = true;
  });
  return (
    <svg
      viewBox="0 0 240 100"
      preserveAspectRatio="none"
      role="img"
      aria-label={
        finite.length
          ? `${SENSOR_DEFINITIONS[source].label} history`
          : "No vehicle samples yet"
      }
    >
      <path className="dash-chart-grid" d="M0 20H240M0 50H240M0 80H240" />
      {path && <path className="dash-chart-line" d={path} />}
    </svg>
  );
}
function WidgetContent({ widget, data, onGo, palette }) {
  const media = data.shownMedia || {},
    phone = data.phone || {},
    obd = data.obd || {},
    projection = data.projection || {},
    nav = data.navigation || {};
  switch (widget.type) {
    case "clock":
      return (
        <div className="dash-original-body clock-card">
          <ClockCardContent time={data.time} now={data.now} />
        </div>
      );
    case "navigation":
      return (
        <button
          className="dash-original-body navigation-card"
          aria-label="Navigation card"
          onClick={() => onGo("android-resume")}
        >
          <NavigationCardContent navigation={nav} />
        </button>
      );
    case "music":
      return (
        <div className="dash-original-body media-card">
          <MusicCardContent
            media={media}
            liveMedia={data.liveMedia}
            onOpen={() => onGo(media.source || "storage")}
            onPrevious={data.previous}
            onPlay={data.play}
            onNext={data.next}
          />
        </div>
      );
    case "phone":
      return (
        <div className="dash-original-body phone-card">
          <PhoneCardContent
            name={phone.name || data.phonebook?.name || ""}
            onGo={onGo}
          />
        </div>
      );
    case "connections":
      return (
        <div className="dash-connections">
          {[
            ["Phone", Boolean(phone.connected)],
            [
              "Android Auto",
              Boolean(projection.connected && projection.videoReady),
            ],
            ["OBD", Boolean(obd.connected)],
          ].map(([label, connected]) => (
            <div key={label}>
              <span>
                <i className={connected ? "connected" : ""} />
                {label}
              </span>
              <b>{connected ? "Connected" : "Disconnected"}</b>
            </div>
          ))}
        </div>
      );
    case "shortcuts":
      return (
        <div className="dash-shortcuts">
          {[
            ["custom-obd", "speed", "My OBD"],
            ["obd-logs", "description", "Logs"],
            ["settings", "settings", "Settings"],
          ].map(([id, icon, label]) => (
            <button key={id} onClick={() => onGo(id)}>
              <Symbol name={icon} />
              <span>{label}</span>
            </button>
          ))}
        </div>
      );
    case "diagnostics":
      return (
        <div className="dash-diagnostics">
          <strong>
            {!obd.connected
              ? "Vehicle disconnected"
              : obd.diagnostics?.timestamp
                ? `${obd.diagnostics.codes?.length || 0} trouble codes reported`
                : "Waiting for a diagnostic scan"}
          </strong>
          <p>
            {obd.error ||
              "View recorded diagnostic events and connection history."}
          </p>
          <button onClick={() => onGo("obd-logs")}>
            Open diagnostic logs
            <Symbol name="arrow_forward" />
          </button>
        </div>
      );
    case "sensor": {
      const definition = SENSOR_DEFINITIONS[widget.source],
        reading = sensorReading(obd, widget.source, data.now.getTime());
      return (
        <div className={`dash-sensor dash-sensor-${widget.display}`}>
          {["arc", "ticks"].includes(widget.display) ? (
            <div className="dash-gauge">
              <Gauge
                name={widget.source}
                value={reading.value}
                variant={widget.display === "ticks" ? 2 : 1}
                palette={palette}
                definition={{
                  ...definition,
                  label: widget.title || definition.label,
                }}
              />
            </div>
          ) : (
            <>
              <div className="dash-reading">
                <strong>
                  {reading.value === null
                    ? "—"
                    : reading.value.toFixed(definition.decimals)}
                </strong>
                <span>{definition.unit}</span>
              </div>
              {widget.display === "chart" && (
                <Trend
                  telemetry={obd}
                  source={widget.source}
                  reading={reading}
                />
              )}
            </>
          )}
          <small>{reading.reason}</small>
        </div>
      );
    }
    default:
      return null;
  }
}
function appearanceStyle(config, palette) {
  const a = config.appearance;
  return {
    "--dash-gap": a.gap + "px",
    "--dash-radius": a.radius + "px",
    "--dash-opacity": a.opacity / 100,
    "--dash-blur": a.blur + "px",
    "--dash-accent": a.accent === "theme" ? palette["--primary"] : a.accent,
  };
}
export function WidgetBoard({
  config,
  data,
  onGo,
  palette,
  editing = false,
  selected,
  onSelect,
  onMove,
  drag,
  setDrag,
}) {
  const grid = useRef(null),
    scroll = useRef(null),
    gesture = useRef(null),
    positions = useRef(new Map());
  const [metrics, setMetrics] = useState({ cols: 6, row: 150 });
  useEffect(() => {
    const node = scroll.current;
    const measure = () => {
      const cols = node.clientWidth < 620 ? 2 : 6,
        row =
          cols === 2
            ? Math.min(
                160,
                Math.max(
                  120,
                  (node.clientHeight - config.appearance.gap * 2) / 3,
                ),
              )
            : Math.max(
                112,
                (node.clientHeight - config.appearance.gap * 2) / 3,
              );
      setMetrics((old) =>
        old.cols === cols && old.row === row ? old : { cols, row },
      );
    };
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    measure();
    return () => observer.disconnect();
  }, [config.appearance.gap]);
  useEffect(() => {
    if (!editing || !selected || drag) return;
    const node = grid.current?.querySelector(`[data-widget-id="${selected}"]`);
    node?.scrollIntoView({
      block: "nearest",
      inline: "nearest",
      behavior: "auto",
    });
  }, [selected, editing]);
  useLayoutEffect(() => {
    const previous = positions.current,
      next = new Map();
    for (const node of grid.current.querySelectorAll("[data-widget-id]")) {
      const rect = node.getBoundingClientRect(),
        before = previous.get(node.dataset.widgetId);
      next.set(node.dataset.widgetId, rect);
      if (
        before &&
        config.appearance.motion &&
        !matchMedia("(prefers-reduced-motion: reduce)").matches &&
        (before.x !== rect.x || before.y !== rect.y)
      )
        node.animate(
          [
            {
              transform: `translate(${before.x - rect.x}px,${before.y - rect.y}px)`,
            },
            { transform: "none" },
          ],
          { duration: 180, easing: "cubic-bezier(.2,.8,.2,1)" },
        );
    }
    positions.current = next;
  }, [config.widgets, config.appearance.motion, metrics.cols]);
  const cellAt = (x, y) => {
    const rect = grid.current.getBoundingClientRect(),
      gap = config.appearance.gap;
    if (x < rect.left || x > rect.right || y < rect.top) return null;
    return {
      x: Math.min(5, Math.floor((x - rect.left) / ((rect.width + gap) / 6))),
      y: Math.floor((y - rect.top) / (metrics.row + gap)),
    };
  };
  const grip = (w) => ({
    "data-dashboard-drag-handle": "true",
    onPointerDown: (e) => {
      if (e.button !== 0 || !e.isPrimary || metrics.cols !== 6) return;
      e.preventDefault();
      e.stopPropagation();
      e.currentTarget.setPointerCapture(e.pointerId);
      gesture.current = {
        id: w.id,
        pointer: e.pointerId,
        x: e.clientX,
        y: e.clientY,
        moved: false,
      };
      onSelect(w.id);
    },
    onPointerMove: (e) => {
      const d = gesture.current;
      if (!d || d.pointer !== e.pointerId) return;
      e.preventDefault();
      e.stopPropagation();
      d.moved = d.moved || Math.hypot(e.clientX - d.x, e.clientY - d.y) > 8;
      if (d.moved) {
        const cell = cellAt(e.clientX, e.clientY);
        setDrag({
          id: d.id,
          cell,
          valid: cell
            ? Boolean(placeWidget(config.widgets, d.id, cell.x, cell.y))
            : false,
        });
        const rect = scroll.current.getBoundingClientRect();
        if (e.clientY > rect.bottom - 45) scroll.current.scrollTop += 12;
        else if (e.clientY < rect.top + 45) scroll.current.scrollTop -= 12;
      }
    },
    onPointerUp: (e) => {
      const d = gesture.current;
      if (!d) return;
      gesture.current = null;
      e.stopPropagation();
      const cell = cellAt(e.clientX, e.clientY);
      setDrag(null);
      if (e.currentTarget.hasPointerCapture(e.pointerId))
        e.currentTarget.releasePointerCapture(e.pointerId);
      if (d.moved && cell) onMove(d.id, cell.x, cell.y);
    },
    onPointerCancel: () => {
      gesture.current = null;
      setDrag(null);
    },
    onKeyDown: (e) => {
      const delta = {
        ArrowLeft: [-1, 0],
        ArrowRight: [1, 0],
        ArrowUp: [0, -1],
        ArrowDown: [0, 1],
      }[e.key];
      if (delta) {
        e.preventDefault();
        e.stopPropagation();
        onMove(w.id, w.x + delta[0], w.y + delta[1]);
      }
    },
  });
  const glass = config.appearance.surface === "glass";
  const effectivePalette = useMemo(
    () => ({
      ...palette,
      ...(glass ? { "--text": "#f6f3ff", "--active": "#3a364b" } : {}),
      "--primary":
        config.appearance.accent === "theme"
          ? palette["--primary"]
          : config.appearance.accent,
    }),
    [palette, glass, config.appearance.accent],
  );
  return (
    <div
      className={`dash-board dash-surface-${config.appearance.surface} dash-backdrop-${config.appearance.backdrop} ${config.appearance.motion ? "" : "dash-no-motion"}`}
      style={appearanceStyle(config, palette)}
    >
      <div className="dash-grid-scroll" ref={scroll}>
        <div
          ref={grid}
          className={`dash-widget-grid ${editing ? "is-editing" : ""} ${metrics.cols === 2 ? "is-compact" : ""}`}
          style={{
            "--dash-row": metrics.row + "px",
            "--dash-cols": metrics.cols,
          }}
          aria-label="Dashboard widgets"
        >
          {[...config.widgets]
            .sort((a, b) => a.y - b.y || a.x - b.x)
            .map((w) => (
              <article
                key={w.id}
                className={`dash-widget ${ORIGINAL_WIDGET_TYPES.includes(w.type) ? `dash-original-widget dash-original-${w.type}` : ""} ${selected === w.id && editing ? "is-selected" : ""} ${drag?.id === w.id ? "is-dragging" : ""}`}
                data-widget-id={w.id}
                data-layout-kind={editing ? undefined : "widget"}
                data-layout-id={w.id}
                tabIndex={0}
                aria-label={w.title || WIDGETS[w.type].label}
                style={{
                  gridColumn:
                    metrics.cols === 6
                      ? `${w.x + 1} / span ${w.w}`
                      : `span ${Math.min(2, w.w)}`,
                  gridRow:
                    metrics.cols === 6
                      ? `${w.y + 1} / span ${w.h}`
                      : `span ${Math.min(2, w.h)}`,
                }}
                onClickCapture={(e) => {
                  if (editing) {
                    e.preventDefault();
                    e.stopPropagation();
                    onSelect(w.id);
                  }
                }}
                onKeyDown={(e) => {
                  if (editing && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault();
                    onSelect(w.id);
                  }
                }}
              >
                {(editing ||
                  !ORIGINAL_WIDGET_TYPES.includes(w.type) ||
                  (w.title && w.title !== WIDGETS[w.type].label)) && (
                  <header
                    className={
                      ORIGINAL_WIDGET_TYPES.includes(w.type)
                        ? "dash-original-header"
                        : undefined
                    }
                  >
                    <span
                      className={
                        w.title && w.title !== WIDGETS[w.type].label
                          ? "dash-custom-title"
                          : undefined
                      }
                    >
                      <Symbol name={WIDGETS[w.type].icon} />
                      {w.title || WIDGETS[w.type].label}
                    </span>
                    {editing && (
                      <button
                        aria-label={`Drag ${w.title || WIDGETS[w.type].label}`}
                        title={
                          metrics.cols === 6
                            ? "Drag or use arrow keys"
                            : "Use the Move controls on compact screens"
                        }
                        {...grip(w)}
                      >
                        <Symbol name="drag_indicator" />
                      </button>
                    )}
                  </header>
                )}
                <div className="dash-widget-content">
                  <WidgetContent
                    widget={w}
                    data={data}
                    onGo={onGo}
                    palette={effectivePalette}
                  />
                </div>
              </article>
            ))}
          {editing && drag?.cell && metrics.cols === 6 && (
            <div
              className={`dash-drop-target ${drag.valid ? "" : "invalid"}`}
              style={{
                gridColumn: `${Math.min(6 - (config.widgets.find((w) => w.id === drag.id)?.w || 1), Math.max(0, drag.cell.x)) + 1} / span ${config.widgets.find((w) => w.id === drag.id)?.w || 1}`,
                gridRow: `${Math.min(8 - (config.widgets.find((w) => w.id === drag.id)?.h || 1), Math.max(0, drag.cell.y)) + 1} / span ${config.widgets.find((w) => w.id === drag.id)?.h || 1}`,
              }}
            />
          )}
          {!config.widgets.length && (
            <div className="dash-empty">
              <Symbol name="widgets" />
              <h2>Your dashboard, your way</h2>
              <p>Add a widget to start building your cockpit.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
export function DashboardView({ workspace, data, onGo, palette }) {
  return (
    <section
      className={`personal-dashboard ${workspace.config.appearance.surface === "glass" ? "dash-host-glass" : ""}`}
    >
      {data.obd?.mode === "simulator" && (
        <span className="dash-mode dash-mode-floating">Simulator</span>
      )}
      <button
        className="dashboard-customize-entry is-icon-only"
        aria-label="Customize dashboard"
        title="Customize dashboard"
        onClick={() => onGo("dashboard-editor")}
      >
        <Symbol name="tune" />
      </button>
      <WidgetBoard
        config={workspace.config}
        data={data}
        onGo={onGo}
        palette={palette}
      />
    </section>
  );
}
function Keyboard({ value, onChange, close }) {
  return (
    <div
      className="dash-keyboard"
      role="group"
      aria-label="Widget title keyboard"
    >
      <div>
        <strong>Widget title</strong>
        <button onClick={close}>Done typing</button>
      </div>
      <output>{value || "Empty"}</output>
      <div>
        {Array.from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789").map((c) => (
          <button
            key={c}
            onClick={() =>
              onChange(
                Array.from(value + c)
                  .slice(0, 48)
                  .join(""),
              )
            }
          >
            {c}
          </button>
        ))}
        <button onClick={() => onChange((value + " ").slice(0, 48))}>
          Space
        </button>
        <button onClick={() => onChange("")}>Clear</button>
        <button
          aria-label="Delete character"
          onClick={() => onChange(Array.from(value).slice(0, -1).join(""))}
        >
          <Symbol name="backspace" />
        </button>
      </div>
    </div>
  );
}
export function DashboardStudio({
  workspace,
  initialConfig,
  initialRevision,
  onBrowse,
  data,
  onGo,
  palette,
  onClose,
}) {
  const [draft, setDraft] = useState(() => copy(initialConfig)),
    [selected, setSelected] = useState(initialConfig.widgets[0]?.id || ""),
    [panel, setPanel] = useState("widgets"),
    [message, setMessage] = useState(""),
    [keyboard, setKeyboard] = useState(false),
    [libraryOpen, setLibraryOpen] = useState(false),
    [drag, setDrag] = useState(null);
  const [baseRevision, setBaseRevision] = useState(initialRevision);
  useEffect(() => {
    if (!baseRevision && workspace.ready) setBaseRevision(workspace.revision);
  }, [baseRevision, workspace.ready, workspace.revision]);
  const widget = draft.widgets.find((w) => w.id === selected);
  const appearance = (key, value) =>
    setDraft((d) => ({
      ...d,
      enabled: true,
      appearance: { ...d.appearance, [key]: value },
    }));
  const changeWidget = (patch) =>
    setDraft((d) => ({
      ...d,
      enabled: true,
      widgets: d.widgets.map((w) =>
        w.id === selected ? { ...w, ...patch } : w,
      ),
    }));
  const move = (id, x, y, size = {}) => {
    const result = placeWidget(draft.widgets, id, x, y, size);
    if (result) {
      setDraft((d) => ({ ...d, enabled: true, widgets: result }));
      setMessage("");
    } else
      setMessage(
        "That space is occupied or outside the grid. Move a widget first.",
      );
  };
  async function save() {
    try {
      validateDashboard(draft);
      if (await workspace.save(draft, baseRevision)) onClose();
    } catch (e) {
      setMessage(e.message);
    }
  }
  return (
    <section className="dashboard-studio" aria-label="Dashboard Studio">
      <header className="dash-studio-header">
        <div>
          <span className="dash-eyebrow">DASHBOARD STUDIO</span>
          <h1>Make it yours.</h1>
        </div>
        <div>
          <button onClick={onClose} disabled={workspace.busy}>
            Cancel
          </button>
          <button
            className="dash-primary"
            onClick={save}
            disabled={
              !workspace.ready || !workspace.available || workspace.busy
            }
          >
            {workspace.busy ? "Saving…" : "Save layout"}
            <Symbol name="check" />
          </button>
        </div>
      </header>
      <div className="dash-studio-body">
        <aside className="dash-inspector">
          <div className="dash-tabs">
            {[
              ["widgets", "Widgets"],
              ["appearance", "Appearance"],
            ].map(([id, label]) => (
              <button
                key={id}
                aria-pressed={panel === id}
                onClick={() => setPanel(id)}
              >
                {label}
              </button>
            ))}
          </div>
          {panel === "widgets" ? (
            <>
              <p className="dash-caption">
                Add a widget, then drag its grip or use the Move controls.
              </p>
              <button
                className="dash-add-widget"
                aria-expanded={libraryOpen}
                onClick={() => setLibraryOpen((v) => !v)}
              >
                <Symbol name="add" />
                Add widget
              </button>
              {libraryOpen && (
                <div className="dash-widget-library">
                  {Object.entries(WIDGETS).map(([type, meta]) => (
                    <button
                      key={type}
                      disabled={draft.widgets.length >= 16}
                      onClick={() => {
                        const next = addWidget(draft, type);
                        if (next) {
                          setDraft(next);
                          setSelected(next.widgets.at(-1).id);
                          setLibraryOpen(false);
                          setMessage("");
                        } else
                          setMessage(
                            "No space available. Move or remove a widget first.",
                          );
                      }}
                    >
                      <Symbol name={meta.icon} />
                      {meta.label}
                    </button>
                  ))}
                </div>
              )}
              <div className="dash-inspector-divider" />
              {widget ? (
                <section
                  className="dash-widget-properties"
                  aria-label="Selected widget settings"
                >
                  <h2>Selected widget</h2>
                  <label>
                    Title
                    <input
                      value={widget.title}
                      maxLength={48}
                      onChange={(e) => changeWidget({ title: e.target.value })}
                    />
                  </label>
                  <button onClick={() => setKeyboard((v) => !v)}>
                    <Symbol name="keyboard" />
                    On-screen keyboard
                  </button>
                  {widget.type === "sensor" && (
                    <>
                      <label>
                        Vehicle data
                        <select
                          value={widget.source}
                          onChange={(e) =>
                            changeWidget({ source: e.target.value })
                          }
                        >
                          {Object.entries(SENSOR_DEFINITIONS).map(
                            ([id, meta]) => (
                              <option key={id} value={id}>
                                {meta.label}
                              </option>
                            ),
                          )}
                        </select>
                      </label>
                      <label>
                        Display
                        <select
                          value={widget.display}
                          onChange={(e) =>
                            changeWidget({ display: e.target.value })
                          }
                        >
                          <option value="block">Block</option>
                          <option value="arc">Original arc gauge</option>
                          <option value="ticks">Original tick gauge</option>
                          <option value="chart">Chart</option>
                        </select>
                      </label>
                    </>
                  )}
                  <label>
                    Swap position
                    <select
                      aria-label="Swap widget position"
                      value=""
                      onChange={(e) => {
                        const target = draft.widgets.find(
                          (w) => w.id === e.target.value,
                        );
                        if (target) move(widget.id, target.x, target.y);
                      }}
                    >
                      <option value="">Choose another widget</option>
                      {draft.widgets
                        .filter(
                          (w) =>
                            w.id !== widget.id &&
                            w.w === widget.w &&
                            w.h === widget.h &&
                            placeWidget(draft.widgets, widget.id, w.x, w.y),
                        )
                        .map((w) => (
                          <option key={w.id} value={w.id}>
                            {w.title || WIDGETS[w.type].label}
                          </option>
                        ))}
                    </select>
                  </label>
                  <span className="dash-field-label">Move</span>
                  <div className="dash-moves">
                    {[
                      ["arrow_back", -1, 0, "left"],
                      ["arrow_forward", 1, 0, "right"],
                      ["arrow_upward", 0, -1, "up"],
                      ["arrow_downward", 0, 1, "down"],
                    ].map(([icon, dx, dy, label]) => (
                      <button
                        key={label}
                        aria-label={`Move widget ${label}`}
                        disabled={
                          !placeWidget(
                            draft.widgets,
                            widget.id,
                            widget.x + dx,
                            widget.y + dy,
                          )
                        }
                        onClick={() =>
                          move(widget.id, widget.x + dx, widget.y + dy)
                        }
                      >
                        <Symbol name={icon} />
                      </button>
                    ))}
                  </div>
                  <label>
                    Width · {widget.w} of 6 columns
                    <input
                      type="range"
                      min="1"
                      max="6"
                      step="1"
                      value={widget.w}
                      onChange={(e) =>
                        move(widget.id, widget.x, widget.y, {
                          w: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                  <label>
                    Height · {widget.h} rows
                    <input
                      type="range"
                      min="1"
                      max="4"
                      step="1"
                      value={widget.h}
                      onChange={(e) =>
                        move(widget.id, widget.x, widget.y, {
                          h: Number(e.target.value),
                        })
                      }
                    />
                  </label>
                  <button
                    className="dash-remove"
                    onClick={() => {
                      setDraft((d) => ({
                        ...d,
                        enabled: true,
                        widgets: d.widgets.filter((w) => w.id !== selected),
                      }));
                      setSelected("");
                      setKeyboard(false);
                    }}
                  >
                    <Symbol name="delete" />
                    Remove widget
                  </button>
                </section>
              ) : (
                <p className="dash-caption">
                  Select a widget in the preview to configure it.
                </p>
              )}
            </>
          ) : (
            <section
              className="dash-appearance"
              aria-label="Dashboard appearance"
            >
              <h2>Surface</h2>
              <div className="dash-surface-options">
                {["classic", "glass"].map((v) => (
                  <button
                    key={v}
                    aria-pressed={draft.appearance.surface === v}
                    onClick={() => appearance("surface", v)}
                  >
                    {v === "classic" ? "Classic" : "Glass"}
                  </button>
                ))}
              </div>
              <label>
                Backdrop
                <select
                  value={draft.appearance.backdrop}
                  onChange={(e) => appearance("backdrop", e.target.value)}
                >
                  {["aurora", "midnight", "sunrise", "graphite"].map((v) => (
                    <option key={v} value={v}>
                      {v[0].toUpperCase() + v.slice(1)}
                    </option>
                  ))}
                </select>
              </label>
              <span className="dash-field-label">Accent</span>
              <div className="dash-swatches">
                {[
                  "theme",
                  "#b9a0ff",
                  "#7ed8ee",
                  "#f3adbc",
                  "#a8dda0",
                  "#eebc75",
                ].map((color) => (
                  <button
                    key={color}
                    aria-label={
                      color === "theme"
                        ? "Use current theme accent"
                        : `Dashboard accent ${color}`
                    }
                    aria-pressed={draft.appearance.accent === color}
                    style={{
                      "--swatch":
                        color === "theme" ? palette["--primary"] : color,
                    }}
                    onClick={() => appearance("accent", color)}
                  >
                    {color === "theme" ? (
                      <Symbol name="palette" />
                    ) : draft.appearance.accent === color ? (
                      <Symbol name="check" />
                    ) : null}
                  </button>
                ))}
              </div>
              {[
                ["opacity", "Panel opacity", 55, 100, "%"],
                ["blur", "Background blur", 0, 24, "px"],
                ["radius", "Corner rounding", 0, 36, "px"],
                ["gap", "Widget spacing", 4, 24, "px"],
              ].map(([key, label, min, max, unit]) => (
                <label key={key}>
                  {label} · {draft.appearance[key]}
                  {unit}
                  <input
                    type="range"
                    min={min}
                    max={max}
                    value={draft.appearance[key]}
                    onChange={(e) => appearance(key, Number(e.target.value))}
                  />
                </label>
              ))}
              <button
                role="switch"
                aria-checked={draft.appearance.motion}
                onClick={() => appearance("motion", !draft.appearance.motion)}
              >
                <Symbol name="animation" />
                Motion {draft.appearance.motion ? "on" : "off"}
              </button>
              <p className="dash-caption">
                Glass affects the dashboard. Reduce blur or choose Classic for a
                simpler surface.
              </p>
            </section>
          )}
        </aside>
        <div className="dash-preview">
          <div className="dash-preview-heading">
            <span>LIVE PREVIEW</span>
            <span>
              {draft.widgets.length}/16 widgets · {workspace.storage}
            </span>
          </div>
          {!draft.enabled && (
            <p className="dash-inline-note">
              Saving this layout restores the original dashboard.
            </p>
          )}
          <WidgetBoard
            config={draft}
            data={data}
            onGo={onGo}
            palette={palette}
            editing
            selected={selected}
            onSelect={setSelected}
            onMove={move}
            drag={drag}
            setDrag={setDrag}
          />
          <footer>
            {message || workspace.error ? (
              <p role="alert">{message || workspace.error}</p>
            ) : (
              <p>Changes stay in preview until you save.</p>
            )}
            <button
              disabled={workspace.busy}
              onClick={() => onBrowse(draft, baseRevision)}
            >
              Explore layouts
              <Symbol name="arrow_forward" />
            </button>
          </footer>
        </div>
      </div>
      {keyboard && widget && (
        <Keyboard
          value={widget.title}
          onChange={(value) => changeWidget({ title: value })}
          close={() => setKeyboard(false)}
        />
      )}
    </section>
  );
}
export function LayoutExtensions({ workspace, onPreview, onClose }) {
  const input = useRef(null);
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  async function importFile(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      if (file.size > 16384)
        throw Error("Layout files must be 16 KiB or smaller");
      const pack = parseDashboardPack(await file.text());
      onPreview(pack.config);
    } catch (e) {
      setMessage(e.message);
    }
  }
  async function exportFile() {
    setBusy(true);
    try {
      setMessage(await workspace.exportLayout());
    } catch (e) {
      setMessage(e.message || "Could not export layout");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="dashboard-extensions" aria-label="Dashboard extensions">
      <header className="dash-studio-header">
        <div>
          <span className="dash-eyebrow">EXTENSIONS / LAYOUTS</span>
          <h1>A different kind of cockpit.</h1>
        </div>
        <button onClick={onClose}>Back</button>
      </header>
      <p className="dash-extension-intro">
        Start with a layout, make it your own, then share it. Preview every
        change before saving.
      </p>
      <div className="dash-pack-actions">
        <button onClick={() => input.current.click()}>
          <Symbol name="upload_file" />
          Import layout
        </button>
        <button
          disabled={busy || workspace.busy || !workspace.ready}
          onClick={exportFile}
        >
          <Symbol name="download" />
          {busy ? "Exporting…" : "Export saved layout"}
        </button>
        <input
          ref={input}
          type="file"
          accept=".json,application/json"
          onChange={importFile}
          hidden
        />
      </div>
      {message && (
        <p role="status" className="dash-inline-note">
          {message}
        </p>
      )}
      <div className="dash-pack-grid">
        {PRESETS.map((p) => (
          <article key={p.id} className="dash-pack">
            <div
              className={`dash-pack-preview dash-pack-${p.id}`}
              aria-hidden="true"
            >
              {p.config.widgets
                .filter(
                  (w) =>
                    p.id !== "original" ||
                    ["clock", "navigation", "music", "phone"].includes(w.type),
                )
                .map((w) => (
                  <i
                    key={w.id}
                    style={{
                      gridColumn: `${w.x + 1}/span ${w.w}`,
                      gridRow: `${w.y + 1}/span ${w.h}`,
                    }}
                  >
                    <Symbol name={WIDGETS[w.type].icon} />
                  </i>
                ))}
            </div>
            <div>
              <span className="dash-eyebrow">BUNDLED LAYOUT</span>
              <h2>{p.name}</h2>
              <p>{p.description}</p>
              <button onClick={() => onPreview(copy(p.config))}>
                Preview layout
                <Symbol name="arrow_forward" />
              </button>
            </div>
          </article>
        ))}
      </div>
      <div className="dash-community-note">
        <Symbol name="extension" />
        <div>
          <h2>Built to be shared</h2>
          <p>
            Layout files contain widget positions and appearance settings.
            Community downloads are planned; this version supports bundled
            layouts and importing a shared JSON file.
          </p>
        </div>
      </div>
    </section>
  );
}
