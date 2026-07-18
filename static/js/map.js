import { buildPopup } from "./popups.js?v=20260717";

const COLORS = {
  organization: "#2f6f9f",
  facility: "#147d78",
  program: "#b48216",
  infrastructure: "#c63f2b",
  "operating-environment": "#6b5d95",
};

export function createMap(root) {
  const defaultView = [Number(root.dataset.lat), Number(root.dataset.lon)];
  const defaultZoom = Number(root.dataset.zoom);
  const map = window.L.map("map", { zoomControl: false }).setView(
    defaultView,
    defaultZoom,
  );
  window.L.control.zoom({ position: "bottomright" }).addTo(map);
  window.L.tileLayer(root.dataset.tileUrl, {
    attribution: root.dataset.attribution,
    maxZoom: 19,
  }).addTo(map);
  map.attributionControl.addAttribution(
    "County boundaries: U.S. Census Bureau TIGERweb (2025)",
  );
  map.createPane("state-boundary-casing");
  map.getPane("state-boundary-casing").style.zIndex = 352;
  map.getPane("state-boundary-casing").style.pointerEvents = "none";
  const stateBoundaryCasing = window.L.geoJSON(null, {
    pane: "state-boundary-casing",
    interactive: false,
    style: {
      color: "#ffffff",
      fill: false,
      opacity: 0.9,
      weight: 4,
    },
  }).addTo(map);
  map.createPane("state-boundary");
  map.getPane("state-boundary").style.zIndex = 353;
  map.getPane("state-boundary").style.pointerEvents = "none";
  const stateBoundaryLayer = window.L.geoJSON(null, {
    pane: "state-boundary",
    interactive: false,
    style: {
      color: "#5c686f",
      fill: false,
      opacity: 0.95,
      weight: 2,
    },
  }).addTo(map);
  fetch(root.dataset.stateBoundaryUrl, {
    headers: { Accept: "application/geo+json, application/json" },
  })
    .then((response) => {
      if (!response.ok) throw new Error(`State boundary request failed: ${response.status}`);
      return response.json();
    })
    .then((data) => {
      stateBoundaryCasing.addData(data);
      stateBoundaryLayer.addData(data);
    })
    .catch((error) => console.error(error));
  map.createPane("county-boundaries");
  map.getPane("county-boundaries").style.zIndex = 350;
  const countyLayer = window.L.geoJSON(null, {
    pane: "county-boundaries",
    style: {
      color: "#56645d",
      dashArray: "4 4",
      fill: false,
      opacity: 0.72,
      weight: 1.25,
    },
    onEachFeature(feature, boundary) {
      boundary.bindTooltip(feature.properties.NAME, {
        direction: "center",
        opacity: 0.9,
        sticky: true,
      });
    },
  });
  let countyLayerLoaded = false;
  let countyLayerVisible = false;
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

  function reset() {
    map.setView(defaultView, defaultZoom);
  }

  function setStateBoundaryVisible(visible) {
    if (visible) {
      stateBoundaryCasing.addTo(map);
      stateBoundaryLayer.addTo(map);
    } else {
      stateBoundaryCasing.removeFrom(map);
      stateBoundaryLayer.removeFrom(map);
    }
  }

  async function setCountyLayerVisible(visible) {
    countyLayerVisible = visible;
    if (!visible) {
      countyLayer.removeFrom(map);
      return;
    }
    if (!countyLayerLoaded) {
      const response = await fetch(root.dataset.countiesUrl, {
        headers: { Accept: "application/geo+json, application/json" },
      });
      if (!response.ok) throw new Error(`County boundary request failed: ${response.status}`);
      countyLayer.addData(await response.json());
      countyLayerLoaded = true;
    }
    if (countyLayerVisible) countyLayer.addTo(map);
  }

  return { map, draw, reset, select, setCountyLayerVisible, setStateBoundaryVisible };
}
