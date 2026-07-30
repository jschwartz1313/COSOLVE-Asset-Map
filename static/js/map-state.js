const MAP_LAYER_STATE_VERSION = "3";
const MAP_STATE_KEYS = [
  "map_lat",
  "map_lon",
  "map_zoom",
  "map_layers",
  "map_layers_v",
  "map_basemap",
];
export const MAP_LAYER_ORDER = [
  "assets",
  "state",
  "regions",
  "mpz",
  "counties",
  "verification",
  "precision",
  "relationships",
];
export const MAP_BASEMAPS = ["street", "light", "imagery"];

function validNumber(value, minimum, maximum) {
  const number = Number(value);
  return Number.isFinite(number) && number >= minimum && number <= maximum
    ? number
    : null;
}

export function filterParamsFromMapUrl(params) {
  const filters = new URLSearchParams(params);
  for (const key of MAP_STATE_KEYS) filters.delete(key);
  return filters;
}

export function mapStateFromParams(params) {
  const hasCenter = ["map_lat", "map_lon", "map_zoom"].every((key) => params.has(key));
  const hasLayers = params.has("map_layers");
  const hasBasemap = params.has("map_basemap");
  if (!hasCenter && !hasLayers && !hasBasemap) return null;

  const latitude = hasCenter ? validNumber(params.get("map_lat"), -90, 90) : null;
  const longitude = hasCenter ? validNumber(params.get("map_lon"), -180, 180) : null;
  const zoom = hasCenter ? validNumber(params.get("map_zoom"), 1, 19) : null;
  let layers = hasLayers
    ? params
        .get("map_layers")
        .split(",")
        .filter((layer) => MAP_LAYER_ORDER.includes(layer))
    : null;
  const layerVersion = Number(params.get("map_layers_v") || "1");
  if (layers && layerVersion < 2 && !layers.includes("assets")) {
    layers = ["assets", ...layers];
  }
  const requestedBasemap = params.get("map_basemap");
  const basemap = MAP_BASEMAPS.includes(requestedBasemap) ? requestedBasemap : "street";

  return {
    latitude,
    longitude,
    zoom,
    layers,
    basemap,
    hasValidCenter: latitude !== null && longitude !== null && zoom !== null,
  };
}

export function paramsWithMapState(filters, state) {
  const params = filterParamsFromMapUrl(filters);
  params.set("map_lat", Number(state.latitude).toFixed(5));
  params.set("map_lon", Number(state.longitude).toFixed(5));
  params.set("map_zoom", String(Math.round(Number(state.zoom))));
  params.set(
    "map_layers",
    MAP_LAYER_ORDER.filter((layer) => state.layers.includes(layer)).join(","),
  );
  params.set("map_layers_v", MAP_LAYER_STATE_VERSION);
  params.set(
    "map_basemap",
    MAP_BASEMAPS.includes(state.basemap) ? state.basemap : "street",
  );
  return params;
}
