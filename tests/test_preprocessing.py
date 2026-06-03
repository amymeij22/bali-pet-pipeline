import pytest

import sys
from pathlib import Path

# Agar import modul di folder induk `src/` berfungsi saat pytest dari root/repo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from biometeo_worker.preprocessing import cloud_percent_to_oktas, preprocess_bmkg_record, ws_kmh_to_ms_10m


def test_ws_kmh_to_ms_10m():
    assert ws_kmh_to_ms_10m(36.0) == pytest.approx(10.0)


def test_tcc_to_oktas():
    assert cloud_percent_to_oktas(100.0) == 8.0
    assert cloud_percent_to_oktas(0.0) == 0.0


def test_preprocess_timezone_and_rh():
    row = {
        "utc_datetime": "2026-01-15T06:00:00Z",
        "local_datetime": "2026-01-15T14:00:00+08:00",
        "t": 28.0,
        "hu": 65.0,
        "ws": 36.0,
        "wd": "E",
        "tcc": 50.0,
        "weather_desc": "Cerah",
        "vs_text": "Baik",
    }
    static = {
        "kdepum_code": "51.03.01.1002",
        "village_name": "Kuta",
        "latitude": -8.7180,
        "longitude": 115.1690,
        "sea_level_height": 5.0,
        "destination_name": ["Pantai Kuta"],
    }
    out, err = preprocess_bmkg_record(row, static)
    assert err is None
    assert out is not None
    assert out["timezone_offset"] == 8
    assert out["N_oktas"] == pytest.approx(4.0)
    assert out["ws_10m_ms"] == pytest.approx(10.0)


def test_preprocess_rh_invalid():
    row = {
        "utc_datetime": "2026-01-15T06:00:00Z",
        "local_datetime": "2026-01-15T14:00:00+08:00",
        "t": 28.0,
        "hu": 101.0,
        "ws": 10.0,
        "wd": "E",
        "tcc": 0.0,
        "weather_desc": "Cerah",
        "vs_text": "Baik",
    }
    static = {
        "kdepum_code": "51.03.01.1002",
        "village_name": "Kuta",
        "latitude": -8.7180,
        "longitude": 115.1690,
        "sea_level_height": 5.0,
        "destination_name": ["Pantai Kuta"],
    }
    out, err = preprocess_bmkg_record(row, static)
    assert out is None
    assert err is not None
