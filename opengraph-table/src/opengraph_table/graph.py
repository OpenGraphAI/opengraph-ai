"""Build and persist a NetworkX knowledge graph from table data."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
from jinja2 import Template

from opengraph_table.schema import TableExtraction


class TableGraph:
    """Multi-table knowledge graph backed by networkx.DiGraph."""

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()
        self._sources: dict[str, dict[str, Any]] = {}  # Track source metadata

    def load(self, path: Path) -> None:
        """Load existing graph from JSON file."""
        if not path.exists():
            return
        data = json.loads(path.read_text())
        self._g = nx.node_link_graph(data.get("graph", {}), directed=True)
        self._sources = data.get("sources", {})

    def add_extraction(self, extraction: TableExtraction) -> None:
        """Add all data from a TableExtraction into the graph."""
        source_id = extraction.source.id

        # Register source
        self._sources[source_id] = extraction.source.model_dump()

        # Add source node
        self._g.add_node(
            source_id,
            type="source",
            filename=extraction.source.filename,
            title=extraction.source.title,
            sheet_name=extraction.source.sheet_name,
            extracted_at=extraction.source.extracted_at,
        )

        # Add column nodes and edges to source
        for col in extraction.columns:
            col_id = f"{source_id}__col_{col.index}_{col.name.lower().replace(' ', '_')}"
            self._g.add_node(
                col_id,
                type="column",
                name=col.name,
                data_type=col.data_type,
                is_key=col.is_key,
                nullable=col.nullable,
                source=source_id,
            )
            self._g.add_edge(source_id, col_id, relation="contains_column")

        # Add entity nodes
        for entity in extraction.entities:
            entity_id = f"{source_id}__entity_{entity.id}"
            self._g.add_node(
                entity_id,
                type="entity",
                name=entity.name,
                entity_type=entity.entity_type,
                attributes=entity.attributes,
                confidence=entity.confidence,
                source=source_id,
            )
            # Link entity to source
            self._g.add_edge(source_id, entity_id, relation="contains_entity")

        # Add relationship edges between entities
        for rel in extraction.relationships:
            src = f"{source_id}__entity_{rel.source_entity_id}"
            tgt = f"{source_id}__entity_{rel.target_entity_id}"
            if self._g.has_node(src) and self._g.has_node(tgt):
                self._g.add_edge(
                    src, tgt, relation=rel.relation_type, confidence=rel.confidence
                )

        # Add metric nodes
        for metric in extraction.metrics:
            metric_id = f"{source_id}__metric_{metric.id}"
            self._g.add_node(
                metric_id,
                type="metric",
                name=metric.name,
                metric_type=metric.metric_type,
                value=metric.value,
                confidence=metric.confidence,
                source=source_id,
            )
            self._g.add_edge(source_id, metric_id, relation="contains_metric")

        # Add note nodes
        for note in extraction.notes:
            note_id = f"{source_id}__note_{note.id}"
            self._g.add_node(
                note_id,
                type="note",
                content=note.content,
                note_type=note.note_type,
                source=source_id,
            )
            self._g.add_edge(source_id, note_id, relation="contains_note")

    def add_graph_json(self, graph_json: dict[str, Any]) -> None:
        """Add a Claude-produced graph JSON document into the graph.

        This is the primary integration path when the LLM returns graph JSON
        directly for a table/image.
        """
        sources = graph_json.get("sources", {})
        if isinstance(sources, dict):
            self._sources.update(sources)

        raw_graph = graph_json.get("graph", graph_json)
        edges_key = "links" if "links" in raw_graph and "edges" not in raw_graph else "edges"
        new_graph = nx.node_link_graph(raw_graph, directed=True, edges=edges_key)

        self._g.add_nodes_from(new_graph.nodes(data=True))
        self._g.add_edges_from(new_graph.edges(data=True))

    def merge_entities(self) -> dict[str, int]:
        """Merge equivalent entity nodes across sources.

        Returns:
            Stats on entities merged.
        """
        stats: dict[str, int] = {"entities_merged": 0, "relationships_repointed": 0}

        # Group entities by normalized (name, entity_type)
        entity_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        for node_id, attrs in self._g.nodes(data=True):
            if attrs.get("type") == "entity":
                name = attrs.get("name", node_id).lower().strip()
                etype = attrs.get("entity_type", "unknown").lower().strip()
                entity_groups[(name, etype)].append(node_id)

        # For each group with duplicates, merge into canonical (highest confidence)
        for (name, etype), nodes in entity_groups.items():
            if len(nodes) > 1:
                canonical = max(nodes, key=lambda n: self._g.nodes[n].get("confidence", 0.0))
                to_remove = set(nodes) - {canonical}

                # Repoint all edges
                for old_id in to_remove:
                    for pred in list(self._g.predecessors(old_id)):
                        # DiGraph returns single dict, not .values()
                        edge_data = self._g[pred][old_id]
                        self._g.add_edge(pred, canonical, **edge_data)

                    for succ in list(self._g.successors(old_id)):
                        # DiGraph returns single dict, not .values()
                        edge_data = self._g[old_id][succ]
                        self._g.add_edge(canonical, succ, **edge_data)

                    self._g.remove_node(old_id)

                stats["entities_merged"] += len(to_remove)
                stats["relationships_repointed"] += len(to_remove)

        return stats

    def summary(self) -> dict[str, Any]:
        """Return high-level graph statistics."""
        node_count_by_type: dict[str, int] = defaultdict(int)
        for _, attrs in self._g.nodes(data=True):
            node_count_by_type[attrs.get("type", "unknown")] += 1

        relation_count: dict[str, int] = defaultdict(int)
        for _, _, attrs in self._g.edges(data=True):
            relation_count[attrs.get("relation", "unknown")] += 1

        degrees = dict(self._g.degree())
        top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:15]

        return {
            "total_nodes": self._g.number_of_nodes(),
            "total_edges": self._g.number_of_edges(),
            "node_count_by_type": dict(node_count_by_type),
            "relation_count": dict(relation_count),
            "top_nodes": [{"id": n, "degree": d} for n, d in top_nodes],
            "sources": len(self._sources),
        }

    def to_json(self, path: Path) -> None:
        """Save graph to JSON (node_link format)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "graph": nx.node_link_data(self._g),
            "sources": self._sources,
            "metadata": self.summary(),
        }
        path.write_text(json.dumps(data, indent=2))

    def to_html(self, path: Path) -> None:
        """Generate an HTML visualization of the graph."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Build summary data
        summary = self.summary()
        entities = [n for n, a in self._g.nodes(data=True) if a.get("type") == "entity"]
        relationships = [
            (u, v, data.get("relation", ""))
            for u, v, data in self._g.edges(data=True)
            if self._g.nodes[u].get("type") == "entity"
        ]

        html_template = Template(
            """\
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Table Knowledge Graph</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        h1, h2 { color: #333; }
        .stat { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .stat-key { font-weight: bold; color: #0066cc; }
        .entity-list { background: white; padding: 15px; border-radius: 5px; }
        .entity { margin: 8px 0; padding: 8px; background: #e8f4f8; border-left: 3px solid #0066cc; }
        .entity-name { font-weight: bold; }
        .entity-type { font-size: 0.9em; color: #666; }
        .relationships { background: white; padding: 15px; border-radius: 5px; margin-top: 20px; }
        .relationship { margin: 5px 0; padding: 5px; background: #f0f0f0; }
        code { background: #f0f0f0; padding: 2px 5px; border-radius: 3px; }
    </style>
</head>
<body>
    <h1>Table Knowledge Graph</h1>
    
    <div class="stat">
        <div><span class="stat-key">Total Nodes:</span> {{ summary.total_nodes }}</div>
        <div><span class="stat-key">Total Edges:</span> {{ summary.total_edges }}</div>
        <div><span class="stat-key">Sources:</span> {{ summary.sources }}</div>
    </div>
    
    <div class="stat">
        <h3>Node Types</h3>
        {% for ntype, count in summary.node_count_by_type.items() %}
            <div>{{ ntype }}: {{ count }}</div>
        {% endfor %}
    </div>
    
    <div class="entity-list">
        <h2>Entities ({{ entities|length }})</h2>
        {% for entity_id in entities %}
            {% set node = graph_data[entity_id] %}
            <div class="entity">
                <div class="entity-name">{{ node.name }}</div>
                <div class="entity-type">Type: {{ node.entity_type }}</div>
                {% if node.attributes %}
                    <div>Attributes: {{ node.attributes|dictsort|list }}</div>
                {% endif %}
            </div>
        {% endfor %}
    </div>
    
    <div class="relationships">
        <h2>Relationships ({{ relationships|length }})</h2>
        {% for src, tgt, rel in relationships %}
            <div class="relationship">
                <code>{{ graph_data[src].name }}</code>
                <strong>{{ rel }}</strong>
                <code>{{ graph_data[tgt].name }}</code>
            </div>
        {% endfor %}
    </div>
</body>
</html>
"""
        )

        graph_data = {n: dict(a) for n, a in self._g.nodes(data=True)}

        html_content = html_template.render(
            summary=summary,
            entities=entities,
            relationships=relationships,
            graph_data=graph_data,
        )
        path.write_text(html_content)

    def to_markdown(self, path: Path) -> None:
        """Generate a Markdown report of the graph."""
        path.parent.mkdir(parents=True, exist_ok=True)

        summary = self.summary()

        lines = [
            "# Table Knowledge Graph Report\n",
            f"**Generated:** {Path.cwd()}\n",
            f"**Total Nodes:** {summary['total_nodes']}\n",
            f"**Total Edges:** {summary['total_edges']}\n",
            f"**Sources:** {summary['sources']}\n",
            "\n## Node Types\n",
        ]

        for ntype, count in sorted(summary["node_count_by_type"].items()):
            lines.append(f"- {ntype}: {count}\n")

        lines.append("\n## Relations\n")
        for rel, count in sorted(summary["relation_count"].items()):
            lines.append(f"- {rel}: {count}\n")

        lines.append("\n## Entities\n")
        entities = [
            (nid, self._g.nodes[nid])
            for nid, attrs in self._g.nodes(data=True)
            if attrs.get("type") == "entity"
        ]
        for entity_id, attrs in sorted(entities, key=lambda x: x[1].get("name", "")):
            lines.append(f"### {attrs.get('name', 'Unknown')}\n")
            lines.append(f"- Type: {attrs.get('entity_type', 'unknown')}\n")
            lines.append(f"- Confidence: {attrs.get('confidence', 0.0):.2f}\n")
            if attrs.get("attributes"):
                lines.append("- Attributes:\n")
                for k, v in attrs["attributes"].items():
                    lines.append(f"  - {k}: {v}\n")
            lines.append("\n")

        path.write_text("".join(lines))


def build_graph_from_tables(
    folder: Path,
    output_prefix: Path,
    merge: bool = True,
    write_html: bool = False,
    write_markdown: bool = False,
) -> TableGraph:
    """Extract and build knowledge graph from all tables in folder.

    Args:
        folder: Folder containing table images.
        output_prefix: Prefix for output files (json, optional html/md).
        merge: Whether to merge equivalent entities.
        write_html: Whether to write an HTML visualization.
        write_markdown: Whether to write a Markdown report.

    Returns:
        TableGraph instance.
    """
    import anthropic

    from opengraph_table.extract import extract_tables_llm_graph_json

    table_extensions = {".tsv", ".csv", ".xlsx", ".xls"}
    table_files = sorted(
        f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in table_extensions
    )

    if not table_files:
        raise ValueError(
            f"No table files found in {folder}. Expected extensions: {', '.join(sorted(table_extensions))}"
        )

    client = anthropic.Anthropic()
    graph = TableGraph()

    # Try to load existing graph
    json_path = output_prefix.parent / f"{output_prefix.name}.json"
    if json_path.exists():
        print(f"Loading existing graph from {json_path}")
        graph.load(json_path)

    print(f"Sending {len(table_files)} tables to Claude in one request...")
    graph_json = extract_tables_llm_graph_json(table_files, client)
    graph.add_graph_json(graph_json)

    if merge:
        stats = graph.merge_entities()
        print(f"Merging stats: {stats}")

    # Save outputs
    json_path = output_prefix.parent / f"{output_prefix.name}.json"

    graph.to_json(json_path)
    output_paths = [str(json_path)]

    if write_html:
        html_path = output_prefix.parent / f"{output_prefix.name}.html"
        graph.to_html(html_path)
        output_paths.append(str(html_path))

    if write_markdown:
        md_path = output_prefix.parent / f"{output_prefix.name}.md"
        graph.to_markdown(md_path)
        output_paths.append(str(md_path))

    print(f"Graph saved to {', '.join(output_paths)}")
    print(json.dumps(graph.summary(), indent=2))

    return graph
