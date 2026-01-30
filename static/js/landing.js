/**
 * Landing page — scroll reveal, nav behavior
 */

(function () {
  'use strict';

  var nav = document.getElementById('lumo-nav');
  var hero = document.getElementById('lumo-hero');

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function handleScroll() {
    var y = window.scrollY || window.pageYOffset;
    if (nav) nav.classList.toggle('scrolled', y > 60);

    document.querySelectorAll('.lumo-reveal[data-reveal]').forEach(function (el) {
      var rect = el.getBoundingClientRect();
      var winH = window.innerHeight;
      if (rect.top < winH * 0.85 && rect.bottom > 0) {
        var ratio = 1 - rect.top / winH;
        var eased = easeOutCubic(Math.min(Math.max(ratio, 0), 1));
        if (eased > 0.2) el.classList.add('visible');
      }
    });
  }

  window.addEventListener('scroll', handleScroll, { passive: true });
  window.addEventListener('load', handleScroll);
})();
