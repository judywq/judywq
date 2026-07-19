/*! Circular gallery (React Bits–inspired). Drag or scroll to rotate. */
(function () {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function initGallery(root) {
    const ring = root.querySelector(".circular-gallery__ring");
    const items = root.querySelectorAll(".circular-gallery__item");
    if (!ring || !items.length) return;

    const count = items.length;
    root.style.setProperty("--cg-count", String(count));
    items.forEach((item, i) => item.style.setProperty("--i", String(i)));

    let rotation = 0;
    let dragging = false;
    let pointerId = null;
    let startX = 0;
    let startRot = 0;
    let velocity = 0;
    let lastX = 0;
    let lastT = 0;
    let raf = null;
    let autoplay = !reduceMotion;

    function setRotation(value) {
      rotation = value;
      ring.style.setProperty("--cg-rotate", `${rotation}deg`);
    }

    function tickAutoplay() {
      if (!autoplay || dragging) {
        raf = null;
        return;
      }
      setRotation(rotation + 0.08);
      raf = requestAnimationFrame(tickAutoplay);
    }

    function startAutoplay() {
      if (reduceMotion || raf) return;
      autoplay = true;
      raf = requestAnimationFrame(tickAutoplay);
    }

    function stopAutoplay() {
      autoplay = false;
      if (raf) {
        cancelAnimationFrame(raf);
        raf = null;
      }
    }

    const viewport = root.querySelector(".circular-gallery__viewport") || root;

    viewport.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      dragging = true;
      pointerId = e.pointerId;
      startX = e.clientX;
      startRot = rotation;
      lastX = e.clientX;
      lastT = performance.now();
      velocity = 0;
      stopAutoplay();
      viewport.setPointerCapture(e.pointerId);
      viewport.classList.add("is-dragging");
    });

    viewport.addEventListener("pointermove", (e) => {
      if (!dragging || e.pointerId !== pointerId) return;
      const dx = e.clientX - startX;
      setRotation(startRot + dx * 0.35);
      const now = performance.now();
      const dt = Math.max(now - lastT, 1);
      velocity = ((e.clientX - lastX) / dt) * 12;
      lastX = e.clientX;
      lastT = now;
    });

    function endDrag(e) {
      if (!dragging || (e && e.pointerId !== pointerId)) return;
      dragging = false;
      pointerId = null;
      viewport.classList.remove("is-dragging");
      if (!reduceMotion) {
        const coast = () => {
          if (Math.abs(velocity) < 0.05) {
            startAutoplay();
            return;
          }
          setRotation(rotation + velocity);
          velocity *= 0.94;
          requestAnimationFrame(coast);
        };
        requestAnimationFrame(coast);
      }
    }

    viewport.addEventListener("pointerup", endDrag);
    viewport.addEventListener("pointercancel", endDrag);

    viewport.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        stopAutoplay();
        setRotation(rotation + e.deltaY * 0.08 + e.deltaX * 0.08);
        clearTimeout(viewport._cgWheelTimer);
        viewport._cgWheelTimer = setTimeout(startAutoplay, 900);
      },
      { passive: false }
    );

    viewport.addEventListener("mouseenter", stopAutoplay);
    viewport.addEventListener("mouseleave", () => {
      if (!dragging) startAutoplay();
    });

    setRotation(0);
    startAutoplay();
  }

  function boot() {
    document.querySelectorAll("[data-circular-gallery]").forEach(initGallery);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
