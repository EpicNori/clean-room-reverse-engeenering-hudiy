const SWITCHES = {output: 'outputNotice', input: 'inputNotice', track: 'nowPlayingNotice'};
export function noticeEnabled(prefs, kind) {
  if (prefs.notificationsEnabled === false) return false;
  if (kind === 'toast') return prefs.toastNotice !== false;
  return kind in SWITCHES && Boolean(prefs[SWITCHES[kind]]);
}

export function mutedNoticeKinds(prefs) {
  return ['toast', ...Object.keys(SWITCHES)].filter(kind => !noticeEnabled(prefs, kind));
}

export function noticeSeconds(prefs, kind) {
  const value = prefs[kind === 'toast' ? 'toastDuration' : 'notificationDuration'];
  return Number.isInteger(value) && value >= 1 && value <= 15 ? value : kind === 'toast' ? 2 : 8;
}

// One transient notice, no history or queue of phone data.
export class NoticeCenter {
  constructor(preferences, emit, schedule = (fn, delay) => setTimeout(fn, delay), cancel = id => clearTimeout(id)) {
    Object.assign(this, {preferences, emit, schedule, cancel, current: null, timer: null});
  }
  show(kind, text) {
    if (!noticeEnabled(this.preferences(), kind)) return false;
    if (kind === 'track' && this.current && this.current.kind !== 'track') return false;
    const message = Array.from(String(text || '').trim()).slice(0, 256).join('');
    if (!message) return false;
    this.cancel(this.timer);
    const notice = {kind, message, duration: noticeSeconds(this.preferences(), kind)};
    this.current = notice;
    this.emit(notice);
    this.timer = this.schedule(() => {
      if (this.current === notice) { this.current = null; this.emit({...notice, message: '', expired: true}); }
    }, notice.duration * 1000);
    return true;
  }
  sync() {
    if (this.current && !noticeEnabled(this.preferences(), this.current.kind)) {
      this.cancel(this.timer);
      const notice = this.current; this.current = null;
      this.emit({...notice, message: ''});
    }
  }
  dispose() { this.cancel(this.timer); this.current = null; }
}

// Position, cover-art polling and pause/resume are not new tracks. A disconnect
// keeps the last identity, so reconnecting the same track does not announce it.
export class TrackObserver {
  constructor() { this.identity = ''; }
  observe(local, remote) {
    const track = local?.playing && local?.title ? local : remote?.playing ? remote : local;
    if (!track?.playing || !String(track.title || '').trim()) return null;
    const identity = JSON.stringify([track.source, track.title, track.artist || '', track.album || '']);
    if (identity === this.identity) return null;
    this.identity = identity;
    return [track.title, track.artist].filter(Boolean).join(' · ');
  }
}
