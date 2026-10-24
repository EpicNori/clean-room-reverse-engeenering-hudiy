import React,{useEffect,useState} from 'react';

export function LicenseNotices(){
  const [open,setOpen]=useState(false),[text,setText]=useState(''),[error,setError]=useState(false),[retry,setRetry]=useState(0);
  useEffect(()=>{
    if(!open || text)return;
    let closed=false;const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
    setError(false);
    (async()=>{
      try{
        const response=await fetch('/THIRD_PARTY_NOTICES.txt',{signal:controller.signal});
        if(!response.ok || !response.headers.get('content-type')?.startsWith('text/plain'))throw Error();
        const value=await response.text();
        if(!value || value.length>512*1024)throw Error();
        if(!closed)setText(value);
      }catch{if(!closed)setError(true);}
      finally{clearTimeout(timer);}
    })();
    return()=>{closed=true;clearTimeout(timer);controller.abort();};
  },[open,text,retry]);
  return <details className="license-notices" onToggle={event=>setOpen(event.currentTarget.open)}>
    <summary>Open-source licenses and font credits</summary>
    {open && (text ? <pre tabIndex={0} aria-label="License texts">{text}</pre> : <div role="status">
      {error ? <>License notices could not be loaded.<button className="layout-reset" onClick={()=>setRetry(v=>v+1)}>Retry loading notices</button></> : 'Loading license notices…'}
    </div>)}
  </details>;
}
