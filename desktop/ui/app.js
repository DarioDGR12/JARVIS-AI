(() => {
  const log = document.getElementById("log");
  const meta = document.getElementById("meta");
  const form = document.getElementById("f");
  const q = document.getElementById("q");
  const mute = document.getElementById("mute");
  const btn = form.querySelector("button");
  const views = {
    chat: document.getElementById("chat-view"),
    settings: document.getElementById("settings-view"),
    system: document.getElementById("system-view"),
    ha: document.getElementById("ha-view"),
  };
  const setupForm = document.getElementById("setup");
  const setupMsg = document.getElementById("setup-msg");
  const providerEl = document.getElementById("provider");
  const keyRow = document.getElementById("key-row");
  const baseRow = document.getElementById("base-row");

  const BRAIN = "http://127.0.0.1:8765";

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

  function showView(name) {
    Object.entries(views).forEach(([key, el]) => {
      if (el) el.hidden = key !== name;
    });
    document.querySelectorAll("#nav button").forEach((b) => {
      b.classList.toggle("on", b.dataset.view === name);
    });
    if (name === "system") loadSystem();
    if (name === "ha") loadHa();
  }

  function syncProviderFields() {
    const id = providerEl.value;
    keyRow.hidden = id === "demo";
    baseRow.hidden = id !== "custom";
  }

  async function refresh() {
    try {
      const base = await brainUrl();
      const s = await fetch(base + "/api/status").then((r) => r.json());
      const p = s.product || {};
      const mode = p.mode === "byok" ? "BYOK " + (p.provider || "") : (p.mode || "demo");
      const auth = s.auth && s.auth.enrolled ? "howdy" : "sin howdy";
      meta.textContent = (s.ok ? "en línea" : "Hermes caído") + " · " + mode
        + (s.tts ? " · voz " + s.tts : " · sin voz") + " · " + auth;
      if (p.provider) providerEl.value = p.provider;
      if (p.model) document.getElementById("model").value = p.model;
      if (p.base_url) document.getElementById("base-url").value = p.base_url;
      syncProviderFields();
    } catch (err) {
      meta.textContent = "cerebro no responde";
      console.error("status", err);
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
          const btn = document.createElement("button");
          btn.textContent = "toggle";
          btn.onclick = async () => {
            const domain = ent.entity_id.split(".")[0];
            const r = await fetch(base + "/api/ha/call", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ domain, service: "toggle", entity_id: ent.entity_id }),
            });
            const data = await r.json();
            document.getElementById("ha-msg").textContent = data.ok ? "ok" : (data.error || "fail");
            loadHa();
          };
          row.appendChild(btn);
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
  document.getElementById("btn-back").addEventListener("click", () => showView("chat"));
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
  refresh();
  setInterval(refresh, 8000);
  q.focus();
})();
