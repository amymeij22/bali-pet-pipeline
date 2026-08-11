"""
Orkestrator pipeline produksi: BMKG -> prapemrosesan -> biometeo -> klasifikasi ->
arsip CSV (selaras cloud_run/main.py) -> PostgreSQL (Supabase) -> Supabase Storage (S3).

Default: jalankan end-to-end (database + storage). Gunakan --dry-run / --skip-db / --skip-storage bila perlu.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from biometeo_worker.bmkg_client import fetch_all_unique_villages, fetch_forecast_for_village
from biometeo_worker.classification import classify_pet
from biometeo_worker.config import Settings, load_settings
from biometeo_worker.database import ForecastRowDB, import_forecast_batch, check_already_processed_batches
from biometeo_worker.destinations import DESTINATIONS, DestinationConfig, build_unique_villages
from biometeo_worker.destinations_source_db import fetch_destination_configs, validate_destination_configs
from biometeo_worker.logger import get_logger, setup_logging
from biometeo_worker.preprocessing import preprocess_bmkg_record
from biometeo_worker.storage import upload_run_folder

log = get_logger(__name__)

BIOMETEO_VERSION = "0.4.1"


def _safe_folder_ts(produced_at: str) -> str:
    return produced_at.replace(":", "-").replace("T", "_").replace("/", "-")


def _static_by_kdepum(destinations: list[DestinationConfig]) -> dict[str, DestinationConfig]:
    out: dict[str, DestinationConfig] = {}
    for d in destinations:
        out.setdefault(d["kdepum_code"], d)
    return out


def _destinations_by_kdepum(destinations: list[DestinationConfig]) -> dict[str, list[DestinationConfig]]:
    out: dict[str, list[DestinationConfig]] = {}
    for d in destinations:
        out.setdefault(d["kdepum_code"], []).append(d)
    return out


def _series_val(row: pd.Series, *keys: str, default: Any = "") -> Any:
    for k in keys:
        if k in row.index:
            v = row[k]
            if pd.isna(v):
                continue
            return v
    return default


def validate_runtime_settings(settings: Settings, *, dry_run: bool, skip_db: bool, skip_storage: bool) -> None:
    if dry_run:
        return
    if not skip_db:
        has_url = bool(settings.database_url)
        has_parts = all(
            [
                settings.db_user,
                settings.db_password,
                settings.db_host,
                settings.db_port,
                settings.db_name,
            ]
        )
        if not has_url and not has_parts:
            raise ValueError(
                "Produksi membutuhkan koneksi database: set DATABASE_URL atau "
                "DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME — atau gunakan --skip-db / --dry-run"
            )
    if not skip_storage:
        if not all(
            [
                settings.s3_endpoint_url,
                settings.s3_access_key_id,
                settings.s3_secret_access_key,
            ]
        ):
            raise ValueError(
                "Produksi membutuhkan S3 Supabase: S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, "
                "S3_SECRET_ACCESS_KEY — atau gunakan --skip-storage / --dry-run"
            )
    # Jika tidak menyimpan artefak lokal, pipeline harus upload ke storage agar artefak tidak hilang.
    if (settings.app_env in {"prod", "production"}) and (not settings.keep_local_artifacts) and skip_storage:
        raise ValueError("APP_ENV=prod dengan KEEP_LOCAL_ARTIFACTS=0 membutuhkan upload storage (jangan gunakan --skip-storage)")


def build_grp_and_exports(
    grp: pd.DataFrame,
    kdep_to_dests: dict[str, list[str]],
    produced_at: str,
    *,
    include_db_rows: bool = True,
) -> tuple[list[ForecastRowDB], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Satu pass: baris DB per desa×waktu + CSV arsip per destinasi (seperti pipeline lama)."""
    db_rows: list[ForecastRowDB] = []
    raw_rows: list[dict[str, Any]] = []
    proc_rows: list[dict[str, Any]] = []
    class_rows: list[dict[str, Any]] = []
    final_rows: list[dict[str, Any]] = []

    for _, row in grp.iterrows():
        kdep = str(row["kdepum_code"])
        # Ekspansi destinasi
        row_dest = _series_val(row, "destination_name", default="")
        if row_dest:
            dests = [str(row_dest)]
        else:
            dests = kdep_to_dests.get(kdep) or [str(row["village_name"])]

        pet_val = float(row["pet_value"])
        tmrt = float(row["tmrt"])
        vp = float(row["vapor_pressure"])
        ct = classify_pet(pet_val, "temperate")
        cs = classify_pet(pet_val, "sub_tropic")

        t_val = _series_val(row, "t", "Ta")
        hu_val = _series_val(row, "hu", "RH")
        ws_val = _series_val(row, "ws", "wind_speed_kmh_bmkg")
        wd_val = _series_val(row, "wd", default="")
        wdesc = _series_val(row, "weather_desc", default="")
        vs = _series_val(row, "vs_text", default="")
        tcc = _series_val(row, "tcc", "cloud_cover_percent")

        for dest in dests:
            if include_db_rows:
                db_rows.append(
                    ForecastRowDB(
                        kdepum_code=kdep,
                        destination_name=dest,
                        forecast_time=str(row["utc_datetime"]),
                        temperature=float(t_val),
                        humidity=float(hu_val),
                        wind_speed_kmh=float(ws_val),
                        wind_direction=str(wd_val),
                        weather_condition=str(wdesc),
                        visibility=str(vs),
                        pet_value=pet_val,
                        temperate_category_key=ct,
                        sub_tropic_category_key=cs,
                        cloud_cover=float(row["cloud_cover_percent"]),
                        tmrt=tmrt,
                        vapor_pressure=vp,
                        wind_speed_1_1m=float(row["wind_speed_1_1m_ms"]),
                    )
                )

            raw_one: dict[str, Any] = {
                "lokasi_wisata": dest,
                "kdepum_code": kdep,
                "village_name": row["village_name"],
                "local_datetime": row["local_datetime"],
                "utc_datetime": row["utc_datetime"],
                "t": t_val,
                "hu": hu_val,
                "ws": ws_val,
                "wd": wd_val,
                "weather_desc": wdesc,
                "vs_text": vs,
                "tcc": tcc,
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "sea_level_height": row["sea_level_height"],
                "N_oktas": row["N_oktas"],
                "wind_speed_1_1m_ms": row["wind_speed_1_1m_ms"],
                "wind_speed_reduction_method": _series_val(row, "wind_speed_reduction_method", default=""),
                "Tmrt": tmrt,
                "vapor_pressure": vp,
                "PET": pet_val,
                "temperate_category_key": ct,
                "sub_tropic_category_key": cs,
                "bmkg_lat": row["bmkg_lat"] if "bmkg_lat" in row.index else None,
                "bmkg_lon": row["bmkg_lon"] if "bmkg_lon" in row.index else None,
            }
            raw_rows.append(raw_one)

            proc_rows.append(
                {
                    "lokasi_wisata": dest,
                    "kdepum_code": kdep,
                    "local_datetime": row["local_datetime"],
                    "t": t_val,
                    "hu": hu_val,
                    "ws": ws_val,
                    "wd": wd_val,
                    "weather_desc": wdesc,
                    "vs_text": vs,
                    "tcc": tcc,
                    "Tmrt": tmrt,
                    "PET": pet_val,
                }
            )

            class_one = dict(raw_one)
            class_one["class_temperate"] = ct
            class_one["class_sub_tropic"] = cs
            class_rows.append(class_one)

            final_rows.append(
                {
                    "produced_at": produced_at,
                    "kdepum_code": kdep,
                    "village_name": row["village_name"],
                    "destination_name": dest,
                    "forecast_time": row["utc_datetime"],
                    "temperature": float(t_val),
                    "humidity": float(hu_val),
                    "wind_speed": float(ws_val),
                    "wind_direction": wd_val,
                    "weather_condition": wdesc,
                    "visibility": vs,
                    "pet_value": pet_val,
                    "temperate_category_key": ct,
                    "sub_tropic_category_key": cs,
                    "cloud_cover": float(row["cloud_cover_percent"]),
                    "tmrt": tmrt,
                    "vapor_pressure": vp,
                    "wind_speed_1_1m_ms": float(row["wind_speed_1_1m_ms"]),
                }
            )

    return (
        db_rows,
        pd.DataFrame(raw_rows),
        pd.DataFrame(proc_rows),
        pd.DataFrame(class_rows),
        pd.DataFrame(final_rows),
    )


def determine_set_latest(slot: str, trigger_source: str) -> bool:
    """
    Menentukan apakah status is_latest harus diperbarui berdasarkan slot dan trigger source.
    Pembaruan is_latest hanya bernilai True pada:
    - Slot 'manual'
    - Slot 'morning' dengan trigger 02:15 (02.15)
    - Slot 'evening' dengan trigger 14:15 (14.15)
    """
    if slot == "manual":
        return True

    ts = trigger_source.strip().replace(".", ":").lower()
    if slot == "morning":
        return ts.startswith("02:15") or ts == "02:15"
    if slot == "evening":
        return ts.startswith("14:15") or ts == "14:15"

    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pipeline PET Bali (biometeo): BMKG -> biometeo -> CSV -> Postgres -> S3"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Hitung dan tulis arsip ke folder output; tidak insert database dan tidak upload storage",
    )
    p.add_argument("--skip-db", action="store_true", help="Lewati insert database")
    p.add_argument("--skip-storage", action="store_true", help="Lewati upload storage")
    p.add_argument(
        "--max-villages",
        type=int,
        default=None,
        help="Opsional: batasi jumlah desa unik (untuk produksi penuh, jangan gunakan flag ini)",
    )
    p.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Folder induk output (override OUTPUT_PARENT_DIR)",
    )
    p.add_argument(
        "--slot",
        type=str,
        choices=["morning", "evening", "manual"],
        default=os.getenv("RUN_SLOT", "manual"),
        help="Pipeline slot (morning, evening, manual)",
    )
    p.add_argument(
        "--trigger-source",
        type=str,
        default="manual",
        help="Sumber pemicu eksekusi pipeline (contoh: 02:15, 03:15, 04:15, 14:15, 15:15, 16:15, atau manual)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = parse_args(argv or sys.argv[1:])
    settings = load_settings()
    log.info("Slot terpilih: %s, Sumber Trigger: %s", args.slot, args.trigger_source)

    try:
        validate_runtime_settings(
            settings,
            dry_run=args.dry_run,
            skip_db=args.skip_db,
            skip_storage=args.skip_storage,
        )
    except ValueError as e:
        log.error("%s", e)
        return 1

    started = datetime.now(timezone.utc)

    # Load konfigurasi destinasi
    destinations: list[DestinationConfig] = []
    if args.dry_run:
        destinations = DESTINATIONS
        log.info("Dry-run: memakai konfigurasi destinasi dari file (destinations.py)")
    else:
        try:
            destinations = fetch_destination_configs(settings)
            validate_destination_configs(destinations)
            log.info("Memuat konfigurasi destinasi dari database: %s baris", len(destinations))
        except Exception as e:  # noqa: BLE001
            log.warning("Gagal memuat destinasi dari DB (%s). Fallback ke file.", e)
            destinations = DESTINATIONS

    destinations_by_kdep = _destinations_by_kdepum(destinations)
    villages = build_unique_villages(destinations)
    if args.max_villages is not None:
        villages = villages[: max(0, args.max_villages)]
    kdep_to_dests = {v["kdepum_code"]: v["destination_names"] for v in villages}

    log.info("Memuat konfigurasi: destinasi=%s desa_unik=%s", len(destinations), len(villages))

    do_db = not args.dry_run and not args.skip_db
    if do_db and villages:
        import random
        import time

        log.info("Memulai pengecekan batch awal (probe) dengan 3 lokasi acak...")
        probe_villages = random.sample(villages, min(3, len(villages)))
        probe_results = []

        for i, pv in enumerate(probe_villages):
            kdep = pv["kdepum_code"]
            vname = pv["village_name"]
            log.info("Probe [%s/%s] kdepum=%s village=%s", i + 1, len(probe_villages), kdep, vname)

            recs, prod, fs, fe, err = fetch_forecast_for_village(
                kdepum_code=kdep,
                village_name=vname,
                destination_names=pv.get("destination_names", []),
                settings=settings,
            )
            if err:
                log.warning("Probe [%s/%s] gagal: %s", i + 1, len(probe_villages), err)
            elif prod:
                log.info("Probe [%s/%s] sukses -> analysis_date: %s", i + 1, len(probe_villages), prod)
                probe_results.append(prod)
            else:
                log.warning("Probe [%s/%s] sukses tetapi tidak memiliki produced_at/analysis_date", i + 1, len(probe_villages))

            if i < len(probe_villages) - 1:
                time.sleep(settings.request_delay_seconds)

        if probe_results:
            unique_prods = list(set(probe_results))
            log.info("Memeriksa status %s analysis_date unik di database...", len(unique_prods))
            existing_batches = check_already_processed_batches(unique_prods, settings)

            if len(existing_batches) == len(unique_prods):
                log.info(
                    "Semua %s/%s data hasil probe sudah terdaftar di database: %s. Melanjutkan pipeline penuh (mode upsert diaktifkan).",
                    len(existing_batches),
                    len(unique_prods),
                    list(existing_batches),
                )
            else:
                new_batches = set(unique_prods) - existing_batches
                log.info(
                    "Ditemukan batch baru yang belum ada di database: %s. Melanjutkan pipeline penuh.",
                    list(new_batches),
                )
        else:
            log.warning("Pengecekan probe tidak mendapatkan analysis_date valid. Melanjutkan pipeline penuh sebagai fallback.")

    fetch = fetch_all_unique_villages(villages, settings)
    if not fetch.raw_records and not fetch.failed_villages:
        log.error("Tidak ada respons BMKG dan tidak ada error desa — pipeline dihentikan")
        return 2
    if not fetch.raw_records:
        log.error("Semua desa gagal di-fetch BMKG — pipeline gagal")
        return 3

    produced_at = fetch.produced_at or datetime.now(timezone.utc).isoformat()
    folder_ts = _safe_folder_ts(produced_at)
    run_name = f"pet_analysis_{folder_ts}"

    # Tentukan direktori penyimpanan
    keep_local = args.dry_run or settings.keep_local_artifacts or (settings.app_env not in {"prod", "production"})
    parent = args.output_dir or settings.output_parent_dir

    def _run_in_dir(run_dir: str) -> int:
        raw_df = pd.DataFrame(fetch.raw_records)

        preprocessed: list[dict[str, Any]] = []
        failed_rows: list[dict[str, Any]] = []
        for _, row in raw_df.iterrows():
            r = row.to_dict()
            kdep = r.get("kdepum_code")
            ds = destinations_by_kdep.get(kdep) if kdep else None
            if not ds:
                failed_rows.append({**r, "error": "kdepum tidak ditemukan di sumber destinasi (DB/fallback file)"})
                continue

            # Ekspansi per destinasi agar koordinat/elevasi dipakai sesuai destinasi.
            for d in ds:
                static = {
                    "kdepum_code": d["kdepum_code"],
                    "village_name": d["village_name"],
                    "latitude": d["latitude"],
                    "longitude": d["longitude"],
                    "sea_level_height": d["sea_level_height"],
                    "destination_name": d["destination_name"],
                }
                pr, err = preprocess_bmkg_record(r, static)
                if err:
                    failed_rows.append({**r, "destination_name": d["destination_name"], "error": err})
                    continue
                preprocessed.append(pr)

        pre_df = pd.DataFrame(preprocessed)

        bio_rows: list[dict[str, Any]] = []
        # Lazy import biometeo_engine
        from biometeo_worker.biometeo_engine import calculate_biometeo_outputs  # noqa: WPS433

        for pr in preprocessed:
            try:
                bio = calculate_biometeo_outputs(pr)
                bio_rows.append({**pr, **bio})
            except Exception as e:  # noqa: BLE001
                failed_rows.append({**pr, "error": f"biometeo:{e}"})

        bio_df = pd.DataFrame(bio_rows)

        if failed_rows:
            pd.DataFrame(failed_rows).to_csv(os.path.join(run_dir, "failed_rows.csv"), index=False)

        if bio_df.empty:
            log.error("Tidak ada hasil biometeo — pipeline gagal")
            finished = datetime.now(timezone.utc)
            summary = {
                "produced_at": produced_at,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "duration_seconds": (finished - started).total_seconds(),
                "total_unique_villages": len(villages),
                "success_villages": len(villages) - len(fetch.failed_villages),
                "failed_villages": len(fetch.failed_villages),
                "total_records_raw": len(raw_df),
                "total_records_valid": len(preprocessed),
                "total_records_inserted": 0,
                "total_records_skipped": len(failed_rows),
                "forecast_start": fetch.forecast_start,
                "forecast_end": fetch.forecast_end,
                "biometeo_version": BIOMETEO_VERSION,
                "status": "failed",
            }
            with open(os.path.join(run_dir, "run_summary.json"), "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            return 4

        # Untuk DB: simpan per destinasi×waktu (bio_df sudah diekspansi per destinasi).
        db_rows, _, _, _, _ = build_grp_and_exports(bio_df, kdep_to_dests, produced_at)
        _, raw_legacy_df, proc_df, class_df, final_df = build_grp_and_exports(
            bio_df, kdep_to_dests, produced_at, include_db_rows=False
        )

        # Simpan arsip CSV
        raw_legacy_df.to_csv(os.path.join(run_dir, "raw_data.csv"), index=False)
        proc_df.to_csv(os.path.join(run_dir, "processed_data.csv"), index=False)
        final_df.to_csv(os.path.join(run_dir, "final_forecast_data.csv"), index=False)
        log.info("Arsip standar: raw_data.csv, processed_data.csv, final_forecast_data.csv")

        times = [str(x) for x in bio_df["utc_datetime"].dropna().tolist()]
        f_start = fetch.forecast_start or (min(times) if times else "")
        f_end = fetch.forecast_end or (max(times) if times else "")

        failed_villages_df = pd.DataFrame(fetch.failed_villages)
        if not failed_villages_df.empty:
            failed_villages_df.to_csv(os.path.join(run_dir, "failed_villages.csv"), index=False)

        finished = datetime.now(timezone.utc)
        duration = (finished - started).total_seconds()

        success_v = len(villages) - len(fetch.failed_villages)
        status = "success"
        if fetch.failed_villages:
            status = "partial_success"
        if success_v == 0:
            status = "failed"

        summary = {
            "produced_at": produced_at,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": duration,
            "total_unique_villages": len(villages),
            "success_villages": success_v,
            "failed_villages": len(fetch.failed_villages),
            "total_records_raw": len(raw_df),
            "total_records_valid": len(preprocessed),
            "total_records_inserted": 0,
            "total_records_skipped": len(failed_rows),
            "forecast_start": f_start,
            "forecast_end": f_end,
            "biometeo_version": BIOMETEO_VERSION,
            "status": status,
        }

        do_db = not args.dry_run and not args.skip_db
        inserted = 0
        if do_db:
            set_latest = determine_set_latest(args.slot, args.trigger_source)
            inserted = import_forecast_batch(
                produced_at=produced_at,
                forecast_start=f_start,
                forecast_end=f_end,
                rows=db_rows,
                settings=settings,
                set_latest=set_latest,
            )
            summary["total_records_inserted"] = inserted
            if inserted == 0:
                summary["status"] = "failed"
                log.error(
                    "Insert database: 0 baris — periksa mapping kdepum_code ke tabel villages "
                    "dan category_key ke thermal_categories"
                )
                with open(os.path.join(run_dir, "run_summary.json"), "w", encoding="utf-8") as f:
                    json.dump(summary, f, indent=2, ensure_ascii=False)
                return 6

        with open(os.path.join(run_dir, "run_summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        log.info("Menulis run_summary.json status=%s", status)

        do_storage = not args.dry_run and not args.skip_storage
        if do_storage:
            up = upload_run_folder(run_dir, settings)
            if up.get("failed"):
                log.error("Upload storage selesai dengan %s kegagalan", len(up["failed"]))
                return 5
        elif args.dry_run:
            log.info("Dry-run: tidak upload storage")
        elif args.skip_storage:
            log.info("Melewati upload storage (--skip-storage)")

        log.info(
            "Ringkasan: desa_ok=%s/%s baris_final_destinasi=%s baris_upsert_desa=%s inserted=%s",
            success_v,
            len(villages),
            len(final_df),
            len(db_rows),
            inserted,
        )
        return 0 if status != "failed" else 4

    if keep_local:
        run_dir = os.path.join(parent, run_name)
        os.makedirs(run_dir, exist_ok=True)
        return _run_in_dir(run_dir)

    with tempfile.TemporaryDirectory(prefix="pet_analysis_") as base:
        run_dir = os.path.join(base, run_name)
        os.makedirs(run_dir, exist_ok=True)
        return _run_in_dir(run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
