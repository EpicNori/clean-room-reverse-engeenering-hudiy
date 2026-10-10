import React, { useEffect, useRef, useState } from 'react';

const Icon = ({ name }) => <span className="material-symbols-rounded" aria-hidden="true">{name}</span>;

export function BluetoothView({ mode, action }) {
  const [data, setData] = useState({available: false, devices: [], name: 'Hudiy', error: 'Loading Bluetooth devices…'});
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const list = useRef(null), cancel = useRef(null), confirm = useRef(null), opener = useRef(null);
  useEffect(() => {
    let closed = false, active = false;
    const poll = async () => {
      if (active) return;
      active = true;
      const controller = new AbortController(), deadline = setTimeout(() => controller.abort(), 2000);
      try {
        const response = await fetch('/api/bluetooth', { signal: controller.signal });
        if (!response.ok) throw Error();
        const result = await response.json();
        if (!closed) setData(result);
      } catch { if (!closed) setData({available:false, devices:[], name:'Hudiy', error:'Live Bluetooth is available on the Pi'}); }
      finally { active = false; clearTimeout(deadline); }
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => { closed = true; clearInterval(interval); };
  }, []);
  useEffect(() => { setSelected(null); if (list.current) list.current.scrollTop = 0; }, [mode]);
  useEffect(() => {
    if (!selected) return;
    cancel.current?.focus();
    const trigger = opener.current;
    return () => { if (trigger?.isConnected) trigger.focus(); };
  }, [selected]);
  const run = async (name, args) => {
    setBusy(true);
    try { return await action(name, args); } finally { setBusy(false); }
  };
  const connections=mode==='bluetooth-connections';
  const devices = data.devices.filter(item => mode === 'remove' || connections ? item.paired : !item.paired);
  const scanActive = data.scanActive;
  return <div className={mode === 'pair' ? 'bluetooth-pair-view' : undefined}>
    {mode === 'pair' && <>
      <header><h1>Pair</h1><button className="phonebook-refresh" disabled={busy || !data.available}
        onClick={() => run('bluetooth-pair-menu')}><Icon name="link" />{busy ? 'Opening…' : 'Pair device'}</button></header>
      <p className="phonebook-status" role="status">{data.name}{scanActive ? ' · Scanning…' : ''}</p>
    </>}
    <div className={`bluetooth-device-list ${mode === 'pair' ? 'bluetooth-discovery-list' : ''} ${connections?'bluetooth-connections-list':''}`} ref={list}>
      {connections && <p className="setting-note">Choose which paired devices reconnect automatically. Attempts are limited to once every 30 seconds per device.</p>}
      {devices.map(device => <div className="bluetooth-device" key={device.address}>
        <Icon name="bluetooth" />
        <div className="bluetooth-device-name"><strong>{device.name}</strong><span>{device.address}</span>{connections && <span>{device.connected?'Connected':'Disconnected'}</span>}</div>
        {connections ? <div className="bluetooth-connection-controls">
          <button className="layout-reset" disabled={busy || !data.available} aria-label={`${device.connected?'Disconnect':'Connect'} ${device.name}`} onClick={event=>{
            if(device.connected){opener.current=event.currentTarget;setSelected(device);}
            else run('bluetooth-connect',{address:device.address});
          }}>{device.connected?'Disconnect':'Connect'}</button>
          <label><input type="checkbox" aria-label={`Automatically reconnect ${device.name}`} checked={(data.autoConnect || []).includes(device.address)} disabled={busy || !data.available}
            onChange={async event=>{const enabled=event.target.checked;const result=await run('bluetooth-autoconnect',{address:device.address,enabled});
              if(result)setData(current=>({...current,autoConnect:enabled?[...new Set([...(current.autoConnect || []),device.address])]:(current.autoConnect || []).filter(a=>a!==device.address)}));}}/>Automatic reconnect</label>
        </div> : mode === 'remove' && <button className="bluetooth-device-action" aria-label={`Unpair ${device.name}`}
          disabled={busy || !data.available} onClick={event => {
            if (mode === 'remove') { opener.current = event.currentTarget; setSelected(device); }
            else run('bluetooth-pair-menu');
          }}><Icon name={mode === 'remove' ? 'link_off' : 'link'} /></button>}
      </div>)}
      {!data.available && <p className="bluetooth-empty" role="status">{data.error}</p>}
      {data.available && !devices.length && (mode === 'remove' || connections) && <p className="bluetooth-empty">No paired devices.</p>}
      {data.available && !devices.length && mode === 'pair' && <p className="bluetooth-empty">{scanActive ? 'Searching for nearby devices…' : 'Tap Pair device to find and pair a device.'}</p>}
    </div>
    <div className="bluetooth-scroll-buttons">
      <button aria-label="Scroll devices up" onClick={() => list.current?.scrollBy({top:-300,behavior:'smooth'})}><Icon name="expand_less" /></button>
      <button aria-label="Scroll devices down" onClick={() => list.current?.scrollBy({top:300,behavior:'smooth'})}><Icon name="expand_more" /></button>
    </div>
    {selected && <div className="customize-backdrop"><div className="customize-menu" role="dialog" aria-modal="true" aria-label={`${connections?'Disconnect':'Unpair'} ${selected.name}`} onKeyDown={event => {
      if (event.key === 'Escape' && !busy) { event.preventDefault(); event.stopPropagation(); setSelected(null); }
      if (event.key === 'Tab') {
        if (event.shiftKey && document.activeElement === cancel.current) { event.preventDefault(); confirm.current?.focus(); }
        else if (!event.shiftKey && document.activeElement === confirm.current) { event.preventDefault(); cancel.current?.focus(); }
      }
    }}>
      <strong>{connections?'Disconnect':'Unpair'} {selected.name}?</strong>
      <p>{connections?'Phone media and calls can stop. Automatic reconnect will be disabled for this device.':`Remove the saved Bluetooth pairing${selected.connected?' and disconnect this device':''}. To use it again, pair it again.`}</p>
      <button ref={cancel} disabled={busy} onClick={() => setSelected(null)}>Cancel</button>
      <button ref={confirm} disabled={busy} onClick={async () => {
        const result = await run(connections?'bluetooth-disconnect':'bluetooth-remove', {address:selected.address, confirmed:true});
        if (result) { setData(current => ({...current, devices:connections?current.devices.map(device=>device.address===selected.address?{...device,connected:false}:device):current.devices.filter(device => device.address !== selected.address),autoConnect:(current.autoConnect || []).filter(a=>a!==selected.address)})); setSelected(null); }
      }}>{busy ? 'Working…' : connections?'Disconnect device':'Unpair device'}</button>
    </div></div>}
  </div>;
}
