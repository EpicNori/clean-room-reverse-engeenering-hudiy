import { menus } from './catalog.js';

export const LAYOUT_KEY = 'hudiy.layout.v1';
export const SHORTCUTS = Object.fromEntries([
  ['dashboard', { label: 'Dashboard', icon: 'grid_view' }],
  ['apps', { label: 'Applications', icon: 'apps' }],
  ['mute', { label: 'Mute', icon: 'volume_mute' }],
  ['volume-down', { label: 'Volume down', icon: 'volume_down' }],
  ['volume-up', { label: 'Volume up', icon: 'volume_up' }],
  ['connection-status', { label: 'Connection status', icon: 'bluetooth' }],
  ['clock', { label: 'Clock', icon: 'schedule' }],
  ['media-toggle', { label: 'Play / pause', icon: 'play_arrow' }],
  ['media-previous', { label: 'Previous track', icon: 'skip_previous' }],
  ['media-next', { label: 'Next track', icon: 'skip_next' }],
  ...Object.values(menus).flat().map(([label, icon, id]) => [id, { label, icon }]),
  ['android-resume', { label: 'Resume Android Auto', icon: 'navigation' }],
]);
export const REQUIRED_SHORTCUTS = ['dashboard', 'apps', 'android-resume'];
export const DEFAULT_TASKBAR = ['dashboard', 'apps', 'mute', 'volume-down', 'volume-up', 'android-resume', 'connection-status', 'clock'];
export const SCREEN_IDS = new Set(['dashboard', 'apps', 'settings', 'obd-settings', 'playlist', 'stations',
  ...Object.values(menus).flat().map(([, , id]) => id).filter(id => !['quit', 'android-usb', 'android-wifi', 'android-resume', 'android-quit', 'autobox-wifi', 'autobox-resume'].includes(id))]);

function order(value, allowed, complete = true) {
  const selected = Array.isArray(value) ? value.filter(id => typeof id === 'string' && allowed.includes(id)) : [];
  return [...new Set([...selected, ...(complete ? allowed : [])])];
}
export function normalizeLayout(value) {
  const raw = value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  const taskbar = order(Array.isArray(raw.taskbar) ? raw.taskbar : DEFAULT_TASKBAR, Object.keys(SHORTCUTS), false);
  return {
    taskbar: [...new Set([...taskbar, ...REQUIRED_SHORTCUTS])],
    columns: order(raw.columns, ['clock-navigation', 'music', 'phone']),
    leftCards: order(raw.leftCards, ['clock', 'navigation']),
    menus: Object.fromEntries(Object.entries(menus).map(([group, entries]) =>
      [group, order(raw.menus?.[group], entries.map(([, , id]) => id))])),
  };
}
export function readLayout() {
  try { return normalizeLayout(JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}')); }
  catch { return normalizeLayout({}); }
}
export function moveItem(items, id, delta) {
  const index = items.indexOf(id), next = index + delta;
  if (index < 0 || next < 0 || next >= items.length) return items;
  const result = [...items];
  [result[index], result[next]] = [result[next], result[index]];
  return result;
}
export function pinShortcut(layout, id) {
  if (!(id in SHORTCUTS) || layout.taskbar.includes(id)) return layout;
  const taskbar = [...layout.taskbar];
  const beforeProjection = taskbar.indexOf('android-resume');
  taskbar.splice(beforeProjection < 0 ? taskbar.length : beforeProjection, 0, id);
  return { ...layout, taskbar };
}

export function customizationAttributes(kind, id, group, shortcut) {
  return { 'data-layout-kind': kind, 'data-layout-id': id, 'data-layout-group': group, 'data-layout-shortcut': shortcut };
}
