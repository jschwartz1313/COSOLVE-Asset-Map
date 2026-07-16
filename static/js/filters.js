export function bindFilterDrawer(root) {
  const panel = root.querySelector(".filters-panel");
  root.querySelector(".filter-open")?.addEventListener("click", () => panel.classList.add("is-open"));
  root.querySelector(".filter-close")?.addEventListener("click", () => panel.classList.remove("is-open"));
  return () => panel.classList.remove("is-open");
}

