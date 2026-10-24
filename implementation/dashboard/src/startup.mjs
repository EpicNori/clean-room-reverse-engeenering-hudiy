// Readiness is reported only by the two owned native web views after layout and paint.
export function startupIdentity(search) {
  const query = new URLSearchParams(search), surface = query.get('host'), token = query.get('startup');
  return ['content', 'taskbar'].includes(surface) && /^[a-f0-9]{32}$/.test(token || '') ? {surface, token} : null;
}

export function reportStartup(identity, {fonts, paint, request, later = setTimeout, cancel = clearTimeout}) {
  let stopped = false, timer, attempts = 0;
  const send = async () => {
    if (stopped) return;
    try {
      if (await request({action: 'startup-ready', ...identity})) return;
    } catch {}
    if (!stopped && ++attempts < 60) timer = later(send, 1000);
  };
  Promise.resolve(fonts).then(async () => {
    await paint(); await paint();
    if (!stopped) await send();
  }).catch(() => { /* The native recovery screen handles renderer/font failures. */ });
  return () => {stopped = true; cancel(timer);};
}
