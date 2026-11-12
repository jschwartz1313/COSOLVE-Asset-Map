import { assetPickerPage, assetPickerQuery } from "./asset-picker-state.js?v=20261112-1";

const dialog = document.querySelector("[data-asset-picker]");
const opener = document.querySelector("[data-open-asset-picker]");
const state = document.getElementById("comparison-selection");

if (dialog && opener && state && typeof dialog.showModal === "function") {
  initializePicker();
}

function initializePicker() {
  const initial = JSON.parse(state.textContent);
  const existing = new Set(initial.slugs);
  const draft = new Map();
  const form = dialog.querySelector("[data-picker-form]");
  const search = form.elements.q;
  const fallbackSearch = document.querySelector("[data-picker-fallback] input[name=q]");
  const continueTyping = fallbackSearch === document.activeElement;
  if (fallbackSearch) search.value = fallbackSearch.value;
  const options = dialog.querySelector("[data-picker-options]");
  const status = dialog.querySelector("[data-picker-status]");
  const error = dialog.querySelector("[data-picker-error]");
  const previous = dialog.querySelector("[data-picker-previous]");
  const next = dialog.querySelector("[data-picker-next]");
  const confirm = dialog.querySelector("[data-picker-confirm]");
  const draftSection = dialog.querySelector("[data-picker-draft]");
  const draftList = draftSection.querySelector("ul");
  let currentPage = 1;
  let pages = 1;
  let requestedPage = 1;
  let request;
  let requestVersion = 0;
  let debounce;
  let renderedDraft;

  function renderDraft() {
    const signature = JSON.stringify([...draft]);
    if (signature === renderedDraft) return;
    renderedDraft = signature;
    draftSection.hidden = draft.size === 0;
    draftList.replaceChildren();
    for (const [slug, name] of draft) {
      const item = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = name;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "\u00d7";
      remove.setAttribute("aria-label", `Remove ${name} from selection`);
      remove.title = `Remove ${name} from selection`;
      remove.addEventListener("click", () => {
        const index = [...draft.keys()].indexOf(slug);
        draft.delete(slug);
        updateSelection();
        const remaining = draftList.querySelectorAll("button");
        (remaining[Math.min(index, remaining.length - 1)] || search).focus();
      });
      item.append(label, remove);
      draftList.append(item);
    }
  }

  function updateSelection() {
    const count = existing.size + draft.size;
    dialog.querySelector("[data-picker-count]").textContent = `${count} of 5 selected`;
    confirm.disabled = draft.size === 0;
    confirm.textContent = draft.size ? `Add selected assets (${draft.size})` : "Add selected assets";
    for (const input of options.querySelectorAll("input[type=checkbox]")) {
      const present = existing.has(input.value);
      input.checked = present || draft.has(input.value);
      input.disabled = present || (count >= 5 && !draft.has(input.value));
      input.closest("label").classList.toggle("is-selected", input.checked);
    }
    renderDraft();
  }

  function renderOptions(assets) {
    const fragment = document.createDocumentFragment();
    for (const asset of assets) {
      const row = document.createElement("label");
      row.className = "asset-picker-option";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = asset.slug;
      input.setAttribute("aria-label", asset.name);
      const content = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = asset.name;
      const meta = document.createElement("small");
      meta.id = `picker-meta-${asset.slug}`;
      meta.textContent = `${asset.record_type_label} \u00b7 ${asset.location}`;
      input.setAttribute("aria-describedby", meta.id);
      content.append(name, meta);
      if (existing.has(asset.slug)) {
        row.classList.add("is-existing");
        const selected = document.createElement("small");
        selected.textContent = "Already compared";
        content.append(selected);
      }
      input.addEventListener("change", () => {
        if (existing.has(asset.slug)) return;
        if (input.checked && existing.size + draft.size < 5) draft.set(asset.slug, asset.name);
        else draft.delete(asset.slug);
        updateSelection();
      });
      row.append(input, content);
      fragment.append(row);
    }
    options.replaceChildren(fragment);
    updateSelection();
  }

  async function loadPage(number = 1) {
    clearTimeout(debounce);
    request?.abort();
    const version = ++requestVersion;
    const controller = new AbortController();
    request = controller;
    requestedPage = number;
    const query = new URLSearchParams(new FormData(form));
    query.set("page", number);
    error.hidden = true;
    status.textContent = "Loading assets\u2026";
    options.replaceChildren();
    options.setAttribute("aria-busy", "true");
    previous.disabled = next.disabled = true;
    dialog.querySelector("[data-picker-page]").textContent = "";
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 15000);
    try {
      const response = await fetch(`/compare/options/?${query}`, {
        signal: controller.signal, cache: "no-store", headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("Asset list unavailable");
      const result = assetPickerPage(await response.json());
      if (version !== requestVersion || !dialog.open) return;
      currentPage = result.page;
      pages = result.pages;
      status.textContent = result.count ? `${result.count} matching asset${result.count === 1 ? "" : "s"}`
        : "No matching assets";
      renderOptions(result.assets);
      previous.disabled = currentPage <= 1;
      next.disabled = currentPage >= pages;
      dialog.querySelector("[data-picker-page]").textContent = `Page ${currentPage} of ${pages}`;
    } catch (failure) {
      if (version !== requestVersion || !dialog.open
        || (failure.name === "AbortError" && !timedOut)) return;
      status.textContent = "";
      error.hidden = false;
    } finally {
      clearTimeout(timeout);
      if (version === requestVersion) options.setAttribute("aria-busy", "false");
    }
  }

  opener.addEventListener("click", () => {
    draft.clear();
    renderedDraft = undefined;
    updateSelection();
    dialog.showModal();
    document.body.classList.add("has-asset-picker");
    search.focus();
    void loadPage(1);
  });
  dialog.querySelectorAll("[data-picker-cancel]").forEach(button => {
    button.addEventListener("click", () => dialog.close());
  });
  dialog.addEventListener("click", event => {
    const rect = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right
      || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
  });
  dialog.addEventListener("close", () => {
    ++requestVersion;
    request?.abort();
    clearTimeout(debounce);
    document.body.classList.remove("has-asset-picker");
    opener.focus({ preventScroll: true });
  });
  dialog.addEventListener("keydown", event => {
    if (event.key !== "Tab") return;
    const focusable = [...dialog.querySelectorAll("button,input,select,a[href],[tabindex='0']")]
      .filter(element => !element.disabled && element.getClientRects().length);
    const first = focusable[0];
    const last = focusable.at(-1);
    if (!first) return;
    const outside = !dialog.contains(document.activeElement) || document.activeElement === dialog;
    if (event.shiftKey && (document.activeElement === first || outside)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (document.activeElement === last || outside)) {
      event.preventDefault();
      first.focus();
    }
  });
  form.addEventListener("submit", event => { event.preventDefault(); void loadPage(1); });
  search.addEventListener("input", () => {
    clearTimeout(debounce);
    // Invalidate old results immediately; typing must not select a stale match.
    ++requestVersion;
    request?.abort();
    options.replaceChildren();
    options.setAttribute("aria-busy", "true");
    error.hidden = true;
    status.textContent = "Loading assets\u2026";
    dialog.querySelector("[data-picker-page]").textContent = "";
    previous.disabled = next.disabled = true;
    debounce = setTimeout(() => void loadPage(1), 250);
  });
  for (const select of form.querySelectorAll("select")) {
    select.addEventListener("change", () => void loadPage(1));
  }
  form.addEventListener("reset", event => {
    event.preventDefault();
    search.value = form.elements.record_type.value = form.elements.region.value = "";
    void loadPage(1);
    search.focus();
  });
  previous.addEventListener("click", () => void loadPage(currentPage - 1));
  next.addEventListener("click", () => void loadPage(currentPage + 1));
  dialog.querySelector("[data-picker-retry]").addEventListener("click", () => void loadPage(requestedPage));
  confirm.addEventListener("click", () => {
    if (!draft.size) return;
    confirm.disabled = true;
    location.assign(`/compare/?${assetPickerQuery([...existing], [...draft.keys()])}`);
  });
  document.querySelectorAll("[data-picker-fallback]").forEach(element => { element.hidden = true; });
  opener.disabled = existing.size >= 5;
  opener.title = opener.disabled ? "Remove an asset to add another" : "Add assets to comparison";
  opener.hidden = false;
  if (!opener.disabled && (continueTyping || (initial && new URLSearchParams(location.search).get("q")))) {
    opener.click();
  }
}
