(function () {
    'use strict';

    var hero = document.getElementById('hero');
    var mistContainer = document.getElementById('mist-container');
    var mistCanvas = document.getElementById('mist-canvas');
    var scrollIndicator = document.getElementById('scroll-indicator');

    if (!hero || !mistCanvas) return;

    var ctx = mistCanvas.getContext('2d');
    var MIST_W = 480;
    var MIST_H = 270;
    var cursorRadiusPx = 36;
    var cursorStrength = 0.85;
    var smoothFactor = 0.12;
    var mouseX = 0.5;
    var mouseY = 0.5;
    var smoothX = 0.5;
    var smoothY = 0.5;
    var scrollY = 0;
    var scrollThrottle = null;
    var scrollIndicatorThreshold = 80;
    var parallaxMist = 0.35;
    var startTime = Date.now();

    /* ----- 3D value noise (Perlin-like) ----- */
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

    function resizeMist() {
        mistCanvas.width = MIST_W;
        mistCanvas.height = MIST_H;
        mistCanvas.style.width = '100%';
        mistCanvas.style.height = '100%';
    }

    function drawMist() {
        var now = Date.now();
        var t = now * 0.00008;
        var w = MIST_W;
        var h = MIST_H;
        var centerX = w * 0.5;
        var centerY = h * 0.5;
        var maxDist = Math.max(w, h) * 0.52;
        var imageData = ctx.createImageData(w, h);
        var data = imageData.data;

        smoothX += (mouseX - smoothX) * smoothFactor;
        smoothY += (mouseY - smoothY) * smoothFactor;
        var cursorCanvasX = smoothX * w;
        var cursorCanvasY = smoothY * h;

        for (var j = 0; j < h; j++) {
            for (var i = 0; i < w; i++) {
                var nx = (i / w) * 2 - 0.5;
                var ny = (j / h) * 2 - 0.5;

                var worldX1 = nx * 1.1 + t;
                var worldY1 = ny * 1.1 + t * 0.7;
                var worldZ1 = t * 0.9;
                var n1 = noise3D(worldX1, worldY1, worldZ1) * 0.5 + 0.5;

                var worldX2 = nx * 1.2 + t * 0.6 + 10;
                var worldY2 = ny * 1.2 + t * 0.5;
                var worldZ2 = t * 0.7 + 5;
                var n2 = noise3D(worldX2, worldY2, worldZ2) * 0.5 + 0.5;

                var n = n1 * 0.55 + n2 * 0.45;
                var warp = noise3D(nx * 0.4 + t * 0.3, ny * 0.4, t * 0.2) * 0.04;
                n = Math.max(0, Math.min(1, n + warp));

                var dx = (i - centerX);
                var dy = (j - centerY);
                var distFromCenter = Math.sqrt(dx * dx + dy * dy);
                var normDist = Math.min(1, distFromCenter / maxDist);
                var density = normDist < 0.4
                    ? lerp(0.42, 0.2, normDist / 0.4)
                    : lerp(0.2, 0, (normDist - 0.4) / 0.6);
                n *= density;

                var distFromCursor = Math.sqrt((i - cursorCanvasX) * (i - cursorCanvasX) + (j - cursorCanvasY) * (j - cursorCanvasY));
                var cursorFalloff = Math.exp(-(distFromCursor * distFromCursor) / (cursorRadiusPx * cursorRadiusPx * 1.2));
                n = Math.max(0, n - cursorStrength * cursorFalloff);

                var r = 255;
                var g = Math.floor(lerp(242, 232, n1));
                var b = Math.floor(lerp(228, 218, n2));
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

    function applyParallax() {
        var y = window.scrollY || window.pageYOffset;
        if (mistContainer) mistContainer.style.transform = 'translate3d(0, ' + (y * parallaxMist) + 'px, 0)';
    }

    function onScroll() {
        scrollY = window.scrollY || window.pageYOffset;
        if (scrollY > scrollIndicatorThreshold) {
            hero.classList.add('scrolled');
        } else {
            hero.classList.remove('scrolled');
        }
        applyParallax();
    }

    function tick() {
        drawMist();
        requestAnimationFrame(tick);
    }

    hero.addEventListener('mousemove', function (e) {
        mouseX = e.clientX / window.innerWidth;
        mouseY = e.clientY / window.innerHeight;
    });

    window.addEventListener('scroll', function () {
        if (scrollThrottle) return;
        scrollThrottle = requestAnimationFrame(function () {
            onScroll();
            scrollThrottle = null;
        });
    }, { passive: true });

    window.addEventListener('resize', function () {
        resizeMist();
        applyParallax();
    });

    resizeMist();
    onScroll();
    requestAnimationFrame(tick);
})();
