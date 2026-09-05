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
  let ttsAudio = null;
  let voiceRec = null;
  let voiceListening = false;
  const WAKE_RE = /^(oye\s+|hey\s+)?jarvis[,.]?\s*/i;

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
    applyVisor(!!hud.visor, { remote: true });
    applyClickThrough(!!hud.click_through, { remote: true });
    if (hud.presence !== undefined && hud.presence !== null) {
      document.body.dataset.presence = hud.presence ? "1" : "0";
    }
    const hl = document.getElementById("screen-highlight");
    if (hl && hud.last_display && hud.last_display.kind === "highlight") {
      hl.hidden = false;
      setTimeout(() => { hl.hidden = true; }, 4000);
    }
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
    if (ev.type === "map.focus" || ev.type === "map.query" || ev.type === "map.show_feeds" || ev.type === "map.live"
      || ev.type === "map.zoom" || ev.type === "hud.gesture") {
      sendToGlobe(ev);
    }
    if (ev.type === "map.live") playLiveFromId((ev.payload && ev.payload.id) || "iss");
    if (ev.type === "hud.set_mode" || ev.type === "hud.display" || ev.type === "hud.speak"
      || ev.type === "hud.highlight" || ev.type === "brain.status" || ev.type === "persona.changed"
      || ev.type === "auth.challenge" || ev.type === "auth.result" || ev.type === "hud.ready"
      || ev.type === "hud.camera" || ev.type === "vision.screen_context" || ev.type === "vision.error"
      || ev.type === "vision.watch" || ev.type === "hud.visor" || ev.type === "hud.overlay"
      || ev.type === "hud.presence" || ev.type === "hud.gesture"
      || ev.type === "hud.click_through" || ev.type === "voice.wake" || ev.type === "system.alert"
      || ev.type === "surveillance.alert") {
      refreshHud();
    }
    if (ev.type === "hud.camera") applyCamFromHud(ev.payload || {});
    if (ev.type === "hud.visor") applyVisor(!!(ev.payload && ev.payload.enabled), { remote: true });
    if (ev.type === "hud.overlay") applyOverlay(!!(ev.payload && ev.payload.enabled), { remote: true });
    if (ev.type === "hud.click_through") applyClickThrough(!!(ev.payload && ev.payload.enabled), { remote: true });
    if (ev.type === "voice.wake") {
      q.focus();
      document.body.dataset.mode = "listening";
    }
    if (ev.type === "hud.speak") {
      /* TTS arrives as WAV on chat/transcript responses; barge-in is local. */
    }
    if (ev.type === "hud.highlight") {
      const box = document.getElementById("screen-highlight");
      if (box) {
        box.hidden = false;
        setTimeout(() => { box.hidden = true; }, 4000);
      }
    }
    if (String(ev.type).indexOf("vision.") === 0) refreshVision();
  }

  function mapStatus(text) {
    const el = document.getElementById("map-status");
    if (el) el.textContent = text;
  }

  let hlsHandle = null;

  function stopLive() {
    const video = document.getElementById("live-video");
    const empty = document.getElementById("live-empty");
    if (hlsHandle) {
      try { hlsHandle.destroy(); } catch { /* ignore */ }
      hlsHandle = null;
    }
    if (video) {
      video.pause();
      video.removeAttribute("src");
      video.load();
      video.hidden = true;
    }
    if (empty) empty.textContent = "sin directo · un feed (NASA+)";
  }

  function loadHlsLib() {
    if (window.Hls) return Promise.resolve(window.Hls);
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "globe/vendor/hls.min.js";
      s.onload = () => resolve(window.Hls);
      s.onerror = () => reject(new Error("hls.js"));
      document.head.appendChild(s);
    });
  }

  async function playLive(url, label) {
    const video = document.getElementById("live-video");
    const empty = document.getElementById("live-empty");
    if (!video || !url) return;
    stopLive();
    if (empty) empty.textContent = "conectando " + (label || "live") + "…";
    if (url.indexOf("/api/map/hls") < 0) {
      const base = await brainUrl();
      url = base + "/api/map/hls?u=" + encodeURIComponent(url);
    }
    try {
      const Hls = await loadHlsLib().catch(() => null);
      if (Hls && Hls.isSupported()) {
        hlsHandle = new Hls({
          enableWorker: true,
          lowLatencyMode: false,
          startLevel: 0,
        });
        await new Promise((resolve, reject) => {
          const onFatal = (_, data) => {
            if (data && data.fatal) reject(new Error(data.details || "hls"));
          };
          hlsHandle.on(Hls.Events.ERROR, onFatal);
          hlsHandle.on(Hls.Events.MANIFEST_PARSED, () => resolve());
          hlsHandle.loadSource(url);
          hlsHandle.attachMedia(video);
          setTimeout(() => reject(new Error("timeout HLS")), 12000);
        });
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = url;
      } else {
        throw new Error("HLS no soportado");
      }
      video.hidden = false;
      await video.play().catch(() => {});
      if (empty) empty.textContent = "LIVE · " + (label || "NASA TV");
    } catch (err) {
      if (empty) empty.textContent = "feed caído · " + (err.message || err);
    }
  }

  async function playLiveFromId(id) {
    try {
      const base = await brainUrl();
      const data = await fetch(base + "/api/map").then((r) => r.json());
      const feeds = (data.live || data.feeds || []).filter((f) => f.hls);
      let want = id;
      if (!want || want === "next") {
        want = (data.last_selection && data.last_selection.feed_id) || "iss";
      }
      const hit = feeds.find((f) => f.id === want) || feeds[0];
      if (hit && hit.hls) playLive(hit.hls, hit.loc || hit.id);
    } catch {
      /* ignore */
    }
  }

  window.jarvisHud = {
    gesture(kind, extra) {
      const name = kind === "spread" ? "spread" : "pinch";
      const payload = {
        name,
        hand: (extra && extra.hand) || "both",
        confidence: (extra && extra.confidence) || 0.8,
        timestamp: Date.now(),
        scale: extra && extra.dist,
      };
      brainUrl().then((base) => fetch(base + "/api/hud/gesture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })).catch(() => {});
      sendToGlobe({ type: "hud.gesture", payload });
    },
  };

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
      if (sel) sel.textContent = (p.feed_id || "") + " · " + (p.lat || "") + ", " + (p.lon || "")
        + (p.live ? " · LIVE" : "");
      if (p.hls) playLive(p.hls, p.feed_id);
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
    stopLive();
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

  async function applyVisor(enabled, opts) {
    const remote = opts && opts.remote;
    document.body.dataset.visor = enabled ? "on" : "off";
    const btn = document.getElementById("btn-visor");
    if (btn) btn.classList.toggle("visor-on", enabled);
    const api = tauri();
    if (api && api.core && api.core.invoke) {
      try { await api.core.invoke("set_visor", { enabled }); } catch { /* ignore */ }
    }
    if (!remote) {
      try {
        const base = await brainUrl();
        await fetch(base + "/api/hud/visor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        });
      } catch (err) {
        console.error("visor", err);
      }
    }
    if (enabled && currentView !== "home") paintView("home");
    if (!enabled) applyClickThrough(false, { remote: true });
  }

  async function applyOverlay(enabled, opts) {
    const remote = opts && opts.remote;
    document.body.dataset.overlay = enabled ? "on" : "off";
    const btn = document.getElementById("btn-overlay");
    if (btn) btn.classList.toggle("visor-on", enabled);
    const api = tauri();
    if (api && api.core && api.core.invoke) {
      try { await api.core.invoke("set_overlay", { enabled }); } catch { /* ignore */ }
    }
    if (!remote) {
      try {
        const base = await brainUrl();
        await fetch(base + "/api/hud/overlay", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        });
      } catch (err) {
        console.error("overlay", err);
      }
    }
  }

  async function applyClickThrough(enabled, opts) {
    const remote = opts && opts.remote;
    document.body.dataset.through = enabled ? "on" : "off";
    const btn = document.getElementById("btn-through");
    if (btn) btn.classList.toggle("visor-on", enabled);
    const api = tauri();
    if (api && api.core && api.core.invoke) {
      try { await api.core.invoke("set_click_through", { enabled }); } catch { /* ignore */ }
    }
    if (!remote) {
      try {
        const base = await brainUrl();
        await fetch(base + "/api/hud/click-through", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        });
      } catch (err) {
        console.error("click-through", err);
      }
    }
  }

  function bargeIn() {
    if (!ttsAudio) return;
    try {
      ttsAudio.pause();
      ttsAudio.currentTime = 0;
    } catch { /* ignore */ }
    ttsAudio = null;
  }

  function playReplyAudio(b64) {
    if (!b64 || (mute && mute.checked)) return;
    bargeIn();
    ttsAudio = new Audio("data:audio/wav;base64," + b64);
    ttsAudio.play().catch(() => {});
  }

  function speechCtor() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function setVoiceUi(on) {
    voiceListening = !!on;
    document.body.classList.toggle("listening-voice", voiceListening);
    ["btn-mic", "btn-mic-chat", "btn-mic-home"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = voiceListening ? "Oyendo…" : (id === "btn-mic-home" ? "Escuchar" : "Mic");
    });
  }

  async function postWake(phrase) {
    try {
      const base = await brainUrl();
      await fetch(base + "/api/voice/wake", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phrase: phrase || "jarvis" }),
      });
    } catch (err) {
      console.error("wake", err);
    }
  }

  async function postTranscript(text) {
    add("you", text);
    try {
      const base = await brainUrl();
      const r = await fetch(base + "/api/voice/transcript", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await r.json();
      if (!data.ok) throw new Error(data.error || r.statusText);
      add("jarvis", data.reply || "(sin texto)");
      applyHud(data.hud);
      playReplyAudio(data.audio_wav_b64);
    } catch (err) {
      add("err", String(err.message || err));
    }
  }

  function handleHeard(raw) {
    const text = (raw || "").trim();
    if (!text) return;
    const woke = WAKE_RE.test(text);
    const rest = text.replace(WAKE_RE, "").trim();
    if (woke) postWake("jarvis");
    if (rest) postTranscript(rest);
    else if (!woke) postTranscript(text);
  }

  function stopListen() {
    stopPcm();
    if (voiceRec) {
      try { voiceRec.onend = null; voiceRec.stop(); } catch { /* ignore */ }
      voiceRec = null;
    }
    setVoiceUi(false);
  }

  let pcmSocket = null;
  let pcmCtx = null;
  let pcmSource = null;

  async function stopPcm() {
    if (pcmSource) {
      try { pcmSource.disconnect(); } catch { /* ignore */ }
      pcmSource = null;
    }
    if (pcmCtx) {
      try { pcmCtx.close(); } catch { /* ignore */ }
      pcmCtx = null;
    }
    if (pcmSocket) {
      try { pcmSocket.close(); } catch { /* ignore */ }
      pcmSocket = null;
    }
  }

  async function startPcm() {
    const base = await brainUrl();
    const voice = await fetch(base + "/api/voice").then((r) => r.json()).catch(() => ({}));
    if (!(voice.local && voice.local.loaded)) return false;
    await stopPcm();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    const ws = new WebSocket(base.replace("http", "ws") + "/ws/voice");
    ws.binaryType = "arraybuffer";
    pcmSocket = ws;
    const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    pcmCtx = ctx;
    const src = ctx.createMediaStreamSource(stream);
    pcmSource = src;
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    proc.onaudioprocess = (ev) => {
      if (!pcmSocket || pcmSocket.readyState !== 1) return;
      const input = ev.inputBuffer.getChannelData(0);
      const pcm = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      pcmSocket.send(pcm.buffer);
    };
    src.connect(proc);
    proc.connect(ctx.destination);
    return true;
  }

  function startListen() {
    bargeIn();
    if (voiceRec) {
      try { voiceRec.onend = null; voiceRec.stop(); } catch { /* ignore */ }
      voiceRec = null;
    }
    startPcm().then((used) => {
      if (used) setVoiceUi(true);
    }).catch(() => {});
    const Ctor = speechCtor();
    if (!Ctor) {
      add("err", "Web Speech no está en este motor. Escribe o usa POST /api/voice/transcript.");
      q.focus();
      return;
    }
    const rec = new Ctor();
    rec.lang = "es-ES";
    rec.interimResults = false;
    rec.continuous = true;
    rec.onspeechstart = () => bargeIn();
    rec.onresult = (ev) => {
      const last = ev.results[ev.results.length - 1];
      if (!last || !last.isFinal) return;
      handleHeard(last[0] && last[0].transcript);
    };
    rec.onerror = (ev) => {
      const fatal = ev.error === "not-allowed" || ev.error === "service-not-allowed"
        || ev.error === "audio-capture";
      if (ev.error === "not-allowed") add("err", "micrófono: permiso denegado");
      else if (ev.error === "audio-capture" || ev.error === "service-not-allowed") {
        add("err", "voz: sin micrófono en este equipo");
      } else if (ev.error !== "no-speech" && ev.error !== "aborted") {
        add("err", "voz: " + ev.error);
      }
      if (fatal) {
        voiceListening = false;
        try { rec.onend = null; rec.stop(); } catch { /* ignore */ }
        if (voiceRec === rec) voiceRec = null;
        setVoiceUi(false);
      }
    };
    rec.onend = () => {
      if (voiceListening && voiceRec === rec) {
        try { rec.start(); } catch { setVoiceUi(false); }
      }
    };
    voiceRec = rec;
    try {
      rec.start();
      setVoiceUi(true);
    } catch (err) {
      add("err", String(err.message || err));
      setVoiceUi(false);
    }
  }

  function toggleListen() {
    if (voiceListening) stopListen();
    else startListen();
  }

  let lastPresence = null;
  async function samplePresence() {
    if (!camStream) {
      if (lastPresence !== null) {
        lastPresence = null;
        document.body.dataset.presence = "";
      }
      return;
    }
    const video = document.getElementById("cam-home") || document.getElementById("cam-vision");
    if (!video || !video.videoWidth) return;
    try {
      const canvas = document.createElement("canvas");
      canvas.width = 32;
      canvas.height = 24;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, 32, 24);
      const data = ctx.getImageData(0, 0, 32, 24).data;
      let sum = 0;
      for (let i = 0; i < data.length; i += 4) sum += data[i] + data[i + 1] + data[i + 2];
      const mean = sum / ((data.length / 4) * 3);
      const present = mean > 12;
      if (present === lastPresence) return;
      lastPresence = present;
      document.body.dataset.presence = present ? "1" : "0";
      const base = await brainUrl();
      await fetch(base + "/api/hud/presence", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ present, source: "webcam" }),
      });
    } catch {
      /* ignore */
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
      paintRegions((s.last && s.last.regions) || []);
    } catch (err) {
      document.getElementById("vision-msg").textContent = String(err);
    }
  }

  function paintRegions(regions) {
    const layer = document.getElementById("screen-regions");
    if (!layer) return;
    layer.innerHTML = "";
    if (!regions.length) {
      layer.hidden = true;
      return;
    }
    layer.hidden = false;
    regions.forEach((reg) => {
      const box = document.createElement("button");
      box.type = "button";
      box.className = "ocr-box";
      box.style.left = ((reg.x || 0) * 100) + "%";
      box.style.top = ((reg.y || 0) * 100) + "%";
      box.style.width = ((reg.w || 0.1) * 100) + "%";
      box.style.height = ((reg.h || 0.08) * 100) + "%";
      box.textContent = reg.text || "";
      box.onclick = () => {
        brainUrl().then((base) => fetch(base + "/api/vision/click", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: reg.text || "" }),
        })).catch(() => {});
      };
      layer.appendChild(box);
    });
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
      const seat = hud.presence === true ? "piloto" : (hud.presence === false ? "vacío" : "");
      meta.textContent = (s.ok ? "en línea" : "Hermes caído") + " · " + mode
        + (s.tts ? " · voz " + s.tts : " · sin voz") + " · " + auth
        + " · " + cam
        + (seat ? " · " + seat : "")
        + (hud.visor ? " · visor" : "")
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
      playReplyAudio(data.audio_wav_b64);
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
      const hud = s.hud || await fetch(base + "/api/hud").then((r) => r.json());
      const camLine = document.getElementById("cam-line");
      if (camLine) {
        camLine.textContent = "Webcam HUD: "
          + (hud.camera_enabled ? (hud.camera_label || "encendida") : "apagada")
          + (hud.camera_hold ? " · HOLD Howdy (V4L2 libre)" : "")
          + (hud.presence === true ? " · piloto" : "")
          + (hud.camera_error ? " · " + hud.camera_error : "");
      }
      const voice = s.voice || {};
      const voiceLine = document.getElementById("voice-line");
      if (voiceLine) {
        voiceLine.textContent = "Voz: wake " + (voice.wake || "?")
          + " · STT " + (voice.stt || "?")
          + (voice.pcm ? " · PCM" : "")
          + (voice.barge_in ? " · barge-in" : "");
      }
      const surv = s.surv || {};
      const survLine = document.getElementById("surv-line");
      if (survLine) {
        survLine.textContent = "Puerta: "
          + (surv.armed ? "armada" : "desarmada")
          + " · " + (surv.policy || "external")
          + (surv.last ? " · último " + (surv.last.text || "") : "");
      }
      const proto = document.getElementById("surv-proto");
      if (proto) {
        proto.textContent = "Detector: " + (surv.ingest || "POST /api/surveillance/alert")
          + " · " + ((surv.fields || []).join(", ") || "kind, camera, score, text");
      }
      const armBtn = document.getElementById("btn-arm");
      if (armBtn) armBtn.textContent = surv.armed ? "Desarmar puerta" : "Armar puerta";
    } catch (err) {
      document.getElementById("sys-stats").textContent = String(err);
    }
  }

  function paintZoneGrid(box, items, extraClass) {
    if (!box) return;
    box.innerHTML = "";
    (items || []).forEach((z) => {
      const el = document.createElement("div");
      el.className = "zone" + (extraClass ? " " + extraClass : "") + (z.on ? " on" : "");
      el.innerHTML = "<h4>" + z.label + "</h4><p>" + (z.on || 0) + "/" + (z.count || 0) + " on</p>";
      box.appendChild(el);
    });
  }

  function paintSchematic(data, states) {
    const box = document.getElementById("ha-schematic");
    const rooms = document.getElementById("ha-rooms");
    const zones = (data && data.zones) || [
      { id: "luces", label: "Luces", on: 0, count: 0 },
      { id: "clima", label: "Clima", on: 0, count: 0 },
      { id: "puertas", label: "Puertas", on: 0, count: 0 },
      { id: "media", label: "Media", on: 0, count: 0 },
    ];
    paintZoneGrid(box, zones, "");
    paintZoneGrid(rooms, (data && data.rooms) || [], "room");
  }

  async function loadHa() {
    const box = document.getElementById("ha-states");
    box.textContent = "";
    try {
      const base = await brainUrl();
      const s = await fetch(base + "/api/ha/states").then((r) => r.json());
      if (!s.ok) {
        document.getElementById("ha-msg").textContent = s.error || "HA no configurado";
        paintSchematic(null, []);
        return;
      }
      const states = s.states || [];
      document.getElementById("ha-msg").textContent = states.length + " entidades";
      try {
        const sch = await fetch(base + "/api/ha/schematic").then((r) => r.json());
        paintSchematic(sch, states);
      } catch {
        paintSchematic(null, states);
      }
      const groups = {};
      states.forEach((ent) => {
        const domain = String(ent.entity_id || "").split(".")[0] || "otros";
        (groups[domain] = groups[domain] || []).push(ent);
      });
      Object.keys(groups).sort().forEach((domain) => {
        const head = document.createElement("h3");
        head.textContent = domain + " · " + groups[domain].length;
        head.style.cssText = "margin:12px 0 6px;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:var(--accent)";
        box.appendChild(head);
        groups[domain].forEach((ent) => {
          const row = document.createElement("div");
          row.className = "entity";
          row.innerHTML = "<span>" + (ent.name || ent.entity_id) + "</span><span>" + (ent.state || "") + "</span>";
          if (domain === "light" || domain === "switch" || domain === "scene") {
            const toggle = document.createElement("button");
            toggle.textContent = domain === "scene" ? "activar" : "toggle";
            toggle.onclick = async () => {
              const r = await fetch(base + "/api/ha/call", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  domain,
                  service: domain === "scene" ? "turn_on" : "toggle",
                  entity_id: ent.entity_id,
                }),
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
  document.getElementById("btn-visor").addEventListener("click", () => {
    applyVisor(document.body.dataset.visor !== "on");
  });
  const overlayBtn = document.getElementById("btn-overlay");
  if (overlayBtn) {
    overlayBtn.addEventListener("click", () => {
      applyOverlay(document.body.dataset.overlay !== "on");
    });
  }
  document.getElementById("btn-through").addEventListener("click", () => {
    applyClickThrough(document.body.dataset.through !== "on");
  });
  ["btn-mic", "btn-mic-chat", "btn-mic-home"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("click", toggleListen);
  });
  const armBtn = document.getElementById("btn-arm");
  if (armBtn) {
    armBtn.addEventListener("click", async () => {
      const base = await brainUrl();
      const cur = await fetch(base + "/api/surveillance").then((r) => r.json());
      const r = await fetch(base + "/api/surveillance/arm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ armed: !cur.armed }),
      });
      const data = await r.json();
      const line = document.getElementById("surv-line");
      if (r.status === 403) {
        if (line) line.textContent = "Puerta: Howdy " + ((data.auth && data.auth.error) || "auth");
        return;
      }
      loadSystem();
    });
  }
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
  setInterval(samplePresence, 2500);
  q.focus();
})();
