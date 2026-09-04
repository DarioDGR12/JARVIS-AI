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
  const CAM_DEVICE_KEY = "jarvis.cam.device";
  let camStream = null;
  let camBlocked = false;
  let camMissing = false;
  let camBusy = false;
  let camHoldReleased = false;
  let camStarting = false;
  let lastCamDevice = "";
  try { lastCamDevice = localStorage.getItem(CAM_DEVICE_KEY) || ""; } catch { lastCamDevice = ""; }

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
    applyCamFromHud(hud);
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
    if (name === "vision") refreshVision();
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
      || ev.type === "auth.challenge" || ev.type === "auth.result" || ev.type === "hud.ready"
      || ev.type === "hud.camera" || ev.type === "vision.screen_context" || ev.type === "vision.error"
      || ev.type === "vision.watch") {
      refreshHud();
    }
    if (ev.type === "hud.camera") applyCamFromHud(ev.payload || {});
    if (String(ev.type).indexOf("vision.") === 0) refreshVision();
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

  function bindCamVideos() {
    ["cam-home", "cam-vision"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.srcObject = camStream;
      el.muted = true;
      el.playsInline = true;
      if (camStream) el.play().catch(() => {});
    });
  }

  function setCamBadges() {
    const hold = document.body.classList.contains("cam-hold");
    const on = document.body.classList.contains("cam-on") || camHoldReleased;
    document.querySelectorAll(".cam-badge").forEach((el) => {
      el.textContent = hold ? "HOLD" : (on ? "LIVE" : "OFF");
    });
  }

  function patchMetaCam() {
    const el = document.getElementById("meta");
    if (!el) return;
    const hold = document.body.classList.contains("cam-hold");
    const on = document.body.classList.contains("cam-on") || camHoldReleased;
    const token = hold ? "cam hold" : (on ? "cam" : "sin cam");
    el.textContent = el.textContent.replace(/ · [^·]+ · HUD /, " · " + token + " · HUD ");
  }

  function setCamUi({ on, msg, empty }) {
    if (on !== undefined) document.body.classList.toggle("cam-on", !!on);
    const btnCam = document.getElementById("btn-cam");
    const btnHome = document.getElementById("btn-cam-home");
    const hold = document.body.classList.contains("cam-hold");
    const live = document.body.classList.contains("cam-on") || camHoldReleased;
    if (btnCam) {
      btnCam.disabled = hold;
      btnCam.textContent = hold ? "En hold" : (live ? "Apagar cámara" : "Encender cámara");
    }
    if (btnHome) {
      btnHome.disabled = hold;
      btnHome.textContent = hold ? "Hold" : (live ? "Apagar" : "Encender");
    }
    if (msg !== undefined) {
      const el = document.getElementById("cam-msg");
      if (el) el.textContent = msg;
    }
    if (empty !== undefined) {
      ["cam-vision-empty", "cam-home-empty"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.textContent = empty;
      });
    }
    setCamBadges();
    patchMetaCam();
  }

  function camErrorText(err) {
    const name = (err && err.name) || "";
    if (name === "NotAllowedError" || name === "PermissionDeniedError") return "permiso denegado";
    if (name === "NotFoundError" || name === "OverconstrainedError") return "no hay cámara en este equipo";
    if (name === "NotReadableError" || name === "TrackStartError") return "cámara ocupada (Howdy u otra app)";
    if (name === "SecurityError") return "contexto no seguro";
    if (name === "AbortError") return "solicitud cancelada";
    return String((err && err.message) || err || "error de cámara");
  }

  async function listCamDevices() {
    const sel = document.getElementById("cam-device");
    if (!sel || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
    try {
      const videos = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
      const prev = sel.value || lastCamDevice;
      sel.replaceChildren();
      const def = document.createElement("option");
      def.value = "";
      def.textContent = videos.length ? "Cámara por defecto" : "Sin dispositivos";
      sel.appendChild(def);
      videos.forEach((d, i) => {
        const opt = document.createElement("option");
        opt.value = d.deviceId;
        opt.textContent = d.label || ("Cámara " + (i + 1));
        sel.appendChild(opt);
      });
      if (prev && videos.some((d) => d.deviceId === prev)) sel.value = prev;
      sel.hidden = videos.length <= 1;
    } catch {
      /* ignore */
    }
  }

  async function startCam() {
    if (camStarting) return !!camStream;
    if (camStream) {
      bindCamVideos();
      setCamUi({ on: true, msg: "cámara en vivo", empty: "sin cámara" });
      return true;
    }
    if (camBlocked || camMissing) return false;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      camMissing = true;
      setCamUi({ on: false, msg: "getUserMedia no disponible", empty: "sin API de cámara" });
      await publishCam({ enabled: false, error: "getUserMedia no disponible" });
      return false;
    }
    camStarting = true;
    const deviceId = (document.getElementById("cam-device") || {}).value || lastCamDevice;
    const video = deviceId
      ? { deviceId: { exact: deviceId }, width: { ideal: 640 } }
      : { facingMode: "user", width: { ideal: 640 } };
    try {
      camStream = await navigator.mediaDevices.getUserMedia({ video, audio: false });
      const track = camStream.getVideoTracks()[0];
      const label = (track && track.label) || "webcam";
      if (track && track.getSettings) {
        const id = track.getSettings().deviceId;
        if (id) {
          lastCamDevice = id;
          try { localStorage.setItem(CAM_DEVICE_KEY, id); } catch { /* ignore */ }
        }
      }
      camBlocked = false;
      camMissing = false;
      camBusy = false;
      bindCamVideos();
      setCamUi({ on: true, msg: "cámara en vivo · " + label, empty: "sin cámara" });
      await listCamDevices();
      await publishCam({
        enabled: true,
        hold: false,
        label,
        device_id: lastCamDevice,
        error: "",
      });
      return true;
    } catch (err) {
      const name = err && err.name;
      const text = camErrorText(err);
      if (name === "NotAllowedError" || name === "PermissionDeniedError") camBlocked = true;
      else if (name === "NotFoundError" || name === "OverconstrainedError") camMissing = true;
      else if (name === "NotReadableError" || name === "TrackStartError") camBusy = true;
      setCamUi({ on: false, msg: text, empty: text });
      await publishCam({ enabled: false, error: text });
      return false;
    } finally {
      camStarting = false;
    }
  }

  function stopCam(opts) {
    const silent = opts && opts.silent;
    camHoldReleased = false;
    if (camStream) {
      camStream.getTracks().forEach((t) => t.stop());
      camStream = null;
    }
    bindCamVideos();
    setCamUi({ on: false, msg: silent ? undefined : "cámara apagada", empty: "cámara apagada" });
  }

  function releaseForHowdy() {
    document.body.classList.add("cam-hold");
    if (camStream) {
      camStream.getTracks().forEach((t) => t.stop());
      camStream = null;
      bindCamVideos();
      document.body.classList.remove("cam-on");
      camHoldReleased = true;
    }
    setCamUi({ msg: "Howdy · V4L2 libre" });
  }

  async function resumeAfterHowdy() {
    document.body.classList.remove("cam-hold");
    if (camHoldReleased) {
      camHoldReleased = false;
      camBusy = false;
      await startCam();
      return;
    }
    setCamBadges();
  }

  function applyCamFromHud(hud) {
    if (!hud) return;
    if (hud.camera_hold === true) {
      releaseForHowdy();
    } else if (hud.camera_hold === false && document.body.classList.contains("cam-hold")) {
      resumeAfterHowdy();
    }
    if (hud.camera_enabled === true && !camStream && !camBlocked && !camMissing && !camHoldReleased) {
      startCam();
    }
    if (hud.camera_enabled === false && (camStream || camHoldReleased)) {
      stopCam();
    }
  }

  async function publishCam(payload) {
    try {
      const base = await brainUrl();
      const r = await fetch(base + "/api/hud/camera", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (r.status === 404) {
        await fetch(base + "/api/bus", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ type: "hud.camera", source: "hud", payload }),
        });
      }
    } catch (err) {
      console.error("hud camera", err);
    }
  }

  async function toggleCamButton() {
    if (document.body.classList.contains("cam-hold")) return;
    if (camStream || camHoldReleased) {
      stopCam();
      await publishCam({ enabled: false, hold: false, error: "", label: "" });
      return;
    }
    camBlocked = false;
    camMissing = false;
    camBusy = false;
    await startCam();
  }

  function showScreenPreview(b64) {
    const img = document.getElementById("screen-preview");
    const empty = document.getElementById("screen-empty");
    if (!img) return;
    if (b64) {
      img.src = "data:image/jpeg;base64," + b64;
      img.hidden = false;
      if (empty) empty.hidden = true;
    } else {
      img.hidden = true;
      if (empty) empty.hidden = false;
    }
  }

  async function refreshVision() {
    try {
      const base = await brainUrl();
      const s = await fetch(base + "/api/vision").then((r) => r.json());
      const last = s.last || {};
      document.getElementById("vision-msg").textContent =
        (last.text || "sin captura")
        + (s.session ? " · " + s.session : "")
        + (s.watch ? " · WATCH" : "")
        + (s.error ? " · " + s.error : "");
      document.getElementById("btn-watch").classList.toggle("on", !!s.watch);
      document.getElementById("btn-watch").textContent = s.watch ? "Parar vigilancia" : "Vigilancia pantalla";
      showScreenPreview(s.preview_jpeg_b64);
    } catch (err) {
      document.getElementById("vision-msg").textContent = String(err);
    }
  }

  async function captureScreen() {
    const box = document.getElementById("vision-msg");
    box.textContent = "capturando…";
    try {
      const base = await brainUrl();
      const r = await fetch(base + "/api/vision/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "once" }),
      });
      const data = await r.json();
      if (!data.ok) throw new Error(data.error || r.statusText);
      box.textContent = data.text || "ok";
      showScreenPreview(data.preview_jpeg_b64);
    } catch (err) {
      box.textContent = String(err.message || err);
    }
  }

  async function toggleWatch() {
    const base = await brainUrl();
    const cur = await fetch(base + "/api/vision").then((r) => r.json());
    const r = await fetch(base + "/api/vision/watch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !cur.watch, interval_ms: 15000 }),
    });
    const data = await r.json();
    if (r.status === 403) {
      document.getElementById("vision-msg").textContent = "Howdy: " + ((data.auth && data.auth.error) || "auth");
      return;
    }
    refreshVision();
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
      const cam = hud.camera_hold ? "cam hold" : (hud.camera_enabled ? (hud.camera_label || "cam") : "sin cam");
      meta.textContent = (s.ok ? "en línea" : "Hermes caído") + " · " + mode
        + (s.tts ? " · voz " + s.tts : " · sin voz") + " · " + auth
        + " · " + cam + " · HUD " + (hud.operational || "?");
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
          camera: !!camStream,
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
        " · V4L2 " + (a.camera || "?") +
        (a.compare_path ? " · " + a.compare_path : "");
      const hud = await fetch(base + "/api/hud").then((r) => r.json());
      const camLine = document.getElementById("cam-line");
      if (camLine) {
        camLine.textContent = "Webcam HUD: "
          + (hud.camera_enabled ? (hud.camera_label || "encendida") : "apagada")
          + (hud.camera_hold ? " · HOLD Howdy (V4L2 libre)" : "")
          + (hud.camera_error ? " · " + hud.camera_error : "");
      }
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
  document.getElementById("btn-capture").addEventListener("click", captureScreen);
  document.getElementById("btn-watch").addEventListener("click", toggleWatch);
  document.getElementById("btn-cam").addEventListener("click", toggleCamButton);
  document.getElementById("btn-cam-home").addEventListener("click", (ev) => {
    ev.stopPropagation();
    toggleCamButton();
  });
  document.getElementById("cam-pip").addEventListener("click", (ev) => {
    if (ev.target && ev.target.closest && ev.target.closest("button")) return;
    showView("vision");
  });
  document.getElementById("cam-device").addEventListener("change", async (ev) => {
    lastCamDevice = ev.target.value || "";
    try { localStorage.setItem(CAM_DEVICE_KEY, lastCamDevice); } catch { /* ignore */ }
    if (camStream || camHoldReleased) {
      stopCam({ silent: true });
      camBlocked = false;
      camMissing = false;
      camBusy = false;
      await startCam();
    }
  });
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
  listCamDevices();
  markReady();
  refresh();
  setInterval(refresh, 8000);
  q.focus();
})();
