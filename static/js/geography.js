export function inventoryPrefix() {
  const prefix = typeof document === "undefined" ? "" : document.body?.dataset.sitePrefix || "";
  return /^\/states\/[a-z]+(?:-[a-z]+)*$/.test(prefix) ? prefix : "";
}

export function sitePath(path) {
  return `${inventoryPrefix()}${path}`;
}
