-- Migrasi: ubah weather_forecasts dari per-desa menjadi per-destinasi.
-- Target skema:
--   weather_forecasts.destination_id (FK -> public.destinations.id)
--   UNIQUE (destination_id, batch_id, forecast_time)
--
-- Catatan backfill:
--   Data lama berbasis village_id tidak bisa dipetakan 1:1 ke destinasi tertentu.
--   Maka backfill dilakukan dengan menduplikasi setiap baris forecast desa ke SEMUA destinasi dalam desa tsb.
--
-- Aman dijalankan berulang (idempotent) selama proses migrasi berhasil sekali.

BEGIN;

-- Lock untuk mencegah penulisan paralel saat swap tabel.
LOCK TABLE public.weather_forecasts IN ACCESS EXCLUSIVE MODE;

DO $$
DECLARE
  has_destination_id boolean;
  has_village_id boolean;
  has_table boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='weather_forecasts'
  ) INTO has_table;

  IF NOT has_table THEN
    RAISE NOTICE 'Tabel public.weather_forecasts tidak ada; skip migrasi.';
    RETURN;
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='weather_forecasts' AND column_name='destination_id'
  ) INTO has_destination_id;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='weather_forecasts' AND column_name='village_id'
  ) INTO has_village_id;

  -- Sudah migrasi jika destination_id ada dan village_id sudah tidak ada.
  IF has_destination_id AND (NOT has_village_id) THEN
    RAISE NOTICE 'weather_forecasts sudah berbasis destination_id; skip migrasi.';
    RETURN;
  END IF;
END $$;

-- Buat tabel baru dengan skema per-destinasi.
DROP TABLE IF EXISTS public.weather_forecasts__new;
CREATE TABLE public.weather_forecasts__new (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  destination_id UUID NOT NULL REFERENCES public.destinations(id) ON DELETE CASCADE,
  batch_id UUID NOT NULL REFERENCES public.forecast_batches(id) ON DELETE CASCADE,
  forecast_time TIMESTAMPTZ NOT NULL,

  temperature NUMERIC(4,1) NOT NULL,
  humidity NUMERIC(4,1) NOT NULL,
  wind_speed NUMERIC(5,2) NOT NULL,
  wind_direction VARCHAR(10) NOT NULL,
  weather_condition VARCHAR(100) NOT NULL,
  visibility VARCHAR(50) NOT NULL,

  pet_value NUMERIC(5,2) NOT NULL,

  cloud_cover NUMERIC(5,2),
  tmrt NUMERIC(7,2),
  vapor_pressure NUMERIC(7,3),
  wind_speed_1_1m NUMERIC(7,3),

  temperate_thermal_category UUID REFERENCES public.thermal_categories(id) ON DELETE SET NULL,
  sub_tropic_thermal_category UUID REFERENCES public.thermal_categories(id) ON DELETE SET NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT humidity_range CHECK (humidity >= 0 AND humidity <= 100),
  CONSTRAINT uniq_destination_batch_time UNIQUE (destination_id, batch_id, forecast_time)
);

-- Backfill dari tabel lama jika masih punya village_id.
DO $$
DECLARE
  has_village_id boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='weather_forecasts' AND column_name='village_id'
  ) INTO has_village_id;

  IF has_village_id THEN
    INSERT INTO public.weather_forecasts__new (
      destination_id,
      batch_id,
      forecast_time,
      temperature,
      humidity,
      wind_speed,
      wind_direction,
      weather_condition,
      visibility,
      pet_value,
      cloud_cover,
      tmrt,
      vapor_pressure,
      wind_speed_1_1m,
      temperate_thermal_category,
      sub_tropic_thermal_category,
      created_at
    )
    SELECT
      d.id AS destination_id,
      wf.batch_id,
      wf.forecast_time,
      wf.temperature,
      wf.humidity,
      wf.wind_speed,
      wf.wind_direction,
      wf.weather_condition,
      wf.visibility,
      wf.pet_value,
      wf.cloud_cover,
      wf.tmrt,
      wf.vapor_pressure,
      wf.wind_speed_1_1m,
      wf.temperate_thermal_category,
      wf.sub_tropic_thermal_category,
      COALESCE(wf.created_at, NOW()) AS created_at
    FROM public.weather_forecasts wf
    JOIN public.destinations d ON d.village_id = wf.village_id;
  END IF;
END $$;

-- Indexes selaras skema baru.
CREATE INDEX IF NOT EXISTS idx_forecasts_batch_time
ON public.weather_forecasts__new (batch_id, forecast_time);

CREATE INDEX IF NOT EXISTS idx_forecasts_destination_batch
ON public.weather_forecasts__new (destination_id, batch_id);

-- Swap: simpan backup lama (drop jika sudah ada), lalu rename.
DROP TABLE IF EXISTS public.weather_forecasts__old;
ALTER TABLE public.weather_forecasts RENAME TO weather_forecasts__old;
ALTER TABLE public.weather_forecasts__new RENAME TO weather_forecasts;

-- Cleanup: buang tabel lama agar tidak konflik skema.
DROP TABLE public.weather_forecasts__old;

COMMIT;

