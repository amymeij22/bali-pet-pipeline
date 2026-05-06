"""
Smoke test biometeo — membutuhkan package terpasang (wheel sesuai Python/OS).

Jika lingkungan tidak mendukung instalasi biometeo, lewati tes ini:
  pytest -m "not biometeo_smoke"
atau:
  pytest --ignore=tests/test_biometeo_smoke.py
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytestmark = [pytest.mark.biometeo_smoke]


def test_tmrt_and_pet_finite():
    biometeo = pytest.importorskip("biometeo")

    from biometeo_engine import extract_pet, extract_tmrt_vp

    tmrt_res = biometeo.Tmrt_calc(
        Ta=25.0,
        RH=60.0,
        v=0.5,
        longitude=115.1889,
        latitude=-8.4095,
        sea_level_height=50.0,
        day_of_year=100,
        hour_of_day=12.0,
        timezone_offset=8,
        N=4.0,
        alb=0.3,
        albhum=0.3,
        RedGChk=False,
        foglimit=90,
        bowen=1.0,
    )
    Tmrt, VP = extract_tmrt_vp(tmrt_res)
    assert math.isfinite(Tmrt) and math.isfinite(VP)

    pet_res = biometeo.PET(
        Ta=25.0,
        VP=VP,
        v=0.5,
        Tmrt=Tmrt,
        icl=0.9,
        work=80,
        ht=1.75,
        mbody=75,
        age=35,
        sex=1,
        pos=1,
    )
    pet = extract_pet(pet_res)
    assert math.isfinite(pet)
