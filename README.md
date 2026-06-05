# Pipeline PET / Kenyamanan Termal (GitHub Actions Windows Worker)

Repositori ini berisi orkestrator *pipeline* data *end-to-end* yang bertugas mengunduh data prakiraan cuaca dari API BMKG, memproses parameter meteorologi untuk menghitung indeks kenyamanan termal *Physiologically Equivalent Temperature* (PET) menggunakan pustaka `biometeo` (v0.4.1), mengklasifikasikan kategori kenyamanan termal, serta mengarsipkan hasilnya ke database PostgreSQL (Supabase) dan Supabase Storage (S3-compatible).

Sistem ini dikonfigurasi untuk berjalan di lingkungan **GitHub Actions dengan runner Windows (`windows-latest`)** karena pustaka perhitungan biometeorologi (`biometeo`) membutuhkan dependensi biner yang berjalan di platform Windows/Microsoft.

---

## Daftar Isi
- [Arsitektur & Struktur Direktori](#arsitektur--struktur-direktori)
- [Fitur Pengecekan Batch Dini (Probe Check)](#fitur-pengecekan-batch-dini-probe-check)
- [Dependensi Utama](#dependensi-utama)
- [Variabel Lingkungan (Environment Variables)](#variabel-lingkungan-environment-variables)
- [Penggunaan Lokal (Windows)](#penggunaan-lokal-windows)
- [Penggunaan di GitHub Actions](#penggunaan-di-github-actions)
- [Pemicu Jadwal Eksternal (GCP)](#pemicu-jadwal-eksternal-gcp)
- [Sinkronisasi Data Destinasi](#sinkronisasi-data-destinasi)
- [Pengujian & Verifikasi](#pengujian--verifikasi)

---

## Arsitektur & Struktur Direktori

Repositori ini disusun menggunakan struktur paket Python standar (`src/`) agar modular, teruji, dan mudah dipelihara.

```text
action/
├── .github/
│   └── workflows/
│       ├── ci.yml                  # CI otomatis saat push/PR ke branch main
│       └── run-biometeo-worker.yml  # Definisi run-worker untuk produksi & manual
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
│       ├── destinations.py         # Master data koordinat & elevasi 49 destinasi
│       ├── destinations_source_db.py # Pengambilan konfigurasi destinasi dari DB
│       ├── preprocessing.py        # Normalisasi satuan & reduksi kecepatan angin
│       └── storage.py              # Operasi upload arsip ke Supabase Storage (S3)
├── scripts/
│   ├── smoke_test.py               # Pengujian fungsionalitas biometeo & biometeo_worker
│   ├── run_local.ps1               # Script PowerShell untuk eksekusi lokal
│   └── sync_destinations_to_db.py  # Sinkronisasi master destinasi lokal ke DB
├── reports/                        # Lokasi penyimpanan laporan & keluaran CSV runtime
├── tests/                          # Berkas pengujian unit (pytest)
├── .env.example
├── .gitignore
├── pyproject.toml                  # Konfigurasi project & pytest
├── README.md
└── requirements.txt
```

---

## Fitur Pengecekan Batch Dini (Probe Check)

Untuk menghemat kuota menit komputasi GitHub Actions runner dan menghindari duplikasi pemrosesan data, program ini dilengkapi dengan mekanisme **Pengecekan Batch Dini (Probe Check)**:

1. **Pengambilan Sampel (Probe)**: Di awal program, orkestrator memilih **3 desa secara acak** dari daftar destinasi aktif dan melakukan request BMKG singkat untuk mengambil nilai `analysis_date`.
2. **Validasi Database**: Program mengecek ke database Supabase (tabel `forecast_batches`) apakah seluruh `analysis_date` sampel tersebut sudah terdaftar.
3. **Pemberhentian Dini (Early Skip)**: 
   - Jika **semua** sampel `analysis_date` sudah ada di database, program akan log informasi skip dan langsung **berhenti secara bersih (Exit 0)** dalam waktu < 1 detik.
   - Jika ditemukan `analysis_date` baru atau jika database dinonaktifkan (mode `--dry-run`/`--skip-db`), program akan melanjutkan eksekusi pipeline penuh (mengunduh data 45 desa, menghitung PET, mengunggah ke DB dan S3).

Mekanisme ini menjaga agar program bersifat *Idempotent* dan memungkinkan pemicuan terjadwal dijalankan secara berkala (misal setiap jam) tanpa membuang-buang sumber daya komputasi.

---

## Dependensi Utama

Detail pustaka utama yang digunakan dalam proyek ini dapat dilihat pada berkas [requirements.txt](requirements.txt):

*   `biometeo==0.4.1`: Pustaka utama perhitungan parameter kenyamanan termal manusia (*Mean Radiant Temperature* / Tmrt dan *Physiologically Equivalent Temperature* / PET).
*   `pandas` & `numpy`: Pustaka manipulasi data dan perhitungan numerik.
*   `psycopg2-binary`: Driver konektor PostgreSQL untuk operasi database.
*   `boto3`: AWS SDK untuk Python yang digunakan untuk mengunggah arsip ke Supabase Storage via protokol S3.
*   `pytest` & `pytest-html`: Alat pengujian unit beserta pembuat laporan HTML hasil uji.

---

## Variabel Lingkungan (Environment Variables)

Salin berkas `.env.example` menjadi `.env` dan sesuaikan nilainya untuk menjalankan *pipeline* secara lokal atau konfigurasi di GitHub Secrets untuk kebutuhan *action workflow*.

| Variabel | Deskripsi | Default |
|---|---|---|
| `DATABASE_URL` | URI koneksi utama PostgreSQL/Supabase | - |
| `DB_USER` s.d. `DB_NAME` | Kredensial koneksi database alternatif | - |
| `S3_ENDPOINT_URL` | URL endpoint S3 Supabase Storage | - |
| `S3_ACCESS_KEY_ID` | Access Key ID untuk S3 storage | - |
| `S3_SECRET_ACCESS_KEY` | Secret Access Key untuk S3 storage | - |
| `S3_BUCKET_NAME` | Nama bucket tempat penyimpanan arsip | `pet_analysis` |
| `APP_ENV` | Mode runtime aplikasi (`dev` atau `prod`) | `dev` |
| `KEEP_LOCAL_ARTIFACTS`| Menyimpan arsip keluaran lokal setelah run | `true` |
| `OUTPUT_PARENT_DIR` | Folder utama penyimpanan laporan lokal | `reports` |

*Catatan: Pada lingkungan `APP_ENV=prod` dan `KEEP_LOCAL_ARTIFACTS=false`, berkas CSV keluaran akan dibuat di direktori temporer sistem dan langsung dihapus setelah berhasil diunggah ke storage S3 untuk efisiensi ruang penyimpanan.*

---

## Penggunaan Lokal (Windows)

Eksekusi lokal memerlukan sistem operasi Windows agar pustaka biner `biometeo` dapat dijalankan.

### Langkah Persiapan
1. Aktifkan *virtual environment* Python:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
2. Pasang semua dependensi yang dibutuhkan:
   ```powershell
   pip install -r requirements.txt
   ```

### Eksekusi Pipeline
Jalankan *pipeline* menggunakan skrip PowerShell pembantu:
```powershell
.\scripts\run_local.ps1
```
Skrip di atas secara otomatis menyetel variabel `PYTHONPATH=src` dan `RUN_ENV=local` serta memanggil program utama dengan parameter slot `manual`.

Opsi argumen CLI tambahan pada `main.py`:
*   `--slot [morning|evening|manual]`: Menentukan slot waktu eksekusi run.
*   `--dry-run`: Menghitung data dan menulis file lokal tanpa melakukan pengunggahan ke DB atau S3 Storage.
*   `--skip-db`: Melewati proses unggah data hasil perhitungan ke database.
*   `--skip-storage`: Melewati proses unggah berkas arsip ke S3 Storage.
*   `--max-villages [N]`: Membatasi pemrosesan data BMKG hanya untuk N desa pertama.

---

## Penggunaan di GitHub Actions

Repositori ini memiliki dua workflow GitHub Actions:

### 1. CI Workflow (`.github/workflows/ci.yml`)
Berjalan secara otomatis pada setiap `push` atau `pull_request` ke cabang `main`. Alur ini bertugas memverifikasi kualitas kode dengan menjalankan *smoke test* dan unit test (`pytest`) menggunakan runner Windows.

### 2. Run Biometeo Worker Workflow (`.github/workflows/run-biometeo-worker.yml`)
Digunakan untuk jalannya pipeline produksi (scheduled) atau manual debug via `workflow_dispatch`.

*   **Parameter Input Manual Run**:
    *   `slot` (pilihan: `morning`, `evening`, `manual`): Slot waktu berjalan.
    *   `run_tests` (tipe: `boolean`, default `false`): Jika disetel `true` (hanya berlaku jika `slot=manual`), alur kerja akan menjalankan unit test (`pytest`) secara lengkap. Pada slot terjadwal (`morning`/`evening`), langkah pengujian unit dilewati untuk menghemat compute time.
*   **Langkah Pemicu Manual**:
    1. Masuk ke menu **Actions** di GitHub.
    2. Pilih workflow **Run Biometeo Worker** di sebelah kiri.
    3. Klik **Run workflow**, tentukan opsi input parameter, lalu klik tombol **Run workflow** berwarna hijau.

### Kredensial Rahasia (Secrets) yang Dibutuhkan
Kunci-kunci berikut harus dikonfigurasi di repositori GitHub (**Settings -> Secrets and Variables -> Actions**):
*   `DATABASE_URL`: URI koneksi database Supabase.
*   `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION`: Informasi bucket Supabase Storage (S3).

---

## Pemicu Jadwal Eksternal (GCP)

Untuk menghemat kuota eksekusi dan meningkatkan keandalan kontrol penjadwalan, repositori ini **tidak menggunakan modul cron scheduler bawaan GitHub Actions**.

Sebagai gantinya, jadwal eksekusi produksi pagi & sore diorkestrasi secara eksternal (seperti **GCP Cloud Scheduler**). Penjadwal tersebut mengirimkan request HTTP POST ke REST API GitHub (`/repos/{owner}/{repo}/actions/workflows/run-biometeo-worker.yml/dispatches`) dengan autentikasi Token PAT dan input parameter `slot` yang sesuai.

---

## Sinkronisasi Data Destinasi

Jika terdapat pembaruan data koordinat, nama destinasi, atau tinggi elevasi laut pada konfigurasi lokal di [destinations.py](src/biometeo_worker/destinations.py), data tersebut harus disinkronkan ke database menggunakan perintah:

```powershell
$env:PYTHONPATH="src"
python -m scripts.sync_destinations_to_db
```

Tambahkan bendera `--dry-run` untuk memverifikasi perubahan dan melakukan simulasi (rollback otomatis) sebelum perubahan permanen diterapkan di database.

---

## Pengujian & Verifikasi

### Pengujian Unit (Pytest)
Pengujian unit menggunakan pustaka `pytest` dengan pengaturan yang didefinisikan dalam `pyproject.toml`.
Untuk menjalankan seluruh suite pengujian secara lokal:
```powershell
pytest
```

### Smoke Test
Smoke test digunakan untuk memverifikasi fungsionalitas dasar komputasi *biometeo* dan keutuhan paket *worker* dengan cepat (dalam milidetik). Pengujian ini otomatis dijalankan di GitHub Actions runner sebelum langkah kerja lainnya dimulai:
```powershell
python scripts/smoke_test.py
```
Uji coba ini memverifikasi:
1. Python aktif di runner.
2. Pustaka biner `biometeo` sukses di-import.
3. Fungsi komputasi inti (`Tmrt_calc` dan `mPET`) berfungsi normal.
4. Struktur internal `biometeo_worker` dapat di-import dengan benar.

---

## Kontribusi & Hak Cipta

Proyek ini bersifat **private** (tertutup). Seluruh hak cipta dilindungi oleh penulis dan Sekolah Tinggi Meteorologi Klimatologi dan Geofisika (STMKG). 

Hubungi penulis jika ada pertanyaan lebih lanjut terkait penelitian ini:
*   **Nama**: Ahmad Meijlan Yasir
*   **Email**: yasirahmad220504@gmail.com
*   **Instansi**: Sekolah Tinggi Meteorologi Klimatologi dan Geofisika (STMKG), Tangerang.
