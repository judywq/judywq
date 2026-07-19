/*! Masonry gallery (React Bits–inspired).
 * https://reactbits.dev/components/masonry
 */
(function () {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const QUERIES = ["(min-width: 1200px)", "(min-width: 800px)", "(min-width: 520px)"];
  const COLUMN_COUNTS = [3, 3, 2];
  const DEFAULT_COLUMNS = 1;

  function columnsForViewport() {
    const i = QUERIES.findIndex((q) => window.matchMedia(q).matches);
    return i === -1 ? DEFAULT_COLUMNS : COLUMN_COUNTS[i];
  }

  function preload(urls) {
    return Promise.all(
      urls.map(
        (src) =>
          new Promise((resolve) => {
            const img = new Image();
            img.onload = img.onerror = () =>
              resolve({
                src,
                w: img.naturalWidth || 4,
                h: img.naturalHeight || 3,
              });
            img.src = src;
          })
      )
    );
  }

  function initMasonry(root) {
    const list = root.querySelector(".masonry-gallery__list");
    const items = Array.from(root.querySelectorAll(".masonry-gallery__item"));
    if (!list || !items.length) return;

    const metas = items.map((el, i) => ({
      el,
      id: el.dataset.key || String(i + 1),
      src: el.dataset.src || el.querySelector("img")?.src,
      ratio: Number(el.dataset.ratio) || 0,
    }));

    let width = 0;
    let hasMounted = false;
    let layoutRaf = null;

    function layout(ratios) {
      width = list.clientWidth;
      if (!width) return;

      const cols = columnsForViewport();
      const gap = 10;
      const colWidth = (width - gap * (cols - 1)) / cols;
      const colHeights = new Array(cols).fill(0);

      const grid = metas.map((meta, index) => {
        const ratio = ratios[index] || meta.ratio || 0.75;
        const col = colHeights.indexOf(Math.min(...colHeights));
        const h = colWidth * ratio;
        const x = col * (colWidth + gap);
        const y = colHeights[col];
        colHeights[col] += h + gap;
        return { ...meta, x, y, w: colWidth, h, index };
      });

      list.style.height = `${Math.max(...colHeights, 0)}px`;

      grid.forEach((item) => {
        const { el, x, y, w, h, index } = item;
        el.style.width = `${w}px`;
        el.style.height = `${h}px`;

        if (!hasMounted) {
          if (reduceMotion) {
            el.style.transform = `translate(${x}px, ${y}px)`;
            el.style.opacity = "1";
            el.style.filter = "none";
            el.classList.add("is-visible");
          } else {
            const startY = y + 120;
            el.style.transform = `translate(${x}px, ${startY}px)`;
            el.style.opacity = "0";
            el.style.filter = "blur(8px)";
            // Force style flush before revealing.
            void el.offsetWidth;
            el.style.transitionDelay = `${index * 0.05}s`;
            el.style.transform = `translate(${x}px, ${y}px)`;
            el.style.opacity = "1";
            el.style.filter = "blur(0)";
            el.classList.add("is-visible");
          }
        } else {
          el.style.transitionDelay = "0s";
          el.style.transform = `translate(${x}px, ${y}px)`;
        }
      });

      hasMounted = true;
      root.classList.add("is-ready");
    }

    function scheduleLayout(ratios) {
      cancelAnimationFrame(layoutRaf);
      layoutRaf = requestAnimationFrame(() => layout(ratios));
    }

    const urls = metas.map((m) => m.src).filter(Boolean);
    preload(urls).then((loaded) => {
      const ratios = metas.map((m, i) => {
        if (m.ratio) return m.ratio;
        const info = loaded[i];
        if (!info || !info.w) return 0.75;
        // Slight variety so equal photos still feel masonry-like.
        const base = info.h / info.w;
        const jitter = 0.92 + ((Number(m.id) * 17) % 7) * 0.025;
        return Math.min(1.35, Math.max(0.55, base * jitter));
      });

      scheduleLayout(ratios);

      const ro = new ResizeObserver(() => scheduleLayout(ratios));
      ro.observe(list);
      QUERIES.forEach((q) => {
        window.matchMedia(q).addEventListener("change", () => scheduleLayout(ratios));
      });
    });

    // Lightbox-ish: open full image (new tab keeps it simple & accessible).
    items.forEach((el) => {
      el.addEventListener("click", (e) => {
        const href = el.getAttribute("href") || el.dataset.src;
        if (!href) return;
        if (el.tagName === "A") return; // native navigation
        e.preventDefault();
        window.open(href, "_blank", "noopener");
      });
    });
  }

  function boot() {
    document.querySelectorAll("[data-masonry-gallery]").forEach(initMasonry);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
