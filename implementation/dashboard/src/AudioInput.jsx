import React,{useEffect,useRef,useState} from 'react';

const defaults={device:'default',volume:100,muted:false};
export function AudioInput({action,pair}) {
  const [state,setState]=useState({available:false,settings:defaults,devices:[]});
  const [draft,setDraft]=useState(defaults),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0);
  const edited=useRef(false),generation=useRef(0),mounted=useRef(true);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useEffect(()=>{
    let stopped=false,timer,controller;
    const poll=async()=>{
      const version=generation.current;
      controller=new AbortController();const deadline=setTimeout(()=>controller.abort(),2000);
      try {
        const response=await fetch('/api/audio-input',{signal:controller.signal});
        if(!response.ok)throw Error();
        const data=await response.json();
        if(!stopped && version===generation.current){setState(data);if(!edited.current)setDraft(data.settings);}
      } catch {if(!stopped && version===generation.current)setState(s=>({...s,available:false,captureActive:false,error:'Microphone service unavailable'}));}
      finally {clearTimeout(deadline);if(!stopped)timer=setTimeout(poll,3000);}
    };
    poll();return()=>{stopped=true;clearTimeout(timer);controller?.abort();};
  },[refresh]);
  const change=patch=>{edited.current=true;setDirty(true);setDraft(d=>({...d,...patch}));};
  const save=async()=>{
    setBusy(true);generation.current++;
    try {
      const result=await action('audio-input',{settings:draft});
      if(result?.saved && mounted.current){generation.current++;setState(result);setDraft(result.settings);edited.current=false;setDirty(false);}
    } finally {if(mounted.current){setBusy(false);setRefresh(v=>v+1);}}
  };
  const missing=draft.device!=='default' && !state.devices.some(d=>d.id===draft.device);
  const capture=state.captureActive ? state.settings.muted ? 'Voice capture active · muted' : 'Voice capture active' : 'Voice capture idle';
  return <section className="audio-input-settings" aria-label="Microphone settings" aria-busy={busy}>
    <p className="setting-note">Choose the microphone used for Android Auto voice input. Capture starts only when Android Auto requests it.</p>
    <div className="audio-input-device">
      <label htmlFor="microphone-device">Microphone</label>
      <select id="microphone-device" value={draft.device} disabled={!state.available || busy} onChange={event=>change({device:event.target.value})}>
        <option value="default">System default</option>
        {state.devices.map(device=><option key={device.id} value={device.id} disabled={!device.supported}>{device.name}{device.isDefault?' · default':''}{!device.supported?' · unsupported format':''}</option>)}
        {missing && <option value={draft.device}>Saved microphone unavailable</option>}
      </select>
      <button className="layout-reset" disabled={busy} onClick={()=>setRefresh(v=>v+1)}>Refresh devices</button>
    </div>
    <p className="setting-note" role="status">{!state.available ? state.error : state.error || `${state.microphoneAvailable?'Microphone ready':'No compatible microphone'} · ${capture}${state.applied?'':' · applying saved settings'}`}</p>
    <fieldset className="audio-input-controls" disabled={!state.available || busy}>
      <legend className="audio-input-legend">Capture controls</legend>
      <div className="setting-row toggle-row"><label htmlFor="microphone-mute">Mute input</label>
        <button id="microphone-mute" type="button" className={`switch ${draft.muted?'on':''}`} role="switch" aria-label="Mute input" aria-checked={draft.muted} onClick={()=>change({muted:!draft.muted})}><span/></button>
      </div>
      <div className="audio-input-volume"><label htmlFor="microphone-volume">Input volume <output>{draft.volume}%</output></label>
        <input id="microphone-volume" type="range" min="0" max="100" step="1" value={draft.volume} aria-valuetext={`${draft.volume}%`} onChange={event=>change({volume:Number(event.target.value)})}/>
      </div>
    </fieldset>
    <div className="audio-input-actions">
      <button className="layout-reset" disabled={!state.available || busy || !dirty} onClick={save}>{busy?'Saving…':'Save input settings'}</button>
      <button className="layout-reset" disabled={busy || !dirty} onClick={()=>{edited.current=false;setDirty(false);setDraft(state.settings);}}>Discard changes</button>
      {dirty && <span role="status">Unsaved changes</span>}
    </div>
    <div className="audio-input-add"><strong>Add a microphone</strong>
      <p className="setting-note">Plug in a USB microphone, then refresh the list. For a Bluetooth microphone, pair it first; it appears here when the system exposes an audio input.</p>
      <button className="layout-reset" disabled={busy} onClick={pair}>Pair Bluetooth device</button>
    </div>
  </section>;
}
