/**
 * Split section parallax — section-scoped, dayos.com style.
 * Panels move at different speeds (data-speed). Content: headings slide opposite directions, text fades.
 * Uses transform: translate3d only; no layout shift, no page container movement.
 *
 * TWEAK: data-speed on .lumo-split-panel — e.g. 0.08 and -0.06. Higher absolute = more movement.
 * TWEAK: Content slide distance — CONTENT_OFFSET_LEFT / CONTENT_OFFSET_RIGHT (px). Animation timing in CSS.
 */
(function () {
  'use strict';

  var section = document.getElementById('lumo-split');
  if (!section) return;

  var panels = section.querySelectorAll('.lumo-split-panel[data-speed]');
  var inner = section.querySelector('.lumo-split-inner');

  /* Distance (px) content moves on scroll. Increase for stronger slide-in. */
  var CONTENT_OFFSET_LEFT = 48;
  var CONTENT_OFFSET_RIGHT = 48;

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function update() {
    var rect = section.getBoundingClientRect();
    var winH = window.innerHeight;
    var sectionTop = rect.top;
    var sectionHeight = rect.height;

    /* Progress: 0 = section just entering viewport bottom, 1 = section fully scrolled past. */
    var progress = 0;
    if (sectionTop < winH && sectionTop + sectionHeight > 0) {
      var visibleStart = Math.max(0, winH - sectionTop - sectionHeight);
      progress = Math.min(1, Math.max(0, visibleStart / (winH + sectionHeight * 0.5)));
      progress = easeOutCubic(progress);
    }

    /* Panel parallax: translateY by data-speed * scroll progress. */
    panels.forEach(function (panel) {
      var speed = parseFloat(panel.getAttribute('data-speed')) || 0;
      var move = (winH * 0.15) * speed * progress;
      panel.style.transform = 'translate3d(0, ' + move + 'px, 0)';

      var content = panel.querySelector('.lumo-split-content');
      if (!content) return;

      var isLeft = panel.classList.contains('lumo-split-left');
      var offset = isLeft ? CONTENT_OFFSET_LEFT : -CONTENT_OFFSET_RIGHT;
      var contentX = offset * (1 - progress);
      var opacity = 0.4 + 0.6 * progress;
      content.style.transform = 'translate3d(' + contentX + 'px, 0, 0)';
      content.style.opacity = opacity;
    });
  }

  function onScroll() {
    requestAnimationFrame(update);
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', update);
  window.addEventListener('load', update);
  update();
})();
