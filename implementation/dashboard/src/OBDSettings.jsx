import React, {useEffect, useRef, useState} from 'react';

export function OBDSettings({action, status, demo, demoControl}) {
  const [transport, setTransport] = useState('hudiy');
  const [settings, setSettings] = useState({available:false, devices:[]});
  const [address, setAddress] = useState(''), [channel, setChannel] = useState(2);
  const [port, setPort] = useState('/dev/rfcomm0'), [busy, setBusy] = useState(false);
  const hydrated = useRef(false);
  useEffect(() => {
    let closed = false;
    const poll = async () => {
      const controller = new AbortController(), timer = setTimeout(() => controller.abort(),2000);
      try {
        const response = await fetch('/api/obd-settings', {signal:controller.signal});
        if (!response.ok) throw Error();
        const data = await response.json();
        if (closed) return;
        setSettings(data);
        if (!hydrated.current && data.available) {
          setAddress(data.address || data.devices[0]?.address || '');
          setChannel(Number.isInteger(data.channel) && data.channel>=1 && data.channel<=30 ? data.channel : 2);
          hydrated.current = true;
        }
      } catch { if (!closed) setSettings({available:false,devices:[]}); }
      finally { clearTimeout(timer); }
    };
    poll();
    const interval = setInterval(poll,5000);
    return () => {closed=true; clearInterval(interval);};
  }, []);
  const run = async (name, args) => {
    setBusy(true);
    try {return await action(name,args);} finally {setBusy(false);}
  };
  const paths = ['/dev/rfcomm0','/dev/rfcomm1','/dev/rfcomm2','/dev/ttyUSB0','/dev/ttyACM0','COM1','COM2'];
  return <>
    {demoControl}
    <label className="setting-row obd-choice">Connection
      <select aria-label="OBD connection type" value={transport} onChange={e=>setTransport(e.target.value)}>
        <option value="hudiy">Bluetooth through Hudiy</option><option value="serial">Serial / USB</option>
      </select>
    </label>
    {transport==='hudiy' ? <>
      <label className="setting-row obd-choice">Paired ELM327
        <select aria-label="Paired Bluetooth OBD adapter" value={address} disabled={!settings.available || busy} onChange={e=>setAddress(e.target.value)}>
          {!settings.devices.some(d=>d.address===address) && <option value={address}>{address || 'No paired serial adapter'}</option>}
          {settings.devices.map(device=><option value={device.address} key={device.address}>{device.name} · {device.address}</option>)}
        </select>
      </label>
      <div className="setting-row obd-choice"><span>RFCOMM channel</span><div className="obd-channel">
        <button aria-label="Decrease RFCOMM channel" disabled={busy || channel<=1} onClick={()=>setChannel(v=>v-1)}>−</button>
        <output aria-label="RFCOMM channel">{channel}</output>
        <button aria-label="Increase RFCOMM channel" disabled={busy || channel>=30} onClick={()=>setChannel(v=>v+1)}>+</button>
      </div></div>
      <div className="obd-actions">
        <button disabled={busy || !settings.available || !settings.devices.some(d=>d.address===address)}
          onClick={()=>run('obd-native-settings',{address,channel})}>Save and reconnect Hudiy</button>
        <button disabled={busy || !status.projection?.nativeOBDConnected}
          onClick={()=>run('obd-connect',{port:'hudiy'})}>Read live sensors</button>
      </div>
      <p className="obd-details">{!settings.available ? 'Bluetooth OBD settings are available on the Pi.' :
        status.projection?.nativeOBDConnected ? 'The configured Bluetooth adapter is connected.' : 'Turn on your paired ELM327 and the vehicle ignition.'}
        <br/>This adapter uses Bluetooth Serial Port. BLE-only adapters are not supported yet.</p>
    </> : <>
      <label className="setting-row obd-choice">Serial port
        <select aria-label="ELM327 port presets" value={paths.includes(port)?port:'custom'} onChange={e=>setPort(e.target.value==='custom'?'':e.target.value)}>
          {paths.map(path=><option key={path}>{path}</option>)}<option value="custom">Custom port</option>
        </select>
      </label>
      <div className="setting-row obd-path"><label>ELM327 serial port
        <input aria-label="ELM327 serial port" value={port} onChange={e=>setPort(e.target.value)}/>
      </label><button disabled={busy} onClick={()=>run('obd-connect',{port})}>Connect</button></div>
    </>}
    <button className="setting-row link-row" disabled={busy} onClick={()=>run('obd-disconnect')}>Stop sensor polling</button>
    <p className="obd-details">Status: {demo?'Demo data':status.obd?.connected?'Connected':'Disconnected'}
      {status.obd?.error && <><br/>{status.obd.error}</>}</p>
  </>;
}
