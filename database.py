"""Insert / upsert ke Supabase Postgres (psycopg2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg2
from psycopg2.extras import execute_values

from config import Settings
from logger import get_logger

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
) -> int:
    """
    Transaksi:
    1) insert batch is_latest=FALSE
    2) upsert weather_forecasts
    3) jika ada baris yang sukses diproses, set batch is_latest=TRUE dan nonaktifkan batch lain
    Mengembalikan jumlah baris forecast yang di-upsert.
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
        cur.execute(
            """
            INSERT INTO public.forecast_batches (produced_at, is_latest, forecast_start, forecast_end)
            VALUES (%s, FALSE, %s, %s)
            ON CONFLICT (produced_at) DO UPDATE SET forecast_start = EXCLUDED.forecast_start,
                                                   forecast_end = EXCLUDED.forecast_end,
                                                   is_latest = FALSE
            RETURNING id
            """,
            (produced_at, forecast_start, forecast_end),
        )
        batch_id = cur.fetchone()[0]
        log.info("Batch dibuat/updated id=%s produced_at=%s (is_latest sementara FALSE)", batch_id, produced_at)

        cur.execute("SELECT kdepum_code, id FROM public.villages")
        v_map = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("SELECT category_key, id FROM public.thermal_categories")
        t_map = {r[0]: r[1] for r in cur.fetchall()}

        tuples: list[tuple[Any, ...]] = []
        missing_v = set()
        missing_c = set()

        for r in rows:
            vid = v_map.get(r.kdepum_code)
            if not vid:
                missing_v.add(r.kdepum_code)
                continue
            tid = t_map.get(r.temperate_category_key) if r.temperate_category_key else None
            sid = t_map.get(r.sub_tropic_category_key) if r.sub_tropic_category_key else None
            if r.temperate_category_key and tid is None:
                missing_c.add(r.temperate_category_key)
            if r.sub_tropic_category_key and sid is None:
                missing_c.add(r.sub_tropic_category_key)

            base = (
                vid,
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
        if missing_c:
            log.error("category_key tidak ada di thermal_categories (contoh): %s", list(missing_c)[:5])

        if not tuples:
            conn.rollback()
            log.error("Tidak ada tuple valid untuk insert; rollback")
            return 0

        # dedupe key (village, batch, time)
        dedup: dict[tuple[Any, Any, Any], tuple[Any, ...]] = {}
        for t in tuples:
            dedup[(t[0], t[1], t[2])] = t
        tuples = list(dedup.values())

        base_cols = [
            "village_id",
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
            ON CONFLICT (village_id, batch_id, forecast_time)
            DO UPDATE SET {", ".join(set_lines)}
        """

        execute_values(cur, query, tuples)
        n = len(tuples)

        cur.execute(
            """
            UPDATE public.forecast_batches
            SET is_latest = TRUE
            WHERE id = %s
            """,
            (batch_id,),
        )
        cur.execute(
            """
            UPDATE public.forecast_batches
            SET is_latest = FALSE
            WHERE id <> %s
            """,
            (batch_id,),
        )

        conn.commit()
        log.info("DB commit: %s baris forecast upsert, batch %s set is_latest=TRUE", n, batch_id)
        return n
    except Exception:
        conn.rollback()
        log.exception("DB error — rollback")
        raise
    finally:
        cur.close()
        conn.close()
