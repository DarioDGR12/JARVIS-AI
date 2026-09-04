(() => {
  const FEED_CAP = 80;
  const MIN_DIST = 4.4;
  const MAX_DIST = 15;

  const sceneEl = document.getElementById("scene");
  const focusEl = document.getElementById("focus");
  const countEl = document.getElementById("count");

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x05070b, 0.035);
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 80);
  camera.position.set(0, 0.4, 8.5);
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

  const texture = new THREE.CanvasTexture(paintEarth());
  texture.wrapS = THREE.ClampToEdgeWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  const globe = new THREE.Mesh(
    new THREE.SphereGeometry(2, 64, 48),
    new THREE.MeshPhongMaterial({ map: texture, shininess: 8, specular: 0x223344 }),
  );
  earth.add(globe);
  const atmosphere = new THREE.Mesh(
    new THREE.SphereGeometry(2.06, 48, 32),
    new THREE.MeshBasicMaterial({
      color: 0x6ec8d4,
      transparent: true,
      opacity: 0.08,
      side: THREE.BackSide,
    }),
  );
  earth.add(atmosphere);

  const stars = new THREE.Points(
    starGeo(),
    new THREE.PointsMaterial({ color: 0xcdd6e2, size: 0.03, sizeAttenuation: true }),
  );
  scene.add(stars);

  const markers = new THREE.Group();
  earth.add(markers);
  const pinMat = new THREE.MeshBasicMaterial({ color: 0xd4b36a });
  const pinSel = new THREE.MeshBasicMaterial({ color: 0x6ec8d4 });
  const pinGeo = new THREE.SphereGeometry(0.035, 10, 8);

  let feeds = [];
  let visible = [];
  let selected = null;
  let raf = 0;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let dist = 8.5;
  let rotY = 0.35;
  let rotX = 0.25;
  let alive = true;

  function paintEarth() {
    const w = 1024;
    const h = 512;
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const g = c.getContext("2d");
    const sea = g.createLinearGradient(0, 0, 0, h);
    sea.addColorStop(0, "#0b1c33");
    sea.addColorStop(0.5, "#12344d");
    sea.addColorStop(1, "#0b1c33");
    g.fillStyle = sea;
    g.fillRect(0, 0, w, h);
    g.strokeStyle = "rgba(110,200,212,0.12)";
    g.lineWidth = 1;
    for (let i = 1; i < 12; i++) {
      const y = (h / 12) * i;
      g.beginPath();
      g.moveTo(0, y);
      g.lineTo(w, y);
      g.stroke();
    }
    for (let i = 1; i < 24; i++) {
      const x = (w / 24) * i;
      g.beginPath();
      g.moveTo(x, 0);
      g.lineTo(x, h);
      g.stroke();
    }
    g.fillStyle = "#3d5a3a";
    land(g, w, h);
    return c;
  }

  function land(g, w, h) {
    const blobs = [
      [-100, 50, 55, 28],
      [-70, 20, 28, 42],
      [-60, -20, 22, 38],
      [10, 50, 40, 22],
      [20, 10, 28, 42],
      [70, 45, 70, 30],
      [100, 20, 40, 28],
      [135, -25, 28, 18],
    ];
    blobs.forEach(([lon, lat, rw, rh]) => {
      const x = ((lon + 180) / 360) * w;
      const y = ((90 - lat) / 180) * h;
      g.beginPath();
      g.ellipse(x, y, (rw / 360) * w, (rh / 180) * h, 0, 0, Math.PI * 2);
      g.fill();
    });
  }

  function starGeo() {
    const geo = new THREE.BufferGeometry();
    const pts = [];
    for (let i = 0; i < 400; i++) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(28 + Math.random() * 20);
      pts.push(v.x, v.y, v.z);
    }
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return geo;
  }

  function latLonToVec(lat, lon, r) {
    const phi = THREE.MathUtils.degToRad(90 - lat);
    const theta = THREE.MathUtils.degToRad(lon + 180);
    return new THREE.Vector3(
      -r * Math.sin(phi) * Math.cos(theta),
      r * Math.cos(phi),
      r * Math.sin(phi) * Math.sin(theta),
    );
  }

  function zoomToDist(zoom) {
    const z = Math.min(10, Math.max(1, Number(zoom) || 5));
    return MAX_DIST - ((z - 1) * (MAX_DIST - MIN_DIST)) / 9;
  }

  function applyCamera() {
    camera.position.set(
      dist * Math.sin(rotY) * Math.cos(rotX),
      dist * Math.sin(rotX),
      dist * Math.cos(rotY) * Math.cos(rotX),
    );
    camera.lookAt(0, 0, 0);
  }

  function focusLatLon(lat, lon, zoom) {
    const latN = Number(lat);
    const lonN = Number(lon);
    if (!Number.isFinite(latN) || !Number.isFinite(lonN)) return;
    dist = zoomToDist(zoom);
    const v = latLonToVec(latN, lonN, 1);
    rotY = Math.atan2(v.x, v.z);
    rotX = Math.asin(Math.max(-0.9, Math.min(0.9, v.y)));
    applyCamera();
    const hit = visible.find((f) => Math.abs(f.lat - latN) < 0.4 && Math.abs(f.lon - lonN) < 0.4);
    focusEl.textContent = hit ? hit.loc + " · " + hit.country : latN.toFixed(2) + ", " + lonN.toFixed(2);
  }

  function clearPins() {
    while (markers.children.length) {
      const child = markers.children[0];
      markers.remove(child);
      if (child.geometry) child.geometry.dispose();
    }
  }

  function drawPins(list) {
    clearPins();
    list.forEach((feed) => {
      const mesh = new THREE.Mesh(pinGeo, selected && selected.id === feed.id ? pinSel : pinMat);
      mesh.position.copy(latLonToVec(feed.lat, feed.lon, 2.04));
      mesh.userData.feed = feed;
      markers.add(mesh);
    });
    countEl.textContent = list.length + " pines";
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

  function addFeeds(incoming) {
    const next = (incoming || []).map(normalize).filter(Boolean).slice(0, FEED_CAP);
    feeds = next;
    visible = next;
    drawPins(visible);
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
    drawPins(visible);
    post("map.feed_ready", { count: visible.length, region: region || "all" });
  }

  function query(q) {
    const needle = String(q || "").trim().toLowerCase();
    if (!needle) {
      visible = feeds;
      drawPins(visible);
      return;
    }
    visible = feeds.filter((f) =>
      [f.id, f.loc, f.country, f.region].join(" ").toLowerCase().includes(needle),
    );
    drawPins(visible);
    if (visible[0]) focusLatLon(visible[0].lat, visible[0].lon, 7);
    post("map.feed_ready", { count: visible.length, region: needle });
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
    if (!hits.length) return;
    const feed = hits[0].object.userData.feed;
    selected = feed;
    drawPins(visible);
    focusEl.textContent = feed.loc + " · " + feed.country;
    post("map.selection", { lat: feed.lat, lon: feed.lon, feed_id: feed.id });
  }

  function resize() {
    const w = sceneEl.clientWidth || window.innerWidth;
    const h = sceneEl.clientHeight || window.innerHeight;
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
  }

  function loop() {
    if (!alive) return;
    if (!dragging) rotY += 0.0012;
    applyCamera();
    renderer.render(scene, camera);
    raf = requestAnimationFrame(loop);
  }

  function post(type, payload) {
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({ type, payload, source: "sentinel" }, "*");
    }
  }

  function onHost(ev) {
    const data = ev.data || {};
    const type = data.type;
    const payload = data.payload || {};
    if (type === "map.focus") focusLatLon(payload.lat, payload.lon, payload.zoom);
    else if (type === "map.show_feeds") showFeeds(payload);
    else if (type === "map.query") query(payload.q);
    else if (type === "map.add_feeds") addFeeds(payload.feeds || payload);
  }

  function destroy() {
    alive = false;
    cancelAnimationFrame(raf);
    window.removeEventListener("message", onHost);
    window.removeEventListener("resize", resize);
    renderer.dispose();
    if (renderer.forceContextLoss) renderer.forceContextLoss();
    if (renderer.domElement && renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement);
    }
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
  renderer.domElement.addEventListener(
    "wheel",
    (ev) => {
      ev.preventDefault();
      dist = Math.max(MIN_DIST, Math.min(MAX_DIST, dist + ev.deltaY * 0.01));
    },
    { passive: false },
  );
  window.addEventListener("message", onHost);
  window.addEventListener("resize", resize);
  window.addEventListener("pagehide", destroy);

  window.JARVIS_GLOBE = {
    focusLatLon,
    addFeeds,
    loadSet: showFeeds,
    query,
    destroy,
  };

  resize();
  applyCamera();
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
  loop();
})();
