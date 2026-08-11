# opengraph-image

`opengraph-image` is the v0 image-only MCP server for the OpenGraph AI project: given a folder of images it uses Claude vision to extract entities and relationships, builds a local NetworkX knowledge graph, and exposes two MCP tools (`ingest_images` and `query_graph`) so that any MCP-compatible client can ask natural-language questions over the visual content — no text documents required.

> 💡 Prefer a hosted notebook? Open the [Colab quickstart](https://colab.research.google.com/github/OpenGraphAI/opengraph-ai/blob/main/opengraph-image/notebooks/opengraph_image_quickstart.ipynb).
