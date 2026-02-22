/**
 * Scroll reveal — soft fade + slide when sections enter viewport.
 * Use data-reveal on elements; they get .revealed when in view. No aggressive parallax.
 */

(function () {
  'use strict';

  var selector = '[data-reveal]';
  var threshold = 0.12;
  var rootMargin = '0px 0px -10% 0px';

  function init() {
    var elements = document.querySelectorAll(selector);
    if (!elements.length) return;

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
          }
        });
      },
      { threshold: threshold, rootMargin: rootMargin }
    );

    elements.forEach(function (el) {
      observer.observe(el);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
