import { fetchAssets, fetchRelationships } from "./api.js?v=20260730";
import { bindFilterDrawer, bindFilterIndicators } from "./filters.js?v=20260722-3";
import {
  downloadFeatureCsv,
  featuresWithinBounds,
  featuresWithinRadius,
  summarizeRegion,
} from "./map-analysis.js?v=20260730";
import { createMap } from "./map.js?v=20260730-1";
import {
  filterParamsFromMapUrl,
  mapStateFromParams,
  paramsWithMapState,
} from "./map-state.js?v=20260730";
import { renderResults, selectResult } from "./results.js?v=20260727-2";
import { hydrateForm, paramsFromForm, updateUrl } from "./state.js?v=20260717";

const root = document.querySelector("[data-map-app]");
const form = document.querySelector("#asset-filters");
const list = document.querySelector("#result-list");
const count = document.querySelector("#result-count");
const status = document.querySelector("#map-status");
const directoryLink = document.querySelector("#directory-link");
const exportLink = document.querySelector("#export-link");
const saveViewLink = document.querySelector("#save-view-link");
const copyViewButton = document.querySelector("#copy-view-link");
const printViewButton = document.querySelector("#print-view");
const presentationButton = document.querySelector("#presentation-view");
const exitPresentationButton = document.querySelector("#exit-presentation");
const viewActionStatus = document.querySelector("#view-action-status");
const printMapSummary = document.querySelector("#print-map-summary");
const assetLayerToggle = document.querySelector("#asset-layer-toggle");
const countyLayerToggle = document.querySelector("#county-layer-toggle");
const regionLayerToggle = document.querySelector("#region-layer-toggle");
const mpzLayerToggle = document.querySelector("#mpz-layer-toggle");
const stateBoundaryToggle = document.querySelector("#state-boundary-toggle");
const relationshipLayerToggle = document.querySelector("#relationship-layer-toggle");
const verificationLayerToggle = document.querySelector("#verification-layer-toggle");
const precisionLayerToggle = document.querySelector("#precision-layer-toggle");
const basemapInputs = [...document.querySelectorAll('input[name="map-basemap"]')];
const verificationLegend = document.querySelector("[data-verification-legend]");
const precisionLegend = document.querySelector("[data-precision-legend]");
const nearbyRadius = document.querySelector("#nearby-radius");
const nearbySearchButton = document.querySelector("#nearby-search");
const selectAreaButton = document.querySelector("#select-area");
const selectExtentButton = document.querySelector("#select-extent");
const exportAreaButton = document.querySelector("#export-area");
const clearAnalysisButton = document.querySelector("#clear-analysis");
const analysisStatus = document.querySelector("#analysis-status");
const summaryRegion = document.querySelector("#summary-region");
const showRegionSummaryButton = document.querySelector("#show-region-summary");
const mapAnalysisDetails = document.querySelector(".map-analysis");
const insightPanel = document.querySelector("#map-insight-panel");
const insightTitle = document.querySelector("#map-insight-title");
const insightContent = document.querySelector("#map-insight-content");
const closeInsightButton = document.querySelector("#close-map-insight");
const initialPageParams = new URLSearchParams(window.location.search);
const initialMapState = mapStateFromParams(initialPageParams);
const initialFilterParams = filterParamsFromMapUrl(initialPageParams);
const defaultVisibleLayers = ["assets", "state"];

function selectedBasemap() {
  return basemapInputs.find((input) => input.checked)?.value || "street";
}

function applyLayerToggleState(state) {
  const layers = state?.layers || defaultVisibleLayers;
  assetLayerToggle.checked = layers.includes("assets");
  stateBoundaryToggle.checked = layers.includes("state");
  regionLayerToggle.checked = layers.includes("regions");
  mpzLayerToggle.checked = layers.includes("mpz");
  countyLayerToggle.checked = layers.includes("counties");
  relationshipLayerToggle.checked = layers.includes("relationships");
  verificationLayerToggle.checked = layers.includes("verification");
  precisionLayerToggle.checked = layers.includes("precision");
  const basemap = state?.basemap || "street";
  for (const input of basemapInputs) input.checked = input.value === basemap;
}

applyLayerToggleState(initialMapState);
const mapController = createMap(root);
const closeDrawer = bindFilterDrawer(root);
const updateFilterIndicators = bindFilterIndicators(form);
let activeFilterParams = initialFilterParams;
let allFeatures = [];
let fullResultCount = 0;
let selectedAreaFeatures = [];
let relationshipDataLoaded = false;
let loadRequestId = 0;

function showStatus(message) {
  status.textContent = message;
  status.hidden = !message;
}

function currentLayers() {
  const layers = [];
  if (assetLayerToggle.checked) layers.push("assets");
  if (stateBoundaryToggle.checked) layers.push("state");
  if (regionLayerToggle.checked) layers.push("regions");
  if (mpzLayerToggle.checked) layers.push("mpz");
  if (countyLayerToggle.checked) layers.push("counties");
  if (verificationLayerToggle.checked) layers.push("verification");
  if (precisionLayerToggle.checked) layers.push("precision");
  if (relationshipLayerToggle.checked) layers.push("relationships");
  return layers;
}

function currentMapParams() {
  const center = mapController.getViewState();
  return paramsWithMapState(activeFilterParams, {
    ...center,
    basemap: selectedBasemap(),
    layers: currentLayers(),
  });
}

function currentMapUrl() {
  const url = new URL(window.location.pathname, window.location.origin);
  url.search = currentMapParams().toString();
  return url.toString();
}

function updateViewActions() {
  const params = currentMapParams();
  if (saveViewLink) {
    saveViewLink.href = `/saved-views/?view_type=map&query=${encodeURIComponent(params)}`;
  }
  if (printMapSummary) {
    const filterState = activeFilterParams.toString() ? "Filtered view" : "Statewide view";
    printMapSummary.textContent = `${filterState} · ${count.textContent || "0"} assets · ${new Date().toLocaleDateString()}`;
  }
}

function renderFeatureCollection(
  features,
  { fit = false, resultCount = features.length, showSearchLabels = false } = {},
) {
  const selectOnMap = (id) => {
    mapController.select(id);
    selectResult(list, id);
  };
  mapController.draw(features, (id) => selectResult(list, id), {
    fit,
    showLabels: showSearchLabels,
  });
  renderResults(list, features, selectOnMap);
  count.textContent = String(resultCount);
  updateViewActions();
}

function clearAnalysis({ render = true } = {}) {
  mapController.clearAnalysisGraphics();
  selectedAreaFeatures = [];
  exportAreaButton.disabled = true;
  clearAnalysisButton.hidden = true;
  analysisStatus.textContent = "";
  if (render && allFeatures.length) {
    renderFeatureCollection(allFeatures, {
      resultCount: fullResultCount,
      showSearchLabels: Boolean(activeFilterParams.get("q")?.trim()),
    });
  }
}

function applyAreaSelection(bounds) {
  selectedAreaFeatures = featuresWithinBounds(allFeatures, bounds);
  renderFeatureCollection(selectedAreaFeatures);
  exportAreaButton.disabled = selectedAreaFeatures.length === 0;
  clearAnalysisButton.hidden = false;
  analysisStatus.textContent = `${selectedAreaFeatures.length} assets selected`;
}

function renderRegionSummary(regionSlug, regionName) {
  const summary = summarizeRegion(allFeatures, regionSlug);
  mapAnalysisDetails.open = false;
  insightTitle.textContent = regionName;
  insightContent.replaceChildren();

  const metrics = document.createElement("div");
  metrics.className = "insight-metrics";
  for (const [value, label] of [
    [summary.total, "Assets"],
    [summary.siteLevel, "Site-level pins"],
    [summary.reviewed, "Reviewed"],
  ]) {
    const item = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = String(value);
    item.append(strong, label);
    metrics.append(item);
  }
  insightContent.append(metrics);

  if (summary.types.length) {
    const heading = document.createElement("h3");
    heading.textContent = "Asset mix";
    const listNode = document.createElement("dl");
    for (const [label, value] of summary.types) {
      const term = document.createElement("dt");
      term.textContent = label;
      const definition = document.createElement("dd");
      definition.textContent = String(value);
      listNode.append(term, definition);
    }
    insightContent.append(heading, listNode);
  }
  if (summary.capabilities.length) {
    const heading = document.createElement("h3");
    heading.textContent = "Leading capabilities";
    const listNode = document.createElement("ol");
    for (const [label, value] of summary.capabilities) {
      const item = document.createElement("li");
      item.textContent = `${label} (${value})`;
      listNode.append(item);
    }
    insightContent.append(heading, listNode);
  }
  insightPanel.hidden = false;
}

document.querySelector("#reset-view").addEventListener("click", () => mapController.reset());
assetLayerToggle.addEventListener("change", () => {
  mapController.setAssetLayerVisible(assetLayerToggle.checked);
  updateViewActions();
});
stateBoundaryToggle.addEventListener("change", () => {
  mapController.setStateBoundaryVisible(stateBoundaryToggle.checked);
  updateViewActions();
});
verificationLayerToggle.addEventListener("change", () => {
  mapController.setVerificationLayerVisible(verificationLayerToggle.checked);
  verificationLegend.hidden = !verificationLayerToggle.checked;
  updateViewActions();
});
precisionLayerToggle.addEventListener("change", () => {
  mapController.setPrecisionLayerVisible(precisionLayerToggle.checked);
  precisionLegend.hidden = !precisionLayerToggle.checked;
  updateViewActions();
});
for (const input of basemapInputs) {
  input.addEventListener("change", () => {
    if (!input.checked) return;
    mapController.setBasemap(input.value);
    updateViewActions();
  });
}

async function updateCountyLayer() {
  countyLayerToggle.disabled = true;
  try {
    await mapController.setCountyLayerVisible(countyLayerToggle.checked);
  } catch (error) {
    countyLayerToggle.checked = false;
    showStatus("County boundaries could not be loaded.");
    console.error(error);
  } finally {
    countyLayerToggle.disabled = false;
    updateViewActions();
  }
}

countyLayerToggle.addEventListener("change", updateCountyLayer);

async function updateRegionLayer() {
  regionLayerToggle.disabled = true;
  try {
    await mapController.setRegionLayerVisible(regionLayerToggle.checked);
  } catch (error) {
    regionLayerToggle.checked = false;
    showStatus("Ecosystem region shading could not be loaded.");
    console.error(error);
  } finally {
    regionLayerToggle.disabled = false;
    updateViewActions();
  }
}

regionLayerToggle.addEventListener("change", updateRegionLayer);

async function updateMpzLayer() {
  mpzLayerToggle.disabled = true;
  try {
    await mapController.setMpzLayerVisible(mpzLayerToggle.checked);
  } catch (error) {
    mpzLayerToggle.checked = false;
    showStatus("Potential Maritime Prosperity Zone tracts could not be loaded.");
    console.error(error);
  } finally {
    mpzLayerToggle.disabled = false;
    updateViewActions();
  }
}

mpzLayerToggle.addEventListener("change", updateMpzLayer);

async function updateRelationshipLayer() {
  relationshipLayerToggle.disabled = true;
  try {
    if (relationshipLayerToggle.checked && !relationshipDataLoaded) {
      const data = await fetchRelationships(root.dataset.relationshipsUrl);
      mapController.setRelationshipFeatures(data.features);
      relationshipDataLoaded = true;
    }
    mapController.setRelationshipLayerVisible(relationshipLayerToggle.checked);
  } catch (error) {
    relationshipLayerToggle.checked = false;
    mapController.setRelationshipLayerVisible(false);
    showStatus("Asset relationships could not be loaded.");
    console.error(error);
  } finally {
    relationshipLayerToggle.disabled = false;
    updateViewActions();
  }
}

relationshipLayerToggle.addEventListener("change", updateRelationshipLayer);

async function copyCurrentView() {
  const url = currentMapUrl();
  try {
    await navigator.clipboard.writeText(url);
  } catch {
    const input = document.createElement("textarea");
    input.value = url;
    input.setAttribute("readonly", "");
    input.className = "visually-hidden";
    document.body.append(input);
    input.select();
    document.execCommand("copy");
    input.remove();
  }
  copyViewButton.textContent = "Link copied";
  viewActionStatus.textContent = "A link to this exact map view was copied.";
  window.setTimeout(() => {
    copyViewButton.textContent = "Copy view link";
    viewActionStatus.textContent = "";
  }, 1800);
}

function setPresentationMode(enabled) {
  document.body.classList.toggle("presentation-mode", enabled);
  exitPresentationButton.hidden = !enabled;
  if (enabled) {
    for (const details of document.querySelectorAll(".map-tools details")) details.open = false;
    document.querySelector(".map-legend").open = true;
  }
  window.requestAnimationFrame(() => mapController.refresh());
}

copyViewButton.addEventListener("click", copyCurrentView);
printViewButton.addEventListener("click", () => window.print());
presentationButton.addEventListener("click", () => setPresentationMode(true));
exitPresentationButton.addEventListener("click", () => setPresentationMode(false));
window.addEventListener("beforeprint", () => {
  document.querySelector(".map-legend").open = true;
  mapController.refresh();
});
mapController.onViewChange(updateViewActions);

nearbySearchButton.addEventListener("click", () => {
  clearAnalysis({ render: false });
  const radius = Number(nearbyRadius.value);
  const center = mapController.map.getCenter();
  const nearbyFeatures = featuresWithinRadius(allFeatures, center, radius);
  mapController.showNearbyRadius(radius);
  renderFeatureCollection(nearbyFeatures);
  clearAnalysisButton.hidden = false;
  analysisStatus.textContent = `${nearbyFeatures.length} assets within ${radius} miles`;
});

selectAreaButton.addEventListener("click", () => {
  clearAnalysis();
  analysisStatus.textContent = "Drawing selection";
  mapAnalysisDetails.open = false;
  mapController.beginAreaSelection(applyAreaSelection);
});

selectExtentButton.addEventListener("click", () => {
  clearAnalysis();
  mapController.selectVisibleExtent(applyAreaSelection);
});

exportAreaButton.addEventListener("click", () => {
  if (!selectedAreaFeatures.length) return;
  downloadFeatureCsv(selectedAreaFeatures, "cosolve-selected-assets.csv");
});

clearAnalysisButton.addEventListener("click", () => clearAnalysis());
showRegionSummaryButton.addEventListener("click", () => {
  const option = summaryRegion.selectedOptions[0];
  renderRegionSummary(option.value, option.textContent);
});
mapController.onRegionSelect((properties) => {
  summaryRegion.value = properties.region_slug;
  renderRegionSummary(properties.region_slug, properties.region_name);
});
closeInsightButton.addEventListener("click", () => {
  insightPanel.hidden = true;
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (document.body.classList.contains("presentation-mode")) {
    setPresentationMode(false);
  }
});

async function syncLayerVisibility() {
  mapController.setAssetLayerVisible(assetLayerToggle.checked);
  mapController.setStateBoundaryVisible(stateBoundaryToggle.checked);
  mapController.setVerificationLayerVisible(verificationLayerToggle.checked);
  mapController.setPrecisionLayerVisible(precisionLayerToggle.checked);
  verificationLegend.hidden = !verificationLayerToggle.checked;
  precisionLegend.hidden = !precisionLayerToggle.checked;
  mapController.setBasemap(selectedBasemap());
  await Promise.all([
    updateRegionLayer(),
    updateMpzLayer(),
    updateCountyLayer(),
    updateRelationshipLayer(),
  ]);
}

async function load(params, { changeUrl = true, viewState = null } = {}) {
  const requestId = ++loadRequestId;
  const requestedFilterParams = filterParamsFromMapUrl(params);
  activeFilterParams = requestedFilterParams;
  clearAnalysis({ render: false });
  insightPanel.hidden = true;
  showStatus("Loading public asset listings...");
  try {
    const data = await fetchAssets(requestedFilterParams);
    if (requestId !== loadRequestId) return;
    allFeatures = data.features;
    fullResultCount = data.result_count;
    renderFeatureCollection(data.features, {
      fit: true,
      resultCount: data.result_count,
      showSearchLabels: Boolean(requestedFilterParams.get("q")?.trim()),
    });
    mapController.setViewState(viewState);
    directoryLink.href = requestedFilterParams.toString()
      ? `/directory/?${requestedFilterParams}`
      : "/directory/";
    if (exportLink) {
      exportLink.href = requestedFilterParams.toString()
        ? `/admin/imports/export/?${requestedFilterParams}`
        : "/admin/imports/export/";
    }
    showStatus(
      data.truncated
        ? `Showing ${data.returned_count} of ${data.result_count} matching assets. Narrow the filters to see every result.`
        : "",
    );
    if (changeUrl) {
      updateUrl(requestedFilterParams);
      closeDrawer();
    }
  } catch (error) {
    if (requestId !== loadRequestId) return;
    showStatus("The map data could not be loaded. The directory remains available.");
    list.replaceChildren();
    console.error(error);
  }
}

hydrateForm(form, initialFilterParams);
updateFilterIndicators();
syncLayerVisibility();
load(initialFilterParams, { changeUrl: false, viewState: initialMapState });

form.addEventListener("submit", (event) => {
  event.preventDefault();
  load(paramsFromForm(form));
});
form.addEventListener("reset", () => {
  window.setTimeout(() => {
    updateFilterIndicators();
    load(new URLSearchParams());
  }, 0);
});
window.addEventListener("popstate", () => {
  const pageParams = new URLSearchParams(window.location.search);
  const filters = filterParamsFromMapUrl(pageParams);
  const viewState = mapStateFromParams(pageParams);
  applyLayerToggleState(viewState);
  syncLayerVisibility();
  hydrateForm(form, filters);
  updateFilterIndicators();
  load(filters, { changeUrl: false, viewState });
});
