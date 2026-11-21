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

test("manual switch reveals tiles left to right with the top ahead", async () => {
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
      style: {}, classList: { add() {} }, setAttribute() {}, appendChild() {},
      remove() {},
      animate(frames, options) { animations.push({ frames, options }); },
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
  assert.equal(animations.length, 6);
  assert.ok(animations[2].options.delay > animations[0].options.delay);
  assert.ok(animations[3].options.delay > animations[0].options.delay);
  assert.equal(document.documentElement.dataset.theme, "dark");
  finish();
  await finished;
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(button.disabled, false);
});

test("each documentation page includes the theme script and control", async () => {
  for (const name of ["index", "getting-started", "showcases", "timecourse", "methods", "checklist", "community"]) {
    const html = await readFile(new URL(`../docs/${name}.html`, import.meta.url), "utf8");
    assert.match(html, /<script src="theme\.js"><\/script>\s*<link rel="stylesheet"/);
    assert.match(html, /<button class="theme-toggle" type="button" role="switch" aria-label="Night mode" aria-checked="false" hidden>/);
  }
});
