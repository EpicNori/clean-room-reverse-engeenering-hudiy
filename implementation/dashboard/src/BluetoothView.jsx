import {canUseBluetoothAudio, useBluetoothAudio} from './bluetoothAudio.mjs';
import {deviceIcon, deviceKind, deviceStatus, friendlyBluetoothError, isAudioOutput, splitDevices, validDeviceName} from './bluetoothScreen.mjs';
import React, { useEffect, useRef, useState } from 'react';

const Icon = ({ name }) => <span className="material-symbols-rounded" aria-hidden="true">{name}</span>;
const OFFLINE = {available:false, powered:false, devices:[], name:'coscarOS', error:'Live Bluetooth is available on the Pi'};
const FOCUSABLE = 'button:not(:disabled), input:not(:disabled)';
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

// Own request helper: the inline status needs the backend's error text even when popups are off.
async function post(name, params = {}) {
  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch('/api/action', {method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:name, ...params}), signal:controller.signal});
      let result = {};
      try { result = await response.json(); } catch {}
      if (response.ok) return result;
      // The 1 s refresh briefly holds the Bluetooth lock; nothing was changed, so retry.
      if (/operation in progress/i.test(result.error || '') && attempt < 2) { await wait(700); continue; }
      throw Error(result.error || 'Action unavailable');
    } finally { clearTimeout(timer); }
  }
}

function Dialog({ label, busy, onClose, children }) {
  const box = useRef(null);
  useEffect(() => {
    const opener = document.activeElement;
    box.current?.querySelector(FOCUSABLE)?.focus();
    return () => { if (opener?.isConnected) opener.focus(); };
  }, []);
  return <div className="customize-backdrop"><div ref={box} className="customize-menu bluetooth-dialog" role="dialog" aria-modal="true" aria-label={label} onKeyDown={event => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); if (!busy) onClose(); }
    if (event.key === 'Tab') {
      const items = [...box.current.querySelectorAll(FOCUSABLE)];
      if (!items.length) return;
      if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items.at(-1).focus(); }
      else if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); items[0].focus(); }
    }
  }}>{children}</div></div>;
}

function SwitchRow({ label, checked, disabled, onToggle, children }) {
  return <button type="button" className="bluetooth-switch-row" role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={onToggle}>
    <span>{children}</span><span className={`switch ${checked ? 'on' : ''}`}><span/></span>
  </button>;
}

export function BluetoothView() {
  const [data, setData] = useState({...OFFLINE, error:'Loading Bluetooth devices…'});
  const [audioRoute, setAudioRoute] = useState({available:false,address:'',routed:false});
  const audioPending = useRef(false), audioGeneration = useRef(0);
  const [status, setStatus] = useState({text:'', tone:'idle'});
  const [pending, setPending] = useState(false);
  // dialog: {address, step: 'details'|'disconnect'|'unpair', origin: 'row'|'details'}
  const [dialog, setDialog] = useState(null);
  const [nameDraft, setNameDraft] = useState('');
  const list = useRef(null), scanOwned = useRef(false), autoScanned = useRef(false), latest = useRef(data), previous = useRef(null);
  latest.current = data;

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
      } catch { if (!closed) setData(OFFLINE); }
      finally { active = false; clearTimeout(deadline); }
    };
    poll();
    const interval = setInterval(poll, 1000);
    return () => { closed = true; clearInterval(interval); };
  }, []);
  useEffect(() => {
    let closed=false,active=false;
    const poll=async()=>{
      if(active)return;active=true;
      const generation=audioGeneration.current;
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),2000);
      try {
        const response=await fetch('/api/audio-route',{signal:controller.signal});
        if(!response.ok)throw Error();
        const result=await response.json();
        if(!closed && !audioPending.current && generation===audioGeneration.current)setAudioRoute(result);
      } catch {if(!closed && !audioPending.current && generation===audioGeneration.current)setAudioRoute(current=>({...current,available:false}));}
      finally {active=false;clearTimeout(timer);}
    };
    poll();const timer=setInterval(poll,2000);
    return()=>{closed=true;clearInterval(timer);};
  },[]);

  const run = async (name, params, progress) => {
    setPending(true);
    if (progress) setStatus({text:progress, tone:'busy'});
    try {
      const result = await post(name, params);
      setStatus({text:result.message || '', tone:'idle'});
      return result;
    } catch (error) {
      setStatus({text:friendlyBluetoothError(error.message), tone:'error'});
      return null;
    } finally { setPending(false); }
  };
  const ready = Boolean(data.available && data.powered);

  // Discovery starts by itself; the backend ends it after 30 s because it disturbs wireless Android Auto.
  const scan = async () => {
    const result = await run('bluetooth-scan', {}, 'Searching for nearby devices…');
    if (result) { scanOwned.current = true; setData(current => ({...current, scanActive:true})); setStatus({text:'', tone:'idle'}); }
  };
  useEffect(() => {
    if (!ready) { autoScanned.current = false; return; }
    if (autoScanned.current) return;
    autoScanned.current = true;
    scan();
  }, [ready]);
  useEffect(() => () => {
    if (scanOwned.current && latest.current.scanActive) post('bluetooth-scan-stop').catch(() => {});
  }, []);

  // Report finished background work (connect, disconnect, pair+connect) in the inline status.
  useEffect(() => {
    const before = previous.current;
    previous.current = {operations:data.operations || {}, progress:data.pairingProgress || null};
    if (!before) return;
    const named = address => (data.devices || []).find(device => device.address === address);
    for (const [address, operation] of Object.entries(data.operations || {}))
      if (operation.state === 'failed' && before.operations[address]?.state !== 'failed')
        setStatus({text:`${named(address)?.name || 'Device'}: ${operation.message}`, tone:'error'});
    for (const [address, operation] of Object.entries(before.operations))
      if (['connecting','disconnecting'].includes(operation.state) && !data.operations?.[address] && named(address)) {
        const device = named(address);
        setStatus({text:device.connected ? `Connected to ${device.name}.` : `${device.name} is disconnected.`, tone:'idle'});
      }
    const progress = data.pairingProgress, old = before.progress;
    if (progress && (progress.state !== old?.state || progress.address !== old?.address)) {
      if (progress.state === 'connecting') setStatus({text:`Paired with ${progress.name}. Connecting…`, tone:'busy'});
      if (progress.state === 'connected') setStatus({text:`${progress.name} is paired and connected.`, tone:'idle'});
      if (progress.state === 'failed') setStatus({text:`${progress.name}: ${progress.message}`, tone:'error'});
    }
  }, [data]);

  const markOperation = (address, state) => setData(current => ({...current, operations:{...(current.operations || {}), [address]:{state, message:''}}}));
  const connect = async device => {
    const result = await run('bluetooth-connect', {address:device.address}, `Connecting to ${device.name}…`);
    if (result && result.state !== 'disconnected') markOperation(device.address, 'connecting');
  };
  const disconnect = async device => {
    const result = await run('bluetooth-disconnect', {address:device.address, confirmed:true}, `Disconnecting ${device.name}…`);
    if (!result) return false;
    setData(current => ({...current,
      operations:result.state === 'disconnecting' ? {...(current.operations || {}), [device.address]:{state:'disconnecting', message:''}} : current.operations,
      effectiveAutoConnect:(current.effectiveAutoConnect || current.autoConnect || []).filter(a => a !== device.address),
      autoConnect:(current.autoConnect || []).filter(a => a !== device.address)}));
    return true;
  };
  const pair = async device => {
    if (!data.pairingAvailable) { setStatus({text:'Pairing is not ready yet. Try again in a moment.', tone:'error'}); return; }
    const result = await run('bluetooth-pair', {address:device.address}, `Pairing with ${device.name}…`);
    if (result) setData(current => ({...current, scanActive:false, pairingBusy:true, pairingProgress:{address:device.address, name:device.name, state:'pairing', message:''}}));
  };
  const automatic = async (device, enabled) => {
    const result = await run('bluetooth-autoconnect', {address:device.address, enabled});
    if (result) setData(current => ({...current,
      effectiveAutoConnect:enabled ? [...new Set([...(current.effectiveAutoConnect || current.autoConnect || []), device.address])] : (current.effectiveAutoConnect || current.autoConnect || []).filter(a => a !== device.address),
      autoConnect:enabled ? [...new Set([...(current.autoConnect || []), device.address])] : (current.autoConnect || []).filter(a => a !== device.address)}));
  };
  const chooseAudio = async device => {
    if (audioPending.current) return;
    audioPending.current = true; audioGeneration.current++; setPending(true); setStatus({text:'Selecting audio device…', tone:'busy'});
    try {
      const result = await useBluetoothAudio(device, (name, params) => post(name, params).catch(() => null));
      if (result.saved) setAudioRoute(current => ({...current, address:device.address, routed:false}));
      setStatus({text:result.message, tone:result.saved ? 'idle' : 'error'});
    } catch { setStatus({text:'Audio device could not be selected. Please retry.', tone:'error'}); }
    finally { audioPending.current = false; setPending(false); }
  };

  const { paired, available } = splitDevices(data.devices);
  const selected = dialog && (data.devices || []).find(device => device.address === dialog.address && device.paired);
  useEffect(() => { if (dialog && !selected && !pending) setDialog(null); }, [dialog, selected, pending]);
  const openDetails = device => { setNameDraft(device.name); setDialog({address:device.address, step:'details', origin:'details'}); };
  const closeStep = () => setDialog(current => current?.origin === 'details' ? {...current, step:'details'} : null);
  const statusOf = device => deviceStatus(device, {operations:data.operations, pairingProgress:data.pairingProgress});
  const autoConnect = data.effectiveAutoConnect || data.autoConnect || [];

  const row = device => {
    const state = statusOf(device), audio = device.paired && isAudioOutput(device, audioRoute);
    const label = device.paired ? (state.busy ? `${device.name}, ${state.text}` : device.connected ? `Disconnect ${device.name}` : `Connect ${device.name}`) : `Pair ${device.name}`;
    return <div className="bluetooth-device bluetooth-row" key={device.address}>
      <button type="button" className="bluetooth-row-main" aria-label={label}
        disabled={pending || state.busy || (!device.paired && (data.pairingBusy || Boolean(data.pairing)))}
        onClick={() => device.paired ? (device.connected ? setDialog({address:device.address, step:'disconnect', origin:'row'}) : connect(device)) : pair(device)}>
        <Icon name={deviceIcon(device)} />
        <span className="bluetooth-device-name"><strong>{device.name}</strong>
          {(state.text || audio) && <span className={`bluetooth-row-status ${state.tone}`}>{state.busy && <span className="bluetooth-spinner" aria-hidden="true"/>}{state.text}{audio && <em>{state.text ? ' · ' : ''}Audio output</em>}</span>}
        </span>
      </button>
      {device.paired && <button type="button" className="bluetooth-device-action" aria-label={`Settings for ${device.name}`} disabled={pending} onClick={() => openDetails(device)}><Icon name="settings" /></button>}
    </div>;
  };

  const details = device => {
    const state = statusOf(device), audio = isAudioOutput(device, audioRoute), automaticOn = autoConnect.includes(device.address);
    return <>
      <strong>{device.name}</strong>
      <p>{deviceKind(device)} · {device.address}</p>
      <p className={`bluetooth-row-status ${state.tone}`} role="status">{state.text}{audio ? ' · Audio output' : ''}</p>
      <label className="bluetooth-rename"><span>Name</span>
        <input type="text" value={nameDraft} maxLength={64} disabled={pending} onChange={event => setNameDraft(event.target.value)}/></label>
      <button type="button" disabled={pending || !validDeviceName(nameDraft) || nameDraft.trim() === device.name}
        onClick={async () => { const result = await run('bluetooth-rename', {address:device.address, name:nameDraft.trim()}, 'Saving name…');
          if (result) setData(current => ({...current, devices:current.devices.map(d => d.address === device.address ? {...d, name:result.name} : d)})); }}>
        <Icon name="edit" />Save name</button>
      <button type="button" disabled={pending || state.busy || !ready}
        onClick={() => device.connected ? setDialog({address:device.address, step:'disconnect', origin:'details'}) : connect(device)}>
        <Icon name={device.connected ? 'link_off' : 'link'} />{device.connected ? 'Disconnect' : 'Connect'}</button>
      {canUseBluetoothAudio(device) && <>
        <button type="button" className="bluetooth-use-audio" disabled={pending || !audioRoute.available || audio}
          aria-label={`${audio ? 'Audio device selected' : 'Use as audio device'}: ${device.name}`} onClick={() => chooseAudio(device)}>
          <Icon name="speaker" />{audio ? 'Audio device selected' : 'Use as audio device'}</button>
        {audio && <p className="bluetooth-audio-route" role="status">{audioRoute.routed ? 'Audio output active' : !device.connected ? 'Connect to use audio' : audioRoute.error || 'Waiting for audio output'}</p>}
        {!audioRoute.available && <p className="bluetooth-audio-route">Audio output service unavailable</p>}
      </>}
      <SwitchRow label={`Automatically reconnect ${device.name}`} checked={automaticOn} disabled={pending} onToggle={() => automatic(device, !automaticOn)}>Automatic reconnect</SwitchRow>
      <button type="button" disabled={pending} onClick={() => setDialog({address:device.address, step:'unpair', origin:'details'})}><Icon name="delete" />Unpair</button>
      <button type="button" disabled={pending} onClick={() => setDialog(null)}>Done</button>
    </>;
  };

  // Dialogs sit outside the positioned list area so their backdrop covers the whole screen.
  return <><div className="bluetooth-view">
    <header>
      <h1>Bluetooth</h1>
      <button type="button" className="bluetooth-power" role="switch" aria-checked={Boolean(data.powered)} aria-label="Bluetooth"
        disabled={pending || !data.available} onClick={async () => {
          const enabled = !data.powered;
          const result = await run('bluetooth-power', {enabled}, enabled ? 'Turning Bluetooth on…' : 'Turning Bluetooth off…');
          if (result) setData(current => ({...current, powered:enabled, scanActive:enabled && current.scanActive}));
        }}><span>{data.powered ? 'On' : 'Off'}</span><span className={`switch ${data.powered ? 'on' : ''}`}><span/></span></button>
    </header>
    <p className="phonebook-status">{data.available ? `Visible as ${data.name}` : data.error}</p>
    <p className={`bluetooth-status ${status.tone}`} role="status">{status.text || (!dialog && data.pairingError && !data.pairingProgress ? data.pairingError : '')}</p>
    <div className="bluetooth-device-list bluetooth-sections" ref={list}>
      {data.available && !data.powered && <p className="bluetooth-empty">Turn on Bluetooth to see paired devices and pair new ones.</p>}
      {ready && <>
        <h2 className="bluetooth-section-title">Paired devices</h2>
        {paired.map(row)}
        {!paired.length && <p className="bluetooth-empty">No paired devices yet.</p>}
        <div className="bluetooth-section-title bluetooth-available-title">
          <h2>Available devices</h2>
          {data.scanActive ? <span className="bluetooth-searching"><span className="bluetooth-spinner" aria-hidden="true"/>Searching…</span>
            : <button type="button" className="phonebook-refresh" disabled={pending || data.pairingBusy} onClick={scan}><Icon name="refresh" />Scan again</button>}
        </div>
        {available.map(row)}
        {!available.length && <p className="bluetooth-empty">{data.scanActive ? 'Looking for nearby devices. Make the other device visible.' : 'No devices found. Make the other device visible, then tap Scan again.'}</p>}
      </>}
    </div>
    <div className="bluetooth-scroll-buttons">
      <button aria-label="Scroll devices up" onClick={() => list.current?.scrollBy({top:-300,behavior:'smooth'})}><Icon name="expand_less" /></button>
      <button aria-label="Scroll devices down" onClick={() => list.current?.scrollBy({top:300,behavior:'smooth'})}><Icon name="expand_more" /></button>
    </div>
    </div>
    {selected && dialog.step === 'details' && <Dialog key="details" label={`${selected.name} settings`} busy={pending} onClose={() => setDialog(null)}>{details(selected)}</Dialog>}
    {selected && dialog.step === 'disconnect' && <Dialog key="disconnect" label={`Disconnect ${selected.name}`} busy={pending} onClose={closeStep}>
      <strong>Disconnect {selected.name}?</strong>
      <p>Phone media and calls can stop. Automatic reconnect will be disabled for this device.</p>
      <button type="button" disabled={pending} onClick={closeStep}>Cancel</button>
      <button type="button" disabled={pending} onClick={async () => { if (await disconnect(selected)) closeStep(); }}>{pending ? 'Working…' : 'Disconnect'}</button>
    </Dialog>}
    {selected && dialog.step === 'unpair' && <Dialog key="unpair" label={`Unpair ${selected.name}`} busy={pending} onClose={closeStep}>
      <strong>Unpair {selected.name}?</strong>
      <p>Remove the saved Bluetooth pairing{selected.connected ? ' and disconnect this device' : ''}. To use it again, pair it again.</p>
      <button type="button" disabled={pending} onClick={closeStep}>Cancel</button>
      <button type="button" disabled={pending} onClick={async () => {
        const address = selected.address;
        const result = await run('bluetooth-remove', {address, confirmed:true}, `Unpairing ${selected.name}…`);
        if (result) { setData(current => ({...current, devices:current.devices.filter(d => d.address !== address),
          effectiveAutoConnect:(current.effectiveAutoConnect || current.autoConnect || []).filter(a => a !== address),
          autoConnect:(current.autoConnect || []).filter(a => a !== address)})); setDialog(null); }
      }}>{pending ? 'Working…' : 'Unpair device'}</button>
    </Dialog>}
    {data.pairing && <Dialog key={`pairing-${data.pairing.id}`} label="Confirm Bluetooth pairing" busy={pending}
      onClose={() => run('bluetooth-pair-confirm', {id:data.pairing.id, accepted:false})}>
      <strong>Pair {data.pairing.name}?</strong>
      {data.pairing.kind === 'pin' ? <>
        <p>Choose the PIN supplied with your adapter.</p>
        {['1234','0000'].map(pin => <button type="button" key={pin} disabled={pending} onClick={() => run('bluetooth-pair-confirm', {id:data.pairing.id, accepted:true, pin})}>Use {pin}</button>)}
      </> : <>
        {data.pairing.code && <p className="bluetooth-pair-code">Confirm that the other device shows <b>{data.pairing.code}</b>.</p>}
        <button type="button" disabled={pending} onClick={() => run('bluetooth-pair-confirm', {id:data.pairing.id, accepted:true})}>Confirm pairing</button>
      </>}
      <button type="button" disabled={pending} onClick={() => run('bluetooth-pair-confirm', {id:data.pairing.id, accepted:false})}>Cancel</button>
    </Dialog>}
  </>;
}
