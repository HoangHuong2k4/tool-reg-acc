// ==== CAPCUT PRO CHECKER (UNIVERSAL: HOTMAIL & ATOMICMAIL) ====
let cpIsRunning = false;
let cpEvt = null;
let cpLogs = [];
let cpFilter = 'ALL';
let cpResults = [];

function cpSetUI(running) {
  cpIsRunning = running;
  const startBtn = document.getElementById('cp-startBtn');
  const stopBtn = document.getElementById('cp-stopBtn');
  const dot = document.getElementById('cp-statusDot');
  const text = document.getElementById('cp-statusText');

  if (startBtn) startBtn.style.display = running ? 'none' : 'block';
  if (stopBtn) stopBtn.style.display = running ? 'block' : 'none';
  if (dot) dot.className = 'dot ' + (running ? 'running' : '');
  if (text) text.textContent = running ? 'Đang quét...' : 'Idle';
}

function cpUpdateCount() {
  const input = document.getElementById('cp-accountsInput');
  if (!input) return;
  const lines = input.value.split('\n').filter(l => l.trim().length > 0);
  const lbl = document.getElementById('cp-accCountLabel');
  if (lbl) lbl.textContent = `${lines.length} tài khoản`;
}

function cpClearInput() {
  const input = document.getElementById('cp-accountsInput');
  if (input) {
    input.value = '';
    cpUpdateCount();
  }
}

async function cpLoadFromFile(fileInput) {
  const file = fileInput.files && fileInput.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    const content = e.target.result;
    const input = document.getElementById('cp-accountsInput');
    if (input) {
      input.value = content;
      cpUpdateCount();
      showToast('📂', `Đã nạp file: ${file.name}`);
    }
  };
  reader.readAsText(file);
  fileInput.value = '';
}

async function cpLoadFromCapcutDb() {
  try {
    showToast('⏳', 'Đang tải từ CapCut DB...');
    const r = await fetch('/api/checkpro/capcut_accounts');
    const d = await r.json();
    if (d.success && d.accounts) {
      const input = document.getElementById('cp-accountsInput');
      if (input) {
        input.value = d.accounts;
        cpUpdateCount();
        showToast('📥', `Đã nạp ${d.count} tài khoản từ CapCut DB!`);
      }
    } else {
      showToast('⚠️', d.error || 'Chưa có tài khoản nào!');
    }
  } catch (e) {
    showToast('❌', 'Lỗi kết nối máy chủ!');
  }
}

async function cpLoadFromHotmailsTxt() {
  try {
    showToast('⏳', 'Đang tải data/hotmails.txt...');
    const r = await fetch('/api/checkpro/hotmails_txt');
    const d = await r.json();
    if (d.success && d.accounts) {
      const input = document.getElementById('cp-accountsInput');
      if (input) {
        input.value = d.accounts;
        cpUpdateCount();
        showToast('📧', `Đã nạp ${d.count} tài khoản từ data/hotmails.txt!`);
      }
    } else {
      showToast('⚠️', d.error || 'Không tìm thấy file hotmails.txt!');
    }
  } catch (e) {
    showToast('❌', 'Lỗi nạp file hotmails.txt!');
  }
}

function cpUpdateStats(stats) {
  if (!stats) return;
  const total = document.getElementById('cp-statTotal');
  const done = document.getElementById('cp-statDone');
  const found = document.getElementById('cp-statFound');
  const refunded = document.getElementById('cp-statRefunded');
  const fail = document.getElementById('cp-statFail');

  if (total && stats.total !== undefined) total.textContent = stats.total;
  if (done && stats.done !== undefined) done.textContent = stats.done;
  if (found && stats.found !== undefined) found.textContent = stats.found;
  if (refunded && stats.refunded !== undefined) refunded.textContent = stats.refunded;
  if (fail && stats.fail !== undefined) fail.textContent = stats.fail;
}

function cpAddLog(time, level, msg) {
  cpLogs.push({ time, level, msg });
  const wrap = document.getElementById('cp-logWrap');
  if (!wrap) return;

  // Lựa chọn icon và style đồng nhất, tránh double icon
  let icon = '📌';
  let cls = 'log-info';
  let normLevel = 'INFO';

  if (level === 'OK' || msg.includes('🟢') || msg.includes('Active Pro')) {
    icon = '🟢';
    cls = 'log-ok';
    normLevel = 'OK';
  } else if (level === 'WARN' || msg.includes('⚠️') || msg.includes('HOÀN TIỀN') || msg.includes('hoàn tiền') || msg.includes('HỦY')) {
    icon = '⚠️';
    cls = 'log-warn';
    normLevel = 'WARN';
  } else if (level === 'ERR' || msg.includes('❌') || msg.includes('Lỗi')) {
    icon = '❌';
    cls = 'log-err';
    normLevel = 'ERR';
  } else if (msg.includes('🚀') || msg.includes('Bắt đầu')) {
    icon = '🚀';
    cls = 'log-info';
    normLevel = 'INFO';
  } else if (msg.includes('🏁') || msg.includes('HOÀN TẤT')) {
    icon = '🏁';
    cls = 'log-ok';
    normLevel = 'OK';
  }

  // Tẩy icon trùng lặp ở đầu msg nếu đã có icon đứng trước
  let cleanMsg = msg;
  ['🟢', '✅', '⚠️', '❌', '📌', '🚀', '🏁'].forEach(em => {
    if (cleanMsg.startsWith(em + ' ')) cleanMsg = cleanMsg.slice(2);
    else if (cleanMsg.startsWith(em)) cleanMsg = cleanMsg.slice(1);
  });

  const div = document.createElement('div');
  div.className = `log-entry ${cls}`;
  div.dataset.level = normLevel;
  div.innerHTML = `<span class="log-time">${time}</span><span class="log-icon">${icon}</span><span class="log-msg">${escHtml(cleanMsg.trim())}</span>`;

  if (cpFilter !== 'ALL' && normLevel !== cpFilter) {
    div.style.display = 'none';
  }

  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
}

function cpSetFilter(filter, btn) {
  cpFilter = filter;
  document.querySelectorAll('#tab-checkpro .log-filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  const entries = document.querySelectorAll('#cp-logWrap .log-entry');
  entries.forEach(e => {
    if (filter === 'ALL') {
      e.style.display = 'flex';
      return;
    }
    const lvl = (e.dataset.level || '').toUpperCase();
    const text = (e.textContent || '').toLowerCase();
    let match = false;
    if (filter === 'WARN') {
      match = (lvl === 'WARN' || lvl === 'WARNING' || text.includes('hoàn tiền') || text.includes('hủy') || text.includes('refund') || text.includes('⚠️'));
    } else if (filter === 'OK') {
      match = (lvl === 'OK' || lvl === 'SUCCESS' || text.includes('active pro') || text.includes('tìm thấy') || text.includes('hoàn tất') || text.includes('🟢'));
    } else if (filter === 'ERR') {
      match = (lvl === 'ERR' || lvl === 'ERROR' || text.includes('lỗi') || text.includes('thất bại') || text.includes('❌'));
    }
    e.style.display = match ? 'flex' : 'none';
  });
}

function cpClearLog() {
  cpLogs = [];
  const wrap = document.getElementById('cp-logWrap');
  if (wrap) wrap.innerHTML = '';
}

// Trạng thái lọc bảng kết quả: 'ALL' | 'FOUND' | 'REFUNDED' | 'FAIL'
let cpTableStatusFilter = 'ALL';

function cpSetTableStatusFilter(status, btn) {
  cpTableStatusFilter = status;
  // Cập nhật giao diện active cho các nút tab trên bảng
  document.querySelectorAll('.cp-tab-btn').forEach(b => {
    if (b.dataset.filter === status) {
      b.classList.add('active');
      b.style.color = 'var(--text)';
      b.style.fontWeight = '600';
    } else {
      b.classList.remove('active');
      b.style.color = 'var(--muted)';
      b.style.fontWeight = 'normal';
    }
  });
  cpFilterTable();
}

function cpToggleMode() {
  const mode = document.getElementById('cp-checkMode')?.value || 'mail';
  const mailRow = document.getElementById('cp-mailConfigRow');
  const webRow = document.getElementById('cp-webConfigRow');
  if (mode === 'web') {
    if (mailRow) mailRow.style.display = 'none';
    if (webRow) webRow.style.display = 'block';
  } else {
    if (mailRow) mailRow.style.display = 'flex';
    if (webRow) webRow.style.display = 'none';
  }
}

function cpRenderTableRow(r, idx) {
  let badgeHtml = '';
  if (r.status === 'FOUND') {
    badgeHtml = '<span style="background:rgba(16,185,129,0.18);color:#34d399;border:1px solid rgba(16,185,129,0.3);padding:2px 8px;border-radius:4px;font-weight:600;font-size:10.5px;white-space:nowrap;display:inline-block;">🟢 Pro monthly</span>';
  } else if (r.status === 'REFUNDED') {
    badgeHtml = '<span style="background:rgba(245,158,11,0.18);color:#fbbf24;border:1px solid rgba(245,158,11,0.3);padding:2px 8px;border-radius:4px;font-weight:600;font-size:10.5px;white-space:nowrap;display:inline-block;">⚠️ Đã hoàn tiền</span>';
  } else if (r.status === 'LOGIN_OK') {
    badgeHtml = '<span style="background:rgba(59,130,246,0.18);color:#60a5fa;border:1px solid rgba(59,130,246,0.3);padding:2px 8px;border-radius:4px;font-size:10.5px;white-space:nowrap;display:inline-block;">ℹ️ Chưa có Pro</span>';
  } else {
    badgeHtml = '<span style="background:rgba(239,68,68,0.18);color:#f87171;border:1px solid rgba(239,68,68,0.3);padding:2px 8px;border-radius:4px;font-size:10.5px;white-space:nowrap;display:inline-block;">❌ Lỗi</span>';
  }

  const dateStr = r.date ? r.date.replace('T', ' ').replace('.000Z', '').replace('Z', '') : '–';
  const mailboxName = r.type === 'capcut_web' ? '🌐 CapCut Web' : (r.type === 'hotmail' ? 'Hotmail OAuth' : (r.mailbox_id || 'AtomicMail'));

  return `
    <tr data-index="${idx}" style="border-bottom:1px solid var(--border);height:32px;">
      <td style="text-align:center;color:var(--muted);font-size:10px;">${idx + 1}</td>
      <td style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${escHtml(r.email)}">
        <span style="font-weight:500;font-size:11.5px;color:var(--text);">${escHtml(r.email)}</span>
      </td>
      <td style="text-align:center;white-space:nowrap;">${badgeHtml}</td>
      <td style="text-align:center;font-size:10px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${escHtml(r.mailbox_id || '')}">
        ${escHtml(mailboxName)}
      </td>
      <td style="text-align:center;font-size:10.5px;color:var(--yellow);white-space:nowrap;">${escHtml(dateStr)}</td>
      <td style="text-align:center;white-space:nowrap;">
        <div style="display:inline-flex;gap:4px;justify-content:center;align-items:center;">
          <button class="btn btn-secondary" style="height:22px;padding:0 6px;font-size:10px;line-height:20px;border-radius:4px;border-color:var(--accent);color:var(--accent);" onclick="cpShowDetail(${idx})" title="Xem chi tiết">👁</button>
          <button class="btn btn-secondary" style="height:22px;padding:0 6px;font-size:10px;line-height:20px;border-radius:4px;border-color:#38bdf8;color:#38bdf8;" onclick="cpLoginCheckSingle(${idx})" title="Mở trình duyệt tự đăng nhập CapCut để check tay">🌐 Login</button>
        </div>
      </td>
    </tr>
  `;
}

async function cpLoginCheckSingle(idx) {
  const r = cpResults[idx];
  if (!r || !r.email) return;

  const defaultPwd = (document.getElementById('cp-defaultPassword')?.value || 'capcut123').trim();
  const pwd = r.password || defaultPwd || 'capcut123';

  showToast('🌐', `Đang chạy ngầm kiểm tra CapCut cho ${r.email}...`, 3500);

  try {
    const res = await fetch('/api/checkpro/login_check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: r.email,
        password: pwd,
        headless: true
      })
    });
    const d = await res.json();
    if (!d.success) {
      showToast('❌', d.error || 'Lỗi khởi chạy');
    } else {
      showToast('🚀', `Đang kiểm tra ngầm cho ${r.email}! Vui lòng theo dõi log.`);
    }
  } catch(e) {
    showToast('❌', 'Lỗi kết nối máy chủ!');
  }
}

function cpAddRow(data) {
  // Nếu đã có dòng với email này thì cập nhật
  const existingIdx = cpResults.findIndex(r => r.email && data.email && r.email.toLowerCase() === data.email.toLowerCase());
  if (existingIdx >= 0) {
    cpResults[existingIdx] = Object.assign({}, cpResults[existingIdx], data);
  } else {
    cpResults.push(data);
  }
  cpFilterTable();
}

function cpFilterTable() {
  const query = (document.getElementById('cp-searchFilter')?.value || '').trim().toLowerCase();
  const tbody = document.getElementById('cp-resultsBody');
  if (!tbody) return;

  if (cpResults.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px;">Chưa có kết quả nào</td></tr>';
    return;
  }

  let html = '';
  let count = 0;
  cpResults.forEach((r, idx) => {
    // 1. Kiểm tra trạng thái lọc
    let statusMatch = true;
    if (cpTableStatusFilter === 'FOUND') {
      statusMatch = (r.status === 'FOUND');
    } else if (cpTableStatusFilter === 'REFUNDED') {
      statusMatch = (r.status === 'REFUNDED');
    } else if (cpTableStatusFilter === 'FAIL') {
      statusMatch = (r.status !== 'FOUND' && r.status !== 'REFUNDED');
    }

    // 2. Kiểm tra từ khóa tìm kiếm (email, ngày, nội dung thư, lỗi)
    const text = `${r.email} ${r.status_text} ${r.date} ${r.subject || ''} ${r.intro || ''} ${r.error || ''}`.toLowerCase();
    const queryMatch = (!query || text.includes(query));

    if (statusMatch && queryMatch) {
      html += cpRenderTableRow(r, idx);
      count++;
    }
  });

  const filterName = cpTableStatusFilter === 'REFUNDED' ? 'Đã hoàn tiền' : (cpTableStatusFilter === 'FOUND' ? 'Pro monthly' : (cpTableStatusFilter === 'FAIL' ? 'Lỗi/Không có' : ''));
  tbody.innerHTML = html || `<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px;">Không có tài khoản nào phù hợp bộ lọc ${filterName ? '(' + filterName + ')' : ''}</td></tr>`;
}

function cpShowDetail(idx) {
  const r = cpResults[idx];
  if (!r) return;

  document.getElementById('cp-modalEmail').textContent = r.email || '';
  document.getElementById('cp-modalStatus').textContent = r.status_text || r.status || '';
  document.getElementById('cp-modalDate').textContent = r.date || '–';
  document.getElementById('cp-modalFrom').textContent = r.from || '–';
  document.getElementById('cp-modalSubject').textContent = r.subject || '(Không có tiêu đề)';
  document.getElementById('cp-modalIntro').textContent = r.intro || r.error || '(Trống)';

  const modal = document.getElementById('cp-detailModal');
  if (modal) modal.style.display = 'flex';
}

function cpStartSSE() {
  if (cpEvt) cpEvt.close();
  cpEvt = new EventSource('/api/checkpro/stream');

  cpEvt.onmessage = function(e) {
    try {
      const data = JSON.parse(e.data);
      if (data.type === 'log') {
        cpAddLog(data.time, data.level, data.msg);
      } else if (data.type === 'row') {
        cpAddRow(data.data);
      } else if (data.type === 'stats') {
        cpUpdateStats(data.stats);
      } else if (data.type === 'done') {
        cpSetUI(false);
        cpUpdateStats(data.stats);
        showToast('🏁', 'Đã hoàn tất quét danh sách tài khoản!');
        if (cpEvt) cpEvt.close();
      }
    } catch (err) {}
  };
}

async function cpStart() {
  if (cpIsRunning) return;
  const accountsText = (document.getElementById('cp-accountsInput').value || '').trim();
  if (!accountsText) {
    showToast('⚠️', 'Vui lòng nhập hoặc nạp ít nhất 1 tài khoản!');
    return;
  }

  const keyword = (document.getElementById('cp-keyword')?.value || '').trim() || 'Pro monthly';
  const threads = parseInt(document.getElementById('cp-threads')?.value) || 3;
  const checkMode = document.getElementById('cp-checkMode')?.value || 'mail';
  const defaultPassword = (document.getElementById('cp-defaultPassword')?.value || 'capcut123').trim();

  cpResults = [];
  const tbody = document.getElementById('cp-resultsBody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px;">⏳ Đang kiểm tra...</td></tr>';
  cpClearLog();

  try {
    const res = await fetch('/api/checkpro/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        accounts: accountsText,
        keyword,
        threads,
        check_mode: checkMode,
        default_password: defaultPassword,
        headless: true
      })
    });
    const d = await res.json();
    if (!d.success) {
      showToast('❌', d.error || 'Lỗi khởi chạy');
      return;
    }

    cpSetUI(true);
    cpStartSSE();
    showToast('🚀', 'Đã bắt đầu quét tài khoản!');
  } catch (e) {
    showToast('❌', 'Lỗi kết nối máy chủ!');
  }
}

async function cpStop() {
  try {
    await fetch('/api/checkpro/stop', { method: 'POST' });
    showToast('⏹', 'Đã gửi yêu cầu dừng.');
    cpSetUI(false);
    if (cpEvt) cpEvt.close();
  } catch (e) {
    showToast('❌', 'Lỗi gửi yêu cầu dừng!');
  }
}

async function cpClearResults() {
  showConfirmModal('Xóa kết quả Check Pro', 'Bạn có chắc chắn muốn xóa toàn bộ danh sách kết quả vừa quét?', async () => {
    try {
      await fetch('/api/checkpro/clear', { method: 'POST' });
      cpResults = [];
      const tbody = document.getElementById('cp-resultsBody');
      if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px;">Chưa có kết quả nào</td></tr>';
      cpUpdateStats({ total: 0, done: 0, found: 0, refunded: 0, fail: 0 });
      showToast('🗑️', 'Đã xóa kết quả!');
    } catch (e) {}
  });
}

async function cpCopyPro() {
  const foundList = cpResults.filter(r => r.status === 'FOUND');
  if (foundList.length === 0) {
    showToast('⚠️', 'Chưa có tài khoản nào tìm thấy gói Pro active!');
    return;
  }
  const lines = foundList.map(r => `${r.email}\t${r.password || ''}\t${r.date || ''}`);
  await navigator.clipboard.writeText(lines.join('\n'));
  showToast('📋', `Đã copy ${foundList.length} tài khoản Pro (Email \\t Pass \\t Date)!`);
}

async function cpCopyRefunded() {
  const refList = cpResults.filter(r => r.status === 'REFUNDED');
  if (refList.length === 0) {
    showToast('⚠️', 'Không có tài khoản nào bị hoàn tiền!');
    return;
  }
  const lines = refList.map(r => `${r.email}\t${r.password || ''}\t${r.date || ''}\t${r.subject || ''}`);
  await navigator.clipboard.writeText(lines.join('\n'));
  showToast('📋', `Đã copy ${refList.length} tài khoản hoàn tiền!`);
}

async function cpCopyAll() {
  if (cpResults.length === 0) {
    showToast('⚠️', 'Chưa có kết quả nào để copy!');
    return;
  }
  const lines = cpResults.map(r => `${r.email}\t${r.password || ''}\t${r.status_text}\t${r.date || ''}\t${r.intro || r.error || ''}`);
  await navigator.clipboard.writeText(lines.join('\n'));
  showToast('📋', `Đã copy ${cpResults.length} dòng kết quả!`);
}

function cpExportCsv() {
  if (cpResults.length === 0) {
    showToast('⚠️', 'Chưa có kết quả nào để xuất!');
    return;
  }
  window.location.href = '/api/checkpro/export_csv';
}

document.addEventListener('DOMContentLoaded', () => {
  cpUpdateCount();
});
