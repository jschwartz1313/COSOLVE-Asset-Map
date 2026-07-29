import { buildPopup } from "./popups.js?v=20260727";

const ICON_FILES = {
  university: "university.svg",
  organization: "building-2.svg",
  facility: "factory.svg",
  program: "clipboard-list.svg",
  infrastructure: "construction.svg",
  "operating-environment": "radar.svg",
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
  map.attributionControl.addAttribution(
    "Ecosystem regions: COSOLVE working analytical groupings",
  );
  map.attributionControl.addAttribution(
    "Potential MPZ tracts: U.S. Census Bureau; MARAD, Port of Virginia, U.S. Navy",
  );
  map.createPane("ecosystem-regions");
  map.getPane("ecosystem-regions").style.zIndex = 340;
  const regionLayer = window.L.geoJSON(null, {
    pane: "ecosystem-regions",
    style(feature) {
      const color = feature.properties.region_color || "#66757d";
      return {
        color,
        fillColor: color,
        fillOpacity: 0.24,
        opacity: 0.9,
        weight: 1.8,
      };
    },
    onEachFeature(feature, boundary) {
      const name = feature.properties.region_name;
      const label = document.createElement("span");
      label.textContent = name;
      boundary.bindTooltip(label, {
        className: "region-map-label",
        direction: "center",
        opacity: 0.96,
        permanent: true,
      });
      boundary.on({
        mouseover() {
          boundary.setStyle({ fillOpacity: 0.34, weight: 2.4 });
        },
        mouseout() {
          regionLayer.resetStyle(boundary);
        },
        add() {
          const path = boundary.getElement();
          if (path) path.setAttribute("aria-label", `${name} ecosystem region`);
        },
      });
    },
  });
  let regionLayerLoaded = false;
  let regionLayerVisible = false;
  map.createPane("maritime-prosperity-zones");
  map.getPane("maritime-prosperity-zones").style.zIndex = 345;
  const mpzLayer = window.L.geoJSON(null, {
    pane: "maritime-prosperity-zones",
    style: {
      color: "#8a5a12",
      dashArray: "5 3",
      fillColor: "#d59b35",
      fillOpacity: 0.32,
      opacity: 0.95,
      weight: 2,
    },
    onEachFeature(feature, boundary) {
      const properties = feature.properties;
      const tooltip = document.createElement("span");
      tooltip.textContent = `Potential MPZ tract: ${properties.tract_name}`;
      boundary.bindTooltip(tooltip, { direction: "top", opacity: 0.96, sticky: true });

      const popup = document.createElement("section");
      popup.className = "mpz-popup";
      const eyebrow = document.createElement("span");
      eyebrow.className = "mpz-popup-status";
      eyebrow.textContent = properties.designation_status;
      const heading = document.createElement("h3");
      heading.textContent = `Potential MPZ tract ${properties.tract_name.replace("Census Tract ", "")}`;
      const basis = document.createElement("p");
      basis.textContent = properties.candidate_basis;
      const listHeading = document.createElement("strong");
      listHeading.textContent = `Documented facilities (${properties.facility_count})`;
      const list = document.createElement("ul");
      for (const facility of properties.facilities) {
        const item = document.createElement("li");
        item.textContent = `${facility.name} (${facility.type})`;
        list.append(item);
      }
      const sources = document.createElement("p");
      sources.className = "mpz-popup-sources";
      sources.append("Basis sources: ");
      properties.sources.forEach((source, index) => {
        if (index) sources.append(", ");
        const link = document.createElement("a");
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = source.label;
        sources.append(link);
      });
      const geoid = document.createElement("small");
      geoid.textContent = `2020 Census tract GEOID ${properties.geoid}`;
      popup.append(eyebrow, heading, basis, listHeading, list, sources, geoid);
      boundary.bindPopup(popup, { maxWidth: 330 });
      boundary.on({
        mouseover() {
          boundary.setStyle({ fillOpacity: 0.44, weight: 2.6 });
        },
        mouseout() {
          mpzLayer.resetStyle(boundary);
        },
        add() {
          const path = boundary.getElement();
          if (path) {
            path.setAttribute(
              "aria-label",
              `${properties.tract_name}, potential Maritime Prosperity Zone planning candidate`,
            );
          }
        },
      });
    },
  });
  let mpzLayerLoaded = false;
  let mpzLayerVisible = false;
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

  function buildMarkerIcon(recordType) {
    const visual = document.createElement("span");
    visual.className = `asset-marker ${recordType}`;
    const image = document.createElement("img");
    image.src = `${root.dataset.iconBaseUrl}${ICON_FILES[recordType] || ICON_FILES["operating-environment"]}`;
    image.alt = "";
    image.setAttribute("aria-hidden", "true");
    visual.append(image);
    return window.L.divIcon({
      className: "asset-marker-shell",
      html: visual,
      iconAnchor: [12, 12],
      iconSize: [24, 24],
      popupAnchor: [0, -12],
      tooltipAnchor: [0, -12],
    });
  }

  function draw(features, onSelect, { showLabels = false } = {}) {
    layer.clearLayers();
    markers.clear();
    const bounds = [];
    for (const feature of features) {
      if (!feature.geometry) continue;
      const [longitude, latitude] = feature.geometry.coordinates;
      const marker = window.L.marker([latitude, longitude], {
        alt: `${feature.properties.name} asset marker`,
        icon: buildMarkerIcon(feature.properties.record_type),
        keyboard: true,
        riseOnHover: true,
        title: feature.properties.name,
      });
      marker.bindPopup(buildPopup(feature));
      if (showLabels) {
        marker.bindTooltip(feature.properties.name, {
          className: "asset-search-label",
          direction: "top",
          offset: [0, -12],
          opacity: 1,
          permanent: true,
        });
      }
      marker.on("click", () => onSelect(feature.id));
      layer.addLayer(marker);
      markers.set(feature.id, marker);
      bounds.push([latitude, longitude]);
    }
    if (bounds.length > 1) {
      map.fitBounds(bounds, { animate: false, padding: [35, 35], maxZoom: 11 });
    } else if (bounds.length === 1) {
      map.setView(bounds[0], 10, { animate: false });
    }
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

  function getViewState() {
    const center = map.getCenter();
    return {
      latitude: center.lat,
      longitude: center.lng,
      zoom: map.getZoom(),
    };
  }

  function setViewState(state) {
    if (!state?.hasValidCenter) return;
    map.setView([state.latitude, state.longitude], state.zoom, { animate: false });
  }

  function onViewChange(callback) {
    map.on("moveend zoomend", callback);
  }

  function refresh() {
    map.invalidateSize({ animate: false });
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

  async function setRegionLayerVisible(visible) {
    regionLayerVisible = visible;
    if (!visible) {
      regionLayer.removeFrom(map);
      return;
    }
    if (!regionLayerLoaded) {
      const response = await fetch(root.dataset.regionsUrl, {
        headers: { Accept: "application/geo+json, application/json" },
      });
      if (!response.ok) throw new Error(`Region boundary request failed: ${response.status}`);
      regionLayer.addData(await response.json());
      regionLayerLoaded = true;
    }
    if (regionLayerVisible) regionLayer.addTo(map);
  }

  async function setMpzLayerVisible(visible) {
    mpzLayerVisible = visible;
    if (!visible) {
      mpzLayer.removeFrom(map);
      return;
    }
    if (!mpzLayerLoaded) {
      const response = await fetch(root.dataset.mpzCandidatesUrl, {
        headers: { Accept: "application/geo+json, application/json" },
      });
      if (!response.ok) {
        throw new Error(`Potential MPZ tract request failed: ${response.status}`);
      }
      mpzLayer.addData(await response.json());
      mpzLayerLoaded = true;
    }
    if (mpzLayerVisible) mpzLayer.addTo(map);
  }

  return {
    map,
    draw,
    getViewState,
    onViewChange,
    refresh,
    reset,
    select,
    setViewState,
    setCountyLayerVisible,
    setMpzLayerVisible,
    setRegionLayerVisible,
    setStateBoundaryVisible,
  };
}
