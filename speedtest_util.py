"""
Speedtest Utility for HomeMonitor
Lightweight, zero-dependency internet speed test using Cloudflare CDN endpoints.
"""

import time
import json
import urllib.request
import threading
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SPEEDTEST_FILE = DATA_DIR / "speedtest.json"

class SpeedtestManager:
    def __init__(self, data_file: Path = SPEEDTEST_FILE):
        self.data_file = data_file
        self.is_running = False
        self.lock = threading.Lock()
        self.history = self._load_history()

    def _load_history(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_history(self):
        try:
            with open(self.data_file, "w") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"Error saving speedtest history: {e}")

    def get_history(self):
        with self.lock:
            return list(self.history)

    def get_latest(self):
        with self.lock:
            return self.history[0] if self.history else None

    def run_test(self, triggered_by: str = "manual"):
        """Runs latency, download, and upload tests."""
        if self.is_running:
            return False, "Pengujian kecepatan sedang berjalan", None

        self.is_running = True
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            # 1. Latency & Jitter test (3 ping samples to Cloudflare)
            latencies = []
            for _ in range(3):
                try:
                    t0 = time.time()
                    req = urllib.request.Request("https://speed.cloudflare.com/__down?bytes=0", headers=headers)
                    with urllib.request.urlopen(req, timeout=5) as r:
                        r.read()
                    latencies.append((time.time() - t0) * 1000.0)
                except Exception:
                    pass
                time.sleep(0.05)

            ping_ms = round(min(latencies), 1) if latencies else 20.0
            jitter_ms = round(max(latencies) - min(latencies), 1) if len(latencies) >= 2 else 1.0

            # 2. Download test (Fetch 10 MB payload)
            download_bytes = 10 * 1024 * 1024
            req_dl = urllib.request.Request(
                f"https://speed.cloudflare.com/__down?bytes={download_bytes}",
                headers=headers
            )
            t0 = time.time()
            with urllib.request.urlopen(req_dl, timeout=20) as r:
                data = r.read()
            dt_dl = max(0.05, time.time() - t0)
            dl_mbps = round((len(data) * 8.0) / (dt_dl * 1_000_000.0), 2)

            # 3. Upload test (POST 2 MB payload)
            upload_bytes = 2 * 1024 * 1024
            payload = b"0" * upload_bytes
            headers_up = dict(headers)
            headers_up["Content-Type"] = "application/octet-stream"
            req_up = urllib.request.Request(
                "https://speed.cloudflare.com/__up",
                data=payload,
                headers=headers_up,
                method="POST"
            )
            t0 = time.time()
            with urllib.request.urlopen(req_up, timeout=20) as r:
                r.read()
            dt_up = max(0.05, time.time() - t0)
            ul_mbps = round((upload_bytes * 8.0) / (dt_up * 1_000_000.0), 2)

            # Rating
            quality = "Sangat Cepat" if dl_mbps >= 50 else ("Cepat & Stabil" if dl_mbps >= 20 else "Cukup")

            result = {
                "id": f"speed_{int(time.time())}",
                "timestamp": int(time.time()),
                "time_str": time.strftime("%Y-%m-%d %H:%M:%S WIB"),
                "download_mbps": dl_mbps,
                "upload_mbps": ul_mbps,
                "ping_ms": ping_ms,
                "jitter_ms": jitter_ms,
                "quality": quality,
                "server": "Cloudflare CDN Edge",
                "triggered_by": triggered_by
            }

            with self.lock:
                self.history.insert(0, result)
                self.history = self.history[:50]  # Keep last 50
                self._save_history()

            return True, "Pengujian kecepatan selesai", result

        except Exception as e:
            return False, f"Gagal menjalankan speedtest: {e}", None
        finally:
            self.is_running = False
