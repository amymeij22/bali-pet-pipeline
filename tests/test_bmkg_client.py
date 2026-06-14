import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from biometeo_worker.bmkg_client import _validate_json, fetch_forecast_for_village, fetch_all_unique_villages
from biometeo_worker.config import Settings


def test_validate_json_success():
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"Content-Type": "application/json"}
    resp.json.return_value = {"lokasi": "Bali", "data": "dummy"}
    assert _validate_json(resp) == {"lokasi": "Bali", "data": "dummy"}


def test_validate_json_failure_status():
    resp = MagicMock()
    resp.status_code = 500
    with pytest.raises(ValueError, match="HTTP 500"):
        _validate_json(resp)


def test_validate_json_non_json():
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"Content-Type": "text/html"}
    with pytest.raises(ValueError, match="bukan JSON"):
        _validate_json(resp)


def test_validate_json_invalid_structure():
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"Content-Type": "application/json"}
    resp.json.return_value = {"something": "else"}
    with pytest.raises(ValueError, match="struktur tidak valid"):
        _validate_json(resp)


def test_fetch_forecast_for_village_success():
    settings = Settings(
        database_url="postgresql://user:pass@host:5432/db",
        db_user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_name=None,
        s3_endpoint_url="",
        s3_access_key_id="",
        s3_secret_access_key="",
        s3_bucket_name="pet_analysis",
        s3_region="ap-southeast-1",
        app_env="dev",
        keep_local_artifacts=True,
        output_parent_dir="reports",
        request_timeout_seconds=30,
        request_retry_count=3,
        request_retry_delay_seconds=0.1,
        request_delay_seconds=0.1,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.json.return_value = {
        "lokasi": {"lat": -8.7, "lon": 115.1, "timezone": "WITA"},
        "data": [
            {
                "cuaca": [
                    [
                        {"analysis_date": "2026-06-07T04:00:00Z", "utc_datetime": "2026-06-07T04:00:00Z", "t": 30.0}
                    ]
                ]
            }
        ]
    }

    with patch("requests.get", return_value=mock_resp) as mock_get:
        records, produced, f_start, f_end, err = fetch_forecast_for_village(
            kdepum_code="51.03.01.1002",
            village_name="Kuta",
            destination_names=["Pantai Kuta"],
            settings=settings
        )

        assert err is None
        assert produced == "2026-06-07T04:00:00Z"
        assert f_start == "2026-06-07T04:00:00Z"
        assert f_end == "2026-06-07T04:00:00Z"
        assert len(records) == 1
        assert records[0]["kdepum_code"] == "51.03.01.1002"
        assert records[0]["village_name"] == "Kuta"
        assert mock_get.call_count == 1


def test_fetch_forecast_for_village_retries_and_fails():
    settings = Settings(
        database_url="postgresql://user:pass@host:5432/db",
        db_user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_name=None,
        s3_endpoint_url="",
        s3_access_key_id="",
        s3_secret_access_key="",
        s3_bucket_name="pet_analysis",
        s3_region="ap-southeast-1",
        app_env="dev",
        keep_local_artifacts=True,
        output_parent_dir="reports",
        request_timeout_seconds=30,
        request_retry_count=3,
        request_retry_delay_seconds=0.01,
        request_delay_seconds=0.01,
    )

    with patch("requests.get", side_effect=requests.exceptions.Timeout) as mock_get:
        records, produced, f_start, f_end, err = fetch_forecast_for_village(
            kdepum_code="51.03.01.1002",
            village_name="Kuta",
            destination_names=["Pantai Kuta"],
            settings=settings
        )

        assert err == "timeout"
        assert records == []
        assert produced is None
        assert mock_get.call_count == 3


def test_fetch_all_unique_villages():
    settings = Settings(
        database_url="postgresql://user:pass@host:5432/db",
        db_user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_name=None,
        s3_endpoint_url="",
        s3_access_key_id="",
        s3_secret_access_key="",
        s3_bucket_name="pet_analysis",
        s3_region="ap-southeast-1",
        app_env="dev",
        keep_local_artifacts=True,
        output_parent_dir="reports",
        request_timeout_seconds=30,
        request_retry_count=3,
        request_retry_delay_seconds=0.01,
        request_delay_seconds=0.01,
    )

    villages = [
        {"kdepum_code": "51.03.01.1002", "village_name": "Kuta", "destination_names": ["Pantai Kuta"]},
        {"kdepum_code": "51.03.01.1003", "village_name": "Legian", "destination_names": ["Pantai Legian"]},
    ]

    # Mock fetch_forecast_for_village
    mock_recs_1 = [{"utc_datetime": "2026-06-07T04:00:00Z", "t": 30.0}]
    mock_recs_2 = [{"utc_datetime": "2026-06-07T05:00:00Z", "t": 31.0}]

    def mock_fetch(kdepum_code, village_name, destination_names, settings):
        if kdepum_code == "51.03.01.1002":
            return mock_recs_1, "2026-06-07T04:00:00Z", "2026-06-07T04:00:00Z", "2026-06-07T04:00:00Z", None
        elif kdepum_code == "51.03.01.1003":
            return mock_recs_2, "2026-06-07T04:00:00Z", "2026-06-07T05:00:00Z", "2026-06-07T05:00:00Z", None
        return [], None, None, None, "error"

    with patch("biometeo_worker.bmkg_client.fetch_forecast_for_village", side_effect=mock_fetch):
        result = fetch_all_unique_villages(villages, settings)

        assert result.produced_at == "2026-06-07T04:00:00Z"
        assert result.forecast_start == "2026-06-07T04:00:00Z"
        assert result.forecast_end == "2026-06-07T05:00:00Z"
        assert len(result.raw_records) == 2
        assert len(result.failed_villages) == 0


def test_fetch_forecast_for_village_empty_records(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        database_url="postgresql://user:pass@host:5432/db",
        db_user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_name=None,
        s3_endpoint_url="",
        s3_access_key_id="",
        s3_secret_access_key="",
        s3_bucket_name="pet_analysis",
        s3_region="ap-southeast-1",
        app_env="dev",
        keep_local_artifacts=True,
        output_parent_dir="reports",
        request_timeout_seconds=30,
        request_retry_count=2,
        request_retry_delay_seconds=0.01,
        request_delay_seconds=0.01,
    )
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.json.return_value = {
        "lokasi": {"lat": -8.7, "lon": 115.1, "timezone": "WITA"},
        "data": [{"cuaca": []}]
    }
    
    with patch("requests.get", return_value=mock_resp):
        records, produced, f_start, f_end, err = fetch_forecast_for_village(
            kdepum_code="51.03.01.1002",
            village_name="Kuta",
            destination_names=["Pantai Kuta"],
            settings=settings
        )
        assert err == "response tanpa record cuaca"
        assert records == []


def test_fetch_forecast_for_village_request_exception(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        database_url="postgresql://user:pass@host:5432/db",
        db_user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_name=None,
        s3_endpoint_url="",
        s3_access_key_id="",
        s3_secret_access_key="",
        s3_bucket_name="pet_analysis",
        s3_region="ap-southeast-1",
        app_env="dev",
        keep_local_artifacts=True,
        output_parent_dir="reports",
        request_timeout_seconds=30,
        request_retry_count=1,
        request_retry_delay_seconds=0.01,
        request_delay_seconds=0.01,
    )
    
    with patch("requests.get", side_effect=requests.exceptions.RequestException("Request error!")):
        records, produced, f_start, f_end, err = fetch_forecast_for_village(
            kdepum_code="51.03.01.1002",
            village_name="Kuta",
            destination_names=["Pantai Kuta"],
            settings=settings
        )
        assert "request_error" in err


def test_fetch_forecast_for_village_generic_exception(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        database_url="postgresql://user:pass@host:5432/db",
        db_user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_name=None,
        s3_endpoint_url="",
        s3_access_key_id="",
        s3_secret_access_key="",
        s3_bucket_name="pet_analysis",
        s3_region="ap-southeast-1",
        app_env="dev",
        keep_local_artifacts=True,
        output_parent_dir="reports",
        request_timeout_seconds=30,
        request_retry_count=1,
        request_retry_delay_seconds=0.01,
        request_delay_seconds=0.01,
    )
    
    with patch("requests.get", side_effect=RuntimeError("Some error!")):
        records, produced, f_start, f_end, err = fetch_forecast_for_village(
            kdepum_code="51.03.01.1002",
            village_name="Kuta",
            destination_names=["Pantai Kuta"],
            settings=settings
        )
        assert "RuntimeError" in err


def test_fetch_all_unique_villages_with_errors():
    settings = Settings(
        database_url="postgresql://user:pass@host:5432/db",
        db_user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_name=None,
        s3_endpoint_url="",
        s3_access_key_id="",
        s3_secret_access_key="",
        s3_bucket_name="pet_analysis",
        s3_region="ap-southeast-1",
        app_env="dev",
        keep_local_artifacts=True,
        output_parent_dir="reports",
        request_timeout_seconds=30,
        request_retry_count=1,
        request_retry_delay_seconds=0.01,
        request_delay_seconds=0.01,
    )

    villages = [
        {"kdepum_code": "51.03.01.1002", "village_name": "Kuta", "destination_names": ["Pantai Kuta"]},
    ]

    with patch("biometeo_worker.bmkg_client.fetch_forecast_for_village", return_value=([], None, None, None, "some error")):
        result = fetch_all_unique_villages(villages, settings)
        assert len(result.failed_villages) == 1
        assert result.failed_villages[0]["error"] == "some error"

