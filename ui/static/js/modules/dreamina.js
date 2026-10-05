// ======================= DREAMINA =======================
let drmIsRunning = false;
let drmEvt = null;
let drmOk = 0, drmFail = 0, drmTotal = 0;
let drmApiSource = 'dongvanfb';
let drmBrowserType = 'chrome';
let drmHeadless = false;
let drmFilter = 'ALL';
let drmSessionAccounts = [];
let drmAccountsTab = 'session';

function drmSetAccountsTab(tab) {
  drmAccountsTab = tab;
  document.getElementById('drm-tabAccountsSession').classList.toggle('active', tab === 'session');
  document.getElementById('drm-tabAccountsAll').classList.toggle('active', tab === 'all');
  drmLoadAccounts();
}

function drmSetApiSource(src) {
  drmApiSource = src;
  ['dongvanfb','mixmmo'].forEach(s => {
    const el = document.getElementById(`drm-source${s.charAt(0).toUpperCase()+s.slice(1)}`);
    if(el) el.classList.toggle('active', s === src);
  });
}

function drmSetBrowser(b) {
  drmBrowserType = b;
  ['Chrome','Firefox','Camoufox'].forEach(s => {
    const el = document.getElementById(`drm-browser${s}`);
    if(el) el.classList.toggle('active', s.toLowerCase() === b.toLowerCase());
  });
}

function drmToggleHeadless() {
  drmHeadless = !drmHeadless;
  const btn = document.getElementById('drm-headlessToggle');
  if(btn) btn.classList.toggle('active', drmHeadless);
}

function drmSetFilter(f, btn) {
  drmFilter = f;
  document.querySelectorAll('#drm-logWrap').forEach(() => {});
  document.querySelectorAll('.log-filter-btn').forEach(b => {
    if(b.closest('#tab-dreamina')) b.classList.remove('active');
  });
  if(btn) btn.classList.add('active');
  document.querySelectorAll('#drm-logWrap .log-entry').forEach(el => {
    if(f === 'ALL') el.style.display = '';
    else el.style.display = el.classList.contains('log-' + f.toLowerCase()) ? '' : 'none';
  });
}

function drmClearLog() {
  const wrap = document.getElementById('drm-logWrap');
  if(wrap) wrap.innerHTML = '<div class="log-entry log-info"><span class="log-time">--:--:--</span><span class="log-icon">📌</span><span class="log-msg">Log đã được xóa.</span></div>';
}

function drmAddLog(time, level, msg) {
  const wrap = document.getElementById('drm-logWrap');
  if(!wrap) return;
  const cls = {OK:'ok',WARN:'warn',ERR:'err',INFO:'info'}[level] || 'info';
  const icon = {OK:'✅',WARN:'⚠️',ERR:'❌',INFO:'📌'}[level] || '📌';
  const el = document.createElement('div');
  el.className = `log-entry log-${cls}`;
  el.innerHTML = `<span class="log-time">${escHtml(time)}</span><span class="log-icon">${icon}</span><span class="log-msg">${escHtml(msg)}</span>`;
  if(drmFilter !== 'ALL' && !el.classList.contains('log-' + drmFilter.toLowerCase())) el.style.display = 'none';
  wrap.appendChild(el);
  wrap.scrollTop = wrap.scrollHeight;
}

async function drmLoadHotmailCount() {
  try {
    const r = await fetch('/api/dreamina/hotmail/count');
    const d = await r.json();
    const n = d.count || 0;
    ['drm-hotmailCountLabel','drm-hotmailCountBadge','drm-statHotmail'].forEach(id => {
      const el = document.getElementById(id);
      if(el) el.textContent = n;
    });
  } catch(e) {}
}

async function drmUploadHotmail(input) {
  if(!input.files[0]) return;
  // Đọc file và hiển thị lên textarea
  const reader = new FileReader();
  reader.onload = async (e) => {
    const text = e.target.result.trim();
    const ta = document.getElementById('drm-hotmailTextarea');
    if(ta) { ta.value = text; drmCountTextareaLines(); }
    // Tự động lưu luôn
    await drmSaveHotmailFromTextarea();
  };
  reader.readAsText(input.files[0]);
  input.value = ''; // reset để có thể upload lại cùng file
}

async function drmSaveHotmailFromTextarea() {
  const ta = document.getElementById('drm-hotmailTextarea');
  if(!ta) return;
  const lines = ta.value.trim().split('\n').filter(l => l.trim() && l.includes('|'));
  if(!lines.length) { showToast('⚠️', 'Chưa có dòng hotmail hợp lệ nào (cần dạng email|pass|token|id)!'); return; }
  const blob = new Blob([lines.join('\n') + '\n'], {type: 'text/plain'});
  const fd = new FormData();
  fd.append('file', blob, 'hotmails.txt');
  try {
    const r = await fetch('/api/dreamina/hotmail/upload', {method:'POST', body:fd});
    const d = await r.json();
    showToast('💾', `Đã lưu ${d.count} hotmail vào file!`);
    drmLoadHotmailCount();
  } catch(e) { showToast('❌', 'Lỗi lưu!'); }
}

function drmCountTextareaLines() {
  const ta = document.getElementById('drm-hotmailTextarea');
  if(!ta) return;
  const count = ta.value.split('\n').filter(l => l.trim() && l.includes('|')).length;
  ['drm-hotmailCountLabel'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.textContent = count;
  });
}

async function drmStartTask() {
  if(drmIsRunning) return;
  const count = parseInt(document.getElementById('drm-count').value) || 4;
  const threads = parseInt(document.getElementById('drm-threads').value) || 2;

  try {
    const r = await fetch('/api/dreamina/task/start', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({count, threads, headless:drmHeadless, browser_type:drmBrowserType, mail_api_source:drmApiSource})
    });
    const d = await r.json();
    if(!d.success) { showToast('❌', d.error || 'Lỗi!'); return; }
  } catch(e) { showToast('❌', 'Lỗi kết nối!'); return; }

  drmIsRunning = true;
  drmOk = 0; drmFail = 0; drmTotal = count;
  drmSessionAccounts = [];
  document.getElementById('drm-startBtn').style.display = 'none';
  document.getElementById('drm-stopBtn').style.display = '';
  document.getElementById('drm-statusDot').className = 'dot dot-running';
  document.getElementById('drm-statusText').textContent = 'Running';
  document.getElementById('drm-statOk').textContent = '0';
  document.getElementById('drm-statFail').textContent = '0';
  document.getElementById('drm-statPct').textContent = '0%';
  document.getElementById('drm-progressBar').style.width = '0%';

  if(drmEvt) drmEvt.close();
  drmEvt = new EventSource('/api/dreamina/task/stream');
  drmEvt.onmessage = e => {
    try {
      const msg = JSON.parse(e.data);
      if(msg.type === 'log') {
        drmAddLog(msg.time, msg.level, msg.msg);
      } else if(msg.type === 'result') {
        if(msg.success) drmOk++; else drmFail++;
        const done = drmOk + drmFail;
        const pct = drmTotal ? Math.round(done/drmTotal*100) : 0;
        document.getElementById('drm-statOk').textContent = drmOk;
        document.getElementById('drm-statFail').textContent = drmFail;
        document.getElementById('drm-statPct').textContent = pct + '%';
        document.getElementById('drm-progressBar').style.width = pct + '%';
      } else if(msg.type === 'account') {
        drmSessionAccounts.push(msg);
        drmRenderSessionAccounts();
      } else if(msg.type === 'done' || msg.type === 'stopped') {
        drmIsRunning = false;
        if(drmEvt) { drmEvt.close(); drmEvt = null; }
        document.getElementById('drm-startBtn').style.display = '';
        document.getElementById('drm-stopBtn').style.display = 'none';
        document.getElementById('drm-statusDot').className = 'dot';
        document.getElementById('drm-statusText').textContent = msg.type === 'stopped' ? 'Stopped' : 'Done';
        drmLoadHotmailCount();
        drmLoadAccounts();
        showToast('✅', `Dreamina: ${drmOk} OK / ${drmFail} lỗi`);
      }
    } catch(err) {}
  };
  drmEvt.onerror = () => {
    if(!drmIsRunning) { if(drmEvt) drmEvt.close(); }
  };
}

async function drmStopTask() {
  try { await fetch('/api/dreamina/task/stop', {method:'POST'}); } catch(e) {}
  drmIsRunning = false;
  if(drmEvt) { drmEvt.close(); drmEvt = null; }
  document.getElementById('drm-startBtn').style.display = '';
  document.getElementById('drm-stopBtn').style.display = 'none';
  document.getElementById('drm-statusDot').className = 'dot';
  document.getElementById('drm-statusText').textContent = 'Stopped';
}

async function drmCloseBrowsers() {
  try { await fetch('/api/dreamina/task/close_browsers', {method:'POST'}); showToast('✅', 'Đã đóng trình duyệt!'); }
  catch(e) { showToast('❌', 'Lỗi!'); }
}

function drmRenderSessionAccounts() {
  const tbody = document.getElementById('drm-accountsBody');
  if(!tbody) return;
  if(!drmSessionAccounts.length) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--muted);padding:20px;">Chưa có tài khoản nào</td></tr>';
    return;
  }
  tbody.innerHTML = drmSessionAccounts.map(a => `
    <tr>
      <td style="font-family:'JetBrains Mono',monospace;">${escHtml(a.email||'')}</td>
      <td style="font-family:'JetBrains Mono',monospace;">${escHtml(a.password||'')}</td>
      <td><span style="color:var(--green);font-size:11px;">✅ OK</span></td>
    </tr>`).join('');
}

async function drmLoadAccounts() {
  try {
    const r = await fetch('/api/dreamina/accounts?session=' + (drmAccountsTab === 'session'));
    const d = await r.json();
    const tbody = document.getElementById('drm-accountsBody');
    if (!tbody) return;
    const accounts = d.accounts || [];
    if (!accounts.length) {
      tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--muted);padding:20px;">Chưa có tài khoản nào</td></tr>';
      return;
    }
    tbody.innerHTML = accounts.slice().reverse().slice(0, 50).map(a => `
      <tr>
        <td style="font-family:'JetBrains Mono',monospace;color:var(--text);">${escHtml(a.email || '')}</td>
        <td><code style="color:var(--muted)">${escHtml(a.password || '')}</code></td>
        <td>
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="tag tag-ok" style="margin:0;">✅ OK</span>
            <button class="copy-btn" title="Copy Email | Pass" onclick="navigator.clipboard.writeText('${escHtml(a.email)}\\t${escHtml(a.password)}');showToast('📋','Đã copy!');">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            </button>
          </div>
        </td>
      </tr>`).join('');
  } catch (e) {}
}

async function drmCopyAccounts() {
  try {
    const r = await fetch('/api/dreamina/accounts/raw?session=' + (drmAccountsTab === 'session'));
    const text = await r.text();
    if (!text.trim()) { showToast('⚠️', 'Không có dữ liệu!'); return; }
    await navigator.clipboard.writeText(text);
    showToast('📋', 'Đã copy tài khoản Dreamina (Full)!');
  } catch (e) { showToast('❌', 'Lỗi copy!'); }
}

async function drmCopyAccountsEP() {
  try {
    const r = await fetch('/api/dreamina/accounts/raw_ep?session=' + (drmAccountsTab === 'session'));
    const text = await r.text();
    if (!text.trim()) { showToast('⚠️', 'Không có dữ liệu!'); return; }
    await navigator.clipboard.writeText(text);
    showToast('📋', 'Đã copy (Email|Pass)!');
  } catch (e) { showToast('❌', 'Lỗi copy!'); }
}

async function drmClearAccounts() {
  showConfirmModal('Xóa tài khoản Dreamina', 'Bạn có chắc chắn muốn xóa toàn bộ danh sách tài khoản Dreamina đã tạo?', async () => {
    try {
      await fetch('/api/dreamina/accounts/clear', { method: 'POST' });
      showToast('🗑️', 'Đã xóa danh sách!');
      drmLoadAccounts();
    } catch (e) {}
  });
}

// Load on init
drmLoadHotmailCount();
drmLoadAccounts();

// Textarea live count
const _drmTa = document.getElementById('drm-hotmailTextarea');
if(_drmTa) _drmTa.addEventListener('input', drmCountTextareaLines);

function gptFilterAccounts() {
    const input = document.getElementById('gptSearchInput');
    const badgeSelect = document.getElementById('gptBadgeFilter');
    const textFilter = input ? input.value.toLowerCase().trim() : '';
    const badgeFilter = badgeSelect ? badgeSelect.value : 'all';
    
    const tbody = document.getElementById('gpt-accountsBody');
    if (!tbody) return;
    const trs = tbody.getElementsByTagName('tr');
    
    let visibleCount = 0;
    for (let i = 0; i < trs.length; i++) {
        // Skip the empty/colspan rows
        if (trs[i].cells.length === 1 && trs[i].cells[0].colSpan > 1) {
            continue;
        }
        
        const tds = trs[i].getElementsByTagName('td');
        if (!tds.length) continue;
        
        // Badge filter: dựa vào nội dung text của cột MoMo (index 3) và Ưu Đãi (index 4)
        let badgeMatch = true;
        if (badgeFilter !== 'all') {
            const momoText = (tds[3] ? tds[3].textContent : '').toLowerCase();
            const trialText = (tds[4] ? tds[4].textContent : '').toLowerCase();
            const hasMomo = momoText.includes('momo');
            const hasTrial = trialText.includes('có trial') || trialText.includes('gói 0') || /(?:^|\D)0\s*đ/.test(trialText);
            const hasApplePayOnly = momoText.includes('apple pay only');
            const hasGooglePay = momoText.includes('google pay');
            
            if (badgeFilter === 'momo') badgeMatch = hasMomo;
            else if (badgeFilter === 'trial') badgeMatch = hasTrial;
            else if (badgeFilter === 'momo_trial') badgeMatch = hasMomo && hasTrial;
            else if (badgeFilter === 'trial_no_momo') badgeMatch = hasTrial && !hasMomo;
            else if (badgeFilter === 'apple_pay_only') badgeMatch = hasApplePayOnly;
            else if (badgeFilter === 'google_pay_present') badgeMatch = hasGooglePay;
            else if (badgeFilter === 'trial_apple_pay_only') badgeMatch = hasTrial && hasApplePayOnly;
        }
        
        // Text filter
        let textMatch = true;
        if (textFilter) {
            textMatch = false;
            for (let j = 0; j < tds.length; j++) {
                if (tds[j] && (tds[j].textContent || tds[j].innerText).toLowerCase().indexOf(textFilter) > -1) {
                    textMatch = true;
                    break;
                }
            }
        }
        
        const visible = badgeMatch && textMatch;
        trs[i].style.display = visible ? '' : 'none';
        if (visible) visibleCount++;
    }
    
    // Cập nhật label nút Copy
    const copyFilteredBtn = document.getElementById('gptCopyBtn');
    if (copyFilteredBtn && (badgeFilter !== 'all' || textFilter)) {
        copyFilteredBtn.textContent = `📋 Copy (${visibleCount})`;
        copyFilteredBtn.style.color = '#00d4ff';
        copyFilteredBtn.style.borderColor = 'rgba(0, 212, 255, 0.35)';
        copyFilteredBtn.style.background = 'rgba(0, 212, 255, 0.15)';
    } else if (copyFilteredBtn) {
        copyFilteredBtn.textContent = '📋 Copy';
        copyFilteredBtn.style.color = '';
        copyFilteredBtn.style.borderColor = '';
        copyFilteredBtn.style.background = '';
    }
}

