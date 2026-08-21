"""Render a DocumentGraph to a self-contained interactive HTML visualization
using Cytoscape.js (chosen over D3 for its better scaling on larger graphs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opengraph_text.graph import DocumentGraph

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>opengraph-text graph</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.2/cytoscape.min.js"></script>
<script src="https://unpkg.com/layout-base@2.0.1/layout-base.js"></script>
<script src="https://unpkg.com/cose-base@2.2.0/cose-base.js"></script>
<script src="https://unpkg.com/cytoscape-fcose@2.2.0/cytoscape-fcose.js"></script>
<style>
  html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; \
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0b0e14; color: #eee; }
  #cy { position: absolute; top: 0; left: 0; right: 320px; bottom: 0; }
  #empty-state { position: absolute; inset: 0 320px 0 0; display: flex; align-items: center; \
justify-content: center; font-size: 16px; color: #888; }

  #sidebar { position: absolute; top: 0; right: 0; width: 320px; height: 100%; box-sizing: border-box; \
background: #12151c; border-left: 1px solid #262b36; overflow-y: auto; padding: 14px; font-size: 12px; }
  #sidebar h2 { font-size: 13px; margin: 16px 0 8px; color: #aaa; text-transform: uppercase; \
letter-spacing: 0.04em; }
  #sidebar h2:first-child { margin-top: 0; }

  #search-box { width: 100%; box-sizing: border-box; padding: 6px 8px; border-radius: 4px; \
border: 1px solid #333; background: #1a1e27; color: #eee; font-size: 12px; }

  .legend-row, .filter-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
  .legend-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 50%; flex: none; }

  #confidence-value { color: #888; }

  button { background: #1a1e27; color: #eee; border: 1px solid #333; border-radius: 4px; \
padding: 6px 10px; font-size: 12px; cursor: pointer; }
  button:hover { background: #23283333; }

  #detail-panel { border-top: 1px solid #262b36; padding-top: 10px; margin-top: 10px; }
  #detail-panel .field { margin-bottom: 4px; word-break: break-word; }
  #detail-panel .field-key { color: #888; }
  #detail-empty { color: #666; }

  .provenance-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; \
cursor: pointer; padding: 4px; border-radius: 4px; }
  .provenance-item:hover { background: #1a1e27; }
  .provenance-name { font-size: 11px; color: #ccc; }

  #tooltip { position: absolute; pointer-events: none; background: rgba(20, 20, 25, 0.95); \
color: #eee; padding: 8px 10px; border-radius: 6px; font-size: 12px; max-width: 320px; \
white-space: pre-wrap; opacity: 0; transition: opacity 0.1s ease; z-index: 10; }
</style>
</head>
<body>
<div id="cy"></div>
<div id="empty-state" style="display: none;">This graph has no nodes.</div>
<div id="tooltip"></div>

<div id="sidebar">
  <h2>Search</h2>
  <input id="search-box" type="text" placeholder="Filter by label..." />

  <h2>Legend / Node Types</h2>
  <div id="legend"></div>

  <h2>Edge Relations</h2>
  <div id="relation-filters"></div>

  <h2>Min Confidence</h2>
  <input id="confidence-slider" type="range" min="0" max="1" step="0.05" value="0" style="width: 100%;" />
  <div id="confidence-value">0.00</div>

  <h2>Export</h2>
  <button id="export-btn">Download PNG</button>

  <div id="detail-panel">
    <h2>Details</h2>
    <div id="detail-empty">Click a node to see its fields.</div>
    <div id="detail-fields"></div>
    <div id="provenance"></div>
  </div>
</div>

<script>
const graphData = __GRAPH_DATA__;

if (typeof cytoscapeFcose !== "undefined") {
  try {
    cytoscape.use(cytoscapeFcose);
  } catch (e) {
    console.warn("fcose registration failed, falling back to cose", e);
  }
}

if (graphData.nodes.length === 0) {
  document.getElementById("empty-state").style.display = "flex";
} else {
  const nodesById = {};
  graphData.nodes.forEach((n) => { nodesById[n.id] = n; });

  const elements = [
    ...graphData.nodes.map((n) => ({ data: { ...n } })),
    ...graphData.edges.map((e, i) => ({
      data: { id: "e" + i, source: e.source, target: e.target, relation: e.relation, confidence: e.confidence },
    })),
  ];

  const nodeTypes = Array.from(new Set(graphData.nodes.map((n) => n.type))).sort();
  const relations = Array.from(new Set(graphData.edges.map((e) => e.relation))).sort();

  const palette = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac"];
  const color = {};
  nodeTypes.forEach((t, i) => { color[t] = palette[i % palette.length]; });

  const cy = cytoscape({
    container: document.getElementById("cy"),
    elements,
    style: [
      {
        selector: "node",
        style: {
          "background-color": (ele) => color[ele.data("type")] || "#888",
          "label": "data(label)",
          "font-size": 9,
          "color": "#eee",
          "text-valign": "bottom",
          "text-margin-y": 4,
          "width": (ele) => 14 + Math.min(ele.degree(), 20) * 3,
          "height": (ele) => 14 + Math.min(ele.degree(), 20) * 3,
          "border-width": 1,
          "border-color": "#fff",
        },
      },
      {
        selector: "edge",
        style: {
          "width": 1.5,
          "line-color": "#555",
          "target-arrow-color": "#555",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "opacity": 0.7,
        },
      },
      { selector: ".faded", style: { opacity: 0.08 } },
      { selector: ".hidden", style: { display: "none" } },
      {
        selector: "edge.relation-label",
        style: { label: "data(relation)", "font-size": 8, color: "#ccc" },
      },
    ],
    layout: { name: "preset" },
  });

  function runLayout() {
    try {
      cy.layout({ name: "fcose", animate: false, randomize: true }).run();
    } catch (e) {
      console.warn("fcose layout failed, falling back to cose", e);
      cy.layout({ name: "cose", animate: false }).run();
    }
  }
  runLayout();

  // Legend + type filters
  const legend = document.getElementById("legend");
  const hiddenTypes = new Set();
  const hiddenRelations = new Set();
  let minConfidence = 0;

  function applyFilters() {
    cy.nodes().forEach((n) => {
      const typeHidden = hiddenTypes.has(n.data("type"));
      const conf = n.data("confidence");
      // Document nodes carry no confidence score, so they are never hidden by the slider.
      const confHidden = conf !== undefined && conf !== null && conf < minConfidence;
      n.toggleClass("hidden", typeHidden || confHidden);
    });
    cy.edges().forEach((e) => {
      const relHidden = hiddenRelations.has(e.data("relation"));
      const conf = e.data("confidence");
      const confHidden = conf !== undefined && conf !== null && conf < minConfidence;
      const endpointsHidden = e.source().hasClass("hidden") || e.target().hasClass("hidden");
      e.toggleClass("hidden", relHidden || confHidden || endpointsHidden);
    });
  }

  nodeTypes.forEach((t) => {
    const row = document.createElement("label");
    row.className = "legend-row";
    row.style.cursor = "pointer";
    row.innerHTML = `<input type="checkbox" checked data-type="${t}" /> ` +
      `<span class="legend-swatch" style="background:${color[t]}"></span><span>${t}</span>`;
    row.querySelector("input").addEventListener("change", (ev) => {
      if (ev.target.checked) hiddenTypes.delete(t); else hiddenTypes.add(t);
      applyFilters();
    });
    legend.appendChild(row);
  });

  const relationFilters = document.getElementById("relation-filters");
  relations.forEach((r) => {
    const row = document.createElement("label");
    row.className = "filter-row";
    row.style.cursor = "pointer";
    row.innerHTML = `<input type="checkbox" checked data-relation="${r}" /> <span>${r}</span>`;
    row.querySelector("input").addEventListener("change", (ev) => {
      if (ev.target.checked) hiddenRelations.delete(r); else hiddenRelations.add(r);
      applyFilters();
    });
    relationFilters.appendChild(row);
  });

  const confidenceSlider = document.getElementById("confidence-slider");
  const confidenceValue = document.getElementById("confidence-value");
  confidenceSlider.addEventListener("input", (ev) => {
    minConfidence = parseFloat(ev.target.value);
    confidenceValue.textContent = minConfidence.toFixed(2);
    applyFilters();
  });

  // Search
  const searchBox = document.getElementById("search-box");
  searchBox.addEventListener("input", (ev) => {
    const q = ev.target.value.trim().toLowerCase();
    cy.nodes().removeClass("faded");
    if (!q) return;
    const matches = cy.nodes().filter((n) => (n.data("label") || "").toLowerCase().includes(q));
    cy.nodes().not(matches).addClass("faded");
    if (matches.length > 0) {
      cy.animate({ fit: { eles: matches, padding: 60 } }, { duration: 300 });
    }
  });

  // Tooltip
  const tooltip = document.getElementById("tooltip");
  function formatFields(data) {
    return Object.entries(data)
      .filter(([k]) => k !== "id")
      .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
      .join("\\n");
  }

  cy.on("mouseover", "node", (ev) => {
    const pos = ev.renderedPosition || ev.target.renderedPosition();
    tooltip.style.opacity = 1;
    tooltip.innerHTML = formatFields(ev.target.data()).replace(/\\n/g, "<br/>");
    tooltip.style.left = pos.x + 20 + "px";
    tooltip.style.top = pos.y + 10 + "px";
    highlightNeighborhood(ev.target);
  });
  cy.on("mouseout", "node", () => {
    tooltip.style.opacity = 0;
    clearHighlight();
  });

  cy.on("mouseover", "edge", (ev) => {
    ev.target.addClass("relation-label");
    const pos = ev.renderedPosition || { x: 0, y: 0 };
    tooltip.style.opacity = 1;
    tooltip.textContent = "relation: " + ev.target.data("relation");
    tooltip.style.left = pos.x + 20 + "px";
    tooltip.style.top = pos.y + 10 + "px";
  });
  cy.on("mouseout", "edge", (ev) => {
    ev.target.removeClass("relation-label");
    tooltip.style.opacity = 0;
  });
  cy.on("mousemove", (ev) => {
    if (tooltip.style.opacity === "1") {
      tooltip.style.left = ev.renderedPosition.x + 20 + "px";
      tooltip.style.top = ev.renderedPosition.y + 10 + "px";
    }
  });

  function highlightNeighborhood(node) {
    const neighborhood = node.closedNeighborhood();
    cy.elements().not(neighborhood).addClass("faded");
  }
  function clearHighlight() {
    cy.elements().removeClass("faded");
  }

  // Click: select + detail panel + neighborhood highlight
  const detailEmpty = document.getElementById("detail-empty");
  const detailFields = document.getElementById("detail-fields");
  const provenance = document.getElementById("provenance");

  function documentFilenameFor(documentId) {
    const node = nodesById[documentId];
    if (!node) return documentId;
    return node.label || documentId;
  }

  function showDetail(node) {
    const data = node.data();
    detailEmpty.style.display = "none";
    detailFields.innerHTML = "";
    provenance.innerHTML = "";

    Object.entries(data).forEach(([k, v]) => {
      if (v === undefined || v === null) return;
      const row = document.createElement("div");
      row.className = "field";
      row.innerHTML = `<span class="field-key">${k}:</span> ${typeof v === "object" ? JSON.stringify(v) : v}`;
      detailFields.appendChild(row);
    });

    if (data.type !== "document" && Array.isArray(data.seen_in) && data.seen_in.length > 0) {
      const heading = document.createElement("h2");
      heading.textContent = "Provenance";
      provenance.appendChild(heading);

      data.seen_in.forEach((documentId) => {
        const item = document.createElement("div");
        item.className = "provenance-item";

        const name = document.createElement("span");
        name.className = "provenance-name";
        name.textContent = documentFilenameFor(documentId);

        item.appendChild(name);
        item.addEventListener("click", () => {
          const target = cy.getElementById(documentId);
          if (target.length > 0) {
            cy.animate({ center: { eles: target }, zoom: 1.5 }, { duration: 300 });
            cy.$(":selected").unselect();
            target.select();
            highlightNeighborhood(target);
          }
        });
        provenance.appendChild(item);
      });
    }
  }

  cy.on("tap", "node", (ev) => {
    showDetail(ev.target);
    cy.elements().removeClass("faded");
    highlightNeighborhood(ev.target);
  });
  cy.on("tap", (ev) => {
    if (ev.target === cy) {
      detailEmpty.style.display = "block";
      detailFields.innerHTML = "";
      provenance.innerHTML = "";
      clearHighlight();
    }
  });

  document.getElementById("export-btn").addEventListener("click", () => {
    const png = cy.png({ full: true, scale: 2, bg: "#0b0e14" });
    const link = document.createElement("a");
    link.href = png;
    link.download = "graph.png";
    link.click();
  });
}
</script>
</body>
</html>
"""


def render_graph_html(graph: "DocumentGraph", output: Path) -> Path:
    """Render graph to a self-contained interactive HTML file at output."""
    vis_data = graph.to_vis_data()
    embedded_json = json.dumps(vis_data).replace("</", "<\\/")

    html = _HTML_TEMPLATE.replace("__GRAPH_DATA__", embedded_json)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)
    return output
