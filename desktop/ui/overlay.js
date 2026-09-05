(() => {
  const BRAIN = "http://127.0.0.1:8765";
  const label = document.getElementById("core-label");
  const visual = document.getElementById("core-visual");
  const ring = document.getElementById("ring");

  function paint(hud) {
    const mode = (hud && hud.operational) || "standby";
    document.body.dataset.mode = mode;
    if (ring) ring.dataset.mode = mode;
    if (label) label.textContent = String(mode).toUpperCase();
    if (visual) visual.textContent = ((hud && hud.visual) || "jarvis").toUpperCase();
  }

  async function refresh() {
    try {
      const hud = await fetch(BRAIN + "/api/hud").then((r) => r.json());
      paint(hud);
    } catch {
      /* overlay stays last known */
    }
  }

  function bus() {
    try {
      const ws = new WebSocket(BRAIN.replace("http", "ws") + "/ws/bus");
      ws.onmessage = (ev) => {
        let data;
        try { data = JSON.parse(ev.data); } catch { return; }
        if (data && (data.type === "hud.set_mode" || data.type === "brain.status")) refresh();
      };
    } catch {
      /* ignore */
    }
  }

  refresh();
  bus();
  setInterval(refresh, 4000);
})();
