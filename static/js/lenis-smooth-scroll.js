/**
 * Dayos-style smooth scrolling via Lenis.
 * Uses requestAnimationFrame loop; respects prefers-reduced-motion.
 * Anchor links (#lumo-split etc.) scroll smoothly via Lenis.
 */
(function () {
  'use strict';

  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (typeof Lenis === 'undefined') return;

  var lenis = new Lenis({
    duration: 1.2,
    easing: function (t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); },
    smoothWheel: true,
    touchMultiplier: 2
  });

  function raf(time) {
    lenis.raf(time);
    requestAnimationFrame(raf);
  }
  requestAnimationFrame(raf);

  lenis.on('scroll', function () {
    window.dispatchEvent(new CustomEvent('lumoscroll', { detail: { scrollY: lenis.scroll } }));
  });

  document.addEventListener('DOMContentLoaded', function () {
    document.documentElement.classList.add('lenis');
  });

  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    var href = anchor.getAttribute('href');
    if (href === '#') return;
    anchor.addEventListener('click', function (e) {
      var id = href.slice(1);
      var target = document.getElementById(id);
      if (target) {
        e.preventDefault();
        lenis.scrollTo(target, { offset: 0, duration: 1.2 });
      }
    });
  });

  window.lenis = lenis;
})();
