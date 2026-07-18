import { fetchAssets } from "./api.js?v=20260717";
import { bindFilterDrawer, bindFilterIndicators } from "./filters.js?v=20260717";
import { createMap } from "./map.js?v=20260717-5";
import { renderResults, selectResult } from "./results.js?v=20260717";
import { hydrateForm, paramsFromForm, updateUrl } from "./state.js?v=20260717";

const root = document.querySelector("[data-map-app]");
const form = document.querySelector("#asset-filters");
const list = document.querySelector("#result-list");
const count = document.querySelector("#result-count");
const status = document.querySelector("#map-status");
const directoryLink = document.querySelector("#directory-link");
const exportLink = document.querySelector("#export-link");
const countyLayerToggle = document.querySelector("#county-layer-toggle");
const stateBoundaryToggle = document.querySelector("#state-boundary-toggle");
const mapController = createMap(root);
const closeDrawer = bindFilterDrawer(root);
const updateFilterIndicators = bindFilterIndicators(form);
document.querySelector("#reset-view").addEventListener("click", () => mapController.reset());
stateBoundaryToggle.addEventListener("change", () => {
  mapController.setStateBoundaryVisible(stateBoundaryToggle.checked);
});

countyLayerToggle.addEventListener("change", async () => {
  countyLayerToggle.disabled = true;
  try {
    await mapController.setCountyLayerVisible(countyLayerToggle.checked);
  } catch (error) {
    countyLayerToggle.checked = false;
    showStatus("County boundaries could not be loaded.");
    console.error(error);
  } finally {
    countyLayerToggle.disabled = false;
  }
});

function showStatus(message) {
  status.textContent = message;
  status.hidden = !message;
}

async function load(params, { changeUrl = true } = {}) {
  showStatus("Loading published assets...");
  try {
    const data = await fetchAssets(params);
    const selectOnMap = (id) => {
      mapController.select(id);
      selectResult(list, id);
    };
    mapController.draw(data.features, (id) => selectResult(list, id));
    renderResults(list, data.features, selectOnMap);
    count.textContent = String(data.result_count);
    directoryLink.href = params.toString() ? `/directory/?${params}` : "/directory/";
    if (exportLink) {
      exportLink.href = params.toString()
        ? `/admin/imports/export/?${params}`
        : "/admin/imports/export/";
    }
    showStatus(
      data.truncated
        ? `Showing ${data.returned_count} of ${data.result_count} matching assets. Narrow the filters to see every result.`
        : "",
    );
    if (changeUrl) updateUrl(params);
    closeDrawer();
  } catch (error) {
    showStatus("The map data could not be loaded. The directory remains available.");
    list.replaceChildren();
    console.error(error);
  }
}

hydrateForm(form);
updateFilterIndicators();
load(new URLSearchParams(window.location.search), { changeUrl: false });

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
  const params = new URLSearchParams(window.location.search);
  hydrateForm(form, params);
  updateFilterIndicators();
  load(params, { changeUrl: false });
});
