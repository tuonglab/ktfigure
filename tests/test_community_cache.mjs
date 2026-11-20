import { readFile } from "node:fs/promises";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import assert from "node:assert/strict";

test("gallery requests a fresh index after a post is removed", async () => {
  const source = await readFile(new URL("../docs/community.js", import.meta.url), "utf8");
  const gallery = { replaceChildren() {} };
  const status = {};
  let request;
  const context = {
    document: { getElementById: (id) => id === "community-entries" ? gallery : status },
    fetch: async (url, options) => {
      request = { url, cache: options.cache };
      return { ok: true, json: async () => [] };
    },
    console,
  };
  await runInNewContext(source.replace("loadGallery();", "loadGallery()"), context);
  assert.equal(request.url, "community/entries.json");
  assert.equal(request.cache, "no-store");
  assert.match(status.textContent, /No community posts yet/);
});
