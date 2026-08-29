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
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, developmentPreviewMeta);
  assert.match(html, /Migration control workbench/i);
  assert.match(html, /Review unresolved cases/i);
  assert.match(html, /Release readiness/i);

  const source = await readFile(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /Official public sources/i);
  assert.match(source, /DS00979/i);
  assert.match(source, /0037797/i);
  assert.match(source, /0037800/i);
  assert.match(source, /Sources &amp; search/i);
  assert.match(source, /Search migration evidence/i);
  assert.match(source, /aria-controls="mobile-tools"/i);
  assert.match(source, /About this workbench/i);
  assert.match(source, /procurement data and QA analysts/i);
  assert.match(source, /Designed and engineered by Nicolaas/i);
  assert.match(source, /Record accountable decision/i);
  assert.match(source, /selected reviews complete/i);
  assert.match(source, /disabled={!p.canSubmit}/i);
  assert.match(source, /aria-invalid/i);
  assert.match(source, /20 minimum/i);
  assert.match(source, /Decision requirements/i);
  assert.match(source, /Find a review case/i);
  assert.match(source, /Any status/i);
  assert.match(source, /Any priority/i);
  assert.match(source, /Any owner/i);
  assert.match(source, /No review cases match/i);
  assert.match(source, /Specialist terms/i);
  assert.match(source, /The validated dataset approved for reporting/i);
  assert.match(source, /Verified this session/i);
  assert.match(source, /Every record remains accounted for/i);
  assert.match(source, /Official project context/i);
  assert.match(source, /search\.worldbank\.org\/api\/v3\/projects/i);
  assert.match(source, /readiness-ring/i);
  assert.match(source, /restcountries\.com\/v3\.1/i);
  assert.match(source, /api\.worldbank\.org\/v2\/country/i);
  assert.match(source, /api\.frankfurter\.dev/i);
  assert.match(source, /world-atlas\/countries-110m/i);
  assert.match(source, /Record coverage by country/i);
  assert.doesNotMatch(source, /Country shapes come from/i);
  assert.doesNotMatch(
    source,
    /Live country matching is temporarily unavailable/i,
  );
  assert.match(
    source,
    /country-level\s+indicators are intentionally not inferred/i,
  );
  assert.match(source, /Begin review before recording a decision/i);
  assert.match(source, /Release decision package/i);
  assert.match(source, /Search trusted records/i);
  assert.doesNotMatch(source, /Can he engineer the migration/i);
  assert.doesNotMatch(source, /Guide me through it/i);
  assert.doesNotMatch(source, /→|↗/);
});
