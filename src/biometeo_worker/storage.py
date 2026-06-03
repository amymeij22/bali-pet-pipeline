"""Upload arsip hasil run ke Supabase Storage (S3-compatible)."""

from __future__ import annotations

import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from biometeo_worker.config import Settings
from biometeo_worker.logger import get_logger

log = get_logger(__name__)


def _content_type(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith(".csv"):
        return "text/csv"
    return "application/octet-stream"


def get_s3_client(settings: Settings):
    if not all([settings.s3_endpoint_url, settings.s3_access_key_id, settings.s3_secret_access_key]):
        raise ValueError(
            "S3 credentials tidak lengkap: S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY"
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
    )


def upload_run_folder(folder_path: str, settings: Settings) -> dict[str, Any]:
    """Unggah semua file di bawah folder run (rekursif), prefix = nama folder run."""
    log.info("Storage upload folder: %s → bucket=%s", folder_path, settings.s3_bucket_name)
    s3 = get_s3_client(settings)
    prefix = os.path.basename(folder_path.rstrip("/\\"))

    uploaded: list[str] = []
    failed: list[dict[str, str]] = []
    for root, _, files in os.walk(folder_path):
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, folder_path).replace("\\", "/")
            key = f"{prefix}/{rel}"
            ctype = _content_type(name)
            try:
                s3.upload_file(path, settings.s3_bucket_name, key, ExtraArgs={"ContentType": ctype})
                uploaded.append(rel)
                log.info("Uploaded %s → s3://%s/%s", rel, settings.s3_bucket_name, key)
            except ClientError as e:
                failed.append({"file": rel, "error": str(e)})
                log.error("Gagal upload %s: %s", rel, str(e)[:120])

    return {"uploaded": uploaded, "failed": failed, "prefix": prefix}
