const FACETS = ["q", "record_type", "region", "category", "domain", "capability", "mission"];

export function paramsFromForm(form) {
  const params = new URLSearchParams();
  const formData = new FormData(form);
  for (const facet of FACETS) {
    for (const value of formData.getAll(facet)) {
      if (String(value).trim()) params.append(facet, String(value).trim());
    }
  }
  return params;
}

export function hydrateForm(form, params = new URLSearchParams(window.location.search)) {
  for (const element of form.elements) {
    if (!element.name) continue;
    const values = params.getAll(element.name);
    if (element.type === "checkbox") element.checked = values.includes(element.value);
    else if (element.type !== "submit" && element.type !== "reset") element.value = values[0] || "";
  }
}

export function updateUrl(params, { replace = false } = {}) {
  const url = params.toString() ? `${window.location.pathname}?${params}` : window.location.pathname;
  window.history[replace ? "replaceState" : "pushState"]({}, "", url);
}

