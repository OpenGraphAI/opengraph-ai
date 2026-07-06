"""Command-line interface for OpenGraph Text."""

from __future__ import annotations

import argparse
from pathlib import Path

import anthropic

from opengraph_text.extract import extract_document
from opengraph_text.graph import build_graph_from_folder
from opengraph_text.query import query_graph_file


def main() -> None:
    """Run the OpenGraph Text CLI."""
    parser = argparse.ArgumentParser(prog="opengraph-text")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Extract a graph from one text document.")
    extract_parser.add_argument("document_path", type=Path)

    build_parser = subparsers.add_parser("build", help="Build a graph from a folder of text documents.")
    build_parser.add_argument("folder", type=Path)
    build_parser.add_argument("output", type=Path)

    query_parser = subparsers.add_parser("query", help="Query a saved text graph.")
    query_parser.add_argument("graph_path", type=Path)
    query_parser.add_argument("question")

    args = parser.parse_args()
    client = anthropic.Anthropic()

    if args.command == "extract":
        extraction = extract_document(args.document_path, client)
        print(extraction.model_dump_json(indent=2))
    elif args.command == "build":
        build_graph_from_folder(args.folder, args.output)
    elif args.command == "query":
        result = query_graph_file(args.graph_path, args.question, client)
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()