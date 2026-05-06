# Pipeline PET / kenyamanan termal (Cloud Run)

Orkestrator end-to-end yang mengambil prakiraan BMKG, menghitung PET (biometeo==0.4.1), mengklasifikasi kenyamanan, lalu menulis arsip CSV/JSON, meng-upsert ke PostgreSQL (Supabase), dan mengunggah folder run ke Supabase Storage (S3-compatible).

Repo ini hanya memuat **code pipeline + script sinkronisasi**. Struktur skema database mengikuti file:
- `webgis/db/schema.sql`
- `webgis/db/migration.sql`

## Struktur folder `cloudrun/`
- `main.py`: entrypoint pipeline end-to-end (BMKG → biometeo → CSV arsip → DB → Storage)
- `scripts/sync_destinations_to_db.py`: implementasi sinkronisasi (source-of-truth lokal: `destinations.py`)
- `*.py` lain: modul internal pipeline (BMKG client, biometeo wrapper, preprocessing, database, storage, dll.)
- `tests/`: unit/smoke tests untuk modul internal

## Konsep source-of-truth
- **Destinasi & koordinat**: diambil dari DB (`public.destinations` JOIN `public.villages` JOIN master `regencies/districts`).
- Jika DB tidak tersedia (mis. saat `--dry-run`), pipeline fallback ke konfigurasi lokal `destinations.py`.

## Variabel lingkungan
Lihat `.env.example`. Ringkas:
- Database: `DATABASE_URL` atau `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`
- Storage: `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION`
- Runtime:
  - `OUTPUT_PARENT_DIR` (default `pet_analysis`)
  - `APP_ENV` (`dev` atau `prod`)
  - `KEEP_LOCAL_ARTIFACTS`
    - `APP_ENV=dev`: file disimpan lokal seperti biasa.
    - `APP_ENV=prod` dan `KEEP_LOCAL_ARTIFACTS=false`: file ditulis ke temporary dir lalu otomatis dihapus setelah upload ke Storage.

## Menjalankan pipeline

Masuk folder `cloudrun/`, misalnya:

```bash
cd cloudrun
pip install -r requirements.txt
python main.py
```

Opsi CLI:
- `--dry-run`: hitung + tulis arsip ke disk, **tanpa** insert DB dan tanpa upload S3
- `--skip-db`: lewati insert database
- `--skip-storage`: lewati upload storage
- `--max-villages N`: batasi jumlah desa unik (untuk smoke test)

Perilaku output folder:
- Nama folder run selalu `pet_analysis_<timestamp>` di bawah `OUTPUT_PARENT_DIR` **(dev)**.
- **(prod + KEEP_LOCAL_ARTIFACTS=false)**: folder run ditulis di temporary dir dan tidak menetap di filesystem container (diarsipkan di Storage).
Artefak output (standar, selalu sama):
- `raw_data.csv`
- `processed_data.csv`
- `final_forecast_data.csv`
- `run_summary.json`
- File error jika ada: `failed_rows.csv`, `failed_villages.csv`

Exit code:
- `0` sukses
- `4` pipeline gagal (data/hasil)
- `5` gagal upload storage
- `6` insert DB 0 baris

## Sinkronisasi master destinasi (lokal → database)
Jika koordinat/elevasi destinasi diubah di `destinations.py`, sinkronkan ke Supabase:

```bash
python -m scripts.sync_destinations_to_db
```

Simulasi (rollback, tapi verifikasi tetap dijalankan):

```bash
python -m scripts.sync_destinations_to_db --dry-run
```

Script ini memastikan **DB identik 100%** untuk entri destinasi yang terlibat:
- villages (KDEPUM + metadata regency/district via FK)
- destinations (latitude/longitude/sea_level_height)

## Docker & Cloud Run Job
Build dari direktori `cloudrun/`:

```bash
docker build -t pet-pipeline:latest .
```

Jalankan (set env via secret manager / env):

```bash
docker run --rm -e DATABASE_URL=... -e S3_ENDPOINT_URL=... `
  -e S3_ACCESS_KEY_ID=... -e S3_SECRET_ACCESS_KEY=... -e S3_BUCKET_NAME=... `
  pet-pipeline:latest
```

Di GCP: jalankan sebagai **Cloud Run Job** untuk eksekusi terjadwal.

## Pengujian
```bash
pytest
```
