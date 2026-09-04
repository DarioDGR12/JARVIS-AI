(() => {
  const log = document.getElementById("log");
  const meta = document.getElementById("meta");
  const form = document.getElementById("f");
  const q = document.getElementById("q");
  const mute = document.getElementById("mute");
  const btn = form.querySelector("button");
  const views = {
    home: document.getElementById("home-view"),
    chat: document.getElementById("chat-view"),
    settings: document.getElementById("settings-view"),
    system: document.getElementById("system-view"),
    ha: document.getElementById("ha-view"),
    map: document.getElementById("map-view"),
    vision: document.getElementById("vision-view"),
  };
  const setupForm = document.getElementById("setup");
  const setupMsg = document.getElementById("setup-msg");
  const providerEl = document.getElementById("provider");
  const keyRow = document.getElementById("key-row");
  const baseRow = document.getElementById("base-row");

  const BRAIN = "http://127.0.0.1:8765";
  let currentView = "home";
  let busSocket = null;
  let mapFrame = null;
  let pendingMap = [];

  function tauri() {
    return window.__TAURI__ || null;
  }

  async function brainUrl() {
    const api = tauri();
    if (api && api.core && api.core.invoke) {
      try {
        return await api.core.invoke("brain_url");
      } catch {
        return BRAIN;
      }
    }
    return BRAIN;
  }

  function add(cls, text) {
    const hint = document.getElementById("hint");
    if (hint) hint.remove();
    const el = document.createElement("div");
    el.className = "msg " + cls;
    el.textContent = text;
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
  }

  function applyHud(hud) {
    if (!hud) return;
    const mode = hud.operational || "boot";
    const visual = hud.visual || "jarvis";
    document.body.dataset.mode = mode;
    document.body.dataset.visual = visual;
    document.body.dataset.view = hud.view || currentView;
    document.getElementById("mode-chip").textContent = mode;
    const ring = document.getElementById("ring");
    ring.dataset.mode = mode;
    document.getElementById("core-label").textContent = mode.toUpperCase();
    document.getElementById("core-visual").textContent = visual.toUpperCase();
    const card = hud.last_display;
    document.getElementById("display-title").textContent = card && card.title ? String(card.title) : "en espera";
    document.getElementById("display-body").textContent = card && card.content ? String(card.content) : "Sin eventos todavía.";
    document.getElementById("speak-body").textContent =
      hud.last_speak && hud.last_speak.text ? String(hud.last_speak.text) : "Silencio.";
    const list = document.getElementById("toast-list");
    list.replaceChildren();
    (hud.toasts || []).slice(-6).forEach((toast) => {
      const el = document.createElement("div");
      el.className = "toast" + (toast.kind === "alert" ? " alert" : "");
      el.textContent = (toast.title ? toast.title + " · " : "") + (toast.content || "");
      list.appendChild(el);
    });
  }

  function paintView(name) {
    currentView = name;
    Object.entries(views).forEach(([key, el]) => {
      if (el) el.hidden = key !== name;
    });
    document.body.dataset.view = name;
    document.querySelectorAll("#nav button").forEach((b) => {
      b.classList.toggle("on", b.dataset.view === name);
    });
    if (name === "system") loadSystem();
    if (name === "ha") loadHa();
    if (name === "map") mountMap();
    else unmountMap();
  }

  async function showView(name, opts) {
    const remote = opts && opts.remote;
    if (!views[name]) return;
    paintView(name);
    if (remote) return;
    try {
      const base = await brainUrl();
      await fetch(base + "/api/hud/view", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ view: name }),
      });
      await fetch(base + "/api/hud/click", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: "nav", id: name, method: "pointer" }),
      });
    } catch (err) {
      console.error("hud view", err);
    }
  }

  function syncProviderFields() {
    const id = providerEl.value;
    keyRow.hidden = id === "demo";
    baseRow.hidden = id !== "custom";
  }

  function handleBusEvent(ev) {
    if (!ev || !ev.type) return;
    if (ev.type === "hud.show_view" && ev.payload && ev.payload.view) {
      paintView(ev.payload.view);
    }
    if (ev.type === "map.focus" || ev.type === "map.query" || ev.type === "map.show_feeds") {
      sendToGlobe(ev);
    }
    if (ev.type === "hud.set_mode" || ev.type === "hud.display" || ev.type === "hud.speak"
      || ev.type === "hud.highlight" || ev.type === "brain.status" || ev.type === "persona.changed"
      || ev.type === "auth.challenge" || ev.type === "auth.result" || ev.type === "hud.ready") {
      refreshHud();
    }
  }

  function mapStatus(text) {
    const el = document.getElementById("map-status");
    if (el) el.textContent = text;
  }

  function sendToGlobe(ev) {
    if (!mapFrame || !mapFrame.contentWindow) {
      pendingMap.push(ev);
      return;
    }
    mapFrame.contentWindow.postMessage({ type: ev.type, payload: ev.payload || {} }, "*");
  }

  function onGlobeMessage(ev) {
    const data = ev.data || {};
    if (!data.type || String(data.type).indexOf("map.") !== 0) return;
    if (data.type === "map.ready") {
      mapStatus("listo · SENTINEL");
      pendingMap.splice(0).forEach(sendToGlobe);
    }
    if (data.type === "map.selection") {
      const p = data.payload || {};
      const sel = document.getElementById("map-sel");
      if (sel) sel.textContent = (p.feed_id || "") + " · " + (p.lat || "") + ", " + (p.lon || "");
    }
    if (data.type === "map.feed_ready") {
      mapStatus((data.payload && data.payload.count) + " pines");
    }
    brainUrl().then((base) => {
      fetch(base + "/api/bus", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: data.type,
          source: "sentinel",
          payload: data.payload || {},
        }),
      }).catch(() => {});
    });
  }

  function mountMap() {
    const slot = document.getElementById("map-slot");
    if (!slot) return;
    if (mapFrame && mapFrame.parentNode) return;
    mapFrame = document.createElement("iframe");
    mapFrame.src = "globe/index.html";
    mapFrame.title = "SENTINEL";
    mapFrame.setAttribute("allow", "");
    slot.appendChild(mapFrame);
    window.addEventListener("message", onGlobeMessage);
    mapStatus("montando…");
  }

  function unmountMap() {
    if (!mapFrame) return;
    window.removeEventListener("message", onGlobeMessage);
    if (mapFrame.contentWindow && mapFrame.contentWindow.JARVIS_GLOBE) {
      try { mapFrame.contentWindow.JARVIS_GLOBE.destroy(); } catch { /* ignore */ }
    }
    mapFrame.remove();
    mapFrame = null;
    pendingMap = [];
    mapStatus("sin montar");
    const sel = document.getElementById("map-sel");
    if (sel) sel.textContent = "";
  }

  async function refreshHud() {
    try {
      const base = await brainUrl();
      const hud = await fetch(base + "/api/hud").then((r) => r.json());
      applyHud(hud);
    } catch (err) {
      console.error("hud", err);
    }
  }

  async function connectBus(base) {
    const wsUrl = base.replace(/^http/, "ws") + "/ws/bus";
    if (busSocket && busSocket.readyState < 2) return;
    try {
      const ws = new WebSocket(wsUrl);
      busSocket = ws;
      ws.onmessage = (msg) => {
        try {
          handleBusEvent(JSON.parse(msg.data));
        } catch {
          /* ignore malformed bus frames */
        }
      };
      ws.onclose = () => {
        if (busSocket === ws) busSocket = null;
      };
    } catch (err) {
      console.error("bus", err);
    }
  }

  async function refresh() {
    try {
      const base = await brainUrl();
      const s = await fetch(base + "/api/status").then((r) => r.json());
      const p = s.product || {};
      const mode = p.mode === "byok" ? "BYOK " + (p.provider || "") : (p.mode || "demo");
      const auth = s.auth && s.auth.enrolled ? "howdy" : "sin howdy";
      const hud = s.hud || {};
      meta.textContent = (s.ok ? "en línea" : "Hermes caído") + " · " + mode
        + (s.tts ? " · voz " + s.tts : " · sin voz") + " · " + auth
        + " · HUD " + (hud.operational || "?");
      if (p.provider) providerEl.value = p.provider;
      if (p.model) document.getElementById("model").value = p.model;
      if (p.base_url) document.getElementById("base-url").value = p.base_url;
      syncProviderFields();
      applyHud(hud);
      await connectBus(base);
    } catch (err) {
      meta.textContent = "cerebro no responde";
      console.error("status", err);
    }
  }

  async function markReady() {
    try {
      const base = await brainUrl();
      await fetch(base + "/api/hud/ready", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          camera: false,
          viewport: { w: window.innerWidth, h: window.innerHeight },
        }),
      });
    } catch (err) {
      console.error("hud ready", err);
    }
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const text = q.value.trim();
    if (!text) return;
    q.value = "";
    add("you", text);
    btn.disabled = true;
    try {
      const base = await brainUrl();
      const r = await fetch(base + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await r.json();
      if (!data.ok) throw new Error(data.error || r.statusText);
      add("jarvis", data.reply || "(sin texto)");
      applyHud(data.hud);
      if (data.audio_wav_b64 && !mute.checked) {
        const audio = new Audio("data:audio/wav;base64," + data.audio_wav_b64);
        audio.play().catch(() => {});
      }
    } catch (err) {
      add("err", String(err.message || err));
    } finally {
      btn.disabled = false;
      q.focus();
    }
  });

  setupForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setupMsg.textContent = "guardando…";
    const body = {
      provider: providerEl.value,
      api_key: document.getElementById("api-key").value,
      model: document.getElementById("model").value || null,
      base_url: document.getElementById("base-url").value || null,
    };
    try {
      const base = await brainUrl();
      const r = await fetch(base + "/api/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!data.ok) throw new Error(data.error || r.statusText);
      setupMsg.textContent = "Guardado · " + (data.product.mode || "") + " · " + (data.product.model || "");
      document.getElementById("api-key").value = "";
      await refresh();
    } catch (err) {
      setupMsg.textContent = String(err.message || err);
    }
  });

  async function loadSystem() {
    try {
      const base = await brainUrl();
      const s = await fetch(base + "/api/system").then((r) => r.json());
      document.getElementById("sys-stats").textContent = JSON.stringify(s.stats, null, 2);
      const a = s.auth || {};
      document.getElementById("auth-line").textContent =
        "Howdy: " + (a.enrolled ? "compare.py listo" : "no instalado") +
        " · cámara " + (a.camera || "?") +
        (a.compare_path ? " · " + a.compare_path : "");
    } catch (err) {
      document.getElementById("sys-stats").textContent = String(err);
    }
  }

  async function loadHa() {
    const box = document.getElementById("ha-states");
    box.textContent = "";
    try {
      const base = await brainUrl();
      const s = await fetch(base + "/api/ha/states").then((r) => r.json());
      if (!s.ok) {
        document.getElementById("ha-msg").textContent = s.error || "HA no configurado";
        return;
      }
      document.getElementById("ha-msg").textContent = (s.states || []).length + " entidades";
      (s.states || []).forEach((ent) => {
        const row = document.createElement("div");
        row.className = "entity";
        row.innerHTML = "<span>" + (ent.name || ent.entity_id) + "</span><span>" + (ent.state || "") + "</span>";
        if (String(ent.entity_id || "").startsWith("light.") || String(ent.entity_id || "").startsWith("switch.")) {
          const toggle = document.createElement("button");
          toggle.textContent = "toggle";
          toggle.onclick = async () => {
            const domain = ent.entity_id.split(".")[0];
            const r = await fetch(base + "/api/ha/call", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ domain, service: "toggle", entity_id: ent.entity_id }),
            });
            const data = await r.json();
            document.getElementById("ha-msg").textContent = data.ok ? "ok" : (data.error || "fail");
            await refreshHud();
            loadHa();
          };
          row.appendChild(toggle);
        }
        box.appendChild(row);
      });
    } catch (err) {
      document.getElementById("ha-msg").textContent = String(err);
    }
  }

  document.getElementById("ha-setup").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const base = await brainUrl();
    const r = await fetch(base + "/api/ha/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: document.getElementById("ha-url").value,
        token: document.getElementById("ha-token").value,
      }),
    });
    const data = await r.json();
    document.getElementById("ha-msg").textContent = data.ok ? "HA guardado" : (data.error || "fail");
    document.getElementById("ha-token").value = "";
    if (data.ok) loadHa();
  });

  providerEl.addEventListener("change", syncProviderFields);
  document.getElementById("btn-settings").addEventListener("click", () => showView("settings"));
  document.getElementById("btn-back").addEventListener("click", () => showView("home"));
  document.querySelectorAll("#nav button").forEach((b) => {
    b.addEventListener("click", () => showView(b.dataset.view));
  });

  function wireWindow() {
    const api = tauri();
    if (!api || !api.webviewWindow) return;
    const win = api.webviewWindow.getCurrentWebviewWindow();
    document.getElementById("btn-min").onclick = () => win.minimize();
    document.getElementById("btn-max").onclick = () => win.toggleMaximize();
    document.getElementById("btn-close").onclick = () => win.close();
  }

  wireWindow();
  markReady();
  refresh();
  setInterval(refresh, 8000);
  q.focus();
})();
