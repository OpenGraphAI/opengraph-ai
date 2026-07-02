<div align="center">


# 💡 OpenGraph AI

### *Turning heterogeneous data into a queryable knowledge graph*

<p>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-6E56CF?style=for-the-badge&logo=anthropic&logoColor=white" alt="MCP Compatible"></a>
  <a href="https://github.com/OpenGraphAI/opengraph-ai/pulls?q=is%3Apr+is%3Aclosed"><img src="https://img.shields.io/github/issues-pr-closed/OpenGraphAI/opengraph-ai?style=for-the-badge&color=blueviolet&label=PRs%20closed" alt="Closed Pull Requests"></a>
  <a href="https://github.com/OpenGraphAI/opengraph-ai/stargazers"><img src="https://img.shields.io/github/stars/OpenGraphAI/opengraph-ai?style=for-the-badge&color=yellow&label=stars" alt="GitHub Stars"></a>
</p>
<p>
  <a href="https://discord.gg/PGFqf5amy6"><img src="https://img.shields.io/badge/Discord-Join%20us-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord Community"></a>
  <a href="https://huggingface.co/OpenGraph-AI"><img src="https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-OpenGraph--AI-FFD21E?style=for-the-badge" alt="Hugging Face"></a>
  <a href="https://www.opengraphai.io"><img src="https://img.shields.io/badge/Website-opengraphai.io-0A66C2?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Website"></a>
</p>


**`OpenGraph-AI`** turns heterogeneous data including table, text, image, audio and video into queryable knowledge/context graphs to support complex reasoning and retrieval for AI systems, and let users build effective and trusted AI agents.

The v1 version of **`opengraph-image`** builds an MCP server and CLI that extract entities including **node** and **edge**, and relationships from images.

**`opengraph-image`** builds a local knowledge graph, and let you ask natural-language questions over your visual data — no captions, no text documents, no manual labeling required.

</div>

---

## ✨ What is **`opengraph-image`**?

Most "image search" stops at keywords and captions. `opengraph-image` goes further: it looks at *every image in a folder*, identifies the objects, scenes, and attributes in each one, and links them together into a **knowledge graph** — the same kind of structured representation that powers serious reasoning systems.

Once built, that graph is exposed through **five simple MCP tools** so any MCP-compatible agent (Claude Code, Claude Desktop, Cursor, etc.) can reason over your images conversationally:

- 🏗️ `build_graph` — point it at a folder, get back a fully built knowledge graph
- 🧠 `query_graph` — ask it anything, get back an answer grounded in the graph
- 🖼️ `get_image_entities` — drill into one image and see every entity and relationship it contains
- 📝 `list_images` — see every image currently represented in the graph
- 📊 `graph_summary` — get high-level stats about the graph at a glance

No vector database. No manual tagging. No text documents required — just images in, structured understanding out.

---

## 🚀 Quickstart: run it from your own terminal

Try the whole pipeline locally before wiring it into an agent.

```bash
# 1. Move into the package and install it
cd opengraph-image
pip install -e .

# 2. Set your Anthropic API key (used for vision extraction + querying)
cp .env.example .env
echo 'ANTHROPIC_API_KEY=your_anthropic_api_key_here' >> .env

# 3. Build a knowledge graph from a folder of images
opengraph-image build ./tests/sample_images/test_photos
# -> writes ./tests/sample_images/test_photos/opengraph-out/graph.json

# 4. Inspect what got extracted
opengraph-image summary ./tests/sample_images/test_photos

# 5. Ask a natural-language question over the graph
opengraph-image query "What's happening in the park photos?" \
  --graph ./tests/sample_images/test_photos/opengraph-out/graph.json
```

That's it — four commands and you've gone from raw JPEGs to a graph you can interrogate in plain English.

---

## 🔌 Using `opengraph-image` as an MCP server

This is where it gets fun: instead of running the CLI yourself, let your AI coding agent drive the graph for you.

**Step 1 — Install the package** (same as above):

```bash
cd opengraph-image
pip install -e .
```

**Step 2 — Register the MCP server with Claude Code:**

```bash
claude mcp add opengraph-image -- opengraph-image-mcp
```

**Step 3 — Confirm it's connected:**

```bash
claude mcp list
# opengraph-image should show up as ✓ connected
```

**Step 4 — Just ask, in natural language (English for now), inside your Claude Chat session:**

> 🗣️ "Build a knowledge graph from the images in `./photos` and tell me which ones contain people."

> 🗣️ "Query the graph — which images show a dog near a body of water?"

> 🗣️ "List every image you've ingested and summarize the graph."

Claude will call `build_graph`, `query_graph`, `get_image_entities`, `list_images`, and `graph_summary` on your behalf. You never have to touch JSON or write a query language. 🎉

> 💡 **Tip:** `opengraph-image` resolves graphs by folder, so as long as you tell the agent which folder your images live in, it'll find (or build) the right `opengraph-out/graph.json` automatically.

---

## 🧰 Available MCP Tools

| Tool | What it does |
|---|---|
| `build_graph(folder_path)` | Ingests every image in a folder and builds the knowledge graph |
| `query_graph(question, graph_path)` | Answers a natural-language question grounded in the graph |
| `get_image_entities(image_filename, graph_path)` | Returns all entities/edges connected to one image |
| `list_images(graph_path)` | Lists every image currently represented in the graph |
| `graph_summary(graph_path)` | Returns high-level stats about the graph |

---

## ⚙️ Use Cases (10x moonshot ideas)

### 🤖 Robotics

- Autonomous robots can use knowledge graphs to understand relationships between objects, locations, and tasks in their environment.
- Support task planning for humans through coding and organization. 
- Improves decision making through systems and binary code.
- Improves efficiency of tasks. 
- Robots can perform task planning by reasoning about object dependencies, required tools, and action sequences.
- Multi-robot systems can share a common knowledge graph to coordinate activities and exchange contextual information.
- Warehouse and manufacturing robots can use graph-based representations to track inventory, equipment, and workflow dependencies.

### 🖼️ Image Search

- Images can be converted into graph structures that connect detected objects, scenes, and attributes
- Users can search for images based on relationships, such as "person riding a bicycle near a building" rather than simple keyword matching
- Knowledge graphs improve image retrieval by linking visual concepts with semantic meaning.

### 🎬 Video Search

- Video content can be represented as graphs connecting people, objects, actions, locations, and events across frames
- Users can search for specific events, such as a person entering a room and picking up a package
- Graph-based video search enables more accurate retrieval of complex activities and temporal relationships
- AI agents can reason over video-derived knowledge graphs to identify patterns, anomalies, and event sequences

### 🔔 Multimodal AI Agents

- AI agents can combine information from text, images, audio, and video into a unified knowledge graph
- Structured graph representations improve retrieval, reasoning, and explainability for complex AI workflows
- Knowledge graphs provide traceable relationships between entities, helping agents make more informed decisions

---

## 🤝 Contributing

`OpenGraph AI` is early, opinionated, and built in the open source, meaning your ideas can shape where it goes next. We'd love to have you.

- 🐛 **Found a bug or have a feature idea?** [Open an issue](https://github.com/PLACEHOLDER_ORG/PLACEHOLDER_REPO/issues/new) — reproducible steps and context help us move fast.
- 🔧 **Want to fix something yourself?** Fork the repo, make your change under `opengraph-image/`, add a test, and [open a pull request](https://github.com/PLACEHOLDER_ORG/PLACEHOLDER_REPO/pulls). We review fast and merge often.
- 💬 **Want to talk it through first?** Hop into our [Discord](https://discord.gg/PLACEHOLDER_INVITE) — describe what you're thinking and we'll help you find the right entry point.
- ✉️ **Prefer email?** Reach out directly at [team@opengraphai.io](mailto:team@opengraphai.io) — we read everything and reply to humans, not just issues.
- 🙋 **Want to reach a maintainer 1:1?** Don't be shy — tag us in an issue or DM us on Discord. We're genuinely excited to hear what you're building on top of this.

No contribution is too small: typo fixes, new test images, extraction edge cases, and wild "what if it could also do X" ideas are all welcome. 🌱

---

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).
