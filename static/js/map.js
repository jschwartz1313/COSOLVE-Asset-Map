import { buildPopup } from "./popups.js?v=20260730";

const ICON_FILES = {
  university: "university.svg",
  organization: "building-2.svg",
  facility: "factory.svg",
  program: "clipboard-list.svg",
  infrastructure: "construction.svg",
  "operating-environment": "radar.svg",
};

const TYPE_ORDER = [
  "university",
  "organization",
  "facility",
  "program",
  "infrastructure",
  "operating-environment",
];

const CLUSTER_TYPE_LABELS = {
  university: "Univ.",
  organization: "Org.",
  facility: "Facility",
  program: "Program",
  infrastructure: "Infra.",
  "operating-environment": "Ops env.",
};

function clusterComposition(cluster) {
  const counts = new Map();
  for (const marker of cluster.getAllChildMarkers()) {
    const type = marker.options.recordType;
    counts.set(type, (counts.get(type) || 0) + 1);
  }
  return TYPE_ORDER.filter((type) => counts.has(type)).map((type) => ({
    type,
    count: counts.get(type),
    label: CLUSTER_TYPE_LABELS[type],
  }));
}

function buildClusterIcon(cluster) {
  const composition = clusterComposition(cluster);
  const bars = composition
    .map(
      (item) =>
        `<i class="cluster-segment ${item.type}" style="flex:${item.count}" aria-hidden="true"></i>`,
    )
    .join("");
  return window.L.divIcon({
    className: "marker-cluster composition-cluster-shell",
    html: `<span class="composition-cluster"><strong>${cluster.getChildCount()}</strong><span>${bars}</span></span>`,
    iconSize: [40, 40],
  });
}

function clusterTooltip(cluster) {
  return clusterComposition(cluster)
    .map(
      (item) =>
        `<span class="cluster-composition-row"><span>${item.label}</span><strong>${item.count}</strong></span>`,
    )
    .join("");
}

export function createMap(root) {
  const defaultView = [Number(root.dataset.lat), Number(root.dataset.lon)];
  const defaultZoom = Number(root.dataset.zoom);
  const map = window.L.map("map", { zoomControl: false }).setView(defaultView, defaultZoom);
  map.attributionControl.setPrefix(false);
  window.L.control.zoom({ position: "bottomright" }).addTo(map);

  const basemaps = {
    street: {
      url: root.dataset.basemapStreetUrl,
      attribution: root.dataset.basemapStreetAttribution,
      maxZoom: 19,
    },
    light: {
      url: root.dataset.basemapLightUrl,
      attribution: root.dataset.basemapLightAttribution,
      maxZoom: 20,
      subdomains: "abcd",
    },
    imagery: {
      url: root.dataset.basemapImageryUrl,
      attribution: root.dataset.basemapImageryAttribution,
      maxZoom: 16,
    },
  };
  let activeBasemap = "street";
  let basemapLayer = window.L.tileLayer(basemaps.street.url, basemaps.street).addTo(map);

  function setBasemap(name) {
    if (!basemaps[name] || name === activeBasemap) return;
    basemapLayer.removeFrom(map);
    basemapLayer = window.L.tileLayer(basemaps[name].url, basemaps[name]).addTo(map);
    basemapLayer.bringToBack();
    activeBasemap = name;
  }

  let regionSelectCallback = () => {};
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
        click() {
          regionSelectCallback(feature.properties);
        },
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
    style: { color: "#ffffff", fill: false, opacity: 0.9, weight: 4 },
  }).addTo(map);
  map.createPane("state-boundary");
  map.getPane("state-boundary").style.zIndex = 353;
  map.getPane("state-boundary").style.pointerEvents = "none";
  const stateBoundaryLayer = window.L.geoJSON(null, {
    pane: "state-boundary",
    interactive: false,
    style: { color: "#5c686f", fill: false, opacity: 0.95, weight: 2 },
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
    ? window.L.markerClusterGroup({
        showCoverageOnHover: false,
        maxClusterRadius: 48,
        iconCreateFunction: buildClusterIcon,
      })
    : window.L.layerGroup();
  if (layer.on) {
    layer.on("clustermouseover", (event) => {
      event.layer
        .bindTooltip(clusterTooltip(event.layer), {
          className: "cluster-composition-tooltip",
          direction: "top",
          opacity: 0.98,
        })
        .openTooltip();
    });
    layer.on("clustermouseout", (event) => event.layer.closeTooltip());
  }
  layer.addTo(map);
  let assetLayerVisible = true;
  let verificationLayerVisible = false;
  let precisionLayerVisible = false;
  const markers = new Map();

  function buildMarkerIcon(feature) {
    const properties = feature.properties;
    const visual = document.createElement("span");
    const classes = ["asset-marker", properties.record_type];
    if (verificationLayerVisible) {
      classes.push("show-verification", `verification-${properties.verification_state}`);
    }
    if (precisionLayerVisible) {
      classes.push("show-precision", `precision-${properties.location.precision}`);
    }
    visual.className = classes.join(" ");
    const image = document.createElement("img");
    image.src = `${root.dataset.iconBaseUrl}${
      ICON_FILES[properties.record_type] || ICON_FILES["operating-environment"]
    }`;
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

  function refreshMarkerIcons() {
    for (const [id, marker] of markers) {
      marker.setIcon(buildMarkerIcon(marker.options.assetFeature));
      markers.set(id, marker);
    }
    if (layer.refreshClusters) layer.refreshClusters();
  }

  function draw(features, onSelect, { showLabels = false, fit = true } = {}) {
    layer.clearLayers();
    markers.clear();
    const bounds = [];
    for (const feature of features) {
      if (!feature.geometry) continue;
      const [longitude, latitude] = feature.geometry.coordinates;
      const marker = window.L.marker([latitude, longitude], {
        alt: `${feature.properties.name} asset marker`,
        assetFeature: feature,
        icon: buildMarkerIcon(feature),
        keyboard: true,
        recordType: feature.properties.record_type,
        recordTypeLabel: feature.properties.record_type_label,
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
    if (!fit) return;
    if (bounds.length > 1) {
      map.fitBounds(bounds, { animate: false, padding: [35, 35], maxZoom: 11 });
    } else if (bounds.length === 1) {
      map.setView(bounds[0], 10, { animate: false });
    }
  }

  function select(id) {
    const marker = markers.get(id);
    if (!marker || !assetLayerVisible) return;
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
      basemap: activeBasemap,
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

  function setAssetLayerVisible(visible) {
    assetLayerVisible = visible;
    if (visible) layer.addTo(map);
    else layer.removeFrom(map);
  }

  function setVerificationLayerVisible(visible) {
    verificationLayerVisible = visible;
    refreshMarkerIcons();
  }

  function setPrecisionLayerVisible(visible) {
    precisionLayerVisible = visible;
    refreshMarkerIcons();
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

  map.createPane("analysis-selection");
  map.getPane("analysis-selection").style.zIndex = 390;
  let selectionRectangle = null;
  let selectionPolygon = null;
  let selectionVertices = [];
  let selectionVertexLayer = null;
  let selectionStart = null;
  let selectionCallback = null;
  let nearbyCircle = null;
  let selecting = false;
  let selectionMode = null;

  function selectionBounds() {
    if (!selectionRectangle) return null;
    const bounds = selectionRectangle.getBounds();
    return {
      south: bounds.getSouth(),
      west: bounds.getWest(),
      north: bounds.getNorth(),
      east: bounds.getEast(),
    };
  }

  function stopSelecting() {
    if (!selecting) return;
    selecting = false;
    selectionStart = null;
    selectionMode = null;
    map.dragging.enable();
    map.doubleClickZoom.enable();
    map.getContainer().classList.remove("is-selecting-area");
    map.getContainer().classList.remove("is-selecting-polygon");
  }

  const mapContainer = map.getContainer();
  mapContainer.addEventListener("mousedown", (event) => {
    if (!selecting || selectionMode !== "rectangle" || event.button !== 0) return;
    event.preventDefault();
    selectionStart = map.mouseEventToLatLng(event);
    if (selectionRectangle) selectionRectangle.removeFrom(map);
    selectionRectangle = window.L.rectangle([selectionStart, selectionStart], {
      pane: "analysis-selection",
      color: "#c83d2c",
      fillColor: "#c83d2c",
      fillOpacity: 0.09,
      weight: 2,
    }).addTo(map);
  });
  document.addEventListener("mousemove", (event) => {
    if (
      !selecting ||
      selectionMode !== "rectangle" ||
      !selectionStart ||
      !selectionRectangle
    ) {
      return;
    }
    const current = map.mouseEventToLatLng(event);
    selectionRectangle.setBounds(window.L.latLngBounds(selectionStart, current));
  });
  document.addEventListener("mouseup", () => {
    if (
      !selecting ||
      selectionMode !== "rectangle" ||
      !selectionStart ||
      !selectionRectangle
    ) {
      return;
    }
    const callback = selectionCallback;
    stopSelecting();
    callback?.(selectionBounds());
  });

  function beginAreaSelection(callback) {
    stopSelecting();
    if (selectionRectangle) selectionRectangle.removeFrom(map);
    removePolygonSelection();
    selectionRectangle = null;
    selectionCallback = callback;
    selecting = true;
    selectionMode = "rectangle";
    map.dragging.disable();
    map.closePopup();
    map.getContainer().classList.add("is-selecting-area");
  }

  function removePolygonSelection() {
    if (selectionPolygon) selectionPolygon.removeFrom(map);
    if (selectionVertexLayer) selectionVertexLayer.removeFrom(map);
    selectionPolygon = null;
    selectionVertexLayer = null;
    selectionVertices = [];
  }

  function addPolygonVertex(latlng) {
    const previous = selectionVertices.at(-1);
    if (previous) {
      const previousPoint = map.latLngToContainerPoint(previous);
      const currentPoint = map.latLngToContainerPoint(latlng);
      if (previousPoint.distanceTo(currentPoint) < 5) return;
    }
    selectionVertices.push(latlng);
    selectionPolygon.setLatLngs(selectionVertices);
    window.L.circleMarker(latlng, {
      pane: "analysis-selection",
      className: "analysis-selection-vertex",
      color: "#ffffff",
      fillColor: "#c83d2c",
      fillOpacity: 1,
      interactive: false,
      radius: 4,
      weight: 1.5,
    }).addTo(selectionVertexLayer);
  }

  function beginPolygonSelection(callback) {
    stopSelecting();
    if (selectionRectangle) selectionRectangle.removeFrom(map);
    selectionRectangle = null;
    removePolygonSelection();
    selectionCallback = callback;
    selecting = true;
    selectionMode = "polygon";
    map.dragging.disable();
    map.doubleClickZoom.disable();
    map.closePopup();
    selectionPolygon = window.L.polygon([], {
      pane: "analysis-selection",
      className: "analysis-selection-polygon",
      color: "#c83d2c",
      fillColor: "#c83d2c",
      fillOpacity: 0.09,
      interactive: false,
      weight: 2,
    }).addTo(map);
    selectionVertexLayer = window.L.layerGroup().addTo(map);
    map.getContainer().classList.add("is-selecting-polygon");
  }

  function showPolygonSelection(vertices) {
    stopSelecting();
    if (selectionRectangle) selectionRectangle.removeFrom(map);
    selectionRectangle = null;
    removePolygonSelection();
    selectionVertices = vertices.map((vertex) => window.L.latLng(vertex.lat, vertex.lng));
    selectionPolygon = window.L.polygon(selectionVertices, {
      pane: "analysis-selection",
      className: "analysis-selection-polygon",
      color: "#c83d2c",
      fillColor: "#c83d2c",
      fillOpacity: 0.09,
      interactive: false,
      weight: 2,
    }).addTo(map);
  }

  function finishPolygonSelection() {
    if (!selecting || selectionMode !== "polygon" || selectionVertices.length < 3) {
      return false;
    }
    const callback = selectionCallback;
    const vertices = selectionVertices.map((vertex) => ({
      lat: vertex.lat,
      lng: vertex.lng,
    }));
    selectionPolygon.setLatLngs(selectionVertices);
    stopSelecting();
    callback?.(vertices);
    return true;
  }

  function cancelSelection() {
    if (!selecting) return;
    const cancelledMode = selectionMode;
    stopSelecting();
    if (cancelledMode === "polygon") removePolygonSelection();
    if (cancelledMode === "rectangle" && selectionRectangle) {
      selectionRectangle.removeFrom(map);
      selectionRectangle = null;
    }
  }

  mapContainer.addEventListener("pointerdown", (event) => {
    if (!selecting || selectionMode !== "polygon") return;
    event.preventDefault();
    event.stopPropagation();
    addPolygonVertex(map.mouseEventToLatLng(event));
  }, true);
  mapContainer.addEventListener("click", (event) => {
    if (!selecting || selectionMode !== "polygon") return;
    event.preventDefault();
    event.stopPropagation();
  }, true);
  mapContainer.addEventListener("dblclick", (event) => {
    if (!selecting || selectionMode !== "polygon") return;
    event.preventDefault();
    event.stopPropagation();
    finishPolygonSelection();
  }, true);

  function selectVisibleExtent(callback) {
    showAreaSelection({
      south: map.getBounds().getSouth(),
      west: map.getBounds().getWest(),
      north: map.getBounds().getNorth(),
      east: map.getBounds().getEast(),
    });
    callback(selectionBounds());
  }

  function showAreaSelection(bounds) {
    stopSelecting();
    if (selectionRectangle) selectionRectangle.removeFrom(map);
    removePolygonSelection();
    selectionRectangle = window.L.rectangle(
      [
        [bounds.south, bounds.west],
        [bounds.north, bounds.east],
      ],
      {
        pane: "analysis-selection",
        color: "#c83d2c",
        fillColor: "#c83d2c",
        fillOpacity: 0.09,
        weight: 2,
      },
    ).addTo(map);
  }

  function showNearbyRadius(radiusMiles) {
    if (nearbyCircle) nearbyCircle.removeFrom(map);
    nearbyCircle = window.L.circle(map.getCenter(), {
      pane: "analysis-selection",
      color: "#147d78",
      fillColor: "#147d78",
      fillOpacity: 0.07,
      radius: radiusMiles * 1609.344,
      weight: 2,
    }).addTo(map);
  }

  function clearAnalysisGraphics() {
    stopSelecting();
    if (selectionRectangle) selectionRectangle.removeFrom(map);
    removePolygonSelection();
    if (nearbyCircle) nearbyCircle.removeFrom(map);
    selectionRectangle = null;
    nearbyCircle = null;
  }

  return {
    map,
    beginAreaSelection,
    beginPolygonSelection,
    cancelSelection,
    clearAnalysisGraphics,
    draw,
    finishPolygonSelection,
    getViewState,
    onRegionSelect(callback) {
      regionSelectCallback = callback;
    },
    onViewChange,
    refresh,
    reset,
    select,
    selectVisibleExtent,
    setAssetLayerVisible,
    setBasemap,
    setCountyLayerVisible,
    setMpzLayerVisible,
    setPrecisionLayerVisible,
    setRegionLayerVisible,
    setStateBoundaryVisible,
    setVerificationLayerVisible,
    setViewState,
    showAreaSelection,
    showNearbyRadius,
    showPolygonSelection,
  };
}
