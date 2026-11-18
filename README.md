# 🏠 HomeMonitor - Dashboard Hardware & Jaringan Rumah 24/7 + Wake-on-LAN

Aplikasi web modern, ringan, dan responsif yang berjalan 24 jam nonstop pada server rumah (laptop/mini PC) di dalam **Docker Container** untuk memantau status perangkat keras server, memindai seluruh perangkat yang terhubung ke jaringan WiFi/LAN rumah, serta menyalakan PC/komputer dari jarak jauh menggunakan sinyal **Wake-on-LAN (WoL)**.

---

## 🚀 Akses Dashboard Web

Aplikasi berjalan otomatis 24 jam di background via Docker Compose pada port **8080**:

- **Dari Jaringan Rumah (WiFi / LAN):**  
  👉 [http://192.168.1.11:8080](http://192.168.1.11:8080)
- **Dari Luar Rumah (via Tailscale VPN):**  
  👉 [http://100.98.125.66:8080](http://100.98.125.66:8080)
- **Dari Komputer Ini Sendiri:**  
  👉 [http://localhost:8080](http://localhost:8080)

---

## ✨ Fitur Utama

### 1. 📡 Pemantau Jaringan Rumah & Deteksi Nama Otomatis
- **Resolusi Nama Ramah Otomatis:** Mendeteksi otomatis nama asli perangkat bawaan (seperti *`Alif’s MacBook Air`*, *`Android TV`*, *`LifPC`*, *`Poco F6`*) melalui protokol mDNS (Bonjour), SSDP (UPnP), NetBIOS, dan DHCP DNS.
- **Kustomisasi & Penamaan Alias:** Kolom *Nama & Alias* menampilkan nama bawaan secara default, dan Anda dapat mengubah/menambah nama alias kustom kapan saja dengan tombol edit.
- **Pemindaian Paralel Cepat:** Memindai subnet (`192.168.1.0/24`) dalam 2–3 detik menggunakan multithreaded ping sweep & ARP table.
- **Deteksi Penyusup WiFi:** Notifikasi otomatis saat ada perangkat baru yang tidak dikenal terhubung ke WiFi rumah.

### 2. ⚡ Wake-on-LAN (WoL) Center
- **Nyalakan PC 1-Klik:** Mengirimkan *Magic Packet* UDP broadcast ke MAC address target melalui subnet `192.168.1.255`.
- **Live Boot Tracker:** Saat PC dinyalakan, dashboard memantau status boot PC secara live sampai status berubah menjadi **🟢 Online**.
- **Manajemen Target PC:** Simpan beberapa PC/server sekaligus dengan nama dan catatan khusus.

### 3. 🖥️ Pemantau Hardware Server 24 Jam
- **CPU & Suhu:** Penggunaan CPU real-time, load average, dan pembacaan sensor suhu CPU (°C).
- **RAM & Swap:** Monitor kapasitas RAM fisik terpakai, RAM tersedia, serta alokasi Swap memory.
- **Penyimpanan (Storage SSD):** Menampilkan kapasitas partisi penyimpanan dan ruang kosong tersisa.
- **Daya & Deteksi Listrik Padam:** Mendeteksi status colokan charger listrik (AC Adapter) dan kapasitas baterai laptop standby (berfungsi sebagai built-in UPS cadangan daya saat mati lampu).
- **Bandwidth Jaringan:** Kecepatan download (RX) dan upload (TX) real-time antarmuka Ethernet `enp2s0`.
- **Integrasi Docker:** Menampilkan container Docker aktif di server (AdGuard Home, PostgreSQL, Portainer, dll.) melalui koneksi socket langsung.

### 4. 🔔 Integrasi Notifikasi & Speedtest
- **Webhook Notifikasi:** Kirim peringatan real-time (Mati Lampu, Listrik Menyala Kembali, Perangkat Baru di WiFi, Hasil Speedtest) ke Discord, ntfy.sh, Slack, atau Custom Webhook.
- **Auto Speedtest:** Pengujian kecepatan download/upload/ping secara berkala langsung ke Cloudflare Edge CDN tanpa dependensi CLI berat.

---

## 🐳 Pengelolaan via Docker Compose

Aplikasi telah dibungkus menggunakan Docker Compose dengan mode `network_mode: host` agar memiliki akses langsung ke subnet LAN rumah, paket broadcast Wake-on-LAN, dan mDNS discovery:

```bash
# Menjalankan container di background
docker compose up -d

# Melihat status container
docker compose ps

# Melihat log aktivitas real-time
docker compose logs -f

# Me-restart aplikasi
docker compose restart

# Menghentikan aplikasi
docker compose down

# Membangun ulang (rebuild) image setelah perubahan kode
docker compose build && docker compose up -d
```

---

## 📁 Struktur Direktori

```
/home/alif/home-monitor/
├── docker-compose.yml     # Konfigurasi container service & bind mounts
├── Dockerfile             # Definisi image Python 3.11-slim dengan iputils & iproute2
├── .dockerignore          # Daftar file yang diabaikan saat build Docker
├── server.py              # Backend HTTP REST API & Hardware Monitoring
├── device_namer.py        # Resolusi nama perangkat mDNS, SSDP & NetBIOS
├── speedtest_util.py      # Penguji kecepatan internet Cloudflare CDN
├── telegram_bot.py        # Integrasi bot notifikasi & perintah Telegram
├── webhook.py             # Dispatcher notifikasi Webhook (Discord, ntfy, Slack)
├── static/
│   ├── index.html         # Antarmuka web modern responsif (Tailwind CSS)
│   ├── app.js             # Logika dashboard, modal, dan polling real-time
│   └── style.css          # Styling custom & animasi pulse
├── data/                  # Database lokal & konfigurasi (persisten volume)
│   ├── config.json        # Pengaturan webhook, notifikasi, dan bot
│   ├── detected_names.json# Cache nama perangkat yang terdeteksi otomatis
│   ├── devices.json       # Daftar perangkat jaringan & alias pengguna
│   ├── history.json       # Catatan riwayat aktivitas & notifikasi
│   ├── speedtest.json     # Riwayat pengujian kecepatan internet
│   └── wol_targets.json   # Daftar PC target Wake-on-LAN tersimpan
└── README.md              # Dokumentasi lengkap proyek
```
