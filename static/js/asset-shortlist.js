import { comparisonLabels, comparisonSlugs } from "./asset-comparison-state.js?v=20261111-3";

const KEY = "cosolve-asset-comparison-v1";
const controls = [...document.querySelectorAll("[data-compare-asset]")];
const tray = document.querySelector("[data-comparison-tray]");
const labels = new Map(controls.filter(control => control.dataset.compareName).map(control => [
  control.dataset.compareAsset,
  { name: control.dataset.compareName, url: `/assets/${control.dataset.compareAsset}/` },
]));
let selected = [];
let namesFailed = false;
let namesRequest;
let requestVersion = 0;
try {
  selected = comparisonSlugs(JSON.parse(localStorage.getItem(KEY) || "[]"));
} catch { /* Comparison still works when browser storage is unavailable. */ }

function saveSelection() {
  try { localStorage.setItem(KEY, JSON.stringify(selected)); } catch { /* Storage is optional. */ }
}

const serverSelection = document.getElementById("comparison-selection");
if (serverSelection) {
  const state = JSON.parse(serverSelection.textContent);
  if (state.explicit) {
    selected = comparisonSlugs(state.slugs);
    if (Array.isArray(state.assets)) {
      for (const [slug, label] of comparisonLabels(state, selected)) labels.set(slug, label);
    }
    saveSelection();
  } else if (selected.length && !new URLSearchParams(location.search).has("q")) {
    const query = new URLSearchParams();
    selected.forEach(slug => query.append("asset", slug));
    location.replace(`/compare/?${query}`);
  }
}

function renderNames() {
  const list = tray?.querySelector("[data-comparison-assets]");
  if (!list) return;
  list.hidden = selected.length === 0;
  for (const item of [...list.children]) {
    if (!selected.includes(item.dataset.slug)) item.remove();
  }
  selected.forEach((slug, index) => {
    let item = [...list.children].find(node => node.dataset.slug === slug);
    if (!item) {
      item = document.createElement("li");
      item.dataset.slug = slug;
      const name = document.createElement("a");
      name.dataset.comparisonName = "";
      const remove = document.createElement("button");
      remove.type = "button";
      remove.dataset.removeComparedAsset = slug;
      remove.textContent = "\u00d7";
      remove.addEventListener("click", () => {
        const position = selected.indexOf(slug);
        selected = selected.filter(value => value !== slug);
        changedSelection();
        const remaining = list.querySelectorAll("[data-remove-compared-asset]");
        (remaining[Math.min(position, remaining.length - 1)]
          || tray.querySelector("[data-comparison-open]")).focus({ preventScroll: true });
      });
      item.append(name, remove);
    }
    const label = labels.get(slug);
    const name = item.querySelector("[data-comparison-name]");
    name.textContent = label?.name || (namesFailed ? "Asset name unavailable" : "Loading asset name\u2026");
    if (label) name.href = label.url;
    else name.removeAttribute("href");
    const remove = item.querySelector("button");
    const description = `Remove ${label?.name || "selected asset"} from comparison`;
    remove.setAttribute("aria-label", description);
    remove.title = description;
    if (list.children[index] !== item) list.insertBefore(item, list.children[index] || null);
  });
}

function update() {
  controls.forEach(control => {
    const added = selected.includes(control.dataset.compareAsset);
    if (control.matches('input[type="checkbox"]')) {
      control.checked = added;
      control.closest(".directory-row")?.classList.toggle("is-comparison-selected", added);
    } else {
      control.setAttribute("aria-pressed", String(added));
      control.textContent = added ? "Remove from comparison" : "Add to comparison";
    }
    control.disabled = !added && selected.length === 5;
    control.title = control.disabled ? "Five assets selected; remove one to select another"
      : added ? "Remove from comparison" : "Select for comparison";
  });
  if (!tray) return;
  if (tray.hasAttribute("data-hide-empty")) tray.hidden = selected.length === 0;
  tray.querySelector("[data-comparison-count]").textContent = `${selected.length} selected`;
  tray.querySelector("[data-comparison-status]").textContent = `${selected.length} of 5 assets selected for comparison`;
  tray.querySelector("[data-comparison-clear]").hidden = selected.length === 0;
  tray.querySelector("[data-comparison-name-error]").hidden = !namesFailed;
  const query = new URLSearchParams();
  selected.forEach(slug => query.append("asset", slug));
  const open = tray.querySelector("[data-comparison-open]");
  open.href = `/compare/?${query}`;
  open.textContent = selected.length ? "Compare selected assets" : "Compare assets";
  renderNames();
}

async function resolveNames() {
  const version = ++requestVersion;
  namesRequest?.abort();
  namesFailed = false;
  const missing = selected.filter(slug => !labels.has(slug));
  update();
  if (!tray || !missing.length) return;
  namesRequest = new AbortController();
  const controller = namesRequest;
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 15000);
  const query = new URLSearchParams();
  missing.forEach(slug => query.append("asset", slug));
  try {
    const response = await fetch(`/compare/selection/?${query}`, {
      signal: controller.signal, headers: { Accept: "application/json" }, cache: "no-store",
    });
    if (!response.ok) throw new Error("Selected asset names unavailable");
    const found = comparisonLabels(await response.json(), missing);
    if (version !== requestVersion) return;
    for (const [slug, label] of found) labels.set(slug, label);
    const removed = missing.filter(slug => !found.has(slug));
    selected = selected.filter(slug => !removed.includes(slug));
    saveSelection();
    update();
    if (removed.length) tray.querySelector("[data-comparison-status]").textContent =
      `${removed.length} unavailable asset${removed.length === 1 ? " was" : "s were"} removed from comparison`;
  } catch (error) {
    if (version !== requestVersion || (error.name === "AbortError" && !timedOut)) return;
    namesFailed = true;
    update();
  } finally {
    clearTimeout(timeout);
  }
}

function changedSelection() {
  saveSelection();
  void resolveNames();
}

controls.forEach(control => control.addEventListener("click", () => {
  const slug = control.dataset.compareAsset;
  if (selected.includes(slug)) selected = selected.filter(value => value !== slug);
  else if (selected.length < 5) selected.push(slug);
  else return;
  changedSelection();
}));
tray?.querySelector("[data-comparison-clear]")?.addEventListener("click", () => {
  selected = [];
  changedSelection();
  tray.querySelector("[data-comparison-open]").focus({ preventScroll: true });
});
tray?.querySelector("[data-comparison-retry]")?.addEventListener("click", () => {
  void resolveNames();
  tray.querySelector("[data-comparison-open]").focus({ preventScroll: true });
});
function restoreSelection() {
  try { selected = comparisonSlugs(JSON.parse(localStorage.getItem(KEY) || "[]")); }
  catch { selected = []; }
  void resolveNames();
}
window.addEventListener("storage", event => {
  if (event.key !== KEY && event.key !== null) return;
  restoreSelection();
});
window.addEventListener("pageshow", event => {
  if (event.persisted) restoreSelection();
});
void resolveNames();
