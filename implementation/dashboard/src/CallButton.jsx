import React, {useEffect,useRef,useState} from 'react';

export function CallButton({number,available,action,onAccepted}) {
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false);
  const cancel=useRef(null),confirm=useRef(null),trigger=useRef(null);
  useEffect(()=>{if(open)cancel.current?.focus();else trigger.current?.focus();},[open]);
  return <>
    <button ref={trigger} className="icon-button dial-call" aria-label="Call number" disabled={!available || !number} onClick={()=>setOpen(true)}>
      <span className="material-symbols-rounded" style={{fontSize:'calc(80 * var(--unit))'}} aria-hidden="true">call</span>
    </button>
    {open && <div className="customize-backdrop"><div className="customize-menu" role="dialog" aria-modal="true" aria-label="Confirm phone call" onKeyDown={event=>{
      if(event.key==='Escape' && !busy){event.stopPropagation();event.preventDefault();setOpen(false);}
      if(event.key==='Tab'){
        if(event.shiftKey && document.activeElement===cancel.current){event.preventDefault();confirm.current?.focus();}
        else if(!event.shiftKey && document.activeElement===confirm.current){event.preventDefault();cancel.current?.focus();}
      }
    }}>
      <strong>Call {number}?</strong><p>Place a real call through the connected phone.</p>
      <button ref={cancel} disabled={busy} onClick={()=>setOpen(false)}>Cancel</button>
      <button ref={confirm} disabled={busy || !available} onClick={async()=>{
        setBusy(true);try{const result=await action('phone-call',{number,confirmed:true});if(result?.accepted){setOpen(false);onAccepted();}}
        finally{setBusy(false);}
      }}>{busy?'Calling…':'Call'}</button>
    </div></div>}
  </>;
}
