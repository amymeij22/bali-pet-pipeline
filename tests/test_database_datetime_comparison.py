import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from biometeo_worker.database import import_forecast_batch, ForecastRowDB
from biometeo_worker.config import Settings


def test_import_forecast_batch_datetime_comparison_naive_vs_aware():
    # Setup mocks
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    # Mock fetchall returns
    mock_cur.fetchall.side_effect = [
        [],  # optional columns check
        [],  # existing forecasts check
        [("51.03.01.1002", "village_uuid")],  # villages list
        [("51.03.01.1002", "Pantai Kuta", "dest_uuid")],  # destinations list
        [("very_hot", "cat_uuid")],  # thermal categories
    ]

    # Mock fetchone returns
    mock_cur.fetchone.side_effect = [
        None,  # check_already_processed_batches -> None (is_new_batch=True)
        ("batch_uuid",),  # RETURNING id from insert batch
        (datetime(2026, 6, 7, 3, 0, 0),),  # latest_row fetchone (naive datetime in database)
    ]

    # Prepare dummy forecast rows
    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T04:00:00+00:00",
            temperature=30.0,
            humidity=80.0,
            wind_speed_kmh=10.0,
            wind_direction="E",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=32.0,
            temperate_category_key="very_hot",
            sub_tropic_category_key="very_hot",
            cloud_cover=None,
            tmrt=None,
            vapor_pressure=None,
            wind_speed_1_1m=None,
        )
    ]

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
        request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5,
    )

    with patch("biometeo_worker.database.connect", return_value=mock_conn), \
         patch("biometeo_worker.database.execute_values") as mock_execute_values:
        
        # Test importing with aware produced_at (Z notation) vs naive db datetime
        n = import_forecast_batch(
            produced_at="2026-06-07T04:00:00Z",
            forecast_start="2026-06-07T00:00:00Z",
            forecast_end="2026-06-07T08:00:00Z",
            rows=rows,
            settings=settings,
            set_latest=False
        )

        assert n == 1
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()


def test_import_forecast_batch_datetime_comparison_both_aware():
    # Setup mocks
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    # Mock fetchall returns
    mock_cur.fetchall.side_effect = [
        [],  # optional columns check
        [],  # existing forecasts check
        [("51.03.01.1002", "village_uuid")],  # villages list
        [("51.03.01.1002", "Pantai Kuta", "dest_uuid")],  # destinations list
        [("very_hot", "cat_uuid")],  # thermal categories
    ]

    # Mock fetchone returns
    mock_cur.fetchone.side_effect = [
        None,  # check_already_processed_batches -> None (is_new_batch=True)
        ("batch_uuid",),  # RETURNING id from insert batch
        (datetime(2026, 6, 7, 3, 0, 0, tzinfo=timezone.utc),),  # latest_row fetchone (aware datetime in database)
    ]

    # Prepare dummy forecast rows
    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T04:00:00+00:00",
            temperature=30.0,
            humidity=80.0,
            wind_speed_kmh=10.0,
            wind_direction="E",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=32.0,
            temperate_category_key="very_hot",
            sub_tropic_category_key="very_hot",
            cloud_cover=None,
            tmrt=None,
            vapor_pressure=None,
            wind_speed_1_1m=None,
        )
    ]

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
        request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5,
    )

    with patch("biometeo_worker.database.connect", return_value=mock_conn), \
         patch("biometeo_worker.database.execute_values") as mock_execute_values:
        
        # Test importing with aware produced_at (Z notation) vs aware db datetime
        n = import_forecast_batch(
            produced_at="2026-06-07T04:00:00Z",
            forecast_start="2026-06-07T00:00:00Z",
            forecast_end="2026-06-07T08:00:00Z",
            rows=rows,
            settings=settings,
            set_latest=False
        )

        assert n == 1
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()


def test_import_forecast_batch_is_latest_activation_scenarios():
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
        request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5,
    )
    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T04:00:00+00:00",
            temperature=30.0,
            humidity=80.0,
            wind_speed_kmh=10.0,
            wind_direction="E",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=32.0,
            temperate_category_key="very_hot",
            sub_tropic_category_key="very_hot",
            cloud_cover=None,
            tmrt=None,
            vapor_pressure=None,
            wind_speed_1_1m=None,
        )
    ]

    # Kita akan tes 4 skenario untuk aktivasi is_latest:
    # 1. set_latest=False, incoming lebih lama daripada latest di DB -> should_activate=False
    # 2. set_latest=False, incoming lebih baru daripada latest di DB -> should_activate=True
    # 3. set_latest=True, incoming lebih lama daripada latest di DB -> should_activate=True
    # 4. set_latest=False, DB kosong (belum ada latest) -> should_activate=True

    scenarios = [
        # (set_latest, latest_db_time_str, expected_activated)
        (False, "2026-06-07T05:00:00Z", False),  # 1. Incoming (04:00) lebih lama dari DB (05:00)
        (False, "2026-06-07T03:00:00Z", True),   # 2. Incoming (04:00) lebih baru dari DB (03:00)
        (True,  "2026-06-07T05:00:00Z", True),   # 3. set_latest=True, dipaksa aktivasi walau DB lebih baru
        (False, None,                    True),   # 4. DB kosong -> aktivasi
    ]

    for set_latest, db_time, expected_activated in scenarios:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchall.side_effect = [
            [],  # optional columns check
            [],  # existing forecasts check
            [("51.03.01.1002", "village_uuid")],  # villages list
            [("51.03.01.1002", "Pantai Kuta", "dest_uuid")],  # destinations list
            [("very_hot", "cat_uuid")],  # thermal categories
        ]

        fetchone_side_effect = [
            None,  # is_new_batch=True
            ("batch_uuid",),  # RETURNING id from insert batch
        ]
        if db_time is not None:
            db_dt = datetime.fromisoformat(db_time.replace("Z", "+00:00"))
            fetchone_side_effect.append((db_dt,))
        else:
            fetchone_side_effect.append(None)

        mock_cur.fetchone.side_effect = fetchone_side_effect

        with patch("biometeo_worker.database.connect", return_value=mock_conn), \
             patch("biometeo_worker.database.execute_values") as mock_execute_values:

            n = import_forecast_batch(
                produced_at="2026-06-07T04:00:00Z",
                forecast_start="2026-06-07T00:00:00Z",
                forecast_end="2026-06-07T08:00:00Z",
                rows=rows,
                settings=settings,
                set_latest=set_latest
            )

            assert n == 1
            
            # Cek apakah query UPDATE public.forecast_batches SET is_latest = TRUE dijalankan
            all_executes = [args[0] for args, kwargs in mock_cur.execute.call_args_list if len(args) > 0]
            
            activated = any("UPDATE public.forecast_batches" in q and "SET is_latest = TRUE" in q for q in all_executes)
            assert activated == expected_activated, f"Gagal untuk set_latest={set_latest}, db_time={db_time}. Harusnya {expected_activated} tapi didapat {activated}"

