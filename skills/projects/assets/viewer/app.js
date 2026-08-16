const text = (value) => document.createTextNode(value || "—");

function metric(label, value) {
  const item = document.createElement("div");
  item.className = "metric";
  const title = document.createElement("strong");
  title.append(text(label));
  const content = document.createElement("pre");
  content.append(text(value));
  item.append(title, content);
  return item;
}

function sourceCard(file) {
  const card = document.createElement("article");
  const title = document.createElement("h3");
  title.append(text(file.path));
  const body = document.createElement("pre");
  body.append(text(file.content));
  card.append(title, body);
  return card;
}

function diagramCard(file) {
  const card = document.createElement("article");
  const title = document.createElement("h3");
  title.append(text(file.path));
  card.append(title);
  try {
    const model = JSON.parse(file.content);
    if (!Array.isArray(model.nodes) || !Array.isArray(model.edges)) throw new Error();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const defs = document.createElementNS(svg.namespaceURI, "defs");
    defs.innerHTML = '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#7b8d81"/></marker>';
    svg.append(defs);
    const width = 900;
    const positions = new Map(model.nodes.map((node, index) => [node.id, {
      x: Number(node.x) || 120 + (index % 4) * 210,
      y: Number(node.y) || 70 + Math.floor(index / 4) * 130,
    }]));
    svg.setAttribute("viewBox", `0 0 ${width} ${Math.max(260, 160 + Math.ceil(model.nodes.length / 4) * 130)}`);
    model.edges.forEach((edge) => {
      const start = positions.get(edge.source);
      const end = positions.get(edge.target);
      if (!start || !end) return;
      const line = document.createElementNS(svg.namespaceURI, "line");
      line.setAttribute("class", "edge");
      line.setAttribute("x1", start.x + 70);
      line.setAttribute("y1", start.y + 28);
      line.setAttribute("x2", end.x);
      line.setAttribute("y2", end.y + 28);
      svg.append(line);
    });
    model.nodes.forEach((node) => {
      const position = positions.get(node.id);
      const rect = document.createElementNS(svg.namespaceURI, "rect");
      rect.setAttribute("class", "node");
      rect.setAttribute("x", position.x);
      rect.setAttribute("y", position.y);
      rect.setAttribute("width", "140");
      rect.setAttribute("height", "56");
      rect.setAttribute("rx", "12");
      const label = document.createElementNS(svg.namespaceURI, "text");
      label.setAttribute("class", "label");
      label.setAttribute("x", position.x + 70);
      label.setAttribute("y", position.y + 34);
      label.textContent = node.label || node.id;
      svg.append(rect, label);
    });
    card.append(svg);
  } catch {
    const body = document.createElement("pre");
    body.append(text(file.content));
    card.append(body);
  }
  return card;
}

fetch("/api/project")
  .then((response) => response.json())
  .then((project) => {
    document.querySelector("#project-root").append(text(project.projectRoot));
    document.querySelector("#skill").append(text(project.skill));
    const git = document.querySelector("#git");
    git.append(metric("Branch", project.git.branch));
    git.append(metric("HEAD", project.git.head));
    git.append(metric("Working tree", project.git.status || "clean"));
    project.references.forEach((file) => document.querySelector("#references").append(sourceCard(file)));
    project.diagrams.forEach((file) => document.querySelector("#diagrams").append(diagramCard(file)));
  })
  .catch((error) => {
    document.querySelector("main").prepend(metric("Viewer error", String(error)));
  });
