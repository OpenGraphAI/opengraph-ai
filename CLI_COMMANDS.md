# OpenGraph AI CLI Commands

The CLI now uses Cloud Run for graph processing and GCS for storage.

Default project/bucket values in the current workspace are:

- `GCP_PROJECT_ID=opengraph-staging`
- `GCP_PROJECT_NAME=opengraph staging`
- `GCS_BUCKET=davidluobucket`
- `OPENGRAPH_API_URL=https://opengraph-ai-255275373065.us-central1.run.app`

Use:

```bash
python -m cli ...
```

or:

```bash
opengraph ...
```

---

## 1. Version

```bash
python -m cli --version
```

---

## 2. Upload a local file to GCS

Uploads one local file to:

`gs://<bucket>/opengraph-ai/input/<dataset>/<filename>`

```bash
python -m cli upload <file-path> <dataset_name> \
	--bucket <bucket> \
	--project-id <project-id>
```

Example:

```bash
python -m cli upload /tmp/note.txt cloudrun-test-20260519 \
	--bucket davidluobucket \
	--project-id opengraph-staging
```

---

## 3. Extract text/pdf through Cloud Run

This command calls the Cloud Run service and reads a `gs://` input URI.

```bash
python -m cli extract text \
	gs://<bucket>/opengraph-ai/input/<dataset>/<file>.txt \
	--output-gcs-uri gs://<bucket>/opengraph-ai/output/<dataset> \
	--project-id <project-id> \
	--api-url https://opengraph-ai-255275373065.us-central1.run.app
```

PDF example:

```bash
python -m cli extract text \
	gs://<bucket>/opengraph-ai/input/<dataset>/<file>.pdf \
	--output-gcs-uri gs://<bucket>/opengraph-ai/output/<dataset> \
	--project-id <project-id>
```

If `OPENGRAPH_API_URL` is set, `--api-url` is optional.

---

## 4. Extract a table dataset through Cloud Run

Reads a dataset folder from GCS, performs extraction on Cloud Run, stores the graph in Neo4j, and writes JSON/PNG artifacts back to GCS.

```bash
python -m cli extract tables-gcs <dataset_name> \
	--bucket <bucket> \
	--project-id <project-id> \
	--gcs-prefix opengraph-ai/input \
	--output-prefix opengraph-ai/output
```

---

## 5. GraphDB end-to-end from GCS

Runs the Cloud Run graph workflow for a dataset already uploaded to GCS.

```bash
python -m cli graphdb from-gcs <dataset_name> \
	--bucket <bucket> \
	--project-id <project-id> \
	--input-prefix opengraph-ai/input \
	--output-prefix opengraph-ai/output
```

---

## Notes

- `upload` is active again for local-file-to-GCS uploads.
- `graphdb push` and `graphdb pull` remain disabled in GCP-only mode.
- The MCP toolset mirrors the same Cloud Run-backed workflow:
  - `list_gcp_data`
  - `upload_data_to_gcp`
  - `extract_graph_from_gcp`
  - `full_upload_and_extract`

---

## 6. Quick demo

This is the same flow that was tested successfully in the workspace:

```bash
python -m cli upload /tmp/opengraph_cloudrun_note.txt cloudrun-test-20260519 \
	--bucket davidluobucket \
	--project-id opengraph-staging
```

```bash
python -m cli extract text \
	gs://davidluobucket/opengraph-ai/input/cloudrun-test-20260519/opengraph_cloudrun_note.txt \
	--output-gcs-uri gs://davidluobucket/opengraph-ai/output/cloudrun-test-20260519 \
	--project-id opengraph-staging
```

Expected result:

- Graph JSON written to `gs://davidluobucket/opengraph-ai/output/cloudrun-test-20260519/graph.json`
- Graph PNG written to `gs://davidluobucket/opengraph-ai/output/cloudrun-test-20260519/graph.png`
- Extraction succeeds via Cloud Run
