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

  function tiles(createTile) {
    const scale = Math.max(1, Math.sqrt(window.innerWidth * window.innerHeight / 2073600));
    const widths = [19, 26, 22, 29, 21, 25, 18, 27, 23];
    function segments(limit, offset) {
      const result = [];
      let position = 0;
      while (position < limit) {
        const size = Math.round(widths[(result.length + offset) % widths.length] * scale);
        result.push({ position, size });
        position += size;
      }
      return result;
    }
    const columns = segments(window.innerWidth, 0);
    const rows = segments(window.innerHeight, 4);
    const result = [];
    for (let row = 0; row < rows.length; row++) {
      for (let column = 0; column < columns.length; column++) {
        const x = columns[column].position;
        const y = rows[row].position;
        const delay = 650 * x / window.innerWidth + 100 * y / window.innerHeight
          + ((column * 7 + row * 11) % 7) * 8;
        result.push({
          element: createTile(x, y, columns[column].size, rows[row].size),
          delay,
        });
      }
    }
    return result;
  }

  function animateTiles(items, from, to) {
    return items.map(({ element, delay }) => element.animate(
      [
        { transform: `scaleY(${from})`, opacity: from },
        { transform: `scaleY(${to})`, opacity: to },
      ],
      { duration: 320, delay, easing: "ease-in-out", fill: "forwards" },
    ));
  }

  function switchTheme(button) {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches
        || typeof button.animate !== "function") {
      applyTheme();
      return;
    }
    button.disabled = true;

    if (typeof document.startViewTransition === "function") {
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.classList.add("theme-wave-mask");
      svg.setAttribute("aria-hidden", "true");
      const clip = document.createElementNS("http://www.w3.org/2000/svg", "mask");
      clip.id = "theme-wave-clip";
      clip.setAttribute("maskUnits", "userSpaceOnUse");
      clip.setAttribute("width", window.innerWidth);
      clip.setAttribute("height", window.innerHeight);
      svg.appendChild(clip);
      const items = tiles((x, y, width, height) => {
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", x);
        rect.setAttribute("y", y);
        rect.setAttribute("width", width + 1);
        rect.setAttribute("height", height + 1);
        rect.setAttribute("fill", "white");
        rect.style.transformBox = "fill-box";
        rect.style.transformOrigin = "top";
        rect.style.transform = "scaleY(0)";
        rect.style.opacity = "0";
        clip.appendChild(rect);
        return rect;
      });
      document.body.appendChild(svg);
      document.documentElement.classList.add("theme-wiping");
      const transition = document.startViewTransition(applyTheme);
      transition.ready.then(() => animateTiles(items, 0, 1)).catch((error) => {
        console.warn("Theme transition was skipped:", error);
      });
      transition.finished
        .catch((error) => {
          console.warn("Theme transition did not finish:", error);
          applyTheme();
        })
        .finally(() => {
          document.documentElement.classList.remove("theme-wiping");
          svg.remove();
          button.disabled = false;
        });
      return;
    }

    const overlay = document.createElement("div");
    overlay.className = "theme-wave-overlay";
    overlay.setAttribute("aria-hidden", "true");
    overlay.style.setProperty("--wave-color", getComputedStyle(document.documentElement).getPropertyValue("--ink"));
    const items = tiles((x, y, width, height) => {
      const tile = document.createElement("span");
      tile.className = "theme-wave-tile";
      Object.assign(tile.style, {
        left: `${x}px`, top: `${y}px`, width: `${width + 1}px`, height: `${height + 1}px`,
      });
      overlay.appendChild(tile);
      return tile;
    });
    document.body.appendChild(overlay);
    Promise.all(animateTiles(items, 0, 1).map((animation) => animation.finished))
      .then(() => {
        applyTheme();
        return Promise.all(animateTiles(items, 1, 0).map((animation) => animation.finished));
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
