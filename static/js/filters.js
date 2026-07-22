export function bindFilterDrawer(root) {
  const panel = root.querySelector(".filters-panel");
  const openButton = root.querySelector(".filter-open");
  const closeButton = root.querySelector(".filter-close");
  const compactLayout = window.matchMedia("(max-width: 880px)");
  let isOpen = false;

  function syncAccessibility() {
    openButton?.setAttribute("aria-expanded", String(isOpen));
    if (compactLayout.matches) {
      if (isOpen) panel.removeAttribute("inert");
      else panel.setAttribute("inert", "");
      panel.setAttribute("aria-hidden", String(!isOpen));
    } else {
      panel.removeAttribute("inert");
      panel.removeAttribute("aria-hidden");
    }
  }

  function openDrawer() {
    isOpen = true;
    panel.classList.add("is-open");
    syncAccessibility();
    closeButton?.focus();
  }

  function closeDrawer({ restoreFocus = false } = {}) {
    isOpen = false;
    panel.classList.remove("is-open");
    syncAccessibility();
    if (restoreFocus && compactLayout.matches) openButton?.focus();
  }

  openButton?.addEventListener("click", openDrawer);
  closeButton?.addEventListener("click", () => closeDrawer({ restoreFocus: true }));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen) closeDrawer({ restoreFocus: true });
  });
  compactLayout.addEventListener("change", syncAccessibility);
  syncAccessibility();
  return closeDrawer;
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
