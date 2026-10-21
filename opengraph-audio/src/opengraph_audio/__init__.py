"""opengraph-audio: audio-to-knowledge-graph MCP server (v0)."""


def main() -> None:
    from opengraph_audio.cli import app
    app()


def mcp_main() -> None:
    from opengraph_audio.server import serve
    serve()
