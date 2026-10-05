// ==== MAILTEMP OTP MANAGER ====
let mtAllMailboxes = [];

function mtShowSection(show) {
  const sec = document.getElementById('cc-mailtempSection');
  if(sec) sec.style.display = show ? 'block' : 'none';
  if(show) mtLoadMailboxes();
}

async function mtLoadMailboxes() {
  try {
    const r = await fetch('/api/mailtemp/mailboxes');
    const d = await r.json();
    mtAllMailboxes = d.mailboxes || [];
    mtRenderMailboxes(mtAllMailboxes);
  } catch(e) { showToast('❌', 'Lỗi tải mailbox'); }
}

function mtFilterMailboxes() {
  const q = (document.getElementById('mt-searchInput').value || '').toLowerCase();
  const filtered = q ? mtAllMailboxes.filter(m => (m.email||'').toLowerCase().includes(q) || (m.capcut_email||'').toLowerCase().includes(q)) : mtAllMailboxes;
  mtRenderMailboxes(filtered);
}

function mtRenderMailboxes(list) {
  const tbody = document.getElementById('mt-mailboxBody');
  if(!list || list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:20px;">Chưa có mailbox nào được lưu</td></tr>';
    return;
  }
  tbody.innerHTML = list.map(m => {
    const ts = m.created_at ? m.created_at.replace('T',' ').substring(0,16) : '—';
    const ccAcc = m.capcut_email ? `<div style="font-size:10px;color:var(--accent);">${escHtml(m.capcut_email)}</div>` : '<span style="color:var(--muted);font-size:10px;">—</span>';
    return `<tr style="border-bottom:1px solid var(--border);">
      <td style="padding:7px 12px;font-size:11px;">
        <code style="color:var(--accent);font-size:10px;">${escHtml(m.email)}</code>
        <button class="copy-btn" title="Copy email" onclick="navigator.clipboard.writeText('${escHtml(m.email)}');showToast('📋','Đã copy email!');" style="margin-left:4px;">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        </button>
      </td>
      <td style="padding:7px 12px;font-size:11px;">
        <code style="color:var(--muted);font-size:10px;">${escHtml(m.password)}</code>
        <button class="copy-btn" title="Copy password" onclick="navigator.clipboard.writeText('${escHtml(m.password)}');showToast('📋','Đã copy pass!');" style="margin-left:4px;">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        </button>
      </td>
      <td style="padding:7px 12px;">${ccAcc}</td>
      <td style="padding:7px 12px;font-size:10px;color:var(--muted);">${ts}</td>
      <td style="padding:7px 12px;text-align:center;">
        <div style="display:flex;gap:6px;justify-content:center;">
          <button class="btn btn-secondary" style="width:auto;padding:3px 8px;font-size:10px;border-color:#6366f1;color:#6366f1;" onclick="mtGetOtp('${escHtml(m.email)}')">📨 Lấy OTP</button>
          <button class="btn btn-secondary" style="width:auto;padding:3px 8px;font-size:10px;border-color:var(--red);color:var(--red);" onclick="mtDeleteMailbox('${escHtml(m.email)}')">🗑️</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

async function mtGetOtp(email) {
  const modal = document.getElementById('mt-otpModal');
  const emailEl = document.getElementById('mt-otpModalEmail');
  const contentEl = document.getElementById('mt-otpModalContent');
  emailEl.textContent = email;
  contentEl.innerHTML = '<div style="text-align:center;color:var(--muted);padding:20px;">⏳ Đang lấy OTP...</div>';
  modal.style.display = 'flex';
  try {
    const r = await fetch(`/api/mailtemp/otp?email=${encodeURIComponent(email)}`);
    const d = await r.json();
    if(!d.success) {
      contentEl.innerHTML = `<div style="color:var(--red);padding:12px;">❌ ${escHtml(d.error||'Lỗi')}</div>`;
      return;
    }
    const otps = d.otps || [];
    const msgs = d.messages || [];
    if(otps.length > 0) {
      contentEl.innerHTML = `
        <div style="margin-bottom:12px;">
          <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">🔑 Mã OTP phát hiện được (${otps.length}):</div>
          ${otps.map(o => `
            <div style="background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);border-radius:8px;padding:10px 14px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;">
              <div>
                <div style="font-size:22px;font-weight:700;color:#a5b4fc;letter-spacing:3px;">${escHtml(o.code)}</div>
                <div style="font-size:10px;color:var(--muted);margin-top:2px;">Subject: ${escHtml(o.subject||'—')} · From: ${escHtml(o.from||'—')}</div>
              </div>
              <button class="btn btn-secondary" style="width:auto;padding:5px 12px;font-size:11px;" onclick="navigator.clipboard.writeText('${escHtml(o.code)}');showToast('✅','Đã copy OTP: ${escHtml(o.code)}');">📋 Copy</button>
            </div>
          `).join('')}
        </div>
        ${msgs.length > 0 ? `<details style="font-size:11px;color:var(--muted);">
          <summary style="cursor:pointer;margin-bottom:8px;">📩 Tất cả email (${msgs.length})</summary>
          ${msgs.map(m => `<div style="border:1px solid var(--border);border-radius:6px;padding:8px;margin-bottom:6px;">
            <div style="font-weight:600;">${escHtml(m.subject||'(no subject)')}</div>
            <div style="font-size:10px;color:var(--muted);">From: ${escHtml(m.from||m.sender||'—')}</div>
          </div>`).join('')}
        </details>` : ''}
      `;
    } else if(msgs.length > 0) {
      contentEl.innerHTML = `<div style="color:var(--muted);padding:12px;text-align:center;">📭 Có ${msgs.length} email nhưng không tìm thấy OTP</div>
        <div style="font-size:11px;">${msgs.map(m=>`<div style="border:1px solid var(--border);border-radius:6px;padding:8px;margin-bottom:6px;"><b>${escHtml(m.subject||'(no subject)')}</b><br><small>${escHtml(m.from||'')}</small></div>`).join('')}</div>`;
    } else {
      contentEl.innerHTML = '<div style="color:var(--muted);padding:20px;text-align:center;">📭 Hộp thư trống, chưa có email nào</div>';
    }
  } catch(e) {
    contentEl.innerHTML = `<div style="color:var(--red);padding:12px;">❌ Lỗi kết nối: ${escHtml(e.message)}</div>`;
  }
}

async function mtDeleteMailbox(email) {
  try {
    await fetch('/api/mailtemp/mailbox/delete', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});
    showToast('🗑️', 'Đã xóa mailbox');
    mtLoadMailboxes();
  } catch(e) { showToast('❌', 'Lỗi xóa'); }
}

async function mtClearAll() {
  if(!confirm('Xóa toàn bộ danh sách mailtemp?')) return;
  try {
    await fetch('/api/mailtemp/mailbox/clear', {method:'POST'});
    showToast('🗑️', 'Đã xóa hết');
    mtLoadMailboxes();
  } catch(e) { showToast('❌', 'Lỗi xóa'); }
}

