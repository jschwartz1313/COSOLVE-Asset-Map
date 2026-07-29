const MAP_STATE_KEYS = ["map_lat", "map_lon", "map_zoom", "map_layers"];
export const MAP_LAYER_ORDER = ["state", "regions", "mpz", "counties"];

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
  if (!hasCenter && !hasLayers) return null;

  const latitude = hasCenter ? validNumber(params.get("map_lat"), -90, 90) : null;
  const longitude = hasCenter ? validNumber(params.get("map_lon"), -180, 180) : null;
  const zoom = hasCenter ? validNumber(params.get("map_zoom"), 1, 19) : null;
  const layers = hasLayers
    ? params
        .get("map_layers")
        .split(",")
        .filter((layer) => MAP_LAYER_ORDER.includes(layer))
    : null;

  return {
    latitude,
    longitude,
    zoom,
    layers,
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
  return params;
}
