(() => {
  const FEED_CAP = 80;
  const MIN_DIST = 4.4;
  const MAX_DIST = 15;
  const EARTH_URL = "textures/earth.jpg";
  const sceneEl = document.getElementById("scene");
  const focusEl = document.getElementById("focus");
  const countEl = document.getElementById("count");

  let feeds = [];
  let visible = [];
  let selected = null;
  let alive = true;
  let rotY = 0.8;
  let rotX = 0.18;
  let dist = 8.2;
  let backend = null;
  let earthImage = null;

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
    const hls = String(raw.hls || "").trim();
    const img = String(raw.img || "").trim();
    return {
      id: String(raw.id || raw.loc || `${lat},${lon}`),
      loc: String(raw.loc || raw.id || "feed"),
      country: String(raw.country || ""),
      lat,
      lon,
      region: String(raw.region || ""),
      tags: Array.isArray(raw.tags) ? raw.tags.map(String) : [],
      hls,
      img,
      live: !!(hls || img),
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

  function nudgeDist(delta) {
    const next = dist + Number(delta || 0);
    dist = Math.min(MAX_DIST, Math.max(MIN_DIST, next));
    if (backend && backend.draw) backend.draw();
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
    post("map.selection", {
      lat: feed.lat,
      lon: feed.lon,
      feed_id: feed.id,
      hls: feed.hls || "",
      live: !!feed.live,
    });
  }

  function worldFromLatLon(lat, lon) {
    const phi = ((90 - lat) * Math.PI) / 180;
    const theta = ((lon + 180) * Math.PI) / 180;
    return {
      x: -Math.sin(phi) * Math.cos(theta),
      y: Math.cos(phi),
      z: Math.sin(phi) * Math.sin(theta),
    };
  }

  function cameraBasis() {
    const camx = Math.sin(rotY) * Math.cos(rotX);
    const camy = Math.sin(rotX);
    const camz = Math.cos(rotY) * Math.cos(rotX);
    const len = Math.hypot(camx, camy, camz) || 1;
    const forwardX = -camx / len;
    const forwardY = -camy / len;
    const forwardZ = -camz / len;
    let rx = forwardY * 0 - forwardZ * 1;
    let ry = forwardZ * 0 - forwardX * 0;
    let rz = forwardX * 1 - forwardY * 0;
    const rlen = Math.hypot(rx, ry, rz) || 1;
    rx /= rlen;
    ry /= rlen;
    rz /= rlen;
    const ux = ry * forwardZ - rz * forwardY;
    const uy = rz * forwardX - rx * forwardZ;
    const uz = rx * forwardY - ry * forwardX;
    return {
      camx: camx / len,
      camy: camy / len,
      camz: camz / len,
      rx, ry, rz,
      ux, uy, uz,
    };
  }

  function projectWorld(lat, lon, w, h) {
    const R = Math.min(w, h) * 0.38;
    const b = cameraBasis();
    const p = worldFromLatLon(lat, lon);
    const facing = p.x * b.camx + p.y * b.camy + p.z * b.camz;
    if (facing <= 0.02) return null;
    return {
      x: w / 2 + (p.x * b.rx + p.y * b.ry + p.z * b.rz) * R,
      y: h / 2 - (p.x * b.ux + p.y * b.uy + p.z * b.uz) * R,
      R,
    };
  }

  function cachePixels(img) {
    const c = document.createElement("canvas");
    c.width = img.width;
    c.height = img.height;
    const g = c.getContext("2d");
    g.drawImage(img, 0, 0);
    return { data: g.getImageData(0, 0, img.width, img.height).data, w: img.width, h: img.height };
  }

  function drawStars(ctx, w, h) {
    ctx.fillStyle = "#03050a";
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "rgba(232,238,246,0.55)";
    let seed = 17;
    for (let i = 0; i < 90; i += 1) {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      const x = seed % w;
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      const y = seed % h;
      ctx.fillRect(x, y, i % 9 === 0 ? 2 : 1, 1);
    }
  }

  function paintTexturedSphere(ctx, pixels, w, h) {
    const R = Math.min(w, h) * 0.38;
    const cx = w / 2;
    const cy = h / 2;
    const halo = ctx.createRadialGradient(cx, cy, R * 0.86, cx, cy, R * 1.16);
    halo.addColorStop(0, "rgba(90,170,230,0)");
    halo.addColorStop(0.72, "rgba(80,160,220,0.18)");
    halo.addColorStop(1, "rgba(3,5,10,0)");
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(cx, cy, R * 1.16, 0, Math.PI * 2);
    ctx.fill();

    const size = Math.max(96, Math.min(400, Math.round(R * 2)));
    const buf = paintTexturedSphere.buf || (paintTexturedSphere.buf = document.createElement("canvas"));
    if (buf.width !== size) {
      buf.width = size;
      buf.height = size;
    }
    const bctx = buf.getContext("2d");
    const image = bctx.createImageData(size, size);
    const out = image.data;
    const cr = (size - 1) / 2;
    const b = cameraBasis();
    const tw = pixels.w;
    const th = pixels.h;
    const src = pixels.data;
    for (let y = 0; y < size; y += 1) {
      const ny = (cr - y) / cr;
      for (let x = 0; x < size; x += 1) {
        const nx = (x - cr) / cr;
        const rr = nx * nx + ny * ny;
        const oi = (y * size + x) * 4;
        if (rr > 1) {
          out[oi + 3] = 0;
          continue;
        }
        const nz = Math.sqrt(1 - rr);
        const wx = nx * b.rx + ny * b.ux + nz * b.camx;
        const wy = nx * b.ry + ny * b.uy + nz * b.camy;
        const wz = nx * b.rz + ny * b.uz + nz * b.camz;
        const lat = Math.asin(Math.max(-1, Math.min(1, wy)));
        let lon = Math.atan2(wz, -wx) - Math.PI;
        let u = lon / (2 * Math.PI) + 0.5;
        u -= Math.floor(u);
        const v = 0.5 - lat / Math.PI;
        const tx = Math.min(tw - 1, Math.max(0, (u * tw) | 0));
        const ty = Math.min(th - 1, Math.max(0, (v * th) | 0));
        const ti = (ty * tw + tx) * 4;
        const shade = 0.38 + 0.62 * nz;
        out[oi] = src[ti] * shade;
        out[oi + 1] = src[ti + 1] * shade;
        out[oi + 2] = src[ti + 2] * shade;
        out[oi + 3] = 255;
      }
    }
    bctx.putImageData(image, 0, 0);
    ctx.drawImage(buf, cx - R, cy - R, R * 2, R * 2);
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(160,210,255,0.28)";
    ctx.lineWidth = 2;
    ctx.stroke();
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
    let pixels = null;

    function draw() {
      const w = sceneEl.clientWidth || 400;
      const h = sceneEl.clientHeight || 400;
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      drawStars(ctx, w, h);
      if (pixels) paintTexturedSphere(ctx, pixels, w, h);
      else {
        const R = Math.min(w, h) * 0.38;
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, R, 0, Math.PI * 2);
        ctx.fillStyle = "#0a2740";
        ctx.fill();
      }
      visible.forEach((feed) => {
        const p = projectWorld(feed.lat, feed.lon, w, h);
        if (!p) return;
        ctx.beginPath();
        ctx.arc(p.x, p.y, selected && selected.id === feed.id ? 5 : 3, 0, Math.PI * 2);
        ctx.fillStyle = selected && selected.id === feed.id ? "#f4f7ff" : "#ffd36a";
        ctx.strokeStyle = "rgba(0,0,0,0.45)";
        ctx.lineWidth = 1;
        ctx.fill();
        ctx.stroke();
      });
    }

    function pick(ev) {
      const rect = canvas.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const y = ev.clientY - rect.top;
      const w = canvas.width;
      const h = canvas.height;
      let best = null;
      let bestD = 14;
      visible.forEach((feed) => {
        const p = projectWorld(feed.lat, feed.lon, w, h);
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
      rotX = Math.max(-1.15, Math.min(1.15, rotX + (ev.clientY - lastY) * 0.006));
      lastX = ev.clientX;
      lastY = ev.clientY;
      draw();
    });
    canvas.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      dist = Math.max(MIN_DIST, Math.min(MAX_DIST, dist + ev.deltaY * 0.01));
    }, { passive: false });
    window.addEventListener("resize", draw);

    let raf = 0;
    function loop() {
      if (!alive) return;
      if (!dragging) {
        rotY += 0.0024;
        draw();
      }
      raf = requestAnimationFrame(loop);
    }
    loop();

    return {
      draw,
      setEarth(img) {
        pixels = img ? cachePixels(img) : null;
        draw();
      },
      destroy() {
        cancelAnimationFrame(raf);
        if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
      },
    };
  }

  function start3d() {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 80);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x03050a, 1);
    sceneEl.appendChild(renderer.domElement);

    const starsGeo = new THREE.BufferGeometry();
    const starPos = new Float32Array(300 * 3);
    for (let i = 0; i < starPos.length; i += 3) {
      const a = Math.random() * Math.PI * 2;
      const b = Math.acos(2 * Math.random() - 1);
      const r = 28 + Math.random() * 18;
      starPos[i] = r * Math.sin(b) * Math.cos(a);
      starPos[i + 1] = r * Math.cos(b);
      starPos[i + 2] = r * Math.sin(b) * Math.sin(a);
    }
    starsGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    scene.add(new THREE.Points(starsGeo, new THREE.PointsMaterial({ color: 0xdde6ff, size: 0.08 })));

    const earth = new THREE.Group();
    scene.add(earth);
    scene.add(new THREE.AmbientLight(0x6f8498, 0.42));
    const sun = new THREE.DirectionalLight(0xfff6e4, 1.25);
    sun.position.set(-5, 2.2, 4.5);
    scene.add(sun);
    const fill = new THREE.DirectionalLight(0x4d6d9a, 0.28);
    fill.position.set(4, -1, -3);
    scene.add(fill);

    const globeMat = new THREE.MeshPhongMaterial({
      color: 0x0a2740,
      shininess: 14,
      specular: 0x2a4d6a,
    });
    const globe = new THREE.Mesh(new THREE.SphereGeometry(2, 96, 64), globeMat);
    earth.add(globe);
    earth.add(new THREE.Mesh(
      new THREE.SphereGeometry(2.045, 64, 48),
      new THREE.MeshBasicMaterial({ color: 0x7ec8ff, transparent: true, opacity: 0.07, side: THREE.BackSide }),
    ));

    const markers = new THREE.Group();
    earth.add(markers);
    const pinGeo = new THREE.SphereGeometry(0.032, 10, 8);
    const pinMat = new THREE.MeshBasicMaterial({ color: 0xffd36a });
    const pinSel = new THREE.MeshBasicMaterial({ color: 0xf4f7ff });
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
        mesh.position.copy(latLonToVec(feed.lat, feed.lon, 2.05));
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
      rotX = Math.max(-1.15, Math.min(1.15, rotX + (ev.clientY - lastY) * 0.005));
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
      if (!dragging) rotY += 0.0011;
      applyCamera();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(loop);
    }
    resize();
    loop();
    return {
      draw,
      setEarth(img) {
        if (!img) return;
        const tex = new THREE.Texture(img);
        tex.needsUpdate = true;
        if (tex.minFilter !== undefined) tex.minFilter = THREE.LinearFilter;
        globeMat.map = tex;
        globeMat.color = new THREE.Color(0xffffff);
        globeMat.needsUpdate = true;
        draw();
      },
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
    else if (data.type === "map.live") {
      const id = String(payload.id || "iss");
      const hit = feeds.find((f) => f.id === id) || feeds.find((f) => f.live);
      if (hit) {
        focusLatLon(hit.lat, hit.lon, 4);
        selectFeed(hit);
      }
    } else if (data.type === "map.zoom") {
      if (payload.delta != null) nudgeDist(payload.delta);
      else if (payload.dist != null) {
        dist = Math.min(MAX_DIST, Math.max(MIN_DIST, Number(payload.dist)));
        if (backend && backend.draw) backend.draw();
      }
    } else if (data.type === "hud.gesture") {
      const name = String(payload.name || "");
      if (name === "pinch") nudgeDist(-0.55);
      else if (name === "spread") nudgeDist(0.55);
    }
  }

  function destroy() {
    alive = false;
    window.removeEventListener("message", onHost);
    if (backend) backend.destroy();
  }

  function loadEarth() {
    const img = new Image();
    img.onload = () => {
      earthImage = img;
      if (backend && backend.setEarth) backend.setEarth(img);
    };
    img.onerror = () => post("map.error", { reason: "earth-texture" });
    img.src = EARTH_URL;
  }

  window.addEventListener("message", onHost);
  window.addEventListener("pagehide", destroy);
  window.JARVIS_GLOBE = { focusLatLon, addFeeds, loadSet: showFeeds, query, destroy, getDist: () => dist };

  try {
    backend = canWebGL() ? start3d() : start2d();
  } catch (err) {
    console.error("globe 3d failed", err);
    post("map.error", { reason: "webgl" });
    backend = start2d();
  }
  loadEarth();

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
