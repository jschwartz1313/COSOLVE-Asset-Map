import { fetchAssets } from "./api.js?v=20260731";
import {
  bindFilterDrawer,
  bindFilterIndicators,
  withoutFilterValue,
} from "./filters.js?v=20260805-1";
import {
  downloadFeatureCsv,
  featuresWithinBounds,
  featuresWithinPolygon,
  featuresWithinRadius,
  summarizeRegion,
} from "./map-analysis.js?v=20260730-2";
import { createMap } from "./map.js?v=20260806-1";
import {
  analysisStateFromParams,
  filterParamsFromMapUrl,
  mapStateFromParams,
  paramsWithMapState,
  serializePolygonAnalysis,
  serializeRectangleAnalysis,
} from "./map-state.js?v=20260806-1";
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
const printReportTitle = document.querySelector("#print-report-title");
const printReportContext = document.querySelector("#print-report-context");
const printReportRows = document.querySelector("#print-report-rows");
const assetLayerToggle = document.querySelector("#asset-layer-toggle");
const countyLayerToggle = document.querySelector("#county-layer-toggle");
const regionLayerToggle = document.querySelector("#region-layer-toggle");
const mpzLayerToggle = document.querySelector("#mpz-layer-toggle");
const heliportLayerToggle = document.querySelector("#heliport-layer-toggle");
const stateBoundaryToggle = document.querySelector("#state-boundary-toggle");
const verificationLayerToggle = document.querySelector("#verification-layer-toggle");
const precisionLayerToggle = document.querySelector("#precision-layer-toggle");
const basemapInputs = [...document.querySelectorAll('input[name="map-basemap"]')];
const verificationLegend = document.querySelector("[data-verification-legend]");
const precisionLegend = document.querySelector("[data-precision-legend]");
const nearbyRadius = document.querySelector("#nearby-radius");
const nearbySearchButton = document.querySelector("#nearby-search");
const selectAreaButton = document.querySelector("#select-area");
const selectPolygonButton = document.querySelector("#select-polygon");
const finishPolygonButton = document.querySelector("#finish-polygon");
const cancelPolygonButton = document.querySelector("#cancel-polygon");
const selectExtentButton = document.querySelector("#select-extent");
const exportAreaButton = document.querySelector("#export-area");
const clearAnalysisButton = document.querySelector("#clear-analysis");
const analysisStatus = document.querySelector("#analysis-status");
const summaryRegion = document.querySelector("#summary-region");
const showRegionSummaryButton = document.querySelector("#show-region-summary");
const mapAnalysisDetails = document.querySelector(".map-analysis");
const activeFilterBar = document.querySelector("[data-active-filter-bar]");
const activeFilterChips = document.querySelector("[data-active-filter-chips]");
const activeFilterCount = document.querySelector("[data-applied-filter-count]");
const toolbarFilterCount = document.querySelector("[data-toolbar-filter-count]");
const clearActiveFiltersButton = document.querySelector("[data-clear-active-filters]");
const resultsPanel = document.querySelector("#map-results-panel");
const assetResultsView = document.querySelector("#asset-results-view");
const assetResultsTitle = document.querySelector("#asset-results-title");
const insightPanel = document.querySelector("#map-insight-panel");
const insightTitle = document.querySelector("#map-insight-title");
const insightContent = document.querySelector("#map-insight-content");
const closeInsightButton = document.querySelector("#close-map-insight");
const initialPageParams = new URLSearchParams(window.location.search);
const initialMapState = mapStateFromParams(initialPageParams);
const initialAnalysisState = analysisStateFromParams(initialPageParams);
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
  heliportLayerToggle.checked = layers.includes("heliports");
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
let analysisFeatures = [];
let analysisActive = false;
let analysisDefinition = null;
let polygonDrawing = false;
let loadRequestId = 0;

function showStatus(message) {
  status.textContent = message;
  status.hidden = !message;
}

function setPolygonDrawing(active) {
  polygonDrawing = active;
  finishPolygonButton.hidden = !active;
  cancelPolygonButton.hidden = !active;
  selectAreaButton.hidden = active;
  selectPolygonButton.hidden = active;
  selectExtentButton.hidden = active;
}

function currentLayers() {
  const layers = [];
  if (assetLayerToggle.checked) layers.push("assets");
  if (stateBoundaryToggle.checked) layers.push("state");
  if (regionLayerToggle.checked) layers.push("regions");
  if (mpzLayerToggle.checked) layers.push("mpz");
  if (countyLayerToggle.checked) layers.push("counties");
  if (heliportLayerToggle.checked) layers.push("heliports");
  if (verificationLayerToggle.checked) layers.push("verification");
  if (precisionLayerToggle.checked) layers.push("precision");
  return layers;
}

function currentMapParams() {
  const center = mapController.getViewState();
  return paramsWithMapState(activeFilterParams, {
    ...center,
    basemap: selectedBasemap(),
    layers: currentLayers(),
    analysis: analysisDefinition?.serialized || "",
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
  if (exportLink) {
    if (analysisActive) {
      exportLink.href = "#";
      exportLink.textContent = `Export ${analysisFeatures.length} selected`;
      exportLink.setAttribute(
        "aria-label",
        `Export ${analysisFeatures.length} selected assets as CSV`,
      );
      exportLink.setAttribute("aria-disabled", String(analysisFeatures.length === 0));
    } else {
      exportLink.href = activeFilterParams.toString()
        ? `/admin/imports/export/?${activeFilterParams}`
        : "/admin/imports/export/";
      exportLink.textContent = "Export CSV";
      exportLink.removeAttribute("aria-label");
      exportLink.removeAttribute("aria-disabled");
    }
  }
  if (printMapSummary) {
    const filterState = activeFilterParams.toString() ? "Filtered view" : "Statewide view";
    printMapSummary.textContent = `${filterState} · ${count.textContent || "0"} assets · ${new Date().toLocaleDateString()}`;
  }
}

function showAssetResults({ focus = false } = {}) {
  assetResultsView.hidden = false;
  insightPanel.hidden = true;
  resultsPanel.setAttribute("aria-label", "Filtered assets");
  if (focus) assetResultsTitle.focus();
}

function renderFeatureCollection(
  features,
  { fit = false, resultCount = features.length, showSearchLabels = false } = {},
) {
  showAssetResults();
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
  analysisFeatures = [];
  analysisActive = false;
  analysisDefinition = null;
  setPolygonDrawing(false);
  exportAreaButton.disabled = true;
  clearAnalysisButton.hidden = true;
  analysisStatus.textContent = "";
  if (render && allFeatures.length) {
    renderFeatureCollection(allFeatures, {
      resultCount: fullResultCount,
      showSearchLabels: Boolean(activeFilterParams.get("q")?.trim()),
    });
  } else {
    updateViewActions();
  }
}

function applyAnalysisSelection(features, definition = null) {
  analysisFeatures = features;
  analysisActive = true;
  analysisDefinition = definition;
  renderFeatureCollection(analysisFeatures);
  exportAreaButton.disabled = analysisFeatures.length === 0;
  clearAnalysisButton.hidden = false;
  analysisStatus.textContent = `${analysisFeatures.length} assets selected`;
}

function applyAreaSelection(bounds) {
  applyAnalysisSelection(featuresWithinBounds(allFeatures, bounds), {
    type: "rectangle",
    label: "Drawn rectangle",
    serialized: serializeRectangleAnalysis(bounds),
  });
}

function applyPolygonSelection(vertices) {
  setPolygonDrawing(false);
  mapAnalysisDetails.open = false;
  applyAnalysisSelection(featuresWithinPolygon(allFeatures, vertices), {
    type: "polygon",
    label: "Drawn polygon",
    serialized: serializePolygonAnalysis(vertices),
  });
}

function restoreAnalysis(state) {
  if (state?.type === "rectangle") {
    mapController.showAreaSelection(state.bounds);
    applyAnalysisSelection(featuresWithinBounds(allFeatures, state.bounds), {
      type: state.type,
      label: "Saved rectangle",
      serialized: serializeRectangleAnalysis(state.bounds),
    });
  } else if (state?.type === "polygon") {
    mapController.showPolygonSelection(state.vertices);
    applyAnalysisSelection(featuresWithinPolygon(allFeatures, state.vertices), {
      type: state.type,
      label: "Saved polygon",
      serialized: serializePolygonAnalysis(state.vertices),
    });
  }
}

function filterDescription(key, value) {
  const fields = [...form.querySelectorAll(`[name="${CSS.escape(key)}"]`)];
  const field = fields.find((candidate) => candidate.value === value) || fields[0];
  const fallbackLabel = key.replaceAll("_", " ");
  if (!field) return `${fallbackLabel}: ${value}`;

  if (field.type === "checkbox" || field.type === "radio") {
    const details = field.closest("details");
    const summary = details?.querySelector(":scope > summary");
    const groupLabel = summary?.childNodes[0]?.textContent?.trim() || fallbackLabel;
    const valueLabel = field.closest("label")?.querySelector("span")?.textContent?.trim() || value;
    return `${groupLabel}: ${valueLabel}`;
  }

  const groupLabel = field.closest("label")?.querySelector(":scope > span")?.textContent?.trim()
    || fallbackLabel;
  const displayValue = field.tagName === "SELECT"
    ? [...field.options].find((option) => option.value === value)?.textContent || value
    : value;
  return `${groupLabel}: ${displayValue}`;
}

function renderActiveFilters() {
  const entries = [...activeFilterParams];
  activeFilterBar.hidden = entries.length === 0;
  activeFilterCount.textContent = String(entries.length);
  toolbarFilterCount.textContent = String(entries.length);
  toolbarFilterCount.hidden = entries.length === 0;
  activeFilterChips.replaceChildren();

  for (const [key, value] of entries) {
    const description = filterDescription(key, value);
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "active-filter-chip";
    chip.setAttribute("aria-label", `Remove ${description} filter`);
    chip.append(document.createTextNode(description));
    const removeIcon = document.createElement("span");
    removeIcon.setAttribute("aria-hidden", "true");
    removeIcon.textContent = "×";
    chip.append(removeIcon);
    chip.addEventListener("click", () => {
      const next = withoutFilterValue(activeFilterParams, key, value);
      hydrateForm(form, next);
      updateFilterIndicators();
      load(next);
    });
    activeFilterChips.append(chip);
  }
}

function selectedFilterSummary() {
  if (!activeFilterParams.toString()) return "No catalog filters applied";
  return [...activeFilterParams]
    .map(([key, value]) => filterDescription(key, value))
    .join(" · ");
}

function populatePrintReport() {
  const features = analysisActive ? analysisFeatures : allFeatures;
  printReportTitle.textContent = analysisActive
    ? `${analysisDefinition?.label || "Selected area"} asset report`
    : "Current map asset report";
  printReportContext.textContent = `${selectedFilterSummary()} · ${features.length} assets · Generated ${new Date().toLocaleString()}`;
  printReportRows.replaceChildren();
  for (const feature of features) {
    const row = document.createElement("tr");
    for (const value of [
      feature.properties.name,
      feature.properties.record_type_label,
      feature.properties.location.region || "Unassigned",
      feature.properties.location.precision_label,
      feature.properties.verification_state_label,
    ]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    printReportRows.append(row);
  }
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
  assetResultsView.hidden = true;
  insightPanel.hidden = false;
  resultsPanel.setAttribute("aria-label", `${regionName} regional summary`);
  insightContent.scrollTop = 0;
  closeInsightButton.focus();
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

async function updateHeliportLayer() {
  heliportLayerToggle.disabled = true;
  try {
    await mapController.setHeliportLayerVisible(heliportLayerToggle.checked);
  } catch (error) {
    heliportLayerToggle.checked = false;
    showStatus("FAA heliport reference points could not be loaded.");
    console.error(error);
  } finally {
    heliportLayerToggle.disabled = false;
    updateViewActions();
  }
}

heliportLayerToggle.addEventListener("change", updateHeliportLayer);

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
printViewButton.addEventListener("click", () => {
  populatePrintReport();
  window.print();
});
presentationButton.addEventListener("click", () => setPresentationMode(true));
exitPresentationButton.addEventListener("click", () => setPresentationMode(false));
window.addEventListener("beforeprint", () => {
  populatePrintReport();
  document.querySelector(".map-legend").open = true;
  mapController.refresh();
});
mapController.onViewChange(updateViewActions);

nearbySearchButton.addEventListener("click", () => {
  clearAnalysis({ render: false });
  const radius = Number(nearbyRadius.value);
  const center = mapController.map.getCenter();
  const nearbyFeatures = featuresWithinRadius(allFeatures, center, radius);
  analysisFeatures = nearbyFeatures;
  analysisActive = true;
  analysisDefinition = {
    type: "radius",
    label: `${radius}-mile radius from map center`,
    serialized: "",
  };
  mapController.showNearbyRadius(radius);
  renderFeatureCollection(nearbyFeatures);
  exportAreaButton.disabled = nearbyFeatures.length === 0;
  clearAnalysisButton.hidden = false;
  analysisStatus.textContent = `${nearbyFeatures.length} assets within ${radius} miles`;
});

selectAreaButton.addEventListener("click", () => {
  clearAnalysis();
  analysisStatus.textContent = "Drawing selection";
  mapAnalysisDetails.open = false;
  mapController.beginAreaSelection(applyAreaSelection);
});

selectPolygonButton.addEventListener("click", () => {
  clearAnalysis();
  setPolygonDrawing(true);
  analysisStatus.textContent = "Drawing polygon";
  mapController.beginPolygonSelection(applyPolygonSelection);
});

finishPolygonButton.addEventListener("click", () => {
  if (!mapController.finishPolygonSelection()) {
    analysisStatus.textContent = "Polygon needs at least 3 points";
  }
});

cancelPolygonButton.addEventListener("click", () => {
  mapController.cancelSelection();
  clearAnalysis();
});

selectExtentButton.addEventListener("click", () => {
  clearAnalysis();
  mapController.selectVisibleExtent(applyAreaSelection);
});

exportAreaButton.addEventListener("click", () => {
  if (!analysisFeatures.length) return;
  downloadFeatureCsv(analysisFeatures, "cosolve-selected-assets.csv");
});
exportLink?.addEventListener("click", (event) => {
  if (!analysisActive) return;
  event.preventDefault();
  if (!analysisFeatures.length) return;
  downloadFeatureCsv(analysisFeatures, "cosolve-selected-assets.csv");
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
  showAssetResults({ focus: true });
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (polygonDrawing) {
    mapController.cancelSelection();
    clearAnalysis();
  } else if (document.body.classList.contains("presentation-mode")) {
    setPresentationMode(false);
  } else if (!insightPanel.hidden) {
    showAssetResults({ focus: true });
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
    updateHeliportLayer(),
  ]);
}

async function load(
  params,
  { changeUrl = true, viewState = null, analysisState = null } = {},
) {
  const requestId = ++loadRequestId;
  const requestedFilterParams = filterParamsFromMapUrl(params);
  activeFilterParams = requestedFilterParams;
  renderActiveFilters();
  clearAnalysis({ render: false });
  showAssetResults();
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
    restoreAnalysis(analysisState);
    directoryLink.href = requestedFilterParams.toString()
      ? `/directory/?${requestedFilterParams}`
      : "/directory/";
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
load(initialFilterParams, {
  changeUrl: false,
  viewState: initialMapState,
  analysisState: initialAnalysisState,
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  load(paramsFromForm(form));
});
form.addEventListener("reset", (event) => {
  event.preventDefault();
  const emptyFilters = new URLSearchParams();
  hydrateForm(form, emptyFilters);
  for (const details of form.querySelectorAll("details")) details.open = false;
  updateFilterIndicators();
  load(emptyFilters);
});
clearActiveFiltersButton.addEventListener("click", () => {
  const emptyFilters = new URLSearchParams();
  hydrateForm(form, emptyFilters);
  for (const details of form.querySelectorAll("details")) details.open = false;
  updateFilterIndicators();
  load(emptyFilters);
});
window.addEventListener("popstate", () => {
  const pageParams = new URLSearchParams(window.location.search);
  const filters = filterParamsFromMapUrl(pageParams);
  const viewState = mapStateFromParams(pageParams);
  const analysisState = analysisStateFromParams(pageParams);
  applyLayerToggleState(viewState);
  syncLayerVisibility();
  hydrateForm(form, filters);
  updateFilterIndicators();
  load(filters, { changeUrl: false, viewState, analysisState });
});
