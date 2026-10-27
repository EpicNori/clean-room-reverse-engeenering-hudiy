import { useEffect } from "react";

// Native touch scrolls in the browser. labwc can also emit mouse events for a
// touchscreen, so mouse drags need the same scrolling behavior.
export function useDragScroll(rootRef) {
  useEffect(() => {
    const root = rootRef.current;
    let gesture = null;
    let suppressUntil = 0;
    const findScrollArea = (target) => {
      for (
        let node = target;
        node && node !== root;
        node = node.parentElement
      ) {
        const style = getComputedStyle(node);
        const x =
          /auto|scroll/.test(style.overflowX) &&
          node.scrollWidth > node.clientWidth + 1;
        const y =
          /auto|scroll/.test(style.overflowY) &&
          node.scrollHeight > node.clientHeight + 1;
        if (x || y) return { node, x, y };
      }
      return null;
    };
    const down = (event) => {
      gesture = null;
      suppressUntil = 0;
      root.classList.remove("drag-scrolling");
      if (event.pointerType !== "mouse" || event.button !== 0) return;
      if (
        event.target.closest('input,textarea,select,[contenteditable="true"],[data-obd-drag-handle],[data-dashboard-drag-handle]')
      )
        return;
      const area = findScrollArea(event.target);
      if (area)
        gesture = {
          ...area,
          id: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          left: area.node.scrollLeft,
          top: area.node.scrollTop,
          dragging: false,
        };
    };
    const move = (event) => {
      if (!gesture || event.pointerId !== gesture.id) return;
      const dx = event.clientX - gesture.startX,
        dy = event.clientY - gesture.startY;
      const distance = Math.max(
        gesture.x ? Math.abs(dx) : 0,
        gesture.y ? Math.abs(dy) : 0,
      );
      if (!gesture.dragging && distance < 8) return;
      if (!gesture.dragging) {
        gesture.dragging = true;
        gesture.node.setPointerCapture(event.pointerId);
        root.classList.add("drag-scrolling");
        window.getSelection()?.removeAllRanges();
      }
      event.preventDefault();
      if (gesture.x) gesture.node.scrollLeft = gesture.left - dx;
      if (gesture.y) gesture.node.scrollTop = gesture.top - dy;
    };
    const end = (event) => {
      if (!gesture || event.pointerId !== gesture.id) return;
      if (gesture.dragging) {
        suppressUntil = performance.now() + 350;
        if (gesture.node.hasPointerCapture(event.pointerId))
          gesture.node.releasePointerCapture(event.pointerId);
      }
      gesture = null;
      root.classList.remove("drag-scrolling");
    };
    const click = (event) => {
      if (performance.now() < suppressUntil) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    const cancel = () => {
      if (gesture?.node.hasPointerCapture(gesture.id)) gesture.node.releasePointerCapture(gesture.id);
      gesture = null;
      root.classList.remove('drag-scrolling');
    };
    root.addEventListener("pointerdown", down);
    root.addEventListener("pointermove", move, { passive: false });
    root.addEventListener("pointerup", end);
    root.addEventListener("pointercancel", end);
    root.addEventListener("click", click, true);
    root.addEventListener('hudiy-customize', cancel);
    return () => {
      root.removeEventListener("pointerdown", down);
      root.removeEventListener("pointermove", move);
      root.removeEventListener("pointerup", end);
      root.removeEventListener("pointercancel", end);
      root.removeEventListener("click", click, true);
      root.removeEventListener('hudiy-customize', cancel);
      root.classList.remove("drag-scrolling");
    };
  }, [rootRef]);
}
