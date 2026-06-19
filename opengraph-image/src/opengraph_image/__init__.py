"""opengraph-image: image-only knowledge-graph MCP server (v0)."""


def main() -> None:
    from opengraph_image.cli import app
    app()


def mcp_main() -> None:
    from opengraph_image.server import serve
    serve()
