"""Build and persist a NetworkX knowledge graph from extracted image data."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import networkx as nx

from opengraph_image.schema import ImageExtraction


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _node_label(node_id: str, attrs: dict) -> str:
    """Return a short display label for a node, based on its type."""
    node_type = attrs.get("type")
    if node_type == "image":
        return Path(attrs.get("path", node_id)).name
    if node_type in ("object", "scene"):
        return attrs.get("label", node_id)
    if node_type == "attribute":
        return f"{attrs.get('key', '')}={attrs.get('value', '')}"
    if node_type == "text_span":
        text = attrs.get("text", node_id)
        return text if len(text) <= 40 else text[:40] + "..."
    return node_id


class ImageGraph:
    """Multi-image knowledge graph backed by networkx.MultiDiGraph."""

    def __init__(self) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()

    def add_extraction(self, extraction: ImageExtraction) -> None:
        """Add all nodes and edges from an ImageExtraction into the graph."""
        image_id = extraction.image.id

        def scope(node_id: str) -> str:
            """Prefix non-image node IDs with the image ID to avoid cross-extraction collisions."""
            if node_id == image_id:
                return node_id
            return f"{image_id}__{node_id}"

        self._g.add_node(
            image_id,
            type="image",
            path=extraction.image.path,
            width=extraction.image.width,
            height=extraction.image.height,
            format=extraction.image.format,
            seen_in=[image_id],
        )

        for obj in extraction.objects:
            self._g.add_node(
                scope(obj.id),
                type="object",
                label=obj.label,
                confidence=obj.confidence,
                bounding_box=obj.bounding_box,
                seen_in=[image_id],
            )

        for scene in extraction.scenes:
            self._g.add_node(
                scope(scene.id),
                type="scene",
                label=scene.label,
                confidence=scene.confidence,
                seen_in=[image_id],
            )

        for attr in extraction.attributes:
            self._g.add_node(
                scope(attr.id),
                type="attribute",
                key=attr.key,
                value=attr.value,
                confidence=attr.confidence,
                seen_in=[image_id],
            )

        for span in extraction.text_spans:
            self._g.add_node(
                scope(span.id),
                type="text_span",
                text=span.text,
                confidence=span.confidence,
                seen_in=[image_id],
            )

        for edge in extraction.contains_edges:
            self._g.add_edge(scope(edge.source), scope(edge.target), relation="contains", confidence=edge.confidence)

        for edge in extraction.in_scene_edges:
            self._g.add_edge(scope(edge.source), scope(edge.target), relation="in_scene", confidence=edge.confidence)

        for edge in extraction.has_attribute_edges:
            self._g.add_edge(scope(edge.source), scope(edge.target), relation="has_attribute", confidence=edge.confidence)

        for edge in extraction.has_text_edges:
            self._g.add_edge(scope(edge.source), scope(edge.target), relation="has_text", confidence=edge.confidence)

        for edge in extraction.related_to_edges:
            self._g.add_edge(scope(edge.source), scope(edge.target), relation=edge.relation, confidence=edge.confidence)

    def link_across_images(self) -> dict:
        """Merge equivalent entity nodes across images. Returns linking stats."""
        stats: dict[str, int] = {
            "objects_merged": 0,
            "scenes_merged": 0,
            "attributes_merged": 0,
        }

        # Group object nodes by normalized label (lowercase, strip trailing _N suffix).
        object_groups: dict[str, list[str]] = defaultdict(list)
        for node_id, attrs in self._g.nodes(data=True):
            if attrs.get("type") == "object":
                label = attrs.get("label", node_id)
                normalized = re.sub(r"_\d+$", "", label.lower())
                object_groups[normalized].append(node_id)

        for nodes in object_groups.values():
            if len(nodes) > 1:
                stats["objects_merged"] += self._merge_nodes(nodes)

        # Group scene nodes by label.
        scene_groups: dict[str, list[str]] = defaultdict(list)
        for node_id, attrs in self._g.nodes(data=True):
            if attrs.get("type") == "scene":
                label = attrs.get("label", node_id).lower()
                scene_groups[label].append(node_id)

        for nodes in scene_groups.values():
            if len(nodes) > 1:
                stats["scenes_merged"] += self._merge_nodes(nodes)

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
            for img_id in self._g.nodes[old_id].get("seen_in", []):
                if img_id not in seen_in:
                    seen_in.append(img_id)
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
    def from_json(cls, path: Path) -> "ImageGraph":
        """Load a graph from a JSON file written by to_json."""
        data = json.loads(path.read_text())
        g = cls()
        g._g = nx.node_link_graph(data, directed=True, multigraph=True)
        return g

    def resolve_image(self, ref: str) -> str:
        """Resolve an image filename or exact image-node ID to an image node ID.

        Filenames are compared as Path(ref).name against the filenames of
        stored image paths (the same names list_images reports). If no
        filename matches, ref is accepted as an exact image-node ID. No fuzzy
        or substring matching is done.

        Raises ValueError if ref matches several images or none.
        """
        filename = Path(ref).name
        matches = [
            node_id
            for node_id, attrs in self._g.nodes(data=True)
            if attrs.get("type") == "image" and filename
            and Path(attrs.get("path", node_id)).name == filename
        ]
        if len(matches) > 1:
            raise ValueError(
                f"Image filename '{filename}' is ambiguous; it matches image IDs "
                f"{', '.join(sorted(matches))}. Pass one of these IDs instead."
            )
        if matches:
            return matches[0]

        if ref in self._g.nodes and self._g.nodes[ref].get("type") == "image":
            return ref

        raise ValueError(
            f"Image not found: '{ref}'. Use a filename from list_images or an exact image-node ID."
        )

    def to_vis_data(self) -> dict:
        """Return a plain {nodes, edges} dict for visualization, read straight
        from the networkx graph (independent of the on-disk JSON key names)."""
        nodes = []
        for node_id, attrs in self._g.nodes(data=True):
            node_type = attrs.get("type", "unknown")
            node: dict = {
                "id": node_id,
                "type": node_type,
                "label": _node_label(node_id, attrs),
            }
            if "confidence" in attrs:
                node["confidence"] = attrs["confidence"]
            if "seen_in" in attrs:
                node["seen_in"] = attrs["seen_in"]
            if node_type == "image" and "path" in attrs:
                node["path"] = attrs["path"]
            elif node_type == "attribute":
                if "key" in attrs:
                    node["key"] = attrs["key"]
                if "value" in attrs:
                    node["value"] = attrs["value"]
            elif node_type == "text_span" and "text" in attrs:
                node["text"] = attrs["text"]
            nodes.append(node)

        edges = [
            {
                "source": src,
                "target": tgt,
                "relation": attrs.get("relation", "unknown"),
                "confidence": attrs.get("confidence"),
            }
            for src, tgt, attrs in self._g.edges(data=True)
        ]

        return {"nodes": nodes, "edges": edges}

    def get_provenance(self, node_id: str) -> dict:
        """Return the source images recorded for an exact node ID.

        Sources come from the node's seen_in list (an image node is its own
        source). For each source image, direct_edges lists every stored edge
        between that image and the node, in either direction. Source IDs that
        are absent or not image nodes are reported in missing_source_ids.
        These fields describe recorded associations only; they do not show
        that a merge happened or that an extraction was correct.

        Raises ValueError if node_id is not in the graph.
        """
        if node_id not in self._g.nodes:
            raise ValueError(f"Node not found: {node_id}")
        attrs = self._g.nodes[node_id]

        if attrs.get("type") == "image":
            source_ids = [node_id]
        else:
            source_ids = list(dict.fromkeys(attrs.get("seen_in", [])))

        sources = []
        missing_source_ids = []
        for source_id in source_ids:
            if source_id not in self._g.nodes or self._g.nodes[source_id].get("type") != "image":
                missing_source_ids.append(source_id)
                continue

            pairs = [(source_id, node_id)]
            if source_id != node_id:
                pairs.append((node_id, source_id))
            direct_edges = [
                {
                    "source": src,
                    "target": tgt,
                    "relation": data.get("relation", "unknown"),
                    "confidence": data.get("confidence"),
                }
                for src, tgt in pairs
                for data in (self._g.get_edge_data(src, tgt) or {}).values()
            ]

            source_attrs = self._g.nodes[source_id]
            sources.append({
                "image_id": source_id,
                "filename": Path(source_attrs.get("path", source_id)).name,
                "path": source_attrs.get("path"),
                "direct_edges": direct_edges,
            })

        return {
            "node": {
                "id": node_id,
                "type": attrs.get("type", "unknown"),
                "label": _node_label(node_id, attrs),
                "confidence": attrs.get("confidence"),
            },
            "source_count": len(source_ids),
            "multi_source": len(source_ids) > 1,
            "sources": sources,
            "missing_source_ids": missing_source_ids,
        }

    def summary(self) -> dict:
        """Return high-level graph statistics."""
        node_count_by_type: dict[str, int] = defaultdict(int)
        for _, attrs in self._g.nodes(data=True):
            node_count_by_type[attrs.get("type", "unknown")] += 1

        edge_count_by_relation: dict[str, int] = defaultdict(int)
        for _, _, attrs in self._g.edges(data=True):
            edge_count_by_relation[attrs.get("relation", "unknown")] += 1

        degrees = dict(self._g.degree())
        top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:10]
        god_nodes = [
            {
                "id": node_id,
                "label": self._g.nodes[node_id].get("label") or node_id,
                "degree": deg,
            }
            for node_id, deg in top_nodes
        ]

        images = [
            Path(attrs.get("path", node_id)).name
            for node_id, attrs in self._g.nodes(data=True)
            if attrs.get("type") == "image"
        ]

        return {
            "total_nodes": self._g.number_of_nodes(),
            "total_edges": self._g.number_of_edges(),
            "node_count_by_type": dict(node_count_by_type),
            "edge_count_by_relation": dict(edge_count_by_relation),
            "god_nodes": god_nodes,
            "images": images,
        }


def build_graph_from_folder(folder: Path, output: Path) -> ImageGraph:
    """Extract and build a knowledge graph from all images in folder."""
    import anthropic
    from tqdm import tqdm

    from opengraph_image.extract import extract_image

    image_files = sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS
    )

    if not image_files:
        raise ValueError(
            f"No image files found in {folder}. "
            f"Expected extensions: {', '.join(sorted(_IMAGE_EXTENSIONS))}"
        )

    client = anthropic.Anthropic()
    graph = ImageGraph()

    for image_path in tqdm(image_files, desc="Extracting images"):
        extraction = extract_image(image_path, client)
        graph.add_extraction(extraction)

    stats = graph.link_across_images()
    print("Linking stats:", stats)

    graph.to_json(output)
    print(f"Graph saved to {output}")

    try:
        from opengraph_image.render import render_graph_html

        html_output = render_graph_html(graph, output.parent / "graph.html")
        print(f"Graph visualization saved to {html_output}")
    except Exception as e:
        print(f"Warning: failed to render graph.html: {e}")

    s = graph.summary()
    print(json.dumps(s, indent=2))

    return graph
