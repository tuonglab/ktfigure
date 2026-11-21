(() => {
  const key = "ktfigure-theme";
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  let choice = null;
  try {
    const saved = localStorage.getItem(key);
    if (saved === "light" || saved === "dark") choice = saved;
  } catch (error) {
    console.warn("Theme preference is unavailable:", error);
  }

  function applyTheme() {
    const theme = choice || (systemTheme.matches ? "dark" : "light");
    document.documentElement.dataset.theme = theme;
    const button = document.querySelector(".theme-toggle");
    if (button) {
      button.querySelector(".theme-toggle-label").textContent = theme === "dark" ? "Night" : "Day";
      button.setAttribute("aria-checked", String(theme === "dark"));
    }
  }

  function createWave(masked) {
    const width = window.innerWidth;
    const height = window.innerHeight;
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.classList.add(masked ? "theme-wave-mask" : "theme-wave-overlay");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);

    const defs = document.createElementNS(ns, "defs");
    const filter = document.createElementNS(ns, "filter");
    filter.id = "theme-wave-soften";
    filter.setAttribute("filterUnits", "userSpaceOnUse");
    filter.setAttribute("x", -width - 120);
    filter.setAttribute("y", -80);
    filter.setAttribute("width", width + 240);
    filter.setAttribute("height", height + 160);
    const blur = document.createElementNS(ns, "feGaussianBlur");
    blur.setAttribute("stdDeviation", "5");
    filter.appendChild(blur);
    defs.appendChild(filter);
    svg.appendChild(defs);

    const path = document.createElementNS(ns, "path");
    const offsets = [[45, 0], [16, .08], [39, .19], [6, .30], [30, .42],
      [0, .55], [35, .69], [8, .80], [26, 1]];
    const points = offsets.map(([x, fraction]) => ({
      x, y: -32 + fraction * (height + 64),
    }));
    let shape = `M ${-width - 80} -32 L ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length - 1; i++) {
      const point = points[i];
      const next = points[i + 1];
      shape += ` Q ${point.x} ${point.y} ${(point.x + next.x) / 2} ${(point.y + next.y) / 2}`;
    }
    const last = points[points.length - 1];
    shape += ` L ${last.x} ${last.y} L ${-width - 80} ${last.y} Z`;
    path.setAttribute("d", shape);
    path.setAttribute("fill", masked ? "white" : getComputedStyle(document.documentElement).getPropertyValue("--ink"));
    path.setAttribute("filter", "url(#theme-wave-soften)");

    if (masked) {
      const mask = document.createElementNS(ns, "mask");
      mask.id = "theme-wave-clip";
      mask.setAttribute("maskUnits", "userSpaceOnUse");
      mask.setAttribute("width", width);
      mask.setAttribute("height", height);
      mask.appendChild(path);
      defs.appendChild(mask);
    } else {
      svg.appendChild(path);
    }
    return { svg, path, start: -65, end: width + 20 };
  }

  function animateWave(wave, reverse = false) {
    const { path, start, end } = wave;
    return path.animate(
      [
        { transform: `translateX(${reverse ? end : start}px)` },
        { transform: `translateX(${reverse ? start : end}px)` },
      ],
      { duration: 1000, easing: "ease-in-out", fill: "forwards" },
    );
  }

  function fadeTheme(button) {
    const overlay = document.createElement("div");
    overlay.className = "theme-fade-overlay";
    overlay.setAttribute("aria-hidden", "true");
    overlay.style.background = getComputedStyle(document.documentElement).getPropertyValue("--surface");
    document.body.appendChild(overlay);
    overlay.animate([{ opacity: 0 }, { opacity: 1 }], {
      duration: 180, easing: "ease-in", fill: "forwards",
    }).finished
      .then(() => {
        applyTheme();
        return overlay.animate([{ opacity: 1 }, { opacity: 0 }], {
          duration: 180, easing: "ease-out", fill: "forwards",
        }).finished;
      })
      .catch((error) => {
        console.warn("Theme transition was interrupted:", error);
        applyTheme();
      })
      .finally(() => {
        overlay.remove();
        button.disabled = false;
      });
  }

  function switchTheme(button) {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches
        || typeof button.animate !== "function") {
      applyTheme();
      return;
    }
    button.disabled = true;

    if (window.matchMedia("(max-width: 750px)").matches) {
      fadeTheme(button);
      return;
    }

    if (typeof document.startViewTransition === "function") {
      const wave = createWave(true);
      wave.path.style.transform = `translateX(${wave.start}px)`;
      document.body.appendChild(wave.svg);
      document.documentElement.classList.add("theme-wiping");
      const transition = document.startViewTransition(applyTheme);
      transition.ready.then(() => animateWave(wave)).catch((error) => {
        console.warn("Theme transition was skipped:", error);
      });
      transition.finished
        .catch((error) => {
          console.warn("Theme transition did not finish:", error);
          applyTheme();
        })
        .finally(() => {
          document.documentElement.classList.remove("theme-wiping");
          wave.svg.remove();
          button.disabled = false;
        });
      return;
    }

    const wave = createWave(false);
    wave.path.style.transform = `translateX(${wave.start}px)`;
    document.body.appendChild(wave.svg);
    animateWave(wave).finished
      .then(() => {
        applyTheme();
        return animateWave(wave, true).finished;
      })
      .catch((error) => {
        console.warn("Theme transition was interrupted:", error);
        applyTheme();
      })
      .finally(() => {
        wave.svg.remove();
        button.disabled = false;
      });
  }

  applyTheme();
  systemTheme.addEventListener("change", () => {
    if (!choice) applyTheme();
  });
  document.addEventListener("DOMContentLoaded", () => {
    const button = document.querySelector(".theme-toggle");
    if (!button) return;
    button.hidden = false;
    applyTheme();
    button.addEventListener("click", () => {
      choice = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(key, choice);
      } catch (error) {
        console.warn("Could not save theme preference:", error);
      }
      switchTheme(button);
    });
  });
})();
