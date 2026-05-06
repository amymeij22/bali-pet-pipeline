"""Ambil konfigurasi destinasi dari database (source-of-truth).

Kebutuhan komputasi biometeo per destinasi:
- kdepum_code
- village_name
- latitude
- longitude
- sea_level_height

Tabel `public.destinations` menyimpan relasi + metadata lokasi per destinasi.
KDEPUM/nama desa serta regency/district diambil dari `public.villages` (FK ke tabel master).
"""

from __future__ import annotations

from typing import Any

from database import connect
from destinations import DestinationConfig
from logger import get_logger

log = get_logger(__name__)


def fetch_destination_configs(settings) -> list[DestinationConfig]:
    """
    Mengambil daftar destinasi (satu baris per destination_name) dari database.

    Return:
      list[DestinationConfig] — format sama dengan `DESTINATIONS` pada `destinations.py`.
    """
    conn = connect(settings)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
              d.destination_name,
              v.kdepum_code,
              v.village_name AS village_name,
              COALESCE(r.name, '') AS regency,
              COALESCE(di.name, '') AS district,
              d.latitude,
              d.longitude,
              d.sea_level_height
            FROM public.destinations d
            JOIN public.villages v ON v.id = d.village_id
            LEFT JOIN public.regencies r ON r.id = v.regency_id
            LEFT JOIN public.districts di ON di.id = v.district_id
            ORDER BY v.kdepum_code, d.destination_name
            """
        )
        rows = cur.fetchall()
        out: list[DestinationConfig] = []
        for r in rows:
            destination_name, kdepum_code, village_name, regency, district, latitude, longitude, sea_level_height = r
            out.append(
                {
                    "destination_name": str(destination_name),
                    "kdepum_code": str(kdepum_code),
                    "village_name": str(village_name),
                    "regency": str(regency),
                    "district": str(district),
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "sea_level_height": float(sea_level_height),
                }
            )
        return out
    except Exception:  # noqa: BLE001
        log.exception("Gagal mengambil destinasi dari database")
        raise
    finally:
        cur.close()
        conn.close()


def validate_destination_configs(destinations: list[DestinationConfig]) -> None:
    if not destinations:
        raise ValueError("Konfigurasi destinasi dari database kosong")

    missing: list[dict[str, Any]] = []
    for d in destinations:
        for k in [
            "destination_name",
            "kdepum_code",
            "village_name",
            "regency",
            "district",
            "latitude",
            "longitude",
            "sea_level_height",
        ]:
            if k not in d or d[k] in [None, ""]:
                missing.append({"kdepum_code": d.get("kdepum_code"), "missing": k})
                break

    if missing:
        sample = missing[:5]
        raise ValueError(
            "Konfigurasi destinasi dari DB tidak lengkap untuk biometeo. "
            f"Contoh baris bermasalah: {sample}"
        )

