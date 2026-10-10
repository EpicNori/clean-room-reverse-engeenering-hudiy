import React,{useEffect,useState} from 'react';

export function RadioOutput({action,connections}) {
  const [state,setState]=useState({available:false,address:'',receivers:[]}),[draft,setDraft]=useState(''),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false);
  useEffect(()=>{
    let closed=false,active=false;
    const poll=async()=>{
      if(active)return;active=true;
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),2000);
      try{const r=await fetch('/api/audio-route',{signal:controller.signal});if(!r.ok)throw Error();const data=await r.json();if(!closed)setState(data);}
      catch{if(!closed)setState(current=>({...current,available:false,error:'Radio output is available on the Pi'}));}
      finally{active=false;clearTimeout(timer);}
    };
    poll();const interval=setInterval(poll,5000);
    return()=>{closed=true;clearInterval(interval);};
  },[]);
  useEffect(()=>{if(!dirty)setDraft(state.address || '');},[state.address,dirty]);
  return <div className="refresh-setting radio-output-setting">
    <label htmlFor="radio-output">Bluetooth radio output</label>
    <select id="radio-output" aria-label="Bluetooth radio output" disabled={!state.available || busy} value={draft} onChange={event=>{setDirty(true);setDraft(event.target.value);}}>
      <option value="">No automatic radio output</option>
      {state.receivers.map(device=><option key={device.address} value={device.address}>{device.name}{device.connected?' · connected':''}</option>)}
      {state.address && !state.receivers.some(d=>d.address===state.address) && <option value={state.address}>Saved receiver unavailable</option>}
    </select>
    <button className="layout-reset" disabled={!state.available || busy || draft===state.address} onClick={async()=>{
      setBusy(true);try{const result=await action('audio-radio-output',{address:draft});if(result?.saved){setState(current=>({...current,address:draft,routed:false}));setDirty(false);}}finally{setBusy(false);}
    }}>{busy?'Saving…':'Save radio output'}</button>
    {(!state.available || state.address) && <p className="setting-note" role="status">{!state.available ? (state.error || 'Radio output is available on the Pi.') : state.routed ? 'Connected' : state.error || 'Waiting for receiver'}</p>}
    <button className="layout-reset" onClick={connections}>Bluetooth Connections</button>
  </div>;
}
