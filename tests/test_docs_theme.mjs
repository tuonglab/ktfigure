import { readFile } from "node:fs/promises";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import assert from "node:assert/strict";

const source = await readFile(new URL("../docs/theme.js", import.meta.url), "utf8");

function page({ saved = null, dark = false, storageFails = false } = {}) {
  const listeners = {};
  const button = {
    hidden: true,
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
    document, localStorage, window: { matchMedia: () => media },
    console: { warn() {} },
  });
  listeners.ready();
  return { document, button, media, listeners, saved: () => saved };
}

test("follows system appearance until a manual choice is saved", () => {
  const p = page({ dark: true });
  assert.equal(p.document.documentElement.dataset.theme, "dark");
  assert.equal(p.button["aria-label"], "Switch to day mode");
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
  assert.equal(p.button.textContent, "Day mode");
});

test("each documentation page includes the theme script and control", async () => {
  for (const name of ["index", "getting-started", "showcases", "timecourse", "methods", "checklist", "community"]) {
    const html = await readFile(new URL(`../docs/${name}.html`, import.meta.url), "utf8");
    assert.match(html, /<script src="theme\.js"><\/script>\s*<link rel="stylesheet"/);
    assert.match(html, /<button class="theme-toggle" type="button" hidden>/);
  }
});
