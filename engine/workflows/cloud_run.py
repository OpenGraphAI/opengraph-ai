"""Cloud Run API client helpers for OpenGraph graph workflows."""

from __future__ import annotations

import json
import os
from urllib import error
from urllib import request

from engine.config import load_env_config

_DEFAULT_TIMEOUT_SECONDS = 3600


def _resolve_api_url(api_url: str | None = None) -> str:
    load_env_config()
    resolved = api_url or os.environ.get("OPENGRAPH_API_URL")
    if not resolved:
        raise EnvironmentError(
            "OPENGRAPH_API_URL is not set. Provide --api-url or set OPENGRAPH_API_URL in env."
        )
    return resolved.rstrip("/")


def _post_json(url: str, payload: dict, timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Cloud Run request failed ({exc.code}): {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Cloud Run request failed: {exc}") from exc


def run_graph_from_gcs_via_cloud_run(
    *,
    dataset: str,
    bucket: str | None = None,
    input_prefix: str = "opengraph-ai/input",
    output_prefix: str = "opengraph-ai/output",
    model: str | None = None,
    project_id: str | None = None,
    schema_view: bool = False,
    api_url: str | None = None,
) -> dict:
    base = _resolve_api_url(api_url)
    payload = {
        "dataset": dataset,
        "bucket": bucket,
        "input_prefix": input_prefix,
        "output_prefix": output_prefix,
        "model": model,
        "project_id": project_id,
        "schema_view": schema_view,
    }
    return _post_json(f"{base}/graph/from-gcs", payload)


def run_graph_from_gcs_file_via_cloud_run(
    *,
    dataset: str,
    file_name: str,
    bucket: str | None = None,
    input_prefix: str = "opengraph-ai/input",
    output_prefix: str = "opengraph-ai/output",
    project_id: str | None = None,
    model: str | None = None,
    api_url: str | None = None,
) -> dict:
    base = _resolve_api_url(api_url)
    payload = {
        "dataset": dataset,
        "file_name": file_name,
        "bucket": bucket,
        "input_prefix": input_prefix,
        "output_prefix": output_prefix,
        "project_id": project_id,
        "model": model,
    }
    return _post_json(f"{base}/graph/from-gcs-file", payload)
