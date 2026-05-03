/**
 * Dayos-style section parallax — scroll-driven translateY for blocks.
 * Content moves at a slightly different rate to create depth (parallax).
 * Landing: .block[data-reveal] .block-inner. Captions (/captions): .dfd-section-inner
 * in .product-page-captions .dfd-section.captions-reveal (hero is .dfd-hero, excluded).
 * Respects prefers-reduced-motion.
 */
(function () {
  'use strict';

  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  /* Landing: .block inner. Captions product: .dfd-section-inner inside scrolled sections. */
  var blocks = document.querySelectorAll(
    '.block[data-reveal] .block-inner, .product-page-captions .dfd-section.captions-reveal .dfd-section-inner'
  );
  if (!blocks.length) return;

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
