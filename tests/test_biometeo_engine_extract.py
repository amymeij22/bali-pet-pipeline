import math

import pytest


def test_extract_pet_prefers_pet_v():
    pytest.importorskip("biometeo")
    from biometeo_worker import biometeo_engine

    assert biometeo_engine.extract_pet({"PET_v": 31.25}) == pytest.approx(31.25)


def test_extract_tmrt_vp_from_dict():
    pytest.importorskip("biometeo")
    from biometeo_worker import biometeo_engine

    tmrt, vp = biometeo_engine.extract_tmrt_vp({"Tmrt": 45.0, "VP": 20.0})
    assert tmrt == pytest.approx(45.0)
    assert vp == pytest.approx(20.0)


def test_extract_biometeo_value_from_tuple():
    pytest.importorskip("biometeo")
    from biometeo_worker import biometeo_engine

    # fallback tuple/list: ambil indeks 0 atau 1 yang finite
    assert biometeo_engine.extract_biometeo_value((12.0, 34.0), ["does_not_exist"]) == pytest.approx(12.0)
    # non-finite di index 0, finite di index 1
    assert biometeo_engine.extract_biometeo_value((math.nan, 34.0), ["does_not_exist"]) == pytest.approx(34.0)
    # tuple conversion exception cover
    assert biometeo_engine.extract_biometeo_value(("not_a_float", 34.0), ["does_not_exist"]) == pytest.approx(34.0)


def test_calculate_biometeo_outputs():
    pytest.importorskip("biometeo")
    from biometeo_worker import biometeo_engine

    row = {
        "Ta": 25.0,
        "RH": 60.0,
        "wind_speed_1_1m_ms": 1.5,
        "longitude": 115.2167,
        "latitude": -8.65,
        "sea_level_height": 10.0,
        "day_of_year": 165,
        "hour_of_day": 12.0,
        "timezone_offset": 8,
        "N_oktas": 4.0,
    }
    res = biometeo_engine.calculate_biometeo_outputs(row)
    assert "tmrt" in res
    assert "vapor_pressure" in res
    assert "wind_speed_1_1m" in res
    assert "pet_value" in res
    assert math.isfinite(res["tmrt"])
    assert math.isfinite(res["pet_value"])

    # Test v = 0.0 stability logic
    row_calm = row.copy()
    row_calm["wind_speed_1_1m_ms"] = 0.0
    res_calm = biometeo_engine.calculate_biometeo_outputs(row_calm)
    assert res_calm["wind_speed_1_1m"] == pytest.approx(0.1)


def test_calculate_biometeo_outputs_type_errors():
    pytest.importorskip("biometeo")
    from unittest.mock import patch
    from biometeo_worker import biometeo_engine

    row = {
        "Ta": 25.0,
        "RH": 60.0,
        "wind_speed_1_1m_ms": 1.5,
        "longitude": 115.2167,
        "latitude": -8.65,
        "sea_level_height": 10.0,
        "day_of_year": 165,
        "hour_of_day": 12.0,
        "timezone_offset": 8,
        "N_oktas": 4.0,
    }

    # 1. Mock Tmrt_calc to raise TypeError
    with patch("biometeo.Tmrt_calc", side_effect=TypeError("mocked Tmrt_calc type error")):
        with pytest.raises(TypeError, match="mocked Tmrt_calc type error"):
            biometeo_engine.calculate_biometeo_outputs(row)

    # 2. Mock PET to raise TypeError
    with patch("biometeo.PET", side_effect=TypeError("mocked PET type error")):
        with pytest.raises(TypeError, match="mocked PET type error"):
            biometeo_engine.calculate_biometeo_outputs(row)



def test_calculate_biometeo_outputs():
    pytest.importorskip("biometeo")
    from biometeo_worker import biometeo_engine

    row = {
        "Ta": 25.0,
        "RH": 60.0,
        "wind_speed_1_1m_ms": 1.5,
        "longitude": 115.2167,
        "latitude": -8.65,
        "sea_level_height": 10.0,
        "day_of_year": 165,
        "hour_of_day": 12.0,
        "timezone_offset": 8,
        "N_oktas": 4.0,
    }
    res = biometeo_engine.calculate_biometeo_outputs(row)
    assert "tmrt" in res
    assert "vapor_pressure" in res
    assert "wind_speed_1_1m" in res
    assert "pet_value" in res
    assert math.isfinite(res["tmrt"])
    assert math.isfinite(res["pet_value"])

    # Test v = 0.0 stability logic
    row_calm = row.copy()
    row_calm["wind_speed_1_1m_ms"] = 0.0
    res_calm = biometeo_engine.calculate_biometeo_outputs(row_calm)
    assert res_calm["wind_speed_1_1m"] == pytest.approx(0.1)


def test_extract_biometeo_value_attribute_and_errors():
    pytest.importorskip("biometeo")
    from biometeo_worker import biometeo_engine

    # Object attribute extraction
    class DummyResult:
        def __init__(self, val):
            self.test_val = val

    dummy = DummyResult(15.5)
    assert biometeo_engine.extract_biometeo_value(dummy, ["test_val"]) == pytest.approx(15.5)

    # Object attribute extraction non-finite error
    dummy_nan = DummyResult(math.nan)
    with pytest.raises(ValueError, match="Tidak bisa mengekstrak nilai"):
        biometeo_engine.extract_biometeo_value(dummy_nan, ["test_val"])

    # Dict extraction non-finite error
    with pytest.raises(ValueError, match="Tidak bisa mengekstrak nilai"):
        biometeo_engine.extract_biometeo_value({"test_val": math.inf}, ["test_val"])

    # Extraction raises ValueError when extraction is impossible
    with pytest.raises(ValueError, match="extract_biometeo_value: result is None"):
        biometeo_engine.extract_biometeo_value(None, ["test"])

    with pytest.raises(ValueError, match="Tidak bisa mengekstrak nilai"):
        biometeo_engine.extract_biometeo_value({"invalid": "value"}, ["test"])

    with pytest.raises(ValueError, match="Tidak bisa mengekstrak nilai"):
        biometeo_engine.extract_biometeo_value((math.nan, math.inf), ["test"])


