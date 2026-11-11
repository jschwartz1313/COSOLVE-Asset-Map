const KEY = "cosolve-asset-comparison-v1";
const buttons = [...document.querySelectorAll("[data-compare-asset]")];
const tray = document.querySelector("[data-comparison-tray]");
let selected = [];
try {
  const stored = JSON.parse(localStorage.getItem(KEY) || "[]");
  if (Array.isArray(stored)) selected = [...new Set(stored.filter(value =>
    typeof value === "string" && /^[a-z0-9-]{1,240}$/.test(value)))].slice(0, 5);
} catch { /* Comparison still works when browser storage is unavailable. */ }

const serverSelection = document.getElementById("comparison-selection");
if (serverSelection) {
  const state = JSON.parse(serverSelection.textContent);
  if (state.explicit) {
    selected = state.slugs;
    try { localStorage.setItem(KEY, JSON.stringify(selected)); } catch { /* Storage is optional. */ }
  } else if (selected.length && !new URLSearchParams(location.search).has("q")) {
    const query = new URLSearchParams();
    selected.forEach(slug => query.append("asset", slug));
    location.replace(`/compare/?${query}`);
  }
}

function update() {
  buttons.forEach(button => {
    const added = selected.includes(button.dataset.compareAsset);
    if (button.matches('input[type="checkbox"]')) {
      button.checked = added;
      button.closest(".directory-row")?.classList.toggle("is-comparison-selected", added);
    } else {
      button.setAttribute("aria-pressed", String(added));
      button.textContent = added ? "Remove from comparison" : "Add to comparison";
    }
    button.disabled = !added && selected.length === 5;
    button.title = button.disabled ? "Five assets selected; remove one to select another"
      : added ? "Remove from comparison" : "Select for comparison";
  });
  if (tray) {
    if (tray.hasAttribute("data-hide-empty")) tray.hidden = selected.length === 0;
    tray.querySelector("[data-comparison-count]").textContent = `${selected.length} selected`;
    tray.querySelector("[data-comparison-status]").textContent = `${selected.length} of 5 assets selected for comparison`;
    tray.querySelector("[data-comparison-clear]").hidden = selected.length === 0;
    const query = new URLSearchParams();
    selected.forEach(slug => query.append("asset", slug));
    tray.querySelector("a").href = `/compare/?${query}`;
    tray.querySelector("a").textContent = selected.length ? "Compare selected assets" : "Compare assets";
  }
}
buttons.forEach(button => button.addEventListener("click", () => {
  const slug = button.dataset.compareAsset;
  if (selected.includes(slug)) selected = selected.filter(value => value !== slug);
  else if (selected.length < 5) selected.push(slug);
  else {
    if (tray) tray.querySelector("[data-comparison-status]").textContent = "Five assets selected. Remove one to add another.";
    return;
  }
  try { localStorage.setItem(KEY, JSON.stringify(selected)); } catch { /* Storage is optional. */ }
  update();
}));
tray?.querySelector("button")?.addEventListener("click", () => {
  selected = [];
  try { localStorage.removeItem(KEY); } catch { /* Storage is optional. */ }
  update();
});
update();
