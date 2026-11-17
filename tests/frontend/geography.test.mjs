import assert from "node:assert/strict";
import test from "node:test";
import { comparisonLabels } from "../../static/js/asset-comparison-state.js";
import { assetPickerPage } from "../../static/js/asset-picker-state.js";
import { inventoryPrefix, sitePath } from "../../static/js/geography.js";

test("geographic links keep a validated state prefix without changing Virginia paths", () => {
  assert.equal(inventoryPrefix(), "");
  assert.equal(sitePath("/map/"), "/map/");
  globalThis.document = { body: { dataset: { sitePrefix: "/states/north-dakota" } } };
  assert.equal(sitePath("/api/assets.geojson"), "/states/north-dakota/api/assets.geojson");
  document.body.dataset.sitePrefix = "https://evil.test";
  assert.equal(inventoryPrefix(), "");
  delete globalThis.document;
});

test("comparison and picker responses cannot cross the selected state", () => {
  const prefix = "/states/ohio";
  const asset = { slug: "oh-test", name: "Ohio test site", url: prefix + "/assets/oh-test/",
    record_type: "facility", record_type_label: "Facility", location: "Columbus, OH" };
  assert.equal(comparisonLabels({ assets: [asset] }, [asset.slug], prefix).size, 1);
  assert.throws(() => comparisonLabels({ assets: [asset] }, [asset.slug]));
  const page = { assets: [asset], count: 1, page: 1, pages: 1 };
  assert.equal(assetPickerPage(page, prefix), page);
  assert.throws(() => assetPickerPage(page, "/states/texas"));
});
