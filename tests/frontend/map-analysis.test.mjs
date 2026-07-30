import assert from "node:assert/strict";
import test from "node:test";

import {
  distanceMiles,
  featureCsv,
  featuresWithinBounds,
  featuresWithinPolygon,
  featuresWithinRadius,
  summarizeRegion,
} from "../../static/js/map-analysis.js";

function feature(id, lat, lng, overrides = {}) {
  return {
    id,
    geometry: lat === null ? null : { type: "Point", coordinates: [lng, lat] },
    properties: {
      name: `Asset ${id}`,
      record_type_label: "Organization",
      verification_state: "source-backed",
      verification_state_label: "Source-backed; review pending",
      location: {
        address_line: "",
        city: "Norfolk",
        precision: "approximate",
        precision_label: "Approximate",
        region: "Hampton Roads",
        region_slug: "hampton-roads",
      },
      capabilities: [],
      detail_url: `/assets/${id}/`,
      ...overrides,
    },
  };
}

test("distance and radius filtering use real geographic distance", () => {
  const norfolk = { lat: 36.8508, lng: -76.2859 };
  const virginiaBeach = { lat: 36.8529, lng: -75.978 };
  assert.ok(distanceMiles(norfolk, virginiaBeach) > 15);
  assert.ok(distanceMiles(norfolk, virginiaBeach) < 20);
  const features = [
    feature("near", 36.86, -76.29),
    feature("far", 38.9, -77.04),
  ];
  assert.deepEqual(
    featuresWithinRadius(features, norfolk, 25).map((item) => item.id),
    ["near"],
  );
});

test("bounds filtering excludes unmapped and out-of-area records", () => {
  const features = [
    feature("inside", 36.86, -76.29),
    feature("outside", 38.9, -77.04),
    feature("unmapped", null, null),
  ];
  assert.deepEqual(
    featuresWithinBounds(features, {
      south: 36.7,
      west: -76.5,
      north: 37,
      east: -76,
    }).map((item) => item.id),
    ["inside"],
  );
});

test("polygon filtering includes interior and boundary points", () => {
  const features = [
    feature("inside", 36.85, -76.25),
    feature("boundary", 36.8, -76.2),
    feature("outside", 37.1, -76.25),
    feature("unmapped", null, null),
  ];
  const vertices = [
    { lat: 36.8, lng: -76.4 },
    { lat: 36.8, lng: -76.2 },
    { lat: 37, lng: -76.3 },
  ];

  assert.deepEqual(
    featuresWithinPolygon(features, vertices).map((item) => item.id),
    ["inside", "boundary"],
  );
  assert.deepEqual(featuresWithinPolygon(features, vertices.slice(0, 2)), []);
});

test("regional summaries report mix, precision, review, and capabilities", () => {
  const features = [
    feature("one", 36.86, -76.29, {
      verification_state: "reviewed",
      record_type_label: "University",
      location: {
        address_line: "",
        city: "Norfolk",
        precision: "site",
        precision_label: "Site or campus",
        region: "Hampton Roads",
        region_slug: "hampton-roads",
      },
      capabilities: [{ name: "Autonomy and AI", slug: "autonomy-ai" }],
    }),
    feature("two", 36.87, -76.3, {
      capabilities: [{ name: "Autonomy and AI", slug: "autonomy-ai" }],
    }),
  ];
  const summary = summarizeRegion(features, "hampton-roads");
  assert.equal(summary.total, 2);
  assert.equal(summary.reviewed, 1);
  assert.equal(summary.siteLevel, 1);
  assert.deepEqual(summary.capabilities[0], ["Autonomy and AI", 2]);
});

test("CSV export preserves names and public map metadata", () => {
  const csv = featureCsv([feature("quoted", 36.86, -76.29, { name: 'Asset "One"' })]);
  assert.match(csv, /name,asset_type,address/);
  assert.match(csv, /"Asset ""One"""/);
  assert.match(csv, /Source-backed; review pending/);
});
