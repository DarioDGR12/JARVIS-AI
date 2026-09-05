(() => {
  /* Two-pointer pinch/spread. Reimplemented; not copied from jarvis-hud.
     MediaPipe Hands stays optional and off-CDN. Edges only. */
  const pointers = new Map();
  let lastDist = null;
  let lastKind = "";
  let lastAt = 0;

  function distance() {
    if (pointers.size < 2) return null;
    const pts = Array.from(pointers.values());
    const dx = pts[0].x - pts[1].x;
    const dy = pts[0].y - pts[1].y;
    return Math.hypot(dx, dy);
  }

  function emit(kind, extra) {
    const now = Date.now();
    if (kind === lastKind && now - lastAt < 420) return;
    lastKind = kind;
    lastAt = now;
    const api = window.jarvisHud;
    if (api && typeof api.gesture === "function") {
      api.gesture(kind, extra || {});
    }
  }

  function onMove() {
    const d = distance();
    if (d == null) {
      lastDist = null;
      return;
    }
    if (lastDist == null || lastDist < 8) {
      lastDist = d;
      return;
    }
    const ratio = d / lastDist;
    if (ratio < 0.88) emit("pinch", { dist: d, prev: lastDist, hand: "both", confidence: 0.8 });
    else if (ratio > 1.12) emit("spread", { dist: d, prev: lastDist, hand: "both", confidence: 0.8 });
    lastDist = d;
  }

  window.addEventListener("pointerdown", (ev) => {
    pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
  }, { passive: true });
  window.addEventListener("pointermove", (ev) => {
    if (!pointers.has(ev.pointerId)) return;
    pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    onMove();
  }, { passive: true });
  function drop(ev) {
    pointers.delete(ev.pointerId);
    if (pointers.size < 2) lastDist = null;
  }
  window.addEventListener("pointerup", drop, { passive: true });
  window.addEventListener("pointercancel", drop, { passive: true });
})();
