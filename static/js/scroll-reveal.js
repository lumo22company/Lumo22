/**
 * Scroll reveal — soft fade + slide when sections enter viewport.
 * Use data-reveal on elements; they get .revealed when in view. No aggressive parallax.
 *
 * The CSS that hides these elements is scoped to html.js-reveal, and this file is what adds
 * that class. So the page only ever goes invisible when this script is running and able to
 * bring it back: if the file fails to load, is blocked, or the browser has no
 * IntersectionObserver, everything renders as plain visible text instead of a blank page.
 */

(function () {
  'use strict';

  var selector = '[data-reveal]';
  var threshold = 0.12;
  var rootMargin = '0px 0px -10% 0px';
  // Backstop for content sitting on screen that the observer never fired for (layout shift,
  // element inside a scroll container, threshold never met). Only on-screen elements are
  // forced visible — anything further down keeps its reveal-on-scroll animation.
  var FAILSAFE_MS = 2500;

  function revealVisible(elements) {
    for (var i = 0; i < elements.length; i++) {
      var rect = elements[i].getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.bottom > 0) {
        elements[i].classList.add('revealed');
      }
    }
  }

  function init() {
    var elements = document.querySelectorAll(selector);
    if (!elements.length) return;

    // No observer support: leave the page in its plain visible state.
    if (typeof window.IntersectionObserver !== 'function') return;

    document.documentElement.classList.add('js-reveal');

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: threshold, rootMargin: rootMargin }
    );

    elements.forEach(function (el) {
      observer.observe(el);
    });

    window.setTimeout(function () {
      revealVisible(document.querySelectorAll(selector + ':not(.revealed)'));
    }, FAILSAFE_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
