import { buildPopup } from "./popups.js?v=20260906-1";

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

const CONTROLLED_AIRSPACE_COLORS = {
  B: "#9c2f3f",
  C: "#b55a1f",
  D: "#276d79",
  E: "#486da8",
};

function appendDefinitionList(container, entries) {
  const list = document.createElement("dl");
  for (const [label, value] of entries) {
    if (!value) continue;
    const term = document.createElement("dt");
    term.textContent = label;
    const definition = document.createElement("dd");
    definition.textContent = value;
    list.append(term, definition);
  }
  container.append(list);
}

function appendReferenceLink(container, label, url) {
  const link = document.createElement("a");
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = label;
  container.append(link);
}

function referencePopup({ status, title, entries, links = [] }) {
  const popup = document.createElement("section");
  popup.className = "drone-reference-popup";
  const eyebrow = document.createElement("span");
  eyebrow.className = "drone-reference-status";
  eyebrow.textContent = status;
  const heading = document.createElement("h3");
  heading.textContent = title;
  popup.append(eyebrow, heading);
  appendDefinitionList(popup, entries);
  if (links.length) {
    const sources = document.createElement("p");
    sources.className = "drone-reference-sources";
    links.forEach(([label, url], index) => {
      if (index) sources.append(" · ");
      appendReferenceLink(sources, label, url);
    });
    popup.append(sources);
  }
  return popup;
}

function authorizationCeilingClass(value) {
  if (value === 0) return "zero";
  if (value <= 100) return "low";
  if (value <= 250) return "mid";
  return "high";
}

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

  map.createPane("heliports");
  map.getPane("heliports").style.zIndex = 360;
  const heliportLayer = window.L.layerGroup();
  let heliportLayerLoaded = false;
  let heliportLayerVisible = false;

  map.createPane("controlled-airspace");
  map.getPane("controlled-airspace").style.zIndex = 342;
  const controlledAirspaceLayer = window.L.geoJSON(null, {
    pane: "controlled-airspace",
    style(feature) {
      const color = CONTROLLED_AIRSPACE_COLORS[feature.properties.class] || "#486da8";
      return {
        color,
        fillColor: color,
        fillOpacity: 0.12,
        opacity: 0.9,
        weight: 1.6,
      };
    },
    onEachFeature(feature, boundary) {
      const properties = feature.properties;
      boundary.bindTooltip(
        `${properties.name} · Class ${properties.class} from surface`,
        { direction: "top", opacity: 0.96, sticky: true },
      );
      boundary.bindPopup(
        referencePopup({
          status: "FAA controlled airspace",
          title: properties.name,
          entries: [
            ["Class", properties.class ? `Class ${properties.class}` : ""],
            ["Identifier", properties.identifier],
            ["Floor", properties.lower_limit],
            ["Published upper limit", properties.upper_limit],
            ["Hours note", properties.hours_note],
          ],
          links: [["FAA flying near airports", root.dataset.faaAirspaceInfoUrl]],
        }),
        { maxWidth: 330 },
      );
    },
  });
  let controlledAirspaceLoaded = false;
  let controlledAirspaceVisible = false;

  map.createPane("uas-facility-map");
  map.getPane("uas-facility-map").style.zIndex = 344;
  const uasFacilityMapRenderer = window.L.canvas({
    pane: "uas-facility-map",
    padding: 0.5,
  });
  const uasFacilityMapLayer = window.L.geoJSON(null, {
    pane: "uas-facility-map",
    renderer: uasFacilityMapRenderer,
    style(feature) {
      const ceilingClass = authorizationCeilingClass(feature.properties.ceiling_agl_ft);
      const colors = {
        zero: "#a62f35",
        low: "#d27a28",
        mid: "#d0a52c",
        high: "#3d8477",
      };
      const color = colors[ceilingClass];
      return {
        color,
        fillColor: color,
        fillOpacity: 0.28,
        opacity: 0.42,
        weight: 0.45,
      };
    },
    onEachFeature(feature, boundary) {
      const properties = feature.properties;
      const airports = properties.airports
        .map((airport) => {
          const identifiers = [airport.faa_id, airport.icao_id].filter(Boolean).join(" / ");
          const laanc = airport.laanc_enabled ? "LAANC enabled" : "manual FAA process";
          return `${airport.name}${identifiers ? ` (${identifiers})` : ""}; ${laanc}`;
        })
        .join(" · ");
      boundary.bindTooltip(`${properties.ceiling_agl_ft} ft AGL authorization ceiling`, {
        direction: "top",
        opacity: 0.96,
        sticky: true,
      });
      boundary.bindPopup(
        referencePopup({
          status: "FAA UAS Facility Map",
          title: `${properties.ceiling_agl_ft} ft AGL`,
          entries: [
            ["Meaning", "Altitude used by the FAA to evaluate Part 107 authorization requests"],
            ["Airport", airports],
            ["Airspace", properties.airspace_classes.join(", ")],
            ["Map effective", properties.map_effective],
          ],
          links: [["FAA LAANC information", root.dataset.faaUasfmInfoUrl]],
        }),
        { maxWidth: 340 },
      );
    },
  });
  let uasFacilityMapLoaded = false;
  let uasFacilityMapVisible = false;

  map.createPane("flight-constraints");
  map.getPane("flight-constraints").style.zIndex = 346;
  const flightConstraintsLayer = window.L.geoJSON(null, {
    pane: "flight-constraints",
    style(feature) {
      const properties = feature.properties;
      if (properties.constraint_type === "national-security-uas") {
        return {
          className: "flight-constraint national-security",
          color: "#8d2633",
          fillColor: "#b53e4d",
          fillOpacity: 0.38,
          opacity: 0.98,
          weight: 2,
        };
      }
      const strict = ["P", "R"].includes(properties.type_code);
      return {
        className: `flight-constraint ${strict ? "restricted" : "advisory"}`,
        color: strict ? "#732b5a" : "#725d25",
        dashArray: strict ? "5 3" : "7 4",
        fillColor: strict ? "#a94a82" : "#d2b55b",
        fillOpacity: strict ? 0.22 : 0.14,
        opacity: 0.92,
        weight: strict ? 1.8 : 1.4,
      };
    },
    onEachFeature(feature, boundary) {
      const properties = feature.properties;
      boundary.bindTooltip(`${properties.category}: ${properties.name}`, {
        direction: "top",
        opacity: 0.96,
        sticky: true,
      });
      const source = properties.constraint_type === "national-security-uas"
        ? ["FAA national-security UAS restrictions", root.dataset.faaSecurityInfoUrl]
        : ["FAA aeronautical data", root.dataset.faaDataInfoUrl];
      boundary.bindPopup(
        referencePopup({
          status: properties.category,
          title: properties.name,
          entries: [
            ["Facility or base", properties.base],
            ["Agency", properties.branch],
            ["County", properties.county],
            ["Vertical extent", `${properties.floor} to ${properties.ceiling}`],
            ["Published schedule", properties.times_of_use],
            ["FAA remarks", properties.remarks],
          ],
          links: [source],
        }),
        { maxWidth: 350 },
      );
    },
  });
  let flightConstraintsLoaded = false;
  let flightConstraintsVisible = false;

  map.createPane("uas-test-sites");
  map.getPane("uas-test-sites").style.zIndex = 365;
  const uasTestSitesLayer = window.L.layerGroup();
  let uasTestSitesLoaded = false;
  let uasTestSitesVisible = false;

  function heliportPopup(properties) {
    const popup = document.createElement("section");
    popup.className = "heliport-popup";
    const status = document.createElement("span");
    status.className = "heliport-popup-status";
    status.textContent = "FAA reference · Private use";
    const heading = document.createElement("h3");
    heading.textContent = properties.name;
    const location = document.createElement("p");
    location.textContent = [properties.service_city, "Virginia"].filter(Boolean).join(", ");
    const identifier = document.createElement("p");
    identifier.textContent = properties.identifier
      ? `FAA identifier ${properties.identifier}`
      : "No public identifier listed";
    const source = document.createElement("a");
    source.href = "https://www.faa.gov/data/aero_data";
    source.target = "_blank";
    source.rel = "noopener";
    source.textContent = "FAA aeronautical data";
    popup.append(status, heading, location, identifier, source);
    return popup;
  }

  function addHeliports(data) {
    for (const feature of data.features) {
      if (!feature.geometry) continue;
      const [longitude, latitude] = feature.geometry.coordinates;
      const properties = feature.properties;
      const icon = window.L.divIcon({
        className: "heliport-reference-shell",
        html: '<span class="heliport-reference-marker" aria-hidden="true">H</span>',
        iconAnchor: [9, 9],
        iconSize: [18, 18],
        popupAnchor: [0, -9],
        tooltipAnchor: [0, -9],
      });
      const marker = window.L.marker([latitude, longitude], {
        alt: `${properties.name} private-use heliport reference point`,
        icon,
        keyboard: true,
        pane: "heliports",
        riseOnHover: true,
        title: properties.name,
      });
      marker.bindTooltip(properties.name, { direction: "top", opacity: 0.96 });
      marker.bindPopup(heliportPopup(properties), { maxWidth: 300 });
      heliportLayer.addLayer(marker);
    }
  }

  function addUasTestSites(data) {
    for (const feature of data.features) {
      if (!feature.geometry) continue;
      const [longitude, latitude] = feature.geometry.coordinates;
      const properties = feature.properties;
      const icon = window.L.divIcon({
        className: "uas-test-site-shell",
        html: `<span class="uas-test-site-marker" aria-hidden="true"><img src="${root.dataset.iconBaseUrl}radar.svg" alt=""></span>`,
        iconAnchor: [14, 14],
        iconSize: [28, 28],
        popupAnchor: [0, -14],
        tooltipAnchor: [0, -14],
      });
      const marker = window.L.marker([latitude, longitude], {
        alt: `${properties.name} UAS test facility reference point`,
        icon,
        keyboard: true,
        pane: "uas-test-sites",
        riseOnHover: true,
        title: properties.name,
      });
      marker.bindTooltip(properties.name, { direction: "top", opacity: 0.96 });
      const links = [[properties.source_title, properties.source_url]];
      if (properties.secondary_source_url) {
        links.push([properties.secondary_source_title, properties.secondary_source_url]);
      }
      marker.bindPopup(
        referencePopup({
          status: properties.site_type,
          title: properties.name,
          entries: [
            ["Location", `${properties.city}, Virginia · ${properties.location_precision}`],
            ["Published size", properties.published_size],
            ["Takeoff and landing", properties.launch_recovery],
            ["Support infrastructure", properties.support_infrastructure],
            ["Aircraft or mission scope", properties.aircraft_scope],
            ["Access", properties.access],
            ["Published constraints", properties.flight_constraints],
          ],
          links,
        }),
        { maxWidth: 390 },
      );
      uasTestSitesLayer.addLayer(marker);
    }
  }

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

  async function setHeliportLayerVisible(visible) {
    heliportLayerVisible = visible;
    if (!visible) {
      heliportLayer.removeFrom(map);
      return;
    }
    if (!heliportLayerLoaded) {
      const response = await fetch(root.dataset.heliportsUrl, {
        headers: { Accept: "application/geo+json, application/json" },
      });
      if (!response.ok) throw new Error(`Heliport request failed: ${response.status}`);
      addHeliports(await response.json());
      heliportLayerLoaded = true;
    }
    if (heliportLayerVisible) heliportLayer.addTo(map);
  }

  async function toggleGeoJsonLayer({ visible, loaded, layer: targetLayer, url, errorLabel }) {
    if (!visible) {
      targetLayer.removeFrom(map);
      return loaded;
    }
    if (!loaded) {
      const response = await fetch(url, {
        headers: { Accept: "application/geo+json, application/json" },
      });
      if (!response.ok) throw new Error(`${errorLabel} request failed: ${response.status}`);
      targetLayer.addData(await response.json());
      loaded = true;
    }
    targetLayer.addTo(map);
    return loaded;
  }

  async function setControlledAirspaceVisible(visible) {
    controlledAirspaceVisible = visible;
    controlledAirspaceLoaded = await toggleGeoJsonLayer({
      visible,
      loaded: controlledAirspaceLoaded,
      layer: controlledAirspaceLayer,
      url: root.dataset.controlledAirspaceUrl,
      errorLabel: "Controlled airspace",
    });
  }

  async function setUasFacilityMapVisible(visible) {
    uasFacilityMapVisible = visible;
    uasFacilityMapLoaded = await toggleGeoJsonLayer({
      visible,
      loaded: uasFacilityMapLoaded,
      layer: uasFacilityMapLayer,
      url: root.dataset.uasFacilityMapUrl,
      errorLabel: "FAA UAS Facility Map",
    });
  }

  async function setFlightConstraintsVisible(visible) {
    flightConstraintsVisible = visible;
    flightConstraintsLoaded = await toggleGeoJsonLayer({
      visible,
      loaded: flightConstraintsLoaded,
      layer: flightConstraintsLayer,
      url: root.dataset.flightConstraintsUrl,
      errorLabel: "Flight constraints",
    });
  }

  async function setUasTestSitesVisible(visible) {
    uasTestSitesVisible = visible;
    if (!visible) {
      uasTestSitesLayer.removeFrom(map);
      return;
    }
    if (!uasTestSitesLoaded) {
      const response = await fetch(root.dataset.uasTestSitesUrl, {
        headers: { Accept: "application/geo+json, application/json" },
      });
      if (!response.ok) throw new Error(`UAS test-site request failed: ${response.status}`);
      addUasTestSites(await response.json());
      uasTestSitesLoaded = true;
    }
    if (uasTestSitesVisible) uasTestSitesLayer.addTo(map);
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
    setControlledAirspaceVisible,
    setCountyLayerVisible,
    setFlightConstraintsVisible,
    setHeliportLayerVisible,
    setMpzLayerVisible,
    setPrecisionLayerVisible,
    setRegionLayerVisible,
    setStateBoundaryVisible,
    setUasFacilityMapVisible,
    setUasTestSitesVisible,
    setVerificationLayerVisible,
    setViewState,
    showAreaSelection,
    showNearbyRadius,
    showPolygonSelection,
  };
}
