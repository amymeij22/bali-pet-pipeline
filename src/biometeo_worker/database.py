"""Insert / upsert ke Supabase Postgres (psycopg2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg2
from psycopg2.extras import execute_values

from biometeo_worker.config import Settings
from biometeo_worker.logger import get_logger

log = get_logger(__name__)


def connect(settings: Settings):
    if settings.database_url:
        log.info("DB connect via DATABASE_URL")
        return psycopg2.connect(settings.database_url)

    if all([settings.db_user, settings.db_password, settings.db_host, settings.db_port, settings.db_name]):
        log.info("DB connect via DB_* fallback")
        return psycopg2.connect(
            user=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
        )

    raise ValueError("DATABASE_URL atau DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME wajib diisi untuk insert DB")


def _get_optional_forecast_columns(cur) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'weather_forecasts'
        """
    )
    return {r[0] for r in cur.fetchall()}


@dataclass
class ForecastRowDB:
    kdepum_code: str
    destination_name: str
    forecast_time: str
    temperature: float
    humidity: float
    wind_speed_kmh: float
    wind_direction: str
    weather_condition: str
    visibility: str
    pet_value: float
    temperate_category_key: str | None
    sub_tropic_category_key: str | None
    cloud_cover: float | None
    tmrt: float | None
    vapor_pressure: float | None
    wind_speed_1_1m: float | None


def import_forecast_batch(
    produced_at: str,
    forecast_start: str,
    forecast_end: str,
    rows: list[ForecastRowDB],
    settings: Settings,
    set_latest: bool = True,
) -> int:
    """
    Transaksi:
    1) insert batch (is_latest=FALSE secara default, tidak di-reset jika batch sudah ada)
    2) select data forecast yang sudah ada di database untuk batch ini guna meminimalkan I/O
    3) upsert weather_forecasts untuk baris yang belum ada atau nilainya berubah
    4) jika set_latest=True, set batch is_latest=TRUE (jika belum) dan nonaktifkan batch lain (jika masih TRUE)
    Mengembalikan jumlah baris forecast yang benar-benar di-upsert ke DB.
    """
    if not rows:
        log.warning("Tidak ada baris forecast untuk di-insert; batch tidak dibuat sebagai latest")
        return 0

    conn = connect(settings)
    conn.autocommit = False
    cur = conn.cursor()

    optional_cols: set[str] = set()
    try:
        optional_cols = _get_optional_forecast_columns(cur)
    except Exception as e:  # noqa: BLE001
        log.warning("Gagal introspect kolom weather_forecasts (lanjut minimal): %s", e)

    try:
        # Cek apakah batch sudah terdaftar sebelumnya untuk mendeteksi batch baru (resilience)
        cur.execute("SELECT id, is_latest FROM public.forecast_batches WHERE produced_at = %s", (produced_at,))
        batch_row = cur.fetchone()
        is_new_batch = batch_row is None

        cur.execute(
            """
            INSERT INTO public.forecast_batches (produced_at, is_latest, forecast_start, forecast_end)
            VALUES (%s, FALSE, %s, %s)
            ON CONFLICT (produced_at) DO UPDATE SET forecast_start = EXCLUDED.forecast_start,
                                                   forecast_end = EXCLUDED.forecast_end
            RETURNING id
            """,
            (produced_at, forecast_start, forecast_end),
        )
        batch_id = cur.fetchone()[0]
        log.info(
            "Batch dibuat/diperbarui id=%s produced_at=%s (is_new=%s, is_latest tidak ditimpa default)",
            batch_id,
            produced_at,
            is_new_batch,
        )

        # Ambil data forecast yang sudah ada di database untuk batch_id ini
        cur.execute(
            """
            SELECT destination_id, forecast_time::text, temperature, humidity, wind_speed, pet_value
            FROM public.weather_forecasts
            WHERE batch_id = %s
            """,
            (batch_id,),
        )
        existing_map = {}
        for r in cur.fetchall():
            try:
                t_str = r[1].split('+')[0].replace(' ', 'T')
                existing_map[(r[0], t_str)] = (r[2], r[3], r[4], r[5])
            except Exception:
                existing_map[(r[0], str(r[1]))] = (r[2], r[3], r[4], r[5])

        cur.execute("SELECT kdepum_code, id FROM public.villages")
        v_map = {r[0]: r[1] for r in cur.fetchall()}

        # (kdepum_code, destination_name) -> destination_id
        cur.execute(
            """
            SELECT v.kdepum_code, d.destination_name, d.id
            FROM public.destinations d
            JOIN public.villages v ON v.id = d.village_id
            """
        )
        d_map = {(r[0], r[1]): r[2] for r in cur.fetchall()}

        cur.execute("SELECT category_key, id FROM public.thermal_categories")
        t_map = {r[0]: r[1] for r in cur.fetchall()}

        tuples: list[tuple[Any, ...]] = []
        missing_v = set()
        missing_d = set()
        missing_c = set()
        skipped_count = 0

        for r in rows:
            vid = v_map.get(r.kdepum_code)
            if not vid:
                missing_v.add(r.kdepum_code)
                continue

            did = d_map.get((r.kdepum_code, r.destination_name))
            if not did:
                missing_d.add((r.kdepum_code, r.destination_name))
                continue
            tid = t_map.get(r.temperate_category_key) if r.temperate_category_key else None
            sid = t_map.get(r.sub_tropic_category_key) if r.sub_tropic_category_key else None
            if r.temperate_category_key and tid is None:
                missing_c.add(r.temperate_category_key)
            if r.sub_tropic_category_key and sid is None:
                missing_c.add(r.sub_tropic_category_key)

            # Optimasi penyaringan: lewati data yang sudah ada dan nilainya persis sama
            ftime = r.forecast_time
            ftime_clean = ftime.split('+')[0].replace(' ', 'T')
            existing = existing_map.get((did, ftime_clean))
            if existing:
                try:
                    is_same = (
                        abs(float(r.temperature) - float(existing[0])) < 0.01 and
                        abs(float(r.humidity) - float(existing[1])) < 0.01 and
                        abs(float(r.wind_speed_kmh) - float(existing[2])) < 0.01 and
                        abs(float(r.pet_value) - float(existing[3])) < 0.01
                    )
                    if is_same:
                        skipped_count += 1
                        continue
                except (ValueError, TypeError):
                    pass

            base = (
                did,
                batch_id,
                r.forecast_time,
                r.temperature,
                r.humidity,
                r.wind_speed_kmh,
                r.wind_direction,
                r.weather_condition,
                r.visibility,
                r.pet_value,
                tid,
                sid,
            )
            extra: list[Any] = []
            if "cloud_cover" in optional_cols:
                extra.append(r.cloud_cover)
            if "tmrt" in optional_cols:
                extra.append(r.tmrt)
            if "vapor_pressure" in optional_cols:
                extra.append(r.vapor_pressure)
            if "wind_speed_1_1m" in optional_cols:
                extra.append(r.wind_speed_1_1m)

            tuples.append(base + tuple(extra))

        if missing_v:
            log.error("kdepum_code tidak ada di tabel villages (contoh): %s", list(missing_v)[:5])
        if missing_d:
            log.error(
                "destinasi tidak ada di tabel destinations untuk kdepum_code tsb (contoh): %s", list(missing_d)[:5]
            )
        if missing_c:
            log.error("category_key tidak ada di thermal_categories (contoh): %s", list(missing_c)[:5])

        if not tuples and skipped_count == 0:
            conn.rollback()
            log.error("Tidak ada tuple valid untuk insert; rollback")
            return 0

        # dedupe key (destination, batch, time)
        dedup: dict[tuple[Any, Any, Any], tuple[Any, ...]] = {}
        for t in tuples:
            dedup[(t[0], t[1], t[2])] = t
        tuples = list(dedup.values())

        base_cols = [
            "destination_id",
            "batch_id",
            "forecast_time",
            "temperature",
            "humidity",
            "wind_speed",
            "wind_direction",
            "weather_condition",
            "visibility",
            "pet_value",
            "temperate_thermal_category",
            "sub_tropic_thermal_category",
        ]
        dyn_cols: list[str] = []
        if "cloud_cover" in optional_cols:
            dyn_cols.append("cloud_cover")
        if "tmrt" in optional_cols:
            dyn_cols.append("tmrt")
        if "vapor_pressure" in optional_cols:
            dyn_cols.append("vapor_pressure")
        if "wind_speed_1_1m" in optional_cols:
            dyn_cols.append("wind_speed_1_1m")

        col_list = base_cols + dyn_cols

        set_lines = [
            "temperature = EXCLUDED.temperature",
            "humidity = EXCLUDED.humidity",
            "wind_speed = EXCLUDED.wind_speed",
            "wind_direction = EXCLUDED.wind_direction",
            "weather_condition = EXCLUDED.weather_condition",
            "visibility = EXCLUDED.visibility",
            "pet_value = EXCLUDED.pet_value",
            "temperate_thermal_category = EXCLUDED.temperate_thermal_category",
            "sub_tropic_thermal_category = EXCLUDED.sub_tropic_thermal_category",
        ]
        for c in dyn_cols:
            set_lines.append(f"{c} = EXCLUDED.{c}")

        query = f"""
            INSERT INTO public.weather_forecasts ({", ".join(col_list)})
            VALUES %s
            ON CONFLICT (destination_id, batch_id, forecast_time)
            DO UPDATE SET {", ".join(set_lines)}
        """

        n = len(tuples)
        if tuples:
            execute_values(cur, query, tuples)
            log.info("DB execute: %s baris forecast disisipkan/diperbarui (%s baris dilewati karena sama)", n, skipped_count)
        else:
            log.info("DB execute: Semua %s baris forecast dilewati karena sudah ada di database dengan nilai yang sama", len(rows))

        # Tentukan apakah batch ini lebih baru daripada batch yang saat ini ditandai sebagai latest
        cur.execute("SELECT produced_at FROM public.forecast_batches WHERE is_latest = TRUE LIMIT 1")
        latest_row = cur.fetchone()
        
        is_newer_than_current = False
        if latest_row:
            current_latest_produced_at = latest_row[0]
            from datetime import datetime
            try:
                incoming_dt = datetime.fromisoformat(produced_at.replace("Z", "+00:00"))
                if incoming_dt > current_latest_produced_at:
                    is_newer_than_current = True
            except Exception as e:
                log.warning("Gagal membandingkan produced_at: %s", e)
        else:
            # Jika belum ada batch sama sekali di DB, maka batch baru otomatis dianggap lebih baru
            is_newer_than_current = True

        should_activate = set_latest or is_newer_than_current
        if should_activate:
            cur.execute(
                """
                UPDATE public.forecast_batches
                SET is_latest = TRUE
                WHERE id = %s AND is_latest = FALSE
                """,
                (batch_id,),
            )
            cur.execute(
                """
                UPDATE public.forecast_batches
                SET is_latest = FALSE
                WHERE id <> %s AND is_latest = TRUE
                """,
                (batch_id,),
            )
            log.info(
                "Batch id=%s diset is_latest=TRUE dan batch lainnya FALSE (set_latest=%s, is_new=%s)",
                batch_id,
                set_latest,
                is_new_batch,
            )
        else:
            log.info("Batch id=%s (sudah ada) tidak dimodifikasi status is_latest-nya (set_latest=False)", batch_id)

        conn.commit()
        log.info("DB commit selesai: %s baris forecast sukses di-upsert", n)
        return n
    except Exception:
        conn.rollback()
        log.exception("DB error — rollback")
        raise
    finally:
        cur.close()
        conn.close()


def check_already_processed_batches(produced_at_list: list[str], settings: Settings) -> set[str]:
    """
    Memeriksa batch mana saja dari list produced_at yang sudah ada di database.
    Mengembalikan set produced_at yang sudah terdaftar.
    """
    if not produced_at_list:
        return set()

    from datetime import datetime

    conn = connect(settings)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT produced_at::timestamp
            FROM public.forecast_batches
            WHERE produced_at = ANY(%s::timestamptz[])
            """,
            (produced_at_list,),
        )
        db_naive_dts = {r[0] for r in cur.fetchall()}

        input_naive_map = {}
        for s in produced_at_list:
            try:
                s_clean = s.strip()
                dt = datetime.fromisoformat(s_clean)
                input_naive_map[dt] = s_clean
            except ValueError:
                log.warning("Format produced_at tidak valid untuk parsing: %s", s)

        matched_strings = set()
        for dt, orig_s in input_naive_map.items():
            if dt in db_naive_dts:
                matched_strings.add(orig_s)

        return matched_strings
    except Exception as e:
        log.warning("Gagal memeriksa existing batches di DB: %s", e)
        return set()
    finally:
        cur.close()
        conn.close()

