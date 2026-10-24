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
      const enabled = (state.effectiveAutoConnect || state.autoConnect || []).includes(phone.address);
      const label = `Reconnect ${phone.name} over Bluetooth`;
      return <div className="setting-row toggle-row" key={phone.address}>
        <span>{label}</span>
        <button className={`switch ${enabled ? 'on' : ''}`} role="switch" aria-label={label}
          aria-checked={enabled} disabled={busy || !state.available} onClick={async () => {
            if (saving.current) return;
            saving.current = true; setBusy(true);
            try {
              const result = await action('bluetooth-autoconnect', {address: phone.address, enabled: !enabled});
              if (mounted.current && result?.accepted) setState(current => ({...current, effectiveAutoConnect: enabled
                ? (current.effectiveAutoConnect || current.autoConnect || []).filter(address => address !== phone.address)
                : [...new Set([...(current.effectiveAutoConnect || current.autoConnect || []), phone.address])], manualPhones: enabled
                ? [...new Set([...(current.manualPhones || []), phone.address])]
                : (current.manualPhones || []).filter(address => address !== phone.address), autoConnect: enabled
                ? (current.autoConnect || []).filter(address => address !== phone.address)
                : [...new Set([...(current.autoConnect || []), phone.address])]}));
            } finally {saving.current = false; if (mounted.current) setBusy(false);}
          }}><span/></button>
      </div>;
    })}
    <p className="setting-note">{phones.length
      ? 'With car Wi-Fi enabled, automatic connection uses your only paired phone unless its Bluetooth switch is off. For several phones, select which should reconnect. Retries are limited to once every 30 seconds. Automatic opening below controls whether Android Auto appears.'
      : 'Pair your Android phone to choose Bluetooth reconnection. Contact sharing is optional for this setting.'}</p>
  </div>;
}
