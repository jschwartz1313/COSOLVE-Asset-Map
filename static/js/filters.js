export function bindFilterDrawer(root) {
  const panel = root.querySelector(".filters-panel");
  root.querySelector(".filter-open")?.addEventListener("click", () => panel.classList.add("is-open"));
  root.querySelector(".filter-close")?.addEventListener("click", () => panel.classList.remove("is-open"));
  return () => panel.classList.remove("is-open");
}

export function bindFilterIndicators(form) {
  function update() {
    let activeCount = 0;
    for (const element of form.elements) {
      if (!element.name || ["submit", "reset"].includes(element.type)) continue;
      if (element.type === "checkbox") activeCount += Number(element.checked);
      else activeCount += Number(Boolean(element.value.trim()));
    }
    const activeBadge = form.querySelector("[data-active-filter-count]");
    if (activeBadge) {
      activeBadge.textContent = String(activeCount);
      activeBadge.hidden = activeCount === 0;
    }
    for (const badge of form.querySelectorAll("[data-filter-count-for]")) {
      const name = badge.dataset.filterCountFor;
      const count = form.querySelectorAll(`[name="${CSS.escape(name)}"]:checked`).length;
      badge.textContent = String(count);
      badge.hidden = count === 0;
      if (count) badge.closest("details").open = true;
    }
  }

  form.addEventListener("change", update);
  form.addEventListener("input", update);
  update();
  return update;
}
