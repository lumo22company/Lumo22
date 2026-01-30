function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function handleScrollReveal() {
  document.querySelectorAll(".reveal-on-scroll").forEach(section => {
    const rect = section.getBoundingClientRect();
    const windowHeight = window.innerHeight;

    if (rect.top < windowHeight && rect.bottom > 0) {
      const visibleRatio = 1 - rect.top / windowHeight;
      const clamped = Math.min(Math.max(visibleRatio, 0), 1);
      const eased = easeOutCubic(clamped);

      const anim = section.dataset.anim || "left";
      let transform = "";
      let opacity = eased;

      switch (anim) {
        case "right":
          transform = `translateX(${60 * (1 - eased)}px)`;
          break;

        case "up":
          transform = `translateY(${40 * (1 - eased)}px)`;
          break;

        case "fade":
          transform = "translate(0,0)";
          break;

        case "scale":
          const scale = 0.95 + 0.05 * eased;
          transform = `scale(${scale})`;
          break;

        case "left":
        default:
          transform = `translateX(-${60 * (1 - eased)}px)`;
      }

      section.style.transform = transform;
      section.style.opacity = opacity;
    }
  });
}

window.addEventListener("scroll", handleScrollReveal);
window.addEventListener("load", handleScrollReveal);
