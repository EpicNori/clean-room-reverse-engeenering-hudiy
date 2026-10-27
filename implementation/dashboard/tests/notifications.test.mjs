import test from 'node:test';
import assert from 'node:assert/strict';
import {NoticeCenter, TrackObserver, noticeSeconds, mutedNoticeKinds} from '../src/notifications.mjs';

function fixture() {
  const prefs = {outputNotice: true, inputNotice: true, nowPlayingNotice: true, notificationDuration: 8, toastDuration: 2};
  let next = 0; const timers = new Map(), notices = [];
  const center = new NoticeCenter(() => prefs, n => notices.push(n), (fn, delay) => {timers.set(++next, {fn, delay}); return next;}, id => timers.delete(id));
  return {prefs, timers, notices, center};
}
test('switches suppress only their notifications; errors retain toast duration', () => {
  const {prefs, center, notices, timers} = fixture();
  for (const [kind, key] of [['output','outputNotice'], ['input','inputNotice'], ['track','nowPlayingNotice']]) {
    prefs[key] = false; assert.equal(center.show(kind, 'Hidden'), false);
  }
  assert.equal(notices.length, 0);
  center.show('toast', 'Hardware unavailable');
  assert.equal([...timers.values()][0].delay, 2000);
  assert.equal(notices[0].message, 'Hardware unavailable');
});
test('replacement cancels old timeout, configured duration expires, disabling clears', () => {
  const {prefs, center, notices, timers} = fixture();
  center.show('output', 'Volume 80'); const old = [...timers.values()][0].fn;
  prefs.notificationDuration = 3; center.show('output', 'Volume 85');
  assert.equal(timers.size, 1); assert.equal([...timers.values()][0].delay, 3000);
  old(); assert.equal(notices.at(-1).message, 'Volume 85');
  [...timers.values()][0].fn(); assert.equal(notices.at(-1).message, '');
  center.show('input', 'Input muted'); prefs.inputNotice = false; center.sync();
  assert.equal(notices.at(-1).message, ''); assert.equal(timers.size, 0);
});
test('track notices never displace volume/errors and unmount cancels timers', () => {
  const {center, timers, notices} = fixture();
  center.show('output', 'Volume 80'); assert.equal(center.show('track', 'Song'), false);
  center.show('toast', 'Failure'); assert.equal(notices.at(-1).message, 'Failure');
  center.dispose(); assert.equal(timers.size, 0);
});
test('invalid stored durations fall back, long messages stay bounded', () => {
  for (const n of [0, -1, 16, 1.5, NaN, Infinity, '8']) {
    assert.equal(noticeSeconds({notificationDuration:n}, 'output'), 8);
    assert.equal(noticeSeconds({toastDuration:n}, 'toast'), 2);
  }
  const {center, notices} = fixture(); center.show('track', 'a'.repeat(1000));
  assert.equal(notices[0].message.length, 256);
});
test('music announces new identities once, consumes disabled updates, honors playing local files', () => {
  const observer = new TrackObserver();
  const remote = {source:'android', title:'One', artist:'Artist', album:'Album', playing:true};
  assert.equal(observer.observe({}, remote), 'One · Artist');
  assert.equal(observer.observe({}, {...remote, position:'00:21', coverartVersion:5}), null);
  assert.equal(observer.observe({}, {...remote, playing:false}), null);
  assert.equal(observer.observe({}, remote), null);
  assert.equal(observer.observe({}, {}), null);
  assert.equal(observer.observe({}, remote), null);
  const {center,prefs,notices}=fixture(); prefs.nowPlayingNotice=false;
  center.show('track', observer.observe({}, {...remote,title:'Two'}));
  prefs.nowPlayingNotice=true; assert.equal(observer.observe({}, {...remote,title:'Two'}),null);
  assert.equal(notices.length,0);
  assert.equal(observer.observe({source:'storage',title:'Local',playing:true},remote),'Local');
  assert.equal(observer.observe({}, {...remote,source:'bluetooth'}), 'One · Artist');
});

test('default timers do not bind browser functions to the NoticeCenter instance', () => {
  const before = {setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout};
  let scheduled = false;
  try {
    globalThis.setTimeout = function () { assert.equal(this instanceof NoticeCenter, false); scheduled = true; return 42; };
    globalThis.clearTimeout = function () { assert.equal(this instanceof NoticeCenter, false); };
    const center = new NoticeCenter(() => ({outputNotice:true}), () => {});
    center.show('output','Volume 80'); assert.equal(scheduled,true); center.dispose();
  } finally { Object.assign(globalThis, before); }
});
test('stored duration values are bounded before rendering or scheduling', async () => {
  const {readPreferences} = await import('../src/catalog.js');
  const previous = globalThis.localStorage;
  try {
    globalThis.localStorage = {getItem: () => JSON.stringify({notificationDuration:1e9,toastDuration:0})};
    assert.equal(readPreferences().notificationDuration,8); assert.equal(readPreferences().toastDuration,2);
    globalThis.localStorage = {getItem: () => JSON.stringify({notificationDuration:15,toastDuration:1})};
    assert.equal(readPreferences().notificationDuration,15); assert.equal(readPreferences().toastDuration,1);
  } finally { if (previous === undefined) delete globalThis.localStorage; else globalThis.localStorage = previous; }
});

test('long Unicode track names stay bounded without splitting surrogate pairs', () => {
  const {center,notices}=fixture(); center.show('track','🎵'.repeat(300));
  assert.equal(Array.from(notices[0].message).length,256);
  assert.equal(notices[0].message,'🎵'.repeat(256));
});


test('master mute suppresses every popup and clears an active general message without queuing', () => {
  const {prefs, center, notices, timers} = fixture();
  center.show('toast', 'Update available');
  prefs.notificationsEnabled = false;
  center.sync();
  assert.equal(center.current, null);
  assert.equal(notices.at(-1).message, '');
  assert.equal(timers.size, 0);
  const count = notices.length;
  for (const kind of ['toast', 'output', 'input', 'track']) {
    assert.equal(center.show(kind, 'Muted'), false);
  }
  assert.equal(notices.length, count);
  assert.equal(timers.size, 0);
  assert.deepEqual(mutedNoticeKinds(prefs), ['toast', 'output', 'input', 'track']);
  assert.equal(prefs.outputNotice, true);
  prefs.notificationsEnabled = true;
  assert.equal(center.show('output', 'Volume 40'), true);
  assert.equal(notices.at(-1).message, 'Volume 40');
});

test('general messages can be muted separately and native clearing includes toasts', () => {
  const {prefs, center, notices} = fixture();
  center.show('toast', 'Saved');
  prefs.toastNotice = false;
  center.sync();
  assert.equal(notices.at(-1).message, '');
  assert.equal(center.show('toast', 'Saved again'), false);
  assert.deepEqual(mutedNoticeKinds(prefs), ['toast']);
  assert.equal(center.show('output', 'Volume 60'), true);
  prefs.nowPlayingNotice = false;
  assert.deepEqual(mutedNoticeKinds(prefs), ['toast', 'track']);
});

test('master and general popup choices survive reload and ignore invalid stored types', async () => {
  const {readPreferences} = await import('../src/catalog.js');
  const previous = globalThis.localStorage;
  let stored = '{}';
  try {
    globalThis.localStorage = {getItem: () => stored};
    assert.equal(readPreferences().notificationsEnabled, true);
    assert.equal(readPreferences().toastNotice, true);
    stored = JSON.stringify({...readPreferences(), notificationsEnabled:false, toastNotice:false, outputNotice:false});
    const loaded = readPreferences();
    assert.equal(loaded.notificationsEnabled, false);
    assert.equal(loaded.toastNotice, false);
    assert.equal(loaded.outputNotice, false);
    assert.deepEqual(mutedNoticeKinds(loaded), ['toast', 'output', 'input', 'track']);
    stored = JSON.stringify({notificationsEnabled:'false',toastNotice:0});
    assert.equal(readPreferences().notificationsEnabled, true);
    assert.equal(readPreferences().toastNotice, true);
  } finally { if (previous === undefined) delete globalThis.localStorage; else globalThis.localStorage = previous; }
});
