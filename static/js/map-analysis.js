const EARTH_RADIUS_MILES = 3958.7613;

function radians(value) {
  return (Number(value) * Math.PI) / 180;
}

export function distanceMiles(first, second) {
  const latitudeDelta = radians(second.lat - first.lat);
  const longitudeDelta = radians(second.lng - first.lng);
  const firstLatitude = radians(first.lat);
  const secondLatitude = radians(second.lat);
  const value =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(firstLatitude) *
      Math.cos(secondLatitude) *
      Math.sin(longitudeDelta / 2) ** 2;
  return 2 * EARTH_RADIUS_MILES * Math.asin(Math.sqrt(value));
}

function featureCoordinates(feature) {
  if (!feature.geometry) return null;
  const [lng, lat] = feature.geometry.coordinates;
  return { lat, lng };
}

export function featuresWithinRadius(features, center, radiusMiles) {
  return features.filter((feature) => {
    const coordinates = featureCoordinates(feature);
    return coordinates && distanceMiles(center, coordinates) <= radiusMiles;
  });
}

export function featuresWithinBounds(features, bounds) {
  return features.filter((feature) => {
    const coordinates = featureCoordinates(feature);
    return (
      coordinates &&
      coordinates.lat >= bounds.south &&
      coordinates.lat <= bounds.north &&
      coordinates.lng >= bounds.west &&
      coordinates.lng <= bounds.east
    );
  });
}

function pointOnSegment(point, start, end) {
  const crossProduct =
    (point.lng - start.lng) * (end.lat - start.lat) -
    (point.lat - start.lat) * (end.lng - start.lng);
  if (Math.abs(crossProduct) > 1e-10) return false;
  const dotProduct =
    (point.lng - start.lng) * (end.lng - start.lng) +
    (point.lat - start.lat) * (end.lat - start.lat);
  if (dotProduct < 0) return false;
  const squaredLength =
    (end.lng - start.lng) ** 2 + (end.lat - start.lat) ** 2;
  return dotProduct <= squaredLength;
}

function pointWithinPolygon(point, vertices) {
  let inside = false;
  for (
    let index = 0, previous = vertices.length - 1;
    index < vertices.length;
    previous = index++
  ) {
    const start = vertices[previous];
    const end = vertices[index];
    if (pointOnSegment(point, start, end)) return true;
    const crossesLatitude = start.lat > point.lat !== end.lat > point.lat;
    if (crossesLatitude) {
      const intersectionLongitude =
        ((end.lng - start.lng) * (point.lat - start.lat)) /
          (end.lat - start.lat) +
        start.lng;
      if (point.lng < intersectionLongitude) inside = !inside;
    }
  }
  return inside;
}

export function featuresWithinPolygon(features, vertices) {
  if (vertices.length < 3) return [];
  return features.filter((feature) => {
    const coordinates = featureCoordinates(feature);
    return coordinates && pointWithinPolygon(coordinates, vertices);
  });
}

export function summarizeRegion(features, regionSlug) {
  const regional = features.filter(
    (feature) => feature.properties.location.region_slug === regionSlug,
  );
  const typeCounts = new Map();
  const capabilityCounts = new Map();
  let reviewed = 0;
  let siteLevel = 0;
  for (const feature of regional) {
    const properties = feature.properties;
    const type = properties.record_type_label;
    typeCounts.set(type, (typeCounts.get(type) || 0) + 1);
    for (const capability of properties.capabilities || []) {
      capabilityCounts.set(
        capability.name,
        (capabilityCounts.get(capability.name) || 0) + 1,
      );
    }
    if (properties.verification_state === "reviewed") reviewed += 1;
    if (["exact", "site"].includes(properties.location.precision)) siteLevel += 1;
  }
  const descending = (entries) =>
    [...entries].sort((first, second) => second[1] - first[1] || first[0].localeCompare(second[0]));
  return {
    total: regional.length,
    reviewed,
    siteLevel,
    types: descending(typeCounts.entries()),
    capabilities: descending(capabilityCounts.entries()).slice(0, 5),
  };
}

function csvValue(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function featureCsv(features) {
  const columns = [
    ["name", (feature) => feature.properties.name],
    ["asset_type", (feature) => feature.properties.record_type_label],
    ["address", (feature) => feature.properties.location.address_line],
    ["city", (feature) => feature.properties.location.city],
    ["region", (feature) => feature.properties.location.region],
    ["location_precision", (feature) => feature.properties.location.precision_label],
    ["verification", (feature) => feature.properties.verification_state_label],
    ["latitude", (feature) => feature.geometry?.coordinates[1] ?? ""],
    ["longitude", (feature) => feature.geometry?.coordinates[0] ?? ""],
    ["detail_url", (feature) => feature.properties.detail_url],
  ];
  const rows = [columns.map(([heading]) => heading)];
  for (const feature of features) {
    rows.push(columns.map(([, getter]) => getter(feature)));
  }
  return rows.map((row) => row.map(csvValue).join(",")).join("\n");
}

export function downloadFeatureCsv(features, filename) {
  const blob = new Blob([featureCsv(features)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
