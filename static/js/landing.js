/**
 * Landing page — scroll reveal, nav behavior, hero scroll indicator.
 * Works with native scroll or Lenis (listens for lumoscroll when Lenis is active).
 */

(function () {
  'use strict';

  var nav = document.getElementById('lumo-nav');
  var heroScroll = document.getElementById('hero-scroll');
  var scrollHideThreshold = 80;
  var navSolidThreshold = 60;

  function getScrollY() {
    return window.lenis ? window.lenis.scroll : (window.scrollY || window.pageYOffset);
  }

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function handleScroll(ev) {
    var y = (ev && ev.detail && ev.detail.scrollY !== undefined) ? ev.detail.scrollY : getScrollY();
    if (nav) nav.classList.toggle('scrolled', y > navSolidThreshold);
    if (heroScroll) heroScroll.classList.toggle('hidden', y > scrollHideThreshold);

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

  if (heroScroll) {
    heroScroll.addEventListener('click', function () {
      var target = document.getElementById('what-is-lumo');
      if (target) {
        if (window.lenis) {
          window.lenis.scrollTo(target, { offset: 0, duration: 1.2 });
        } else {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
    heroScroll.style.cursor = 'pointer';
  }

  var heroCta = document.querySelector('.hero-cta');
  if (heroCta) {
    heroCta.addEventListener('click', function (e) {
      var target = document.getElementById('lumo-split');
      if (target) {
        e.preventDefault();
        if (window.lenis) {
          window.lenis.scrollTo(target, { offset: 0, duration: 1.2 });
        } else {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  }

  window.addEventListener('scroll', handleScroll, { passive: true });
  window.addEventListener('lumoscroll', handleScroll);
  window.addEventListener('load', function () { handleScroll(); });
})();
