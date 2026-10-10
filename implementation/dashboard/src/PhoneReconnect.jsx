import React, {useEffect, useRef, useState} from 'react';

export function PhoneReconnect({action}) {
  const [state, setState] = useState({available: false, devices: [], autoConnect: []});
  const [busy, setBusy] = useState(false);
  const mounted = useRef(false), saving = useRef(false);
  useEffect(() => {
    mounted.current = true;
    let timer, controller;
    const refresh = async () => {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2000);
      try {
        const response = await fetch('/api/bluetooth', {signal: controller.signal});
        if (response.ok) {
          const data = await response.json();
          if (mounted.current && !saving.current) setState(data);
        }
      } catch {} finally {
        clearTimeout(timeout);
        if (mounted.current) timer = setTimeout(refresh, 5000);
      }
    };
    refresh();
    return () => {mounted.current = false; clearTimeout(timer); controller?.abort();};
  }, []);
  const phones = (state.devices || []).filter(device => device.paired && device.phone);
  return <div className="phone-reconnect-settings">
    {phones.map(phone => {
      const enabled = (state.autoConnect || []).includes(phone.address);
      const label = `Automatically reconnect ${phone.name}`;
      return <div className="setting-row toggle-row" key={phone.address}>
        <span>{label}</span>
        <button className={`switch ${enabled ? 'on' : ''}`} role="switch" aria-label={label}
          aria-checked={enabled} disabled={busy || !state.available} onClick={async () => {
            if (saving.current) return;
            saving.current = true; setBusy(true);
            try {
              const result = await action('bluetooth-autoconnect', {address: phone.address, enabled: !enabled});
              if (mounted.current && result?.accepted) setState(current => ({...current, autoConnect: enabled
                ? (current.autoConnect || []).filter(address => address !== phone.address)
                : [...new Set([...(current.autoConnect || []), phone.address])]}));
            } finally {saving.current = false; if (mounted.current) setBusy(false);}
          }}><span/></button>
      </div>;
    })}
    <p className="setting-note">{phones.length
      ? 'On reconnects your paired phone after startup or connection loss, with retries every 30 seconds. Off uses manual connection. Automatic opening below controls whether Android Auto appears.'
      : 'Pair your phone and allow contact sharing to choose automatic or manual reconnection.'}</p>
  </div>;
}
