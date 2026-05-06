"""Sinkronisasi master destinasi (lokal → database).

Catatan:
- Script ini sumber kebenarannya adalah `cloudrun/destinations.py` (data destinasi + koordinat/elevasi).
- Target:
  - `public.villages`: pastikan KDEPUM + metadata administratif (`regencies/districts` via FK) sesuai
  - `public.destinations`: pastikan koordinat/elevasi destinasi identik dengan `DESTINATIONS` lokal
- Mekanisme verifikasi:
  - Upsert (insert/update) untuk regencies, districts, villages
  - Upsert untuk destinations
  - Delete destinations ekstra di DB yang tidak ada di lokal
  - Verifikasi join DB vs lokal: harus 100% sama
"""

from __future__ import annotations

import os
import sys
import argparse
from dataclasses import dataclass

# Agar bisa dijalankan langsung:
# `python scripts/sync_destinations_to_db.py`
if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import connect
from destinations import DESTINATIONS, DestinationConfig
from logger import get_logger, setup_logging

log = get_logger(__name__)


@dataclass(frozen=True)
class DesiredDestination:
    kdepum_code: str
    village_name: str
    regency: str
    district: str
    destination_name: str
    latitude: float
    longitude: float
    sea_level_height: float


def _desired() -> list[DesiredDestination]:
    out: list[DesiredDestination] = []
    for d in DESTINATIONS:
        if not d.get("kdepum_code"):
            raise ValueError(f"kdepum_code kosong untuk destinasi: {d.get('destination_name')}")
        out.append(
            DesiredDestination(
                kdepum_code=str(d["kdepum_code"]),
                village_name=str(d["village_name"]),
                regency=str(d["regency"]),
                district=str(d["district"]),
                destination_name=str(d["destination_name"]),
                latitude=float(d["latitude"]),
                longitude=float(d["longitude"]),
                sea_level_height=float(d["sea_level_height"]),
            )
        )
    return out


def sync(*, settings, dry_run: bool) -> None:
    desired = _desired()
    desired_by_kdep: dict[str, list[DesiredDestination]] = {}
    for d in desired:
        desired_by_kdep.setdefault(d.kdepum_code, []).append(d)

    conn = connect(settings)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        # Upsert master regencies/districts dan bangun map name->id
        desired_regencies = sorted({d.regency for d in desired})
        log.info("Regencies upsert: %s", len(desired_regencies))
        if not dry_run and desired_regencies:
            cur.executemany(
                """
                INSERT INTO public.regencies (name)
                VALUES (%s)
                ON CONFLICT (name) DO NOTHING
                """,
                [(r,) for r in desired_regencies],
            )

        cur.execute("SELECT id, name FROM public.regencies")
        reg_map = {r[1]: r[0] for r in cur.fetchall()}
        missing_reg = [r for r in desired_regencies if r not in reg_map]
        if missing_reg:
            raise RuntimeError(f"Regency belum ada di DB: {missing_reg[:10]}")

        desired_district_pairs = sorted({(d.regency, d.district) for d in desired})
        log.info("Districts upsert: %s", len(desired_district_pairs))
        if not dry_run and desired_district_pairs:
            cur.executemany(
                """
                INSERT INTO public.districts (regency_id, name)
                VALUES (%s, %s)
                ON CONFLICT (regency_id, name) DO NOTHING
                """,
                [(reg_map[reg], dist) for reg, dist in desired_district_pairs],
            )

        cur.execute(
            """
            SELECT d.id, r.name, d.name
            FROM public.districts d
            JOIN public.regencies r ON r.id = d.regency_id
            """
        )
        dist_map = {(rname, dname): did for (did, rname, dname) in cur.fetchall()}
        missing_dist = [p for p in desired_district_pairs if p not in dist_map]
        if missing_dist:
            raise RuntimeError(f"District belum ada di DB: {missing_dist[:10]}")

        # villages map
        cur.execute("SELECT id, kdepum_code, village_name, regency_id, district_id FROM public.villages")
        v_rows = cur.fetchall()
        v_by_kdep = {r[1]: {"id": r[0], "village_name": r[2], "regency_id": r[3], "district_id": r[4]} for r in v_rows}

        # Ensure villages exist & metadata konsisten per kdepum_code
        to_insert_v = []
        to_update_v = []
        for kdep, items in desired_by_kdep.items():
            vname = items[0].village_name
            reg = items[0].regency
            dist = items[0].district
            for it in items[1:]:
                if it.regency != reg or it.district != dist or it.village_name != vname:
                    raise ValueError(
                        f"Inkonistensi metadata village untuk kdepum={kdep}: "
                        f"({vname},{reg},{dist}) vs ({it.village_name},{it.regency},{it.district})"
                    )

            existing = v_by_kdep.get(kdep)
            reg_id = reg_map[reg]
            dist_id = dist_map[(reg, dist)]
            if not existing:
                to_insert_v.append((kdep, vname, reg_id, dist_id))
            else:
                if (
                    existing.get("village_name") != vname
                    or existing.get("regency_id") != reg_id
                    or existing.get("district_id") != dist_id
                ):
                    to_update_v.append((vname, reg_id, dist_id, kdep))

        if to_insert_v:
            log.info("Villages insert: %s", len(to_insert_v))
            if not dry_run:
                cur.executemany(
                    """
                    INSERT INTO public.villages (kdepum_code, village_name, regency_id, district_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (kdepum_code)
                    DO UPDATE SET
                      village_name = EXCLUDED.village_name,
                      regency_id = EXCLUDED.regency_id,
                      district_id = EXCLUDED.district_id
                    """,
                    to_insert_v,
                )

        if to_update_v:
            log.info("Villages update metadata: %s", len(to_update_v))
            if not dry_run:
                cur.executemany(
                    "UPDATE public.villages SET village_name = %s, regency_id = %s, district_id = %s WHERE kdepum_code = %s",
                    to_update_v,
                )

        # Refresh village ids after insert/update
        cur.execute("SELECT id, kdepum_code, village_name, regency_id, district_id FROM public.villages")
        v_rows = cur.fetchall()
        v_by_kdep = {r[1]: {"id": r[0], "village_name": r[2], "regency_id": r[3], "district_id": r[4]} for r in v_rows}

        missing_v = [k for k in desired_by_kdep.keys() if k not in v_by_kdep]
        if missing_v:
            raise RuntimeError(f"Masih ada kdepum_code belum ada di villages: {missing_v[:10]}")

        # Upsert destinations (per village_id + destination_name)
        upsert_tuples = []
        for d in desired:
            vid = v_by_kdep[d.kdepum_code]["id"]
            upsert_tuples.append((vid, d.destination_name, d.latitude, d.longitude, d.sea_level_height))

        log.info("Destinations upsert: %s", len(upsert_tuples))
        if not dry_run:
            cur.executemany(
                """
                INSERT INTO public.destinations (village_id, destination_name, latitude, longitude, sea_level_height)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (village_id, destination_name)
                DO UPDATE SET
                  latitude = EXCLUDED.latitude,
                  longitude = EXCLUDED.longitude,
                  sea_level_height = EXCLUDED.sea_level_height,
                  updated_at = NOW()
                """,
                upsert_tuples,
            )

        # Delete extra destinations for involved villages
        involved_vids = [v_by_kdep[k]["id"] for k in desired_by_kdep.keys()]
        desired_keys: set[tuple[str, str]] = set()
        for d in desired:
            desired_keys.add((str(v_by_kdep[d.kdepum_code]["id"]), d.destination_name))

        cur.execute(
            """
            SELECT d.id, d.village_id::text, d.destination_name
            FROM public.destinations d
            WHERE d.village_id = ANY(%s::uuid[])
            """,
            (involved_vids,),
        )
        existing = cur.fetchall()
        extra_ids = [r[0] for r in existing if (r[1], r[2]) not in desired_keys]
        if extra_ids and not dry_run:
            log.info("Destinations delete ekstra: %s", len(extra_ids))
            cur.execute("DELETE FROM public.destinations WHERE id = ANY(%s::uuid[])", (extra_ids,))

        # Verify exact match
        cur.execute(
            """
            SELECT
              v.kdepum_code,
              v.village_name,
              r.name as regency,
              di.name as district,
              d.destination_name,
              d.latitude,
              d.longitude,
              d.sea_level_height
            FROM public.destinations d
            JOIN public.villages v ON v.id = d.village_id
            LEFT JOIN public.regencies r ON r.id = v.regency_id
            LEFT JOIN public.districts di ON di.id = v.district_id
            WHERE v.kdepum_code = ANY(%s)
            ORDER BY v.kdepum_code, d.destination_name
            """,
            (list(desired_by_kdep.keys()),),
        )
        db_rows = cur.fetchall()

        desired_rows = sorted(
            [
                (
                    d.kdepum_code,
                    d.village_name,
                    d.regency,
                    d.district,
                    d.destination_name,
                    float(d.latitude),
                    float(d.longitude),
                    float(d.sea_level_height),
                )
                for d in desired
            ],
            key=lambda x: (x[0], x[4]),
        )

        db_norm = sorted(
            [
                (
                    str(r[0]),
                    str(r[1]),
                    str(r[2]) if r[2] is not None else "",
                    str(r[3]) if r[3] is not None else "",
                    str(r[4]),
                    float(r[5]) if r[5] is not None else None,
                    float(r[6]) if r[6] is not None else None,
                    float(r[7]) if r[7] is not None else None,
                )
                for r in db_rows
            ],
            key=lambda x: (x[0], x[4]),
        )

        if len(db_norm) != len(desired_rows):
            raise RuntimeError(f"Verifikasi gagal: jumlah DB={len(db_norm)} vs lokal={len(desired_rows)}")

        diffs = []
        for a, b in zip(db_norm, desired_rows, strict=True):
            if a != b:
                diffs.append({"db": a, "local": b})
                if len(diffs) >= 10:
                    break
        if diffs:
            raise RuntimeError(f"Verifikasi gagal: ada perbedaan. Contoh: {diffs[:3]}")

        if dry_run:
            conn.rollback()
            log.info("Dry-run: tidak ada perubahan yang disimpan.")
        else:
            conn.commit()
            log.info("Sinkronisasi sukses: database identik dengan data lokal (%s baris).", len(desired_rows))
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync destinasi lokal ke Supabase Postgres")
    p.add_argument("--dry-run", action="store_true", help="Simulasikan (rollback), tetap lakukan verifikasi")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = parse_args(argv or [])

    from config import load_settings

    settings = load_settings()
    sync(settings=settings, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

