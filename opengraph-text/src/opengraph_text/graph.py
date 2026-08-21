"""Build and persist a NetworkX knowledge graph from text data."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)  # .env wins over shell env vars

import anthropic
import networkx as nx
from tqdm import tqdm

from .extract import extract_document
from .schema import DocumentExtraction

_TRAILING_DIGITS_RE = re.compile(r"_?\d+$")
_ORG_SUFFIX_RE = re.compile(r"(?:_(?:inc|corp|co))+$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

DOCUMENT_EXTENSIONS = (".txt", ".md", ".pdf")


def _normalize_label(label: str) -> str:
    """Normalize a label for cross-document identity matching.

    Lowercases, snake_cases, and strips trailing disambiguator digits and
    common organization suffixes (_inc, _corp, _co).
    """

    normalized = _NON_ALNUM_RE.sub("_", label.lower()).strip("_")
    normalized = _TRAILING_DIGITS_RE.sub("", normalized)
    normalized = _ORG_SUFFIX_RE.sub("", normalized)
    return normalized


def _local_id_map(extraction: DocumentExtraction) -> dict[str, str]:
    """Map each node id as referenced within an extraction to its graph node key.

    Node ids assigned by the extractor are only unique within a single
    document, so every non-document node is namespaced with its document id
    to keep it distinct in the merged graph until `link_across_documents`
    decides to merge it with an equivalent node from another document.
    """

    doc_id = extraction.document.id
    id_map = {doc_id: doc_id}
    for node in (
        *extraction.entities,
        *extraction.topics,
        *extraction.attributes,
        *extraction.claims,
    ):
        id_map[node.id] = f"{doc_id}:{node.id}"
    return id_map


class DocumentGraph:
    """A multi-document knowledge graph built from `DocumentExtraction`s."""

    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()

    def add_extraction(self, extraction: DocumentExtraction) -> None:
        doc_id = extraction.document.id
        id_map = _local_id_map(extraction)

        self.graph.add_node(
            doc_id,
            type="document",
            path=extraction.document.path,
            word_count=extraction.document.word_count,
            format=extraction.document.format,
            seen_in=[doc_id],
        )

        for entity in extraction.entities:
            self.graph.add_node(
                id_map[entity.id],
                type="entity",
                label=entity.label,
                entity_type=entity.entity_type,
                confidence=entity.confidence,
                seen_in=[doc_id],
            )

        for topic in extraction.topics:
            self.graph.add_node(
                id_map[topic.id],
                type="topic",
                label=topic.label,
                confidence=topic.confidence,
                seen_in=[doc_id],
            )

        for attribute in extraction.attributes:
            self.graph.add_node(
                id_map[attribute.id],
                type="attribute",
                key=attribute.key,
                value=attribute.value,
                confidence=attribute.confidence,
                seen_in=[doc_id],
            )

        for claim in extraction.claims:
            self.graph.add_node(
                id_map[claim.id],
                type="claim",
                text=claim.text,
                confidence=claim.confidence,
                seen_in=[doc_id],
            )

        for edge in extraction.contains_edges:
            self.graph.add_edge(
                id_map[edge.source], id_map[edge.target],
                relation="contains", confidence=edge.confidence,
            )

        for edge in extraction.about_topic_edges:
            self.graph.add_edge(
                id_map[edge.source], id_map[edge.target],
                relation="about_topic", confidence=edge.confidence,
            )

        for edge in extraction.has_attribute_edges:
            self.graph.add_edge(
                id_map[edge.source], id_map[edge.target],
                relation="has_attribute", confidence=edge.confidence,
            )

        for edge in extraction.states_edges:
            self.graph.add_edge(
                id_map[edge.source], id_map[edge.target],
                relation="states", confidence=edge.confidence,
            )

        for edge in extraction.relates_to_edges:
            self.graph.add_edge(
                id_map[edge.source], id_map[edge.target],
                relation=edge.relation, confidence=edge.confidence,
            )

    def _merge_nodes(self, node_ids: list[str]) -> str:
        """Merge a group of equivalent nodes into a single canonical node.

        The highest-confidence node is kept as canonical. `seen_in` lists are
        unioned, incident edges are re-pointed to the canonical node
        (dropping any resulting self-loops), and the other nodes are removed.
        """

        graph = self.graph
        canonical = sorted(
            node_ids, key=lambda n: (-graph.nodes[n]["confidence"], n)
        )[0]
        others = [n for n in node_ids if n != canonical]
        id_set = set(node_ids)

        seen_in = list(graph.nodes[canonical].get("seen_in", []))
        for node_id in others:
            for doc_id in graph.nodes[node_id].get("seen_in", []):
                if doc_id not in seen_in:
                    seen_in.append(doc_id)

        edges_to_add: list[tuple[str, str, dict]] = []
        for node_id in others:
            for u, _v, data in graph.in_edges(node_id, data=True):
                new_u = canonical if u in id_set else u
                edges_to_add.append((new_u, canonical, data))
            for _u, v, data in graph.out_edges(node_id, data=True):
                new_v = canonical if v in id_set else v
                edges_to_add.append((canonical, new_v, data))

        for node_id in others:
            graph.remove_node(node_id)

        graph.nodes[canonical]["seen_in"] = seen_in

        for u, v, data in edges_to_add:
            if u != v:
                graph.add_edge(u, v, **data)

        return canonical

    def link_across_documents(self) -> dict:
        """Merge equivalent entity/topic/attribute nodes across documents.

        Returns a dict of how many nodes of each kind were merged away.
        """

        entity_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        topic_groups: dict[str, list[str]] = defaultdict(list)
        attribute_groups: dict[tuple[str, str], list[str]] = defaultdict(list)

        for node_id, data in self.graph.nodes(data=True):
            node_type = data.get("type")
            if node_type == "entity":
                key = (_normalize_label(data["label"]), data["entity_type"])
                entity_groups[key].append(node_id)
            elif node_type == "topic":
                key = _normalize_label(data["label"])
                topic_groups[key].append(node_id)
            elif node_type == "attribute":
                key = (data["key"], data["value"])
                attribute_groups[key].append(node_id)

        stats = {"entities_merged": 0, "topics_merged": 0, "attributes_merged": 0}

        for node_ids in entity_groups.values():
            if len(node_ids) > 1:
                self._merge_nodes(node_ids)
                stats["entities_merged"] += len(node_ids) - 1

        for node_ids in topic_groups.values():
            if len(node_ids) > 1:
                self._merge_nodes(node_ids)
                stats["topics_merged"] += len(node_ids) - 1

        for node_ids in attribute_groups.values():
            if len(node_ids) > 1:
                self._merge_nodes(node_ids)
                stats["attributes_merged"] += len(node_ids) - 1

        return stats

    def to_json(self, path: Path) -> None:
        data = nx.node_link_data(self.graph, edges="edges")
        Path(path).write_text(json.dumps(data, indent=2))

    @classmethod
    def from_json(cls, path: Path) -> "DocumentGraph":
        data = json.loads(Path(path).read_text())
        instance = cls()
        instance.graph = nx.node_link_graph(
            data, directed=True, multigraph=True, edges="edges"
        )
        return instance

    def to_vis_data(self) -> dict:
        """Return a plain {nodes, edges} dict for visualization, read straight
        from self.graph (independent of the on-disk JSON key names)."""

        def label_for(node_id: str, data: dict) -> str:
            node_type = data.get("type")
            if node_type == "document":
                return Path(data.get("path", node_id)).name
            if node_type in ("entity", "topic"):
                return data.get("label", node_id)
            if node_type == "attribute":
                return f"{data.get('key', '')}={data.get('value', '')}"
            if node_type == "claim":
                text = data.get("text", node_id)
                return text if len(text) <= 40 else text[:40] + "..."
            return node_id

        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            node_type = data.get("type", "unknown")
            node: dict = {
                "id": node_id,
                "type": node_type,
                "label": label_for(node_id, data),
            }
            if "confidence" in data:
                node["confidence"] = data["confidence"]
            if "seen_in" in data:
                node["seen_in"] = data["seen_in"]
            if node_type == "document" and "path" in data:
                node["path"] = data["path"]
            elif node_type == "entity" and "entity_type" in data:
                node["entity_type"] = data["entity_type"]
            elif node_type == "attribute":
                if "key" in data:
                    node["key"] = data["key"]
                if "value" in data:
                    node["value"] = data["value"]
            elif node_type == "claim" and "text" in data:
                node["text"] = data["text"]
            nodes.append(node)

        edges = [
            {
                "source": u,
                "target": v,
                "relation": data.get("relation", "unknown"),
                "confidence": data.get("confidence"),
            }
            for u, v, data in self.graph.edges(data=True)
        ]

        return {"nodes": nodes, "edges": edges}

    def summary(self) -> dict:
        graph = self.graph

        node_count_by_type: dict[str, int] = defaultdict(int)
        documents: list[str] = []
        for node_id, data in graph.nodes(data=True):
            node_type = data.get("type", "unknown")
            node_count_by_type[node_type] += 1
            if node_type == "document":
                documents.append(node_id)

        edge_count_by_relation: dict[str, int] = defaultdict(int)
        for _u, _v, data in graph.edges(data=True):
            edge_count_by_relation[data.get("relation", "unknown")] += 1

        non_document_nodes = [
            node_id for node_id, data in graph.nodes(data=True)
            if data.get("type") != "document"
        ]
        god_nodes = sorted(
            non_document_nodes,
            key=lambda n: graph.in_degree(n) + graph.out_degree(n),
            reverse=True,
        )[:10]

        return {
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "node_count_by_type": dict(node_count_by_type),
            "edge_count_by_relation": dict(edge_count_by_relation),
            "god_nodes": [
                {
                    "id": node_id,
                    "degree": graph.in_degree(node_id) + graph.out_degree(node_id),
                    "type": graph.nodes[node_id].get("type"),
                    "label": graph.nodes[node_id].get("label")
                    or graph.nodes[node_id].get("value")
                    or graph.nodes[node_id].get("text"),
                }
                for node_id in god_nodes
            ],
            "documents": sorted(documents),
        }


def build_graph_from_folder(folder: Path, output: Path) -> DocumentGraph:
    """Extract every supported document in `folder` and build a linked graph."""

    folder = Path(folder)
    document_paths = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in DOCUMENT_EXTENSIONS
    )

    if not document_paths:
        raise ValueError(
            f"No documents found in {folder}. Expected files with one of these "
            f"extensions: {', '.join(DOCUMENT_EXTENSIONS)}"
        )

    client = anthropic.Anthropic()

    graph = DocumentGraph()
    for document_path in tqdm(document_paths, desc="Extracting documents"):
        extraction = extract_document(document_path, client)
        graph.add_extraction(extraction)

    stats = graph.link_across_documents()
    print(f"Linked across documents: {json.dumps(stats)}")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    graph.to_json(output)

    try:
        from .render import render_graph_html

        html_output = render_graph_html(graph, output.parent / "graph.html")
        print(f"Graph visualization saved to {html_output}")
    except Exception as e:
        print(f"Warning: failed to render graph.html: {e}")

    print(json.dumps(graph.summary(), indent=2))

    return graph
