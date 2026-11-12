import assert from "node:assert/strict";
import test from "node:test";
import { assetPickerPage, assetPickerQuery } from "../../static/js/asset-picker-state.js";

const asset = { slug: "example", name: "Example asset", url: "/assets/example/",
  record_type: "facility", record_type_label: "Facility", location: "Hampton, VA" };

test("picker responses allow empty results and bounded paginated records", () => {
  const empty = { assets: [], count: 0, page: 1, pages: 1 };
  assert.deepEqual(assetPickerPage(empty), empty);
  const response = { assets: [asset], count: 25, page: 2, pages: 2 };
  assert.deepEqual(assetPickerPage(response), response);
  for (const update of [{ page: 0 }, { pages: 1 }, { count: -1 }, { page: 3 },
    { assets: Array(25).fill(asset) }, { count: "25" }]) {
    assert.throws(() => assetPickerPage({ ...response, ...update }));
  }
});

test("picker records must have safe local links and valid bounded display fields", () => {
  for (const update of [{ slug: "../secret" }, { url: "javascript:alert(1)" },
    { url: "https://example.com/assets/example/" }, { name: "" }, { name: "x".repeat(221) },
    { location: {} }, { record_type_label: null }]) {
    assert.throws(() => assetPickerPage({ assets: [{ ...asset, ...update }], count: 1,
      page: 1, pages: 1 }));
  }
  assert.throws(() => assetPickerPage({ assets: [asset, asset], count: 2, page: 1, pages: 1 }));
});

test("confirming a draft preserves existing order and the five-asset limit", () => {
  const query = assetPickerQuery(["one", "two"], ["three", "four", "five"]);
  assert.deepEqual(new URLSearchParams(query).getAll("asset"),
    ["one", "two", "three", "four", "five"]);
  assert.throws(() => assetPickerQuery(["one"], ["one"]));
  assert.throws(() => assetPickerQuery(["one", "two"], ["three", "four", "five", "six"]));
  assert.throws(() => assetPickerQuery([], ["../private"]));
});
