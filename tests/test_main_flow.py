import argparse
import sys
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from biometeo_worker.config import Settings
from biometeo_worker.main import (
    _safe_folder_ts,
    _static_by_kdepum,
    _destinations_by_kdepum,
    _series_val,
    validate_runtime_settings,
    build_grp_and_exports,
    parse_args,
    determine_set_latest,
    main,
)


def test_safe_folder_ts():
    assert _safe_folder_ts("2026-06-14T11:51:12Z") == "2026-06-14_11-51-12Z"
    assert _safe_folder_ts("2026/06/14T11:51:12") == "2026-06-14_11-51-12"


def test_static_by_kdepum():
    dests = [
        {"kdepum_code": "k1", "destination_name": "d1"},
        {"kdepum_code": "k1", "destination_name": "d2"},
        {"kdepum_code": "k2", "destination_name": "d3"},
    ]
    out = _static_by_kdepum(dests)  # type: ignore
    assert len(out) == 2
    assert out["k1"]["destination_name"] == "d1"


def test_destinations_by_kdepum():
    dests = [
        {"kdepum_code": "k1", "destination_name": "d1"},
        {"kdepum_code": "k1", "destination_name": "d2"},
        {"kdepum_code": "k2", "destination_name": "d3"},
    ]
    out = _destinations_by_kdepum(dests)  # type: ignore
    assert len(out) == 2
    assert len(out["k1"]) == 2
    assert len(out["k2"]) == 1


def test_series_val():
    s = pd.Series({"a": 1.0, "b": float("nan")})
    assert _series_val(s, "b", "a") == 1.0
    assert _series_val(s, "c", "d", default=10.0) == 10.0


def test_validate_runtime_settings_dry_run():
    settings = Settings(
        database_url=None, db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url=None, s3_access_key_id=None, s3_secret_access_key=None, s3_bucket_name="", s3_region="",
        app_env="dev", keep_local_artifacts=True, output_parent_dir="",
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    validate_runtime_settings(settings, dry_run=True, skip_db=False, skip_storage=False)


def test_validate_runtime_settings_missing_db():
    settings = Settings(
        database_url=None, db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="", s3_region="",
        app_env="dev", keep_local_artifacts=True, output_parent_dir="",
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    with pytest.raises(ValueError, match="koneksi database"):
        validate_runtime_settings(settings, dry_run=False, skip_db=False, skip_storage=False)


def test_validate_runtime_settings_missing_s3():
    settings = Settings(
        database_url="url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url=None, s3_access_key_id=None, s3_secret_access_key=None, s3_bucket_name="", s3_region="",
        app_env="dev", keep_local_artifacts=True, output_parent_dir="",
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    with pytest.raises(ValueError, match="S3 Supabase"):
        validate_runtime_settings(settings, dry_run=False, skip_db=False, skip_storage=False)


def test_validate_runtime_settings_prod_no_storage():
    settings = Settings(
        database_url="url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="", s3_region="",
        app_env="prod", keep_local_artifacts=False, output_parent_dir="",
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    with pytest.raises(ValueError, match="APP_ENV=prod.* KEEP_LOCAL_ARTIFACTS=0"):
        validate_runtime_settings(settings, dry_run=False, skip_db=False, skip_storage=True)


def test_build_grp_and_exports_fallback_kdep():
    # Test line 122 of main.py
    df = pd.DataFrame([
        {
            "kdepum_code": "k1",
            "village_name": "vil1",
            "destination_name": "", # empty destination name triggers fallback
            "local_datetime": "2026-06-14T11:00:00",
            "utc_datetime": "2026-06-14T03:00:00Z",
            "pet_value": 32.5,
            "tmrt": 40.0,
            "vapor_pressure": 22.0,
            "t": 30.0,
            "hu": 60.0,
            "ws": 10.0,
            "cloud_cover_percent": 50.0,
            "wind_speed_1_1m_ms": 1.5,
            "latitude": -8.5,
            "longitude": 115.2,
            "sea_level_height": 10.0,
            "N_oktas": 4.0,
        }
    ])
    # kdep_to_dests has "k1" mapping to ["destA", "destB"]
    db_rows, raw_df, proc_df, class_df, final_df = build_grp_and_exports(df, {"k1": ["destA", "destB"]}, "2026-06-14T03:00:00Z")
    assert len(db_rows) == 2
    assert db_rows[0].destination_name == "destA"
    assert db_rows[1].destination_name == "destB"


def test_determine_set_latest_main():
    assert determine_set_latest("morning", "02:15") is True
    assert determine_set_latest("evening", "14:15") is True
    assert determine_set_latest("morning", "03:15") is False
    assert determine_set_latest("evening", "15:15") is False


def test_parse_args():
    args = parse_args(["--dry-run", "--skip-db", "--skip-storage", "--max-villages", "5", "--output-dir", "mypath", "--slot", "morning", "--trigger-source", "02:15"])
    assert args.dry_run is True
    assert args.skip_db is True
    assert args.skip_storage is True
    assert args.max_villages == 5
    assert args.output_dir == "mypath"
    assert args.slot == "morning"
    assert args.trigger_source == "02:15"


@patch("biometeo_worker.main.load_settings")
def test_main_validation_fails(mock_load_settings):
    settings = Settings(
        database_url=None, db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url=None, s3_access_key_id=None, s3_secret_access_key=None, s3_bucket_name="", s3_region="",
        app_env="dev", keep_local_artifacts=True, output_parent_dir="",
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    mock_load_settings.return_value = settings
    res = main(["--max-villages", "1"])
    assert res == 1


@patch("biometeo_worker.main.fetch_all_unique_villages")
@patch("biometeo_worker.main.load_settings")
def test_main_fetch_empty_stops(mock_load_settings, mock_fetch):
    settings = Settings(
        database_url="db_url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="bucket", s3_region="ap",
        app_env="dev", keep_local_artifacts=True, output_parent_dir="reports",
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    mock_load_settings.return_value = settings
    
    mock_result = MagicMock()
    mock_result.raw_records = []
    mock_result.failed_villages = []
    mock_fetch.return_value = mock_result
    
    res = main(["--dry-run"])
    assert res == 2


@patch("biometeo_worker.main.fetch_all_unique_villages")
@patch("biometeo_worker.main.load_settings")
def test_main_fetch_all_failed(mock_load_settings, mock_fetch):
    settings = Settings(
        database_url="db_url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="bucket", s3_region="ap",
        app_env="dev", keep_local_artifacts=True, output_parent_dir="reports",
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    mock_load_settings.return_value = settings
    
    mock_result = MagicMock()
    mock_result.raw_records = []
    mock_result.failed_villages = [{"kdepum_code": "k1", "village_name": "vil1", "error": "some_error"}]
    mock_fetch.return_value = mock_result
    
    res = main(["--dry-run"])
    assert res == 3


@patch("biometeo_worker.main.upload_run_folder")
@patch("biometeo_worker.main.import_forecast_batch")
@patch("biometeo_worker.biometeo_engine.calculate_biometeo_outputs")
@patch("biometeo_worker.main.fetch_all_unique_villages")
@patch("biometeo_worker.main.check_already_processed_batches")
@patch("biometeo_worker.main.fetch_forecast_for_village")
@patch("biometeo_worker.main.fetch_destination_configs")
@patch("biometeo_worker.main.load_settings")
def test_main_success_flow(
    mock_load_settings,
    mock_fetch_dest,
    mock_fetch_village,
    mock_check_processed,
    mock_fetch_all,
    mock_calc_biometeo,
    mock_import_db,
    mock_upload_storage,
    tmp_path,
):
    settings = Settings(
        database_url="db_url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="bucket", s3_region="ap",
        app_env="dev", keep_local_artifacts=True, output_parent_dir=str(tmp_path),
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    mock_load_settings.return_value = settings

    # DB destinations mock
    mock_fetch_dest.return_value = [
        {
            "destination_name": "Pantai Kuta",
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "regency": "Badung",
            "district": "Kuta",
            "latitude": -8.7,
            "longitude": 115.1,
            "sea_level_height": 5.0,
        }
    ]

    # Probe fetches
    mock_fetch_village.return_value = ([], "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", None)
    mock_check_processed.return_value = set()

    # Fetch all returns a valid record
    mock_res = MagicMock()
    mock_res.produced_at = "2026-06-14T11:00:00Z"
    mock_res.forecast_start = "2026-06-14T11:00:00Z"
    mock_res.forecast_end = "2026-06-14T11:00:00Z"
    mock_res.raw_records = [
        {
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "utc_datetime": "2026-06-14T11:00:00Z",
            "local_datetime": "2026-06-14T19:00:00+08:00",
            "t": 30.0,
            "hu": 60.0,
            "ws": 10.0,
            "tcc": 50.0,
        }
    ]
    mock_res.failed_villages = []
    mock_fetch_all.return_value = mock_res

    # Biometeo calculator mock
    mock_calc_biometeo.return_value = {
        "tmrt": 42.0,
        "vapor_pressure": 23.0,
        "wind_speed_1_1m": 1.2,
        "pet_value": 33.0,
    }

    # DB insertion and Storage upload mock
    mock_import_db.return_value = 1
    mock_upload_storage.return_value = {"failed": []}

    res = main(["--slot", "morning", "--trigger-source", "02:15"])
    assert res == 0
    mock_import_db.assert_called_once()
    mock_upload_storage.assert_called_once()


@patch("biometeo_worker.main.upload_run_folder")
@patch("biometeo_worker.main.import_forecast_batch")
@patch("biometeo_worker.biometeo_engine.calculate_biometeo_outputs")
@patch("biometeo_worker.main.fetch_all_unique_villages")
@patch("biometeo_worker.main.check_already_processed_batches")
@patch("biometeo_worker.main.fetch_forecast_for_village")
@patch("biometeo_worker.main.fetch_destination_configs")
@patch("biometeo_worker.main.load_settings")
def test_main_biometeo_empty_fails(
    mock_load_settings,
    mock_fetch_dest,
    mock_fetch_village,
    mock_check_processed,
    mock_fetch_all,
    mock_calc_biometeo,
    mock_import_db,
    mock_upload_storage,
    tmp_path,
):
    settings = Settings(
        database_url="db_url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="bucket", s3_region="ap",
        app_env="prod", keep_local_artifacts=False, output_parent_dir=str(tmp_path),
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    mock_load_settings.return_value = settings

    # DB destinations fetch fails -> fallback to destinations.py
    mock_fetch_dest.side_effect = RuntimeError("DB Query Failed")
    mock_fetch_village.return_value = ([], "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", None)
    mock_check_processed.return_value = set()

    # Fetch all returns a valid record
    mock_res = MagicMock()
    mock_res.produced_at = "2026-06-14T11:00:00Z"
    mock_res.forecast_start = "2026-06-14T11:00:00Z"
    mock_res.forecast_end = "2026-06-14T11:00:00Z"
    mock_res.raw_records = [
        {
            # Using valid kdepum_code from destinations.py (e.g. Pantai Kuta "51.03.01.1002")
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "utc_datetime": "2026-06-14T11:00:00Z",
            "local_datetime": "2026-06-14T19:00:00+08:00",
            "t": 30.0,
            "hu": 60.0,
            "ws": 10.0,
            "tcc": 50.0,
        }
    ]
    mock_res.failed_villages = []
    mock_fetch_all.return_value = mock_res

    # Biometeo throws an exception -> results in empty bio_df
    mock_calc_biometeo.side_effect = RuntimeError("Biometeo calculation failure")

    res = main(["--max-villages", "1"])
    assert res == 4


@patch("biometeo_worker.main.upload_run_folder")
@patch("biometeo_worker.main.import_forecast_batch")
@patch("biometeo_worker.biometeo_engine.calculate_biometeo_outputs")
@patch("biometeo_worker.main.fetch_all_unique_villages")
@patch("biometeo_worker.main.check_already_processed_batches")
@patch("biometeo_worker.main.fetch_forecast_for_village")
@patch("biometeo_worker.main.fetch_destination_configs")
@patch("biometeo_worker.main.load_settings")
def test_main_db_insert_zero_fails(
    mock_load_settings,
    mock_fetch_dest,
    mock_fetch_village,
    mock_check_processed,
    mock_fetch_all,
    mock_calc_biometeo,
    mock_import_db,
    mock_upload_storage,
    tmp_path,
):
    settings = Settings(
        database_url="db_url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="bucket", s3_region="ap",
        app_env="dev", keep_local_artifacts=True, output_parent_dir=str(tmp_path),
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    mock_load_settings.return_value = settings

    # DB destinations fetch fails -> fallback to destinations.py
    mock_fetch_dest.side_effect = RuntimeError("DB Query Failed")
    mock_fetch_village.return_value = ([], "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", None)
    mock_check_processed.return_value = set()

    # Fetch all returns a valid record
    mock_res = MagicMock()
    mock_res.produced_at = "2026-06-14T11:00:00Z"
    mock_res.forecast_start = "2026-06-14T11:00:00Z"
    mock_res.forecast_end = "2026-06-14T11:00:00Z"
    mock_res.raw_records = [
        {
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "utc_datetime": "2026-06-14T11:00:00Z",
            "local_datetime": "2026-06-14T19:00:00+08:00",
            "t": 30.0,
            "hu": 60.0,
            "ws": 10.0,
            "tcc": 50.0,
        }
    ]
    mock_res.failed_villages = []
    mock_fetch_all.return_value = mock_res

    # Biometeo calculator mock
    mock_calc_biometeo.return_value = {
        "tmrt": 42.0,
        "vapor_pressure": 23.0,
        "wind_speed_1_1m": 1.2,
        "pet_value": 33.0,
    }

    # DB returns 0 rows inserted
    mock_import_db.return_value = 0

    res = main(["--max-villages", "1"])
    assert res == 6


@patch("biometeo_worker.main.upload_run_folder")
@patch("biometeo_worker.main.import_forecast_batch")
@patch("biometeo_worker.biometeo_engine.calculate_biometeo_outputs")
@patch("biometeo_worker.main.fetch_all_unique_villages")
@patch("biometeo_worker.main.check_already_processed_batches")
@patch("biometeo_worker.main.fetch_forecast_for_village")
@patch("biometeo_worker.main.fetch_destination_configs")
@patch("biometeo_worker.main.load_settings")
def test_main_storage_failed_upload(
    mock_load_settings,
    mock_fetch_dest,
    mock_fetch_village,
    mock_check_processed,
    mock_fetch_all,
    mock_calc_biometeo,
    mock_import_db,
    mock_upload_storage,
    tmp_path,
):
    settings = Settings(
        database_url="db_url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="bucket", s3_region="ap",
        app_env="dev", keep_local_artifacts=True, output_parent_dir=str(tmp_path),
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    mock_load_settings.return_value = settings

    # DB destinations fetch fails -> fallback to destinations.py
    mock_fetch_dest.side_effect = RuntimeError("DB Query Failed")
    mock_fetch_village.return_value = ([], "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", None)
    mock_check_processed.return_value = set()

    # Fetch all returns a valid record
    mock_res = MagicMock()
    mock_res.produced_at = "2026-06-14T11:00:00Z"
    mock_res.forecast_start = "2026-06-14T11:00:00Z"
    mock_res.forecast_end = "2026-06-14T11:00:00Z"
    mock_res.raw_records = [
        {
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "utc_datetime": "2026-06-14T11:00:00Z",
            "local_datetime": "2026-06-14T19:00:00+08:00",
            "t": 30.0,
            "hu": 60.0,
            "ws": 10.0,
            "tcc": 50.0,
        }
    ]
    mock_res.failed_villages = []
    mock_fetch_all.return_value = mock_res

    # Biometeo calculator mock
    mock_calc_biometeo.return_value = {
        "tmrt": 42.0,
        "vapor_pressure": 23.0,
        "wind_speed_1_1m": 1.2,
        "pet_value": 33.0,
    }

    # DB returns 1 row inserted
    mock_import_db.return_value = 1
    # Storage upload fails (returns non-empty failed uploads list)
    mock_upload_storage.return_value = {"failed": ["raw_data.csv"]}

    res = main(["--max-villages", "1"])
    assert res == 5


@patch("biometeo_worker.main.upload_run_folder")
@patch("biometeo_worker.main.import_forecast_batch")
@patch("biometeo_worker.biometeo_engine.calculate_biometeo_outputs")
@patch("biometeo_worker.main.fetch_all_unique_villages")
@patch("biometeo_worker.main.check_already_processed_batches")
@patch("biometeo_worker.main.fetch_forecast_for_village")
@patch("biometeo_worker.main.fetch_destination_configs")
@patch("biometeo_worker.main.load_settings")
def test_main_probe_variations_and_skipped_logging(
    mock_load_settings,
    mock_fetch_dest,
    mock_fetch_village,
    mock_check_processed,
    mock_fetch_all,
    mock_calc_biometeo,
    mock_import_db,
    mock_upload_storage,
    tmp_path,
):
    settings = Settings(
        database_url="db_url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="bucket", s3_region="ap",
        app_env="prod", keep_local_artifacts=False, output_parent_dir=str(tmp_path),
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    mock_load_settings.return_value = settings

    # 1. Probe fetches failure path and success path with no produced_at
    # We return 3 probe locations, let's mock side effects:
    # First: raises error / err is set
    # Second: success, prod is None
    # Third: success, prod is set
    mock_fetch_village.side_effect = [
        ([], None, None, None, "some network error"),
        ([], None, None, None, None), # prod is None
        ([], "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", None),
    ]
    # check_already_processed_batches returns that it IS already processed (all match probe_results)
    mock_check_processed.return_value = {"2026-06-14T11:00:00Z"}

    # DB destinations mock
    mock_fetch_dest.return_value = [
        {
            "destination_name": "Pantai Kuta",
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "regency": "Badung",
            "district": "Kuta",
            "latitude": -8.7,
            "longitude": 115.1,
            "sea_level_height": 5.0,
        },
        {
            "destination_name": "Pantai Sanur",
            "kdepum_code": "51.71.02.1001",
            "village_name": "Sanur",
            "regency": "Denpasar",
            "district": "Denpasar Selatan",
            "latitude": -8.68,
            "longitude": 115.26,
            "sea_level_height": 3.0,
        },
        {
            "destination_name": "Pantai Nusa Dua",
            "kdepum_code": "51.03.02.1001",
            "village_name": "Benoa",
            "regency": "Badung",
            "district": "Kuta Selatan",
            "latitude": -8.8,
            "longitude": 115.22,
            "sea_level_height": 4.0,
        }
    ]

    # Fetch all returns a valid record, but also include failed_villages to cover partial_success log/writing
    mock_res = MagicMock()
    mock_res.produced_at = "2026-06-14T11:00:00Z"
    mock_res.forecast_start = "2026-06-14T11:00:00Z"
    mock_res.forecast_end = "2026-06-14T11:00:00Z"
    # Row 1: valid
    # Row 2: invalid kdepum (not in destinations) -> covers line 424
    # Row 3: preprocessing throws error -> covers line 439
    # Row 4: biometeo engine throws error -> covers line 454
    mock_res.raw_records = [
        {
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "utc_datetime": "2026-06-14T11:00:00Z",
            "local_datetime": "2026-06-14T19:00:00+08:00",
            "t": 30.0,
            "hu": 60.0,
            "ws": 10.0,
            "tcc": 50.0,
        },
        {
            "kdepum_code": "non_existent_kdepum",
            "village_name": "Unknown",
            "utc_datetime": "2026-06-14T11:00:00Z",
            "local_datetime": "2026-06-14T19:00:00+08:00",
            "t": 30.0,
            "hu": 60.0,
            "ws": 10.0,
            "tcc": 50.0,
        },
        {
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "utc_datetime": "2026-06-14T11:00:00Z",
            "local_datetime": "2026-06-14T19:00:00+08:00",
            "t": "nan", # will fail preprocess
            "hu": 60.0,
            "ws": 10.0,
            "tcc": 50.0,
        },
        {
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "utc_datetime": "2026-06-14T12:00:00Z",
            "local_datetime": "2026-06-14T20:00:00+08:00",
            "t": 30.0,
            "hu": 60.0,
            "ws": 10.0,
            "tcc": 50.0,
        }
    ]
    mock_res.failed_villages = [{"kdepum_code": "fail_kdep", "village_name": "fail_vil", "error": "fetch error"}]
    mock_fetch_all.return_value = mock_res

    # Biometeo mock: first call succeeds, second call throws error
    mock_calc_biometeo.side_effect = [
        {
            "tmrt": 42.0,
            "vapor_pressure": 23.0,
            "wind_speed_1_1m": 1.2,
            "pet_value": 33.0,
        },
        RuntimeError("Engine calculation fail"),
    ]

    mock_import_db.return_value = 1
    mock_upload_storage.return_value = {"failed": []}

    # Run in prod mode with keep_local_artifacts=False, which triggers TemporaryDirectory path (line 587)
    res = main(["--max-villages", "3"])
    assert res == 0
    mock_upload_storage.assert_called_once()


@patch("biometeo_worker.main.upload_run_folder")
@patch("biometeo_worker.main.import_forecast_batch")
@patch("biometeo_worker.biometeo_engine.calculate_biometeo_outputs")
@patch("biometeo_worker.main.fetch_all_unique_villages")
@patch("biometeo_worker.main.check_already_processed_batches")
@patch("biometeo_worker.main.fetch_forecast_for_village")
@patch("biometeo_worker.main.fetch_destination_configs")
@patch("biometeo_worker.main.load_settings")
def test_main_skip_storage_and_dry_run_branch(
    mock_load_settings,
    mock_fetch_dest,
    mock_fetch_village,
    mock_check_processed,
    mock_fetch_all,
    mock_calc_biometeo,
    mock_import_db,
    mock_upload_storage,
    tmp_path,
):
    settings = Settings(
        database_url="db_url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="bucket", s3_region="ap",
        app_env="dev", keep_local_artifacts=True, output_parent_dir=str(tmp_path),
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    mock_load_settings.return_value = settings

    mock_fetch_dest.return_value = [
        {
            "destination_name": "Pantai Kuta",
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "regency": "Badung",
            "district": "Kuta",
            "latitude": -8.7,
            "longitude": 115.1,
            "sea_level_height": 5.0,
        }
    ]

    mock_fetch_village.return_value = ([], "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", "2026-06-14T11:00:00Z", None)
    mock_check_processed.return_value = set()

    mock_res = MagicMock()
    mock_res.produced_at = "2026-06-14T11:00:00Z"
    mock_res.forecast_start = "2026-06-14T11:00:00Z"
    mock_res.forecast_end = "2026-06-14T11:00:00Z"
    mock_res.raw_records = [
        {
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "utc_datetime": "2026-06-14T11:00:00Z",
            "local_datetime": "2026-06-14T19:00:00+08:00",
            "t": 30.0,
            "hu": 60.0,
            "ws": 10.0,
            "tcc": 50.0,
        }
    ]
    mock_res.failed_villages = []
    mock_fetch_all.return_value = mock_res

    mock_calc_biometeo.return_value = {
        "tmrt": 42.0,
        "vapor_pressure": 23.0,
        "wind_speed_1_1m": 1.2,
        "pet_value": 33.0,
    }

    # 1. Run with --skip-storage
    mock_import_db.return_value = 1
    res_skip = main(["--skip-storage", "--max-villages", "1"])
    assert res_skip == 0
    mock_upload_storage.assert_not_called()

    # 2. Run with --dry-run
    mock_import_db.reset_mock()
    res_dry = main(["--dry-run", "--max-villages", "1"])
    assert res_dry == 0
    mock_import_db.assert_not_called()


def test_determine_set_latest():
    from biometeo_worker.main import determine_set_latest
    # Test slot manual
    assert determine_set_latest("manual", "any") is True
    # Test slot morning with matching trigger
    assert determine_set_latest("morning", "02:15") is True
    assert determine_set_latest("morning", "02.15") is True
    assert determine_set_latest("morning", "02:15:00") is True
    assert determine_set_latest("morning", "12:15") is False
    # Test slot evening with matching trigger
    assert determine_set_latest("evening", "14:15") is True
    assert determine_set_latest("evening", "14.15") is True
    assert determine_set_latest("evening", "14:15:00") is True
    assert determine_set_latest("evening", "12:15") is False
    # Test fallback branch
    assert determine_set_latest("other_slot", "any") is True


@patch("biometeo_worker.main.upload_run_folder")
@patch("biometeo_worker.main.import_forecast_batch")
@patch("biometeo_worker.biometeo_engine.calculate_biometeo_outputs")
@patch("biometeo_worker.main.fetch_all_unique_villages")
@patch("biometeo_worker.main.check_already_processed_batches")
@patch("biometeo_worker.main.fetch_forecast_for_village")
@patch("biometeo_worker.main.fetch_destination_configs")
@patch("biometeo_worker.main.load_settings")
def test_main_probe_empty_and_failed_status(
    mock_load_settings,
    mock_fetch_dest,
    mock_fetch_village,
    mock_check_processed,
    mock_fetch_all,
    mock_calc_biometeo,
    mock_import_db,
    mock_upload_storage,
    tmp_path,
):
    settings = Settings(
        database_url="db_url", db_user=None, db_password=None, db_host=None, db_port=None, db_name=None,
        s3_endpoint_url="s3", s3_access_key_id="id", s3_secret_access_key="key", s3_bucket_name="bucket", s3_region="ap",
        app_env="dev", keep_local_artifacts=True, output_parent_dir=str(tmp_path),
        request_timeout_seconds=30, request_retry_count=3, request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5
    )
    mock_load_settings.return_value = settings

    # All probes fail to return a valid analysis_date
    mock_fetch_village.return_value = ([], None, None, None, "some probe network error")

    # DB destinations mock
    mock_fetch_dest.return_value = [
        {
            "destination_name": "Pantai Kuta",
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "regency": "Badung",
            "district": "Kuta",
            "latitude": -8.7,
            "longitude": 115.1,
            "sea_level_height": 5.0,
        }
    ]

    # Fetch all returns a valid record, but failed_villages has 1 item (success_v = 1 - 1 = 0)
    mock_res = MagicMock()
    mock_res.produced_at = "2026-06-14T11:00:00Z"
    mock_res.forecast_start = "2026-06-14T11:00:00Z"
    mock_res.forecast_end = "2026-06-14T11:00:00Z"
    mock_res.raw_records = [
        {
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "utc_datetime": "2026-06-14T11:00:00Z",
            "local_datetime": "2026-06-14T19:00:00+08:00",
            "t": 30.0,
            "hu": 60.0,
            "ws": 10.0,
            "tcc": 50.0,
        }
    ]
    mock_res.failed_villages = [{"kdepum_code": "51.03.01.1002", "village_name": "Kuta", "error": "failed in fetch_all"}]
    mock_fetch_all.return_value = mock_res

    # Biometeo mock
    mock_calc_biometeo.return_value = {
        "tmrt": 42.0,
        "vapor_pressure": 23.0,
        "wind_speed_1_1m": 1.2,
        "pet_value": 33.0,
    }

    mock_import_db.return_value = 1
    mock_upload_storage.return_value = {"failed": []}

    res = main(["--max-villages", "1"])
    assert res == 4


