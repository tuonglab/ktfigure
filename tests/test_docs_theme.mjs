import { readFile } from "node:fs/promises";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import assert from "node:assert/strict";

const source = await readFile(new URL("../docs/theme.js", import.meta.url), "utf8");

function page({ saved = null, dark = false, storageFails = false, reducedMotion = false } = {}) {
  const listeners = {};
  const label = {};
  const button = {
    hidden: true,
    querySelector: () => label,
    setAttribute(name, value) { this[name] = value; },
    addEventListener(name, callback) { listeners[name] = callback; },
  };
  const media = {
    matches: dark,
    addEventListener(name, callback) { listeners.system = callback; },
  };
  const document = {
    documentElement: { dataset: {} },
    querySelector: () => button,
    addEventListener(name, callback) { listeners.ready = callback; },
  };
  const localStorage = {
    getItem() { if (storageFails) throw Error("unavailable"); return saved; },
    setItem(key, value) { if (storageFails) throw Error("unavailable"); saved = value; },
  };
  runInNewContext(source, {
    document, localStorage, window: {
      matchMedia: (query) => query.includes("reduced-motion") ? { matches: reducedMotion } : media,
    },
    console: { warn() {} },
  });
  listeners.ready();
  return { document, button, label, media, listeners, saved: () => saved };
}

test("follows system appearance until a manual choice is saved", () => {
  const p = page({ dark: true });
  assert.equal(p.document.documentElement.dataset.theme, "dark");
  assert.equal(p.button["aria-checked"], "true");
  assert.equal(p.label.textContent, "Night");
  assert.equal(p.button.hidden, false);
  p.media.matches = false;
  p.listeners.system();
  assert.equal(p.document.documentElement.dataset.theme, "light");
  p.listeners.click();
  assert.equal(p.saved(), "dark");
  p.media.matches = true;
  p.listeners.system();
  p.media.matches = false;
  p.listeners.system();
  assert.equal(p.document.documentElement.dataset.theme, "dark");
  assert.equal(page({ saved: p.saved() }).document.documentElement.dataset.theme, "dark");
});

test("still switches themes when browser storage is unavailable", () => {
  const p = page({ storageFails: true });
  p.listeners.click();
  assert.equal(p.document.documentElement.dataset.theme, "dark");
  assert.equal(p.button["aria-checked"], "true");
  assert.equal(p.label.textContent, "Night");
});

test("reduced motion switches immediately without animating", () => {
  const p = page({ reducedMotion: true });
  p.button.animate = () => { throw Error("animation should not run"); };
  p.listeners.click();
  assert.equal(p.document.documentElement.dataset.theme, "dark");
  assert.equal(p.button["aria-checked"], "true");
});

test("mobile fades the theme without the SVG wave, in both directions", async () => {
  for (const saved of ["light", "dark"]) {
    const listeners = {};
    const animations = [];
    const label = {};
    const button = {
      animate() {}, querySelector: () => label, setAttribute() {},
      addEventListener(name, callback) { listeners[name] = callback; },
    };
    const overlay = {
      style: {}, setAttribute() {}, remove() { this.removed = true; },
      animate(frames, options) {
        let resolve;
        const finished = new Promise((done) => { resolve = done; });
        animations.push({ frames, options, resolve });
        return { finished };
      },
    };
    const document = {
      documentElement: { dataset: {} }, body: { appendChild() {} },
      querySelector: () => button,
      addEventListener(name, callback) { listeners[name] = callback; },
      createElement: () => overlay,
      createElementNS() { throw Error("mobile should not create an SVG wave"); },
      startViewTransition() { throw Error("mobile should not use a view transition"); },
    };
    runInNewContext(source, {
      document, localStorage: { getItem: () => saved, setItem() {} },
      getComputedStyle: () => ({ getPropertyValue: () => "#fff" }),
      window: { matchMedia: (query) => ({
        matches: query === "(max-width: 750px)", addEventListener() {},
      }) },
      console,
    });
    listeners.DOMContentLoaded();
    listeners.click();
    assert.equal(button.disabled, true);
    assert.equal(document.documentElement.dataset.theme, saved);
    assert.equal(overlay.className, "theme-fade-overlay");
    assert.equal(overlay.style.background, "#fff");
    assert.equal(animations[0].frames[0].opacity, 0);
    assert.equal(animations[0].frames[1].opacity, 1);
    animations[0].resolve();
    await Promise.resolve();
    assert.equal(document.documentElement.dataset.theme, saved === "light" ? "dark" : "light");
    assert.equal(animations[1].frames[0].opacity, 1);
    assert.equal(animations[1].frames[1].opacity, 0);
    animations[1].resolve();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(button.disabled, false);
    assert.equal(overlay.removed, true);
  }
});

test("view transition uses one softened wave", async () => {
  const listeners = {};
  const animations = [];
  let finish;
  const finished = new Promise((resolve) => { finish = resolve; });
  const label = {};
  const button = {
    hidden: true,
    animate() {},
    querySelector: () => label,
    setAttribute(name, value) { this[name] = value; },
    addEventListener(name, callback) { listeners[name] = callback; },
  };
  function element() {
    return {
      style: {}, attrs: {}, classList: { add() {} },
      setAttribute(name, value) { this.attrs[name] = value; }, appendChild() {},
      remove() {},
      animate(frames, options) { animations.push({ frames, options, attrs: this.attrs }); },
    };
  }
  const document = {
    documentElement: { dataset: {}, classList: { add() {}, remove() {} } },
    body: { appendChild() {} },
    querySelector: () => button,
    addEventListener(name, callback) { listeners.ready = callback; },
    createElementNS: element,
    startViewTransition(callback) {
      callback();
      return { ready: Promise.resolve(), finished };
    },
  };
  runInNewContext(source, {
    document,
    localStorage: { getItem: () => null, setItem() {} },
    window: {
      innerWidth: 108, innerHeight: 72,
      matchMedia: () => ({ matches: false, addEventListener() {} }),
    },
    console,
  });
  listeners.ready();
  assert.equal(animations.length, 0);
  listeners.click();
  await Promise.resolve();
  assert.equal(animations.length, 1);
  assert.match(animations[0].attrs.d, / Q /);
  assert.equal(animations[0].attrs.filter, "url(#theme-wave-soften)");
  assert.equal(animations[0].frames[0].transform, "translateX(-65px)");
  assert.equal(animations[0].frames[1].transform, "translateX(128px)");
  assert.equal(document.documentElement.dataset.theme, "dark");
  finish();
  await finished;
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(button.disabled, false);
});

test("fallback covers, switches, then uncovers the theme in either direction", async () => {
  for (const saved of ["light", "dark"]) {
    const listeners = {};
    const animations = [];
    const elements = [];
    const label = {};
    const button = {
      animate() {}, querySelector: () => label, setAttribute() {},
      addEventListener(name, callback) { listeners[name] = callback; },
    };
    function element() {
      const el = {
        style: {}, attrs: {}, children: [], classList: { add(name) { el.className = name; } },
        setAttribute(name, value) { this.attrs[name] = value; },
        appendChild(child) { this.children.push(child); },
        remove() { this.removed = true; },
        animate(frames) {
          let resolve;
          const finished = new Promise((done) => { resolve = done; });
          animations.push({ frames, resolve });
          return { finished };
        },
      };
      elements.push(el);
      return el;
    }
    const document = {
      documentElement: { dataset: {} }, body: { appendChild() {} },
      querySelector: () => button,
      addEventListener(name, callback) { listeners.ready = callback; },
      createElementNS: element,
    };
    runInNewContext(source, {
      document, localStorage: { getItem: () => saved, setItem() {} },
      getComputedStyle: () => ({ getPropertyValue: () => "#123456" }),
      window: { innerWidth: 108, innerHeight: 72,
        matchMedia: () => ({ matches: false, addEventListener() {} }) },
      console,
    });
    listeners.ready();
    listeners.click();
    assert.equal(button.disabled, true);
    assert.equal(document.documentElement.dataset.theme, saved);
    assert.equal(animations.length, 1);
    animations[0].resolve();
    await Promise.resolve();
    assert.equal(document.documentElement.dataset.theme, saved === "light" ? "dark" : "light");
    assert.equal(animations.length, 2);
    assert.equal(animations[1].frames[0].transform, animations[0].frames[1].transform);
    assert.equal(animations[1].frames[1].transform, animations[0].frames[0].transform);
    animations[1].resolve();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(button.disabled, false);
    assert.equal(elements.find((el) => el.className === "theme-wave-overlay").removed, true);
  }
});

test("each documentation page includes the theme script and control", async () => {
  for (const name of ["index", "getting-started", "showcases", "timecourse", "methods", "checklist", "community"]) {
    const html = await readFile(new URL(`../docs/${name}.html`, import.meta.url), "utf8");
    assert.match(html, /<script src="theme\.js"><\/script>\s*<link rel="stylesheet"/);
    assert.match(html, /<button class="theme-toggle" type="button" role="switch" aria-label="Night mode" aria-checked="false" hidden>/);
  }
});
