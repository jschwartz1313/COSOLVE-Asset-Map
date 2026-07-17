import assert from "node:assert/strict";
import test from "node:test";

import { hydrateForm, paramsFromEntries } from "../../static/js/state.js";

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

test("empty form entries produce no active filters", () => {
  const params = paramsFromEntries([
    ["q", ""],
    ["record_type", ""],
    ["region", "  "],
  ]);
  assert.equal(params.toString(), "");
});

test("form entries preserve supported repeated filters and ignore unrelated fields", () => {
  const params = paramsFromEntries([
    ["category", "research-technical-depth"],
    ["category", "workforce-talent"],
    ["page", "4"],
    ["q", "  autonomy  "],
  ]);
  assert.equal(
    params.toString(),
    "q=autonomy&category=research-technical-depth&category=workforce-talent",
  );
});

test("hydrateForm restores text, select, and checkbox state", () => {
  const elements = [
    { name: "q", type: "search", value: "old" },
    { name: "region", type: "select-one", value: "" },
    { name: "category", type: "checkbox", value: "research", checked: false },
    { name: "category", type: "checkbox", value: "workforce", checked: true },
  ];
  hydrateForm(
    { elements },
    new URLSearchParams("q=autonomy&region=hampton-roads&category=research"),
  );
  assert.equal(elements[0].value, "autonomy");
  assert.equal(elements[1].value, "hampton-roads");
  assert.equal(elements[2].checked, true);
  assert.equal(elements[3].checked, false);
});
