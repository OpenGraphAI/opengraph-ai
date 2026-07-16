"""Build and persist a NetworkX knowledge graph from extracted document data."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import networkx as nx
from dotenv import load_dotenv

from opengraph_text.schema import DocumentExtraction

load_dotenv(override=True)

_DOCUMENT_EXTENSIONS = {".txt", ".md", ".pdf"}

_TRAILING_DIGITS_RE = re.compile(r"_?\d+$")
_ORG_SUFFIX_RE = re.compile(r"_(inc|corp|co)$")


def _normalize_label(label: str) -> str:
    """Lowercase, snake_case a label and strip trailing digit/org suffixes.

    Suffixes are stripped repeatedly (e.g. "Acme Corp Inc" -> "acme") so that
    variant spellings of the same underlying entity converge on one key.
    """
    snake = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    while True:
        stripped = _TRAILING_DIGITS_RE.sub("", snake).strip("_")
        stripped = _ORG_SUFFIX_RE.sub("", stripped).strip("_")
        if stripped == snake:
            break
        snake = stripped
    return snake


class DocumentGraph:
    """Multi-document knowledge graph backed by networkx.MultiDiGraph."""

    def __init__(self) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()

    def add_extraction(self, extraction: DocumentExtraction) -> None:
        """Add all nodes and edges from a DocumentExtraction into the graph."""
        document_id = extraction.document.id

        def scope(node_id: str) -> str:
            """Prefix non-document node IDs with the document ID to avoid cross-extraction collisions."""
            if node_id == document_id:
                return node_id
            return f"{document_id}__{node_id}"

        self._g.add_node(
            document_id,
            type="document",
            path=extraction.document.path,
            word_count=extraction.document.word_count,
            format=extraction.document.format,
            seen_in=[document_id],
        )

        for entity in extraction.entities:
            self._g.add_node(
                scope(entity.id),
                type="entity",
                label=entity.label,
                entity_type=entity.entity_type,
                confidence=entity.confidence,
                seen_in=[document_id],
            )

        for topic in extraction.topics:
            self._g.add_node(
                scope(topic.id),
                type="topic",
                label=topic.label,
                confidence=topic.confidence,
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

        for claim in extraction.claims:
            self._g.add_node(
                scope(claim.id),
                type="claim",
                text=claim.text,
                confidence=claim.confidence,
                seen_in=[document_id],
            )

        for edge in extraction.contains_edges:
            self._g.add_edge(scope(edge.source), scope(edge.target), relation="contains", confidence=edge.confidence)

        for edge in extraction.about_topic_edges:
            self._g.add_edge(
                scope(edge.source), scope(edge.target), relation="about_topic", confidence=edge.confidence
            )

        for edge in extraction.has_attribute_edges:
            self._g.add_edge(
                scope(edge.source), scope(edge.target), relation="has_attribute", confidence=edge.confidence
            )

        for edge in extraction.states_edges:
            self._g.add_edge(scope(edge.source), scope(edge.target), relation="states", confidence=edge.confidence)

        for edge in extraction.relates_to_edges:
            self._g.add_edge(
                scope(edge.source), scope(edge.target), relation=edge.relation, confidence=edge.confidence
            )

    def link_across_documents(self) -> dict:
        """Merge equivalent entity/topic/attribute nodes across documents. Returns linking stats."""
        stats: dict[str, int] = {
            "entities_merged": 0,
            "topics_merged": 0,
            "attributes_merged": 0,
        }

        # Group entity nodes by (normalized_label, entity_type).
        entity_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        for node_id, attrs in self._g.nodes(data=True):
            if attrs.get("type") == "entity":
                normalized = _normalize_label(attrs.get("label", node_id))
                entity_groups[(normalized, attrs.get("entity_type", ""))].append(node_id)

        for nodes in entity_groups.values():
            if len(nodes) > 1:
                stats["entities_merged"] += self._merge_nodes(nodes)

        # Group topic nodes by normalized label.
        topic_groups: dict[str, list[str]] = defaultdict(list)
        for node_id, attrs in self._g.nodes(data=True):
            if attrs.get("type") == "topic":
                normalized = _normalize_label(attrs.get("label", node_id))
                topic_groups[normalized].append(node_id)

        for nodes in topic_groups.values():
            if len(nodes) > 1:
                stats["topics_merged"] += self._merge_nodes(nodes)

        # Group attribute nodes by key+value.
        attr_groups: dict[str, list[str]] = defaultdict(list)
        for node_id, attrs in self._g.nodes(data=True):
            if attrs.get("type") == "attribute":
                group_key = f"{attrs.get('key', '')}:{attrs.get('value', '').lower()}"
                attr_groups[group_key].append(node_id)

        for nodes in attr_groups.values():
            if len(nodes) > 1:
                stats["attributes_merged"] += self._merge_nodes(nodes)

        return stats

    def _merge_nodes(self, nodes: list[str]) -> int:
        """Merge a list of equivalent nodes into the highest-confidence canonical node.

        Re-points all edges, unions seen_in, and removes the non-canonical nodes.
        Returns the number of nodes removed.
        """
        canonical = max(nodes, key=lambda n: self._g.nodes[n].get("confidence", 0.0))
        to_remove = set(nodes) - {canonical}
        node_map = {old: canonical for old in to_remove}

        # Union seen_in lists.
        seen_in: list[str] = list(self._g.nodes[canonical].get("seen_in", []))
        for old_id in to_remove:
            for doc_id in self._g.nodes[old_id].get("seen_in", []):
                if doc_id not in seen_in:
                    seen_in.append(doc_id)
        self._g.nodes[canonical]["seen_in"] = seen_in

        # Collect all edges that touch any node-to-remove (dedup by (src, tgt, key)).
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
    def from_json(cls, path: Path) -> "DocumentGraph":
        """Load a graph from a JSON file written by to_json."""
        data = json.loads(path.read_text())
        g = cls()
        g._g = nx.node_link_graph(data, directed=True, multigraph=True)
        return g

    def summary(self) -> dict:
        """Return high-level graph statistics."""
        node_count_by_type: dict[str, int] = defaultdict(int)
        for _, attrs in self._g.nodes(data=True):
            node_count_by_type[attrs.get("type", "unknown")] += 1

        edge_count_by_relation: dict[str, int] = defaultdict(int)
        for _, _, attrs in self._g.edges(data=True):
            edge_count_by_relation[attrs.get("relation", "unknown")] += 1

        # Document nodes are mechanically high-degree (every extracted node hangs
        # off them), so exclude them to keep the ranking meaningful.
        degrees = dict(self._g.degree())
        non_document_degrees = {
            node_id: deg for node_id, deg in degrees.items() if self._g.nodes[node_id].get("type") != "document"
        }
        top_nodes = sorted(non_document_degrees.items(), key=lambda x: x[1], reverse=True)[:10]
        god_nodes = [
            {
                "id": node_id,
                "label": self._g.nodes[node_id].get("label") or node_id,
                "degree": deg,
            }
            for node_id, deg in top_nodes
        ]

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
            "god_nodes": god_nodes,
            "documents": documents,
        }


def build_graph_from_folder(folder: Path, output: Path) -> DocumentGraph:
    """Extract and build a knowledge graph from all documents in folder."""
    import anthropic
    from tqdm import tqdm

    from opengraph_text.extract import extract_document

    document_files = sorted(
        f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in _DOCUMENT_EXTENSIONS
    )

    if not document_files:
        raise ValueError(
            f"No documents found in {folder}. Expected extensions: {', '.join(sorted(_DOCUMENT_EXTENSIONS))}"
        )

    client = anthropic.Anthropic()
    graph = DocumentGraph()

    for document_path in tqdm(document_files, desc="Extracting documents"):
        extraction = extract_document(document_path, client)
        graph.add_extraction(extraction)

    stats = graph.link_across_documents()
    print("Linking stats:", stats)

    graph.to_json(output)
    print(f"Graph saved to {output}")

    s = graph.summary()
    print(json.dumps(s, indent=2))

    return graph
