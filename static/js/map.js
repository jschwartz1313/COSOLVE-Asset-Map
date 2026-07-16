import { buildPopup } from "./popups.js";

const COLORS = {
  organization: "#2f6f9f",
  facility: "#147d78",
  program: "#b48216",
  infrastructure: "#c63f2b",
  "operating-environment": "#6b5d95",
};

export function createMap(root) {
  const map = window.L.map("map", { zoomControl: false }).setView(
    [Number(root.dataset.lat), Number(root.dataset.lon)],
    Number(root.dataset.zoom),
  );
  window.L.control.zoom({ position: "bottomright" }).addTo(map);
  window.L.tileLayer(root.dataset.tileUrl, {
    attribution: root.dataset.attribution,
    maxZoom: 19,
  }).addTo(map);
  const layer = window.L.markerClusterGroup
    ? window.L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 48 })
    : window.L.layerGroup();
  layer.addTo(map);
  const markers = new Map();

  function draw(features, onSelect) {
    layer.clearLayers();
    markers.clear();
    const bounds = [];
    for (const feature of features) {
      if (!feature.geometry) continue;
      const [longitude, latitude] = feature.geometry.coordinates;
      const marker = window.L.circleMarker([latitude, longitude], {
        radius: 8,
        color: "#ffffff",
        weight: 3,
        fillColor: COLORS[feature.properties.record_type] || "#5c686f",
        fillOpacity: 1,
        className: "asset-marker",
      });
      marker.bindPopup(buildPopup(feature));
      marker.on("click", () => onSelect(feature.id));
      layer.addLayer(marker);
      markers.set(feature.id, marker);
      bounds.push([latitude, longitude]);
    }
    if (bounds.length > 1) map.fitBounds(bounds, { padding: [35, 35], maxZoom: 11 });
    else if (bounds.length === 1) map.setView(bounds[0], 10);
  }

  function select(id) {
    const marker = markers.get(id);
    if (!marker) return;
    if (layer.zoomToShowLayer) layer.zoomToShowLayer(marker, () => marker.openPopup());
    else marker.openPopup();
  }

  return { map, draw, select };
}

