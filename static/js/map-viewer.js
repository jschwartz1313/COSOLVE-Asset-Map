import { fetchAssets } from "./api.js?v=20260727";
import { bindFilterDrawer, bindFilterIndicators } from "./filters.js?v=20260722-3";
import { createMap } from "./map.js?v=20260729-6";
import {
  filterParamsFromMapUrl,
  mapStateFromParams,
  paramsWithMapState,
} from "./map-state.js?v=20260729-2";
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
const viewActionStatus = document.querySelector("#view-action-status");
const printMapSummary = document.querySelector("#print-map-summary");
const assetLayerToggle = document.querySelector("#asset-layer-toggle");
const countyLayerToggle = document.querySelector("#county-layer-toggle");
const regionLayerToggle = document.querySelector("#region-layer-toggle");
const mpzLayerToggle = document.querySelector("#mpz-layer-toggle");
const stateBoundaryToggle = document.querySelector("#state-boundary-toggle");
const initialPageParams = new URLSearchParams(window.location.search);
const initialMapState = mapStateFromParams(initialPageParams);
const initialFilterParams = filterParamsFromMapUrl(initialPageParams);
const defaultVisibleLayers = ["assets", "state"];

function applyLayerToggleState(state) {
  const layers = state?.layers || defaultVisibleLayers;
  assetLayerToggle.checked = layers.includes("assets");
  stateBoundaryToggle.checked = layers.includes("state");
  regionLayerToggle.checked = layers.includes("regions");
  mpzLayerToggle.checked = layers.includes("mpz");
  countyLayerToggle.checked = layers.includes("counties");
}

applyLayerToggleState(initialMapState);
const mapController = createMap(root);
const closeDrawer = bindFilterDrawer(root);
const updateFilterIndicators = bindFilterIndicators(form);
let activeFilterParams = initialFilterParams;
document.querySelector("#reset-view").addEventListener("click", () => mapController.reset());
assetLayerToggle.addEventListener("change", () => {
  mapController.setAssetLayerVisible(assetLayerToggle.checked);
  updateViewActions();
});
stateBoundaryToggle.addEventListener("change", () => {
  mapController.setStateBoundaryVisible(stateBoundaryToggle.checked);
  updateViewActions();
});

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

function showStatus(message) {
  status.textContent = message;
  status.hidden = !message;
}

function currentMapParams() {
  const center = mapController.getViewState();
  const layers = [];
  if (assetLayerToggle.checked) layers.push("assets");
  if (stateBoundaryToggle.checked) layers.push("state");
  if (regionLayerToggle.checked) layers.push("regions");
  if (mpzLayerToggle.checked) layers.push("mpz");
  if (countyLayerToggle.checked) layers.push("counties");
  return paramsWithMapState(activeFilterParams, { ...center, layers });
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

copyViewButton.addEventListener("click", copyCurrentView);
printViewButton.addEventListener("click", () => window.print());
window.addEventListener("beforeprint", () => {
  document.querySelector(".map-legend").open = true;
  mapController.refresh();
});
mapController.onViewChange(updateViewActions);

async function syncLayerVisibility() {
  mapController.setAssetLayerVisible(assetLayerToggle.checked);
  mapController.setStateBoundaryVisible(stateBoundaryToggle.checked);
  await Promise.all([updateRegionLayer(), updateMpzLayer(), updateCountyLayer()]);
}

async function load(params, { changeUrl = true, viewState = null } = {}) {
  activeFilterParams = filterParamsFromMapUrl(params);
  showStatus("Loading public asset listings...");
  try {
    const data = await fetchAssets(activeFilterParams);
    const selectOnMap = (id) => {
      mapController.select(id);
      selectResult(list, id);
    };
    mapController.draw(data.features, (id) => selectResult(list, id), {
      showLabels: Boolean(activeFilterParams.get("q")?.trim()),
    });
    mapController.setViewState(viewState);
    renderResults(list, data.features, selectOnMap);
    count.textContent = String(data.result_count);
    directoryLink.href = activeFilterParams.toString()
      ? `/directory/?${activeFilterParams}`
      : "/directory/";
    if (exportLink) {
      exportLink.href = activeFilterParams.toString()
        ? `/admin/imports/export/?${activeFilterParams}`
        : "/admin/imports/export/";
    }
    updateViewActions();
    showStatus(
      data.truncated
        ? `Showing ${data.returned_count} of ${data.result_count} matching assets. Narrow the filters to see every result.`
        : "",
    );
    if (changeUrl) updateUrl(activeFilterParams);
    closeDrawer();
  } catch (error) {
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
