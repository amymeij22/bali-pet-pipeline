"""Wrapper biometeo 0.4.1: Tmrt_calc + PET."""

from __future__ import annotations

import math
from typing import Any

try:
    import biometeo
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "Package biometeo==0.4.1 wajib terpasang. "
        "Jangan fallback ke pythermalcomfort/pvlib. Pasang wheel yang sesuai Python/OS."
    ) from e

from biometeo_worker.logger import get_logger

log = get_logger(__name__)

# Parameter fisiologis skripsi revisi (wajib)
PET_PHYS = dict(
    icl=0.9,
    work=80,
    ht=1.75,
    mbody=75,
    age=35,
    sex=1,
    pos=1,
)


def extract_biometeo_value(result: Any, keys: list[str]) -> float:
    """Ambil nilai numerik dari dict / object / tuple(list) dengan kunci/kandidat indeks."""
    if result is None:
        raise ValueError("extract_biometeo_value: result is None")

    last_err: Exception | None = None

    for key in keys:
        if isinstance(result, dict) and key in result:
            try:
                v = float(result[key])
                if math.isnan(v) or math.isinf(v):
                    raise ValueError(f"non-finite {key}={v}")
                return v
            except Exception as e:  # noqa: BLE001
                last_err = e

        if hasattr(result, key):
            try:
                v = float(getattr(result, key))
                if math.isnan(v) or math.isinf(v):
                    raise ValueError(f"non-finite {key}={v}")
                return v
            except Exception as e:  # noqa: BLE001
                last_err = e

    if isinstance(result, (list, tuple)):
        for i in (0, 1):
            if len(result) > i:
                try:
                    v = float(result[i])
                    if not math.isnan(v) and not math.isinf(v):
                        return v
                except Exception as e:  # noqa: BLE001
                    last_err = e

    raise ValueError(
        f"Tidak bisa mengekstrak nilai dari hasil biometeo. keys={keys!r} type={type(result)!r} err={last_err!r}"
    )


def extract_tmrt_vp(tmrt_result: Any) -> tuple[float, float]:
    tmrt = extract_biometeo_value(tmrt_result, ["Tmrt", "tmrt", "TMRT"])
    vp = extract_biometeo_value(tmrt_result, ["VP", "vp", "Vp"])
    return tmrt, vp


def extract_pet(pet_result: Any) -> float:
    return extract_biometeo_value(pet_result, ["PET_v", "PET", "pet", "Pet"])


def calculate_biometeo_outputs(preprocessed_row: dict[str, Any]) -> dict[str, Any]:
    """
    Hitung Tmrt, tekanan uap (VP), dan PET untuk satu baris ter-preprocess.
    Mengembalikan dict dengan kunci: tmrt, vapor_pressure, wind_speed_1_1m, pet_value
    """
    Ta = float(preprocessed_row["Ta"])
    RH = float(preprocessed_row["RH"])
    v = float(preprocessed_row["wind_speed_1_1m_ms"])
    if v == 0.0:
        v = 0.1  # stabilitas numerik PET

    longitude = float(preprocessed_row["longitude"])
    latitude = float(preprocessed_row["latitude"])
    sea_level_height = float(preprocessed_row["sea_level_height"])
    day_of_year = int(preprocessed_row["day_of_year"])
    hour_of_day = float(preprocessed_row["hour_of_day"])
    timezone_offset = int(preprocessed_row["timezone_offset"])
    N = float(preprocessed_row["N_oktas"])

    try:
        tmrt_result = biometeo.Tmrt_calc(
            Ta=Ta,
            RH=RH,
            v=v,
            longitude=longitude,
            latitude=latitude,
            sea_level_height=sea_level_height,
            day_of_year=day_of_year,
            hour_of_day=hour_of_day,
            timezone_offset=timezone_offset,
            N=N,
            alb=0.3,
            albhum=0.3,
            RedGChk=False,
            foglimit=90,
            bowen=1.0,
        )
    except TypeError as e:
        log.error("Tmrt_calc TypeError — periksa versi biometeo / nama argumen: %s", e)
        raise

    Tmrt, VP = extract_tmrt_vp(tmrt_result)

    try:
        pet_result = biometeo.PET(
            Ta=Ta,
            VP=VP,
            v=v,
            Tmrt=Tmrt,
            **PET_PHYS,
        )
    except TypeError as e:
        log.error("PET TypeError — periksa versi biometeo / nama argumen: %s", e)
        raise

    pet_value = extract_pet(pet_result)

    return {
        "tmrt": Tmrt,
        "vapor_pressure": VP,
        "wind_speed_1_1m": v,
        "pet_value": pet_value,
    }
