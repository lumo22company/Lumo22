/**
 * Hero mist — x.ai style: smoky light around "Lumo 22", fades to black at edges.
 * Cursor gently disrupts the smoke (small radius, smooth lerp). Cursor does NOT glow.
 * Section-scoped to hero. GPU-friendly: single canvas, requestAnimationFrame.
 *
 * TWEAK: CURSOR_RADIUS — interaction size (px). CURSOR_SMOOTH — lerp for no jitter.
 * TWEAK: CENTER_DENSITY / EDGE_FALLOFF — mist intensity and halo size.
 */
(function () {
  'use strict';

  var hero = document.getElementById('lumo-hero');
  var canvas = document.getElementById('lumo-mist-canvas');
  if (!hero || !canvas) return;

  var ctx = canvas.getContext('2d');
  var W = 0;
  var H = 0;
  var startTime = Date.now();

  /* Mist: denser near logo, fade to black at edges. */
  var CENTER_DENSITY = 0.45;
  var EDGE_FALLOFF = 0.5;

  /* Cursor disrupt: small radius, smooth (no jitter). Cursor itself does not glow. */
  var CURSOR_RADIUS = 120;
  var CURSOR_SMOOTH = 0.08;
  var cursorTargetX = -1e5;
  var cursorTargetY = -1e5;
  var cursorX = -1e5;
  var cursorY = -1e5;
  var cursorActive = false;

  hero.addEventListener('mousemove', function (e) {
    var rect = hero.getBoundingClientRect();
    if (rect.bottom < 0 || rect.top > window.innerHeight) return;
    cursorTargetX = e.clientX;
    cursorTargetY = e.clientY;
    cursorActive = true;
  });
  hero.addEventListener('mouseleave', function () {
    cursorActive = false;
    cursorTargetX = -1e5;
    cursorTargetY = -1e5;
  });

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

  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W;
    canvas.height = H;
    canvas.style.width = '100%';
    canvas.style.height = '100%';
  }

  function draw() {
    /* Smooth cursor follow — avoids jitter. */
    cursorX = lerp(cursorX, cursorTargetX, CURSOR_SMOOTH);
    cursorY = lerp(cursorY, cursorTargetY, CURSOR_SMOOTH);

    var t = (Date.now() - startTime) * 0.00004;
    var centerX = W * 0.5;
    var centerY = H * 0.5;
    var maxDist = Math.max(W, H) * EDGE_FALLOFF;

    var imageData = ctx.createImageData(W, H);
    var data = imageData.data;

    for (var j = 0; j < H; j++) {
      for (var i = 0; i < W; i++) {
        var nx = (i / W) * 2 - 0.5;
        var ny = (j / H) * 2 - 0.5;

        var wx1 = nx * 1.1 + t;
        var wy1 = ny * 1.1 + t * 0.7;
        var wz1 = t * 0.9;
        var n1 = noise3D(wx1, wy1, wz1) * 0.5 + 0.5;

        var wx2 = nx * 1.2 + t * 0.5 + 10;
        var wy2 = ny * 1.2 + t * 0.4;
        var wz2 = t * 0.7 + 5;
        var n2 = noise3D(wx2, wy2, wz2) * 0.5 + 0.5;

        var n = n1 * 0.55 + n2 * 0.45;
        var warp = noise3D(nx * 0.35 + t * 0.25, ny * 0.35, t * 0.18) * 0.04;
        n = Math.max(0, Math.min(1, n + warp));

        var dx = i - centerX;
        var dy = j - centerY;
        var dist = Math.sqrt(dx * dx + dy * dy);
        var normDist = Math.min(1, dist / maxDist);
        var density = normDist < 0.35
          ? lerp(CENTER_DENSITY, 0.12, normDist / 0.35)
          : lerp(0.12, 0, (normDist - 0.35) / 0.65);
        n *= density;

        /* Cursor disrupt: reduce smoke density near cursor (gentle push-away). No glow on cursor. */
        if (cursorActive && CURSOR_RADIUS > 0) {
          var cdx = i - cursorX;
          var cdy = j - cursorY;
          var cdist = Math.sqrt(cdx * cdx + cdy * cdy);
          if (cdist < CURSOR_RADIUS) {
            var falloff = cdist / CURSOR_RADIUS;
            falloff = falloff * falloff;
            n *= lerp(0.25, 1, falloff);
          }
        }

        var r = Math.floor(lerp(8, 18, n1));
        var g = Math.floor(lerp(10, 20, n2));
        var b = Math.floor(lerp(16, 28, n));
        var alpha = Math.floor(Math.min(1, n * 1.1) * 200);

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
