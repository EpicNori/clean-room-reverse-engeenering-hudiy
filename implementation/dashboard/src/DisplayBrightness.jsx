import React, {useEffect, useState} from 'react';

export function DisplayBrightness({action}) {
  const [state,setState]=useState({available:false,brightness:null});
  const [draft,setDraft]=useState(100), [busy,setBusy]=useState(false);
  useEffect(()=>{
    let closed=false;
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),2000);
    fetch('/api/display',{signal:controller.signal}).then(r=>r.ok?r.json():Promise.reject())
      .then(data=>{if(!closed){setState(data);if(Number.isInteger(data.brightness))setDraft(Math.max(5,data.brightness));}})
      .catch(()=>{}).finally(()=>clearTimeout(timer));
    return ()=>{closed=true;controller.abort();clearTimeout(timer);};
  },[]);
  return <div className="refresh-setting physical-brightness">
    <label>Physical screen brightness
      <span className="brightness-control"><input aria-label="Physical screen brightness" type="range" min="5" max="100" step="1"
        disabled={!state.available || busy} value={draft} onChange={e=>setDraft(Number(e.target.value))}/><output>{draft}%</output></span>
    </label>
    <button className="layout-reset" disabled={!state.available || busy || draft===state.brightness} onClick={async()=>{
      setBusy(true);
      try {const result=await action('display-brightness',{brightness:draft});if(result?.saved){setState(result);setDraft(Math.max(5,result.brightness));}}
      finally {setBusy(false);}
    }}>{busy?'Saving…':'Save brightness'}</button>
    <p className="setting-note">{state.available?'Controls the physical backlight, including Android Auto. Saved for the next start.':'Physical backlight control is available on the Pi.'}</p>
  </div>;
}
