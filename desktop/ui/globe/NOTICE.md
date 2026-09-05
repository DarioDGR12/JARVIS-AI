# Globe module

This iframe is a JARVIS reimplementation of the SENTINEL globe **architecture**
(3D sphere, `{id,loc,country,lat,lon}` feeds, `focusLatLon`, host `postMessage`).

We do **not** vendor `sentinel-feed-grid/src/index.html`. That file is a full
tactical console (CDN Three/hls.js, YouTube, DOT). It would break the Tauri CSP
and fight the HUD chrome. License of the upstream project is still MIT.

## Upstream

- [movingdevious/sentinel-feed-grid](https://github.com/movingdevious/sentinel-feed-grid) — MIT
  Copyright (c) 2026 movingdevious. See `LICENSE.sentinel`.

## Vendored runtime

- [Three.js r128](https://github.com/mrdoob/three.js) — MIT
  Copyright 2010-2021 Three.js Authors. File: `vendor/three.min.js`.

## Data

`feeds.json` is a short curated city list written for this repo (not the
WebcamMap ~10k dump, not ODbL). Live YouTube/HLS are out of this slice.

## Earth texture

`textures/earth.jpg` is a 2048×1024 downsample of NASA Blue Marble
(land surface, shallow water, shaded topography). Public domain
(NASA / US Government). Original: Visible Earth / Blue Marble 2002,
Reto Stöckli, Robert Simmon, NASA GSFC.
