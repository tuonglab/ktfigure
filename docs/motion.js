if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches && "IntersectionObserver" in window) {
  document.documentElement.classList.add("has-motion");

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.12, rootMargin: "0px 0px -5% 0px" },
  );

  document.querySelectorAll("[data-reveal]").forEach((element) => observer.observe(element));
}

const contents = document.querySelector(".contents");

if (contents) {
  const sections = Array.from(contents.querySelectorAll('a[href^="#"]'))
    .map((link) => ({
      link,
      target: document.getElementById(link.getAttribute("href").slice(1)),
    }))
    .filter(({ target }) => target);
  let scheduled = false;

  function updateCurrentSection() {
    scheduled = false;
    const readingLine = Math.min(window.innerHeight * 0.35, 240);
    let current = null;

    for (const section of sections) {
      if (section.target.getBoundingClientRect().top <= readingLine) {
        current = section;
      }
    }

    const last = sections[sections.length - 1];
    if (last && window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) {
      const bounds = last.target.getBoundingClientRect();
      if (bounds.top < window.innerHeight && bounds.bottom > 0) current = last;
    }

    for (const section of sections) {
      if (section === current) {
        section.link.setAttribute("aria-current", "location");
      } else {
        section.link.removeAttribute("aria-current");
      }
    }
  }

  function scheduleUpdate() {
    if (!scheduled) {
      scheduled = true;
      window.requestAnimationFrame(updateCurrentSection);
    }
  }

  window.addEventListener("scroll", scheduleUpdate, { passive: true });
  window.addEventListener("resize", scheduleUpdate);
  window.addEventListener("load", scheduleUpdate);
  scheduleUpdate();
}
