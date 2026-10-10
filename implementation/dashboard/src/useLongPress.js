import { useEffect, useRef } from 'react';

// Cancel on movement so touch panning and the mouse-drag scroll fallback win.
export function useLongPress(rootRef, open) {
  const callback = useRef(open);
  callback.current = open;
  useEffect(() => {
    const root = rootRef.current;
    let pending = null, timeout, suppressUntil = 0, fired = false;
    const clear = () => { clearTimeout(timeout); pending = null; };
    const target = event => event.target.closest('[data-layout-kind]');
    const show = node => {
      const { layoutKind: kind, layoutId: id, layoutGroup: group, layoutShortcut: shortcut } = node.dataset;
      suppressUntil = performance.now() + 800;
      fired = true;
      root.dispatchEvent(new Event('hudiy-customize'));
      callback.current({ kind, id, group, shortcut, element: node });
    };
    const down = event => {
      clear();
      fired = false;
      suppressUntil = 0;
      if (event.button !== 0 || !event.isPrimary || event.target.closest('input,textarea,select,[contenteditable="true"]')) return;
      const node = target(event);
      if (!node) return;
      pending = { node, id: event.pointerId, x: event.clientX, y: event.clientY };
      timeout = setTimeout(() => {
        if (!pending) return;
        show(pending.node);
        clear();
      }, 650);
    };
    const move = event => {
      if (pending && (event.pointerId !== pending.id || Math.hypot(event.clientX - pending.x, event.clientY - pending.y) >= 8)) clear();
    };
    const end = () => { clear(); if (fired) suppressUntil = performance.now() + 350; };
    const click = event => {
      if (performance.now() < suppressUntil) { event.preventDefault(); event.stopPropagation(); }
    };
    const context = event => {
      if (event.target.closest('input,textarea,select,[contenteditable="true"]')) return;
      const node = target(event);
      if (node) { event.preventDefault(); clear(); show(node); }
    };
    const key = event => {
      if (event.key !== 'ContextMenu' && !(event.shiftKey && event.key === 'F10')) return;
      context(event);
    };
    root.addEventListener('pointerdown', down);
    root.addEventListener('pointermove', move, { passive: true });
    root.addEventListener('pointerup', end);
    root.addEventListener('pointercancel', end);
    root.addEventListener('click', click, true);
    root.addEventListener('contextmenu', context);
    root.addEventListener('keydown', key);
    window.addEventListener('blur', end);
    root.addEventListener('scroll', end, true);
    return () => {
      clear();
      root.removeEventListener('pointerdown', down);
      root.removeEventListener('pointermove', move);
      root.removeEventListener('pointerup', end);
      root.removeEventListener('pointercancel', end);
      root.removeEventListener('click', click, true);
      root.removeEventListener('contextmenu', context);
      root.removeEventListener('keydown', key);
      window.removeEventListener('blur', end);
      root.removeEventListener('scroll', end, true);
    };
  }, [rootRef]);
}
