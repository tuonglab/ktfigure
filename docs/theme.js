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
    const size = 36;
    const columns = Math.ceil(window.innerWidth / size);
    const rows = Math.ceil(window.innerHeight / size);
    const result = [];
    for (let row = 0; row < rows; row++) {
      for (let column = 0; column < columns; column++) {
        const delay = 540 * column / Math.max(columns - 1, 1)
          + 110 * row / Math.max(rows - 1, 1)
          + ((column * 7 + row * 11) % 7) * 9;
        result.push({ element: createTile(column, row, size), delay });
      }
    }
    return result;
  }

  function animateTiles(items, from, to) {
    return items.map(({ element, delay }) => element.animate(
      [{ transform: `scaleY(${from})` }, { transform: `scaleY(${to})` }],
      { duration: 220, delay, easing: "ease-in-out", fill: "forwards" },
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
      const clip = document.createElementNS("http://www.w3.org/2000/svg", "clipPath");
      clip.id = "theme-wave-clip";
      clip.setAttribute("clipPathUnits", "userSpaceOnUse");
      svg.appendChild(clip);
      const items = tiles((column, row, size) => {
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", column * size);
        rect.setAttribute("y", row * size);
        rect.setAttribute("width", size + 1);
        rect.setAttribute("height", size + 1);
        rect.style.transformBox = "fill-box";
        rect.style.transformOrigin = "top";
        rect.style.transform = "scaleY(0)";
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
    overlay.style.gridTemplateColumns = `repeat(${Math.ceil(window.innerWidth / 36)}, 1fr)`;
    overlay.style.gridTemplateRows = `repeat(${Math.ceil(window.innerHeight / 36)}, 1fr)`;
    overlay.style.setProperty("--wave-color", getComputedStyle(document.documentElement).getPropertyValue("--ink"));
    const items = tiles(() => {
      const tile = document.createElement("span");
      tile.className = "theme-wave-tile";
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
