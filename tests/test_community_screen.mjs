import test from "node:test";
import assert from "node:assert/strict";
import { screenSubmission } from "../.github/scripts/community-moderation/screen.mjs";

function fakeClient(content) {
  const record = {};
  const client = {
    async listModels() {
      return [
        { id: "text-only", capabilities: { supports: { vision: false } } },
        { id: "vision", capabilities: { supports: { vision: true } } },
      ];
    },
    async createSession(options) {
      record.options = options;
      return {
        async sendAndWait(message) {
          record.message = message;
          if (content instanceof Error) throw content;
          return { data: { content } };
        },
        async disconnect() { record.disconnected = true; },
      };
    },
  };
  return { client, record };
}

test("a clear pass screens the attached image and text without agent tools", async () => {
  const { client, record } = fakeClient('{"verdict":"pass"}');
  await screenSubmission(client, { description: "Test figure", feedback: "My feedback" }, "/tmp/42.png");
  assert.equal(record.options.model, "vision");
  assert.deepEqual(record.options.tools.availableTools, []);
  assert.equal((await record.options.permissions.onRequest()).kind, "reject");
  assert.equal(record.message.attachments[0].path, "/tmp/42.png");
  assert.match(record.message.prompt, /Test figure/);
  assert.match(record.message.prompt, /My feedback/);
  assert.equal(record.disconnected, true);
});

for (const content of ['{"verdict":"hold"}', '{"verdict":"pass","extra":true}', "not JSON", new Error("quota exhausted")]) {
  test(`holds on ${content}`, async () => {
    const { client, record } = fakeClient(content);
    await assert.rejects(screenSubmission(client, {}, "/tmp/42.png"));
    assert.equal(record.disconnected, true);
  });
}

test("holds when no vision model is available", async () => {
  const client = { listModels: async () => [{ capabilities: { supports: { vision: false } } }] };
  await assert.rejects(screenSubmission(client, {}, "/tmp/42.png"), /vision-capable/);
});
