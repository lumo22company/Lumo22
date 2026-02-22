/**
 * Hero canvas — motion-first, canvas-driven volumetric mist (x.ai reference).
 * Canvas covers full viewport. Animated smoke: densest around "Lumo 22", fades to black at edges.
 * Cursor subtly displaces mist (small radius, smooth easing). Cursor does NOT glow.
 * Isolated to hero section only. No CSS gradients or blur — all mist is canvas-rendered.
 */
(function () {
  'use strict';

  var hero = document.getElementById('hero');
  var canvas = document.getElementById('hero-canvas');
  if (!hero || !canvas) return;

  var ctx = canvas.getContext('2d');
  var W = 0;
  var H = 0;
  var startTime = Date.now();

  /* Volumetric mist: density at center (around wordmark). Edge = how far from center before black. */
  var CENTER_DENSITY = 0.52;
  var EDGE_FALLOFF = 0.42;

  /* Cursor: small radius, smooth lerp (no jitter). Displaces mist; cursor itself does not glow. */
  var CURSOR_RADIUS = 140;
  var CURSOR_SMOOTH = 0.06;
  var cursorTargetX = -1e6;
  var cursorTargetY = -1e6;
  var cursorX = -1e6;
  var cursorY = -1e6;
  var cursorActive = false;

  hero.addEventListener('mousemove', function (e) {
    var r = hero.getBoundingClientRect();
    if (r.bottom < 0 || r.top > window.innerHeight) return;
    cursorTargetX = e.clientX;
    cursorTargetY = e.clientY;
    cursorActive = true;
  });
  hero.addEventListener('mouseleave', function () {
    cursorActive = false;
    cursorTargetX = -1e6;
    cursorTargetY = -1e6;
  });

  /* Permutation for 3D noise (reusable). */
  var perm = [];
  for (var i = 0; i < 256; i++) perm[i] = Math.floor(Math.random() * 256);
  for (var i = 256; i < 512; i++) perm[i] = perm[i & 255];

  function fade(t) { return t * t * (3 - 2 * t); }
  function lerp(a, b, t) { return a + t * (b - a); }
  function hash(ix, iy, iz) {
    return perm[(ix + perm[(iy & 255) + perm[iz & 255]]) & 255] / 255;
  }
  function noise3D(x, y, z) {
    var ix = Math.floor(x), iy = Math.floor(y), iz = Math.floor(z);
    var fx = fade(x - ix), fy = fade(y - iy), fz = fade(z - iz);
    var n000 = hash(ix, iy, iz), n100 = hash(ix + 1, iy, iz);
    var n010 = hash(ix, iy + 1, iz), n110 = hash(ix + 1, iy + 1, iz);
    var n001 = hash(ix, iy, iz + 1), n101 = hash(ix + 1, iy, iz + 1);
    var n011 = hash(ix, iy + 1, iz + 1), n111 = hash(ix + 1, iy + 1, iz + 1);
    return lerp(lerp(lerp(n000, n100, fx), lerp(n010, n110, fx), fy),
                lerp(lerp(n001, n101, fx), lerp(n011, n111, fx), fy), fz);
  }

  /* Multi-octave noise for more volumetric, cloud-like mist. */
  function noiseVol(x, y, z) {
    var n = 0;
    n += 0.5 * (noise3D(x, y, z) * 0.5 + 0.5);
    n += 0.3 * (noise3D(x * 2 + 1.3, y * 2, z * 1.5 + 2) * 0.5 + 0.5);
    n += 0.2 * (noise3D(x * 4, y * 4 + 5, z * 2 + 7) * 0.5 + 0.5);
    return Math.max(0, Math.min(1, n));
  }

  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W;
    canvas.height = H;
    canvas.style.width = '100%';
    canvas.style.height = '100%';
  }

  function draw() {
    cursorX = lerp(cursorX, cursorTargetX, CURSOR_SMOOTH);
    cursorY = lerp(cursorY, cursorTargetY, CURSOR_SMOOTH);

    var t = (Date.now() - startTime) * 0.00003;
    var centerX = W * 0.5;
    var centerY = H * 0.5;
    var maxDist = Math.max(W, H) * EDGE_FALLOFF;

    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);

    var imageData = ctx.createImageData(W, H);
    var data = imageData.data;

    for (var j = 0; j < H; j++) {
      for (var i = 0; i < W; i++) {
        var u = i / W;
        var v = j / H;
        var nx = u * 2.2 - 0.1 + t;
        var ny = v * 2.2 - 0.1 + t * 0.8;
        var nz = t * 0.6;

        var n = noiseVol(nx, ny, nz);
        var warp = noise3D(u * 0.4 + t * 0.2, v * 0.4, nz * 0.3) * 0.05;
        n = Math.max(0, Math.min(1, n + warp));

        var dx = i - centerX;
        var dy = j - centerY;
        var dist = Math.sqrt(dx * dx + dy * dy);
        var normDist = Math.min(1, dist / maxDist);
        var density = normDist < 0.3
          ? lerp(CENTER_DENSITY, 0.08, normDist / 0.3)
          : lerp(0.08, 0, (normDist - 0.3) / 0.7);
        n *= density;

        /* Cursor displaces mist: reduce density near cursor (smooth falloff). No glow. */
        if (cursorActive && CURSOR_RADIUS > 0) {
          var cdx = i - cursorX;
          var cdy = j - cursorY;
          var cdist = Math.sqrt(cdx * cdx + cdy * cdy);
          if (cdist < CURSOR_RADIUS) {
            var f = cdist / CURSOR_RADIUS;
            f = f * f * (3 - 2 * f);
            n *= lerp(0.2, 1, f);
          }
        }

        var r = Math.floor(lerp(5, 22, n));
        var g = Math.floor(lerp(6, 24, n));
        var b = Math.floor(lerp(10, 30, n));
        var alpha = Math.floor(Math.min(1, n * 1.05) * 220);

        var idx = (j * W + i) << 2;
        data[idx] = r;
        data[idx + 1] = g;
        data[idx + 2] = b;
        data[idx + 3] = alpha;
      }
    }
    ctx.putImageData(imageData, 0, 0);
  }

  function tick() {
    draw();
    requestAnimationFrame(tick);
  }

  window.addEventListener('resize', resize);
  resize();
  tick();
})();
