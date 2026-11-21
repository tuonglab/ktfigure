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
      button.textContent = theme === "dark" ? "Day mode" : "Night mode";
      button.setAttribute("aria-label", `Switch to ${theme === "dark" ? "day" : "night"} mode`);
    }
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
      applyTheme();
    });
  });
})();
