# OpenGraph Text

## Directory Structure

```bash
.
├── README.md               
├── pyproject.toml          
├── src
│   └── opengraph_text
│       ├── __init__.py
│       ├── cli.py
│       ├── extract.py
│       ├── graph.py
│       ├── query.py
│       ├── schema.py
│       └── server.py
└── tests
    ├── test_exract.py
    └── test_graph.py
```

All files under `src\opengraph_text\` folder are just scaffolds as of now.
* `__init.py` currently contains a default `main()` function.
* `cli.py` currently contains a `app()` function for testing entry point setting.
* `server.py` currently contains a `main()` function for testing entry point setting.
* All other files that are not mentioned only contains a document header.

All files under `tests\` are currently empty, without document headers.

The `.env.example` file contains a placeholder `ANTHROPIC_API_KEY` where could later be used to fit API keys.