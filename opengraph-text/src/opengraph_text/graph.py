"""Build and persist a NetworkX knowledge graph from extracted text data."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import networkx as nx

from opengraph_text.schema import DocumentExtraction

_TEXT_EXTENSIONS = {".txt", ".md"}


class TextGraph:
    """Multi-document knowledge graph backed by networkx.MultiDiGraph."""

    def __init__(self) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()

    def add_extraction(self, extraction: DocumentExtraction) -> None:
        """Add all nodes and edges from a DocumentExtraction into the graph."""
        document_id = extraction.document.id

        def scope(node_id: str) -> str:
            if node_id == document_id:
                return node_id
            return f"{document_id}__{node_id}"

        self._g.add_node(
            document_id,
            type="document",
            path=extraction.document.path,
            title=extraction.document.title,
            language=extraction.document.language,
            source=extraction.document.source,
            seen_in=[document_id],
        )

        for entity in extraction.entities:
            self._g.add_node(
                scope(entity.id),
                type="entity",
                label=entity.label,
                entity_type=entity.type,
                description=entity.description,
                confidence=entity.confidence,
                seen_in=[document_id],
            )

        for chunk in extraction.text_chunks:
            self._g.add_node(
                scope(chunk.id),
                type="text_chunk",
                text=chunk.text,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                confidence=chunk.confidence,
                seen_in=[document_id],
            )

        for attr in extraction.attributes:
            self._g.add_node(
                scope(attr.id),
                type="attribute",
                key=attr.key,
                value=attr.value,
                confidence=attr.confidence,
                seen_in=[document_id],
            )

        for edge in extraction.contains_edges:
            self._g.add_edge(scope(edge.source), scope(edge.target), relation="contains", confidence=edge.confidence)

        for edge in extraction.mentions_edges:
            self._g.add_edge(scope(edge.source), scope(edge.target), relation="mentions", confidence=edge.confidence)

        for edge in extraction.has_attribute_edges:
            self._g.add_edge(scope(edge.source), scope(edge.target), relation="has_attribute", confidence=edge.confidence)

        for edge in extraction.relation_edges:
            self._g.add_edge(
                scope(edge.source),
                scope(edge.target),
                relation=edge.relation,
                evidence=edge.evidence,
                confidence=edge.confidence,
            )

    def link_across_documents(self) -> dict[str, int]:
        """Merge equivalent entity and attribute nodes across documents."""
        stats = {"entities_merged": 0, "attributes_merged": 0}

        entity_groups: dict[str, list[str]] = defaultdict(list)
        for node_id, attrs in self._g.nodes(data=True):
            if attrs.get("type") == "entity":
                label = attrs.get("label", node_id)
                normalized = re.sub(r"_\d+$", "", str(label).lower())
                entity_groups[normalized].append(node_id)

        for nodes in entity_groups.values():
            if len(nodes) > 1:
                stats["entities_merged"] += self._merge_nodes(nodes)

        attr_groups: dict[str, list[str]] = defaultdict(list)
        for node_id, attrs in self._g.nodes(data=True):
            if attrs.get("type") == "attribute":
                group_key = f"{attrs.get('key', '')}:{str(attrs.get('value', '')).lower()}"
                attr_groups[group_key].append(node_id)

        for nodes in attr_groups.values():
            if len(nodes) > 1:
                stats["attributes_merged"] += self._merge_nodes(nodes)

        return stats

    def _merge_nodes(self, nodes: list[str]) -> int:
        """Merge equivalent nodes into the highest-confidence canonical node."""
        canonical = max(nodes, key=lambda n: self._g.nodes[n].get("confidence", 0.0))
        to_remove = set(nodes) - {canonical}
        node_map = {old: canonical for old in to_remove}

        seen_in = list(self._g.nodes[canonical].get("seen_in", []))
        for old_id in to_remove:
            for doc_id in self._g.nodes[old_id].get("seen_in", []):
                if doc_id not in seen_in:
                    seen_in.append(doc_id)
        self._g.nodes[canonical]["seen_in"] = seen_in

        seen_edge_ids: set[tuple] = set()
        edges_to_remove: list[tuple] = []
        edges_to_add: list[tuple] = []

        for old_id in to_remove:
            for src, tgt, key, data in list(self._g.in_edges(old_id, data=True, keys=True)):
                eid = (src, tgt, key)
                if eid in seen_edge_ids:
                    continue
                seen_edge_ids.add(eid)
                new_src = node_map.get(src, src)
                new_tgt = node_map.get(tgt, tgt)
                edges_to_remove.append(eid)
                if new_src != new_tgt:
                    edges_to_add.append((new_src, new_tgt, dict(data)))

            for src, tgt, key, data in list(self._g.out_edges(old_id, data=True, keys=True)):
                eid = (src, tgt, key)
                if eid in seen_edge_ids:
                    continue
                seen_edge_ids.add(eid)
                new_src = node_map.get(src, src)
                new_tgt = node_map.get(tgt, tgt)
                edges_to_remove.append(eid)
                if new_src != new_tgt:
                    edges_to_add.append((new_src, new_tgt, dict(data)))

        for src, tgt, key in edges_to_remove:
            if self._g.has_edge(src, tgt, key=key):
                self._g.remove_edge(src, tgt, key=key)

        for src, tgt, data in edges_to_add:
            self._g.add_edge(src, tgt, **data)

        for old_id in to_remove:
            self._g.remove_node(old_id)

        return len(to_remove)

    def to_json(self, path: Path) -> None:
        """Save the graph to path using node_link_data JSON format."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self._g)
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def from_json(cls, path: Path) -> "TextGraph":
        """Load a graph from a JSON file written by to_json."""
        data = json.loads(path.read_text())
        graph = cls()
        graph._g = nx.node_link_graph(data, directed=True, multigraph=True)
        return graph

    def summary(self) -> dict:
        """Return high-level graph statistics."""
        node_count_by_type: dict[str, int] = defaultdict(int)
        for _, attrs in self._g.nodes(data=True):
            node_count_by_type[attrs.get("type", "unknown")] += 1

        edge_count_by_relation: dict[str, int] = defaultdict(int)
        for _, _, attrs in self._g.edges(data=True):
            edge_count_by_relation[attrs.get("relation", "unknown")] += 1

        documents = [
            Path(attrs.get("path", node_id)).name
            for node_id, attrs in self._g.nodes(data=True)
            if attrs.get("type") == "document"
        ]

        return {
            "total_nodes": self._g.number_of_nodes(),
            "total_edges": self._g.number_of_edges(),
            "node_count_by_type": dict(node_count_by_type),
            "edge_count_by_relation": dict(edge_count_by_relation),
            "documents": documents,
        }


def build_graph_from_folder(folder: Path, output: Path) -> TextGraph:
    """Extract and build a knowledge graph from all text documents in folder."""
    import anthropic
    from tqdm import tqdm

    from opengraph_text.extract import extract_document

    document_files = sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in _TEXT_EXTENSIONS
    )

    if not document_files:
        raise ValueError(f"No text files found in {folder}. Expected extensions: {', '.join(sorted(_TEXT_EXTENSIONS))}")

    client = anthropic.Anthropic()
    graph = TextGraph()

    for document_path in tqdm(document_files, desc="Extracting documents"):
        extraction = extract_document(document_path, client)
        graph.add_extraction(extraction)

    stats = graph.link_across_documents()
    print("Linking stats:", stats)

    graph.to_json(output)
    print(f"Graph saved to {output}")
    print(json.dumps(graph.summary(), indent=2))

    return graph