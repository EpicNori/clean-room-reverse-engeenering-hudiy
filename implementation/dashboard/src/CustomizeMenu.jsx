import React, { useEffect, useRef } from 'react';
import { REQUIRED_SHORTCUTS, SHORTCUTS } from './layout';

export function CustomizeMenu({ item, layout, close, pin, remove, move, inline = false }) {
  const root = useRef(null);
  const shortcut = item.shortcut || item.id;
  const label = item.kind === 'card' ? { clock: 'Clock', navigation: 'Navigation', music: 'Music', phone: 'Phone' }[item.id] : SHORTCUTS[item.id]?.label;
  const column = ['clock', 'navigation'].includes(item.id) ? 'clock-navigation' : item.id;
  const list = item.kind === 'taskbar' ? layout.taskbar : item.kind === 'tile' ? layout.menus[item.group] : layout.columns;
  const moveId = item.kind === 'card' ? column : item.id;
  const index = list?.indexOf(moveId) ?? -1;
  useEffect(() => {
    root.current?.querySelector('button:not(:disabled)')?.focus();
    return () => { if (item.element?.isConnected) item.element.focus(); };
  }, [item]);
  const key = event => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); }
    if (event.key === 'Tab') {
      const buttons = [...root.current.querySelectorAll('button:not(:disabled)')];
      if (!buttons.length) return;
      const edge = event.shiftKey ? buttons[0] : buttons[buttons.length - 1];
      if (document.activeElement === edge) { event.preventDefault(); buttons[event.shiftKey ? buttons.length - 1 : 0].focus(); }
    }
  };
  const content = <div ref={root} className={inline ? 'taskbar-edit' : 'customize-menu'} role="dialog" aria-modal={!inline} aria-label={`Customize ${label}`} onKeyDown={key}>
    <strong>{label}</strong>
    {item.kind !== 'taskbar' && <button onClick={() => pin(shortcut)} disabled={layout.taskbar.includes(shortcut)}>
      <span className="material-symbols-rounded" aria-hidden="true">add</span>
      {layout.taskbar.includes(shortcut) ? 'Already in taskbar' : 'Add to taskbar'}
    </button>}
    {!inline && item.kind !== 'shortcut' && <p>Change {item.kind === 'taskbar' ? 'taskbar' : item.kind === 'tile' ? 'application' : 'dashboard'} position</p>}
    {item.kind !== 'shortcut' && <div className="customize-moves">
      <button aria-label="Move left" title="Move left" disabled={index <= 0} onClick={() => move(-1)}><span className="material-symbols-rounded">arrow_back</span>{!inline && 'Move left'}</button>
      <button aria-label="Move right" title="Move right" disabled={index < 0 || index >= list.length - 1} onClick={() => move(1)}><span className="material-symbols-rounded">arrow_forward</span>{!inline && 'Move right'}</button>
      {item.kind === 'card' && ['clock', 'navigation'].includes(item.id) && <button aria-label="Swap clock and navigation" onClick={() => move(1, 'leftCards')}><span className="material-symbols-rounded">swap_vert</span>Swap top / bottom</button>}
    </div>}
    {item.kind === 'taskbar' && <button aria-label="Remove from taskbar" title={REQUIRED_SHORTCUTS.includes(item.id) ? 'Keep this shortcut available for navigation' : 'Remove from taskbar'} disabled={REQUIRED_SHORTCUTS.includes(item.id)} onClick={() => remove(item.id)}><span className="material-symbols-rounded" aria-hidden="true">remove_circle_outline</span>{!inline && 'Remove from taskbar'}</button>}
    <button aria-label="Done customizing" className="customize-done" onClick={close}><span className="material-symbols-rounded" aria-hidden="true">check</span>{!inline && 'Done'}</button>
  </div>;
  return inline ? content : <div className="customize-backdrop" onClick={event => { if (event.target === event.currentTarget) close(); }}>{content}</div>;
}
