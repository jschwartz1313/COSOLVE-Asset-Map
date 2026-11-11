import assert from "node:assert/strict";
import test from "node:test";
import { comparisonLabels, comparisonSlugs } from "../../static/js/asset-comparison-state.js";

test("existing comparison selections retain order, deduplicate and stay bounded", () => {
  assert.deepEqual(comparisonSlugs(["one", "one", "two", "three", "four", "five", "six"]),
    ["one", "two", "three", "four", "five"]);
  for (const value of [null, {}, "one", 10]) assert.deepEqual(comparisonSlugs(value), []);
  assert.deepEqual(comparisonSlugs(["one", {}, "../private", "<script>", "x".repeat(241)]), ["one"]);
});

test("name resolution accepts only requested names and local asset links", () => {
  const label = { slug: "one", name: "A real asset", url: "/assets/one/" };
  assert.deepEqual([...comparisonLabels({ assets: [label] }, ["one"])],
    [["one", { name: label.name, url: label.url }]]);
  for (const changes of [
    { slug: "private" }, { name: "" }, { name: "x".repeat(221) },
    { url: "javascript:alert(1)" }, { url: "https://elsewhere.example/assets/one/" },
  ]) assert.throws(() => comparisonLabels({ assets: [{ ...label, ...changes }] }, ["one"]));
});

test("incomplete responses represent unavailable records but malformed responses are errors", () => {
  assert.equal(comparisonLabels({ assets: [] }, ["one"]).size, 0);
  for (const payload of [null, {}, { assets: "one" }, { assets: Array(6).fill({}) }]) {
    assert.throws(() => comparisonLabels(payload, ["one"]));
  }
  const asset = { slug: "one", name: "One", url: "/assets/one/" };
  assert.throws(() => comparisonLabels({ assets: [asset, asset] }, ["one"]));
});
