/**
 * Hero bullets parallax — scroll-driven translateY for dfd-hero-bullets.
 * Bullets lag slightly as you scroll past the hero for subtle depth.
 * Respects prefers-reduced-motion.
 */
(function () {
  'use strict';

  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var hero = document.getElementById('captions-hero');
  var bullets = hero ? hero.querySelector('.dfd-hero-bullets') : null;
  if (!bullets) return;

  var MAX_LAG = 20;

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function update() {
    var scrollY = window.scrollY || window.pageYOffset;
    var winH = window.innerHeight;
    var rect = hero.getBoundingClientRect();
    var sectionH = hero.offsetHeight;

    var progress = 0;
    if (rect.top < winH && rect.bottom > 0) {
      var visibleStart = winH - rect.top;
      progress = visibleStart / (winH + sectionH);
      progress = Math.max(0, Math.min(1, progress));
      progress = easeOutCubic(progress);
    }

    var ty = (1 - progress) * MAX_LAG;
    bullets.style.transform = 'translateY(' + ty + 'px)';
  }

  function onScroll() {
    requestAnimationFrame(update);
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  if (window.lenis) window.lenis.on('scroll', onScroll);
  window.addEventListener('lumoscroll', onScroll);
  window.addEventListener('resize', onScroll);
  window.addEventListener('load', update);
  update();
})();
