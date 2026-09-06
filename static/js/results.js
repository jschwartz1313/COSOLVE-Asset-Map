const PAGE_SIZE = 50;
const states = new WeakMap();

function textElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = text;
  return node;
}

function resultRow(feature, container, onSelect) {
  const props = feature.properties;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "result-row";
  button.dataset.assetId = feature.id;
  button.append(textElement("span", `type-pill type-${props.record_type}`, props.record_type_label));
  if (props.activity_status_label) button.append(textElement("span", "activity-label", props.activity_status_label));
  button.append(textElement("h3", "", props.name));
  button.append(textElement("p", "", props.short_description));
  const footer = textElement("div", "row-footer", "");
  const locality = props.location.city
    ? [props.location.city, props.location.state].filter(Boolean).join(", ")
    : props.location.region || props.location.state;
  footer.append(textElement("span", "", locality));
  footer.append(textElement("span", "", props.location.precision_label || ""));
  button.append(footer);
  button.addEventListener("click", () => {
    for (const row of container.querySelectorAll(".result-row")) {
      row.classList.remove("is-selected");
    }
    button.classList.add("is-selected");
    onSelect(feature.id);
  });
  return button;
}

function appendPage(container) {
  const state = states.get(container);
  if (!state) return;
  state.moreButton?.remove();
  const end = Math.min(state.rendered + PAGE_SIZE, state.features.length);
  for (const feature of state.features.slice(state.rendered, end)) {
    container.append(resultRow(feature, container, state.onSelect));
  }
  state.rendered = end;
  if (state.rendered < state.features.length) {
    const remaining = state.features.length - state.rendered;
    const button = textElement(
      "button",
      "button secondary results-more",
      `Show ${Math.min(PAGE_SIZE, remaining)} more`,
    );
    button.type = "button";
    button.addEventListener("click", () => appendPage(container));
    state.moreButton = button;
    container.append(button);
  }
}

export function renderResults(container, features, onSelect) {
  container.replaceChildren();
  states.set(container, { features, onSelect, rendered: 0, moreButton: null });
  if (!features.length) {
    const empty = textElement(
      "div",
      "empty-state",
      "No public asset listings match these filters.",
    );
    container.append(empty);
    return;
  }
  appendPage(container);
}

export function selectResult(container, id) {
  let row = container.querySelector(`[data-asset-id="${CSS.escape(id)}"]`);
  const state = states.get(container);
  if (!row && state) {
    const index = state.features.findIndex((feature) => feature.id === id);
    while (index >= state.rendered && state.rendered < state.features.length) {
      appendPage(container);
    }
    row = container.querySelector(`[data-asset-id="${CSS.escape(id)}"]`);
  }
  if (!row) return;
  for (const item of container.querySelectorAll(".result-row")) {
    item.classList.remove("is-selected");
  }
  row.classList.add("is-selected");
  row.scrollIntoView({ block: "nearest", behavior: "smooth" });
}
