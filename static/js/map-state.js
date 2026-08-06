const MAP_LAYER_STATE_VERSION = "4";
const MAP_STATE_KEYS = [
  "map_lat",
  "map_lon",
  "map_zoom",
  "map_layers",
  "map_layers_v",
  "map_basemap",
  "map_analysis",
];
export const MAP_LAYER_ORDER = [
  "assets",
  "state",
  "regions",
  "mpz",
  "counties",
  "heliports",
  "verification",
  "precision",
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

function coordinatePair(value) {
  const [latitudeValue, longitudeValue, extra] = value.split(",");
  if (extra !== undefined) return null;
  const lat = validNumber(latitudeValue, -90, 90);
  const lng = validNumber(longitudeValue, -180, 180);
  return lat === null || lng === null ? null : { lat, lng };
}

export function analysisStateFromParams(params) {
  const raw = params.get("map_analysis");
  if (!raw) return null;
  const separator = raw.indexOf("|");
  if (separator === -1) return null;
  const type = raw.slice(0, separator);
  const payload = raw.slice(separator + 1);
  if (type === "rectangle") {
    const values = payload.split(",").map(Number);
    if (
      values.length !== 4 ||
      values.some((value) => !Number.isFinite(value)) ||
      values[0] < -90 ||
      values[2] > 90 ||
      values[1] < -180 ||
      values[3] > 180 ||
      values[0] > values[2] ||
      values[1] > values[3]
    ) {
      return null;
    }
    return {
      type,
      bounds: {
        south: values[0],
        west: values[1],
        north: values[2],
        east: values[3],
      },
    };
  }
  if (type === "polygon") {
    const vertices = payload.split(";").map(coordinatePair);
    if (vertices.length < 3 || vertices.some((vertex) => vertex === null)) return null;
    return { type, vertices };
  }
  return null;
}

export function serializeRectangleAnalysis(bounds) {
  return `rectangle|${[
    bounds.south,
    bounds.west,
    bounds.north,
    bounds.east,
  ]
    .map((value) => Number(value).toFixed(5))
    .join(",")}`;
}

export function serializePolygonAnalysis(vertices) {
  return `polygon|${vertices
    .map((vertex) => `${Number(vertex.lat).toFixed(5)},${Number(vertex.lng).toFixed(5)}`)
    .join(";")}`;
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
  if (state.analysis) params.set("map_analysis", state.analysis);
  return params;
}
