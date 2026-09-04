(() => {
  const FEED_CAP = 80;
  const MIN_DIST = 4.4;
  const MAX_DIST = 15;
  const sceneEl = document.getElementById("scene");
  const focusEl = document.getElementById("focus");
  const countEl = document.getElementById("count");

  let feeds = [];
  let visible = [];
  let selected = null;
  let alive = true;
  let rotY = 0.8;
  let rotX = 0.15;
  let dist = 8.5;
  let backend = null;

  function post(type, payload) {
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({ type, payload, source: "sentinel" }, "*");
    }
  }

  function normalize(raw) {
    if (!raw || typeof raw !== "object") return null;
    const lat = Number(raw.lat);
    const lon = Number(raw.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    if (raw.unavailable || raw.invalidUrl || raw.duplicate) return null;
    return {
      id: String(raw.id || raw.loc || `${lat},${lon}`),
      loc: String(raw.loc || raw.id || "feed"),
      country: String(raw.country || ""),
      lat,
      lon,
      region: String(raw.region || ""),
      tags: Array.isArray(raw.tags) ? raw.tags.map(String) : [],
    };
  }

  function setFocusLabel(lat, lon) {
    const hit = visible.find((f) => Math.abs(f.lat - lat) < 0.4 && Math.abs(f.lon - lon) < 0.4);
    focusEl.textContent = hit ? hit.loc + " · " + hit.country : Number(lat).toFixed(2) + ", " + Number(lon).toFixed(2);
  }

  function addFeeds(incoming) {
    feeds = (incoming || []).map(normalize).filter(Boolean).slice(0, FEED_CAP);
    visible = feeds;
    if (backend) backend.draw();
    countEl.textContent = visible.length + " pines";
    post("map.feed_ready", { count: visible.length, region: "all" });
  }

  function showFeeds(filter) {
    const region = String((filter && filter.region) || "").toLowerCase();
    const tags = (filter && filter.tags) || [];
    visible = feeds.filter((f) => {
      if (region && f.region !== region) return false;
      if (tags.length && !tags.some((t) => f.tags.includes(String(t)))) return false;
      return true;
    });
    if (backend) backend.draw();
    countEl.textContent = visible.length + " pines";
    post("map.feed_ready", { count: visible.length, region: region || "all" });
  }

  function query(q) {
    const needle = String(q || "").trim().toLowerCase();
    visible = !needle
      ? feeds
      : feeds.filter((f) => [f.id, f.loc, f.country, f.region].join(" ").toLowerCase().includes(needle));
    if (visible[0]) focusLatLon(visible[0].lat, visible[0].lon, 7);
    else if (backend) backend.draw();
    countEl.textContent = visible.length + " pines";
    post("map.feed_ready", { count: visible.length, region: needle || "all" });
  }

  function zoomToDist(zoom) {
    const z = Math.min(10, Math.max(1, Number(zoom) || 5));
    return MAX_DIST - ((z - 1) * (MAX_DIST - MIN_DIST)) / 9;
  }

  function focusLatLon(lat, lon, zoom) {
    const latN = Number(lat);
    const lonN = Number(lon);
    if (!Number.isFinite(latN) || !Number.isFinite(lonN)) return;
    dist = zoomToDist(zoom);
    rotY = (lonN * Math.PI) / 180;
    rotX = (latN * Math.PI) / 180;
    setFocusLabel(latN, lonN);
    if (backend) backend.draw();
  }

  function selectFeed(feed) {
    selected = feed;
    setFocusLabel(feed.lat, feed.lon);
    if (backend) backend.draw();
    post("map.selection", { lat: feed.lat, lon: feed.lon, feed_id: feed.id });
  }

  function canWebGL() {
    try {
      const c = document.createElement("canvas");
      return !!(window.THREE && (c.getContext("webgl") || c.getContext("experimental-webgl")));
    } catch {
      return false;
    }
  }

  function start2d() {
    const canvas = document.createElement("canvas");
    sceneEl.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    function project(lat, lon) {
      const w = canvas.width;
      const h = canvas.height;
      const R = Math.min(w, h) * 0.36;
      const cx = w / 2;
      const cy = h / 2;
      const la = (lat * Math.PI) / 180;
      const lo = (lon * Math.PI) / 180 - rotY;
      const x = Math.cos(la) * Math.sin(lo);
      const y = Math.sin(la);
      const z = Math.cos(la) * Math.cos(lo);
      if (z < 0) return null;
      return { x: cx + x * R, y: cy - y * R, z, R, cx, cy };
    }

    function draw() {
      const w = sceneEl.clientWidth || 400;
      const h = sceneEl.clientHeight || 400;
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      ctx.fillStyle = "#05070b";
      ctx.fillRect(0, 0, w, h);
      const R = Math.min(w, h) * 0.36;
      const cx = w / 2;
      const cy = h / 2;
      const g = ctx.createRadialGradient(cx - R * 0.3, cy - R * 0.3, R * 0.1, cx, cy, R);
      g.addColorStop(0, "#1b4a66");
      g.addColorStop(1, "#0b1c33");
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();
      ctx.strokeStyle = "rgba(212,179,106,0.35)";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.fillStyle = "rgba(61,90,58,0.85)";
      [
        [10, 50], [20, 10], [70, 45], [100, 20], [135, -25],
        [-100, 50], [-70, 20], [-60, -20],
      ].forEach(([lon, lat]) => {
        const p = project(lat, lon);
        if (!p) return;
        ctx.beginPath();
        ctx.ellipse(p.x, p.y, 22, 14, 0, 0, Math.PI * 2);
        ctx.fill();
      });
      visible.forEach((feed) => {
        const p = project(feed.lat, feed.lon);
        if (!p) return;
        ctx.beginPath();
        ctx.arc(p.x, p.y, selected && selected.id === feed.id ? 5 : 3, 0, Math.PI * 2);
        ctx.fillStyle = selected && selected.id === feed.id ? "#6ec8d4" : "#d4b36a";
        ctx.fill();
      });
    }

    function pick(ev) {
      const rect = canvas.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const y = ev.clientY - rect.top;
      let best = null;
      let bestD = 12;
      visible.forEach((feed) => {
        const p = project(feed.lat, feed.lon);
        if (!p) return;
        const d = Math.hypot(p.x - x, p.y - y);
        if (d < bestD) {
          best = feed;
          bestD = d;
        }
      });
      if (best) selectFeed(best);
    }

    canvas.addEventListener("pointerdown", (ev) => {
      dragging = true;
      lastX = ev.clientX;
      lastY = ev.clientY;
    });
    window.addEventListener("pointerup", (ev) => {
      if (dragging && Math.hypot(ev.clientX - lastX, ev.clientY - lastY) < 4) pick(ev);
      dragging = false;
    });
    window.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      rotY -= (ev.clientX - lastX) * 0.008;
      lastX = ev.clientX;
      lastY = ev.clientY;
      draw();
    });
    window.addEventListener("resize", draw);

    let raf = 0;
    function loop() {
      if (!alive) return;
      if (!dragging) {
        rotY += 0.004;
        draw();
      }
      raf = requestAnimationFrame(loop);
    }
    loop();

    return {
      draw,
      destroy() {
        cancelAnimationFrame(raf);
        if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
      },
    };
  }

  function start3d() {
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x05070b, 0.035);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 80);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x05070b, 1);
    sceneEl.appendChild(renderer.domElement);
    const earth = new THREE.Group();
    scene.add(earth);
    scene.add(new THREE.AmbientLight(0x6a7a8c, 0.55));
    const sun = new THREE.DirectionalLight(0xfff4d6, 1.05);
    sun.position.set(-4, 2, 6);
    scene.add(sun);
    function paintEarth() {
      const w = 1024;
      const h = 512;
      const c = document.createElement("canvas");
      c.width = w;
      c.height = h;
      const g = c.getContext("2d");
      g.fillStyle = "#12344d";
      g.fillRect(0, 0, w, h);
      g.fillStyle = "#3d5a3a";
      [
        [-100, 50, 55, 28], [-70, 20, 28, 42], [-60, -20, 22, 38],
        [10, 50, 40, 22], [20, 10, 28, 42], [70, 45, 70, 30],
        [100, 20, 40, 28], [135, -25, 28, 18],
      ].forEach(([lon, lat, rw, rh]) => {
        g.beginPath();
        g.ellipse(((lon + 180) / 360) * w, ((90 - lat) / 180) * h, (rw / 360) * w, (rh / 180) * h, 0, 0, Math.PI * 2);
        g.fill();
      });
      return c;
    }
    const texture = new THREE.CanvasTexture(paintEarth());
    earth.add(new THREE.Mesh(
      new THREE.SphereGeometry(2, 64, 48),
      new THREE.MeshPhongMaterial({ map: texture, shininess: 8 }),
    ));
    const markers = new THREE.Group();
    earth.add(markers);
    const pinGeo = new THREE.SphereGeometry(0.035, 10, 8);
    const pinMat = new THREE.MeshBasicMaterial({ color: 0xd4b36a });
    const pinSel = new THREE.MeshBasicMaterial({ color: 0x6ec8d4 });
    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    let raf = 0;

    function latLonToVec(lat, lon, r) {
      const phi = THREE.MathUtils.degToRad(90 - lat);
      const theta = THREE.MathUtils.degToRad(lon + 180);
      return new THREE.Vector3(
        -r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta),
      );
    }

    function applyCamera() {
      camera.position.set(
        dist * Math.sin(rotY) * Math.cos(rotX),
        dist * Math.sin(rotX),
        dist * Math.cos(rotY) * Math.cos(rotX),
      );
      camera.lookAt(0, 0, 0);
    }

    function draw() {
      while (markers.children.length) markers.remove(markers.children[0]);
      visible.forEach((feed) => {
        const mesh = new THREE.Mesh(pinGeo, selected && selected.id === feed.id ? pinSel : pinMat);
        mesh.position.copy(latLonToVec(feed.lat, feed.lon, 2.04));
        mesh.userData.feed = feed;
        markers.add(mesh);
      });
      applyCamera();
      renderer.render(scene, camera);
    }

    function resize() {
      const w = sceneEl.clientWidth || window.innerWidth;
      const h = sceneEl.clientHeight || window.innerHeight;
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
      draw();
    }

    function pick(event) {
      const rect = renderer.domElement.getBoundingClientRect();
      const mouse = new THREE.Vector2(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1,
      );
      const ray = new THREE.Raycaster();
      ray.setFromCamera(mouse, camera);
      const hits = ray.intersectObjects(markers.children, false);
      if (hits.length) selectFeed(hits[0].object.userData.feed);
    }

    renderer.domElement.addEventListener("pointerdown", (ev) => {
      dragging = true;
      lastX = ev.clientX;
      lastY = ev.clientY;
    });
    window.addEventListener("pointerup", (ev) => {
      if (dragging && Math.hypot(ev.clientX - lastX, ev.clientY - lastY) < 4) pick(ev);
      dragging = false;
    });
    window.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      rotY -= (ev.clientX - lastX) * 0.005;
      rotX = Math.max(-1.1, Math.min(1.1, rotX + (ev.clientY - lastY) * 0.005));
      lastX = ev.clientX;
      lastY = ev.clientY;
    });
    renderer.domElement.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      dist = Math.max(MIN_DIST, Math.min(MAX_DIST, dist + ev.deltaY * 0.01));
    }, { passive: false });
    window.addEventListener("resize", resize);

    function loop() {
      if (!alive) return;
      if (!dragging) rotY += 0.0012;
      applyCamera();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(loop);
    }
    resize();
    loop();
    return {
      draw,
      destroy() {
        cancelAnimationFrame(raf);
        renderer.dispose();
        if (renderer.forceContextLoss) renderer.forceContextLoss();
        if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
      },
    };
  }

  function onHost(ev) {
    const data = ev.data || {};
    const payload = data.payload || {};
    if (data.type === "map.focus") focusLatLon(payload.lat, payload.lon, payload.zoom);
    else if (data.type === "map.show_feeds") showFeeds(payload);
    else if (data.type === "map.query") query(payload.q);
    else if (data.type === "map.add_feeds") addFeeds(payload.feeds || payload);
  }

  function destroy() {
    alive = false;
    window.removeEventListener("message", onHost);
    if (backend) backend.destroy();
  }

  window.addEventListener("message", onHost);
  window.addEventListener("pagehide", destroy);
  window.JARVIS_GLOBE = { focusLatLon, addFeeds, loadSet: showFeeds, query, destroy };

  try {
    backend = canWebGL() ? start3d() : start2d();
  } catch (err) {
    console.error("globe 3d failed", err);
    post("map.error", { reason: "webgl" });
    backend = start2d();
  }

  fetch("feeds.json")
    .then((r) => r.json())
    .then((data) => {
      addFeeds(data);
      post("map.ready", { source: "sentinel" });
    })
    .catch(() => {
      post("map.error", { reason: "feeds" });
      post("map.ready", { source: "sentinel" });
    });
})();
