"""Konfigurasi runtime dari environment (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    db_user: str | None
    db_password: str | None
    db_host: str | None
    db_port: str | None
    db_name: str | None

    s3_endpoint_url: str | None
    s3_access_key_id: str | None
    s3_secret_access_key: str | None
    s3_bucket_name: str
    s3_region: str

    app_env: str
    keep_local_artifacts: bool

    output_parent_dir: str
    request_timeout_seconds: int
    request_retry_count: int
    request_retry_delay_seconds: float
    request_delay_seconds: float


def load_settings() -> Settings:
    load_dotenv()
    app_env = (os.getenv("APP_ENV", "dev") or "dev").strip().lower()
    keep_default = False if app_env in {"prod", "production"} else True
    return Settings(
        database_url=os.getenv("DATABASE_URL"),
        db_user=os.getenv("DB_USER"),
        db_password=os.getenv("DB_PASSWORD"),
        db_host=os.getenv("DB_HOST"),
        db_port=os.getenv("DB_PORT"),
        db_name=os.getenv("DB_NAME"),
        s3_endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        s3_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
        s3_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        s3_bucket_name=os.getenv("S3_BUCKET_NAME", "pet_analysis"),
        s3_region=os.getenv("S3_REGION", "ap-southeast-1"),
        app_env=app_env,
        keep_local_artifacts=_env_bool("KEEP_LOCAL_ARTIFACTS", keep_default),
        output_parent_dir=os.getenv("OUTPUT_PARENT_DIR", "pet_analysis"),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
        request_retry_count=int(os.getenv("REQUEST_RETRY_COUNT", "3")),
        request_retry_delay_seconds=float(os.getenv("REQUEST_RETRY_DELAY_SECONDS", "2")),
        request_delay_seconds=float(os.getenv("REQUEST_DELAY_SECONDS", "0.5")),
    )
