/**
 * Dayos-style section parallax — scroll-driven translateY for blocks.
 * Content moves at a slightly different rate to create depth (parallax).
 * Respects prefers-reduced-motion.
 */
(function () {
  'use strict';

  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var blocks = document.querySelectorAll('.block[data-reveal] .block-inner, .dfd-section[data-reveal] .dfd-section-inner, .intro[data-reveal] .section-inner');
  var heroInners = document.querySelectorAll('.dfd-hero .dfd-hero-inner, .hero.section-dark .section-inner');
  if (!blocks.length && !heroInners.length) return;

  var MAX_LAG = 24;
  var getScrollY = function () {
    return window.lenis ? window.lenis.scroll : (window.scrollY || window.pageYOffset);
  };

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function update() {
    var scrollY = getScrollY();
    var winH = window.innerHeight;

    heroInners.forEach(function (el) {
      var hero = el.closest('.dfd-hero, .hero');
      if (!hero) return;
      var rect = hero.getBoundingClientRect();
      if (rect.bottom > 0 && rect.top < winH) {
        var ty = scrollY * 0.12;
        el.style.transform = 'translateY(' + ty + 'px)';
      } else {
        el.style.transform = '';
      }
    });

    blocks.forEach(function (el) {
      var section = el.closest('section');
      if (!section) return;
      var rect = section.getBoundingClientRect();
      var sectionTop = rect.top + scrollY;
      var sectionH = section.offsetHeight;

      var progress = 0;
      if (rect.top < winH && rect.bottom > 0) {
        var visibleStart = winH - rect.top;
        progress = visibleStart / (winH + sectionH);
        progress = Math.max(0, Math.min(1, progress));
        progress = easeOutCubic(progress);
      }

      var ty = (1 - progress) * MAX_LAG;
      el.style.transform = 'translateY(' + ty + 'px)';
    });
  }

  function onScroll() {
    requestAnimationFrame(update);
  }

  if (window.lenis) {
    window.lenis.on('scroll', onScroll);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('lumoscroll', onScroll);
  window.addEventListener('resize', onScroll);
  window.addEventListener('load', update);
  update();
})();
