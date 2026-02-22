/**
 * Split section — dayos-style subtle parallax.
 * Apply translateY ONLY to .split-content. Do NOT move the section.
 * Scroll progress 0 → 1; max movement 40px; opposite directions for left/right panels.
 */

(function () {
  'use strict';

  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var section = document.getElementById('lumo-split');
  if (!section) return;

  var leftContent = section.querySelector('.split-left .split-content');
  var rightContent = section.querySelector('.split-right .split-content');

  if (!leftContent || !rightContent) return;

  var MAX_MOVE = 40;

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function update() {
    var rect = section.getBoundingClientRect();
    var winH = window.innerHeight;
    var sectionH = rect.height;

    var progress = 0;
    if (rect.top < winH && rect.bottom > 0) {
      var visibleStart = winH - rect.top;
      progress = visibleStart / (winH + sectionH);
      progress = Math.max(0, Math.min(1, progress));
      progress = easeOutCubic(progress);
    }

    var leftY = (1 - progress) * MAX_MOVE;
    var rightY = (1 - progress) * -MAX_MOVE;

    leftContent.style.transform = 'translateY(' + leftY + 'px)';
    rightContent.style.transform = 'translateY(' + rightY + 'px)';
  }

  function onScroll() {
    requestAnimationFrame(update);
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('lumoscroll', onScroll);
  window.addEventListener('resize', onScroll);
  window.addEventListener('load', update);
  update();
})();
