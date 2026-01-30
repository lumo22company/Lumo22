/**
 * Dark-mode atmospheric mist for hero background
 * Creates subtle, cinematic movement — inspired by x.ai/dayos aesthetic
 * Uses value noise for organic fog with cool undertones
 */
(function () {
  'use strict';

  var hero = document.getElementById('lumo-hero');
  var canvas = document.getElementById('lumo-mist-canvas');
  if (!hero || !canvas) return;

  var ctx = canvas.getContext('2d');
  var W = 480;
  var H = 270;
  var startTime = Date.now();

  /* Permutation table for value noise */
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
    canvas.width = W;
    canvas.height = H;
    canvas.style.width = '100%';
    canvas.style.height = '100%';
  }

  function draw() {
    var t = (Date.now() - startTime) * 0.00004;
    var centerX = W * 0.5;
    var centerY = H * 0.5;
    var maxDist = Math.max(W, H) * 0.55;
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
        var density = normDist < 0.4
          ? lerp(0.35, 0.15, normDist / 0.4)
          : lerp(0.15, 0, (normDist - 0.4) / 0.6);
        n *= density;

        /* Dark mode: deep blue-gray base with subtle warm center glow */
        var r = Math.floor(lerp(12, 20, n1));
        var g = Math.floor(lerp(14, 22, n2));
        var b = Math.floor(lerp(22, 32, n));
        var alpha = Math.floor(Math.min(1, n * 1.2) * 180);

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
