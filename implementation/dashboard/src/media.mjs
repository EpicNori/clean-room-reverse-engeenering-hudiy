const REMOTE_SCREENS = {android: 'android-music', bluetooth: 'a2dp'};
export const isRemotePlayer = screen => Object.values(REMOTE_SCREENS).includes(screen);

function seconds(label) {
  const parts = String(label || '').split(':').map(Number);
  return parts.length <= 3 && parts.every(n => Number.isFinite(n) && n >= 0)
    ? parts.reduce((sum, n) => sum * 60 + n, 0) : 0;
}

export function resolveMedia(local, remote = {}, screen) {
  const source = REMOTE_SCREENS[remote.source];
  const remoteSelected = source && (screen === source ||
    (screen === 'dashboard' && (isRemotePlayer(local.source) || (local.source === 'storage' && !local.title))));
  const empty = {source: isRemotePlayer(screen) ? screen : local.source, title: '', artist: '', album: '', playing: false, time: 0, duration: 0};
  const shownMedia = remoteSelected
    ? {...remote, source, time: seconds(remote.position), duration: seconds(remote.duration),
        timeKnown: /^\d+(?::\d{2}){0,2}$/.test(String(remote.position)),
        durationKnown: /^\d+(?::\d{2}){0,2}$/.test(String(remote.duration))}
    : isRemotePlayer(screen) || isRemotePlayer(local.source) ? empty : local;
  return {liveMedia: Boolean(remoteSelected), shownMedia,
    playerMedia: isRemotePlayer(screen) ? shownMedia : local};
}
