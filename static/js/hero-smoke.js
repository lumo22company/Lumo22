/**
 * Hero mist — x.ai-style: soft, slow-moving, illuminated volumetric mist.
 * Cursor gently displaces mist. No particles, sparks, or neon. Restrained, cinematic.
 * Respects prefers-reduced-motion; static dark fallback if canvas fails.
 */
(function () {
  'use strict';

  var hero = document.getElementById('hero');
  var canvas = document.getElementById('hero-canvas');
  var fallback = hero && hero.querySelector('.hero-fallback');

  if (!hero || !canvas) return;

  var useFallback = false;
  try {
    if (!canvas.getContext('2d')) useFallback = true;
  } catch (e) {
    useFallback = true;
  }
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    useFallback = true;
  }

  if (useFallback) {
    hero.classList.add('hero-use-fallback');
    if (canvas) canvas.style.display = 'none';
    if (fallback) fallback.style.display = 'block';
    return;
  }

  var ctx = canvas.getContext('2d');
  var W = 0, H = 0;
  var startTime = Date.now();

  /* Reference: slow, smart, atmospheric. Different speeds per layer for depth. */
  var TIME_BASE = 0.000035;
  var LAYER_SPEEDS = [0.25, 0.5, 0.85, 1.2];

  /* Reference: broad radial influence, very subtle strength — “marginally darker”, minimal change. */
  var CURSOR_RADIUS_FRAC = 0.28;
  var CURSOR_REDUCE = 0.06;
  var CURSOR_EASE = 0.045;
  var cursorTargetX = -1e7, cursorTargetY = -1e7;
  var cursorX = -1e7, cursorY = -1e7;

  hero.addEventListener('mousemove', function (e) {
    var r = hero.getBoundingClientRect();
    if (r.bottom < 0 || r.top > window.innerHeight) return;
    cursorTargetX = e.clientX;
    cursorTargetY = e.clientY;
  });
  hero.addEventListener('mouseleave', function () {
    cursorTargetX = -1e7;
    cursorTargetY = -1e7;
  });

  var perm = [];
  for (var i = 0; i < 256; i++) perm[i] = i;
  for (i = 255; i > 0; i--) {
    var j = Math.floor(Math.random() * (i + 1));
    var t = perm[i]; perm[i] = perm[j]; perm[j] = t;
  }
  for (i = 256; i < 512; i++) perm[i] = perm[i & 255];

  function fade(t) { return t * t * t * (t * (t * 6 - 15) + 10); }
  function lerp(a, b, t) { return a + t * (b - a); }

  function grad3D(hash, x, y, z) {
    var h = hash & 15;
    var u = h < 8 ? x : y, v = h < 4 ? y : (h === 12 || h === 14 ? x : z);
    return ((h & 1) ? -u : u) + ((h & 2) ? -v : v);
  }

  function noise3D(x, y, z) {
    var X = Math.floor(x) & 255, Y = Math.floor(y) & 255, Z = Math.floor(z) & 255;
    var fx = x - Math.floor(x), fy = y - Math.floor(y), fz = z - Math.floor(z);
    var u = fade(fx), v = fade(fy), w = fade(fz);
    var A = perm[X] + Y, AA = perm[A] + Z, AB = perm[A + 1] + Z;
    var B = perm[X + 1] + Y, BA = perm[B] + Z, BB = perm[B + 1] + Z;
    return lerp(
      lerp(lerp(grad3D(perm[AA], fx, fy, fz), grad3D(perm[BA], fx - 1, fy, fz), u),
           lerp(grad3D(perm[AB], fx, fy - 1, fz), grad3D(perm[BB], fx - 1, fy - 1, fz), u), v),
      lerp(lerp(grad3D(perm[AA + 1], fx, fy, fz - 1), grad3D(perm[BA + 1], fx - 1, fy, fz - 1), u),
           lerp(grad3D(perm[AB + 1], fx, fy - 1, fz - 1), grad3D(perm[BB + 1], fx - 1, fy - 1, fz - 1), u), v), w
    );
  }

  function n(x, y, z) { return noise3D(x, y, z) * 0.5 + 0.5; }

  function layeredNoise(x, y, z, t) {
    var v = 0;
    v += 0.45 * n(x * 1.1, y * 1.1, z * 0.7 + t * LAYER_SPEEDS[0]);
    v += 0.30 * n(x * 2.2 + 3.3, y * 2.2 + 1.1, z * 1.0 + t * LAYER_SPEEDS[1]);
    v += 0.15 * n(x * 4 + 7, y * 4 + 13, z * 1.5 + t * LAYER_SPEEDS[2]);
    v += 0.10 * n(x * 7 + 19, y * 7 + 23, z * 2 + t * LAYER_SPEEDS[3]);
    return Math.max(0, Math.min(1, v));
  }

  /* Smooth falloff for cursor: no abrupt edge. */
  function smoothFalloff(t) {
    t = Math.max(0, Math.min(1, t));
    return (1 - t) * (1 - t);
  }

  var offscreen = document.createElement('canvas');
  var offctx = offscreen.getContext('2d');

  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W;
    canvas.height = H;
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    offscreen.width = W;
    offscreen.height = H;
  }

  function draw() {
    var t = (Date.now() - startTime) * TIME_BASE;
    cursorX = lerp(cursorX, cursorTargetX, CURSOR_EASE);
    cursorY = lerp(cursorY, cursorTargetY, CURSOR_EASE);

    var centerX = W * 0.5, centerY = H * 0.5;
    /* Reference: illuminated region ~60–70% height, 70–80% width; soft falloff to black. */
    var regionScale = Math.max(W, H) * 0.52;
    var cursorRadius = W * CURSOR_RADIUS_FRAC;

    offctx.fillStyle = '#000';
    offctx.fillRect(0, 0, W, H);

    var imageData = offctx.createImageData(W, H);
    var data = imageData.data;

    for (var j = 0; j < H; j++) {
      for (var i = 0; i < W; i++) {
        var u = i / W, v = j / H;
        var nx = u * 2.1 - 0.5 + t * 0.18;
        var ny = v * 2.1 - 0.5 + t * 0.12;
        var nz = t * 0.35;
        var mist = layeredNoise(nx, ny, nz, t);

        /* Large soft illuminated region: gentle falloff from centre so logo stays clear. */
        var dx = (i - centerX) / regionScale;
        var dy = (j - centerY) / regionScale;
        var r = Math.sqrt(dx * dx + dy * dy);
        var edge = Math.max(0, 1 - r);
        edge = edge * edge;
        mist *= 0.22 + 0.78 * edge;

        /* Reference: cursor = very subtle reduction in mist density, broad radius, smooth falloff. */
        var cdx = i - cursorX, cdy = j - cursorY;
        var cdist = Math.sqrt(cdx * cdx + cdy * cdy);
        if (cdist < cursorRadius && cursorTargetX > -1e6) {
          var f = smoothFalloff(cdist / cursorRadius);
          mist *= 1 - f * CURSOR_REDUCE;
        }

        /* Soft illuminated mist — subtle off-white, not intense. */
        var br = Math.floor(mist * 48);
        var alpha = Math.floor(mist * 180);
        var idx = (j * W + i) << 2;
        data[idx] = br;
        data[idx + 1] = br;
        data[idx + 2] = Math.min(255, Math.floor(br * 1.04));
        data[idx + 3] = alpha;
      }
    }
    offctx.putImageData(imageData, 0, 0);

    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'screen';
    ctx.drawImage(offscreen, 0, 0);
    ctx.globalCompositeOperation = 'source-over';
  }

  function tick() {
    draw();
    requestAnimationFrame(tick);
  }

  window.addEventListener('resize', resize);
  resize();
  tick();
})();
