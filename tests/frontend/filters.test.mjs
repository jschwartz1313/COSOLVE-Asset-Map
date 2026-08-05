import assert from "node:assert/strict";
import test from "node:test";

import { withoutFilterValue } from "../../static/js/filters.js";

test("removing one active filter preserves other facets and repeated values", () => {
  const params = new URLSearchParams();
  params.append("category", "research-technical-depth");
  params.append("category", "workforce-talent");
  params.set("region", "hampton-roads");

  const next = withoutFilterValue(
    params,
    "category",
    "research-technical-depth",
  );

  assert.deepEqual(next.getAll("category"), ["workforce-talent"]);
  assert.equal(next.get("region"), "hampton-roads");
});
