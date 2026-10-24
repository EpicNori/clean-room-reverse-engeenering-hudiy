import React, { useEffect, useRef, useState } from "react";
import "./softwareUpdates.css";
const Icon = ({ name }) => (
  <span className="material-symbols-rounded" aria-hidden="true">
    {name}
  </span>
);
const short = (value) => (value ? value.slice(0, 10) : "Unavailable");
const phases = {
  idle: "Ready",
  checking: "Checking GitHub",
  available: "Update available",
  current: "Up to date",
  downloading: "Downloading",
  building: "Building update",
  testing: "Running checks",
  ready: "Ready to install",
  activating: "Restarting application",
  verifying: "Verifying startup",
  failed: "Update stopped",
  cancelled: "Cancelled",
  "rolled-back": "Previous version restored",
};
async function request(data) {
  const controller = new AbortController(),
    timer = setTimeout(() => controller.abort(), 6000);
  try {
    const response = await fetch("/api/software-update", {
      signal: controller.signal,
      ...(data
        ? {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
          }
        : {}),
    });
    const result = await response.json();
    if (!response.ok)
      throw Error(result.error || "Software-update service unavailable");
    return result;
  } finally {
    clearTimeout(timer);
  }
}

export function SoftwareUpdates() {
  const [state, setState] = useState(null),
    [draft, setDraft] = useState(null),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [confirm, setConfirm] = useState(null);
  const alive = useRef(true),
    polling = useRef(false),
    version = useRef(0),
    editing = useRef(false),
    working = useRef(false),
    dialog = useRef(null),
    opener = useRef(null),
    restart = useRef(false);
  editing.current = dirty;
  useEffect(() => {
    alive.current = true;
    async function poll() {
      if (polling.current || working.current) return;
      polling.current = true;
      const at = version.current;
      try {
        const result = await request();
        if (alive.current && at === version.current) {
          setState(result);
          if (!editing.current) setDraft(result.settings);
          if (restart.current) {
            restart.current = false;
            setNotice("Application reconnected.");
          }
          setError("");
        }
      } catch (e) {
        if (alive.current && !restart.current)
          setError("Could not read software-update status.");
      } finally {
        polling.current = false;
      }
    }
    poll();
    const timer = setInterval(poll, 2000);
    return () => {
      alive.current = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    if (confirm) {
      opener.current = document.activeElement;
      dialog.current?.querySelector("button")?.focus();
    } else if (opener.current?.isConnected) {
      opener.current.focus();
      opener.current = null;
    }
  }, [confirm]);
  async function run(action, extra = {}) {
    if (working.current) return;
    working.current = true;
    version.current += 1;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await request({ action, ...extra });
      if (alive.current) {
        if (action === "install" || action === "rollback") {
          restart.current = true;
          setNotice(
            "Application restart requested. This page will reconnect when startup checks finish.",
          );
          setConfirm(null);
        } else {
          setState(result);
          if (action === "settings") {
            setDraft(result.settings);
            setDirty(false);
            setNotice("Software-update settings saved.");
          }
        }
      }
      return true;
    } catch (e) {
      if (alive.current)
        setError(
          e.name === "AbortError"
            ? "Request timed out. Check the status before retrying."
            : e.message,
        );
      return false;
    } finally {
      working.current = false;
      if (alive.current) setBusy(false);
    }
  }
  const change = (key, value) => {
    setDraft((d) => ({ ...d, [key]: value }));
    setDirty(true);
  };
  const active = busy || state?.busy || state?.pendingRestart,
    available = state?.available,
    updatable =
      state?.latestRevision && state.latestRevision !== state.installedRevision;
  const checked = state?.checkedAt
    ? new Date(state.checkedAt * 1000).toLocaleString()
    : "Not checked yet";
  return (
    <div className="software-updates">
      <header>
        <div>
          <h1>Software updates</h1>
          <p>Hudiy · GitHub OTA</p>
        </div>
        <span className="software-version">
          {short(state?.installedRevision)}
        </span>
      </header>
      {error && (
        <p className="software-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="software-notice" role="status">
          {notice}
        </p>
      )}
      <section className="software-status" aria-label="Software-update status">
        <div className={`software-status-icon ${state?.busy ? "is-busy" : ""}`}>
          <Icon
            name={
              state?.phase === "current"
                ? "verified"
                : state?.phase === "failed"
                  ? "error_outline"
                  : "system_update"
            }
          />
        </div>
        <div>
          <h2>{phases[state?.phase] || "Loading updates…"}</h2>
          <p aria-live="polite">
            {state?.message || "Reading installed software information…"}
          </p>
          {state?.idleWaitReason && state.phase === "ready" && (
            <p>{state.idleWaitReason}</p>
          )}
          <p className="software-network">
            <Icon
              name={
                state?.network?.type === "ethernet"
                  ? "settings_ethernet"
                  : "wifi"
              }
            />
            {state?.network?.message || "Checking network…"}
          </p>
          <dl>
            <div>
              <dt>Installed</dt>
              <dd>{short(state?.installedRevision)}</dd>
            </div>
            <div>
              <dt>Latest on GitHub</dt>
              <dd>{short(state?.latestRevision)}</dd>
            </div>
            <div>
              <dt>Last check</dt>
              <dd>{checked}</dd>
            </div>
          </dl>
        </div>
      </section>
      <div className="software-actions">
        <button disabled={!available || active} onClick={() => run("check")}>
          <Icon name="refresh" />
          Check for updates
        </button>
        <button
          disabled={!available || active || !updatable}
          onClick={() => run("prepare")}
        >
          <Icon name="download" />
          Prepare update
        </button>
        <button
          className="software-primary"
          disabled={
            !available ||
            active ||
            !state?.preparedRevision ||
            state.preparedRevision === state.installedRevision
          }
          onClick={() => setConfirm("install")}
        >
          <Icon name="restart_alt" />
          Install & restart
        </button>
        {state?.busy && (
          <button disabled={busy} onClick={() => run("cancel")}>
            Cancel preparation
          </button>
        )}
        {state?.canRollback && (
          <button
            disabled={!available || active}
            onClick={() => setConfirm("rollback")}
          >
            Restore previous version
          </button>
        )}
      </div>
      {!available && (
        <p className="software-hint">
          OTA installation is available in the Raspberry Pi application after
          starting it with the updated launcher. The browser preview can show
          this settings page.
        </p>
      )}
      {draft && (
        <section
          className="software-options"
          aria-label="Software-update settings"
        >
          <h2>Update preferences</h2>
          <label className="software-toggle">
            <span>
              <strong>Check automatically</strong>
              <small>
                Look for new GitHub commits while an Internet route is
                available.
              </small>
            </span>
            <input
              type="checkbox"
              role="switch"
              aria-label="Check for software updates automatically"
              checked={draft.autoCheck}
              disabled={!available || busy}
              onChange={(e) => change("autoCheck", e.target.checked)}
            />
          </label>
          <label className="software-toggle">
            <span>
              <strong>Update notifications</strong>
              <small>
                Show a notice when a new GitHub version is available or
                prepared.
              </small>
            </span>
            <input
              type="checkbox"
              role="switch"
              aria-label="Show software update notifications"
              checked={draft.notifyUpdates ?? true}
              disabled={!available || busy}
              onChange={(e) => change("notifyUpdates", e.target.checked)}
            />
          </label>
          <label className="software-field">
            <span>Installation mode</span>
            <select
              aria-label="Software installation mode"
              value={draft.mode}
              disabled={!available || busy}
              onChange={(e) => change("mode", e.target.value)}
            >
              <option value="notify">Notify me · install on tap</option>
              <option value="idle">
                Prepare and install automatically when idle
              </option>
            </select>
          </label>
          <p className="software-hint">
            Automatic activation waits for fresh OBD speed and RPM at zero for
            30 seconds, Android Auto disconnected, no active call and no OBD
            recording. Otherwise the built update waits for manual parked
            confirmation.
          </p>
          <label className="software-field">
            <span>Check every (hours)</span>
            <div>
              <button
                aria-label="Decrease software check interval"
                disabled={!available || busy || draft.checkIntervalHours <= 1}
                onClick={() =>
                  change("checkIntervalHours", draft.checkIntervalHours - 1)
                }
              >
                −
              </button>
              <select
                aria-label="Software check interval in hours"
                value={draft.checkIntervalHours}
                disabled={!available || busy}
                onChange={(e) =>
                  change("checkIntervalHours", Number(e.target.value))
                }
              >
                {[
                  ...new Set([
                    1,
                    3,
                    6,
                    12,
                    24,
                    48,
                    72,
                    168,
                    draft.checkIntervalHours,
                  ]),
                ]
                  .sort((a, b) => a - b)
                  .map((n) => (
                    <option key={n}>{n}</option>
                  ))}
              </select>
              <button
                aria-label="Increase software check interval"
                disabled={!available || busy || draft.checkIntervalHours >= 168}
                onClick={() =>
                  change("checkIntervalHours", draft.checkIntervalHours + 1)
                }
              >
                +
              </button>
            </div>
          </label>
          <label className="software-toggle">
            <span>
              <strong>Prepare during Android Auto</strong>
              <small>
                Download and build over the available Internet route. Activation
                still waits; preparation can affect responsiveness.
              </small>
            </span>
            <input
              type="checkbox"
              role="switch"
              aria-label="Prepare updates while Android Auto is connected"
              checked={draft.prepareDuringAndroidAuto}
              disabled={!available || busy}
              onChange={(e) =>
                change("prepareDuringAndroidAuto", e.target.checked)
              }
            />
          </label>
          <label className="software-toggle">
            <span>
              <strong>Allow metered connections</strong>
              <small>
                Also use routes marked metered or with unknown metering status.
              </small>
            </span>
            <input
              type="checkbox"
              role="switch"
              aria-label="Allow software updates on metered connections"
              checked={draft.allowMetered}
              disabled={!available || busy}
              onChange={(e) => change("allowMetered", e.target.checked)}
            />
          </label>
          <label className="software-field">
            <span>Keep managed versions</span>
            <select
              aria-label="Managed software versions to retain"
              value={draft.keepVersions}
              disabled={!available || busy}
              onChange={(e) => change("keepVersions", Number(e.target.value))}
            >
              {[2, 3, 4].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </label>
          <div className="software-actions">
            <button
              disabled={!dirty || busy}
              onClick={() => {
                setDraft(state.settings);
                setDirty(false);
              }}
            >
              Discard changes
            </button>
            <button
              disabled={!dirty || !available || busy}
              onClick={() => run("settings", { settings: draft })}
            >
              Save update preferences
            </button>
          </div>
          {dirty && (
            <p className="software-hint" role="status">
              Unsaved update preferences
            </p>
          )}
        </section>
      )}
      <details className="software-details">
        <summary>Connection and recovery</summary>
        <p>
          Wired Ethernet can provide Internet while wireless Android Auto uses
          the Pi’s Wi-Fi. Wi-Fi Internet is usable when that adapter is
          available, or through a separate adapter. The updater uses the current
          route and never disconnects Android Auto or changes Wi-Fi mode to
          fetch an update.
        </p>
        <p>
          Updates come only from{" "}
          {state?.repository || "EpicNori/clean-room-reverse-engeenering-hudiy"}{" "}
          · main. They build in a separate directory as the desktop user. At
          least 4 GiB free space and the installer’s build dependencies are
          required. No OS packages are installed automatically.
        </p>
        <p>
          Install restarts the app and briefly disconnects projection. The
          stable launcher checks the new interface and backend, restoring the
          previous version if startup fails. Keep the Pi powered during
          preparation and activation.
        </p>
      </details>
      {confirm && (
        <div className="software-dialog-backdrop">
          <section
            ref={dialog}
            role="dialog"
            aria-modal="true"
            aria-label="Confirm software restart"
            className="software-dialog"
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === "Escape" && !busy) setConfirm(null);
              if (e.key === "Tab") {
                const controls = [
                  ...dialog.current.querySelectorAll("button:not(:disabled)"),
                ];
                if (e.shiftKey && document.activeElement === controls[0]) {
                  e.preventDefault();
                  controls.at(-1)?.focus();
                } else if (
                  !e.shiftKey &&
                  document.activeElement === controls.at(-1)
                ) {
                  e.preventDefault();
                  controls[0]?.focus();
                }
              }
            }}
          >
            <h2>
              {confirm === "rollback"
                ? "Restore the previous version?"
                : "Install the prepared update?"}
            </h2>
            <p>
              Confirm the car is parked. The app will restart and Android Auto
              will briefly disconnect. Your saved settings and diagnostic logs
              remain in private storage.
            </p>
            {error && <p role="alert">{error}</p>}
            <div className="software-actions">
              <button disabled={busy} onClick={() => setConfirm(null)}>
                Keep using the app
              </button>
              <button
                disabled={busy}
                onClick={() => run(confirm, { parked: true })}
              >
                Parked · restart now
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
