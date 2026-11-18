#!/usr/bin/env python3
"""
HomeMonitor - 24/7 Home Server Hardware & Network Monitor with Wake-on-LAN
Lightweight, zero-dependency, pure Python 3 service.
"""

import os
import sys
import time

# Set timezone to UTC+7 (Asia/Jakarta / WIB)
os.environ["TZ"] = "Asia/Jakarta"
try:
    time.tzset()
except Exception:
    pass
import json
import socket
import struct
import urllib.parse
import threading
import subprocess
import concurrent.futures
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from speedtest_util import SpeedtestManager
from telegram_bot import TelegramBot
from webhook import WebhookManager
from device_namer import DeviceNamer

# Paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DEVICES_FILE = DATA_DIR / "devices.json"
WOL_TARGETS_FILE = DATA_DIR / "wol_targets.json"
HISTORY_FILE = DATA_DIR / "history.json"
CONFIG_FILE = DATA_DIR / "config.json"
SPEEDTEST_FILE = DATA_DIR / "speedtest.json"
DETECTED_NAMES_FILE = DATA_DIR / "detected_names.json"

# Default configuration
DEFAULT_CONFIG = {
    "port": 8080,
    "host": "0.0.0.0",
    "auto_scan_interval": 60,  # seconds, 0 = disabled
    "ping_timeout": 1.0,
    "scan_threads": 48,
    "webhook_url": "",
    "webhook_enabled": True,
    "telegram_token": "",
    "telegram_chat_id": "",
    "notify_power": True,
    "notify_new_devices": True,
    "notify_speedtest": True,
    "notify_wol": False,
    "enable_bot_commands": False,
    "auto_speedtest_interval_hours": 6
}

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception:
            pass
    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")

current_config = load_config()

def get_current_config():
    return current_config

# MAC OUI Vendor Prefix Lookup Table (Prefix in UPPERCASE without separators)
OUI_VENDORS = {
    "AC9E17": "Intel Corporate",
    "5C93A2": "Intel Corporate",
    "001AA0": "Intel Corporate",
    "00216A": "Intel Corporate",
    "0024D7": "Intel Corporate",
    "3C5282": "Intel Corporate",
    "4851B7": "Intel Corporate",
    "7CD1C3": "Intel Corporate",
    "8086F2": "Intel Corporate",
    "000393": "Apple",
    "000502": "Apple",
    "000A27": "Apple",
    "000A95": "Apple",
    "0010FA": "Apple",
    "001124": "Apple",
    "001451": "Apple",
    "0016CB": "Apple",
    "0017F2": "Apple",
    "001B63": "Apple",
    "001CB3": "Apple",
    "001E52": "Apple",
    "001EC2": "Apple",
    "0021E9": "Apple",
    "002241": "Apple",
    "002312": "Apple",
    "002500": "Apple",
    "00254B": "Apple",
    "002608": "Apple",
    "0026BB": "Apple",
    "00264A": "Apple",
    "F01898": "Apple",
    "F40F24": "Apple",
    "F437B7": "Apple",
    "F82793": "Apple",
    "FCFC48": "Apple",
    "A483E7": "Apple",
    "BC9FEF": "Apple",
    "C869CD": "Apple",
    "E0ACCB": "Apple",
    "D46195": "Huawei Technologies",
    "001E10": "Huawei Technologies",
    "002293": "Huawei Technologies",
    "002568": "Huawei Technologies",
    "00259E": "Huawei Technologies",
    "0819A6": "Huawei Technologies",
    "087A4C": "Huawei Technologies",
    "0C96BF": "Huawei Technologies",
    "104780": "Huawei Technologies",
    "200889": "Huawei Technologies",
    "342EB6": "Huawei Technologies",
    "4455B1": "Huawei Technologies",
    "48435A": "Huawei Technologies",
    "4846FB": "Huawei Technologies",
    "4C1FCC": "Huawei Technologies",
    "548998": "Huawei Technologies",
    "70723C": "Huawei Technologies",
    "78D752": "Huawei Technologies",
    "888603": "Huawei Technologies",
    "88CF98": "Huawei Technologies",
    "D02DB3": "Huawei Technologies",
    "E0247F": "Huawei Technologies",
    "F48E92": "Huawei Technologies",
    "0000F0": "Samsung Electronics",
    "0007AB": "Samsung Electronics",
    "001247": "Samsung Electronics",
    "001599": "Samsung Electronics",
    "00166B": "Samsung Electronics",
    "0018AF": "Samsung Electronics",
    "001A8A": "Samsung Electronics",
    "001D25": "Samsung Electronics",
    "0808C2": "Samsung Electronics",
    "14BB6E": "Samsung Electronics",
    "244B03": "Samsung Electronics",
    "34C3AC": "Samsung Electronics",
    "380B40": "Samsung Electronics",
    "44783E": "Samsung Electronics",
    "508569": "Samsung Electronics",
    "5492BE": "Samsung Electronics",
    "5CA39D": "Samsung Electronics",
    "684AE9": "Samsung Electronics",
    "78471D": "Samsung Electronics",
    "8425DB": "Samsung Electronics",
    "88329B": "Samsung Electronics",
    "9097F3": "Samsung Electronics",
    "A87C01": "Samsung Electronics",
    "B0C4E7": "Samsung Electronics",
    "BC4486": "Samsung Electronics",
    "C44202": "Samsung Electronics",
    "CCF735": "Samsung Electronics",
    "E47CF9": "Samsung Electronics",
    "F47B5E": "Samsung Electronics",
    "00EC0A": "Xiaomi Communications",
    "04CF8C": "Xiaomi Communications",
    "0C1DAF": "Xiaomi Communications",
    "14F65A": "Xiaomi Communications",
    "185936": "Xiaomi Communications",
    "286C07": "Xiaomi Communications",
    "34CE00": "Xiaomi Communications",
    "38A4ED": "Xiaomi Communications",
    "584498": "Xiaomi Communications",
    "640980": "Xiaomi Communications",
    "742344": "Xiaomi Communications",
    "7C49EB": "Xiaomi Communications",
    "88C397": "Xiaomi Communications",
    "8CBEBE": "Xiaomi Communications",
    "98FAE3": "Xiaomi Communications",
    "A086C6": "Xiaomi Communications",
    "ACC1EE": "Xiaomi Communications",
    "C40BCB": "Xiaomi Communications",
    "D4970B": "Xiaomi Communications",
    "E446DA": "Xiaomi Communications",
    "FC643A": "Xiaomi Communications",
    "000AEB": "TP-Link Technologies",
    "001478": "TP-Link Technologies",
    "0019E0": "TP-Link Technologies",
    "001D0F": "TP-Link Technologies",
    "002127": "TP-Link Technologies",
    "0023CD": "TP-Link Technologies",
    "002586": "TP-Link Technologies",
    "002719": "TP-Link Technologies",
    "14CC20": "TP-Link Technologies",
    "14CF92": "TP-Link Technologies",
    "1C3BF3": "TP-Link Technologies",
    "30B5C2": "TP-Link Technologies",
    "50C7BF": "TP-Link Technologies",
    "60E327": "TP-Link Technologies",
    "645601": "TP-Link Technologies",
    "6466B3": "TP-Link Technologies",
    "704F57": "TP-Link Technologies",
    "7883C6": "TP-Link Technologies",
    "8416F9": "TP-Link Technologies",
    "90F652": "TP-Link Technologies",
    "98DED0": "TP-Link Technologies",
    "A0F3C1": "TP-Link Technologies",
    "C04A00": "TP-Link Technologies",
    "D807B6": "TP-Link Technologies",
    "E848B8": "TP-Link Technologies",
    "EC086B": "TP-Link Technologies",
    "F4EC38": "TP-Link Technologies",
    "240AC4": "Espressif Systems (ESP IoT)",
    "2462AB": "Espressif Systems (ESP IoT)",
    "24B2DE": "Espressif Systems (ESP IoT)",
    "30AEA4": "Espressif Systems (ESP IoT)",
    "4022D8": "Espressif Systems (ESP IoT)",
    "409151": "Espressif Systems (ESP IoT)",
    "5443B2": "Espressif Systems (ESP IoT)",
    "5CCF7F": "Espressif Systems (ESP IoT)",
    "600194": "Espressif Systems (ESP IoT)",
    "68C63A": "Espressif Systems (ESP IoT)",
    "807D3A": "Espressif Systems (ESP IoT)",
    "84CCA8": "Espressif Systems (ESP IoT)",
    "94B555": "Espressif Systems (ESP IoT)",
    "A4CF12": "Espressif Systems (ESP IoT)",
    "A4E57C": "Espressif Systems (ESP IoT)",
    "AC67B2": "Espressif Systems (ESP IoT)",
    "B4E62D": "Espressif Systems (ESP IoT)",
    "BCDDC2": "Espressif Systems (ESP IoT)",
    "C44F33": "Espressif Systems (ESP IoT)",
    "C82B96": "Espressif Systems (ESP IoT)",
    "CC50E3": "Espressif Systems (ESP IoT)",
    "D8A01D": "Espressif Systems (ESP IoT)",
    "DC4F22": "Espressif Systems (ESP IoT)",
    "B827EB": "Raspberry Pi Foundation",
    "DCA632": "Raspberry Pi Foundation",
    "E45F01": "Raspberry Pi Foundation",
    "28CDC1": "Raspberry Pi Foundation",
    "000C6E": "ASUSTek Computer",
    "04D4C4": "ASUSTek Computer",
    "08606E": "ASUSTek Computer",
    "107B44": "ASUSTek Computer",
    "14DAE9": "ASUSTek Computer",
    "1831BF": "ASUSTek Computer",
    "2C4D54": "ASUSTek Computer",
    "38D547": "ASUSTek Computer",
    "50465D": "ASUSTek Computer",
    "74D02B": "ASUSTek Computer",
    "90E6BA": "ASUSTek Computer",
    "AC220B": "ASUSTek Computer",
    "BCEE7B": "ASUSTek Computer",
    "000740": "Realtek Semiconductor",
    "000CE7": "Realtek Semiconductor",
    "0014D1": "Realtek Semiconductor",
    "00E04C": "Realtek Semiconductor",
    "485D60": "Realtek Semiconductor",
    "525400": "QEMU Virtual NIC",
    "00155D": "Microsoft Hyper-V",
    "000C29": "VMware",
    "005056": "VMware",
    "080027": "Oracle VirtualBox",
    "001132": "Synology",
    "00089B": "QNAP Systems",
    "0418D6": "Ubiquiti Networks",
    "24A43C": "Ubiquiti Networks",
    "44D9E7": "Ubiquiti Networks",
    "68D79A": "Ubiquiti Networks",
    "788A20": "Ubiquiti Networks",
    "802AA8": "Ubiquiti Networks",
    "B4FBE4": "Ubiquiti Networks",
    "F09FC2": "Ubiquiti Networks"
}

def get_vendor_for_mac(mac: str) -> str:
    """Lookup manufacturer name by MAC address prefix."""
    if not mac:
        return "Unknown"
    cleaned = mac.replace(":", "").replace("-", "").upper()
    prefix = cleaned[:6]
    return OUI_VENDORS.get(prefix, "Generic / Unknown")


class SystemMonitor:
    """Collects CPU, Memory, Disk, Temperature, Power and Network bandwidth."""
    def __init__(self):
        self.last_cpu_time = 0
        self.last_cpu_idle = 0
        self.last_cpu_total = 0
        self.cpu_percent = 0.0

        self.last_net_time = 0
        self.last_rx_bytes = 0
        self.last_tx_bytes = 0
        self.rx_rate_kbps = 0.0
        self.tx_rate_kbps = 0.0

        self.net_interface = "enp2s0"
        self._init_network_iface()

    def _init_network_iface(self):
        try:
            res = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=2)
            for line in res.stdout.splitlines():
                parts = line.split()
                if "dev" in parts:
                    idx = parts.index("dev")
                    if idx + 1 < len(parts):
                        self.net_interface = parts[idx + 1]
                        break
        except Exception:
            pass

    def get_cpu_info(self):
        # Calculate CPU usage
        try:
            with open("/proc/stat") as f:
                first_line = f.readline()
            fields = [float(x) for x in first_line.split()[1:8]]
            idle = fields[3] + fields[4]
            total = sum(fields)

            now = time.time()
            if self.last_cpu_total > 0 and (now - self.last_cpu_time) >= 0.2:
                idle_delta = idle - self.last_cpu_idle
                total_delta = total - self.last_cpu_total
                if total_delta > 0:
                    self.cpu_percent = round(max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100)), 1)
            self.last_cpu_idle = idle
            self.last_cpu_total = total
            self.last_cpu_time = now
        except Exception:
            pass

        # CPU Model and Cores
        model = "Intel Processor"
        cores = 2
        try:
            with open("/proc/cpuinfo") as f:
                core_count = 0
                for line in f:
                    if line.startswith("model name"):
                        model = line.split(":", 1)[1].strip()
                    elif line.startswith("processor"):
                        core_count += 1
                if core_count > 0:
                    cores = core_count
        except Exception:
            pass

        # Load average
        load1, load5, load15 = os.getloadavg()

        # Temperature
        temp_c = None
        thermal_path = Path("/sys/class/thermal")
        if thermal_path.exists():
            for tz in sorted(thermal_path.glob("thermal_zone*")):
                try:
                    type_file = tz / "type"
                    temp_file = tz / "temp"
                    if temp_file.exists():
                        t_type = type_file.read_text().strip() if type_file.exists() else ""
                        raw = int(temp_file.read_text().strip())
                        val = round(raw / 1000.0, 1)
                        if val > 0:
                            if "pkg" in t_type.lower() or "acpi" in t_type.lower() or temp_c is None:
                                temp_c = val
                                if "pkg" in t_type.lower():
                                    break
                except Exception:
                    continue

        return {
            "usage_percent": self.cpu_percent,
            "model": model,
            "cores": cores,
            "temperature_c": temp_c,
            "load_avg": [round(load1, 2), round(load5, 2), round(load15, 2)]
        }

    def get_mem_info(self):
        mem = {}
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        mem[key] = int(val) * 1024  # bytes

            total = mem.get("MemTotal", 1)
            avail = mem.get("MemAvailable", mem.get("MemFree", 0))
            used = total - avail
            percent = round((used / total) * 100, 1)

            swap_total = mem.get("SwapTotal", 0)
            swap_free = mem.get("SwapFree", 0)
            swap_used = swap_total - swap_free
            swap_percent = round((swap_used / swap_total * 100), 1) if swap_total > 0 else 0

            return {
                "total_bytes": total,
                "used_bytes": used,
                "available_bytes": avail,
                "percent": percent,
                "swap_total": swap_total,
                "swap_used": swap_used,
                "swap_percent": swap_percent
            }
        except Exception:
            return {"total_bytes": 0, "used_bytes": 0, "percent": 0}

    def get_disk_info(self):
        try:
            target_path = "/app/data" if os.path.exists("/app/data") else (str(DATA_DIR) if DATA_DIR.exists() else "/")
            st = os.statvfs(target_path)
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - free
            percent = round((used / total) * 100, 1) if total > 0 else 0
            return {
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "percent": percent
            }
        except Exception:
            return {"total_bytes": 0, "used_bytes": 0, "free_bytes": 0, "percent": 0}

    def get_power_info(self):
        info = {
            "has_battery": False,
            "ac_connected": True,
            "capacity": 100,
            "status": "AC Power"
        }
        ac_file = Path("/sys/class/power_supply/AC0/online")
        bat_dir = Path("/sys/class/power_supply/BAT0")

        if ac_file.exists():
            try:
                info["ac_connected"] = (ac_file.read_text().strip() == "1")
            except Exception:
                pass

        if bat_dir.exists():
            info["has_battery"] = True
            try:
                cap_file = bat_dir / "capacity"
                stat_file = bat_dir / "status"
                if cap_file.exists():
                    info["capacity"] = int(cap_file.read_text().strip())
                if stat_file.exists():
                    info["status"] = stat_file.read_text().strip()
            except Exception:
                pass
        return info

    def get_network_rates(self):
        rx_bytes = 0
        tx_bytes = 0
        try:
            with open("/proc/net/dev") as f:
                for line in f:
                    if self.net_interface in line:
                        parts = line.split(":", 1)[1].split()
                        rx_bytes = int(parts[0])
                        tx_bytes = int(parts[8])
                        break

            now = time.time()
            if self.last_net_time > 0:
                dt = now - self.last_net_time
                if dt >= 0.5:
                    self.rx_rate_kbps = round((rx_bytes - self.last_rx_bytes) / dt / 1024.0, 2)
                    self.tx_rate_kbps = round((tx_bytes - self.last_tx_bytes) / dt / 1024.0, 2)
                    self.last_net_time = now
                    self.last_rx_bytes = rx_bytes
                    self.last_tx_bytes = tx_bytes
            else:
                self.last_net_time = now
                self.last_rx_bytes = rx_bytes
                self.last_tx_bytes = tx_bytes
        except Exception:
            pass

        return {
            "interface": self.net_interface,
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes,
            "rx_rate_kbps": max(0.0, self.rx_rate_kbps),
            "tx_rate_kbps": max(0.0, self.tx_rate_kbps)
        }

    def get_uptime_info(self):
        try:
            with open("/proc/uptime") as f:
                uptime_seconds = float(f.readline().split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            mins = int((uptime_seconds % 3600) // 60)
            formatted = f"{days} hari, {hours} jam, {mins} menit" if days > 0 else f"{hours} jam, {mins} menit"
            return {
                "uptime_seconds": int(uptime_seconds),
                "formatted": formatted
            }
        except Exception:
            return {"uptime_seconds": 0, "formatted": "N/A"}

    def get_docker_summary(self):
        """Check for docker containers via /var/run/docker.sock or CLI."""
        containers = []
        sock_path = "/var/run/docker.sock"
        if os.path.exists(sock_path):
            try:
                import http.client
                class UnixSocketHTTPConnection(http.client.HTTPConnection):
                    def __init__(self, s_path):
                        super().__init__('localhost')
                        self.s_path = s_path
                    def connect(self):
                        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        self.sock.settimeout(2.0)
                        self.sock.connect(self.s_path)

                conn = UnixSocketHTTPConnection(sock_path)
                conn.request("GET", "/containers/json")
                res = conn.getresponse()
                if res.status == 200:
                    raw_data = json.loads(res.read().decode('utf-8'))
                    for c in raw_data:
                        names = c.get("Names", [])
                        name = names[0].lstrip("/") if names else c.get("Id", "")[:12]
                        ports_list = []
                        for p in c.get("Ports", []):
                            ip = p.get("IP", "")
                            pub = p.get("PublicPort", "")
                            priv = p.get("PrivatePort", "")
                            ptype = p.get("Type", "tcp")
                            if pub:
                                ports_list.append(f"{ip + ':' if ip else ''}{pub}->{priv}/{ptype}")
                            elif priv:
                                ports_list.append(f"{priv}/{ptype}")
                        containers.append({
                            "id": c.get("Id", "")[:12],
                            "image": c.get("Image", ""),
                            "name": name,
                            "status": c.get("Status", ""),
                            "ports": ", ".join(ports_list)
                        })
                    return containers
            except Exception:
                pass

        try:
            res = subprocess.run(
                ["docker", "ps", "--format", "{{.ID}}|{{.Image}}|{{.Names}}|{{.Status}}|{{.Ports}}"],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    parts = line.split("|")
                    if len(parts) >= 4:
                        containers.append({
                            "id": parts[0],
                            "image": parts[1],
                            "name": parts[2],
                            "status": parts[3],
                            "ports": parts[4] if len(parts) > 4 else ""
                        })
        except Exception:
            pass
        return containers

    def snapshot(self):
        return {
            "timestamp": int(time.time()),
            "local_time": time.strftime("%Y-%m-%d %H:%M:%S WIB"),
            "timezone": "Asia/Jakarta (UTC+7)",
            "cpu": self.get_cpu_info(),
            "memory": self.get_mem_info(),
            "disk": self.get_disk_info(),
            "power": self.get_power_info(),
            "network": self.get_network_rates(),
            "uptime": self.get_uptime_info(),
            "hostname": socket.gethostname(),
            "docker": self.get_docker_summary()
        }


class NetworkScanner:
    """Discovers devices on home network via parallel ping + ARP cache resolution and friendly name discovery."""
    def __init__(self, data_file: Path, history_file: Path, device_namer: DeviceNamer = None):
        self.data_file = data_file
        self.history_file = history_file
        self.device_namer = device_namer
        self.devices = self._load_devices()
        self.history = self._load_history()
        self.is_scanning = False
        self.last_scan_time = 0
        self.lock = threading.Lock()

    def _load_devices(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_devices(self):
        try:
            with open(self.data_file, "w") as f:
                json.dump(self.devices, f, indent=2)
        except Exception as e:
            print(f"Error saving devices: {e}")

    def _load_history(self):
        if self.history_file.exists():
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def log_event(self, event_type: str, message: str, details: dict = None):
        with self.lock:
            entry = {
                "timestamp": int(time.time()),
                "time_str": time.strftime("%Y-%m-%d %H:%M:%S WIB"),
                "type": event_type,
                "message": message,
                "details": details or {}
            }
            self.history.insert(0, entry)
            # Keep last 200 events
            self.history = self.history[:200]
            try:
                with open(self.history_file, "w") as f:
                    json.dump(self.history, f, indent=2)
            except Exception:
                pass

    def get_network_info(self):
        """Detect local IP, subnet, gateway, broadcast, tailscale."""
        gateway = None
        iface = "enp2s0"
        try:
            res = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=2)
            for line in res.stdout.splitlines():
                parts = line.split()
                if "default" in parts and "via" in parts:
                    gateway = parts[parts.index("via") + 1]
                if "dev" in parts:
                    iface = parts[parts.index("dev") + 1]
        except Exception:
            pass

        local_ip = "192.168.1.11"
        subnet_cidr = "192.168.1.0/24"
        broadcast = "192.168.1.255"

        if iface:
            try:
                res = subprocess.run(["ip", "-o", "-4", "addr", "show", iface], capture_output=True, text=True, timeout=2)
                for line in res.stdout.splitlines():
                    parts = line.split()
                    if "inet" in parts:
                        idx = parts.index("inet")
                        ip_cidr = parts[idx + 1]
                        local_ip = ip_cidr.split("/")[0]
                        cidr = ip_cidr.split("/")[1] if "/" in ip_cidr else "24"
                        base = ".".join(local_ip.split(".")[:3])
                        subnet_cidr = f"{base}.0/{cidr}"
                    if "brd" in parts:
                        broadcast = parts[parts.index("brd") + 1]
            except Exception:
                pass

        # Tailscale IP
        tailscale_ip = None
        try:
            res = subprocess.run(["ip", "-o", "-4", "addr", "show", "tailscale0"], capture_output=True, text=True, timeout=2)
            for line in res.stdout.splitlines():
                parts = line.split()
                if "inet" in parts:
                    tailscale_ip = parts[parts.index("inet") + 1].split("/")[0]
        except Exception:
            pass

        return {
            "local_ip": local_ip,
            "subnet": subnet_cidr,
            "gateway": gateway,
            "broadcast": broadcast,
            "interface": iface,
            "tailscale_ip": tailscale_ip
        }

    def _ping_single(self, ip: str, timeout: float = 1.0):
        """Pings a single IP, extracts latency."""
        try:
            p = subprocess.run(
                ["ping", "-c", "1", f"-W", str(int(timeout)), "-q", ip],
                capture_output=True, text=True, timeout=timeout + 0.5
            )
            if p.returncode == 0:
                latency = None
                for line in p.stdout.splitlines():
                    if "rtt min/avg/max/mdev" in line:
                        parts = line.split("=")[1].strip().split("/")
                        if len(parts) >= 2:
                            latency = round(float(parts[1]), 2)
                            break
                    elif "time=" in line:
                        idx = line.find("time=")
                        part = line[idx+5:].split()[0]
                        latency = round(float(part), 2)
                        break
                return ip, True, latency
            return ip, False, None
        except Exception:
            return ip, False, None

    def _read_arp_table(self):
        arp_map = {}
        # Read from /proc/net/arp
        try:
            with open("/proc/net/arp") as f:
                for line in f.readlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 6:
                        ip, hw, flags, mac, mask, dev = parts[:6]
                        if mac and mac != "00:00:00:00:00:00" and len(mac) == 17:
                            arp_map[ip] = mac.upper()
        except Exception:
            pass

        # Also supplement with `ip neigh`
        try:
            res = subprocess.run(["ip", "neigh"], capture_output=True, text=True, timeout=2)
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and "lladdr" in parts:
                    ip = parts[0]
                    mac = parts[parts.index("lladdr") + 1].upper()
                    if len(mac) == 17:
                        arp_map[ip] = mac
        except Exception:
            pass

        return arp_map

    def _resolve_hostname(self, ip: str):
        # Quick non-blocking / short-timeout check without mutating global socket timeout
        try:
            if not hasattr(self, "_dns_pool"):
                self._dns_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
            fut = self._dns_pool.submit(socket.gethostbyaddr, ip)
            return fut.result(timeout=0.4)[0]
        except Exception:
            return ""

    def scan(self, custom_subnet: str = None):
        """Perform concurrent ping sweep of the subnet."""
        if self.is_scanning:
            return False, "Pemindaian sedang berjalan"

        self.is_scanning = True
        try:
            net_info = self.get_network_info()
            subnet = custom_subnet or net_info["subnet"]
            base_ip = ".".join(subnet.split("/")[0].split(".")[:3])
            gateway_ip = net_info["gateway"]
            local_ip = net_info["local_ip"]

            target_ips = [f"{base_ip}.{i}" for i in range(1, 255)]

            # Concurrent ping sweep
            ping_results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=64) as executor:
                future_to_ip = {executor.submit(self._ping_single, ip, 0.5): ip for ip in target_ips}
                for future in concurrent.futures.as_completed(future_to_ip):
                    ip, is_online, latency = future.result()
                    if is_online:
                        ping_results[ip] = latency

            # Get ARP table right after ping sweep
            arp_table = self._read_arp_table()

            # Host itself MAC address
            host_mac = None
            try:
                with open(f"/sys/class/net/{net_info['interface']}/address") as f:
                    host_mac = f.read().strip().upper()
            except Exception:
                pass

            now = int(time.time())
            
            # Prepare updates outside lock
            all_found_ips = set(list(ping_results.keys()) + list(arp_table.keys()))
            new_entries = {}
            new_events = []

            # Snapshot existing devices for merging
            with self.lock:
                current_devices = dict(self.devices)

            # Query device_namer for active discovery (mDNS, SSDP, NetBIOS, Reverse DNS)
            if self.device_namer:
                try:
                    self.device_namer.scan_active(list(all_found_ips))
                except Exception as e:
                    print(f"Device namer scan error: {e}")

            for ip in all_found_ips:
                # Ignore docker internal IPs, loopback, and IPv6 link-local
                if ":" in ip or ip.startswith("172.") or ip.startswith("127."):
                    continue

                mac = arp_table.get(ip, "")
                if ip == local_ip and host_mac:
                    mac = host_mac

                key = mac if mac else f"IP_{ip}"
                existing = current_devices.get(key, {})

                is_online = (ip in ping_results) or (ip == local_ip)
                latency = ping_results.get(ip, 0.1 if ip == local_ip else None)

                # Hostname lookup (only if online and not known)
                hostname = existing.get("hostname", "")
                if is_online and not hostname:
                    hostname = self._resolve_hostname(ip)

                vendor = get_vendor_for_mac(mac)
                is_router = (ip == gateway_ip)
                is_host = (ip == local_ip)

                # Resolve friendly detected name (from mDNS/SSDP/NetBIOS/DHCP)
                detected_name = ""
                if self.device_namer:
                    detected_name = self.device_namer.get_name(ip)
                if not detected_name:
                    detected_name = existing.get("detected_name", "")
                if not detected_name:
                    if is_host:
                        detected_name = f"Home Server ({hostname or 'Laptop'})"
                    elif is_router:
                        detected_name = "Router Huawei (Gateway)" if "huawei" in vendor.lower() else "Router Gateway"

                device_entry = {
                    "id": key,
                    "ip": ip,
                    "mac": mac,
                    "vendor": vendor,
                    "hostname": hostname,
                    "detected_name": detected_name,
                    "custom_name": existing.get("custom_name", ""),
                    "notes": existing.get("notes", ""),
                    "is_online": is_online,
                    "latency_ms": latency,
                    "is_router": is_router,
                    "is_host": is_host,
                    "first_seen": existing.get("first_seen", now),
                    "last_seen": now if is_online else existing.get("last_seen", now)
                }

                if key not in current_devices:
                    name_display = device_entry["custom_name"] or detected_name or hostname or vendor
                    new_events.append((
                        "device_discovered",
                        f"Perangkat baru ditemukan: {ip} ({name_display})",
                        {"ip": ip, "mac": mac, "vendor": vendor, "name": name_display}
                    ))

                new_entries[key] = device_entry

            # Atomic commit to self.devices
            with self.lock:
                # Mark previous not found as offline
                for k, dev in self.devices.items():
                    if k not in new_entries:
                        dev["is_online"] = False
                self.devices.update(new_entries)
                self._save_devices()
                self.last_scan_time = now

            for ev_type, msg, det in new_events:
                self.log_event(ev_type, msg, det)
                if ev_type == "device_discovered":
                    try:
                        time_str = time.strftime("%Y-%m-%d %H:%M:%S WIB")
                        ip_d = det.get("ip", "")
                        mac_d = det.get("mac", "")
                        ven_d = det.get("vendor", "")
                        name_d = det.get("name", "")
                        if 'webhook_manager' in globals():
                            webhook_manager.notify_new_device(ip_d, mac_d, ven_d, "", time_str)
                            webhook_manager.notify_new_device(ip_d, mac_d, ven_d, name_d, time_str)
                        if 'telegram_bot' in globals():
                            telegram_bot.notify_new_device(ip_d, mac_d, ven_d, "", time_str)
                            telegram_bot.notify_new_device(ip_d, mac_d, ven_d, name_d, time_str)
                    except Exception as e:
                        print(f"Error sending new device notification: {e}")

            return True, f"Pemindaian selesai: {len(ping_results)} perangkat aktif ditemukan"
        finally:
            self.is_scanning = False

    def update_device(self, key: str, custom_name: str, notes: str):
        with self.lock:
            if key in self.devices:
                self.devices[key]["custom_name"] = custom_name.strip()
                self.devices[key]["notes"] = notes.strip()
                self._save_devices()
                return True
            return False

    def list_devices(self):
        with self.lock:
            # Dynamically update detected_name if device_namer has a newer name
            if self.device_namer:
                for dev in self.devices.values():
                    ip = dev.get("ip", "")
                    if ip:
                        cur_det = dev.get("detected_name", "")
                        new_det = self.device_namer.get_name(ip)
                        if new_det and new_det != cur_det:
                            dev["detected_name"] = new_det
            dev_list = list(self.devices.values())
            # Sort: Host first, Router second, then Online devices, then by IP
            def sort_key(d):
                ip_parts = [int(p) if p.isdigit() else 0 for p in d.get("ip", "0.0.0.0").split(".")]
                return (
                    0 if d.get("is_host") else (1 if d.get("is_router") else 2),
                    0 if d.get("is_online") else 1,
                    ip_parts
                )
            return sorted(dev_list, key=sort_key)


class WolManager:
    """Manages saved Wake-on-LAN target computers and sends magic packets."""
    def __init__(self, targets_file: Path, scanner: NetworkScanner):
        self.targets_file = targets_file
        self.scanner = scanner
        self.targets = self._load_targets()
        self.lock = threading.Lock()

    def _load_targets(self):
        if self.targets_file.exists():
            try:
                with open(self.targets_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_targets(self):
        try:
            with open(self.targets_file, "w") as f:
                json.dump(self.targets, f, indent=2)
        except Exception as e:
            print(f"Error saving targets: {e}")

    def list_targets(self):
        with self.lock:
            return list(self.targets)

    def add_target(self, name: str, mac: str, ip: str = "", broadcast_ip: str = "192.168.1.255", port: int = 9, notes: str = ""):
        cleaned_mac = mac.replace(":", "").replace("-", "").upper()
        if len(cleaned_mac) != 12:
            raise ValueError("Format MAC address tidak valid (contoh: AA:BB:CC:DD:EE:FF)")

        formatted_mac = ":".join([cleaned_mac[i:i+2] for i in range(0, 12, 2)])
        with self.lock:
            # Check existing
            for t in self.targets:
                if t["mac"].upper() == formatted_mac:
                    t["name"] = name
                    t["ip"] = ip
                    t["broadcast_ip"] = broadcast_ip
                    t["port"] = port
                    t["notes"] = notes
                    self._save_targets()
                    return t

            target = {
                "id": f"wol_{int(time.time()*1000)}",
                "name": name,
                "mac": formatted_mac,
                "ip": ip,
                "broadcast_ip": broadcast_ip or "192.168.1.255",
                "port": int(port or 9),
                "notes": notes,
                "created_at": int(time.time()),
                "last_woken": None
            }
            self.targets.append(target)
            self._save_targets()
            return target

    def delete_target(self, target_id: str):
        with self.lock:
            original_len = len(self.targets)
            self.targets = [t for t in self.targets if t.get("id") != target_id and t.get("mac") != target_id]
            if len(self.targets) < original_len:
                self._save_targets()
                return True
            return False

    def send_magic_packet(self, mac: str, broadcast_ip: str = "192.168.1.255", port: int = 9, target_ip: str = None, target_name: str = None):
        """Constructs and broadcasts Wake-on-LAN magic packet."""
        cleaned_mac = mac.replace(":", "").replace("-", "").replace(".", "").upper()
        if len(cleaned_mac) != 12:
            raise ValueError("Format MAC address tidak valid. Harus 12 karakter hex.")

        mac_bytes = bytes.fromhex(cleaned_mac)
        magic_packet = b"\xff" * 6 + mac_bytes * 16

        destinations = [
            (broadcast_ip, port),
            (broadcast_ip, 7 if port == 9 else 9),
            ("255.255.255.255", port)
        ]

        sent_count = 0
        for dest, p in destinations:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    # Send packet twice with slight pause to ensure delivery
                    for _ in range(2):
                        s.sendto(magic_packet, (dest, p))
                        time.sleep(0.02)
                sent_count += 1
            except Exception as e:
                print(f"Warning WoL send error to {dest}:{p}: {e}")

        # Update last_woken
        now = int(time.time())
        with self.lock:
            for t in self.targets:
                if t["mac"].replace(":", "").upper() == cleaned_mac:
                    t["last_woken"] = now
            self._save_targets()

        # Log event
        display_name = target_name or mac
        self.scanner.log_event(
            "wol_triggered",
            f"Sinyal Wake-on-LAN dikirim ke {display_name} ({mac})",
            {"mac": mac, "target_ip": target_ip, "broadcast_ip": broadcast_ip, "port": port}
        )

        if 'webhook_manager' in globals():
            try:
                webhook_manager.notify_wol_triggered(display_name, mac, target_ip or "")
            except Exception:
                pass

        return True


# Global instances
device_namer = DeviceNamer(DETECTED_NAMES_FILE)
device_namer.start_passive_listener()
system_monitor = SystemMonitor()
network_scanner = NetworkScanner(DEVICES_FILE, HISTORY_FILE, device_namer=device_namer)
wol_manager = WolManager(WOL_TARGETS_FILE, network_scanner)
speedtest_manager = SpeedtestManager(SPEEDTEST_FILE)
webhook_manager = WebhookManager(config_getter=get_current_config)
telegram_bot = TelegramBot(
    config_getter=get_current_config,
    system_monitor=system_monitor,
    network_scanner=network_scanner,
    wol_manager=wol_manager,
    speedtest_manager=speedtest_manager
)


class BackgroundWorker(threading.Thread):
    """Periodically refreshes monitor stats, runs auto-scans, detects power outage, and triggers auto-speedtests."""
    def __init__(self, interval: int = 60):
        super().__init__(daemon=True)
        self.interval = interval
        self.running = True
        self.last_ac_state = None
        self.last_speedtest_time = time.time()

    def run(self):
        # Initial scan on startup
        time.sleep(2)
        try:
            print("Memulai pemindaian jaringan awal...")
            network_scanner.scan()
            print("Pemindaian awal selesai.")
        except Exception as e:
            print(f"Error during initial scan: {e}")

        # Start Telegram bot polling (if enabled)
        telegram_bot.start_polling()

        scan_counter = 0
        while self.running:
            time.sleep(2)
            scan_counter += 2

            # 1. Power outage detector
            try:
                p = system_monitor.get_power_info()
                curr_ac = p.get("ac_connected", True)
                cap = p.get("capacity", 100)
                t_str = time.strftime("%Y-%m-%d %H:%M:%S WIB")

                if self.last_ac_state is not None:
                    if self.last_ac_state is True and curr_ac is False:
                        network_scanner.log_event("power_outage", f"⚠️ LISTRIK RUMAH PADAM! Server beralih ke baterai ({cap}%).", {"battery": cap})
                        webhook_manager.notify_power_outage(cap, t_str)
                        telegram_bot.notify_power_outage(cap, t_str)
                    elif self.last_ac_state is False and curr_ac is True:
                        network_scanner.log_event("power_restored", f"✅ Listrik rumah sudah menyala kembali (Baterai {cap}%).", {"battery": cap})
                        webhook_manager.notify_power_restored(cap, t_str)
                        telegram_bot.notify_power_restored(cap, t_str)
                self.last_ac_state = curr_ac
            except Exception as e:
                pass

            # 2. Periodic network scan
            cfg = get_current_config()
            auto_scan_interval = cfg.get("auto_scan_interval", 60)
            if auto_scan_interval > 0 and scan_counter >= auto_scan_interval:
                scan_counter = 0
                if not network_scanner.is_scanning:
                    try:
                        network_scanner.scan()
                    except Exception:
                        pass

            # 3. Periodic auto-speedtest
            hours = cfg.get("auto_speedtest_interval_hours", 6)
            if hours > 0:
                interval_secs = hours * 3600
                if (time.time() - self.last_speedtest_time) >= interval_secs:
                    self.last_speedtest_time = time.time()
                    try:
                        ok, msg, res = speedtest_manager.run_test(triggered_by="auto_scheduler")
                        if ok and res and cfg.get("notify_speedtest", True):
                            telegram_bot.notify_speedtest_result(res)
                    except Exception:
                        pass


class RequestHandler(SimpleHTTPRequestHandler):
    """HTTP Request handler supporting REST API and modern static SPA."""
    timeout = 30

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        if not getattr(self, "_is_json_response", False):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def _send_json(self, data, status: int = 200):
        self._is_json_response = True
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # API Endpoints
        if path == "/api/system":
            self._send_json(system_monitor.snapshot())
            return

        elif path == "/api/network/info":
            self._send_json(network_scanner.get_network_info())
            return

        elif path == "/api/network/devices":
            devices = network_scanner.list_devices()
            online_count = sum(1 for d in devices if d.get("is_online"))
            self._send_json({
                "devices": devices,
                "total": len(devices),
                "online": online_count,
                "offline": len(devices) - online_count,
                "is_scanning": network_scanner.is_scanning,
                "last_scan_time": network_scanner.last_scan_time
            })
            return

        elif path == "/api/wol/targets":
            targets = wol_manager.list_targets()
            # Enrich with online status from current device list
            dev_map = {d.get("mac", "").upper(): d for d in network_scanner.list_devices()}
            enriched = []
            for t in targets:
                item = dict(t)
                mac_key = t.get("mac", "").upper()
                if mac_key in dev_map:
                    item["is_online"] = dev_map[mac_key].get("is_online", False)
                    item["latency_ms"] = dev_map[mac_key].get("latency_ms")
                    if not item.get("ip"):
                        item["ip"] = dev_map[mac_key].get("ip")
                else:
                    item["is_online"] = False
                    item["latency_ms"] = None
                enriched.append(item)
            self._send_json(enriched)
            return

        elif path == "/api/wol/check":
            # Fast ping check to see if target IP is now online
            ip = query.get("ip", [""])[0]
            if not ip:
                self._send_json({"error": "Parameter ip dibutuhkan"}, 400)
                return
            ip, is_online, latency = network_scanner._ping_single(ip, timeout=1.0)
            self._send_json({
                "ip": ip,
                "is_online": is_online,
                "latency_ms": latency
            })
            return

        elif path == "/api/history":
            self._send_json(network_scanner.history)
            return

        elif path == "/api/config":
            cfg = dict(current_config)
            tok = cfg.get("telegram_token", "")
            if len(tok) > 8:
                cfg["telegram_token_masked"] = tok[:4] + "••••" + tok[-4:]
            else:
                cfg["telegram_token_masked"] = tok
            cfg["is_telegram_configured"] = bool(tok and cfg.get("telegram_chat_id"))
            self._send_json(cfg)
            return

        elif path == "/api/speedtest/history":
            self._send_json({
                "is_running": speedtest_manager.is_running,
                "latest": speedtest_manager.get_latest(),
                "history": speedtest_manager.get_history()
            })
            return

        # Fallback to static files
        if path == "/" or not (STATIC_DIR / path.lstrip("/")).exists():
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            body = self._read_json()
        except Exception as e:
            self._send_json({"error": f"JSON body tidak valid: {e}"}, 400)
            return

        if path == "/api/network/scan":
            custom_subnet = body.get("subnet")
            # Run scan in background thread if not already running
            if network_scanner.is_scanning:
                self._send_json({"status": "running", "message": "Pemindaian sudah sedang berjalan"})
                return

            def run_scan():
                network_scanner.scan(custom_subnet)

            threading.Thread(target=run_scan, daemon=True).start()
            self._send_json({"status": "started", "message": "Pemindaian jaringan dimulai"})
            return

        elif path == "/api/network/device/rename":
            key = body.get("id") or body.get("mac")
            custom_name = body.get("custom_name", "")
            notes = body.get("notes", "")
            if not key:
                self._send_json({"error": "ID atau MAC perangkat dibutuhkan"}, 400)
                return

            success = network_scanner.update_device(key, custom_name, notes)
            if success:
                self._send_json({"success": True, "message": "Nama perangkat berhasil diperbarui"})
            else:
                self._send_json({"error": "Perangkat tidak ditemukan"}, 404)
            return

        elif path == "/api/wol/targets":
            name = body.get("name", "Komputer")
            mac = body.get("mac", "")
            ip = body.get("ip", "")
            broadcast_ip = body.get("broadcast_ip", "192.168.1.255")
            port = body.get("port", 9)
            notes = body.get("notes", "")

            try:
                target = wol_manager.add_target(name, mac, ip, broadcast_ip, port, notes)
                self._send_json({"success": True, "target": target})
            except ValueError as e:
                self._send_json({"error": str(e)}, 400)
            return

        elif path == "/api/wol/wake":
            mac = body.get("mac", "")
            broadcast_ip = body.get("broadcast_ip", "192.168.1.255")
            port = int(body.get("port", 9))
            target_ip = body.get("ip", "")
            target_name = body.get("name", "")

            try:
                wol_manager.send_magic_packet(
                    mac=mac,
                    broadcast_ip=broadcast_ip,
                    port=port,
                    target_ip=target_ip,
                    target_name=target_name
                )
                self._send_json({
                    "success": True,
                    "message": f"Magic Packet berhasil dikirim ke {target_name or mac} ({mac})"
                })
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return

        elif path == "/api/config":
            for k in [
                "webhook_url", "webhook_enabled", "notify_wol",
                "telegram_token", "telegram_chat_id", "notify_power",
                "notify_new_devices", "notify_speedtest", "enable_bot_commands",
                "auto_speedtest_interval_hours", "auto_scan_interval"
            ]:
                if k in body:
                    current_config[k] = body[k]
            save_config(current_config)
            self._send_json({"success": True, "message": "Pengaturan berhasil disimpan"})
            return

        elif path == "/api/webhook/test":
            test_url = body.get("url") or current_config.get("webhook_url")
            ok, msg = webhook_manager.test_webhook(test_url)
            if ok:
                self._send_json({"success": True, "message": f"Pesan tes berhasil dikirim ke Webhook! ({msg})"})
            else:
                self._send_json({"error": f"Gagal mengirim ke Webhook: {msg}"}, 400)
            return

        elif path == "/api/telegram/test":
            token = body.get("token") or current_config.get("telegram_token")
            chat_id = body.get("chat_id") or current_config.get("telegram_chat_id")
            ok, msg = telegram_bot.test_connection(token, chat_id)
            if ok:
                self._send_json({"success": True, "message": msg})
            else:
                self._send_json({"error": msg}, 400)
            return

        elif path == "/api/speedtest/run":
            if speedtest_manager.is_running:
                self._send_json({"status": "running", "message": "Pengujian kecepatan sedang berjalan"})
                return

            def do_speedtest():
                ok, msg, res = speedtest_manager.run_test(triggered_by="web_dashboard")
                if ok and res:
                    webhook_manager.notify_speedtest(res)
                    if current_config.get("notify_speedtest", True):
                        telegram_bot.notify_speedtest_result(res)

            threading.Thread(target=do_speedtest, daemon=True).start()
            self._send_json({"status": "started", "message": "Pengujian kecepatan internet dimulai"})
            return

        self._send_json({"error": "Endpoint tidak ditemukan"}, 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/wol/targets":
            target_id = query.get("id", [""])[0]
            if not target_id:
                self._send_json({"error": "Parameter id dibutuhkan"}, 400)
                return
            success = wol_manager.delete_target(target_id)
            self._send_json({"success": success})
            return

        self._send_json({"error": "Endpoint tidak ditemukan"}, 404)


class HomeMonitorHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 64


def main():
    port = int(os.environ.get("PORT", DEFAULT_CONFIG["port"]))
    host = os.environ.get("HOST", DEFAULT_CONFIG["host"])

    print(f"==================================================")
    print(f"   🏠 HomeMonitor Server & Network Dashboard     ")
    print(f"==================================================")
    print(f"[*] Berjalan pada http://{host}:{port}")
    
    net = network_scanner.get_network_info()
    if net.get("local_ip"):
        print(f"[*] Akses LAN      : http://{net['local_ip']}:{port}")
    if net.get("tailscale_ip"):
        print(f"[*] Akses Tailscale: http://{net['tailscale_ip']}:{port}")
    print(f"[*] Antarmuka      : {net.get('interface')} ({net.get('subnet')})")
    print(f"[*] Gateway        : {net.get('gateway')}")
    print(f"==================================================")

    # Start background auto-scanner worker
    worker = BackgroundWorker(interval=DEFAULT_CONFIG["auto_scan_interval"])
    worker.start()

    server = HomeMonitorHTTPServer((host, port), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Menghentikan server HomeMonitor...")
        server.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
