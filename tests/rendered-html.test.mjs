import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const developmentPreviewMeta =
  /<meta(?=[^>]*\bname=["']codex-preview["'])(?=[^>]*\bcontent=["']development["'])[^>]*>/i;

test("renders development preview metadata", async () => {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  const response = await worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );

  assert.equal(response.status, 200);
  assert.match(
    response.headers.get("content-type") ?? "",
    /^text\/html\b/i,
  );
  const html = await response.text();
  assert.match(html, developmentPreviewMeta);
  assert.match(html, /Migration control workbench/i);
  assert.match(html, /Review unresolved cases/i);
  assert.match(html, /Release readiness/i);

  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(source, /Official public sources/i);
  assert.match(source, /DS00979/i);
  assert.match(source, /0037797/i);
  assert.match(source, /0037800/i);
  assert.match(source, /Record accountable decision/i);
  assert.match(source, /Release decision package/i);
  assert.match(source, /Search trusted records/i);
  assert.doesNotMatch(source, /Can he engineer the migration/i);
  assert.doesNotMatch(source, /Guide me through it/i);
  assert.doesNotMatch(source, /→|↗/);
});
