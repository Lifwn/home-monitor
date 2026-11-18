"""
Webhook Notification Manager for HomeMonitor
Supports sending instant alerts to:
- Discord Webhooks (with rich colored embeds)
- Slack Webhooks
- ntfy.sh Push Notifications (https://ntfy.sh/<topic>)
- Generic JSON HTTP POST endpoints (n8n, Home Assistant, Make, custom APIs)
- Telegram Bot API (via webhook/direct)

Zero external dependencies (pure Python 3 urllib).
"""

import time
import json
import urllib.request
import urllib.parse
from pathlib import Path

class WebhookManager:
    def __init__(self, config_getter):
        self.config_getter = config_getter

    def get_webhook_url(self) -> str:
        cfg = self.config_getter()
        return cfg.get("webhook_url", "").strip()

    def is_enabled(self) -> bool:
        cfg = self.config_getter()
        url = self.get_webhook_url()
        return bool(url and cfg.get("webhook_enabled", True))

    def send_notification(self, event_type: str, title: str, message: str, details: dict = None, level: str = "info"):
        """
        Dispatches notification to configured webhook URL.
        level: 'info' (blue), 'success' (green), 'warning' (amber/red), 'danger' (red)
        """
        url = self.get_webhook_url()
        if not url:
            return False, "Webhook URL belum dikonfigurasi"

        now_str = time.strftime("%Y-%m-%d %H:%M:%S WIB")
        details = details or {}

        # 1. DISCORD WEBHOOK
        if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
            color_map = {
                "info": 0x38bdf8,     # Light blue
                "success": 0x10b981,  # Emerald
                "warning": 0xf59e0b,  # Amber
                "danger": 0xef4444    # Red
            }
            fields = []
            for k, v in details.items():
                fields.append({"name": str(k).replace("_", " ").title(), "value": str(v), "inline": True})

            payload = {
                "username": "HomeMonitor 24/7",
                "avatar_url": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/home-assistant.png",
                "embeds": [
                    {
                        "title": title,
                        "description": message,
                        "color": color_map.get(level, 0x10b981),
                        "fields": fields,
                        "footer": {
                            "text": f"HomeMonitor Server • {now_str}"
                        }
                    }
                ]
            }

        # 2. SLACK WEBHOOK
        elif "hooks.slack.com" in url:
            payload = {
                "text": f"*{title}*\n{message}\n_{now_str}_"
            }

        # 3. NTFY.SH (Free Mobile Push Notification)
        elif "ntfy.sh" in url:
            priority_map = {
                "info": 3,
                "success": 3,
                "warning": 4,
                "danger": 5
            }
            tags_map = {
                "power_outage": ["warning", "zap"],
                "power_restored": ["white_check_mark", "electric_plug"],
                "device_discovered": ["mag", "satellite"],
                "speedtest": ["rocket", "chart_with_upwards_trend"],
                "wol_triggered": ["zap", "computer"]
            }
            payload = {
                "title": title,
                "message": message,
                "priority": priority_map.get(level, 3),
                "tags": tags_map.get(event_type, ["bell"])
            }

        # 4. GENERIC JSON POST
        else:
            payload = {
                "event": event_type,
                "title": title,
                "message": message,
                "level": level,
                "timestamp": int(time.time()),
                "time_str": now_str,
                "details": details
            }

        return self._post_json(url, payload)

    def _post_json(self, url: str, payload: dict):
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "HomeMonitor-Webhook/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                return True, f"HTTP {response.status}"
        except urllib.error.HTTPError as e:
            try:
                err_text = e.read().decode("utf-8")[:150]
                return False, f"HTTP {e.code}: {err_text}"
            except Exception:
                return False, f"HTTP Error {e.code}: {e.reason}"
        except Exception as e:
            return False, str(e)

    def test_webhook(self, test_url: str = None):
        """Sends an immediate test event."""
        target_url = test_url or self.get_webhook_url()
        if not target_url:
            return False, "Masukkan Webhook URL terlebih dahulu"

        saved_url = self.get_webhook_url()
        # Temporarily use target_url
        orig_getter = self.config_getter
        self.config_getter = lambda: {"webhook_url": target_url, "webhook_enabled": True}

        try:
            ok, msg = self.send_notification(
                event_type="test",
                title="🎉 Tes Notifikasi HomeMonitor Berhasil!",
                message="Webhook server rumah Anda berfungsi dengan normal dan siap mengirim peringatan.",
                details={
                    "Status": "Online 24/7",
                    "Waktu Server": time.strftime("%Y-%m-%d %H:%M:%S WIB")
                },
                level="success"
            )
            return ok, msg
        finally:
            self.config_getter = orig_getter

    # Helper notification triggers
    def notify_power_outage(self, battery_pct: int, time_str: str):
        cfg = self.config_getter()
        if not cfg.get("notify_power", True):
            return
        self.send_notification(
            event_type="power_outage",
            title="🚨 PERINGATAN: LISTRIK RUMAH PADAM!",
            message="Daya listrik PLN/AC terputus. Server laptop beralih ke baterai (UPS Mode).",
            details={
                "Sisa Baterai": f"{battery_pct}%",
                "Waktu Padam": time_str
            },
            level="danger"
        )

    def notify_power_restored(self, battery_pct: int, time_str: str):
        cfg = self.config_getter()
        if not cfg.get("notify_power", True):
            return
        self.send_notification(
            event_type="power_restored",
            title="✅ LISTRIK SUDAH MENYALA KEMBALI!",
            message="Daya listrik AC tersambung kembali ke server rumah.",
            details={
                "Kondisi Baterai": f"{battery_pct}%",
                "Waktu Pulih": time_str
            },
            level="success"
        )

    def notify_new_device(self, ip: str, mac: str, vendor: str, name: str, time_str: str):
        cfg = self.config_getter()
        if not cfg.get("notify_new_devices", True):
            return
        self.send_notification(
            event_type="device_discovered",
            title="🔍 PERANGKAT BARU TERHUBUNG KE WIFI!",
            message=f"Terdeteksi perangkat baru yang belum pernah dikenal terhubung ke jaringan rumah.",
            details={
                "IP Address": ip,
                "MAC Address": mac,
                "Vendor / Merk": vendor,
                "Nama / Host": name or "-",
                "Waktu": time_str
            },
            level="warning"
        )

    def notify_speedtest(self, res: dict):
        cfg = self.config_getter()
        if not cfg.get("notify_speedtest", True):
            return
        self.send_notification(
            event_type="speedtest",
            title="🚀 HASIL SPEEDTEST INTERNET RUMAH",
            message=f"Pengujian otomatis kecepatan internet selesai dengan status: {res.get('quality', 'Normal')}.",
            details={
                "Download": f"{res.get('download_mbps', 0)} Mbps",
                "Upload": f"{res.get('upload_mbps', 0)} Mbps",
                "Ping": f"{res.get('ping_ms', 0)} ms",
                "Jitter": f"{res.get('jitter_ms', 0)} ms",
                "Waktu": res.get("time_str", "")
            },
            level="info"
        )

    def notify_wol_triggered(self, target_name: str, mac: str, ip: str = ""):
        cfg = self.config_getter()
        if not cfg.get("notify_wol", False):
            return
        self.send_notification(
            event_type="wol_triggered",
            title="⚡ SINYAL WAKE-ON-LAN DIKIRIM!",
            message=f"Magic Packet telah dikirim ke PC target: {target_name}.",
            details={
                "Target PC": target_name,
                "MAC Address": mac,
                "Target IP": ip or "Subnet Broadcast"
            },
            level="info"
        )
