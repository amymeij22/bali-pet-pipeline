# Bali PET biometeo_worker (Backend Pipeline)

Pipeline data otomatis berbasis Python untuk mengunduh prakiraan cuaca wilayah Bali dari BMKG, memproses parameter meteorologi untuk menghitung kenyamanan termal manusia menggunakan indeks **Physiological Equivalent Temperature (PET)**, serta menyimpannya ke database PostgreSQL (Supabase) dan arsip Supabase Storage (S3).

Proyek ini dikembangkan sebagai bagian dari penelitian Tugas Akhir (Skripsi) di **Sekolah Tinggi Meteorologi Klimatologi dan Geofisika (STMKG)**.

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://python.org)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Windows_Runner-blue?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![GCP Cloud Scheduler](https://img.shields.io/badge/GCP-Cloud_Scheduler-blue?logo=googlecloud&logoColor=white)](https://cloud.google.com/scheduler)
[![Pytest](https://img.shields.io/badge/Pytest-102%20Passed-green?logo=pytest&logoColor=white)](https://pytest.org)
[![Coverage](https://img.shields.io/badge/Coverage-100%25-green?logo=pytest&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-Proprietary-red)](#)

---

## Daftar Isi
- [Diagram Alur Kerja](#diagram-alur-kerja)
- [Tentang Proyek](#tentang-proyek)
- [Arsitektur & Struktur Direktori](#arsitektur--struktur-direktori)
- [Data untuk Reproduksi Penelitian](#data-untuk-reproduksi-penelitian)
- [Fitur Utama](#fitur-utama)
- [Spesifikasi Teknologi (Tech Stack)](#spesifikasi-teknologi-tech-stack)
- [Panduan Instalasi & Penggunaan](#panduan-instalasi--penggunaan)
- [Pengujian & Penjaminan Kualitas (Testing)](#pengujian--penjaminan-kualitas-testing)
  - [1. Pengujian Unit (Pytest)](#1-pengujian-unit-pytest)
  - [2. Pengujian Asap (Smoke Test)](#2-pengujian-asap-smoke-test)
- [Orkestrasi GCP Cloud Scheduler](#orkestrasi-gcp-cloud-scheduler)
- [Sinkronisasi Data Destinasi](#sinkronisasi-data-destinasi)
- [Kontribusi & Kontak](#kontribusi--kontak)

---

## Diagram Alur Kerja

Pemrosesan data berjalan terjadwal dari pengunduhan hingga pembaruan dasbor WebGIS secara otomatis:

```mermaid
graph TD
    A[GCP Cloud Scheduler] -- "POST Request (Trigger)" --> B[GitHub Actions Runner]
    B -- "Eksekusi main.py" --> C{Probe Check?}
    C -- "Data Sudah Ada" --> D[Melanjutkan dengan Mode Upsert]
    C -- "Ada Data Baru" --> E[Request Data Prakiraan BMKG]
    D --> E
    E --> F[Preprocessing Data Cuaca]
    F --> G["Hitung mPET & Tmrt (biometeo)"]
    G --> H[Klasifikasi Kenyamanan PET]
    H --> I["Simpan Arsip CSV ke Supabase Storage (S3)"]
    H --> J["Unggah Hasil ke PostgreSQL (Supabase)"]
    I --> K["Picu Notifikasi via WebGIS Push Service"]
    J --> K
    K --> L[Selesai]
```

---

## Tentang Proyek

Sistem ini dikonfigurasi untuk berjalan di lingkungan **GitHub Actions dengan runner Windows (`windows-latest`)** karena pustaka komputasi biometeorologi (`biometeo`) membutuhkan dependensi biner Fortran/C khusus platform Windows. 

Pipeline ini memproses prakiraan cuaca 3 harian dari BMKG untuk **49 destinasi wisata utama** di Provinsi Bali, menghitung suhu radiasi rerata (*Mean Radiant Temperature* / Tmrt), melakukan reduksi tinggi kecepatan angin dari 10m ke 1.1m, mengklasifikasikan tingkat kenyamanan termal tubuh manusia, dan mengirimkan sinyal pembaruan data secara real-time ke aplikasi client WebGIS.

---

## Arsitektur & Struktur Direktori

Repositori ini ditata secara modular menggunakan struktur paket Python standar (`src/`):

```text
action/
├── .github/
│   └── workflows/
│       ├── ci.yml                  # CI otomatis saat push/PR ke branch main
│       └── run-biometeo-worker.yml  # Definisi workflow GHA produksi & manual
├── pet_analysis/                   # Arsip data riil untuk reproduksi penelitian (7 Juni – 6 Juli 2026)
├── src/
│   └── biometeo_worker/            # Paket program utama
│       ├── __init__.py
│       ├── main.py                 # Entrypoint orkestrator pipeline & probe check
│       ├── config.py               # Manajer konfigurasi & env var
│       ├── logger.py               # Modul logging terpusat (UTC)
│       ├── biometeo_engine.py      # Integrasi Tmrt_calc & PET biometeo
│       ├── bmkg_client.py          # Client API prakiraan cuaca BMKG
│       ├── classification.py       # Klasifikasi kenyamanan (Temperate & Sub-Tropic)
│       ├── database.py             # Operasi database PostgreSQL & check batches
│       ├── destinations.py         # Master data koordinat lokal 49 destinasi
│       ├── destinations_source_db.py # Pemuatan konfigurasi destinasi dari database
│       ├── preprocessing.py        # Normalisasi satuan & reduksi kecepatan angin
│       └── storage.py              # Operasi upload arsip ke Supabase Storage (S3)
├── scripts/
│   ├── smoke_test.py               # Pengujian cepat fungsionalitas biometeo
│   ├── run_local.ps1               # Script PowerShell untuk eksekusi lokal
│   └── sync_destinations_to_db.py  # Sinkronisasi master destinasi lokal ke DB
├── reports/                        # Penyimpanan laporan CSV hasil eksekusi lokal
├── tests/                          # Berkas pengujian unit (pytest)
├── pyproject.toml                  # Konfigurasi proyek, pytest, & coverage
└── requirements.txt                # Dependensi library Python
```

---

## Data untuk Reproduksi Penelitian

Untuk keperluan transparansi, verifikasi ilmiah, dan reproduksi komputasi penelitian Tugas Akhir, repositori ini menyertakan arsip data hasil kalkulasi dan klasifikasi kenyamanan termal PET pada folder [`pet_analysis/`](pet_analysis/).

Data yang tersedia mencakup rentang waktu satu bulan operasional:
- **Rentang Waktu Batch Produksi**: **7 Juni 2026 s.d. 6 Juli 2026**
  - **Batch Paling Awal**: `pet_analysis_2026-06-07_00-00-00` (7 Juni 2026, 00:00:00 UTC)
  - **Batch Paling Akhir**: `pet_analysis_2026-07-06_12-00-00` (6 Juli 2026, 12:00:00 UTC / jangkauan prakiraan cuaca hingga 8 Juli 2026, 23:00:00 UTC)
- **Total Batch Tersimpan**: 57 batch komputasi
- **Struktur Berkas pada Setiap Folder Batch**:
  - `raw_data.csv`: Data mentah parameter cuaca hasil scraping API BMKG untuk seluruh destinasi wisata.
  - `processed_data.csv`: Data cuaca hasil pra-pemrosesan, normalisasi parameter, dan penyesuaian kecepatan angin ke level 1.1 m.
  - `final_forecast_data.csv`: Hasil komputasi parameter biometeorologi (`Tmrt`, `mPET`, dan `PET`).
  - `pet_classification.csv` / `run_summary.json`: Hasil klasifikasi kategori kenyamanan termal dan ringkasan eksekusi batch.

Data ini dapat digunakan untuk mereplikasi kalkulasi, menganalisis variabilitas termal di destinasi wisata Bali, maupun memvalidasi keluaran sistem tanpa perlu melakukan query ulang ke API BMKG historis.

---

## Fitur Utama

- **Pengecekan Batch Dini (Probe Check)**: Program mengirimkan request API BMKG singkat ke 3 desa sampel secara acak untuk membandingkan timestamp produksi (`produced_at`). Jika data tersebut sudah terdaftar di database, sistem akan mencatatnya dan tetap melanjutkan pipeline dalam mode *upsert* untuk menjamin redundansi dan pembaruan data secara aman.
- **Dukungan Rerun Dinamis (Run 2/3)**: Menyediakan kolom `updated_at` pada tabel `forecast_batches` yang diperbarui secara dinamis jika batch dengan `produced_at` yang sama diimpor kembali. Memungkinkan client WebGIS memicu *auto-refresh* data di latar belakang.
- **Manajemen Status `is_latest`**: Menjamin status `is_latest = TRUE` hanya disematkan pada data batch yang secara kronologis lebih baru dibandingkan batch aktif di database untuk menghindari notifikasi spam.
- **Komparasi Datetime Aman Zona Waktu**: Secara cerdas menyelaraskan objek datetime *timezone-aware* (dari API BMKG) dengan *timezone-naive* (PostgreSQL) sebelum melakukan perbandingan kronologis.
- **Transformasi Kecepatan Angin (Roughness)**: Menerapkan reduksi tinggi hembusan angin dari 10m standar BMKG ke tinggi sensorik kenyamanan manusia (1.1m) menggunakan koefisien kekasaran tetap ($\alpha = 0.2$) atau pustaka komputasi `biometeo`.
- **Arsip Multi-Penyimpanan**: Menyimpan data tabular per jam ke database PostgreSQL (Supabase) untuk konsumsi REST API, sekaligus mengompres hasil run ke berkas `.csv.gz` dan mengunggahnya ke Supabase Storage (S3) untuk kepentingan riset masa depan.

---

## Spesifikasi Teknologi (Tech Stack)

*   **Pustaka Inti Biometeorologi**: `biometeo v0.4.1` (Kompilasi Fortran/C untuk Windows)
*   **Manipulasi & Analisis Data**: `pandas v2.2` & `numpy v2.0`
*   **Akses Database PostgreSQL**: `psycopg2-binary v2.9`
*   **Konektor S3 Cloud Storage**: `boto3 v1.34` & `botocore v1.34`
*   **Kerangka Pengujian Unit**: `pytest v8.3` & `pytest-cov v5.0` & `pytest-html v4.1`

---

## Panduan Instalasi & Penggunaan

### 1. Prasyarat
*   Perangkat bersistem operasi **Windows** (karena pustaka biner `biometeo` dikompilasi untuk runtime Windows).
*   **Python 3.10** ke atas.

### 2. Instalasi Proyek
Masuk ke folder `action` lalu buat virtual environment dan pasang dependensi:
```powershell
cd action
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Konfigurasi Environment
Salin berkas `.env.example` menjadi `.env` di folder root `action/` dan lengkapi nilainya:
```env
DATABASE_URL=postgresql://postgres:password@db.supabase.co:5432/postgres
S3_ENDPOINT_URL=https://proyek-anda.supabase.co/storage/v1/s3
S3_ACCESS_KEY_ID=access_key_supabase_anda
S3_SECRET_ACCESS_KEY=secret_access_key_supabase_anda
S3_BUCKET_NAME=pet_analysis
APP_ENV=dev
KEEP_LOCAL_ARTIFACTS=true
OUTPUT_PARENT_DIR=reports
```

### 4. Eksekusi Lokal
Jalankan skrip pembantu PowerShell untuk mulai memproses data prakiraan cuaca secara instan:
```powershell
.\scripts\run_local.ps1
```
*Catatan: Skrip ini secara otomatis memformat `PYTHONPATH` dan menjalankan slot waktu `manual`.*

Untuk kustomisasi manual, Anda bisa menggunakan perintah interpreter Python secara langsung dengan parameter CLI berikut:
```powershell
# Jalankan slot waktu pagi (morning) dengan membatasi hanya 5 desa pertama
.venv\Scripts\python.exe -m biometeo_worker.main --slot morning --max-villages 5

# Jalankan pengujian kering (dry-run) tanpa menulis data ke database Supabase maupun S3
.venv\Scripts\python.exe -m biometeo_worker.main --slot manual --dry-run
```

Opsi parameter CLI tambahan pada `main.py`:
*   `--slot [morning|evening|manual]`: Menentukan slot waktu eksekusi run.
*   `--trigger-source [02:15|14:15|...|manual]`: Menentukan sumber pemicu scheduler untuk mengontrol aktivasi status `is_latest` (default: `manual`).
*   `--dry-run`: Menghitung data dan menulis file lokal tanpa mengunggah ke DB atau S3.
*   `--skip-db`: Melewati proses unggah data ke database PostgreSQL.
*   `--skip-storage`: Melewati proses unggah file arsip CSV ke S3 Storage.
*   `--max-villages [N]`: Membatasi pengolahan data hanya untuk N desa pertama (sangat berguna untuk debugging cepat).

---

## Pengujian & Penjaminan Kualitas (Testing)

Aplikasi pipeline backend dilengkapi dengan dua tingkat verifikasi otomatis:

### 1. Pengujian Unit (Pytest)
Menguji logika modul independen seperti kalkulasi normalisasi cuaca, skema database, pemecah string tanggal, penentu kategori kenyamanan, validasi respons API BMKG, dan status aktivasi batch terbaru.
*   **Cakupan**: **102 skenario pengujian** dengan **100% Code Coverage (927/927 statements)** lengkap untuk seluruh berkas di bawah `biometeo_worker`.
*   **Perintah menjalankan tes**:
    ```powershell
    # Jalankan pengujian unit (otomatis membuat laporan kelulusan & cakupan visual HTML)
    .venv\Scripts\python.exe -m pytest
    ```
*   **Laporan Hasil Uji (Visual HTML)**:
    Menjalankan tes akan secara otomatis memproduksi dua berkas laporan di bawah folder `reports/`:
    1.  **`reports/pytest-report.html`**: Laporan status hasil eksekusi pengujian skenario unit (Lulus).
    2.  **`reports/coverage-report/index.html`**: Laporan interaktif cakupan kode (*code coverage*) per berkas yang menampilkan baris teruji dan yang dilewati.

### 2. Pengujian Asap (Smoke Test)
Memverifikasi fungsionalitas dasar komputasi biner `biometeo` dan integritas modul worker dalam hitungan milidetik.
*   **Perintah menjalankan tes**:
    ```powershell
    .venv\Scripts\python.exe scripts/smoke_test.py
    ```
*   Smoke test memverifikasi:
    *   Pustaka biner `biometeo` berhasil di-import tanpa error runtime C.
    *   Fungsi komputasi inti (`Tmrt_calc` dan `mPET`) menghasilkan output matematis yang valid.
    *   Struktur internal program `biometeo_worker` terstruktur dengan benar.

### 3. Pemeliharaan Kode (Code Maintenance)
Seluruh komentar dan dokumentasi di dalam kode program disederhanakan agar ringkas, bersih, dan bebas dari komentar berlebihan yang redundan (AI-generated). Hal ini dilakukan untuk menjaga keterbacaan kode dengan tetap mempertahankan fungsionalitas logika 100%.

---

## Orkestrasi GCP Cloud Scheduler

Untuk menghemat kuota eksekusi dan meningkatkan keandalan kontrol penjadwalan, proyek ini **tidak menggunakan cron scheduler bawaan GitHub Actions**.

Sebagai gantinya, jadwal eksekusi produksi pagi & sore diorkestrasi secara eksternal menggunakan **GCP Cloud Scheduler**:
*   Penjadwal GCP mengirimkan request HTTP POST ke REST API GitHub (`/repos/{owner}/{repo}/actions/workflows/run-biometeo-worker.yml/dispatches`) secara terjadwal (pukul 02:15 UTC & 14:15 UTC).
*   Request diautentikasi menggunakan Token PAT (Personal Access Token) dengan menyematkan input parameter `slot` yang sesuai (`morning` atau `evening`).

---

## Sinkronisasi Data Destinasi

Jika terdapat pembaruan data koordinat, nama destinasi, atau tinggi elevasi laut pada konfigurasi lokal di [destinations.py](src/biometeo_worker/destinations.py), data tersebut harus disinkronkan ke database PostgreSQL Supabase menggunakan skrip berikut:
```powershell
.venv\Scripts\python.exe -m scripts.sync_destinations_to_db
```
Tambahkan bendera `--dry-run` untuk memverifikasi perubahan dan melakukan simulasi (rollback otomatis) sebelum perubahan permanen diterapkan di database.

---

## Kontribusi & Kontak

Proyek ini bersifat tertutup (private) untuk kepentingan Tugas Akhir. Hubungi penulis apabila memiliki pertanyaan terkait sistem ini:

*   **Nama**: Ahmad Meijlan Yasir
*   **Email**: yasirahmad220504@gmail.com
*   **Instansi**: Sekolah Tinggi Meteorologi Klimatologi dan Geofisika (STMKG), Tangerang.
