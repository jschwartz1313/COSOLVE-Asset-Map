function textElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = text;
  return node;
}

export function renderResults(container, features, onSelect) {
  container.replaceChildren();
  if (!features.length) {
    const empty = textElement("div", "empty-state", "No published assets match these filters.");
    container.append(empty);
    return;
  }
  for (const feature of features) {
    const props = feature.properties;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "result-row";
    button.dataset.assetId = feature.id;
    button.append(textElement("span", `type-pill type-${props.record_type}`, props.record_type_label));
    button.append(textElement("h3", "", props.name));
    button.append(textElement("p", "", props.short_description));
    const footer = textElement("div", "row-footer", "");
    footer.append(textElement("span", "", [props.location.city, props.location.state].filter(Boolean).join(", ")));
    footer.append(textElement("span", "", props.location.precision || ""));
    button.append(footer);
    button.addEventListener("click", () => {
      for (const row of container.querySelectorAll(".result-row")) row.classList.remove("is-selected");
      button.classList.add("is-selected");
      onSelect(feature.id);
    });
    container.append(button);
  }
}

export function selectResult(container, id) {
  const row = container.querySelector(`[data-asset-id="${CSS.escape(id)}"]`);
  if (!row) return;
  for (const item of container.querySelectorAll(".result-row")) item.classList.remove("is-selected");
  row.classList.add("is-selected");
  row.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

