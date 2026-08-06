import assert from "node:assert/strict";
import test from "node:test";

import {
  analysisStateFromParams,
  filterParamsFromMapUrl,
  mapStateFromParams,
  paramsWithMapState,
  serializePolygonAnalysis,
  serializeRectangleAnalysis,
} from "../../static/js/map-state.js";
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

test("saved map state preserves filters, center, zoom, and layers", () => {
  const params = paramsWithMapState(
    new URLSearchParams("region=hampton-roads&record_type=university"),
    {
      latitude: 36.912345,
      longitude: -76.301234,
      zoom: 11,
      layers: ["assets", "state", "mpz", "counties", "heliports"],
      basemap: "light",
    },
  );
  const state = mapStateFromParams(params);

  assert.equal(
    filterParamsFromMapUrl(params).toString(),
    "region=hampton-roads&record_type=university",
  );
  assert.deepEqual(state, {
    latitude: 36.91235,
    longitude: -76.30123,
    zoom: 11,
    layers: ["assets", "state", "mpz", "counties", "heliports"],
    basemap: "light",
    hasValidCenter: true,
  });
  assert.equal(params.get("map_layers_v"), "4");
});

test("legacy saved map layers retain asset points", () => {
  const state = mapStateFromParams(
    new URLSearchParams("map_layers=regions,unknown"),
  );
  assert.deepEqual(state.layers, ["assets", "regions"]);
  assert.equal(state.basemap, "street");
});

test("invalid saved map coordinates are ignored safely", () => {
  const state = mapStateFromParams(
    new URLSearchParams(
      "map_lat=200&map_lon=-76&map_zoom=8&map_layers=regions&map_layers_v=2",
    ),
  );
  assert.equal(state.hasValidCenter, false);
  assert.deepEqual(state.layers, ["regions"]);
  assert.equal(state.basemap, "street");
});

test("versioned saved map state can hide asset points", () => {
  const state = mapStateFromParams(
    new URLSearchParams("map_layers=state&map_layers_v=2"),
  );
  assert.deepEqual(state.layers, ["state"]);
});

test("saved map state restores imagery and analytical layers", () => {
  const state = mapStateFromParams(
    new URLSearchParams(
      "map_layers=assets,verification,precision,relationships&map_layers_v=3&map_basemap=imagery",
    ),
  );
  assert.deepEqual(state.layers, [
    "assets",
    "verification",
    "precision",
  ]);
  assert.equal(state.basemap, "imagery");
});

test("saved map state preserves and restores rectangle analysis geometry", () => {
  const serialized = serializeRectangleAnalysis({
    south: 36.7,
    west: -76.5,
    north: 37.1,
    east: -76.1,
  });
  const params = paramsWithMapState(new URLSearchParams("region=hampton-roads"), {
    latitude: 36.9,
    longitude: -76.3,
    zoom: 9,
    layers: ["assets", "state"],
    basemap: "street",
    analysis: serialized,
  });

  assert.deepEqual(analysisStateFromParams(params), {
    type: "rectangle",
    bounds: { south: 36.7, west: -76.5, north: 37.1, east: -76.1 },
  });
  assert.equal(filterParamsFromMapUrl(params).toString(), "region=hampton-roads");
});

test("saved polygon geometry validates coordinates and rejects malformed state", () => {
  const serialized = serializePolygonAnalysis([
    { lat: 36.8, lng: -76.4 },
    { lat: 36.8, lng: -76.2 },
    { lat: 37, lng: -76.3 },
  ]);
  assert.deepEqual(
    analysisStateFromParams(new URLSearchParams({ map_analysis: serialized })),
    {
      type: "polygon",
      vertices: [
        { lat: 36.8, lng: -76.4 },
        { lat: 36.8, lng: -76.2 },
        { lat: 37, lng: -76.3 },
      ],
    },
  );
  assert.equal(
    analysisStateFromParams(
      new URLSearchParams({ map_analysis: "polygon|36.8,-76.4;invalid" }),
    ),
    null,
  );
});
