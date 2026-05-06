import sys
from pathlib import Path

import pytest

# Agar import modul di folder induk `cloudrun/` berfungsi saat pytest dari root/repo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_settings

from main import validate_runtime_settings


def test_load_settings_defaults_dev(monkeypatch: pytest.MonkeyPatch):
    # `.env` bisa mengisi APP_ENV secara implicit via load_dotenv().
    # Paksa "unset" menjadi empty string agar tidak terambil dari `.env`.
    monkeypatch.setenv("APP_ENV", "")
    # `.env` juga bisa mengisi KEEP_LOCAL_ARTIFACTS, jadi untuk test deterministik,
    # set explicit value agar parsing _env_bool ter-cover.
    monkeypatch.setenv("KEEP_LOCAL_ARTIFACTS", "true")
    s = load_settings()
    assert s.app_env == "dev"
    assert s.keep_local_artifacts is True


def test_load_settings_default_keep_local_false_in_prod(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("KEEP_LOCAL_ARTIFACTS", raising=False)
    s = load_settings()
    assert s.app_env == "prod"
    assert s.keep_local_artifacts is False


def test_validate_runtime_settings_prod_keep_local_false_cannot_skip_storage(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("KEEP_LOCAL_ARTIFACTS", "0")
    s = load_settings()
    with pytest.raises(ValueError, match=r"APP_ENV=prod.*jangan gunakan --skip-storage"):
        validate_runtime_settings(s, dry_run=False, skip_db=True, skip_storage=True)

