import React, { useEffect, useRef, useState } from "react";
import "./obdLogs.css";

const Icon = ({ name }) => (
  <span className="material-symbols-rounded" aria-hidden="true">
    {name}
  </span>
);
const size = (n) =>
  Number.isFinite(n)
    ? n < 1024 * 1024
      ? `${(n / 1024).toFixed(1)} KB`
      : `${(n / 1024 / 1024).toFixed(1)} MB`
    : "—";
const date = (n) =>
  Number.isFinite(n) ? new Date(n * 1000).toLocaleString() : "Unknown time";
const duration = (n) =>
  `${Math.floor(n / 3600) ? Math.floor(n / 3600) + ":" : ""}${String(Math.floor(n / 60) % 60).padStart(2, "0")}:${String(Math.floor(n) % 60).padStart(2, "0")}`;

async function request(path = "/api/obd-logs", data) {
  const controller = new AbortController(),
    timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(path, {
      signal: controller.signal,
      ...(data
        ? {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
          }
        : {}),
    });
    const body = await response.json();
    if (!response.ok)
      throw Error(body.error || "Diagnostic logging is unavailable");
    return body;
  } finally {
    clearTimeout(timer);
  }
}

const captureFields = [
  ["rawReplies", "Raw adapter requests and replies"],
  ["samples", "Dashboard and derived samples"],
  ["customSensors", "Read every configured custom mapping"],
  ["liveData", "Expanded live PID scan · Mode 01"],
  ["freezeFrame", "Freeze frame 0 · Mode 02"],
  ["monitorTests", "CAN monitor results · Mode 06"],
  ["vehicleInfo", "Vehicle information · Mode 09"],
  ["faultCodes", "Fault codes · standard and discovered CAN ECUs"],
];
const numberFields = [
  [
    "scanIntervalSeconds",
    "Extra scan interval (seconds)",
    1,
    30,
    [1, 2, 5, 10, 15, 30],
  ],
  [
    "sampleIntervalSeconds",
    "Save dashboard sample every (seconds)",
    1,
    60,
    [1, 2, 5, 10, 15, 30, 60],
  ],
  [
    "diagnosticIntervalSeconds",
    "Fault-code refresh (seconds)",
    10,
    300,
    [10, 15, 30, 60, 120, 300],
  ],
  [
    "snapshotIntervalSeconds",
    "Freeze frame / monitor / information refresh (seconds)",
    10,
    600,
    [10, 30, 60, 120, 300, 600],
  ],
  ["maxSessionMiB", "Maximum session size (MiB)", 1, 64, [1, 4, 8, 16, 32, 64]],
  [
    "maxTotalMiB",
    "Total log storage (MiB)",
    16,
    1024,
    [16, 32, 64, 128, 256, 512, 1024],
  ],
  ["maxSessions", "Maximum saved sessions", 1, 100, [1, 5, 10, 20, 50, 100]],
];

function LogSettings({ value, busy, onSave, active }) {
  const [draft, setDraft] = useState(value),
    [dirty, setDirty] = useState(false);
  useEffect(() => {
    if (!dirty) setDraft(value);
  }, [JSON.stringify(value), dirty]);
  const set = (key, next) => {
    setDraft((d) => ({ ...d, [key]: next }));
    setDirty(true);
  };
  if (!draft) return null;
  return (
    <details className="obd-log-settings">
      <summary>Recording settings · data, intervals and storage</summary>
      <p className="obd-log-hint">
        {active
          ? "The current recording keeps its original capture settings. Changes apply to the next session."
          : "Choose what the next recording captures."}{" "}
        Raw exchanges and dashboard samples can include readings already
        requested by your dashboard, independently of the expanded scan choices.
      </p>
      <div className="obd-log-setting-checks">
        {captureFields.map(([key, label]) => (
          <label key={key}>
            <input
              type="checkbox"
              checked={draft[key]}
              disabled={busy}
              onChange={(e) => set(key, e.target.checked)}
            />
            <span>{label}</span>
          </label>
        ))}
      </div>
      <div className="obd-log-setting-numbers">
        {numberFields.map(([key, label, min, max, presets]) => (
          <label key={key}>
            <span>{label}</span>
            <div>
              <button
                type="button"
                aria-label={`Decrease ${label}`}
                disabled={busy || draft[key] <= min}
                onClick={() => set(key, draft[key] - 1)}
              >
                −
              </button>
              <select
                aria-label={label}
                value={draft[key]}
                disabled={busy}
                onChange={(e) => set(key, Number(e.target.value))}
              >
                {[...new Set([...presets, draft[key]])]
                  .sort((a, b) => a - b)
                  .map((number) => (
                    <option key={number}>{number}</option>
                  ))}
              </select>
              <button
                type="button"
                aria-label={`Increase ${label}`}
                disabled={busy || draft[key] >= max}
                onClick={() => set(key, draft[key] + 1)}
              >
                +
              </button>
            </div>
          </label>
        ))}
      </div>
      <div className="obd-log-actions">
        <button
          disabled={!dirty || busy}
          onClick={() => {
            setDraft(value);
            setDirty(false);
          }}
        >
          Discard changes
        </button>
        <button
          disabled={!dirty || busy}
          onClick={async () => {
            if (await onSave({ ...draft, autoRecord: value.autoRecord }))
              setDirty(false);
          }}
        >
          Save recording settings
        </button>
      </div>
      {dirty && (
        <p className="obd-log-hint" role="status">
          Unsaved recording settings
        </p>
      )}
    </details>
  );
}

export function OBDLogs({ telemetry, onSettings, onDashboard, demo = false }) {
  const [state, setState] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [preview, setPreview] = useState(null),
    [remove, setRemove] = useState(null),
    [tick, setTick] = useState(Date.now());
  const alive = useRef(true),
    pending = useRef(false),
    version = useRef(0),
    mutating = useRef(false),
    dialog = useRef(null),
    opener = useRef(null);
  async function refresh() {
    if (pending.current || mutating.current) return;
    pending.current = true;
    const requestVersion = version.current;
    try {
      const next = await request();
      if (
        alive.current &&
        !mutating.current &&
        requestVersion === version.current
      ) {
        setState(next);
        setError("");
      }
    } catch (e) {
      if (alive.current)
        setError(
          e.name === "AbortError"
            ? "Logging service did not respond"
            : e.message,
        );
    } finally {
      pending.current = false;
    }
  }
  useEffect(() => {
    alive.current = true;
    refresh();
    const timer = setInterval(() => {
      setTick(Date.now());
      refresh();
    }, 2000);
    return () => {
      alive.current = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    if (remove) {
      opener.current = document.activeElement;
      dialog.current?.querySelector("button")?.focus();
    } else if (opener.current?.isConnected) {
      opener.current.focus();
      opener.current = null;
    }
  }, [remove]);
  async function run(data) {
    if (mutating.current) return;
    mutating.current = true;
    version.current += 1;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const next = await request("/api/obd-logs", data);
      if (alive.current) {
        if (data.action === "export")
          setNotice(`Saved ${next.filename} to ${next.directory}`);
        else {
          setState(next);
          if (data.action === "settings")
            setNotice(
              "Recording settings saved. Capture changes apply to the next session.",
            );
        }
        if (data.action === "remove") {
          setRemove(null);
          if (preview?.id === data.id) setPreview(null);
        }
      }
      return true;
    } catch (e) {
      if (alive.current)
        setError(
          e.name === "AbortError"
            ? "Request timed out. Check the recording status before retrying."
            : e.message,
        );
      return false;
    } finally {
      mutating.current = false;
      if (alive.current) setBusy(false);
    }
  }
  async function showPreview(identifier) {
    setError("");
    try {
      const result = await request(`/api/obd-logs/${identifier}/preview`);
      if (alive.current) setPreview(result);
    } catch (e) {
      if (alive.current) setError(e.message);
    }
  }
  const active = state?.active,
    elapsed = active ? Math.max(0, tick / 1000 - active.startedAt) : 0;
  const supported = state?.coverage?.supported || {};
  return (
    <div className="obd-logs">
      <header className="obd-log-header">
        <div>
          <h1>OBD Logs</h1>
          <p>
            {telemetry?.mode === "simulator"
              ? "SIMULATOR · test readings"
              : telemetry?.connected
                ? "ELM327 connected"
                : "OBD disconnected"}
          </p>
        </div>
        <div className="obd-log-actions">
          <button onClick={onDashboard}>
            <Icon name="dashboard_customize" />
            My OBD
          </button>
          <button onClick={onSettings} aria-label="OBD connection settings">
            <Icon name="settings" />
          </button>
        </div>
      </header>
      {(error || state?.error) && (
        <p className="obd-log-error" role="alert">
          {error || state.error}
        </p>
      )}
      {notice && (
        <p className="obd-log-notice" role="status">
          {notice}
        </p>
      )}
      <section className="obd-log-recorder" aria-label="Diagnostic recorder">
        <div className="obd-log-recorder-head">
          <div>
            <h2>
              <span
                className={`obd-record-indicator ${active ? "is-recording" : ""}`}
                aria-hidden="true"
              />
              {state?.finishing
                ? "Finishing recording…"
                : active
                  ? "Recording diagnostics"
                  : "Diagnostic recording"}
            </h2>
            <p>
              {active
                ? telemetry?.connected
                  ? "Recording continues when you leave this page."
                  : "Waiting for the adapter; connection errors and reconnects are recorded."
                : "Record the full available diagnostic stream, independently of your visible dashboard."}
            </p>
          </div>
          <div className="obd-log-actions">
            {active ? (
              <button
                className="obd-log-primary"
                disabled={busy || state.finishing}
                onClick={() => run({ action: "stop" })}
              >
                <Icon name="stop_circle" />
                Stop & save
              </button>
            ) : (
              <button
                className="obd-log-primary"
                disabled={busy || !state || state.finishing}
                onClick={() => run({ action: "start" })}
              >
                <Icon name="fiber_manual_record" />
                Start recording
              </button>
            )}
          </div>
        </div>
        <div className="obd-log-metrics" aria-live="off">
          <div>
            <span>Duration</span>
            <strong>{active ? duration(elapsed) : "00:00"}</strong>
          </div>
          <div>
            <span>Events</span>
            <strong>{active?.events ?? 0}</strong>
          </div>
          <div>
            <span>Session size</span>
            <strong>{size(active?.bytes ?? 0)}</strong>
          </div>
          <div>
            <span>Discovered PIDs</span>
            <strong>
              {Object.values(supported).reduce((n, list) => n + list.length, 0)}
            </strong>
          </div>
        </div>
        <label className="obd-log-auto">
          <span>
            <strong>Record on OBD connection</strong>
            <small>
              Start a new session automatically when the adapter connects. Saved
              on this device.
            </small>
          </span>
          <input
            type="checkbox"
            role="switch"
            aria-label="Record automatically on OBD connection"
            checked={state?.autoRecord || false}
            disabled={!state || busy}
            onChange={(e) =>
              run({ action: "settings", autoRecord: e.target.checked })
            }
          />
        </label>
        {state?.settings && (
          <LogSettings
            value={state.settings}
            busy={busy}
            active={Boolean(active)}
            onSave={(settings) => run({ action: "settings", settings })}
          />
        )}
        {demo && (
          <p className="obd-log-hint">
            Dashboard Demo values are not recorded. Logging uses only the actual
            adapter or explicitly labelled simulator.
          </p>
        )}
        <details className="obd-log-coverage">
          <summary>
            Capture coverage{" "}
            {active &&
              (state.coverage?.discovering
                ? "· discovering…"
                : "· scan scheduled")}
          </summary>
          <p>
            All ECU-advertised live PIDs, freeze frame 0, CAN monitor data,
            vehicle information, stored/pending/permanent fault codes, read-only
            UDS fault status and available fault details from discovered CAN ECUs, all
            configured custom sensors, session estimates and raw adapter
            replies. Unsupported or undecoded data stays marked or raw.
          </p>
          <p>
            Reads share one adapter and are paced. More supported PIDs mean a
            longer sweep; each reading keeps its own acquisition time. Discovery
            requires no car model. Proprietary live signals still need definitions;
            a generic OBD connection cannot expose every vehicle module.
          </p>
          <p>
            First sweep: {state?.coverage?.queriedReadings ?? 0} / {state?.coverage?.scheduledReadings ?? 0} readings queried
            {state?.coverage?.firstSweepComplete ? " · finished" : " · incomplete"}.
            {" "}{state?.coverage?.ecuHeaders?.length ?? 0} CAN ECUs discovered.
          </p>
          {state?.coverage?.limitations?.map((message) => <p key={message}>{message}</p>)}
          {Object.entries(supported).map(([mode, pids]) => (
            <p key={mode}>
              <strong>Mode {mode}</strong> · {pids.length} PIDs{" "}
              <span className="obd-log-pids">
                {pids.join(" · ") || "None advertised"}
              </span>
            </p>
          ))}
          {Object.entries(state?.coverage?.unavailable || {}).map(
            ([command, message]) => (
              <p key={command}>
                <strong>{command}</strong> · {message}
              </p>
            ),
          )}
        </details>
        <p className="obd-log-hint">
          {size(state?.limits?.sessionBytes ?? 33554432)} per session ·{" "}
          {state?.limits?.sessions ?? 20} saved sessions ·{" "}
          {size(state?.limits?.totalBytes ?? 268435456)} total. Recording stops
          visibly at the limit; saved logs are never automatically erased.
        </p>
        {active && (
          <button disabled={busy || state?.finishing} onClick={() => run({ action: "mark" })}>
            <Icon name="flag" />
            Mark fault / power loss
          </button>
        )}
        {active && (
          <button onClick={() => showPreview(active.id)}>
            <Icon name="visibility" />
            View recent events
          </button>
        )}
      </section>
      <section
        className="obd-log-sessions"
        aria-label="Saved diagnostic sessions"
      >
        <div className="obd-log-section-header">
          <h2>Saved sessions</h2>
          <button onClick={refresh} disabled={busy}>
            <Icon name="refresh" />
            Refresh
          </button>
        </div>
        {!state ? (
          <p>Loading recordings…</p>
        ) : !state.sessions?.length ? (
          <div className="obd-log-empty">
            <Icon name="description" />
            <h3>No recordings yet</h3>
            <p>
              Start a recording before reproducing the vehicle problem, then
              stop and export the session.
            </p>
          </div>
        ) : (
          state.sessions.map((session) => (
            <article
              className="obd-log-session"
              key={session.id}
              aria-label={`Recording ${session.id}`}
            >
              <div>
                <h3>{date(session.startedAt)}</h3>
                <p>
                  <strong>
                    {session.state === "recording"
                      ? "Recording"
                      : session.state === "complete"
                        ? "Saved"
                        : "Interrupted"}
                  </strong>{" "}
                  ·{" "}
                  {session.mode === "simulator"
                    ? "SIMULATOR"
                    : session.mode === "live"
                      ? "Vehicle"
                      : "Waiting for adapter"}{" "}
                  · {size(session.bytes)} · {session.events ?? "Unknown"} events
                </p>
                <small>{session.reason || session.id}</small>
                {session.captureSummary && (
                  <p>
                    {!session.captureSummary.hasVehicleData
                      ? "No usable vehicle responses recorded"
                      : `${session.captureSummary.queriedReadings} / ${session.captureSummary.scheduledReadings} readings queried · ${session.captureSummary.firstSweepComplete ? "first sweep finished" : "partial capture"} · ${session.captureSummary.unavailableReadings} unavailable`}
                  </p>
                )}
              </div>
              <div className="obd-log-actions">
                <button
                  onClick={() => showPreview(session.id)}
                  aria-label={`View recording ${session.id}`}
                >
                  <Icon name="visibility" />
                  View
                </button>
                {session.state !== "recording" && (
                  <>
                    <button
                      disabled={busy}
                      onClick={() =>
                        run({ action: "export", id: session.id, format: "csv" })
                      }
                      aria-label={`Export CSV ${session.id}`}
                    >
                      Export CSV
                    </button>
                    <button
                      disabled={busy}
                      onClick={() =>
                        run({
                          action: "export",
                          id: session.id,
                          format: "jsonl",
                        })
                      }
                      aria-label={`Export JSONL ${session.id}`}
                    >
                      Export JSONL
                    </button>
                    <a
                      href={`/api/obd-logs/${session.id}/jsonl`}
                      download={`obd-${session.id}.jsonl`}
                    >
                      Download JSONL
                    </a>
                    <button
                      disabled={busy}
                      onClick={() => setRemove(session.id)}
                      aria-label={`Remove recording ${session.id}`}
                    >
                      <Icon name="delete_outline" />
                    </button>
                  </>
                )}
              </div>
            </article>
          ))
        )}
      </section>
      {preview && (
        <section
          className="obd-log-preview"
          aria-label="Recent diagnostic events"
        >
          <div className="obd-log-section-header">
            <h2>Recent events · last {preview.events.length}</h2>
            <div className="obd-log-actions">
              <button onClick={() => showPreview(preview.id)}>
                Refresh events
              </button>
              <button
                onClick={() => setPreview(null)}
                aria-label="Close recent events"
              >
                <Icon name="close" />
              </button>
            </div>
          </div>
          <p className="obd-log-hint">
            Full data is retained in JSONL. CSV includes raw responses and
            structured event data.
          </p>
          {preview.events.map((event, index) => (
            <details key={index}>
              <summary>
                {new Date(event.timestamp * 1000).toLocaleTimeString()} ·{" "}
                {event.type}
                {event.data?.command && ` · ${event.data.command}`}
                {event.data?.error && ` · ${event.data.error}`}
              </summary>
              <pre>{JSON.stringify(event.data, null, 2)}</pre>
            </details>
          ))}
        </section>
      )}
      {remove && (
        <div className="obd-log-dialog-backdrop">
          <section
            ref={dialog}
            className="obd-log-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Remove saved recording"
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === "Escape" && !busy) setRemove(null);
              if (e.key === "Tab") {
                const buttons = [
                  ...dialog.current.querySelectorAll("button:not(:disabled)"),
                ];
                if (e.shiftKey && document.activeElement === buttons[0]) {
                  e.preventDefault();
                  buttons.at(-1)?.focus();
                } else if (
                  !e.shiftKey &&
                  document.activeElement === buttons.at(-1)
                ) {
                  e.preventDefault();
                  buttons[0]?.focus();
                }
              }
            }}
          >
            <h2>Remove saved recording?</h2>
            <p>
              This permanently removes this diagnostic session from the device.
              Export it first if you need it. Existing exported copies remain
              available.
            </p>
            {error && <p role="alert">{error}</p>}
            <div className="obd-log-actions">
              <button disabled={busy} onClick={() => setRemove(null)}>
                Keep recording
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  run({ action: "remove", id: remove, confirmed: true })
                }
              >
                Remove recording
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
