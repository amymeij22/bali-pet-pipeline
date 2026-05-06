import math

import pytest


def test_extract_pet_prefers_pet_v():
    pytest.importorskip("biometeo")
    import biometeo_engine

    assert biometeo_engine.extract_pet({"PET_v": 31.25}) == pytest.approx(31.25)


def test_extract_tmrt_vp_from_dict():
    pytest.importorskip("biometeo")
    import biometeo_engine

    tmrt, vp = biometeo_engine.extract_tmrt_vp({"Tmrt": 45.0, "VP": 20.0})
    assert tmrt == pytest.approx(45.0)
    assert vp == pytest.approx(20.0)


def test_extract_biometeo_value_from_tuple():
    pytest.importorskip("biometeo")
    import biometeo_engine

    # fallback tuple/list: ambil indeks 0 atau 1 yang finite
    assert biometeo_engine.extract_biometeo_value((12.0, 34.0), ["does_not_exist"]) == pytest.approx(12.0)
    # non-finite di index 0, finite di index 1
    assert biometeo_engine.extract_biometeo_value((math.nan, 34.0), ["does_not_exist"]) == pytest.approx(34.0)

