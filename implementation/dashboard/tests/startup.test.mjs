import test from 'node:test';
import assert from 'node:assert/strict';
import {startupIdentity,reportStartup} from '../src/startup.mjs';
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('only owned native surfaces with a bounded generation token acknowledge startup',()=>{
  assert.deepEqual(startupIdentity('?host=content&startup='+'a'.repeat(32)),{surface:'content',token:'a'.repeat(32)});
  for(const query of ['', '?host=content','?host=other&startup='+'a'.repeat(32),'?host=taskbar&startup=../file']) assert.equal(startupIdentity(query),null);
});
test('font readiness and two paint frames precede a successful native acknowledgement',async()=>{
  const events=[];let resolveFonts;
  const stop=reportStartup({surface:'taskbar',token:'a'.repeat(32)},{fonts:new Promise(resolve=>resolveFonts=resolve),paint:async()=>events.push('paint'),request:async payload=>{events.push(payload.surface);return true;}});
  await tick();assert.deepEqual(events,[]);
  resolveFonts();await tick();assert.deepEqual(events,['paint','paint','taskbar']);stop();
});
test('failed acknowledgement retries, and unmount cancels an owned retry',async()=>{
  let retry,cancelled,requests=0;
  const stop=reportStartup({surface:'content',token:'a'.repeat(32)},{fonts:Promise.resolve(),paint:async()=>{},request:async()=>++requests>1,later:callback=>{retry=callback;return 42;},cancel:value=>cancelled=value});
  await tick();assert.equal(requests,1);await retry();assert.equal(requests,2);stop();assert.equal(cancelled,42);
});
test('unmounted views never acknowledge a later font completion',async()=>{
  let resolveFonts,requests=0;
  const stop=reportStartup({surface:'content',token:'a'.repeat(32)},{fonts:new Promise(resolve=>resolveFonts=resolve),paint:async()=>{},request:async()=>{requests++;return true;}});
  stop();resolveFonts();await tick();assert.equal(requests,0);
});
