# Pipeline PET / Kenyamanan Termal (GitHub Actions Windows Worker)

Repositori ini berisi orkestrator *pipeline* data *end-to-end* yang bertugas mengunduh data prakiraan cuaca dari API BMKG, memproses parameter meteorologi untuk menghitung indeks kenyamanan termal *Physiologically Equivalent Temperature* (PET) menggunakan pustaka `biometeo` (v0.4.1), mengklasifikasikan kategori kenyamanan termal, serta mengarsipkan hasilnya ke database PostgreSQL (Supabase) dan Supabase Storage (S3-compatible).

Sistem ini dikonfigurasi untuk berjalan di lingkungan **GitHub Actions dengan runner Windows (`windows-latest`)** karena pustaka perhitungan biometeorologi (`biometeo`) membutuhkan dependensi biner yang berjalan di platform Windows/Microsoft.

---

## Daftar Isi
- [Arsitektur & Struktur Direktori](#arsitektur--struktur-direktori)
- [Dependensi Utama](#dependensi-utama)
- [Variabel Lingkungan (Environment Variables)](#variabel-lingkungan-environment-variables)
- [Penggunaan Lokal (Windows)](#penggunaan-lokal-windows)
- [Penggunaan di GitHub Actions](#penggunaan-di-github-actions)
- [Pemicu Jadwal Eksternal (GCP)](#pemicu-jadwal-eksternal-gcp)
- [Sinkronisasi Data Destinasi](#sinkronisasi-data-destinasi)
- [Pengujian Unit](#pengujian-unit)

---

## Arsitektur & Struktur Direktori

Repositori ini disusun menggunakan struktur paket Python standar (`src/`) agar modular, teruji, dan mudah dipelihara.

```text
action/
├── .github/
│   └── workflows/
│       └── run-biometeo-worker.yml  # Definisi workflow GitHub Actions
├── src/
│   └── biometeo_worker/            # Paket program utama
│       ├── __init__.py
│       ├── main.py                 # Entrypoint orkestrator pipeline
│       ├── config.py               # Manajer konfigurasi & env var
│       ├── logger.py               # Modul logging terpusat (UTC)
│       ├── biometeo_engine.py      # Integrasi Tmrt_calc & PET biometeo
│       ├── bmkg_client.py          # Client API prakiraan cuaca BMKG
│       ├── classification.py       # Klasifikasi kenyamanan (Temperate & Sub-Tropic)
│       ├── database.py             # Operasi database PostgreSQL
│       ├── destinations.py         # Master data koordinat & elevasi 49 destinasi
│       ├── destinations_source_db.py # Pengambilan konfigurasi destinasi dari DB
│       ├── preprocessing.py        # Normalisasi satuan & reduksi kecepatan angin
│       └── storage.py              # Operasi upload arsip ke Supabase Storage (S3)
├── scripts/
│   ├── smoke_test.py               # Pengujian fungsionalitas pustaka biometeo
│   ├── run_local.ps1               # Script PowerShell untuk eksekusi lokal
│   └── sync_destinations_to_db.py  # Sinkronisasi master destinasi lokal ke DB
├── migrations/                     # Berkas migrasi database
├── reports/                        # Lokasi penyimpanan laporan & keluaran CSV runtime
├── tests/                          # Berkas pengujian unit (pytest)
├── .env.example
├── .gitignore
├── pyproject.toml                  # Konfigurasi project & pytest
├── README.md
└── requirements.txt
```

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
*   `--max-villages [N]`: Membatasi pemrosesan data BMKG hanya untuk N desa pertama (digunakan untuk *smoke testing* cepat).

---

## Penggunaan di GitHub Actions

Workflow GitHub Actions dikonfigurasi pada berkas [.github/workflows/run-biometeo-worker.yml](.github/workflows/run-biometeo-worker.yml).

### Pemicu Manual (Manual Run)
Workflow ini dikonfigurasi menggunakan pemicu `workflow_dispatch` sehingga dapat dijalankan secara manual melalui antarmuka web GitHub:
1. Masuk ke menu **Actions** pada halaman repositori GitHub.
2. Pilih workflow **Run Biometeo Worker** di panel sebelah kiri.
3. Klik tombol dropdown **Run workflow**.
4. Pilih opsi slot waktu eksekusi yang diinginkan (`morning`, `evening`, atau `manual`).
5. Klik tombol **Run workflow** untuk memulai proses.

### Kredensial Rahasia (Secrets) yang Dibutuhkan
Sebelum menjalankan *workflow*, pastikan kunci-kunci berikut sudah dikonfigurasi di menu **Settings -> Secrets and Variables -> Actions** pada repositori GitHub:
*   `SUPABASE_URL`: URL API utama proyek Supabase.
*   `SUPABASE_SERVICE_ROLE_KEY`: Service role API key dengan hak akses tulis database dan storage.
*   `BMKG_API_KEY`: API Key jika diperlukan untuk mengakses endpoint BMKG (opsional).

---

## Pemicu Jadwal Eksternal (GCP)

Untuk menghemat kuota eksekusi dan meningkatkan keandalan kontrol penjadwalan, repositori ini **tidak menggunakan modul cron scheduler bawaan GitHub Actions**.

Sebagai gantinya, orkestrasi jadwal run dijalankan secara terpusat dari layanan penjadwalan luar (seperti **GCP Cloud Scheduler** atau orkestrator eksternal lainnya). Penjadwal luar tersebut akan mengirimkan HTTP POST request ke REST API GitHub (`/repos/{owner}/{repo}/actions/workflows/run-biometeo-worker.yml/dispatches`) dengan membawa payload autentikasi GitHub Personal Access Token (PAT) beserta parameter input `slot` yang sesuai.

---

## Sinkronisasi Data Destinasi

Jika terdapat pembaruan data koordinat, nama destinasi, atau tinggi elevasi laut pada konfigurasi lokal di [destinations.py](src/biometeo_worker/destinations.py), data tersebut harus disinkronkan ke database menggunakan perintah:

```powershell
$env:PYTHONPATH="src"
python -m scripts.sync_destinations_to_db
```

Tambahkan bendera `--dry-run` untuk memverifikasi perubahan dan melakukan simulasi (rollback otomatis) sebelum perubahan permanen diterapkan di database.

---

## Pengujian Unit

Pengujian unit menggunakan pustaka `pytest` dengan pengaturan yang didefinisikan dalam `pyproject.toml`.

Untuk menjalankan seluruh suite pengujian secara lokal:
```powershell
pytest
```

Untuk menjalankan uji fungsionalitas dasar komputasi *biometeo*:
```powershell
python scripts/smoke_test.py
```
