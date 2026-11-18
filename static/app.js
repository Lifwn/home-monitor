/**
 * HomeMonitor - Frontend Application Logic
 */

let allDevices = [];
let currentFilter = 'all';
let wolTargets = [];
let activeTab = 'network';
let isScanning = false;
let activeWolCheck = null;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
  updateLiveClock();
  setInterval(updateLiveClock, 1000);
  setInterval(fetchSystemStats, 2500);
  setInterval(fetchDevices, 6000);
  setInterval(fetchWolTargets, 6000);
  setInterval(fetchHistory, 10000);
});

function updateLiveClock() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString('id-ID', {
    timeZone: 'Asia/Jakarta',
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
  const clockEl = document.getElementById('header-live-clock');
  if (clockEl) {
    clockEl.textContent = `${timeStr} WIB`;
  }
}

async function initDashboard() {
  await Promise.all([
    fetchNetworkInfo(),
    fetchSystemStats(),
    fetchDevices(),
    fetchWolTargets(),
    fetchHistory(),
    fetchSpeedtest(),
    fetchConfig()
  ]);
}

// ---------------- TAB NAVIGATION ----------------
function switchTab(tab) {
  activeTab = tab;
  ['network', 'wol', 'speedtest', 'hardware', 'history', 'settings'].forEach(t => {
    const btn = document.getElementById(`tab-btn-${t}`);
    const content = document.getElementById(`tab-content-${t}`);
    if (!btn || !content) return;
    if (t === tab) {
      btn.classList.add('active');
      btn.classList.remove('border-transparent', 'text-slate-400');
      btn.classList.add('border-emerald-500', 'text-emerald-400');
      content.classList.remove('hidden');
    } else {
      btn.classList.remove('active');
      btn.classList.add('border-transparent', 'text-slate-400');
      btn.classList.remove('border-emerald-500', 'text-emerald-400');
      content.classList.add('hidden');
    }
  });

  if (tab === 'history') fetchHistory();
  if (tab === 'wol') fetchWolTargets();
  if (tab === 'speedtest') fetchSpeedtest();
  if (tab === 'settings') fetchConfig();
}

// ---------------- SYSTEM STATS ----------------
async function fetchNetworkInfo() {
  try {
    const res = await fetch('/api/network/info');
    if (!res.ok) return;
    const data = await res.json();
    if (data.local_ip) {
      document.getElementById('header-lan-ip').textContent = data.local_ip;
    }
    if (data.subnet) {
      document.getElementById('kpi-subnet').textContent = data.subnet;
    }
    if (data.tailscale_ip) {
      const pill = document.getElementById('header-tailscale-pill');
      pill.textContent = `TS: ${data.tailscale_ip}`;
      pill.classList.remove('hidden');
    }
  } catch (err) {
    console.warn('Network info error:', err);
  }
}

async function fetchSystemStats() {
  try {
    const res = await fetch('/api/system');
    if (!res.ok) return;
    const data = await res.json();

    // Hostname & Server Time
    if (data.hostname) {
      document.getElementById('header-hostname').textContent = data.hostname;
    }
    if (data.local_time) {
      const serverTimeEl = document.getElementById('hw-server-time');
      if (serverTimeEl) {
        serverTimeEl.textContent = data.local_time;
      }
    }

    // CPU
    if (data.cpu) {
      const cpuUsage = data.cpu.usage_percent || 0;
      document.getElementById('kpi-cpu-usage').textContent = `${cpuUsage}%`;
      document.getElementById('kpi-cpu-bar').style.width = `${Math.min(100, Math.max(5, cpuUsage))}%`;

      if (data.cpu.temperature_c !== null) {
        document.getElementById('kpi-cpu-temp').textContent = `${data.cpu.temperature_c}°C`;
        document.getElementById('hw-cpu-temp-badge').textContent = `${data.cpu.temperature_c}°C`;
      }

      if (data.cpu.model) {
        document.getElementById('hw-cpu-model').textContent = data.cpu.model;
      }
      if (data.cpu.cores) {
        document.getElementById('hw-cpu-cores').textContent = `${data.cpu.cores} Cores`;
      }
      if (data.cpu.load_avg) {
        document.getElementById('hw-cpu-load').textContent = data.cpu.load_avg.join(', ');
      }
    }

    // RAM
    if (data.memory) {
      const ramPercent = data.memory.percent || 0;
      const usedGb = (data.memory.used_bytes / (1024 ** 3)).toFixed(1);
      const totalGb = (data.memory.total_bytes / (1024 ** 3)).toFixed(1);
      const availGb = (data.memory.available_bytes / (1024 ** 3)).toFixed(1);

      document.getElementById('kpi-ram-usage').textContent = `${ramPercent}%`;
      document.getElementById('kpi-ram-text').textContent = `${usedGb}/${totalGb} GB`;
      document.getElementById('kpi-ram-bar').style.width = `${Math.min(100, Math.max(5, ramPercent))}%`;

      document.getElementById('hw-ram-detail-text').textContent = `${usedGb} GB / ${totalGb} GB (${ramPercent}%)`;
      document.getElementById('hw-ram-detail-bar').style.width = `${ramPercent}%`;
      document.getElementById('hw-ram-avail').textContent = `${availGb} GB`;

      const swapUsedMb = Math.round(data.memory.swap_used / (1024 ** 2));
      const swapTotalMb = Math.round(data.memory.swap_total / (1024 ** 2));
      document.getElementById('hw-swap-text').textContent = `${swapUsedMb} MB / ${swapTotalMb} MB`;
    }

    // Disk
    if (data.disk) {
      const diskPercent = data.disk.percent || 0;
      const diskUsedGb = (data.disk.used_bytes / (1024 ** 3)).toFixed(1);
      const diskTotalGb = (data.disk.total_bytes / (1024 ** 3)).toFixed(1);
      const diskFreeGb = (data.disk.free_bytes / (1024 ** 3)).toFixed(1);

      document.getElementById('hw-disk-text').textContent = `${diskUsedGb} GB / ${diskTotalGb} GB (${diskPercent}%)`;
      document.getElementById('hw-disk-bar').style.width = `${diskPercent}%`;
      document.getElementById('hw-disk-free').textContent = `${diskFreeGb} GB`;
    }

    // Network Bandwidth
    if (data.network) {
      document.getElementById('kpi-net-rx').textContent = `${data.network.rx_rate_kbps} KB/s`;
      document.getElementById('kpi-net-tx').textContent = `${data.network.tx_rate_kbps} KB/s`;
      document.getElementById('kpi-net-iface').textContent = `Interface: ${data.network.interface}`;
    }

    // Power & Battery
    if (data.power) {
      const p = data.power;
      const statusEl = document.getElementById('kpi-power-status');
      const batEl = document.getElementById('kpi-power-bat');
      const iconEl = document.getElementById('kpi-power-icon');

      if (p.ac_connected) {
        statusEl.textContent = 'AC Terhubung';
        iconEl.textContent = '🔌';
        batEl.textContent = `(${p.capacity}%)`;
        document.getElementById('hw-power-detail').textContent = `AC Adapter Terhubung • Baterai ${p.capacity}% (Standby UPS Mode)`;
      } else {
        statusEl.textContent = 'Baterai';
        iconEl.textContent = '🔋';
        batEl.textContent = `(${p.capacity}%)`;
        document.getElementById('hw-power-detail').textContent = `Mode Baterai • ${p.capacity}% Tersisa`;
      }
    }

    // Uptime
    if (data.uptime && data.uptime.formatted) {
      document.getElementById('kpi-uptime').textContent = `Uptime: ${data.uptime.formatted}`;
    }

    // Docker Containers
    if (data.docker) {
      renderDocker(data.docker);
    }
  } catch (err) {
    console.warn('System stats fetch error:', err);
  }
}

function renderDocker(containers) {
  const container = document.getElementById('docker-container-list');
  const countBadge = document.getElementById('docker-count-badge');
  countBadge.textContent = `${containers.length} Container Berjalan`;

  if (!containers.length) {
    container.innerHTML = `<div class="col-span-2 text-slate-500 py-3 text-center">Tidak ada container docker yang terdeteksi aktif.</div>`;
    return;
  }

  container.innerHTML = containers.map(c => `
    <div class="bg-[#0c121e] border border-slate-800 rounded-xl p-3 flex items-start justify-between">
      <div>
        <div class="font-bold text-white flex items-center space-x-1.5">
          <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
          <span>${escapeHtml(c.name)}</span>
        </div>
        <div class="text-[11px] text-slate-400 font-mono mt-0.5 truncate max-w-[220px]" title="${escapeHtml(c.image)}">
          ${escapeHtml(c.image)}
        </div>
        <div class="text-[10px] text-emerald-400 font-medium mt-1">
          ${escapeHtml(c.status)}
        </div>
      </div>
      <span class="text-[10px] font-mono bg-slate-800 text-slate-400 px-2 py-0.5 rounded">
        ${escapeHtml(c.id.substring(0, 10))}
      </span>
    </div>
  `).join('');
}

// ---------------- NETWORK DEVICES ----------------
async function fetchDevices() {
  try {
    const res = await fetch('/api/network/devices');
    if (!res.ok) return;
    const data = await res.json();
    allDevices = data.devices || [];

    // Update KPI
    document.getElementById('kpi-devices-online').textContent = data.online || 0;
    document.getElementById('kpi-devices-total').textContent = `/ ${data.total || 0} total`;
    document.getElementById('badge-device-count').textContent = data.online || 0;

    // Scan state
    setScanUI(data.is_scanning);

    renderDevices();
  } catch (err) {
    console.warn('Fetch devices error:', err);
  }
}

function setFilter(filter) {
  currentFilter = filter;
  ['all', 'online', 'offline'].forEach(f => {
    const btn = document.getElementById(`filter-${f}`);
    if (f === filter) {
      btn.className = 'px-3 py-1 rounded-lg font-medium bg-emerald-500/20 text-emerald-400';
    } else {
      btn.className = 'px-3 py-1 rounded-lg font-medium text-slate-400 hover:text-white';
    }
  });
  renderDevices();
}

function renderDevices() {
  const tbody = document.getElementById('devices-table-body');
  const search = document.getElementById('device-search').value.toLowerCase().trim();

  let filtered = allDevices.filter(d => {
    if (currentFilter === 'online' && !d.is_online) return false;
    if (currentFilter === 'offline' && d.is_online) return false;
    if (search) {
      const matchIp = (d.ip || '').toLowerCase().includes(search);
      const matchMac = (d.mac || '').toLowerCase().includes(search);
      const matchName = (d.custom_name || '').toLowerCase().includes(search);
      const matchDet = (d.detected_name || '').toLowerCase().includes(search);
      const matchHost = (d.hostname || '').toLowerCase().includes(search);
      const matchVendor = (d.vendor || '').toLowerCase().includes(search);
      const matchNotes = (d.notes || '').toLowerCase().includes(search);
      return matchIp || matchMac || matchName || matchDet || matchHost || matchVendor || matchNotes;
    }
    return true;
  });

  if (!filtered.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="py-8 text-center text-slate-500 text-xs">
          Tidak ada perangkat yang cocok dengan kriteria pencarian.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(d => {
    const isOnline = d.is_online;
    const hasCustom = Boolean(d.custom_name && d.custom_name.trim());
    const detectedName = d.detected_name || d.hostname || '';
    const displayName = (hasCustom ? d.custom_name.trim() : detectedName) || (d.is_router ? 'Router Gateway' : (d.is_host ? 'Home Server Ini' : 'Perangkat'));
    const isTargetWol = wolTargets.some(t => t.mac.toUpperCase() === (d.mac || '').toUpperCase());

    return `
      <tr class="hover:bg-slate-800/40 transition">
        <!-- Status -->
        <td class="py-3 px-4">
          <div class="flex items-center space-x-2">
            <span class="w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}"></span>
            <span class="font-semibold text-xs ${isOnline ? 'text-emerald-400' : 'text-slate-500'}">
              ${isOnline ? 'Online' : 'Offline'}
            </span>
          </div>
        </td>

        <!-- Nama / Alias -->
        <td class="py-3 px-4">
          <div class="flex items-center space-x-1.5">
            <div class="font-bold text-white text-xs sm:text-sm flex items-center gap-1.5 flex-wrap">
              <span>${escapeHtml(displayName)}</span>
              ${d.is_router ? '<span class="text-[10px] bg-blue-500/20 text-blue-400 px-1.5 py-0.2 rounded font-mono">ROUTER</span>' : ''}
              ${d.is_host ? '<span class="text-[10px] bg-emerald-500/20 text-emerald-400 px-1.5 py-0.2 rounded font-mono">SERVER INI</span>' : ''}
              ${hasCustom ? '<span class="text-[10px] bg-purple-500/20 text-purple-300 px-1.5 py-0.2 rounded font-mono font-medium">ALIAS</span>' : ''}
            </div>
            <button onclick="openEditDeviceModal('${escapeHtml(d.id)}', '${escapeHtml(d.ip)}', '${escapeHtml(d.mac)}', '${escapeHtml(d.vendor)}', '${escapeHtml(d.custom_name || '')}', '${escapeHtml(d.notes || '')}', '${escapeHtml(detectedName || '')}')" class="text-slate-500 hover:text-emerald-400 p-1 transition" title="Beri Nama / Ubah Alias">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg>
            </button>
          </div>
          ${hasCustom && detectedName && detectedName !== d.custom_name ? `<div class="text-[11px] text-slate-400 font-sans truncate max-w-[200px]">Bawaan: <span class="text-slate-300 font-medium">${escapeHtml(detectedName)}</span></div>` : ''}
          ${!hasCustom && d.hostname && d.hostname !== displayName && !detectedName.includes(d.hostname) ? `<div class="text-[11px] text-slate-400 font-mono truncate max-w-[180px]">${escapeHtml(d.hostname)}</div>` : ''}
          ${d.notes ? `<div class="text-[11px] text-slate-500 italic truncate max-w-[200px]">${escapeHtml(d.notes)}</div>` : ''}
        </td>

        <!-- IP -->
        <td class="py-3 px-4 font-mono font-semibold text-slate-200 text-xs sm:text-sm">
          ${escapeHtml(d.ip)}
        </td>

        <!-- MAC -->
        <td class="py-3 px-4 font-mono text-xs text-slate-400">
          <div class="flex items-center space-x-1.5">
            <span>${d.mac || 'Tidak diketahui'}</span>
            ${d.mac ? `
              <button onclick="copyToClipboard('${d.mac}', 'MAC disalin')" class="text-slate-500 hover:text-slate-300 p-0.5" title="Salin MAC">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
              </button>
            ` : ''}
          </div>
        </td>

        <!-- Vendor -->
        <td class="py-3 px-4 text-xs">
          <span class="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700/60 font-medium">
            ${escapeHtml(d.vendor || 'Generic')}
          </span>
        </td>

        <!-- Latency -->
        <td class="py-3 px-4 font-mono text-xs">
          ${isOnline && d.latency_ms !== null ? `
            <span class="${d.latency_ms < 5 ? 'text-emerald-400' : (d.latency_ms < 50 ? 'text-blue-400' : 'text-amber-400')} font-semibold">
              ${d.latency_ms} ms
            </span>
          ` : '<span class="text-slate-600">-</span>'}
        </td>

        <!-- Aksi -->
        <td class="py-3 px-4 text-right">
          <div class="flex items-center justify-end space-x-1.5">
            ${d.mac && !d.is_host ? `
              <button onclick="prepareQuickWol('${escapeHtml(d.mac)}', '${escapeHtml(displayName)}', '${escapeHtml(d.ip)}')" class="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-semibold flex items-center space-x-1 transition" title="Kirim Magic Packet (WoL)">
                <span>⚡ WoL</span>
              </button>
              ${!isTargetWol ? `
                <button onclick="quickAddWol('${escapeHtml(displayName)}', '${escapeHtml(d.mac)}', '${escapeHtml(d.ip)}')" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition" title="Simpan sebagai Target WoL">
                  + Simpan
                </button>
              ` : ''}
            ` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

// ---------------- NETWORK SCAN TRIGGER ----------------
let scanIntervalTimer = null;

async function triggerScan() {
  if (isScanning) return;
  setScanUI(true);

  try {
    const res = await fetch('/api/network/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    showToast(data.message || 'Pemindaian jaringan dimulai', 'info');

    let counter = 3;
    const bannerTimer = document.getElementById('scan-timer');
    if (scanIntervalTimer) clearInterval(scanIntervalTimer);
    scanIntervalTimer = setInterval(() => {
      counter++;
      if (bannerTimer) bannerTimer.textContent = `${counter}s`;
    }, 1000);

    // Poll until scan completes
    const checkScanner = setInterval(async () => {
      const checkRes = await fetch('/api/network/devices');
      if (checkRes.ok) {
        const checkData = await checkRes.json();
        if (!checkData.is_scanning) {
          clearInterval(checkScanner);
          clearInterval(scanIntervalTimer);
          setScanUI(false);
          allDevices = checkData.devices || [];
          document.getElementById('kpi-devices-online').textContent = checkData.online || 0;
          document.getElementById('kpi-devices-total').textContent = `/ ${checkData.total || 0} total`;
          document.getElementById('badge-device-count').textContent = checkData.online || 0;
          renderDevices();
          showToast(`Pemindaian selesai! Ditemukan ${checkData.online} perangkat online.`, 'success');
        }
      }
    }, 1500);

  } catch (err) {
    setScanUI(false);
    showToast('Gagal memicu pemindaian jaringan', 'error');
  }
}

function setScanUI(scanning) {
  isScanning = scanning;
  const icon = document.getElementById('scan-icon');
  const text = document.getElementById('scan-text');
  const banner = document.getElementById('scan-progress-banner');

  if (scanning) {
    icon.classList.add('animate-spin');
    text.textContent = 'Memindai...';
    banner.classList.remove('hidden');
  } else {
    icon.classList.remove('animate-spin');
    text.textContent = 'Pindai Jaringan';
    banner.classList.add('hidden');
  }
}

// ---------------- WAKE ON LAN ----------------
async function fetchWolTargets() {
  try {
    const res = await fetch('/api/wol/targets');
    if (!res.ok) return;
    wolTargets = await res.json();
    document.getElementById('badge-wol-count').textContent = wolTargets.length;
    document.getElementById('wol-target-summary').textContent = `${wolTargets.length} Komputer Tersimpan`;
    renderWolTargets();
  } catch (err) {
    console.warn('Fetch WoL targets error:', err);
  }
}

function renderWolTargets() {
  const container = document.getElementById('wol-targets-grid');
  if (!wolTargets.length) {
    container.innerHTML = `
      <div class="col-span-full bg-cardBg border border-dashed border-slate-800 rounded-2xl p-8 text-center space-y-3">
        <div class="text-3xl">⚡</div>
        <h4 class="text-white font-bold">Belum Ada Target PC Tersimpan</h4>
        <p class="text-xs text-slate-400 max-w-md mx-auto">
          Tambahkan PC rumah Anda (komputer desktop, laptop kantor, NAS) untuk menyalakannya kapan saja melalui tombol Wake-on-LAN.
        </p>
        <button onclick="openAddWolModal()" class="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs inline-flex items-center space-x-1.5 transition">
          <span>+ Tambah PC Sekarang</span>
        </button>
      </div>
    `;
    return;
  }

  container.innerHTML = wolTargets.map(t => {
    const isOnline = t.is_online;
    return `
      <div class="bg-cardBg border ${isOnline ? 'border-emerald-500/40 shadow-lg shadow-emerald-500/5' : 'border-cardBorder'} rounded-2xl p-5 space-y-4 relative overflow-hidden transition">
        
        <!-- Header PC -->
        <div class="flex items-start justify-between">
          <div class="space-y-1">
            <div class="flex items-center space-x-2">
              <span class="w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}"></span>
              <h4 class="font-bold text-white text-base">${escapeHtml(t.name)}</h4>
            </div>
            <p class="text-xs font-mono text-emerald-400">${escapeHtml(t.mac)}</p>
          </div>

          <div class="flex items-center space-x-1">
            <span class="text-[11px] font-semibold px-2 py-0.5 rounded-full ${isOnline ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'}">
              ${isOnline ? `Online (${t.latency_ms || 1}ms)` : 'Mati / Tidur'}
            </span>
            <button onclick="deleteWolTarget('${escapeHtml(t.id)}')" class="text-slate-600 hover:text-rose-400 p-1" title="Hapus target">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
            </button>
          </div>
        </div>

        <!-- Meta Details -->
        <div class="space-y-1 text-xs text-slate-400 font-mono bg-[#0c121e] p-2.5 rounded-xl border border-slate-800/80">
          <div class="flex justify-between">
            <span class="text-slate-500 font-sans">Target IP:</span>
            <span class="text-slate-200">${escapeHtml(t.ip || 'Auto-scan')}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-500 font-sans">Broadcast:</span>
            <span class="text-slate-200">${escapeHtml(t.broadcast_ip || '192.168.1.255')}:${t.port || 9}</span>
          </div>
          ${t.last_woken ? `
            <div class="flex justify-between text-[11px]">
              <span class="text-slate-500 font-sans">Terakhir WoL:</span>
              <span class="text-emerald-400 font-sans">${formatTimestamp(t.last_woken)}</span>
            </div>
          ` : ''}
        </div>

        ${t.notes ? `<p class="text-xs text-slate-500 italic">${escapeHtml(t.notes)}</p>` : ''}

        <!-- Primary Trigger Button -->
        <button onclick="wakeDevice('${escapeHtml(t.mac)}', '${escapeHtml(t.name)}', '${escapeHtml(t.ip || '')}', '${escapeHtml(t.broadcast_ip || '192.168.1.255')}', ${t.port || 9})" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-bold text-xs sm:text-sm shadow-md shadow-emerald-500/20 flex items-center justify-center space-x-2 transition transform active:scale-98">
          <span>⚡</span>
          <span>Nyalakan PC Ini (WoL)</span>
        </button>

      </div>
    `;
  }).join('');
}

async function wakeDevice(mac, name, ip, broadcastIp, port) {
  showToast(`Mengirim sinyal WoL ke ${name}...`, 'info');
  startWolTracker(name, mac, ip);

  try {
    const res = await fetch('/api/wol/wake', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mac: mac,
        name: name,
        ip: ip,
        broadcast_ip: broadcastIp || '192.168.1.255',
        port: port || 9
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      fetchWolTargets();
    } else {
      showToast(data.error || 'Gagal mengirim magic packet', 'error');
    }
  } catch (err) {
    showToast('Terjadi kesalahan jaringan saat mengirim WoL', 'error');
  }
}

function startWolTracker(name, mac, ip) {
  const tracker = document.getElementById('wol-live-tracker');
  const title = document.getElementById('wol-tracker-title');
  const subtitle = document.getElementById('wol-tracker-subtitle');
  const bar = document.getElementById('wol-tracker-bar');
  const timer = document.getElementById('wol-tracker-timer');
  const log = document.getElementById('wol-tracker-log');

  tracker.classList.remove('hidden');
  title.textContent = `Menyalakan ${name}...`;
  subtitle.textContent = `Magic packet terkirim ke ${mac}. Memantau status boot PC...`;
  log.textContent = `UDP Magic Packet disiarkan. Menunggu PC merespons ping (${ip || 'Subnet'})...`;

  if (activeWolCheck) clearInterval(activeWolCheck);

  let secondsLeft = 60;
  bar.style.width = '10%';
  timer.textContent = `${secondsLeft}s`;

  activeWolCheck = setInterval(async () => {
    secondsLeft -= 2;
    const progress = Math.min(100, Math.round(((60 - secondsLeft) / 60) * 100));
    bar.style.width = `${progress}%`;
    timer.textContent = `${secondsLeft}s`;

    // If we have an IP, actively check ping
    if (ip) {
      try {
        const pingRes = await fetch(`/api/wol/check?ip=${ip}`);
        if (pingRes.ok) {
          const pingData = await pingRes.json();
          if (pingData.is_online) {
            clearInterval(activeWolCheck);
            title.textContent = `🎉 ${name} Berhasil Menyala!`;
            subtitle.textContent = `PC telah online dan merespons ping (${pingData.latency_ms || 1} ms)`;
            bar.style.width = '100%';
            bar.className = 'bg-emerald-400 h-2 rounded-full';
            log.textContent = `Koneksi tersambung pada ${ip}`;
            showToast(`PC ${name} sudah Online!`, 'success');
            fetchDevices();
            fetchWolTargets();
            return;
          }
        }
      } catch (e) { }
    }

    if (secondsLeft <= 0) {
      clearInterval(activeWolCheck);
      title.textContent = `Pemantauan Selesai (${name})`;
      subtitle.textContent = `Sinyal telah dikirim. Jika PC belum online, periksa pengaturan BIOS/UEFI dan fast startup.`;
      log.textContent = `Batas waktu pantau 60 detik berakhir.`;
    }
  }, 2000);
}

function dismissWolTracker() {
  if (activeWolCheck) clearInterval(activeWolCheck);
  document.getElementById('wol-live-tracker').classList.add('hidden');
}

function openAddWolModal() {
  document.getElementById('modal-add-wol').classList.remove('hidden');
}

function closeAddWolModal() {
  document.getElementById('modal-add-wol').classList.add('hidden');
}

async function handleSaveWolTarget(e) {
  e.preventDefault();
  const name = document.getElementById('form-wol-name').value.trim();
  const mac = document.getElementById('form-wol-mac').value.trim();
  const ip = document.getElementById('form-wol-ip').value.trim();
  const port = parseInt(document.getElementById('form-wol-port').value) || 9;
  const broadcast_ip = document.getElementById('form-wol-broadcast').value.trim() || '192.168.1.255';
  const notes = document.getElementById('form-wol-notes').value.trim();

  try {
    const res = await fetch('/api/wol/targets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, mac, ip, port, broadcast_ip, notes })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Target PC "${name}" berhasil disimpan`, 'success');
      closeAddWolModal();
      fetchWolTargets();
      e.target.reset();
    } else {
      showToast(data.error || 'Gagal menyimpan target WoL', 'error');
    }
  } catch (err) {
    showToast('Terjadi kesalahan jaringan', 'error');
  }
}

async function deleteWolTarget(id) {
  if (!confirm('Yakin ingin menghapus PC ini dari daftar Wake-on-LAN?')) return;
  try {
    const res = await fetch(`/api/wol/targets?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      showToast('Target WoL berhasil dihapus', 'info');
      fetchWolTargets();
    }
  } catch (err) {
    showToast('Gagal menghapus target', 'error');
  }
}

function quickAddWol(name, mac, ip) {
  document.getElementById('form-wol-name').value = name || 'PC';
  document.getElementById('form-wol-mac').value = mac || '';
  document.getElementById('form-wol-ip').value = ip || '';
  openAddWolModal();
}

function prepareQuickWol(mac, name, ip) {
  wakeDevice(mac, name || 'PC', ip || '', '192.168.1.255', 9);
}

function openQuickWolModal() {
  const manualMac = prompt('Masukkan MAC Address PC yang ingin dinyalakan (contoh: AA:BB:CC:DD:EE:FF):');
  if (manualMac && manualMac.trim()) {
    wakeDevice(manualMac.trim(), 'PC Manual', '', '192.168.1.255', 9);
  }
}

// ---------------- DEVICE RENAME / ALIAS ----------------
function openEditDeviceModal(id, ip, mac, vendor, name, notes, detectedName) {
  document.getElementById('edit-dev-key').value = id;
  document.getElementById('edit-dev-ip').textContent = ip;
  document.getElementById('edit-dev-mac').textContent = mac;
  document.getElementById('edit-dev-vendor').textContent = vendor;
  const detEl = document.getElementById('edit-dev-detected');
  if (detEl) {
    detEl.textContent = detectedName || 'Tidak terdeteksi (Default)';
  }
  document.getElementById('edit-dev-name').value = name;
  document.getElementById('edit-dev-notes').value = notes;
  document.getElementById('modal-edit-device').classList.remove('hidden');
}

function closeEditDeviceModal() {
  document.getElementById('modal-edit-device').classList.add('hidden');
}

async function handleSaveDeviceAlias(e) {
  e.preventDefault();
  const id = document.getElementById('edit-dev-key').value;
  const custom_name = document.getElementById('edit-dev-name').value.trim();
  const notes = document.getElementById('edit-dev-notes').value.trim();

  try {
    const res = await fetch('/api/network/device/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, custom_name, notes })
    });
    const data = await res.json();
    if (data.success) {
      if (custom_name) {
        showToast('Alias perangkat berhasil disimpan', 'success');
      } else {
        showToast('Alias dihapus, menggunakan nama bawaan', 'info');
      }
      closeEditDeviceModal();
      fetchDevices();
    } else {
      showToast(data.error || 'Gagal menyimpan alias', 'error');
    }
  } catch (err) {
    showToast('Terjadi kesalahan jaringan', 'error');
  }
}

  // ---------------- HISTORY LOGS ----------------
  async function fetchHistory() {
    try {
      const res = await fetch('/api/history');
      if (!res.ok) return;
      const logs = await res.json();
      renderHistory(logs);
    } catch (err) {
      console.warn('Fetch history error:', err);
    }
  }

  function renderHistory(logs) {
    const container = document.getElementById('history-log-list');
    if (!logs || !logs.length) {
      container.innerHTML = `<div class="text-slate-500 text-xs py-4 text-center">Belum ada catatan aktivitas.</div>`;
      return;
    }

    container.innerHTML = logs.map(item => {
      let icon = '📝';
      let color = 'text-slate-300';
      if (item.type === 'wol_triggered') {
        icon = '⚡';
        color = 'text-amber-300';
      } else if (item.type === 'device_discovered') {
        icon = '🔍';
        color = 'text-emerald-300';
      }

      return `
      <div class="flex items-start space-x-3 p-3 rounded-xl bg-[#0c121e] border border-slate-800 text-xs">
        <span class="text-sm">${icon}</span>
        <div class="flex-1 space-y-0.5">
          <div class="font-medium ${color}">${escapeHtml(item.message)}</div>
          <div class="text-[10px] text-slate-500 font-mono">${escapeHtml(item.time_str || '')}</div>
        </div>
      </div>
    `;
    }).join('');
  }

  // ---------------- SPEEDTEST ----------------
  let speedtestInterval = null;

  async function fetchSpeedtest() {
    try {
      const res = await fetch('/api/speedtest/history');
      if (!res.ok) return;
      const data = await res.json();
      renderSpeedtest(data);
    } catch (err) {
      console.warn('Fetch speedtest error:', err);
    }
  }

  function renderSpeedtest(data) {
    const latest = data.latest;
    const history = data.history || [];

    if (latest) {
      document.getElementById('speed-dl-val').textContent = latest.download_mbps;
      document.getElementById('speed-ul-val').textContent = latest.upload_mbps;
      document.getElementById('speed-ping-val').textContent = latest.ping_ms;
      document.getElementById('speed-jitter-val').textContent = `${latest.jitter_ms || 1.0} ms`;
      document.getElementById('speed-quality-val').textContent = latest.quality || 'Stabil';
      document.getElementById('speed-time-val').textContent = `${latest.time_str} (${latest.triggered_by})`;
    }

    document.getElementById('speedtest-history-count').textContent = `${history.length} Pengujian`;
    const tbody = document.getElementById('speedtest-history-body');

    if (!history.length) {
      tbody.innerHTML = `
      <tr>
        <td colspan="6" class="py-6 text-center text-slate-500">
          Belum ada riwayat pengujian kecepatan. Klik tombol "Uji Kecepatan Sekarang" di atas.
        </td>
      </tr>
    `;
      return;
    }

    tbody.innerHTML = history.map(h => `
    <tr class="hover:bg-slate-800/40 font-mono transition">
      <td class="py-2.5 px-3 text-slate-300 font-sans">${escapeHtml(h.time_str)}</td>
      <td class="py-2.5 px-3 text-emerald-400 font-bold">${h.download_mbps} Mbps</td>
      <td class="py-2.5 px-3 text-cyan-400 font-bold">${h.upload_mbps} Mbps</td>
      <td class="py-2.5 px-3 text-purple-400">${h.ping_ms} ms</td>
      <td class="py-2.5 px-3 font-sans">
        <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold ${h.download_mbps >= 50 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-cyan-500/20 text-cyan-300'}">
          ${escapeHtml(h.quality)}
        </span>
      </td>
      <td class="py-2.5 px-3 text-[11px] text-slate-500 font-sans">${escapeHtml(h.triggered_by)}</td>
    </tr>
  `).join('');
  }

  async function triggerSpeedtest() {
    const btn = document.getElementById('btn-run-speedtest');
    const icon = document.getElementById('speedtest-btn-icon');
    const text = document.getElementById('speedtest-btn-text');

    btn.disabled = true;
    icon.classList.add('animate-spin');
    text.textContent = 'Menguji Kecepatan (~10s)...';
    showToast('Pengujian kecepatan dimulai ke Cloudflare Edge CDN...', 'info');

    try {
      const res = await fetch('/api/speedtest/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const data = await res.json();

      let checkCount = 0;
      const interval = setInterval(async () => {
        checkCount++;
        const checkRes = await fetch('/api/speedtest/history');
        if (checkRes.ok) {
          const checkData = await checkRes.json();
          if (!checkData.is_running || checkCount >= 15) {
            clearInterval(interval);
            btn.disabled = false;
            icon.classList.remove('animate-spin');
            text.textContent = 'Uji Kecepatan Sekarang';
            renderSpeedtest(checkData);
            if (checkData.latest) {
              showToast(`Selesai! Download: ${checkData.latest.download_mbps} Mbps, Upload: ${checkData.latest.upload_mbps} Mbps`, 'success');
            }
          }
        }
      }, 2000);

    } catch (err) {
      btn.disabled = false;
      icon.classList.remove('animate-spin');
      text.textContent = 'Uji Kecepatan Sekarang';
      showToast('Gagal menjalankan speedtest', 'error');
    }
  }

  // ---------------- SETTINGS & TELEGRAM BOT ----------------
  let currentServerConfig = {};

  async function fetchConfig() {
    try {
      const res = await fetch('/api/config');
      if (!res.ok) return;
      currentServerConfig = await res.json();
      renderConfigForm(currentServerConfig);
    } catch (err) {
      console.warn('Fetch config error:', err);
    }
  }

  function renderConfigForm(cfg) {
    const statusPill = document.getElementById('settings-webhook-status-pill');
    const badgeStatus = document.getElementById('badge-webhook-status');
    const webhookInput = document.getElementById('input-webhook-url');

    if (webhookInput) {
      webhookInput.value = cfg.webhook_url || '';
    }

    if (cfg.webhook_url) {
      if (statusPill) {
        statusPill.textContent = '🟢 Webhook Aktif';
        statusPill.className = 'text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
      }
      if (badgeStatus) badgeStatus.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
    } else {
      if (statusPill) {
        statusPill.textContent = '⚪ Belum Dikonfigurasi';
        statusPill.className = 'text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-800 text-slate-400 border border-slate-700';
      }
      if (badgeStatus) badgeStatus.className = 'w-2 h-2 rounded-full bg-slate-600';
    }

    // Telegram Inputs
    const tgTokenInput = document.getElementById('input-tg-token');
    if (tgTokenInput && cfg.telegram_token_masked) {
      tgTokenInput.placeholder = `Tersimpan: ${cfg.telegram_token_masked}`;
    }
    const tgChatInput = document.getElementById('input-tg-chat-id');
    if (tgChatInput) {
      tgChatInput.value = cfg.telegram_chat_id || '';
    }

    // Checkboxes
    document.getElementById('chk-notify-power').checked = (cfg.notify_power !== false);
    document.getElementById('chk-notify-new-devices').checked = (cfg.notify_new_devices !== false);
    document.getElementById('chk-notify-speedtest').checked = (cfg.notify_speedtest !== false);
    const chkWol = document.getElementById('chk-notify-wol');
    if (chkWol) chkWol.checked = (cfg.notify_wol === true);
    document.getElementById('input-speedtest-interval').value = cfg.auto_speedtest_interval_hours || 6;
  }

  async function handleSaveSettings(e) {
    e.preventDefault();
    const webhook_url = (document.getElementById('input-webhook-url') ? document.getElementById('input-webhook-url').value.trim() : '');
    const token = (document.getElementById('input-tg-token') ? document.getElementById('input-tg-token').value.trim() : '');
    const chat_id = (document.getElementById('input-tg-chat-id') ? document.getElementById('input-tg-chat-id').value.trim() : '');
    const notify_power = document.getElementById('chk-notify-power').checked;
    const notify_new_devices = document.getElementById('chk-notify-new-devices').checked;
    const notify_speedtest = document.getElementById('chk-notify-speedtest').checked;
    const notify_wol = document.getElementById('chk-notify-wol') ? document.getElementById('chk-notify-wol').checked : false;
    const auto_speedtest_interval_hours = parseInt(document.getElementById('input-speedtest-interval').value) || 6;

    const payload = {
      webhook_url: webhook_url,
      webhook_enabled: Boolean(webhook_url),
      telegram_chat_id: chat_id,
      notify_power,
      notify_new_devices,
      notify_speedtest,
      notify_wol,
      auto_speedtest_interval_hours
    };
    if (token) {
      payload.telegram_token = token;
    }

    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        showToast('Pengaturan Webhook berhasil disimpan!', 'success');
        if (document.getElementById('input-tg-token')) {
          document.getElementById('input-tg-token').value = '';
        }
        fetchConfig();
      } else {
        showToast(data.error || 'Gagal menyimpan pengaturan', 'error');
      }
    } catch (err) {
      showToast('Terjadi kesalahan jaringan', 'error');
    }
  }

  async function testWebhookMessage() {
    const webhook_url = document.getElementById('input-webhook-url') ? document.getElementById('input-webhook-url').value.trim() : '';
    if (!webhook_url) {
      showToast('Masukkan link Webhook URL terlebih dahulu!', 'error');
      return;
    }

    showToast('Mengirim notifikasi tes ke Webhook...', 'info');
    try {
      const res = await fetch('/api/webhook/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: webhook_url })
      });
      const data = await res.json();
      if (data.success) {
        showToast(data.message || 'Pesan tes berhasil dikirim ke Webhook!', 'success');
        fetchConfig();
      } else {
        showToast(data.error || 'Gagal mengirim ke Webhook. Periksa kembali link URL.', 'error');
      }
    } catch (err) {
      showToast('Gagal menghubungi server', 'error');
    }
  }

  async function testTelegramMessage() {
    const token = document.getElementById('input-tg-token').value.trim();
    const chat_id = document.getElementById('input-tg-chat-id').value.trim();

    showToast('Mengirim pesan verifikasi ke Telegram...', 'info');
    try {
      const res = await fetch('/api/telegram/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, chat_id })
      });
      const data = await res.json();
      if (data.success) {
        showToast('Pesan berhasil terkirim ke Telegram Anda!', 'success');
        fetchConfig();
      } else {
        showToast(data.error || 'Gagal mengirim ke Telegram. Periksa token dan chat ID.', 'error');
      }
    } catch (err) {
      showToast('Gagal menghubungi server', 'error');
    }
  }

  // ---------------- TOAST NOTIFICATIONS ----------------
  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');

    const bg = type === 'success' ? 'bg-emerald-950/90 border-emerald-500 text-emerald-300' :
      type === 'error' ? 'bg-rose-950/90 border-rose-500 text-rose-300' :
        'bg-slate-900/90 border-slate-700 text-slate-200';

    toast.className = `p-3.5 rounded-xl border shadow-xl flex items-center space-x-2 text-xs font-semibold backdrop-blur-md transition-all duration-300 transform translate-y-2 opacity-0 pointer-events-auto ${bg}`;
    toast.innerHTML = `
    <span>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
    <span>${escapeHtml(message)}</span>
  `;

    container.appendChild(toast);
    requestAnimationFrame(() => {
      toast.classList.remove('translate-y-2', 'opacity-0');
    });

    setTimeout(() => {
      toast.classList.add('opacity-0', 'translate-y-2');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // ---------------- UTILS ----------------
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatTimestamp(ts) {
    if (!ts) return '-';
    const d = new Date(ts * 1000);
    const timeStr = d.toLocaleTimeString('id-ID', {
      timeZone: 'Asia/Jakarta',
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    const dateStr = d.toLocaleDateString('id-ID', {
      timeZone: 'Asia/Jakarta',
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
    return `${timeStr} WIB • ${dateStr}`;
  }

  function copyToClipboard(text, msg) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(msg || 'Disalin ke clipboard', 'success');
    }).catch(() => {
      prompt('Salin teks:', text);
    });
  }
