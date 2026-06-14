import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import psycopg2

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from biometeo_worker.config import Settings
from biometeo_worker.database import (
    ForecastRowDB,
    check_already_processed_batches,
    connect,
    import_forecast_batch,
)
from biometeo_worker.destinations_source_db import (
    fetch_destination_configs,
    validate_destination_configs,
)


def _setup_mock_db(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cur
    mock_cur.connection = mock_conn
    mock_conn.encoding = "UTF8"
    mock_cur.mogrify.return_value = b"(dummy_values)"
    return mock_conn, mock_cur


def test_database_connect_url():
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

    with patch("psycopg2.connect") as mock_connect:
        connect(settings)
        mock_connect.assert_called_once_with("postgresql://user:pass@host:5432/db")


def test_database_connect_fallback():
    settings = Settings(
        database_url=None,
        db_user="myuser",
        db_password="mypassword",
        db_host="myhost",
        db_port="5432",
        db_name="mydb",
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

    with patch("psycopg2.connect") as mock_connect:
        connect(settings)
        mock_connect.assert_called_once_with(
            user="myuser",
            password="mypassword",
            host="myhost",
            port="5432",
            dbname="mydb",
        )


def test_database_connect_raises():
    settings = Settings(
        database_url=None,
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

    with pytest.raises(ValueError, match="DATABASE_URL atau DB_USER.*wajib diisi"):
        connect(settings)


@patch("biometeo_worker.database.connect")
def test_import_forecast_batch_empty_rows(mock_connect):
    settings = MagicMock()
    n = import_forecast_batch("2026-06-07T04:00:00Z", "2026-06-07T04:00:00Z", "2026-06-07T05:00:00Z", [], settings)
    assert n == 0
    mock_connect.assert_not_called()


@patch("biometeo_worker.database.connect")
def test_import_forecast_batch_success(mock_connect):
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

    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    def cur_execute(query, params=None):
        query_str = query.decode("utf-8") if isinstance(query, bytes) else query
        q_upper = query_str.upper()
        if "INFORMATION_SCHEMA.COLUMNS" in q_upper:
            mock_cur.fetchall.return_value = [("cloud_cover",), ("tmrt",), ("vapor_pressure",), ("wind_speed_1_1m",)]
        elif "SELECT ID, IS_LATEST FROM PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10, False)
        elif "INSERT INTO PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10,)
        elif "SELECT DESTINATION_ID, FORECAST_TIME::TEXT, TEMPERATURE" in q_upper:
            mock_cur.fetchall.return_value = [
                (1, "2026-06-07 04:00:00+00", 30.0, 60.0, 10.0, 31.0)
            ]
        elif "SELECT KDEPUM_CODE, ID FROM PUBLIC.VILLAGES" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", 100)]
        elif "SELECT V.KDEPUM_CODE, D.DESTINATION_NAME, D.ID" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", "Pantai Kuta", 1)]
        elif "SELECT CATEGORY_KEY, ID FROM PUBLIC.THERMAL_CATEGORIES" in q_upper:
            mock_cur.fetchall.return_value = [("hot", 5), ("warm", 6)]
        elif "SELECT PRODUCED_AT FROM PUBLIC.FORECAST_BATCHES WHERE IS_LATEST = TRUE" in q_upper:
            mock_cur.fetchone.return_value = (datetime(2026, 6, 7, 3, 0, 0, tzinfo=timezone.utc),)

    mock_cur.execute.side_effect = cur_execute

    rows = [
        # Row 1: duplicate of existing, but temp matches (should be skipped)
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07 04:00:00+00",
            temperature=30.0,
            humidity=60.0,
            wind_speed_kmh=10.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=31.0,
            temperate_category_key="hot",
            sub_tropic_category_key="warm",
            cloud_cover=50.0,
            tmrt=35.0,
            vapor_pressure=25.0,
            wind_speed_1_1m=1.0,
        ),
        # Row 2: new forecast time
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T05:00:00Z",
            temperature=31.0,
            humidity=65.0,
            wind_speed_kmh=12.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=32.0,
            temperate_category_key="hot",
            sub_tropic_category_key="warm",
            cloud_cover=50.0,
            tmrt=35.0,
            vapor_pressure=25.0,
            wind_speed_1_1m=1.0,
        ),
        # Row 3: missing village
        ForecastRowDB(
            kdepum_code="missing_kdepum",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T05:00:00Z",
            temperature=31.0,
            humidity=65.0,
            wind_speed_kmh=12.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=32.0,
            temperate_category_key="hot",
            sub_tropic_category_key="warm",
            cloud_cover=50.0,
            tmrt=35.0,
            vapor_pressure=25.0,
            wind_speed_1_1m=1.0,
        ),
        # Row 4: missing destination mapping
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="missing_destination",
            forecast_time="2026-06-07T05:00:00Z",
            temperature=31.0,
            humidity=65.0,
            wind_speed_kmh=12.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=32.0,
            temperate_category_key="hot",
            sub_tropic_category_key="warm",
            cloud_cover=50.0,
            tmrt=35.0,
            vapor_pressure=25.0,
            wind_speed_1_1m=1.0,
        ),
        # Row 5: missing category mapping
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T06:00:00Z",
            temperature=31.0,
            humidity=65.0,
            wind_speed_kmh=12.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=32.0,
            temperate_category_key="missing_cat_temp",
            sub_tropic_category_key="missing_cat_sub",
            cloud_cover=50.0,
            tmrt=35.0,
            vapor_pressure=25.0,
            wind_speed_1_1m=1.0,
        ),
    ]

    n = import_forecast_batch(
        "2026-06-07T04:00:00Z",
        "2026-06-07T04:00:00Z",
        "2026-06-07T06:00:00Z",
        rows,
        settings,
        set_latest=True,
    )
    
    assert n == 2
    mock_conn.commit.assert_called_once()


@patch("biometeo_worker.database.connect")
def test_import_forecast_batch_edge_exceptions_and_skips(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    def cur_execute(query, params=None):
        query_str = query.decode("utf-8") if isinstance(query, bytes) else query
        q_upper = query_str.upper()
        if "INFORMATION_SCHEMA.COLUMNS" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT ID, IS_LATEST FROM PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10, False)
        elif "INSERT INTO PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10,)
        elif "SELECT DESTINATION_ID, FORECAST_TIME::TEXT, TEMPERATURE" in q_upper:
            # 1. Non-string/None time raises split exception (caught by try-except split)
            # 2. String time with non-float temperature raises ValueError (caught by skip try-except)
            mock_cur.fetchall.return_value = [
                (1, None, 30.0, 60.0, 10.0, 31.0),
                (1, "2026-06-07 05:00:00+00", "not_a_float", 60.0, 10.0, 31.0)
            ]
        elif "SELECT KDEPUM_CODE, ID FROM PUBLIC.VILLAGES" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", 100)]
        elif "SELECT V.KDEPUM_CODE, D.DESTINATION_NAME, D.ID" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", "Pantai Kuta", 1)]
        elif "SELECT CATEGORY_KEY, ID FROM PUBLIC.THERMAL_CATEGORIES" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT PRODUCED_AT FROM PUBLIC.FORECAST_BATCHES WHERE IS_LATEST = TRUE" in q_upper:
            mock_cur.fetchone.return_value = None

    mock_cur.execute.side_effect = cur_execute

    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07 05:00:00+00",
            temperature=30.0,
            humidity=60.0,
            wind_speed_kmh=10.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=31.0,
            temperate_category_key=None,
            sub_tropic_category_key=None,
            cloud_cover=None,
            tmrt=None,
            vapor_pressure=None,
            wind_speed_1_1m=None,
        )
    ]

    # This should succeed and insert 1 row
    n = import_forecast_batch(
        "2026-06-07T04:00:00Z",
        "2026-06-07T04:00:00Z",
        "2026-06-07T05:00:00Z",
        rows,
        settings,
        set_latest=True,
    )
    assert n == 1


@patch("biometeo_worker.database.connect")
def test_import_forecast_batch_all_skipped(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    def cur_execute(query, params=None):
        query_str = query.decode("utf-8") if isinstance(query, bytes) else query
        q_upper = query_str.upper()
        if "INFORMATION_SCHEMA.COLUMNS" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT ID, IS_LATEST FROM PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10, False)
        elif "INSERT INTO PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10,)
        elif "SELECT DESTINATION_ID, FORECAST_TIME::TEXT, TEMPERATURE" in q_upper:
            mock_cur.fetchall.return_value = [
                (1, "2026-06-07 04:00:00+00", 30.0, 60.0, 10.0, 31.0)
            ]
        elif "SELECT KDEPUM_CODE, ID FROM PUBLIC.VILLAGES" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", 100)]
        elif "SELECT V.KDEPUM_CODE, D.DESTINATION_NAME, D.ID" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", "Pantai Kuta", 1)]
        elif "SELECT CATEGORY_KEY, ID FROM PUBLIC.THERMAL_CATEGORIES" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT PRODUCED_AT FROM PUBLIC.FORECAST_BATCHES WHERE IS_LATEST = TRUE" in q_upper:
            mock_cur.fetchone.return_value = None

    mock_cur.execute.side_effect = cur_execute

    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07 04:00:00+00",
            temperature=30.0,
            humidity=60.0,
            wind_speed_kmh=10.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=31.0,
            temperate_category_key=None,
            sub_tropic_category_key=None,
            cloud_cover=None,
            tmrt=None,
            vapor_pressure=None,
            wind_speed_1_1m=None,
        )
    ]

    # Since it's identical, it is skipped, tuples is empty. But skipped_count > 0, so it returns 0.
    n = import_forecast_batch(
        "2026-06-07T04:00:00Z",
        "2026-06-07T04:00:00Z",
        "2026-06-07T04:00:00Z",
        rows,
        settings,
        set_latest=True,
    )
    assert n == 0


@patch("biometeo_worker.database.connect")
def test_import_forecast_batch_tz_safety_coverage(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    # We will test:
    # 1. current_latest_produced_at has no tzinfo (tz-naive)
    # 2. current_latest_produced_at has tzinfo, but compare_incoming does not (tz-naive)
    
    # Run 1: db has naive datetime, incoming is tz-aware Z
    def cur_execute_1(query, params=None):
        query_str = query.decode("utf-8") if isinstance(query, bytes) else query
        q_upper = query_str.upper()
        if "INFORMATION_SCHEMA.COLUMNS" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT ID, IS_LATEST FROM PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10, False)
        elif "INSERT INTO PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10,)
        elif "SELECT DESTINATION_ID" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", 100)]
        elif "SELECT V.KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", "Pantai Kuta", 1)]
        elif "SELECT CATEGORY_KEY" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT PRODUCED_AT FROM PUBLIC.FORECAST_BATCHES WHERE IS_LATEST = TRUE" in q_upper:
            # return tz-naive
            mock_cur.fetchone.return_value = (datetime(2026, 6, 7, 3, 0, 0),)

    mock_cur.execute.side_effect = cur_execute_1

    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T05:00:00Z",
            temperature=30.0,
            humidity=60.0,
            wind_speed_kmh=10.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=31.0,
            temperate_category_key=None,
            sub_tropic_category_key=None,
            cloud_cover=None,
            tmrt=None,
            vapor_pressure=None,
            wind_speed_1_1m=None,
        )
    ]

    n = import_forecast_batch(
        "2026-06-07T04:00:00Z",  # tz-aware
        "2026-06-07T04:00:00Z",
        "2026-06-07T05:00:00Z",
        rows,
        settings,
        set_latest=True,
    )
    assert n == 1

    # Run 2: db has tz-aware datetime, incoming is tz-naive
    def cur_execute_2(query, params=None):
        query_str = query.decode("utf-8") if isinstance(query, bytes) else query
        q_upper = query_str.upper()
        if "INFORMATION_SCHEMA.COLUMNS" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT ID, IS_LATEST FROM PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10, False)
        elif "INSERT INTO PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10,)
        elif "SELECT DESTINATION_ID" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", 100)]
        elif "SELECT V.KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", "Pantai Kuta", 1)]
        elif "SELECT CATEGORY_KEY" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT PRODUCED_AT FROM PUBLIC.FORECAST_BATCHES WHERE IS_LATEST = TRUE" in q_upper:
            # return tz-aware
            mock_cur.fetchone.return_value = (datetime(2026, 6, 7, 3, 0, 0, tzinfo=timezone.utc),)

    mock_cur.execute.side_effect = cur_execute_2

    n = import_forecast_batch(
        "2026-06-07T04:00:00",  # tz-naive
        "2026-06-07T04:00:00",
        "2026-06-07T05:00:00",
        rows,
        settings,
        set_latest=True,
    )
    assert n == 1


@patch("biometeo_worker.database.connect")
def test_import_forecast_batch_comparison_fails_gracefully(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    def cur_execute(query, params=None):
        query_str = query.decode("utf-8") if isinstance(query, bytes) else query
        q_upper = query_str.upper()
        if "INFORMATION_SCHEMA.COLUMNS" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT ID, IS_LATEST FROM PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10, False)
        elif "INSERT INTO PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10,)
        elif "SELECT DESTINATION_ID" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", 100)]
        elif "SELECT V.KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", "Pantai Kuta", 1)]
        elif "SELECT CATEGORY_KEY" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT PRODUCED_AT FROM PUBLIC.FORECAST_BATCHES WHERE IS_LATEST = TRUE" in q_upper:
            mock_cur.fetchone.return_value = (datetime(2026, 6, 7, 3, 0, 0, tzinfo=timezone.utc),)

    mock_cur.execute.side_effect = cur_execute

    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T05:00:00Z",
            temperature=30.0,
            humidity=60.0,
            wind_speed_kmh=10.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=31.0,
            temperate_category_key=None,
            sub_tropic_category_key=None,
            cloud_cover=None,
            tmrt=None,
            vapor_pressure=None,
            wind_speed_1_1m=None,
        )
    ]

    # "not-a-date" will cause datetime.fromisoformat to throw ValueError, triggering the except block (lines 317-318)
    n = import_forecast_batch(
        "not-a-date",
        "2026-06-07T04:00:00Z",
        "2026-06-07T05:00:00Z",
        rows,
        settings,
        set_latest=False,
    )
    assert n == 1


@patch("biometeo_worker.database.connect")
def test_import_forecast_batch_not_latest_and_older(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    def cur_execute(query, params=None):
        query_str = query.decode("utf-8") if isinstance(query, bytes) else query
        q_upper = query_str.upper()
        if "INFORMATION_SCHEMA.COLUMNS" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT ID, IS_LATEST FROM PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10, False)
        elif "INSERT INTO PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10,)
        elif "SELECT DESTINATION_ID" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", 100)]
        elif "SELECT V.KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", "Pantai Kuta", 1)]
        elif "SELECT CATEGORY_KEY" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT PRODUCED_AT FROM PUBLIC.FORECAST_BATCHES WHERE IS_LATEST = TRUE" in q_upper:
            # Latest is 2026-06-07 05:00:00
            mock_cur.fetchone.return_value = (datetime(2026, 6, 7, 5, 0, 0, tzinfo=timezone.utc),)

    mock_cur.execute.side_effect = cur_execute

    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T05:00:00Z",
            temperature=30.0,
            humidity=60.0,
            wind_speed_kmh=10.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=31.0,
            temperate_category_key=None,
            sub_tropic_category_key=None,
            cloud_cover=None,
            tmrt=None,
            vapor_pressure=None,
            wind_speed_1_1m=None,
        )
    ]

    # Incoming is 2026-06-07 04:00:00 (older), and set_latest=False.
    # should_activate will be False, executing line 348.
    n = import_forecast_batch(
        "2026-06-07T04:00:00Z",
        "2026-06-07T04:00:00Z",
        "2026-06-07T05:00:00Z",
        rows,
        settings,
        set_latest=False,
    )
    assert n == 1


@patch("biometeo_worker.database.connect")
def test_import_forecast_batch_no_valid_tuples_raises(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    # Setup database introspect and map calls
    def cur_execute(query, params=None):
        query_str = query.decode("utf-8") if isinstance(query, bytes) else query
        q_upper = query_str.upper()
        if "INFORMATION_SCHEMA.COLUMNS" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT ID, IS_LATEST FROM PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = None
        elif "INSERT INTO PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10,)
        elif "SELECT DESTINATION_ID" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [] # no villages -> all missing
        elif "SELECT V.KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT CATEGORY_KEY" in q_upper:
            mock_cur.fetchall.return_value = []

    mock_cur.execute.side_effect = cur_execute

    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T04:00:00Z",
            temperature=30.0,
            humidity=60.0,
            wind_speed_kmh=10.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=31.0,
            temperate_category_key="hot",
            sub_tropic_category_key="warm",
            cloud_cover=50.0,
            tmrt=35.0,
            vapor_pressure=25.0,
            wind_speed_1_1m=1.0,
        )
    ]

    n = import_forecast_batch(
        "2026-06-07T04:00:00Z",
        "2026-06-07T04:00:00Z",
        "2026-06-07T04:00:00Z",
        rows,
        settings,
        set_latest=True,
    )
    assert n == 0
    mock_conn.rollback.assert_called_once()


@patch("biometeo_worker.database.connect")
def test_import_forecast_batch_exception_handling(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    # _get_optional_forecast_columns raises error
    mock_cur.execute.side_effect = RuntimeError("DB Connection error!")

    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T04:00:00Z",
            temperature=30.0,
            humidity=60.0,
            wind_speed_kmh=10.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=31.0,
            temperate_category_key="hot",
            sub_tropic_category_key="warm",
            cloud_cover=50.0,
            tmrt=35.0,
            vapor_pressure=25.0,
            wind_speed_1_1m=1.0,
        )
    ]

    with pytest.raises(RuntimeError, match="DB Connection error!"):
        import_forecast_batch(
            "2026-06-07T04:00:00Z",
            "2026-06-07T04:00:00Z",
            "2026-06-07T04:00:00Z",
            rows,
            settings,
        )
    
    mock_conn.rollback.assert_called_once()


@patch("biometeo_worker.database.connect")
def test_check_already_processed_batches_empty(mock_connect):
    settings = MagicMock()
    res = check_already_processed_batches([], settings)
    assert res == set()
    mock_connect.assert_not_called()


@patch("biometeo_worker.database.connect")
def test_check_already_processed_batches_success(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    # mock database response: returned matching naive timestamps
    mock_cur.fetchall.return_value = [
        (datetime(2026, 6, 7, 4, 0, 0),),
        (datetime(2026, 6, 7, 5, 0, 0),),
    ]

    # Input list has one invalid, two matches, and one non-match
    input_list = [
        "2026-06-07T04:00:00",
        "2026-06-07T05:00:00",
        "2026-06-07T06:00:00",
        "invalid_date_string",
    ]

    res = check_already_processed_batches(input_list, settings)
    # The return values will match exactly the parsed datetime matched string names
    assert res == {"2026-06-07T04:00:00", "2026-06-07T05:00:00"}


@patch("biometeo_worker.database.connect")
def test_check_already_processed_batches_exception(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    mock_cur.execute.side_effect = RuntimeError("DB Query Fail")
    res = check_already_processed_batches(["2026-06-07T04:00:00Z"], settings)
    assert res == set()  # fails safe and returns empty set


@patch("biometeo_worker.destinations_source_db.connect")
def test_fetch_destination_configs_success(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    mock_cur.fetchall.return_value = [
        ("Pantai Kuta", "51.03.01.1002", "Kuta", "Badung", "Kuta", -8.7, 115.1, 5.0)
    ]

    res = fetch_destination_configs(settings)
    assert len(res) == 1
    assert res[0]["destination_name"] == "Pantai Kuta"
    assert res[0]["latitude"] == -8.7
    mock_cur.close.assert_called_once()
    mock_conn.close.assert_called_once()


@patch("biometeo_worker.destinations_source_db.connect")
def test_fetch_destination_configs_exception(mock_connect):
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    mock_cur.execute.side_effect = RuntimeError("DB Error")

    with pytest.raises(RuntimeError, match="DB Error"):
        fetch_destination_configs(settings)
        
    mock_cur.close.assert_called_once()
    mock_conn.close.assert_called_once()


def test_validate_destination_configs_empty():
    with pytest.raises(ValueError, match="Konfigurasi destinasi dari database kosong"):
        validate_destination_configs([])


def test_validate_destination_configs_missing_field():
    # missing latitude
    destinations = [
        {
            "destination_name": "Pantai Kuta",
            "kdepum_code": "51.03.01.1002",
            "village_name": "Kuta",
            "regency": "Badung",
            "district": "Kuta",
            "latitude": None, # type: ignore
            "longitude": 115.1,
            "sea_level_height": 5.0,
        }
    ]
    with pytest.raises(ValueError, match="tidak lengkap"):
        validate_destination_configs(destinations)  # type: ignore[arg-type]


@patch("biometeo_worker.database.connect")
def test_import_forecast_batch_double_safety_tz(mock_connect):
    from unittest.mock import PropertyMock
    
    settings = MagicMock()
    mock_conn, mock_cur = _setup_mock_db(mock_connect)

    # 1. First safety branch: compare_incoming.tzinfo is not None, compare_latest.tzinfo is None
    mock_latest_dt_1 = MagicMock()
    # first access in current_latest_produced_at.tzinfo returns timezone.utc (not None)
    # second access in compare_latest.tzinfo returns None
    type(mock_latest_dt_1).tzinfo = PropertyMock(side_effect=[timezone.utc, None])

    def cur_execute_1(query, params=None):
        query_str = query.decode("utf-8") if isinstance(query, bytes) else query
        q_upper = query_str.upper()
        if "INFORMATION_SCHEMA.COLUMNS" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT ID, IS_LATEST FROM PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10, False)
        elif "INSERT INTO PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10,)
        elif "SELECT DESTINATION_ID" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", 100)]
        elif "SELECT V.KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", "Pantai Kuta", 1)]
        elif "SELECT CATEGORY_KEY" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT PRODUCED_AT FROM PUBLIC.FORECAST_BATCHES WHERE IS_LATEST = TRUE" in q_upper:
            mock_cur.fetchone.return_value = (mock_latest_dt_1,)

    mock_cur.execute.side_effect = cur_execute_1

    rows = [
        ForecastRowDB(
            kdepum_code="51.03.01.1002",
            destination_name="Pantai Kuta",
            forecast_time="2026-06-07T05:00:00Z",
            temperature=30.0,
            humidity=60.0,
            wind_speed_kmh=10.0,
            wind_direction="N",
            weather_condition="Cerah",
            visibility="10km",
            pet_value=31.0,
            temperate_category_key=None,
            sub_tropic_category_key=None,
            cloud_cover=None,
            tmrt=None,
            vapor_pressure=None,
            wind_speed_1_1m=None,
        )
    ]

    with patch("datetime.datetime") as mock_datetime_class:
        mock_incoming_dt = MagicMock()
        mock_incoming_dt.tzinfo = timezone.utc
        mock_incoming_dt.replace.return_value = mock_incoming_dt
        mock_datetime_class.fromisoformat.return_value = mock_incoming_dt

        import_forecast_batch(
            "2026-06-07T04:00:00Z",
            "2026-06-07T04:00:00Z",
            "2026-06-07T05:00:00Z",
            rows,
            settings,
            set_latest=True,
        )

    # 2. Second safety branch: compare_incoming.tzinfo is None, compare_latest.tzinfo is not None
    mock_latest_dt_2 = MagicMock()
    # first access in current_latest_produced_at.tzinfo returns timezone.utc (not None)
    # second access in compare_latest.tzinfo returns timezone.utc (not None)
    type(mock_latest_dt_2).tzinfo = PropertyMock(side_effect=[timezone.utc, timezone.utc])

    def cur_execute_2(query, params=None):
        query_str = query.decode("utf-8") if isinstance(query, bytes) else query
        q_upper = query_str.upper()
        if "INFORMATION_SCHEMA.COLUMNS" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT ID, IS_LATEST FROM PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10, False)
        elif "INSERT INTO PUBLIC.FORECAST_BATCHES" in q_upper:
            mock_cur.fetchone.return_value = (10,)
        elif "SELECT DESTINATION_ID" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", 100)]
        elif "SELECT V.KDEPUM_CODE" in q_upper:
            mock_cur.fetchall.return_value = [("51.03.01.1002", "Pantai Kuta", 1)]
        elif "SELECT CATEGORY_KEY" in q_upper:
            mock_cur.fetchall.return_value = []
        elif "SELECT PRODUCED_AT FROM PUBLIC.FORECAST_BATCHES WHERE IS_LATEST = TRUE" in q_upper:
            mock_cur.fetchone.return_value = (mock_latest_dt_2,)

    mock_cur.execute.side_effect = cur_execute_2

    with patch("datetime.datetime") as mock_datetime_class:
        mock_incoming_dt = MagicMock()
        # first access in incoming_dt.tzinfo returns timezone.utc (not None)
        # second access in compare_incoming.tzinfo returns None
        # third access in compare_incoming.tzinfo returns None
        type(mock_incoming_dt).tzinfo = PropertyMock(side_effect=[timezone.utc, None, None])
        mock_incoming_dt.replace.return_value = mock_incoming_dt
        mock_datetime_class.fromisoformat.return_value = mock_incoming_dt

        import_forecast_batch(
            "2026-06-07T04:00:00Z",
            "2026-06-07T04:00:00Z",
            "2026-06-07T05:00:00Z",
            rows,
            settings,
            set_latest=True,
        )

