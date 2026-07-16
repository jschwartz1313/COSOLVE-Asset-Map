import { fetchAssets } from "./api.js";
import { bindFilterDrawer } from "./filters.js";
import { createMap } from "./map.js";
import { renderResults, selectResult } from "./results.js";
import { hydrateForm, paramsFromForm, updateUrl } from "./state.js";

const root = document.querySelector("[data-map-app]");
const form = document.querySelector("#asset-filters");
const list = document.querySelector("#result-list");
const count = document.querySelector("#result-count");
const status = document.querySelector("#map-status");
const directoryLink = document.querySelector("#directory-link");
const mapController = createMap(root);
const closeDrawer = bindFilterDrawer(root);

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
    showStatus("");
    if (changeUrl) updateUrl(params);
    closeDrawer();
  } catch (error) {
    showStatus("The map data could not be loaded. The directory remains available.");
    list.replaceChildren();
    console.error(error);
  }
}

hydrateForm(form);
load(new URLSearchParams(window.location.search), { changeUrl: false });

form.addEventListener("submit", (event) => {
  event.preventDefault();
  load(paramsFromForm(form));
});
form.addEventListener("reset", () => {
  window.setTimeout(() => load(new URLSearchParams()), 0);
});
window.addEventListener("popstate", () => {
  const params = new URLSearchParams(window.location.search);
  hydrateForm(form, params);
  load(params, { changeUrl: false });
});

