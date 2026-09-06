function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function buildPopup(feature) {
  const props = feature.properties;
  const root = element("article", "map-popup");
  root.append(element("span", `type-pill type-${props.record_type}`, props.record_type_label));
  if (props.activity_status_label) root.append(element("span", "activity-label", props.activity_status_label));
  root.append(element("h3", "", props.name));
  const location = [
    props.location.address_line,
    [props.location.city, props.location.state].filter(Boolean).join(", "),
  ].filter(Boolean).join(" · ");
  if (location) root.append(element("p", "popup-location", location));
  root.append(element("small", "popup-precision", props.location.precision_label));
  root.append(element("p", "", props.short_description));
  const link = element("a", "", "View asset");
  link.href = props.detail_url;
  root.append(link);
  return root;
}
