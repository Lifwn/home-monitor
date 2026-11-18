"""
Device Name & Friendly Hostname Resolver for HomeMonitor
Discovers real user-assigned device names (e.g. "Alif’s MacBook Air", "Poco F6", "Android TV")
via:
1. mDNS (Multicast DNS / Bonjour / Avahi) - PTR instance names & TXT records
2. SSDP / UPnP device discovery - friendlyName & modelName
3. NetBIOS Node Status (Windows / Samba / NAS) on UDP 137
4. Reverse DNS (DHCP hostnames)
5. Continuous passive listener on UDP 5353 (mDNS) & UDP 1900 (SSDP)
Zero external dependencies (pure Python 3).
"""

import os
import re
import time
import json
import socket
import struct
import threading
import concurrent.futures
import urllib.request
from pathlib import Path

# Common brand / device keywords for scoring friendly names
DEVICE_KEYWORDS = [
    'macbook', 'iphone', 'ipad', 'apple', 'poco', 'redmi', 'xiaomi',
    'galaxy', 'samsung', 'pixel', 'android', 'tv', 'smart-tv', 'cast',
    'desktop', 'laptop', 'huawei', 'oppo', 'vivo', 'realme', 'roku',
    'synology', 'qnap', 'nas', 'printer', 'playstation', 'xbox', 'nintendo',
    'windows', 'thinkpad', 'dell', 'hp', 'lenovo', 'asus', 'acer'
]

def parse_dns_name(data: bytes, offset: int):
    """Parses DNS domain name with pointer decompression."""
    parts = []
    visited = set()
    orig_offset = offset
    stepped = False
    
    while offset < len(data):
        length = data[offset]
        if length == 0:
            if not stepped:
                orig_offset = offset + 1
            break
        elif (length & 0xc0) == 0xc0:
            if offset + 1 >= len(data):
                break
            ptr = struct.unpack('>H', data[offset:offset+2])[0] & 0x3fff
            if not stepped:
                orig_offset = offset + 2
                stepped = True
            if ptr in visited or ptr >= len(data):
                break
            visited.add(ptr)
            offset = ptr
        else:
            offset += 1
            if offset + length > len(data):
                break
            parts.append(data[offset:offset+length].decode('utf-8', errors='ignore'))
            offset += length
            if not stepped:
                orig_offset = offset
    return '.'.join(parts), orig_offset


class DeviceNamer:
    def __init__(self, data_file: Path = None):
        self.data_file = data_file
        self.detected_names = {}
        self.lock = threading.Lock()
        self.running = False
        self.mdns_thread = None
        self.ssdp_thread = None

        if self.data_file and self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.detected_names = json.load(f)
            except Exception:
                self.detected_names = {}

    def _save(self):
        if not self.data_file:
            return
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.detected_names, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_name(self, ip: str) -> str:
        with self.lock:
            return self.detected_names.get(ip, "")

    def _score_name(self, name: str) -> int:
        """Scores name candidate. Higher score = better friendly device name."""
        if not name or len(name) < 2:
            return -100

        # Disqualify UUID, long hex hashes, or service instance identifiers
        # e.g. Smart-TV-0773b1faac4be96cea5dd1ee668ce1b6, 0773b1fa-ac4b-..., etc.
        if re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}', name):
            return -100
        if re.search(r'(?=[0-9a-fA-F]*[a-fA-F])(?=[0-9a-fA-F]*[0-9])[0-9a-fA-F]{12,}', name):
            return -100
        if re.search(r'[0-9a-fA-F]{16,}', name):
            return -100
        if name.startswith('_') or name.startswith('uuid:'):
            return -100

        score = 10
        # Possessive apostrophe (e.g. Alif’s MacBook Air) is highest quality
        if "’" in name or "'" in name:
            score += 60
        # Contains spaces (e.g. "Poco F6", "Android TV", "Smart TV")
        if " " in name:
            score += 30
        
        name_lower = name.lower()
        if any(k in name_lower for k in DEVICE_KEYWORDS):
            score += 40

        score += min(len(name), 20)
        return score

    def set_name(self, ip: str, name: str) -> bool:
        if not name or not ip:
            return False

        # Clean control characters
        clean = "".join(c for c in name if c.isprintable()).strip()
        if not clean or len(clean) < 2 or clean.endswith('.arpa') or clean == '_gateway':
            return False

        # Strip trailing .local or .lan
        if clean.endswith('.local'):
            clean = clean[:-6]
        if clean.endswith('.lan'):
            clean = clean[:-4]

        new_score = self._score_name(clean)
        if new_score < 0:
            return False

        with self.lock:
            existing = self.detected_names.get(ip, "")
            cur_score = self._score_name(existing) if existing else -1
            if new_score > cur_score or not existing:
                self.detected_names[ip] = clean
                self._save()
                return True
        return False

    def query_netbios(self, ip: str, timeout: float = 0.4) -> str:
        """Queries Windows/Samba/NAS machine name via NetBIOS on UDP 137."""
        query = b'\x80\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\x00\x00!\x00\x01'
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(timeout)
                s.sendto(query, (ip, 137))
                data, _ = s.recvfrom(1024)
                if len(data) > 57:
                    num_names = data[56]
                    for i in range(num_names):
                        name_bytes = data[57 + i*18 : 57 + i*18 + 15]
                        name = name_bytes.decode('ascii', errors='ignore').strip()
                        if name and not name.startswith('__') and not name.startswith('IS~'):
                            return name
        except Exception:
            pass
        return ""

    def query_reverse_dns(self, ip: str) -> str:
        """Queries local DNS for hostname without mutating global socket timeout."""
        try:
            if not hasattr(self, '_dns_pool'):
                self._dns_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
            fut = self._dns_pool.submit(socket.gethostbyaddr, ip)
            h = fut.result(timeout=0.4)[0]
            if h and not h.startswith('_gateway') and not h.endswith('.arpa'):
                clean = h.replace('.local', '').replace('.lan', '').replace('.home', '')
                if clean != ip:
                    return clean
        except Exception:
            pass
        return ""

    def _parse_mdns_packet(self, ip: str, data: bytes):
        """Extracts friendly names from mDNS packet via DNS RR parsing + heuristics."""
        if len(data) < 12:
            return

        try:
            qdcount, ancount, nscount, arcount = struct.unpack('>HHHH', data[4:12])
            off = 12

            # Skip question section
            for _ in range(qdcount):
                if off >= len(data):
                    break
                _, off = parse_dns_name(data, off)
                off += 4  # qtype (2), qclass (2)

            # Process Answer, Authority, and Additional RR records
            total_records = ancount + nscount + arcount
            for _ in range(total_records):
                if off >= len(data):
                    break
                rname, off = parse_dns_name(data, off)
                if off + 10 > len(data):
                    break
                rtype, rclass, ttl, rdlen = struct.unpack('>HHIH', data[off:off+10])
                off += 10
                if off + rdlen > len(data):
                    break
                rdata = data[off:off+rdlen]

                if rtype == 12:  # PTR Record
                    pname, _ = parse_dns_name(data, off)
                    # Instance name is first segment before ._<service>
                    instance = pname.split('._')[0]
                    if instance and not instance.startswith('_') and '.' not in instance:
                        self.set_name(ip, instance)

                elif rtype == 16:  # TXT Record
                    toff = 0
                    while toff < rdlen:
                        tlen = rdata[toff]
                        toff += 1
                        txt = rdata[toff:toff+tlen].decode('utf-8', errors='ignore')
                        toff += tlen
                        if '=' in txt:
                            k, v = txt.split('=', 1)
                            k_l = k.lower().strip()
                            v_clean = v.strip()
                            if k_l in ('fn', 'friendlyname', 'name'):
                                self.set_name(ip, v_clean)
                            elif k_l in ('model', 'md', 'device_name'):
                                # Only set model if nothing better exists
                                if not self.get_name(ip):
                                    self.set_name(ip, v_clean)

                elif rtype == 1:  # A Record
                    if rdlen == 4 and rname.endswith('.local'):
                        h = rname[:-6]
                        try:
                            a_ip = socket.inet_ntoa(rdata)
                            if not h.startswith('_') and not self.get_name(a_ip):
                                self.set_name(a_ip, h)
                        except Exception:
                            pass

                off += rdlen

        except Exception:
            pass

        # Text fallback only if no name has been discovered yet for this IP
        if not self.get_name(ip):
            try:
                text = data.decode('utf-8', errors='ignore')
                m_fn = re.search(r'fn=([^\x00-\x1f\t\r\n]+)', text)
                if m_fn:
                    clean_fn = re.split(r'[\x00-\x1f]', m_fn.group(1))[0].strip()
                    if clean_fn:
                        self.set_name(ip, clean_fn)
            except Exception:
                pass

    def _fetch_ssdp_xml(self, ip: str, loc: str):
        """Fetches UPnP XML descriptor and extracts friendlyName & modelName."""
        try:
            req = urllib.request.Request(loc, headers={'User-Agent': 'HomeMonitor/1.0'})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                xml = resp.read().decode('utf-8', errors='ignore')
                m_fn = re.search(r'<friendlyName>(.*?)</friendlyName>', xml, re.I)
                m_model = re.search(r'<modelName>(.*?)</modelName>', xml, re.I)
                fn = m_fn.group(1).strip() if m_fn else ""
                mod = m_model.group(1).strip() if m_model else ""
                if fn:
                    disp = f"{fn} ({mod})" if mod and mod.lower() not in fn.lower() else fn
                    self.set_name(ip, disp)
        except Exception:
            pass

    def _scan_mdns(self, timeout: float = 1.2):
        """Sends mDNS queries with QU unicast flag for rapid discovery."""
        try:
            hdr = b'\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00'
            def build_q(qname):
                qn = b''
                for p in qname.split('.'):
                    qn += bytes([len(p)]) + p.encode('utf-8')
                return hdr + qn + b'\x00\x00\x0c\x80\x01'

            s_mdns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s_mdns.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s_mdns.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
            s_mdns.settimeout(timeout)

            service_queries = [
                '_services._dns-sd._udp.local',
                '_companion-link._tcp.local',
                '_airplay._tcp.local',
                '_googlecast._tcp.local',
                '_device-info._tcp.local',
                '_spotify-connect._tcp.local',
                '_androidtvremote2._tcp.local',
                '_mi-connect._tcp.local',
                '_quickshare._tcp.local',
                '_adb._tcp.local',
                '_workstation._tcp.local',
                '_http._tcp.local',
                '_smb._tcp.local',
                '_ipp._tcp.local'
            ]
            for query in service_queries:
                s_mdns.sendto(build_q(query), ('224.0.0.251', 5353))

            t_end = time.time() + timeout
            while time.time() < t_end:
                try:
                    data, (ip, port) = s_mdns.recvfrom(4096)
                    self._parse_mdns_packet(ip, data)
                except Exception:
                    break
            s_mdns.close()
        except Exception:
            pass

    def scan_active(self, online_ips: list, timeout: float = 1.2):
        """Active broadcast sweep for SSDP, mDNS, NetBIOS, and Reverse DNS."""
        # 1. NetBIOS and Reverse DNS for active IPs
        for ip in online_ips:
            if not self.get_name(ip):
                nb = self.query_netbios(ip)
                if nb:
                    self.set_name(ip, nb)
                else:
                    rdns = self.query_reverse_dns(ip)
                    if rdns:
                        self.set_name(ip, rdns)

        # 2. SSDP M-SEARCH Broadcast
        locations = {}
        try:
            ssdp_msg = (
                'M-SEARCH * HTTP/1.1\r\n'
                'HOST: 239.255.255.250:1900\r\n'
                'MAN: "ssdp:discover"\r\n'
                'MX: 1\r\n'
                'ST: ssdp:all\r\n\r\n'
            ).encode('utf-8')
            s_ssdp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s_ssdp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s_ssdp.settimeout(timeout)
            s_ssdp.sendto(ssdp_msg, ('239.255.255.250', 1900))

            t_end = time.time() + timeout
            while time.time() < t_end:
                try:
                    data, addr = s_ssdp.recvfrom(2048)
                    ip = addr[0]
                    text = data.decode('utf-8', errors='ignore')
                    m_loc = re.search(r'LOCATION:\s*(http\S+)', text, re.I)
                    if m_loc and ip not in locations:
                        locations[ip] = m_loc.group(1).strip()
                except Exception:
                    break
            s_ssdp.close()

            # Fetch friendly names from device-desc XML in parallel
            if locations:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(locations), 5)) as pool:
                    futures = [pool.submit(self._fetch_ssdp_xml, ip, loc) for ip, loc in locations.items()]
                    concurrent.futures.wait(futures, timeout=1.0)
        except Exception:
            pass

        # 3. mDNS Active Query Broadcast
        self._scan_mdns(timeout)

        with self.lock:
            return dict(self.detected_names)

    def start_passive_listener(self):
        """Starts 24/7 background passive mDNS & SSDP listeners."""
        if self.running:
            return
        self.running = True

        self.mdns_thread = threading.Thread(target=self._mdns_passive_loop, daemon=True)
        self.mdns_thread.start()

        self.ssdp_thread = threading.Thread(target=self._ssdp_passive_loop, daemon=True)
        self.ssdp_thread.start()

    def _mdns_passive_loop(self):
        """Continuously listens for mDNS multicast traffic on 224.0.0.251:5353."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception:
                pass
            sock.bind(('0.0.0.0', 5353))
            mreq = struct.pack('4sl', socket.inet_aton('224.0.0.251'), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.settimeout(3.0)

            while self.running:
                try:
                    data, (ip, port) = sock.recvfrom(4096)
                    self._parse_mdns_packet(ip, data)
                except socket.timeout:
                    continue
                except Exception:
                    time.sleep(1)
            sock.close()
        except Exception as e:
            print(f"Passive mDNS listener error: {e}")

    def _ssdp_passive_loop(self):
        """Continuously listens for SSDP NOTIFY announcements on 239.255.255.250:1900."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception:
                pass
            sock.bind(('0.0.0.0', 1900))
            mreq = struct.pack('4sl', socket.inet_aton('239.255.255.250'), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.settimeout(3.0)

            while self.running:
                try:
                    data, (ip, port) = sock.recvfrom(2048)
                    text = data.decode('utf-8', errors='ignore')
                    if 'LOCATION:' in text.upper():
                        m_loc = re.search(r'LOCATION:\s*(http\S+)', text, re.I)
                        if m_loc:
                            loc = m_loc.group(1).strip()
                            m_ip = re.search(r'http://(\d+\.\d+\.\d+\.\d+)', loc)
                            target_ip = m_ip.group(1) if m_ip else ip
                            threading.Thread(target=self._fetch_ssdp_xml, args=(target_ip, loc), daemon=True).start()
                except socket.timeout:
                    continue
                except Exception:
                    time.sleep(1)
            sock.close()
        except Exception as e:
            print(f"Passive SSDP listener error: {e}")

    def stop(self):
        self.running = False
