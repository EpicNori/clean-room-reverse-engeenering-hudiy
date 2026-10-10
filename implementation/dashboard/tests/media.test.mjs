import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveMedia} from '../src/media.mjs';

const local = {source:'storage',title:'',playing:false,time:0,duration:0};
const bluetooth = {source:'bluetooth',title:'Phone track',artist:'Artist',album:'Album',position:'01:23',duration:'04:56',playing:true,coverart:true,coverartVersion:3};

test('dashboard and Bluetooth player follow the active phone source and reported timeline', () => {
  for (const screen of ['dashboard','a2dp']) {
    const resolved = resolveMedia(local,bluetooth,screen);
    assert.equal(resolved.liveMedia,true);
    assert.equal(resolved.shownMedia.source,'a2dp');
    assert.equal(resolved.shownMedia.time,83);
    assert.equal(resolved.shownMedia.duration,296);
    assert.equal(resolved.shownMedia.coverartVersion,3);
  }
  const switched = resolveMedia({...local,source:'android-music'},bluetooth,'dashboard');
  assert.equal(switched.shownMedia.source,'a2dp');
});

test('a selected local file keeps ownership of its dashboard and storage controls', () => {
  const selected = {...local,title:'Local file',time:17,duration:99,playing:true};
  const resolved = resolveMedia(selected,bluetooth,'dashboard');
  assert.equal(resolved.liveMedia,false);
  assert.equal(resolved.shownMedia,selected);
  assert.equal(resolveMedia(selected,bluetooth,'storage').playerMedia,selected);
});

test('remote player mismatch or disconnect clears title/artwork and never exposes local-file state', () => {
  for (const remote of [{...bluetooth,source:'android'},{}]) {
    const resolved = resolveMedia({...local,title:'Local file',playing:true,time:99},remote,'a2dp');
    assert.equal(resolved.liveMedia,false);
    assert.equal(resolved.playerMedia.title,'');
    assert.equal(resolved.playerMedia.playing,false);
    assert.equal(resolved.playerMedia.time,0);
    assert.equal(resolved.playerMedia.coverart,undefined);
  }
  const resolved = resolveMedia({...local,source:'a2dp',title:'Old Bluetooth title'}, {}, 'dashboard');
  assert.equal(resolved.shownMedia.title,'');
});

test('Android Auto remains separate and malformed timelines display zero', () => {
  const resolved = resolveMedia(local,{...bluetooth,source:'android',position:'bad',duration:'1:02:03'},'android-music');
  assert.equal(resolved.liveMedia,true);
  assert.equal(resolved.playerMedia.source,'android-music');
  assert.equal(resolved.playerMedia.time,0);
  assert.equal(resolved.playerMedia.duration,3723);
});

test('missing Android Auto timelines are explicitly unknown while controls remain finite', () => {
  const resolved = resolveMedia(local,{source:'android',title:'Phone track',position:'00:57',duration:'—'},'dashboard');
  assert.equal(resolved.shownMedia.time,57);
  assert.equal(resolved.shownMedia.timeKnown,true);
  assert.equal(resolved.shownMedia.duration,0);
  assert.equal(resolved.shownMedia.durationKnown,false);
});
