import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeLayout, moveItem, pinShortcut, DEFAULT_TASKBAR, REQUIRED_SHORTCUTS } from '../src/layout.js';

test('stored layout rejects unknown commands and duplicates while retaining navigation', () => {
  const result = normalizeLayout({ taskbar: ['contacts', 'contacts', 'shell', '../phone'], columns: ['phone', 'music', 'music'], menus: { Phone: ['dialpad', 'script'] } });
  assert.deepEqual(result.taskbar, ['contacts', ...REQUIRED_SHORTCUTS]);
  assert.deepEqual(result.columns, ['phone', 'music', 'clock-navigation']);
  assert.equal(result.menus.Phone[0], 'dialpad');
  assert.equal(result.menus.Phone.length, 5);
  assert.ok(!result.menus.Phone.includes('script'));
  assert.deepEqual(normalizeLayout(null).taskbar, DEFAULT_TASKBAR);
});

test('pinning does not duplicate and leaves Android Auto navigation reachable', () => {
  const initial = normalizeLayout({});
  const next = pinShortcut(initial, 'contacts');
  assert.equal(next.taskbar.indexOf('contacts') + 1, next.taskbar.indexOf('android-resume'));
  assert.equal(next.taskbar.length, initial.taskbar.length + 1);
  assert.equal(pinShortcut(next, 'contacts'), next);
  assert.equal(pinShortcut(next, 'shell'), next);
});

test('repositioning respects edges and survives persistence normalization', () => {
  const layout = normalizeLayout({});
  const taskbar = moveItem(layout.taskbar, 'apps', -1);
  assert.equal(taskbar[0], 'apps');
  assert.equal(moveItem(taskbar, 'apps', -1), taskbar);
  assert.equal(moveItem(taskbar, 'missing', 1), taskbar);
  const columns = moveItem(layout.columns, 'phone', -1);
  const persisted = normalizeLayout(JSON.parse(JSON.stringify({ ...layout, taskbar, columns, leftCards: ['navigation', 'clock'] })));
  assert.deepEqual(persisted.taskbar, taskbar);
  assert.deepEqual(persisted.columns, ['clock-navigation', 'phone', 'music']);
  assert.deepEqual(persisted.leftCards, ['navigation', 'clock']);
});
