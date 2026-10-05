// ==== GPM MODE ====
let gpmIsRunning = false, gpmEvt = null;
let gpmOk = 0, gpmFail = 0, gpmTotal = 0;
let gpmLogs = [], gpmFilter = 'ALL';
let gpmMailType = 'hotmail', gpmApiSource = 'dongvanfb', gpmMode = 3;
let gpmProfilesList = [];

function gpmSetMailType(t) {
  gpmMailType = t;
  document.getElementById('gpm-mailHotmail').classList.toggle('active', t === 'hotmail');
  document.getElementById('gpm-mailDomain').classList.toggle('active', t === 'domain');
  const group = document.getElementById('gpm-apiSourceGroup');
  if (group) group.style.display = (t === 'hotmail') ? 'block' : 'none';
}

function gpmSetApiSource(src) {
  gpmApiSource = src;
  document.getElementById('gpm-sourceDongvanfb').classList.toggle('active', src === 'dongvanfb');
  document.getElementById('gpm-sourceMixmmo').classList.toggle('active', src === 'mixmmo');
}

function gpmSetMode(m) {
  gpmMode = m;
  [1, 2, 3].forEach(i => {
    const el = document.getElementById(`gpm-mode${i}`);
    if (el) el.classList.toggle('active', i === m);
  });
  const jlGroup = document.getElementById('gpm-joinLinkGroup');
  if (jlGroup) jlGroup.style.display = (m === 2) ? 'block' : 'none';
}

function gpmSetFilter(f, btn) {
  gpmFilter = f;
  const wrap = document.getElementById('gpm-logWrap');
  if (wrap) wrap.querySelectorAll('.log-filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  if (wrap) wrap.innerHTML = '';
  gpmLogs.forEach(l => {
    if (f === 'ALL' || l.level === f) gpmRenderLog(l);
  });
}

function gpmClearLog() {
  gpmLogs = [];
  const wrap = document.getElementById('gpm-logWrap');
  if (wrap) wrap.innerHTML = '<div class="log-entry log-info"><span class="log-time">--:--:--</span><span class="log-icon">📌</span><span class="log-msg">Nhật ký đã xóa.</span></div>';
}

async function gpmLoadProfiles() {
  const apiUrl = document.getElementById('gpm-apiUrl').value.trim();
  const wrap = document.getElementById('gpm-profileListWrap');
  const countLabel = document.getElementById('gpm-profileCountLabel');
  wrap.innerHTML = '<div style="color:var(--muted);font-size:11px;text-align:center;padding:15px;">⏳ Đang kết nối GPM API...</div>';
  
  try {
    const r = await fetch(`/api/gpm/profiles?api_url=${encodeURIComponent(apiUrl)}`);
    const d = await r.json();
    if (d.success && d.profiles && d.profiles.length > 0) {
      gpmProfilesList = d.profiles;
      countLabel.textContent = `${d.profiles.length} profiles`;
      wrap.innerHTML = d.profiles.map((p) => `
        <label style="display:flex;align-items:center;gap:8px;padding:4px 6px;border-bottom:1px solid rgba(255,255,255,0.05);cursor:pointer;font-size:11px;">
          <input type="checkbox" class="gpm-profile-cb" value="${escHtml(p.id)}" onchange="gpmUpdateSelectedCount()">
          <span style="font-weight:600;color:var(--accent);font-family:monospace;">${escHtml(p.name)}</span>
          <span style="color:var(--muted);font-size:10px;">(ID: ${escHtml(p.id)})</span>
          ${p.raw_proxy ? `<span style="margin-left:auto;font-size:9px;color:var(--green);">${escHtml(p.raw_proxy)}</span>` : ''}
        </label>
      `).join('');
      gpmUpdateSelectedCount();
      showToast('✅', `Đã nạp ${d.profiles.length} GPM profiles!`);
    } else {
      gpmProfilesList = [];
      countLabel.textContent = '0 profiles';
      wrap.innerHTML = `<div style="color:var(--red);font-size:11px;text-align:center;padding:15px;">❌ ${escHtml(d.error || 'Không tải được danh sách profile')}</div>`;
    }
  } catch (e) {
    wrap.innerHTML = '<div style="color:var(--red);font-size:11px;text-align:center;padding:15px;">❌ Lỗi kết nối GPM API!</div>';
  }
}

function gpmUpdateSelectedCount() {
  const cbs = document.querySelectorAll('.gpm-profile-cb:checked');
  const manualRaw = document.getElementById('gpm-manualPids').value.trim();
  let manualCount = 0;
  if (manualRaw) {
    manualCount = manualRaw.replace(/,/g, '\n').split('\n').filter(s => s.trim()).length;
  }
  const total = cbs.length + manualCount;
  document.getElementById('gpm-statSelected').textContent = total;
}

function gpmGetSelectedProfileIds() {
  const pids = [];
  document.querySelectorAll('.gpm-profile-cb:checked').forEach(cb => pids.push(cb.value));
  const manualRaw = document.getElementById('gpm-manualPids').value.trim();
  if (manualRaw) {
    manualRaw.replace(/,/g, '\n').split('\n').forEach(s => {
      const trimmed = s.trim();
      if (trimmed && !pids.includes(trimmed)) pids.push(trimmed);
    });
  }
  return pids;
}

async function gpmOpenProfiles() {
  const pids = gpmGetSelectedProfileIds();
  if (pids.length === 0) {
    showToast('⚠️', 'Vui lòng chọn hoặc nhập ít nhất 1 GPM Profile!');
    return;
  }
  const apiUrl = document.getElementById('gpm-apiUrl').value.trim();
  showToast('⏳', `Đang mở ${pids.length} GPM Profile...`);
  for (const pid of pids) {
    try {
      const r = await fetch('/api/gpm/profile/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: pid, api_url: apiUrl })
      });
      const d = await r.json();
      if (d.success) {
        showToast('✅', `Đã mở GPM Profile: ${pid}`);
      } else {
        showToast('❌', `Lỗi mở ${pid}: ${d.error || ''}`);
      }
    } catch (e) {
      showToast('❌', `Lỗi kết nối khi mở ${pid}`);
    }
  }
}

async function gpmCreateNewProfile() {
  const name = prompt('Nhập tên Profile GPM mới:', `CapCut_Profile_${Date.now().toString().slice(-4)}`);
  if (!name) return;
  const apiUrl = document.getElementById('gpm-apiUrl').value.trim();
  showToast('⏳', `Đang tạo Profile GPM mới: ${name}...`);
  try {
    const r = await fetch('/api/gpm/profile/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, api_url: apiUrl })
    });
    const d = await r.json();
    if (d.success) {
      showToast('✅', `Đã tạo Profile GPM thành công! ID: ${d.profile_id}`);
      gpmLoadProfiles();
    } else {
      showToast('❌', `Lỗi tạo Profile: ${d.error || ''}`);
    }
  } catch (e) {
    showToast('❌', `Lỗi kết nối khi tạo Profile mới`);
  }
}

async function gpmCloseProfiles() {
  const pids = gpmGetSelectedProfileIds();
  if (pids.length === 0) {
    showToast('⚠️', 'Vui lòng chọn hoặc nhập ít nhất 1 GPM Profile!');
    return;
  }
  const apiUrl = document.getElementById('gpm-apiUrl').value.trim();
  for (const pid of pids) {
    try {
      await fetch('/api/gpm/profile/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: pid, api_url: apiUrl })
      });
    } catch (e) {}
  }
  showToast('✅', `Đã gửi lệnh đóng GPM Profile!`);
}

async function gpmLoadAccounts() {
  try {
    const r = await fetch('/api/gpm/accounts?session=true');
    const d = await r.json();
    const tbody = document.getElementById('gpm-accountsBody');
    if (!tbody) return;
    if (!d.accounts || d.accounts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:20px;">Chưa có tài khoản nào</td></tr>';
      return;
    }
    tbody.innerHTML = d.accounts.map(a => `
      <tr>
        <td style="font-family:monospace;font-size:11px;">${escHtml(a.uid || '—')}</td>
        <td style="font-family:monospace;font-size:11px;">${escHtml(a.email)}</td>
        <td style="font-family:monospace;font-size:11px;color:var(--muted);">${escHtml(a.password)}</td>
        <td><span style="color:var(--green);font-size:11px;">✅ OK ${a.join_link ? '🔗' : ''}</span></td>
      </tr>
    `).join('');
  } catch (e) {}
}

async function gpmCopyAccounts() {
  try {
    const r = await fetch('/api/capcut/accounts/raw?session=true');
    const t = await r.text();
    await navigator.clipboard.writeText(t);
    showToast('📋', 'Đã copy tất cả thông tin!');
  } catch (e) {}
}

async function gpmCopyAccountsEP() {
  try {
    const r = await fetch('/api/capcut/accounts/raw_ep?session=true');
    const t = await r.text();
    await navigator.clipboard.writeText(t);
    showToast('📋', 'Đã copy Email|Password!');
  } catch (e) {}
}

async function gpmCopyAccountsEPL() {
  try {
    const r = await fetch('/api/capcut/accounts/raw_epl?session=true');
    const t = await r.text();
    await navigator.clipboard.writeText(t);
    showToast('📋', 'Đã copy Email|Password|Link!');
  } catch (e) {}
}

async function gpmClearAccounts() {
  showConfirmModal('Xóa tài khoản GPM CapCut', 'Bạn có chắc chắn muốn xóa danh sách tài khoản GPM đã tạo?', async () => {
    try {
      await fetch('/api/gpm/accounts/clear', { method: 'POST' });
      showToast('🗑️', 'Đã xóa danh sách GPM accounts!');
      gpmLoadAccounts();
    } catch (e) {}
  });
}

async function gpmStartTask() {
  if (gpmIsRunning) return;
  const pids = gpmGetSelectedProfileIds();
  if (pids.length === 0) {
    showToast('⚠️', 'Vui lòng chọn hoặc nhập ít nhất 1 GPM Profile ID!');
    return;
  }
  const threads = parseInt(document.getElementById('gpm-threads').value) || 1;
  const joinLink = document.getElementById('gpm-joinLink') ? document.getElementById('gpm-joinLink').value.trim() : '';
  const apiUrl = document.getElementById('gpm-apiUrl').value.trim();

  gpmOk = 0; gpmFail = 0; gpmTotal = pids.length; gpmUpdateStats();
  
  const payload = {
    profile_ids: pids,
    threads: threads,
    mail_type: gpmMailType,
    mail_api_source: gpmApiSource,
    mode: gpmMode,
    join_link: joinLink,
    gpm_api_url: apiUrl
  };

  const r = await fetch('/api/gpm/task/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const d = await r.json();
  if (!d.success) {
    showToast('❌', d.error || 'Lỗi khởi chạy');
    return;
  }
  gpmIsRunning = true;
  gpmSetUI(true);
  gpmStartSSE();
  showToast('🚀', `Đã bắt đầu Reg CapCut trên ${pids.length} GPM Profiles!`);
}

async function gpmStopTask() {
  gpmIsRunning = false;
  gpmSetUI(false);
  if (gpmEvt) gpmEvt.close();
  await fetch('/api/gpm/task/stop', { method: 'POST' });
  showToast('⏹', 'Đã dừng GPM Task.');
}

function gpmCloseBrowsers() {
  fetch('/api/capcut/task/close_browsers', { method: 'POST' });
  showToast('💥', 'Đã đóng tất cả trình duyệt!');
}

function gpmStartSSE() {
  if (gpmEvt) gpmEvt.close();
  gpmEvt = new EventSource('/api/gpm/task/stream');
  gpmEvt.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'log') gpmAddLog(data);
    else if (data.type === 'result') {
      if (data.success) gpmOk++; else gpmFail++;
      gpmUpdateStats();
      if (data.success) gpmLoadAccounts();
    }
    else if (data.type === 'done') {
      gpmIsRunning = false; gpmSetUI(false); gpmEvt.close();
      showToast('✅', 'GPM Task hoàn tất!');
      gpmLoadAccounts();
    }
    else if (data.type === 'stopped') {
      gpmIsRunning = false; gpmSetUI(false); gpmEvt.close();
      showToast('⏹', 'GPM Task đã dừng.');
    }
  };
}

function gpmAddLog(data) {
  gpmLogs.push(data);
  if (gpmLogs.length > 2000) gpmLogs.shift();
  if (gpmFilter === 'ALL' || data.level === gpmFilter) gpmRenderLog(data);
}

function gpmRenderLog(data) {
  const wrap = document.getElementById('gpm-logWrap');
  if (!wrap) return;
  const icons = { OK: '✅', ERR: '❌', WARN: '⚠️', INFO: '📌' };
  const classes = { OK: 'log-ok', ERR: 'log-err', WARN: 'log-warn', INFO: 'log-info' };
  const div = document.createElement('div');
  div.className = 'log-entry ' + (classes[data.level] || 'log-info');
  div.innerHTML = `<span class="log-time">${data.time}</span><span class="log-icon">${icons[data.level] || '📌'}</span><span class="log-msg">${escHtml(data.msg)}</span>`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
}

function gpmUpdateStats() {
  document.getElementById('gpm-statOk').textContent = gpmOk;
  document.getElementById('gpm-statFail').textContent = gpmFail;
  const pct = gpmTotal > 0 ? Math.round(((gpmOk + gpmFail) / gpmTotal) * 100) : 0;
  document.getElementById('gpm-statPct').textContent = pct + '%';
  document.getElementById('gpm-progressBar').style.width = pct + '%';
}

function gpmSetUI(running) {
  document.getElementById('gpm-startBtn').style.display = running ? 'none' : 'inline-block';
  document.getElementById('gpm-stopBtn').style.display = running ? 'inline-block' : 'none';
  const dot = document.getElementById('gpm-statusDot'), txt = document.getElementById('gpm-statusText');
  if (running) { dot.className = 'dot running'; txt.textContent = 'Đang chạy...'; }
  else { dot.className = 'dot'; txt.textContent = 'Idle'; }
}
/* ── MAIL LIST PERSISTENCE & MODAL POPUP ───────────────────── */

let activeTextareaForModal = 'gpm-manualPids';

function initAutoSaveMailInput(textareaId, storageKey) {
  const el = document.getElementById(textareaId);
  if (!el) return;

  const saved = localStorage.getItem(storageKey);
  if (saved && !el.value) {
    el.value = saved;
    el.dispatchEvent(new Event('input'));
  }

  el.addEventListener('input', () => {
    localStorage.setItem(storageKey, el.value);
  });
}

function openMailListModal(textareaId = 'gpm-manualPids') {
  activeTextareaForModal = textareaId;
  const modal = document.getElementById('mailListModal');
  if (modal) {
    modal.style.display = 'flex';
    loadSavedMailLists();
  }
}

function closeMailListModal() {
  const modal = document.getElementById('mailListModal');
  if (modal) modal.style.display = 'none';
}

async function loadSavedMailLists() {
  const tbody = document.getElementById('modalMailListsTbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:15px;color:#64748b;">Đang nạp danh sách...</td></tr>';

  try {
    const res = await fetch('/api/maillists');
    const d = await res.json();
    if (!d.success || !d.data || d.data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:15px;color:#64748b;">Chưa có danh sách nào được lưu trong Database</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    window._savedMailListsMap = {};
    d.data.forEach(item => {
      window._savedMailListsMap[item.id] = item.content;
      const tr = document.createElement('tr');
      tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
      const dt = item.created_at ? item.created_at.slice(0, 16).replace('T', ' ') : '';
      tr.innerHTML = `
        <td style="padding:8px 10px;font-weight:600;color:#e2e8f0;">${escHtml(item.title)}</td>
        <td style="padding:8px 10px;font-family:monospace;color:#00d4ff;">${item.item_count} dòng</td>
        <td style="padding:8px 10px;color:#64748b;font-size:10px;">${dt}</td>
        <td style="padding:8px 10px;text-align:right;">
          <button onclick="applySavedMailList(${item.id})" style="padding:3px 8px;border-radius:4px;border:none;background:rgba(16,185,129,0.15);color:#10b981;font-weight:600;font-size:10px;cursor:pointer;margin-right:4px;">📥 Nạp</button>
          <button onclick="deleteSavedMailList(${item.id})" style="padding:3px 8px;border-radius:4px;border:none;background:rgba(239,68,68,0.15);color:#ef4444;font-weight:600;font-size:10px;cursor:pointer;">🗑️ Xóa</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:15px;color:#ef4444;">Lỗi kết nối API lưu danh sách</td></tr>';
  }
}

async function saveCurrentMailListFromModal() {
  const el = document.getElementById(activeTextareaForModal) || document.getElementById('gpm-manualPids');
  const content = el ? el.value.trim() : '';
  if (!content) {
    showToast('❌', 'Vui lòng nhập nội dung email/token vào ô trước khi bấm Lưu!');
    return;
  }
  const titleInput = document.getElementById('modalSaveTitle');
  const title = titleInput ? titleInput.value.trim() : '';

  try {
    const res = await fetch('/api/maillists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content, mail_type: 'capcut' })
    });
    const d = await res.json();
    if (d.success) {
      if (titleInput) titleInput.value = '';
      loadSavedMailLists();
      showToast('💾', 'Đã lưu danh sách mail vào Database!');
    } else {
      showToast('❌', 'Lỗi lưu: ' + (d.error || ''));
    }
  } catch (e) {
    showToast('❌', 'Lỗi kết nối khi lưu danh sách mail');
  }
}

function applySavedMailList(listId) {
  const content = window._savedMailListsMap ? window._savedMailListsMap[listId] : null;
  if (!content) return;

  const el = document.getElementById(activeTextareaForModal) || document.getElementById('gpm-manualPids');
  if (el) {
    el.value = content;
    el.dispatchEvent(new Event('input'));
    localStorage.setItem('gpm_manual_pids_autosave', content);
    closeMailListModal();
    showToast('✅', 'Đã nạp danh sách mail vào Form thành công!');
  }
}

async function deleteSavedMailList(listId) {
  if (!confirm('Bạn có chắc muốn xóa danh sách này khỏi Database?')) return;
  try {
    const res = await fetch(`/api/maillists/${listId}`, { method: 'DELETE' });
    const d = await res.json();
    if (d.success) {
      loadSavedMailLists();
      showToast('🗑️', 'Đã xóa danh sách mail khỏi Database!');
    }
  } catch (e) {
    showToast('❌', 'Lỗi kết nối khi xóa danh sách mail');
  }
}


document.addEventListener('DOMContentLoaded', () => {
  initAutoSaveMailInput('gpm-manualPids', 'gpm_manual_pids_autosave');
});


