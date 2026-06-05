"""Prapemrosesan baris forecast BMKG -> input biometeo."""

from __future__ import annotations

import inspect
import math
from typing import Any

import numpy as np
import pandas as pd

try:
    import biometeo
except ImportError:  # pragma: no cover - di lingkungan tanpa wheel
    biometeo = None  # type: ignore


def _finite_number(x: Any) -> bool:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False
    return not math.isnan(v) and not math.isinf(v)


def cloud_percent_to_oktas(cloud_cover_percent: float) -> float:
    """tcc % -> oktas N, clamp 0–8."""
    n = float(cloud_cover_percent) / 12.5
    return max(0.0, min(8.0, n))


def ws_kmh_to_ms_10m(ws_kmh: float) -> float:
    """BMKG ws dalam km/jam -> m/s pada ketinggian referensi 10 m (asumsi skrip lama: /3.6)."""
    return float(ws_kmh) / 3.6


def wind_10m_ms_to_1_1m_ms(ws_10m_ms: float, alpha: float = 0.2) -> tuple[float, str]:
    """
    Mengurangi kecepatan angin dari ~10 m ke 1.1 m.
    Prioritas: biometeo.v1m_cal jika tersedia dan bisa dipanggil.
    Fallback: power law eksplisit (hanya jika v1m_cal tidak tersedia/gagal).
    Mengembalikan (v_1_1m_ms, method_note).
    """
    if biometeo is None:
        # Paket biometeo tidak terpasang: gunakan fallback power law (bukan sumber utama di produksi).
        v = ws_10m_ms * ((1.1 / 10.0) ** alpha)
        return v, "fallback_power_law_no_biometeo_import"

    cal = getattr(biometeo, "v1m_cal", None)
    if cal is None or not callable(cal):
        v = ws_10m_ms * ((1.1 / 10.0) ** alpha)
        return v, "fallback_power_law_v1m_cal_missing"

    sig = None
    try:
        sig = inspect.signature(cal)
    except (TypeError, ValueError):
        sig = None

    attempts: list[tuple[str, dict[str, Any]]] = []
    if sig is not None:
        params = sig.parameters
        if "WS" in params and "height" in params:
            attempts.append(("kwargs_WS_height", {"WS": ws_10m_ms, "height": 10.0}))
        if "ws" in params and "height" in params:
            attempts.append(("kwargs_ws_height", {"ws": ws_10m_ms, "height": 10.0}))

    attempts.extend(
        [
            ("args_ws10", (ws_10m_ms, 10.0)),
            ("args_height_first", (10.0, ws_10m_ms)),
        ]
    )

    last_err: Exception | None = None
    for name, payload in attempts:
        try:
            if isinstance(payload, dict):
                out = cal(**payload)
            else:
                out = cal(*payload)
            v = float(out)
            if math.isnan(v) or math.isinf(v):
                raise ValueError(f"v1m_cal menghasilkan non-finite: {v}")
            return v, f"biometeo.v1m_cal:{name}"
        except Exception as e:  # noqa: BLE001 - kita coba variasi pemanggilan
            last_err = e
            continue

    v = ws_10m_ms * ((1.1 / 10.0) ** alpha)
    note = "fallback_power_law_v1m_cal_call_failed"
    if last_err is not None:
        note += f":{last_err!s}"
    return v, note


def parse_datetimes(utc_s: str, local_s: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    utc_dt = pd.to_datetime(utc_s, utc=True, errors="coerce")
    local_dt = pd.to_datetime(local_s, errors="coerce")
    if pd.isna(utc_dt) or pd.isna(local_dt):
        raise ValueError("utc_datetime/local_datetime tidak valid")
    return utc_dt, local_dt


def preprocess_bmkg_record(
    row: dict[str, Any],
    static: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """
    row: satu item cuaca dari BMKG + metadata aplikasi
    static: kdepum_code, village_name, latitude, longitude, sea_level_height, destination_name, ...
    Mengembalikan (preprocessed_dict, error_message).
    """
    try:
        utc_dt, local_dt = parse_datetimes(str(row["utc_datetime"]), str(row["local_datetime"]))
    except Exception as e:  # noqa: BLE001
        return None, f"parse_waktu: {e}"

    day_of_year = int(local_dt.dayofyear)
    hour_of_day = float(local_dt.hour) + float(local_dt.minute) / 60.0
    timezone_offset = 8

    try:
        Ta = float(row["t"])
        RH = float(row["hu"])
    except (KeyError, TypeError, ValueError) as e:
        return None, f"suhu/kelembapan: {e}"

    if not _finite_number(Ta):
        return None, "Ta tidak finite"
    if not (0.0 <= RH <= 100.0):
        return None, f"RH di luar 0–100: {RH}"

    try:
        ws_kmh = float(row["ws"])
        tcc = float(row["tcc"])
    except (KeyError, TypeError, ValueError) as e:
        return None, f"angin/tcc: {e}"

    if not _finite_number(ws_kmh) or not _finite_number(tcc):
        return None, "ws atau tcc tidak finite"

    ws_10m_ms = ws_kmh_to_ms_10m(ws_kmh)
    v_1_1m, wind_method = wind_10m_ms_to_1_1m_ms(ws_10m_ms)
    if v_1_1m == 0.0:
        # Stabilitas numerik PET (bukan mengubah metodologi BMKG)
        v_1_1m = 0.1
        wind_method += "+min0.1ms"

    N = cloud_percent_to_oktas(tcc)

    lat = float(static["latitude"])
    lon = float(static["longitude"])
    h = float(static["sea_level_height"])

    out = {
        **row,
        "kdepum_code": static["kdepum_code"],
        "village_name": static["village_name"],
        "destination_name": static.get("destination_name"),
        "latitude": lat,
        "longitude": lon,
        "sea_level_height": h,
        "Ta": Ta,
        "RH": RH,
        "wind_speed_kmh_bmkg": ws_kmh,
        "ws_10m_ms": ws_10m_ms,
        "wind_speed_1_1m_ms": v_1_1m,
        "wind_speed_reduction_method": wind_method,
        "cloud_cover_percent": tcc,
        "N_oktas": N,
        "utc_datetime": utc_dt.isoformat(),
        "local_datetime": local_dt.isoformat(),
        "day_of_year": day_of_year,
        "hour_of_day": hour_of_day,
        "timezone_offset": timezone_offset,
    }
    return out, None


def is_nan_value(x: Any) -> bool:
    if x is None:
        return False
    try:
        if isinstance(x, float) and math.isnan(x):
            return True
        if isinstance(x, (float, int)) and np.isnan(x):  # type: ignore[arg-type]
            return True
    except (TypeError, ValueError):
        return False
    return False
