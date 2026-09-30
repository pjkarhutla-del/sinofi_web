# SIAGA Karhutla — Sistem Informasi Terpadu

Gabungan dua aplikasi HTML statis menjadi **satu sistem informasi** berbasis **Python Django 5.2** dan **PostgreSQL**:

| Aplikasi asal | Menjadi |
|---|---|
| `Laporan_Harian_Dalkarhut_KSDAE` (Supabase + JS) | Dashboard, Matriks Kawasan × Tanggal, Peta Kejadian, Isi/Ubah/Hapus Laporan |
| `Monitor-Hotspot-HK` (Leaflet + Turf.js, panggil API SIPONGI dari browser) | Monitor Hotspot, statistik, ekspor XLSX/CSV/SHP |
| `kawasan.geojson` (dobel di kedua repo, 10 MB) | Tabel `kawasan` di PostgreSQL (579 kawasan, satu sumber kebenaran) |

## Yang berubah secara arsitektur

| Sebelumnya | Sekarang | Manfaat |
|---|---|---|
| Data di Supabase, kunci API tertanam di HTML | PostgreSQL milik sendiri; kredensial di `.env` | Tidak ada kredensial di browser; data di bawah kendali Anda |
| Siapa pun yang tahu kunci bisa menulis (bergantung RLS) | Login + peran (Operator / Pengelola / hanya-baca) | Ada jejak `created_by` / `updated_by` |
| Hotspot diambil langsung dari browser tiap dibuka (± 10 MB GeoJSON diunduh & dihitung Turf.js) | Diambil terjadwal ke tabel `hotspot`, dicocokkan dengan kawasan di server (Shapely STRtree) | Halaman cepat; **riwayat hotspot tersimpan**; 100.000 titik dicocokkan ± 0,3 dtk |
| `NKWS`/`NUPT` disimpan sebagai teks di tiap laporan | Laporan berelasi ke `kawasan` (foreign key) | Tak ada lagi salah ketik nama kawasan yang memutus rantai status |
| Dua modul terpisah tanpa hubungan | Terhubung | Fitur baru: **"Hotspot Belum Ada Laporan"** (kawasan bertitik High/Medium tanpa laporan) |

Logika bisnis pemantauan (rantai status, gelombang pemadaman aktif, keterlambatan update, matriks) dipindahkan dari JavaScript ke `apps/laporan/services.py` dan **diuji otomatis** (61 tes).

## Struktur

```
siaga/                 konfigurasi Django
apps/kawasan/          master kawasan + batas wilayah + indeks spasial
apps/laporan/          laporan harian, parser teks, logika bisnis, peran pengguna
apps/hotspot/          klien SIPONGI, sinkronisasi, statistik, ekspor
apps/dashboard/        halaman: dashboard, matriks, peta, monitor hotspot
templates/, static/    tampilan (Tailwind CDN + Leaflet + Chart.js)
data/kawasan.geojson   sumber batas kawasan (diimpor ke DB)
```

Model data: `Kawasan` 1—N `Laporan`; `Kawasan` 1—N `Hotspot`; `HotspotSyncLog` mencatat tiap sinkronisasi.
Satu baris `Laporan` = satu titik koordinat pada satu tanggal (sama dengan tabel `reports` lama).

## Pemasangan (lokal)

Prasyarat: Python 3.11+, PostgreSQL 14+.

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # lalu sesuaikan kredensial PostgreSQL

# buat database (sekali)
sudo -u postgres psql -c "CREATE USER siaga WITH PASSWORD 'siaga';"
sudo -u postgres psql -c "CREATE DATABASE siaga_karhutla OWNER siaga;"

python manage.py migrate
python manage.py import_kawasan          # 579 kawasan + batas wilayah (± 5 dtk)
python manage.py setup_roles             # grup peran
python manage.py createsuperuser
python manage.py sync_hotspot --days 7   # ambil hotspot SIPONGI 7 hari terakhir
python manage.py runserver
```

Buka http://localhost:8000. Untuk mencoba tanpa data asli: `python manage.py seed_demo --with-user` (akun `demo` / `demo12345` — **jangan di produksi**).

### Docker

```bash
cp .env.example .env    # isi POSTGRES_PASSWORD dan DJANGO_SECRET_KEY, set DJANGO_DEBUG=0
docker compose up -d --build
docker compose exec web sh -c "python manage.py migrate && python manage.py import_kawasan && python manage.py setup_roles && python manage.py createsuperuser"
```

Layanan `hotspot-sync` menyinkronkan SIPONGI tiap 30 menit. Tanpa Docker gunakan `deploy_crontab.example`.

## Peran pengguna

Buat pengguna di `/admin/` lalu masukkan ke grup:

| Peran | Hak |
|---|---|
| (login saja) | Melihat dashboard, matriks, peta, hotspot, daftar laporan; ekspor |
| **Operator Laporan** | + tambah dan ubah laporan |
| **Pengelola Laporan** | + hapus laporan |
| Staf (`is_staff`) | + `/admin/`, tombol "Sinkron SIPONGI" |

`SIAGA_PUBLIC_READ=1` membuka tampilan baca tanpa login (input tetap wajib login) — sesuai perilaku aplikasi lama yang publik.

## Memindahkan data lama dari Supabase

1. Di Supabase → Table Editor → ekspor tabel `reports` ke CSV (opsional: tabel `kawasan` lama).
2. Uji dulu tanpa menyimpan:
   ```bash
   python manage.py import_supabase reports.csv --dry-run
   ```
3. Impor sungguhan:
   ```bash
   python manage.py import_supabase reports.csv --kawasan-csv kawasan_lama.csv
   ```

Aman dijalankan berulang (baris yang sudah masuk dilewati berdasar UUID / ID lama). Baris yang tidak bisa dipetakan ditulis ke `import_dilewati.csv` beserta alasannya — **periksa file ini**. Pencocokan kawasan memakai UPT + nama; pencocokan hanya-nama sengaja dimatikan karena bisa salah atribusi (aktifkan dengan `--match-nkws-only` setelah Anda meninjau daftarnya). Cap waktu `created_at`/`updated_at` asli dipertahankan.

## Perintah manajemen

| Perintah | Fungsi |
|---|---|
| `import_kawasan [--file ...]` | Impor/perbarui kawasan dari GeoJSON (aman diulang) |
| `sync_hotspot [--days N \| --from --to \| --latest]` | Ambil hotspot SIPONGI |
| `sync_hotspot --rematch` | Hitung ulang kawasan semua hotspot (jalankan setelah batas kawasan diubah) |
| `import_supabase` | Impor laporan lama |
| `setup_roles` | Buat grup peran |
| `seed_demo` | Data contoh |

## Catatan operasional

- **Endpoint SIPONGI** (`opsroom.sipongidata.my.id`) adalah API pihak ketiga tanpa dokumentasi resmi yang saya ketahui. Parameter dan bentuk respons mengikuti aplikasi lama; klien menangani tiga bentuk respons yang dipakai kode lama. Bila format berubah, `apps/hotspot/sipongi.py` satu-satunya tempat yang perlu disesuaikan. Setiap sinkronisasi (sukses/gagal) tercatat di admin → *Hotspot sync logs*.
- Hotspot `low` tidak disimpan (aplikasi lama juga hanya menampilkan High/Medium). Ubah lewat `HOTSPOT_STORE_CONFIDENCE`.
- Front-end memakai CDN (Tailwind Play CDN, Leaflet, Chart.js, tile Esri/OSM) sehingga pengguna perlu internet. Untuk produksi resmi, sebaiknya Tailwind di-*build* dan pustaka JS di-*host* lokal.
- Mengubah `kawasan.geojson` lalu `import_kawasan` memperbarui data kawasan yang ada; jalankan `sync_hotspot --rematch` agar hotspot lama mengikuti batas baru.
- Cadangkan PostgreSQL secara berkala (`pg_dump`, lihat `deploy_crontab.example`).

## Pengujian

```bash
python manage.py test        # 61 tes: logika bisnis, parser, spasial, sinkronisasi, izin akses, impor, ekspor
```
