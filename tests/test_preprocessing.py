import sys
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from biometeo_worker.preprocessing import (
    _finite_number,
    cloud_percent_to_oktas,
    ws_kmh_to_ms_10m,
    wind_10m_ms_to_1_1m_ms,
    parse_datetimes,
    preprocess_bmkg_record,
    is_nan_value,
)


def test_finite_number():
    assert _finite_number(10.5) is True
    assert _finite_number("10.5") is True
    assert _finite_number(float("nan")) is False
    assert _finite_number(float("inf")) is False
    assert _finite_number("not_a_number") is False


def test_ws_kmh_to_ms_10m():
    assert ws_kmh_to_ms_10m(36.0) == pytest.approx(10.0)


def test_tcc_to_oktas():
    assert cloud_percent_to_oktas(100.0) == 8.0
    assert cloud_percent_to_oktas(0.0) == 0.0
    assert cloud_percent_to_oktas(120.0) == 8.0
    assert cloud_percent_to_oktas(-10.0) == 0.0


def test_wind_10m_ms_to_1_1m_ms_no_biometeo():
    with patch("biometeo_worker.preprocessing.biometeo", None):
        v, note = wind_10m_ms_to_1_1m_ms(10.0)
        assert note == "fallback_power_law_no_biometeo_import"
        assert v == pytest.approx(10.0 * ((1.1 / 10.0) ** 0.2))


def test_wind_10m_ms_to_1_1m_ms_missing_v1m_cal():
    mock_bio = MagicMock()
    del mock_bio.v1m_cal
    with patch("biometeo_worker.preprocessing.biometeo", mock_bio):
        v, note = wind_10m_ms_to_1_1m_ms(10.0)
        assert note == "fallback_power_law_v1m_cal_missing"


def test_wind_10m_ms_to_1_1m_ms_signature_type_error():
    mock_bio = MagicMock()
    # Mocking v1m_cal as a class or object that inspect.signature fails on
    mock_cal = MagicMock()
    mock_bio.v1m_cal = mock_cal
    
    with patch("inspect.signature", side_effect=TypeError("Mock signature type error")):
        with patch("biometeo_worker.preprocessing.biometeo", mock_bio):
            # Positional fallback args_ws10 should succeed
            mock_cal.return_value = 5.0
            v, note = wind_10m_ms_to_1_1m_ms(10.0)
            assert "biometeo.v1m_cal:args_ws10" in note
            assert v == pytest.approx(5.0)


def test_wind_10m_ms_to_1_1m_ms_kwargs_ws_height():
    mock_bio = MagicMock()
    mock_cal = MagicMock()
    mock_bio.v1m_cal = mock_cal
    
    # We mock inspect.signature to return a signature with parameter name "ws"
    class DummyParam:
        def __init__(self, name):
            self.name = name
    
    mock_sig = MagicMock()
    mock_sig.parameters = {"ws": DummyParam("ws"), "height": DummyParam("height")}
    
    with patch("inspect.signature", return_value=mock_sig):
        with patch("biometeo_worker.preprocessing.biometeo", mock_bio):
            mock_cal.return_value = 6.0
            v, note = wind_10m_ms_to_1_1m_ms(10.0)
            assert note == "biometeo.v1m_cal:kwargs_ws_height"
            assert v == pytest.approx(6.0)


def test_wind_10m_ms_to_1_1m_ms_kwargs_WS_height():
    mock_bio = MagicMock()
    mock_cal = MagicMock()
    mock_bio.v1m_cal = mock_cal
    
    class DummyParam:
        def __init__(self, name):
            self.name = name
    
    mock_sig = MagicMock()
    mock_sig.parameters = {"WS": DummyParam("WS"), "height": DummyParam("height")}
    
    with patch("inspect.signature", return_value=mock_sig):
        with patch("biometeo_worker.preprocessing.biometeo", mock_bio):
            mock_cal.return_value = 7.0
            v, note = wind_10m_ms_to_1_1m_ms(10.0)
            assert note == "biometeo.v1m_cal:kwargs_WS_height"
            assert v == pytest.approx(7.0)


def test_wind_10m_ms_to_1_1m_ms_returns_non_finite():
    mock_bio = MagicMock()
    mock_cal = MagicMock()
    mock_bio.v1m_cal = mock_cal
    
    with patch("biometeo_worker.preprocessing.biometeo", mock_bio):
        # returns NaN, which triggers ValueError and fallback power law
        mock_cal.return_value = float("nan")
        v, note = wind_10m_ms_to_1_1m_ms(10.0)
        assert "fallback_power_law_v1m_cal_call_failed" in note
        assert "v1m_cal menghasilkan non-finite" in note


def test_parse_datetimes_invalid():
    with pytest.raises(ValueError, match="tidak valid"):
        parse_datetimes("invalid-date", "2026-01-15T14:00:00+08:00")


def test_preprocess_bmkg_record_success():
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
        "destination_name": "Pantai Kuta",
    }
    out, err = preprocess_bmkg_record(row, static)
    assert err is None
    assert out is not None
    assert out["timezone_offset"] == 8
    assert out["N_oktas"] == pytest.approx(4.0)
    assert out["ws_10m_ms"] == pytest.approx(10.0)


def test_preprocess_bmkg_record_time_error():
    row = {
        "utc_datetime": None,
        "local_datetime": "2026-01-15T14:00:00+08:00",
    }
    static = {}
    out, err = preprocess_bmkg_record(row, static)
    assert out is None
    assert "parse_waktu" in err


def test_preprocess_bmkg_record_temp_humidity_missing():
    row = {
        "utc_datetime": "2026-01-15T06:00:00Z",
        "local_datetime": "2026-01-15T14:00:00+08:00",
        # t and hu missing
    }
    static = {}
    out, err = preprocess_bmkg_record(row, static)
    assert out is None
    assert "suhu/kelembapan" in err


def test_preprocess_bmkg_record_temp_non_finite():
    row = {
        "utc_datetime": "2026-01-15T06:00:00Z",
        "local_datetime": "2026-01-15T14:00:00+08:00",
        "t": "nan",
        "hu": 60.0,
    }
    static = {}
    out, err = preprocess_bmkg_record(row, static)
    assert out is None
    assert "Ta tidak finite" in err


def test_preprocess_bmkg_record_humidity_out_of_bounds():
    row = {
        "utc_datetime": "2026-01-15T06:00:00Z",
        "local_datetime": "2026-01-15T14:00:00+08:00",
        "t": 28.0,
        "hu": 120.0,
    }
    static = {}
    out, err = preprocess_bmkg_record(row, static)
    assert out is None
    assert "RH di luar 0" in err


def test_preprocess_bmkg_record_wind_tcc_missing():
    row = {
        "utc_datetime": "2026-01-15T06:00:00Z",
        "local_datetime": "2026-01-15T14:00:00+08:00",
        "t": 28.0,
        "hu": 60.0,
        # ws/tcc missing
    }
    static = {}
    out, err = preprocess_bmkg_record(row, static)
    assert out is None
    assert "angin/tcc" in err


def test_preprocess_bmkg_record_wind_tcc_non_finite():
    row = {
        "utc_datetime": "2026-01-15T06:00:00Z",
        "local_datetime": "2026-01-15T14:00:00+08:00",
        "t": 28.0,
        "hu": 60.0,
        "ws": "inf",
        "tcc": 50.0,
    }
    static = {}
    out, err = preprocess_bmkg_record(row, static)
    assert out is None
    assert "ws atau tcc tidak finite" in err


def test_preprocess_bmkg_record_zero_wind_stability():
    row = {
        "utc_datetime": "2026-01-15T06:00:00Z",
        "local_datetime": "2026-01-15T14:00:00+08:00",
        "t": 28.0,
        "hu": 60.0,
        "ws": 0.0,
        "tcc": 50.0,
    }
    static = {
        "kdepum_code": "51.03.01.1002",
        "village_name": "Kuta",
        "latitude": -8.7180,
        "longitude": 115.1690,
        "sea_level_height": 5.0,
        "destination_name": "Pantai Kuta",
    }
    out, err = preprocess_bmkg_record(row, static)
    assert err is None
    assert out["wind_speed_1_1m_ms"] == 0.1
    assert "min0.1ms" in out["wind_speed_reduction_method"]


def test_is_nan_value():
    assert is_nan_value(None) is False
    assert is_nan_value(math.nan) is True
    assert is_nan_value(np.nan) is True
    assert is_nan_value(10) is False
    assert is_nan_value(10.5) is False
    assert is_nan_value("string") is False

    # Trigger line 188 by mocking np.isnan to return True for integers
    with patch("numpy.isnan", return_value=True):
        assert is_nan_value(10) is True

    # Trigger TypeError/ValueError exception block
    # We can pass an object that raises TypeError on comparison checks
    class BadCompare:
        def __eq__(self, other):
            raise TypeError("Bad compare error")
    
    with patch("numpy.isnan", side_effect=TypeError("Numpy isnan type error")):
        assert is_nan_value(10.0) is False
