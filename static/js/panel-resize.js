export const PANEL_LAYOUT_STORAGE_KEY = "cosolve.map-panel-widths.v1";

const MIN_FILTER_WIDTH = 220;
const MAX_FILTER_WIDTH = 460;
const MIN_RESULTS_WIDTH = 260;
const MAX_RESULTS_WIDTH = 520;
const RESIZER_WIDTH = 1;
const STACKED_BREAKPOINT = 650;
const FILTER_DRAWER_BREAKPOINT = 880;
const COMPACT_MAP_BREAKPOINT = 1100;

function clamp(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), Math.max(minimum, maximum));
}

function minimumMapWidth(containerWidth) {
  return containerWidth <= COMPACT_MAP_BREAKPOINT ? 320 : 360;
}

export function constrainPanelWidths({ containerWidth, leftWidth, rightWidth }) {
  const leftVisible = containerWidth > FILTER_DRAWER_BREAKPOINT;
  const resizerCount = leftVisible ? 2 : 1;
  const availableForPanels = Math.max(
    0,
    containerWidth - minimumMapWidth(containerWidth) - (RESIZER_WIDTH * resizerCount),
  );
  let left = clamp(leftWidth, MIN_FILTER_WIDTH, MAX_FILTER_WIDTH);
  let right = clamp(
    rightWidth,
    MIN_RESULTS_WIDTH,
    Math.min(MAX_RESULTS_WIDTH, availableForPanels - (leftVisible ? MIN_FILTER_WIDTH : 0)),
  );

  if (leftVisible) {
    left = clamp(
      left,
      MIN_FILTER_WIDTH,
      Math.min(MAX_FILTER_WIDTH, availableForPanels - MIN_RESULTS_WIDTH),
    );
    let overflow = Math.max(0, left + right - availableForPanels);
    const rightReduction = Math.min(overflow, right - MIN_RESULTS_WIDTH);
    right -= rightReduction;
    overflow -= rightReduction;
    left -= Math.min(overflow, left - MIN_FILTER_WIDTH);
  }

  return {
    left: Math.round(left),
    right: Math.round(right),
    leftVisible,
    resizable: containerWidth > STACKED_BREAKPOINT,
  };
}

function readStoredWidths() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PANEL_LAYOUT_STORAGE_KEY));
    if (Number.isFinite(parsed?.left) && Number.isFinite(parsed?.right)) return parsed;
  } catch {
    // A blocked or malformed preference should never prevent the map from loading.
  }
  return null;
}

function storeWidths(widths) {
  try {
    window.localStorage.setItem(PANEL_LAYOUT_STORAGE_KEY, JSON.stringify(widths));
  } catch {
    // Resizing still works for the current page when browser storage is unavailable.
  }
}

function clearStoredWidths() {
  try {
    window.localStorage.removeItem(PANEL_LAYOUT_STORAGE_KEY);
  } catch {
    // Ignore unavailable browser storage.
  }
}

export function bindPanelResizers(root, { onResize = () => {} } = {}) {
  const filterPanel = root.querySelector("#asset-filters-panel");
  const resultsPanel = root.querySelector("#map-results-panel");
  const leftHandle = root.querySelector('[data-panel-resizer="left"]');
  const rightHandle = root.querySelector('[data-panel-resizer="right"]');
  if (!filterPanel || !resultsPanel || !leftHandle || !rightHandle) return () => {};

  const handles = { left: leftHandle, right: rightHandle };
  let refreshFrame = 0;
  let usingCustomLayout = false;
  let desiredWidths = null;
  let activeWidths = {
    left: filterPanel.getBoundingClientRect().width,
    right: resultsPanel.getBoundingClientRect().width,
  };

  function scheduleMapRefresh() {
    window.cancelAnimationFrame(refreshFrame);
    refreshFrame = window.requestAnimationFrame(onResize);
  }

  function sideBounds(side) {
    const containerWidth = root.getBoundingClientRect().width;
    const leftVisible = containerWidth > FILTER_DRAWER_BREAKPOINT;
    const mapWidth = minimumMapWidth(containerWidth);
    if (side === "left") {
      return {
        minimum: MIN_FILTER_WIDTH,
        maximum: Math.max(
          MIN_FILTER_WIDTH,
          Math.min(
            MAX_FILTER_WIDTH,
            containerWidth - activeWidths.right - mapWidth - (RESIZER_WIDTH * 2),
          ),
        ),
      };
    }
    return {
      minimum: MIN_RESULTS_WIDTH,
      maximum: Math.max(
        MIN_RESULTS_WIDTH,
        Math.min(
          MAX_RESULTS_WIDTH,
          containerWidth - mapWidth - RESIZER_WIDTH
            - (leftVisible ? activeWidths.left + RESIZER_WIDTH : 0),
        ),
      ),
    };
  }

  function updateAccessibility() {
    for (const side of ["left", "right"]) {
      const bounds = sideBounds(side);
      const value = Math.round(activeWidths[side]);
      const panelLabel = side === "left" ? "Filter panel" : "Asset results panel";
      handles[side].setAttribute("aria-valuemin", String(Math.round(bounds.minimum)));
      handles[side].setAttribute("aria-valuemax", String(Math.round(bounds.maximum)));
      handles[side].setAttribute("aria-valuenow", String(value));
      handles[side].setAttribute("aria-valuetext", `${panelLabel} ${value} pixels wide`);
    }
  }

  function applyWidths(widths, { persist = false, remember = true } = {}) {
    activeWidths = constrainPanelWidths({
      containerWidth: root.getBoundingClientRect().width,
      leftWidth: widths.left,
      rightWidth: widths.right,
    });
    root.style.setProperty("--filter-panel-width", `${activeWidths.left}px`);
    root.style.setProperty("--results-panel-width", `${activeWidths.right}px`);
    if (remember) desiredWidths = { left: widths.left, right: widths.right };
    usingCustomLayout = true;
    updateAccessibility();
    scheduleMapRefresh();
    if (persist) storeWidths(desiredWidths);
  }

  function syncDefaultLayout() {
    activeWidths = {
      left: filterPanel.getBoundingClientRect().width,
      right: resultsPanel.getBoundingClientRect().width,
    };
    updateAccessibility();
    scheduleMapRefresh();
  }

  function setSideWidth(side, requestedWidth, { persist = true } = {}) {
    const bounds = sideBounds(side);
    activeWidths[side] = clamp(requestedWidth, bounds.minimum, bounds.maximum);
    root.style.setProperty(
      side === "left" ? "--filter-panel-width" : "--results-panel-width",
      `${Math.round(activeWidths[side])}px`,
    );
    desiredWidths = { left: activeWidths.left, right: activeWidths.right };
    usingCustomLayout = true;
    updateAccessibility();
    scheduleMapRefresh();
    if (persist) storeWidths(desiredWidths);
  }

  function resetLayout() {
    clearStoredWidths();
    root.style.removeProperty("--filter-panel-width");
    root.style.removeProperty("--results-panel-width");
    usingCustomLayout = false;
    desiredWidths = null;
    syncDefaultLayout();
  }

  function bindHandle(side, handle) {
    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || root.getBoundingClientRect().width <= STACKED_BREAKPOINT) return;
      if (side === "left" && root.getBoundingClientRect().width <= FILTER_DRAWER_BREAKPOINT) return;
      event.preventDefault();
      handle.setPointerCapture(event.pointerId);
      handle.classList.add("is-resizing");
      document.body.classList.add("is-resizing-map-panels");

      const onPointerMove = (moveEvent) => {
        const bounds = root.getBoundingClientRect();
        const requestedWidth = side === "left"
          ? moveEvent.clientX - bounds.left
          : bounds.right - moveEvent.clientX;
        setSideWidth(side, requestedWidth, { persist: false });
      };
      const finish = () => {
        handle.removeEventListener("pointermove", onPointerMove);
        handle.removeEventListener("pointerup", finish);
        handle.removeEventListener("pointercancel", finish);
        handle.classList.remove("is-resizing");
        document.body.classList.remove("is-resizing-map-panels");
        desiredWidths = { left: activeWidths.left, right: activeWidths.right };
        storeWidths(desiredWidths);
      };
      handle.addEventListener("pointermove", onPointerMove);
      handle.addEventListener("pointerup", finish);
      handle.addEventListener("pointercancel", finish);
    });

    handle.addEventListener("keydown", (event) => {
      const bounds = sideBounds(side);
      const step = event.shiftKey ? 32 : 16;
      let nextWidth = activeWidths[side];
      if (event.key === "Home") nextWidth = bounds.minimum;
      else if (event.key === "End") nextWidth = bounds.maximum;
      else if (side === "left" && event.key === "ArrowLeft") nextWidth -= step;
      else if (side === "left" && event.key === "ArrowRight") nextWidth += step;
      else if (side === "right" && event.key === "ArrowLeft") nextWidth += step;
      else if (side === "right" && event.key === "ArrowRight") nextWidth -= step;
      else return;
      event.preventDefault();
      setSideWidth(side, nextWidth);
    });

    handle.addEventListener("dblclick", resetLayout);
  }

  bindHandle("left", leftHandle);
  bindHandle("right", rightHandle);

  const storedWidths = readStoredWidths();
  if (storedWidths) applyWidths(storedWidths);
  else syncDefaultLayout();

  const onWindowResize = () => {
    if (usingCustomLayout && desiredWidths) applyWidths(desiredWidths, { remember: false });
    else syncDefaultLayout();
  };
  window.addEventListener("resize", onWindowResize);

  return () => {
    window.removeEventListener("resize", onWindowResize);
    window.cancelAnimationFrame(refreshFrame);
  };
}
