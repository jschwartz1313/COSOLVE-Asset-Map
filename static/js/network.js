const root = document.querySelector("[data-network]");
const dataElement = document.querySelector("#network-data");

if (root && dataElement) {
  const data = JSON.parse(dataElement.textContent);
  const svg = root.querySelector("svg");
  const empty = root.querySelector(".network-empty");
  const namespace = "http://www.w3.org/2000/svg";
  const colors = {
    university: "#8b3f56",
    organization: "#2f6f9f",
    facility: "#147d78",
    program: "#b48216",
    infrastructure: "#c63f2b",
    "operating-environment": "#6b5d95",
  };

  function svgElement(tag, attributes = {}) {
    const node = document.createElementNS(namespace, tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    return node;
  }

  function draw() {
    svg.replaceChildren();
    empty.hidden = data.edges.length > 0;
    if (!data.nodes.length) return;
    const width = Math.max(root.clientWidth, 320);
    const height = Math.max(root.clientHeight, 480);
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const center = { x: width / 2, y: height / 2 };
    const positions = new Map();
    const centerNode = data.nodes.find((node) => node.is_center);
    positions.set(centerNode.id, center);
    const neighbors = data.nodes.filter((node) => !node.is_center);
    const sideCount = Math.ceil(neighbors.length / 2);
    const rowGap = Math.min(40, (height - 60) / Math.max(sideCount - 1, 1));
    const firstY = center.y - ((sideCount - 1) * rowGap) / 2;
    neighbors.forEach((node, index) => {
      const side = index % 2 === 0 ? "left" : "right";
      const row = Math.floor(index / 2);
      positions.set(node.id, {
        x: side === "left" ? width * 0.2 : width * 0.8,
        y: firstY + row * rowGap,
        side,
      });
    });

    for (const edge of data.edges) {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      if (!source || !target) continue;
      svg.append(
        svgElement("line", {
          x1: source.x,
          y1: source.y,
          x2: target.x,
          y2: target.y,
          class: "network-edge",
        }),
      );
    }

    for (const node of data.nodes) {
      const position = positions.get(node.id);
      const link = svgElement("a", { href: node.url, "aria-label": `Open ${node.name}` });
      const group = svgElement("g", {
        class: node.is_center
          ? "network-node is-center"
          : `network-node side-${position.side}`,
        transform: `translate(${position.x} ${position.y})`,
      });
      const circle = svgElement("circle", {
        r: node.is_center ? 34 : 14,
        fill: colors[node.type] || "#5c686f",
      });
      const label = svgElement("text", {
        x: node.is_center ? 0 : position.side === "left" ? -24 : 24,
        y: node.is_center ? 50 : 4,
        "text-anchor": node.is_center
          ? "middle"
          : position.side === "left"
            ? "end"
            : "start",
      });
      const characterLimit = width < 600 ? 13 : 27;
      const shortName =
        node.name.length > characterLimit
          ? `${node.name.slice(0, characterLimit - 3).trim()}...`
          : node.name;
      label.textContent = shortName;
      const title = svgElement("title");
      title.textContent = `${node.name}, ${node.type_label}`;
      group.append(title, circle, label);
      link.append(group);
      svg.append(link);
    }
  }

  draw();
  if ("ResizeObserver" in window) {
    new ResizeObserver(draw).observe(root);
  } else {
    window.addEventListener("resize", draw);
  }
}
