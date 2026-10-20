# OpenGraph Audio

Turn audio recordings into queryable knowledge graphs (v0).

## Pipeline

```
audio → OpenRouter transcription → transcript files → opengraph-text → knowledge graph
```

Planned design: audio is transcribed through OpenRouter (provisional; see
[Configuration](#configuration)), the transcripts are written as text files, and
[opengraph-text](../opengraph-text) handles extraction, graph building,
querying, and rendering.

## Directory Structure

```bash
.
├── README.md
├── pyproject.toml
├── .env.example
├── src
│   └── opengraph_audio
│       ├── __init__.py        # lazy entry points: main(), mcp_main()
│       ├── cli.py             # Typer CLI
│       ├── graph.py           # transcripts → opengraph-text graph
│       ├── schema.py          # transcript models
│       ├── server.py          # MCP server
│       ├── transcribe.py      # OpenRouter transcription
│       └── transcript_io.py   # transcript file read/write
└── tests
```

## Status

This package currently contains only the initial scaffold. **Transcription is not implemented yet.**
The modules contain only docstrings, and the entry points in `__init__.py` point to
`cli.app` and `server.serve`, which do not exist yet, so the `opengraph-audio` and
`opengraph-audio-mcp` commands will fail until later steps implement them.

## Setup

```bash
cd opengraph-audio
uv sync
cp .env.example .env   # fill in OPENROUTER_API_KEY and ANTHROPIC_API_KEY
```

`opengraph-text` is installed as an editable dependency from `../opengraph-text`.

## Configuration

> **Provisional:** the OpenRouter settings below (`OPENROUTER_API_KEY`,
> `OPENGRAPH_AUDIO_MODEL`, `OPENROUTER_BASE_URL`) are placeholders. They may
> change once Andrea confirms the Azure setup.

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | Transcription via OpenRouter |
| `ANTHROPIC_API_KEY` | Graph extraction and querying (opengraph-text) |
| `OPENGRAPH_AUDIO_MODEL` | Transcription model (default `microsoft/mai-transcribe-2`) |
| `OPENROUTER_BASE_URL` | OpenRouter API base URL |

## Entry points

- `opengraph-audio` — CLI
- `opengraph-audio-mcp` — MCP server (stdio)
