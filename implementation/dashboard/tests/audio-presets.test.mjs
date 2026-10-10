import {test} from 'node:test';
import assert from 'node:assert/strict';
import {audioPresets} from '../src/audioPresets.mjs';

test('all audio presets are finite 15-band curves; Flat preserves the signal',()=>{
  for(const curve of Object.values(audioPresets)) {
    assert.equal(curve.length,15);
    assert.ok(curve.every(value=>Number.isFinite(value)&&Math.abs(value)<=12));
  }
  assert.ok(audioPresets.Flat.every(value=>value===0));
});
test('Bass boost targets low frequencies and Voice favors intelligibility over bass',()=>{
  const bass=audioPresets['Bass boost'];
  assert.ok(bass.slice(0,7).every(value=>value>0));
  assert.ok(bass.slice(7).every(value=>value===0));
  assert.ok(audioPresets.Voice.slice(0,4).every(value=>value<0));
  assert.ok(audioPresets.Voice.slice(8,11).every(value=>value>0));
});
