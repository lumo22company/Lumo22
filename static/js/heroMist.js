(function () {
    'use strict';

    var hero = document.getElementById('hero');
    var mistCanvas = document.getElementById('mist-canvas');
    var scrollIndicator = document.getElementById('scroll-indicator');
    if (!hero || !mistCanvas) return;

    var ctx = mistCanvas.getContext('2d');
    var MIST_W = 480;
    var MIST_H = 270;
    var startTime = Date.now();

    /* 3D value noise for organic fog */
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
        mistCanvas.width = MIST_W;
        mistCanvas.height = MIST_H;
        mistCanvas.style.width = '100%';
        mistCanvas.style.height = '100%';
    }

    function drawMist() {
        var now = Date.now();
        var t = now * 0.00006;
        var w = MIST_W;
        var h = MIST_H;
        var centerX = w * 0.5;
        var centerY = h * 0.5;
        var maxDist = Math.max(w, h) * 0.5;
        var imageData = ctx.createImageData(w, h);
        var data = imageData.data;

        for (var j = 0; j < h; j++) {
            for (var i = 0; i < w; i++) {
                var nx = (i / w) * 2 - 0.5;
                var ny = (j / h) * 2 - 0.5;

                var worldX1 = nx * 1.1 + t;
                var worldY1 = ny * 1.1 + t * 0.7;
                var worldZ1 = t * 0.9;
                var n1 = noise3D(worldX1, worldY1, worldZ1) * 0.5 + 0.5;

                var worldX2 = nx * 1.2 + t * 0.5 + 10;
                var worldY2 = ny * 1.2 + t * 0.4;
                var worldZ2 = t * 0.7 + 5;
                var n2 = noise3D(worldX2, worldY2, worldZ2) * 0.5 + 0.5;

                var n = n1 * 0.55 + n2 * 0.45;
                var warp = noise3D(nx * 0.35 + t * 0.25, ny * 0.35, t * 0.18) * 0.04;
                n = Math.max(0, Math.min(1, n + warp));

                var dx = i - centerX;
                var dy = j - centerY;
                var distFromCenter = Math.sqrt(dx * dx + dy * dy);
                var normDist = Math.min(1, distFromCenter / maxDist);
                var density = normDist < 0.38
                    ? lerp(0.45, 0.2, normDist / 0.38)
                    : lerp(0.2, 0, (normDist - 0.38) / 0.62);
                n *= density;

                var r = 255;
                var g = Math.floor(lerp(238, 228, n1));
                var b = Math.floor(lerp(224, 214, n2));
                var alpha = Math.floor(Math.min(1, n) * 255);

                var idx = (j * w + i) << 2;
                data[idx] = r;
                data[idx + 1] = Math.min(255, g);
                data[idx + 2] = Math.min(255, b);
                data[idx + 3] = alpha;
            }
        }
        ctx.putImageData(imageData, 0, 0);
    }

    function onScroll() {
        var y = window.scrollY || window.pageYOffset;
        if (y > 80) hero.classList.add('scrolled');
        else hero.classList.remove('scrolled');
    }

    window.addEventListener('scroll', function () { onScroll(); }, { passive: true });
    window.addEventListener('resize', resize);

    resize();
    onScroll();

    function tick() {
        drawMist();
        requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
})();
