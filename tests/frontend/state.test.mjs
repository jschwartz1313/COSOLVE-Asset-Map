import assert from "node:assert/strict";
import test from "node:test";

test("URLSearchParams preserves repeated facet values", () => {
  const params = new URLSearchParams();
  params.append("category", "test-operational-environments");
  params.append("category", "research-technical-depth");
  params.set("region", "hampton-roads");
  assert.deepEqual(params.getAll("category"), [
    "test-operational-environments",
    "research-technical-depth",
  ]);
  assert.equal(params.get("region"), "hampton-roads");
});

test("clear-all state has no query string", () => {
  assert.equal(new URLSearchParams().toString(), "");
});

