"""
Telegram Bot & Notification Integration for HomeMonitor
Supports alerts (Power outage, New WiFi device, Speedtest) and interactive bot commands (/wake, /status, /devices, /speedtest, /scan).
Pure Python 3 standard library.
"""

import time
import json
import urllib.request
import urllib.parse
import threading
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

class TelegramBot:
    def __init__(self, config_getter, system_monitor=None, network_scanner=None, wol_manager=None, speedtest_manager=None):
        self.config_getter = config_getter
        self.system_monitor = system_monitor
        self.network_scanner = network_scanner
        self.wol_manager = wol_manager
        self.speedtest_manager = speedtest_manager
        self.polling_thread = None
        self.running = False
        self.last_update_id = 0

    def get_token(self):
        cfg = self.config_getter()
        return cfg.get("telegram_token", "").strip()

    def get_chat_id(self):
        cfg = self.config_getter()
        return str(cfg.get("telegram_chat_id", "")).strip()

    def is_configured(self):
        return bool(self.get_token() and self.get_chat_id())

    def send_message(self, text: str, chat_id: str = None, reply_markup: dict = None):
        """Sends an HTML formatted message via Telegram Bot API."""
        token = self.get_token()
        target_chat = chat_id or self.get_chat_id()
        if not token or not target_chat:
            return False, "Token atau Chat ID belum dikonfigurasi"

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as r:
                res = json.loads(r.read().decode("utf-8"))
                return res.get("ok", False), res
        except urllib.error.HTTPError as e:
            try:
                err_resp = json.loads(e.read().decode("utf-8"))
                return False, err_resp.get("description", str(e))
            except Exception:
                return False, f"HTTP Error {e.code}: {e.reason}"
        except Exception as e:
            return False, str(e)

    def test_connection(self, token: str, chat_id: str):
        """Sends a verification message to check credentials."""
        if not token or not chat_id:
            return False, "Token dan Chat ID harus diisi"

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        text = (
            "🎉 <b>Koneksi HomeMonitor Berhasil!</b>\n\n"
            "Bot Telegram server rumah Anda telah aktif dan siap mengirimkan:\n"
            "• ⚡ Notifikasi Listrik Padam / Nyala\n"
            "• 🔍 Deteksi Perangkat Baru di WiFi\n"
            "• 🚀 Hasil Pengujian Kecepatan Internet\n"
            "• 🎮 Remote Wake-on-LAN via Chat (/wake)\n\n"
            "<i>Waktu server: " + time.strftime("%Y-%m-%d %H:%M:%S WIB") + "</i>"
        )
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as r:
                res = json.loads(r.read().decode("utf-8"))
                return res.get("ok", False), "Pesan tes berhasil dikirim ke Telegram!"
        except Exception as e:
            return False, f"Gagal mengirim pesan tes: {e}"

    # ---------------- NOTIFICATION ALERTS ----------------

    def notify_power_outage(self, battery_pct: int, time_str: str):
        cfg = self.config_getter()
        if not cfg.get("notify_power", True):
            return
        text = (
            "🚨 <b>PERINGATAN: LISTRIK RUMAH PADAM!</b>\n\n"
            "Daya listrik AC terputus. Server laptop beralih ke daya baterai (UPS Mode).\n"
            f"🔋 Sisa Baterai: <b>{battery_pct}%</b>\n"
            f"🕒 Waktu Kejadian: <b>{time_str}</b>\n\n"
            "<i>Server tetap menyala selama kapasitas baterai mencukupi.</i>"
        )
        self.send_message(text)

    def notify_power_restored(self, battery_pct: int, time_str: str):
        cfg = self.config_getter()
        if not cfg.get("notify_power", True):
            return
        text = (
            "✅ <b>LISTRIK SUDAH MENYALA KEMBALI!</b>\n\n"
            "Daya listrik AC terhubung kembali ke server rumah.\n"
            f"🔋 Status Baterai: <b>{battery_pct}%</b> (Sedang Mengisi / Siaga)\n"
            f"🕒 Waktu Kejadian: <b>{time_str}</b>\n\n"
            "<i>Sistem kembali beroperasi normal.</i>"
        )
        self.send_message(text)

    def notify_new_device(self, ip: str, mac: str, vendor: str, name: str, time_str: str):
        cfg = self.config_getter()
        if not cfg.get("notify_new_devices", True):
            return
        text = (
            "🔍 <b>DETEKSI: PERANGKAT BARU TERHUBUNG KE WIFI!</b>\n\n"
            f"• <b>Alamat IP:</b> <code>{ip}</code>\n"
            f"• <b>MAC Address:</b> <code>{mac}</code>\n"
            f"• <b>Vendor / Merk:</b> <b>{vendor}</b>\n"
            f"• <b>Nama / Host:</b> {name or '-'}\n"
            f"• <b>Waktu Deteksi:</b> {time_str}\n\n"
            "<i>Buka dashboard untuk memberi nama atau memverifikasi perangkat ini.</i>"
        )
        self.send_message(text)

    def notify_speedtest_result(self, res: dict):
        cfg = self.config_getter()
        if not cfg.get("notify_speedtest", True):
            return
        text = (
            "🚀 <b>LAPORAN HASIL KECEPATAN INTERNET RUMAH</b>\n\n"
            f"• <b>Download:</b> <b>{res.get('download_mbps', 0)} Mbps</b>\n"
            f"• <b>Upload:</b> <b>{res.get('upload_mbps', 0)} Mbps</b>\n"
            f"• <b>Ping Latency:</b> <b>{res.get('ping_ms', 0)} ms</b>\n"
            f"• <b>Kualitas:</b> {res.get('quality', 'Normal')}\n"
            f"• <b>Waktu:</b> {res.get('time_str', '')}"
        )
        self.send_message(text)

    # ---------------- INTERACTIVE POLLING BOT ----------------

    def start_polling(self):
        if self.running:
            return
        self.running = True
        self.polling_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.polling_thread.start()

    def stop_polling(self):
        self.running = False

    def _poll_loop(self):
        print("[*] Telegram Bot command poller dimulai...")
        while self.running:
            token = self.get_token()
            cfg = self.config_getter()
            if not token or not cfg.get("enable_bot_commands", True):
                time.sleep(5)
                continue

            try:
                url = f"https://api.telegram.org/bot{token}/getUpdates?offset={self.last_update_id + 1}&timeout=20"
                req = urllib.request.Request(url, headers={"User-Agent": "HomeMonitor-Bot/1.0"})
                with urllib.request.urlopen(req, timeout=25) as r:
                    res = json.loads(r.read().decode("utf-8"))
                    if res.get("ok") and res.get("result"):
                        for update in res["result"]:
                            self.last_update_id = update["update_id"]
                            self._handle_update(update)
            except Exception:
                time.sleep(3)

    def _handle_update(self, update: dict):
        msg = update.get("message")
        if not msg:
            return

        chat_id = str(msg.get("chat", {}).get("id"))
        text = msg.get("text", "").strip()

        # Security check: If chat_id is set in config, only allow that chat_id
        authorized_chat = self.get_chat_id()
        if authorized_chat and chat_id != authorized_chat:
            self.send_message(
                "⛔ <i>Akses Ditolak: Chat ID Anda belum terdaftar di pengaturan HomeMonitor.</i>",
                chat_id=chat_id
            )
            return

        if not text:
            return

        cmd = text.split()[0].lower()
        args = text.split()[1:]

        if cmd in ["/start", "/help", "menu", "help"]:
            reply = (
                "🏠 <b>Selamat Datang di Asisten HomeMonitor!</b>\n\n"
                "Server rumah Anda standby 24 jam. Gunakan perintah berikut:\n\n"
                "⚡ <code>/wake [nama_pc]</code> — Nyalakan PC rumah lewat Wake-on-LAN\n"
                "📊 <code>/status</code> — Cek CPU, suhu, RAM, daya & baterai\n"
                "📡 <code>/devices</code> — Lihat perangkat yang sedang online di WiFi\n"
                "🔍 <code>/scan</code> — Pindai ulang seluruh jaringan lokal\n"
                "🚀 <code>/speedtest</code> — Uji kecepatan download & upload\n"
                "🔋 <code>/power</code> — Cek status listrik AC & baterai server\n"
                "❓ <code>/help</code> — Bantuan menu ini"
            )
            self.send_message(reply, chat_id=chat_id)

        elif cmd == "/status":
            if not self.system_monitor:
                self.send_message("Sistem monitor belum siap.", chat_id=chat_id)
                return
            snap = self.system_monitor.snapshot()
            cpu = snap.get("cpu", {})
            mem = snap.get("memory", {})
            power = snap.get("power", {})
            uptime = snap.get("uptime", {})
            net = snap.get("network", {})

            used_ram = round(mem.get("used_bytes", 0) / (1024**3), 1)
            total_ram = round(mem.get("total_bytes", 0) / (1024**3), 1)

            online_devs = 0
            if self.network_scanner:
                devs = self.network_scanner.list_devices()
                online_devs = sum(1 for d in devs if d.get("is_online"))

            reply = (
                "📊 <b>STATUS SERVER HOMEMONITOR (24 JAM)</b>\n\n"
                f"• <b>Hostname:</b> <code>{snap.get('hostname')}</code>\n"
                f"• <b>CPU:</b> {cpu.get('usage_percent')}% | Suhu: <b>{cpu.get('temperature_c', '--')}°C</b>\n"
                f"• <b>RAM:</b> {used_ram} GB / {total_ram} GB ({mem.get('percent')} %)\n"
                f"• <b>Status Daya:</b> {'🔌 AC Terhubung' if power.get('ac_connected') else '🔋 Mode Baterai'} ({power.get('capacity')}%)\n"
                f"• <b>Uptime:</b> {uptime.get('formatted')}\n"
                f"• <b>Trafik LAN:</b> ↓ {net.get('rx_rate_kbps')} KB/s | ↑ {net.get('tx_rate_kbps')} KB/s\n"
                f"• <b>Perangkat Online:</b> <b>{online_devs} perangkat</b>\n\n"
                f"<i>Waktu: {snap.get('local_time', '')}</i>"
            )
            self.send_message(reply, chat_id=chat_id)

        elif cmd == "/power":
            if not self.system_monitor:
                return
            p = self.system_monitor.get_power_info()
            status_text = "🔌 Listrik PLN / AC Menyala Normal" if p.get("ac_connected") else "🚨 LISTRIK PADAM (Menggunakan Daya Baterai)"
            reply = (
                f"🔋 <b>STATUS CATU DAYA SERVER</b>\n\n"
                f"• <b>Kondisi:</b> <b>{status_text}</b>\n"
                f"• <b>Kapasitas Baterai:</b> <b>{p.get('capacity')}%</b>\n"
                f"• <b>Status Pengisian:</b> {p.get('status')}\n"
                f"• <b>Fungsi:</b> Built-in UPS Siaga 24 Jam"
            )
            self.send_message(reply, chat_id=chat_id)

        elif cmd == "/devices":
            if not self.network_scanner:
                self.send_message("Network scanner belum siap.", chat_id=chat_id)
                return
            devs = self.network_scanner.list_devices()
            online = [d for d in devs if d.get("is_online")]

            if not online:
                self.send_message("Tidak ada perangkat online terdeteksi.", chat_id=chat_id)
                return

            lines = ["📡 <b>PERANGKAT ONLINE DI JARINGAN RUMAH:</b>\n"]
            for d in online[:20]:  # limit to 20
                name = d.get("custom_name") or d.get("hostname") or d.get("vendor") or "Perangkat"
                badge = " (ROUTER)" if d.get("is_router") else (" (SERVER)" if d.get("is_host") else "")
                lat = f"{d.get('latency_ms', '-')}ms"
                lines.append(f"• <code>{d.get('ip')}</code> — <b>{name}</b>{badge} [{lat}]")

            lines.append(f"\n<i>Total: {len(online)} perangkat online</i>")
            self.send_message("\n".join(lines), chat_id=chat_id)

        elif cmd == "/scan":
            self.send_message("🔍 Memulai pemindaian 254 IP jaringan lokal... Mohon tunggu ~3 detik.", chat_id=chat_id)
            if self.network_scanner:
                def run_and_report():
                    ok, msg = self.network_scanner.scan()
                    devs = self.network_scanner.list_devices()
                    online_count = sum(1 for d in devs if d.get("is_online"))
                    self.send_message(
                        f"✅ <b>Pemindaian Selesai!</b>\nDitemukan <b>{online_count} perangkat aktif</b> di jaringan rumah.",
                        chat_id=chat_id
                    )
                threading.Thread(target=run_and_report, daemon=True).start()

        elif cmd == "/wake":
            if not self.wol_manager:
                self.send_message("Fitur Wake-on-LAN belum siap.", chat_id=chat_id)
                return

            targets = self.wol_manager.list_targets()
            if not args:
                if not targets:
                    self.send_message(
                        "Belum ada target PC tersimpan di daftar Wake-on-LAN.\n"
                        "Gunakan <code>/wake AA:BB:CC:DD:EE:FF</code> atau tambahkan target lewat dashboard web.",
                        chat_id=chat_id
                    )
                    return

                msg_lines = ["⚡ <b>PILIH PC YANG INGIN DINYALAKAN:</b>\n"]
                for t in targets:
                    msg_lines.append(f"• <code>/wake {t['name']}</code> (MAC: <code>{t['mac']}</code>)")
                msg_lines.append("\n<i>Ketik perintah di atas untuk menyalakan PC yang diinginkan.</i>")
                self.send_message("\n".join(msg_lines), chat_id=chat_id)
                return

            query = " ".join(args).lower().strip()
            # Match by name or MAC
            matched = None
            for t in targets:
                if query in t["name"].lower() or query == t["mac"].lower():
                    matched = t
                    break

            if matched:
                mac = matched["mac"]
                name = matched["name"]
                ip = matched.get("ip", "")
                self.wol_manager.send_magic_packet(mac, matched.get("broadcast_ip", "192.168.1.255"), matched.get("port", 9), ip, name)
                self.send_message(
                    f"⚡ <b>Sinyal Magic Packet terkirim ke {name}!</b>\n"
                    f"MAC: <code>{mac}</code>\n"
                    f"Target IP: <code>{ip or 'Subnet'}</code>\n\n"
                    f"<i>PC sedang memulai booting...</i>",
                    chat_id=chat_id
                )
            else:
                # If query looks like a MAC address, send directly
                clean_mac = query.replace(":", "").replace("-", "")
                if len(clean_mac) == 12:
                    try:
                        self.wol_manager.send_magic_packet(query, "192.168.1.255", 9, "", "PC Manual")
                        self.send_message(f"⚡ Magic Packet terkirim ke MAC <code>{query}</code>!", chat_id=chat_id)
                    except Exception as e:
                        self.send_message(f"Gagal mengirim WoL: {e}", chat_id=chat_id)
                else:
                    self.send_message(
                        f"Target PC <b>'{query}'</b> tidak ditemukan di daftar tersimpan.\n"
                        f"Gunakan <code>/wake</code> untuk melihat daftar target yang tersedia.",
                        chat_id=chat_id
                    )

        elif cmd == "/speedtest":
            if not self.speedtest_manager:
                self.send_message("Modul speedtest belum siap.", chat_id=chat_id)
                return

            if self.speedtest_manager.is_running:
                self.send_message("⏳ Pengujian kecepatan sedang berlangsung di server, mohon tunggu sebentar...", chat_id=chat_id)
                return

            self.send_message("🚀 Sedang menguji kecepatan internet rumah (Download & Upload)... Mohon tunggu ~10 detik.", chat_id=chat_id)

            def run_and_reply():
                ok, msg, res = self.speedtest_manager.run_test(triggered_by="telegram_bot")
                if ok and res:
                    reply = (
                        "🚀 <b>HASIL SPEEDTEST INTERNET RUMAH:</b>\n\n"
                        f"• 📥 <b>Download:</b> <b>{res['download_mbps']} Mbps</b>\n"
                        f"• 📤 <b>Upload:</b> <b>{res['upload_mbps']} Mbps</b>\n"
                        f"• ⚡ <b>Ping Latency:</b> <b>{res['ping_ms']} ms</b>\n"
                        f"• 📶 <b>Kualitas:</b> {res['quality']}\n"
                        f"• 🌐 <b>Server:</b> Cloudflare CDN Edge\n\n"
                        f"<i>Waktu: {res['time_str']}</i>"
                    )
                    self.send_message(reply, chat_id=chat_id)
                else:
                    self.send_message(f"❌ Gagal melakukan speedtest: {msg}", chat_id=chat_id)

            threading.Thread(target=run_and_reply, daemon=True).start()

        else:
            self.send_message(
                f"Perintah <code>{cmd}</code> tidak dikenal. Ketik <code>/help</code> untuk melihat daftar perintah.",
                chat_id=chat_id
            )
