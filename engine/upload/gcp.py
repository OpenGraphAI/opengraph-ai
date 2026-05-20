"""Upload dataset files or folders to Google Cloud Storage.

This module provides reusable upload helpers for dataset directories, plus a
small CLI entrypoint that can be shared by scripts or future CLI commands.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_GCS_PREFIX = "opengraph-ai/input"


def _load_env_file(env_path: Path) -> None:
    """Load KEY=VALUE pairs into ``os.environ`` if they are not already set."""
    if not env_path.exists() or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_local_env() -> None:
    """Load ``.env.local`` or ``.env`` from the current project directory."""
    cwd = Path.cwd()
    _load_env_file(cwd / ".env.local")
    _load_env_file(cwd / ".env")


def iter_source_files(source: Path) -> list[Path]:
    """Return files to upload from a file or recursively from a folder."""
    if source.is_file():
        return [source]
    return sorted(path for path in source.rglob("*") if path.is_file())


def destination_blob_name(source: Path, file_path: Path, prefix: str) -> str:
    """Build the destination blob path in GCS."""
    clean_prefix = prefix.strip("/")
    if source.is_file():
        relative = Path(source.name)
    else:
        relative = Path(source.name) / file_path.relative_to(source)
    return f"{clean_prefix}/{relative.as_posix()}"


def upload_dataset_to_gcs(
    source: Path,
    *,
    project_id: str,
    bucket_name: str,
    prefix: str = DEFAULT_GCS_PREFIX,
) -> int:
    """Upload a dataset file or folder to GCS and return the uploaded count."""
    try:
        from google.auth.exceptions import DefaultCredentialsError
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is not installed. Install project dependencies first."
        ) from exc

    try:
        client = storage.Client(project=project_id)
    except DefaultCredentialsError as exc:
        raise RuntimeError(
            "GCP credentials not found. Run 'gcloud auth application-default login' "
            "or set GOOGLE_APPLICATION_CREDENTIALS."
        ) from exc

    bucket = client.bucket(bucket_name)
    files = iter_source_files(source)
    uploaded = 0

    for file_path in files:
        blob_name = destination_blob_name(source, file_path, prefix)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(file_path))
        uploaded += 1
        print(f"Uploaded {file_path} -> gs://{bucket_name}/{blob_name}")

    return uploaded


def upload_file_to_gcs(
    local_file: Path,
    *,
    bucket_name: str,
    blob_name: str,
    project_id: str | None = None,
) -> str:
    """Upload one local file to GCS and return ``gs://`` URI."""
    try:
        from google.auth.exceptions import DefaultCredentialsError
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is not installed. Install project dependencies first."
        ) from exc

    if not local_file.exists() or not local_file.is_file():
        raise ValueError(f"Local file does not exist: {local_file}")

    try:
        client = storage.Client(project=project_id)
    except DefaultCredentialsError as exc:
        raise RuntimeError(
            "GCP credentials not found. Run 'gcloud auth application-default login' "
            "or set GOOGLE_APPLICATION_CREDENTIALS."
        ) from exc

    clean_blob_name = blob_name.strip("/")
    blob = client.bucket(bucket_name).blob(clean_blob_name)
    blob.upload_from_filename(str(local_file))
    return f"gs://{bucket_name}/{clean_blob_name}"


def upload_file_content_to_gcs(
    file_content: bytes,
    *,
    filename: str,
    bucket_name: str,
    blob_name: str,
    project_id: str | None = None,
) -> str:
    """Upload file bytes directly to GCS and return ``gs://`` URI.
    
    This is used when Claude uploads files directly without a local filesystem path.
    """
    try:
        from google.auth.exceptions import DefaultCredentialsError
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is not installed. Install project dependencies first."
        ) from exc

    try:
        client = storage.Client(project=project_id)
    except DefaultCredentialsError as exc:
        raise RuntimeError(
            "GCP credentials not found. Run 'gcloud auth application-default login' "
            "or set GOOGLE_APPLICATION_CREDENTIALS."
        ) from exc

    clean_blob_name = blob_name.strip("/")
    blob = client.bucket(bucket_name).blob(clean_blob_name)
    blob.upload_from_string(file_content)
    return f"gs://{bucket_name}/{clean_blob_name}"


def download_file_from_gcs(
    gcs_uri: str,
    *,
    project_id: str | None = None,
) -> bytes:
    """Download file content from GCS by gs:// URI and return bytes.
    
    Parses gs://bucket/blob/path URIs and downloads the content.
    """
    try:
        from google.auth.exceptions import DefaultCredentialsError
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is not installed. Install project dependencies first."
        ) from exc

    # Parse gs://bucket/path format
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI, got: {gcs_uri}")

    # Remove gs:// prefix
    path_part = gcs_uri[5:]
    bucket_name, _, blob_name = path_part.partition("/")

    if not bucket_name or not blob_name:
        raise ValueError(f"Invalid GCS URI format: {gcs_uri}")

    try:
        client = storage.Client(project=project_id)
    except DefaultCredentialsError as exc:
        raise RuntimeError(
            "GCP credentials not found. Run 'gcloud auth application-default login' "
            "or set GOOGLE_APPLICATION_CREDENTIALS."
        ) from exc

    blob = client.bucket(bucket_name).blob(blob_name)
    return blob.download_as_bytes()


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for dataset uploads."""
    parser = argparse.ArgumentParser(
        description="Upload a dataset file or folder to Google Cloud Storage.",
    )
    parser.add_argument(
        "source",
        help="Path to the dataset file or folder to upload.",
    )
    parser.add_argument(
        "--bucket",
        default=None,
        help="Override GCS bucket name. Defaults to GCS_BUCKET from .env.local.",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Override GCP project ID. Defaults to GCP_PROJECT_ID from .env.local.",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help=(
            "Destination folder prefix inside the bucket "
            f"(default: {DEFAULT_GCS_PREFIX})."
        ),
    )
    parser.add_argument(
        "--credentials",
        default=None,
        help=(
            "Path to a Google service-account JSON key file. "
            "If omitted, GOOGLE_APPLICATION_CREDENTIALS or ADC will be used."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the dataset upload CLI."""
    load_local_env()
    parser = build_parser()
    args = parser.parse_args(argv)

    source = Path(args.source)
    if not source.exists():
        print(f"Error: source not found: {source}", file=sys.stderr)
        return 1

    project_id = args.project_id or os.environ.get("GCP_PROJECT_ID")
    bucket_name = args.bucket or os.environ.get("GCS_BUCKET")
    prefix = args.prefix or os.environ.get("GCS_PREFIX", DEFAULT_GCS_PREFIX)
    credentials_path = args.credentials or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    if credentials_path:
        expanded_credentials_path = str(Path(credentials_path).expanduser())
        if not Path(expanded_credentials_path).exists():
            print(
                f"Error: credentials file not found: {expanded_credentials_path}",
                file=sys.stderr,
            )
            return 1
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = expanded_credentials_path

    if not project_id:
        print(
            "Error: missing GCP_PROJECT_ID. Set it in .env.local or pass --project-id.",
            file=sys.stderr,
        )
        return 1
    if not bucket_name:
        print(
            "Error: missing GCS_BUCKET. Set it in .env.local or pass --bucket.",
            file=sys.stderr,
        )
        return 1

    try:
        uploaded = upload_dataset_to_gcs(
            source,
            project_id=project_id,
            bucket_name=bucket_name,
            prefix=prefix,
        )
    except Exception as exc:
        print(f"Upload failed: {exc}", file=sys.stderr)
        if not credentials_path:
            print(
                "Tip: set GOOGLE_APPLICATION_CREDENTIALS in .env.local or pass --credentials /path/to/key.json",
                file=sys.stderr,
            )
        return 1

    print(f"Done. Uploaded {uploaded} file(s) to gs://{bucket_name}/{prefix.strip('/')}/")
    return 0
