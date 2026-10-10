import React,{useEffect,useRef,useState} from 'react';

export function WirelessSettings({action,standalone=false}) {
  const [state,setState]=useState({available:false,enabled:false}),[busy,setBusy]=useState(false),[confirm,setConfirm]=useState(false);
  const cancel=useRef(null),apply=useRef(null);
  useEffect(()=>{
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),2000);
    fetch('/api/wireless',{signal:controller.signal}).then(r=>r.ok?r.json():Promise.reject()).then(setState).catch(()=>{}).finally(()=>clearTimeout(timer));
    return()=>{controller.abort();clearTimeout(timer);};
  },[]);
  useEffect(()=>{if(confirm)cancel.current?.focus();},[confirm]);
  return <div className="refresh-setting wireless-setting">
    <label>Car Wi-Fi hotspot <span>{state.available?(state.enabled?'Enabled · 5 GHz':'Disabled'):'Available on the Pi'}</span></label>
    <button className="layout-reset" disabled={!state.available || busy} onClick={()=>setConfirm(true)}>{state.enabled?'Disable car hotspot':'Enable car hotspot'}</button>
    <p className="setting-note">The phone connects to the Pi for wireless Android Auto. No home router or internet connection is needed for the connection. Maps and streaming may still need mobile data.</p>
    {state.enabled && state.ssid && <p className="setting-note">Network: {state.ssid}. {standalone ? 'Pair your phone, then choose Connect Wi-Fi in Android Auto.' : 'Pair your phone with Hudiy, unplug USB, then choose Connect Wi-Fi.'}</p>}
    {confirm && <div className="customize-backdrop"><div className="customize-menu" role="dialog" aria-modal="true" aria-label="Change car Wi-Fi hotspot" onKeyDown={event=>{
      if(event.key==='Escape' && !busy){event.preventDefault();event.stopPropagation();setConfirm(false);}
      if(event.key==='Tab'){
        if(event.shiftKey && document.activeElement===cancel.current){event.preventDefault();apply.current?.focus();}
        else if(!event.shiftKey && document.activeElement===apply.current){event.preventDefault();cancel.current?.focus();}
      }
    }}>
      <strong>{state.enabled?'Disable':'Enable'} the car hotspot?</strong>
      <p>{standalone
        ? state.enabled ? 'Wireless Android Auto will disconnect. The dashboard stays running.' : 'The Pi’s current Wi-Fi connection can disconnect. Use Ethernet for remote maintenance; the touchscreen stays available.'
        : state.enabled ? 'Hudiy will restart and wireless Android Auto will disconnect.' : 'Hudiy will restart. The Pi’s current Wi-Fi connection can disconnect; use Ethernet for remote maintenance. You can still use the touchscreen and Quit stops the hotspot.'}</p>
      <button ref={cancel} disabled={busy} onClick={()=>setConfirm(false)}>Cancel</button>
      <button ref={apply} disabled={busy} onClick={async()=>{
        setBusy(true);try{const result=await action('wireless-hotspot',{enabled:!state.enabled,confirmed:true});if(result?.saved){setState(current=>({...current,enabled:!current.enabled}));setConfirm(false);}}
        finally{setBusy(false);}
      }}>{busy?'Applying…':standalone?'Apply':'Apply and restart'}</button>
    </div></div>}
  </div>;
}
