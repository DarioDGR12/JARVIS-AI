# Third-party notices

JARVIS-AI is Apache-2.0. This file lists code and data bundled beside it.

## Three.js r128

- License: MIT
- Path: `desktop/ui/globe/vendor/three.min.js`
- https://github.com/mrdoob/three.js

## sentinel-feed-grid (architecture only)

- License: MIT
- Copyright (c) 2026 movingdevious
- https://github.com/movingdevious/sentinel-feed-grid
- We reimplement the globe + feed schema inside an iframe. We do not copy
  `src/index.html` or the tactical chrome.

WebcamMap (~9 740 cams, ODbL) is **not** bundled. A later extract would need
OSM attribution and share-alike on that dataset alone.

## hls.js 1.5.20

- License: Apache-2.0
- Path: `desktop/ui/globe/vendor/hls.min.js`
- https://github.com/video-dev/hls.js
- Loaded only to play the single NASA TV / ISS live pin.

## NASA Blue Marble

- License: public domain (NASA / US Government)
- Path: `desktop/ui/globe/textures/earth.jpg`
- Downsampled 2048×1024 from Visible Earth Blue Marble 2002
  (Reto Stöckli, Robert Simmon, NASA GSFC)
