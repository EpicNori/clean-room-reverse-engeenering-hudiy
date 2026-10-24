import test from 'node:test';
import assert from 'node:assert/strict';
import {categoryLabel} from '../src/branding.mjs';
import {normalizeLayout} from '../src/layout.js';

test('renamed product displays coscarOS while retaining existing shortcut and menu ordering', () => {
  const saved = {taskbar:['contacts','custom-obd','apps'], menus:{Hudiy:['custom-obd','settings','marketplace']}};
  const result = normalizeLayout(saved);
  assert.equal(categoryLabel('Hudiy'), 'coscarOS');
  assert.equal(categoryLabel('Android Auto'), 'Android Auto');
  assert.deepEqual(result.taskbar.slice(0,3), saved.taskbar);
  assert.deepEqual(result.menus.Hudiy.slice(0,3), saved.menus.Hudiy);
  assert.deepEqual(normalizeLayout(JSON.parse(JSON.stringify(result))), result);
});
