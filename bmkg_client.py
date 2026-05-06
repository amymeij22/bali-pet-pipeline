"""Client BMKG: satu request per KDEPUM unik, dengan retry & logging."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests

from config import Settings
from logger import get_logger

log = get_logger(__name__)


@dataclass
class BmkgFetchResult:
    produced_at: str | None
    forecast_start: str | None
    forecast_end: str | None
    failed_villages: list[dict[str, Any]] = field(default_factory=list)
    raw_records: list[dict[str, Any]] = field(default_factory=list)


def _validate_json(resp: requests.Response) -> dict[str, Any]:
    if resp.status_code != 200:
        raise ValueError(f"HTTP {resp.status_code}")
    ctype = resp.headers.get("Content-Type", "")
    if "application/json" not in ctype:
        raise ValueError(f"bukan JSON (Content-Type={ctype})")
    data = resp.json()
    if "lokasi" not in data or "data" not in data:
        raise ValueError(f"struktur tidak valid keys={list(data.keys())}")
    return data


def fetch_forecast_for_village(
    kdepum_code: str,
    village_name: str,
    destination_names: list[str],
    settings: Settings,
    bmkg_lat: float | None = None,
    bmkg_lon: float | None = None,
) -> tuple[list[dict[str, Any]], str | None, str | None, str | None, str | None]:
    """
    Mengembalikan (records, produced_at, error).
    records: list item cuaca BMKG yang sudah ditambah metadata statis.
    """
    url = f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={kdepum_code}"
    headers = {
        "User-Agent": "PET-Bali-Thermal-Pipeline/1.0 (+https://bmkg.go.id; diseminasi penelitian)",
        "Accept": "application/json",
    }

    last_err: str | None = None
    for attempt in range(settings.request_retry_count):
        try:
            resp = requests.get(url, timeout=settings.request_timeout_seconds, headers=headers)
            data = _validate_json(resp)
            loc = data["lokasi"]
            produced = None
            records: list[dict[str, Any]] = []

            for group in data["data"][0]["cuaca"]:
                for item in group:
                    if produced is None:
                        produced = data["data"][0]["cuaca"][0][0].get("analysis_date")
                    item2 = dict(item)
                    item2.update(
                        {
                            "kdepum_code": kdepum_code,
                            "village_name": village_name,
                            "destination_names": destination_names,
                            "bmkg_lat": bmkg_lat if bmkg_lat is not None else loc.get("lat"),
                            "bmkg_lon": bmkg_lon if bmkg_lon is not None else loc.get("lon"),
                            "bmkg_timezone": loc.get("timezone"),
                        }
                    )
                    records.append(item2)

            if not records:
                return [], produced, None, None, "response tanpa record cuaca"

            fts = [r.get("utc_datetime") for r in records if r.get("utc_datetime")]
            f_start = min(fts) if fts else None
            f_end = max(fts) if fts else None
            return records, produced, f_start, f_end, None
        except requests.exceptions.Timeout:
            last_err = "timeout"
        except requests.exceptions.RequestException as e:
            last_err = f"request_error:{e}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}:{e}"

        if attempt < settings.request_retry_count - 1:
            time.sleep(settings.request_retry_delay_seconds)

    return [], None, None, None, last_err or "unknown_error"


def fetch_all_unique_villages(
    villages: list[dict[str, Any]],
    settings: Settings,
) -> BmkgFetchResult:
    out = BmkgFetchResult(produced_at=None, forecast_start=None, forecast_end=None)
    all_utc: list[str] = []

    for i, v in enumerate(villages):
        kdep = v["kdepum_code"]
        log.info("BMKG fetch [%s/%s] kdepum=%s village=%s", i + 1, len(villages), kdep, v["village_name"])
        recs, prod, fs, fe, err = fetch_forecast_for_village(
            kdepum_code=kdep,
            village_name=v["village_name"],
            destination_names=v.get("destination_names", []),
            settings=settings,
        )
        if err:
            log.error("BMKG gagal kdepum=%s village=%s: %s", kdep, v["village_name"], err)
            out.failed_villages.append({"kdepum_code": kdep, "village_name": v["village_name"], "error": err})
        else:
            out.raw_records.extend(recs)
            if prod and out.produced_at is None:
                out.produced_at = prod
            if fs:
                all_utc.append(fs)
            if fe:
                all_utc.append(fe)

        if i < len(villages) - 1:
            time.sleep(settings.request_delay_seconds)

    if all_utc:
        out.forecast_start = min(all_utc)
        out.forecast_end = max(all_utc)
    return out
