import React, { useEffect, useState } from 'react';

export function UpdateInterval({ label, value, min, max, save }) {
  const [draft, setDraft] = useState(String(value));
  const [busy, setBusy] = useState(false);
  useEffect(() => { setDraft(String(value)); }, [value]);
  const number = Number(draft);
  const valid = draft.trim() !== '' && Number.isInteger(number) && number >= min && number <= max;
  return <div className="refresh-setting">
    <label>{label}<span className="refresh-input">
      <button type="button" aria-label={`Decrease ${label.toLowerCase()}`} disabled={busy || (valid && number <= min)}
        onClick={() => setDraft(String(Math.max(min, (valid ? number : value) - 1)))}>−</button>
      <input type="number" inputMode="numeric" aria-label={label} min={min} max={max} step="1"
        value={draft} onChange={event => setDraft(event.target.value)} disabled={busy} />
      <button type="button" aria-label={`Increase ${label.toLowerCase()}`} disabled={busy || (valid && number >= max)}
        onClick={() => setDraft(String(Math.min(max, (valid ? number : value) + 1)))}>+</button> seconds
    </span></label>
    <button className="layout-reset" disabled={!valid || busy || number === value} onClick={async () => {
      setBusy(true);
      try { await save(number); } finally { setBusy(false); }
    }}>{busy ? 'Saving…' : 'Save'}</button>
    <p className="setting-note">Choose {min}–{max} seconds. Current interval: {value} seconds.</p>
  </div>;
}
