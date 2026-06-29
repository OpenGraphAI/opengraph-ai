"""OpenGraph Table: Extract and query knowledge graphs from tabular data."""

__version__ = "0.1.0"


def main() -> None:
    """CLI entrypoint."""
    from opengraph_table.cli import main as cli_main

    cli_main()


def mcp_main() -> None:
    """MCP server entrypoint."""
    from opengraph_table.server import serve

    serve()
