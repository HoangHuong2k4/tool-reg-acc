// ==== COMMON ====
let ccIsRunning=false, hfIsRunning=false, gptIsRunning=false;
let ccEvt=null, hfEvt=null, gptEvt=null;

function showToast(icon,msg,duration=3000){
  const t=document.getElementById('toast');
  document.getElementById('toastIcon').textContent=icon;document.getElementById('toastMsg').textContent=msg;
  t.classList.add('show');clearTimeout(t._timer);t._timer=setTimeout(()=>t.classList.remove('show'),duration);
}
function escHtml(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

function switchTab(tab, updateHash=true) {
  document.querySelectorAll('.wrap').forEach(w => w.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  
  const targetWrap = document.getElementById(`tab-${tab}`);
  if(targetWrap) targetWrap.classList.add('active');
  
  // Kích hoạt nav button tương ứng
  const navBtns = document.querySelectorAll('.nav-btn');
  navBtns.forEach(b => {
    if (b.getAttribute('onclick').includes(tab)) {
      b.classList.add('active');
    }
  });
  
  if(tab === 'higgsfield') document.body.classList.add('theme-hf');
  else document.body.classList.remove('theme-hf');
  
  if(tab === 'gpm') {
    document.body.classList.add('theme-gpm');
    if(typeof gpmLoadAccounts === 'function') gpmLoadAccounts();
  } else {
    document.body.classList.remove('theme-gpm');
  }

  if(tab === 'settings') loadSettings();
  if(updateHash) window.history.replaceState(null, null, `#${tab}`);
}

async function loadSettings() {
  try {
    const r = await fetch('/api/settings'); const d = await r.json();
    if (d._error) {
      showToast('⚠️', 'Lỗi tải cấu hình từ DB (bị lock), giữ nguyên giao diện để tránh ghi đè!');
      return;
    }
    document.getElementById('setting-api-token').value = d.PROXY_API_TOKEN || '';
    document.getElementById('setting-merchant-id').value = d.PROXY_MERCHANT || '';
    document.getElementById('setting-proxy-id').value = d.PROXY_ID || '';
    document.getElementById('setting-proxy-type').value = d.PROXY_TYPE || 'proxyquick';
    document.getElementById('setting-proxyxoay-key').value = d.PROXYXOAY_KEY || '';
    document.getElementById('setting-proxyquick-v3-list').value = d.PROXY_V3_LIST || '';
    const staticListEl = document.getElementById('setting-proxy-static-list');
    if(staticListEl) staticListEl.value = d.PROXY_STATIC_LIST || '';
    if(document.getElementById('setting-capcut-password')) {
        document.getElementById('setting-capcut-password').value = d.CAPCUT_PASSWORD || 'capcut123';
    }
    if(document.getElementById('setting-gpm-api-url')) {
        document.getElementById('setting-gpm-api-url').value = d.GPM_API_URL || 'http://127.0.0.1:19995';
    }
    const teleBotInput = document.getElementById('setting-telegram-bot-token');
    if(teleBotInput) teleBotInput.value = d.TELEGRAM_BOT_TOKEN || '';
    const teleChatInput = document.getElementById('setting-telegram-chat-id');
    if(teleChatInput) teleChatInput.value = d.TELEGRAM_CHAT_ID || '';
    const masaTokenInput = document.getElementById('setting-masa-token');
    if(masaTokenInput) masaTokenInput.value = d.MASA_TOKEN || '';
    // Load Grok Cards
    const grokCardsInput = document.getElementById('grk-cardsInput');
    if(grokCardsInput) grokCardsInput.value = d.GROK_CARDS_LIST || '';
    // Gmail94 token
    const gmail94Input = document.getElementById('setting-gmail94-token');
    const gmail94Status = document.getElementById('settings-gmail94-status');
    if(gmail94Input) {
      const tok = d.GMAIL94_TOKEN || '';
      gmail94Input.value = tok;
      if(gmail94Status) {
        gmail94Status.textContent = tok ? '(✅ Đã có token)' : '(⚠️ Chưa có token)';
        gmail94Status.style.color = tok ? '#10b981' : 'var(--muted)';
      }
    }
    const gmail94PassInput = document.getElementById('setting-gmail94-password');
    if(gmail94PassInput) {
      gmail94PassInput.value = d.GMAIL94_PASSWORD || '';
    }
    // OTPGmail token
    const otpgmailInput = document.getElementById('setting-otpgmail-token');
    const otpgmailStatus = document.getElementById('settings-otpgmail-status');
    if(otpgmailInput) {
      const tok = d.OTPGMAIL_TOKEN || '';
      otpgmailInput.value = tok;
      if(otpgmailStatus) {
        otpgmailStatus.textContent = tok ? '(✅ Đã có token)' : '(⚠️ Chưa có token)';
        otpgmailStatus.style.color = tok ? '#10b981' : 'var(--muted)';
      }
    }
    const otpgmailPassInput = document.getElementById('setting-otpgmail-password');
    if(otpgmailPassInput) {
      otpgmailPassInput.value = d.OTPGMAIL_PASSWORD || '';
    }
    if(typeof toggleProxySettings === 'function') toggleProxySettings();
  } catch(e) {}
}

async function saveSettings() {
  const data = {
    PROXY_TYPE: document.getElementById('setting-proxy-type').value,
    PROXY_API_TOKEN: document.getElementById('setting-api-token').value.trim(),
    PROXY_MERCHANT: document.getElementById('setting-merchant-id').value.trim(),
    PROXY_ID: document.getElementById('setting-proxy-id').value.trim(),
    PROXYXOAY_KEY: document.getElementById('setting-proxyxoay-key').value.trim(),
    PROXY_V3_LIST: document.getElementById('setting-proxyquick-v3-list').value.trim()
  };
  const staticListEl = document.getElementById('setting-proxy-static-list');
  if(staticListEl) data.PROXY_STATIC_LIST = staticListEl.value.trim();
  if(document.getElementById('setting-capcut-password')) {
      data.CAPCUT_PASSWORD = document.getElementById('setting-capcut-password').value.trim() || 'capcut123';
  }
  if(document.getElementById('setting-gpm-api-url')) {
      data.GPM_API_URL = document.getElementById('setting-gpm-api-url').value.trim() || 'http://127.0.0.1:19995';
  }
  if(document.getElementById('setting-telegram-bot-token')) {
      data.TELEGRAM_BOT_TOKEN = document.getElementById('setting-telegram-bot-token').value.trim();
  }
  if(document.getElementById('setting-telegram-chat-id')) {
      data.TELEGRAM_CHAT_ID = document.getElementById('setting-telegram-chat-id').value.trim();
  }
  if(document.getElementById('setting-masa-token')) {
      data.MASA_TOKEN = document.getElementById('setting-masa-token').value.trim();
  }
  // Gmail94 token & password
  const gmail94Input = document.getElementById('setting-gmail94-token');
  if(gmail94Input) {
    data.GMAIL94_TOKEN = gmail94Input.value.trim();
  }
  const gmail94PassInput = document.getElementById('setting-gmail94-password');
  if(gmail94PassInput) {
    data.GMAIL94_PASSWORD = gmail94PassInput.value.trim();
  }
  // OTPGmail token & password
  const otpgmailInput = document.getElementById('setting-otpgmail-token');
  if(otpgmailInput) {
    data.OTPGMAIL_TOKEN = otpgmailInput.value.trim();
  }
  const otpgmailPassInput = document.getElementById('setting-otpgmail-password');
  if(otpgmailPassInput) {
    data.OTPGMAIL_PASSWORD = otpgmailPassInput.value.trim();
  }
  // Grok Cards
  const grokCardsInput = document.getElementById('grk-cardsInput');
  if(grokCardsInput) {
    data.GROK_CARDS_LIST = grokCardsInput.value.trim();
  }
  try {
    const r = await fetch('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    const d = await r.json();
    if(d.success) {
      showToast('✅', 'Đã lưu cấu hình!');
      // Reload để cập nhật status Gmail94
      loadSettings();
    } else showToast('❌', 'Lỗi lưu cấu hình');
  } catch(e) { showToast('❌', 'Lỗi kết nối'); }
}

function toggleGmail94TokenVisibility() {
  const inp = document.getElementById('setting-gmail94-token');
  if(!inp) return;
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

function toggleOtpgmailTokenVisibility() {
  const inp = document.getElementById('setting-otpgmail-token');
  if(!inp) return;
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

async function loadProxyStatus(){
  try{
    const r=await fetch('/api/proxy/status');const d=await r.json();
    ['cc','hf','gpt','drm'].forEach(pfx=>{
      const el=document.getElementById(pfx+'-proxyIp'), ic=document.getElementById(pfx+'-proxyStatusIcon'), src=document.getElementById(pfx+'-proxySource');
      if(el) {
        if(d.ip){el.textContent=d.ip+' (Live)';el.className='ip status-ok';ic.textContent='✅';}
        else{el.textContent='Lỗi kết nối';el.className='ip status-err';ic.textContent='❌';}
      }
      if(src) {
        src.textContent = d.type === 'proxyxoay' ? 'ProxyXoay.shop' : 'ProxyQuick v2';
      }
    });
  }catch(e){}
}

let autoRotateTimer = null;

function resetAutoRotateTimer() {
  if (autoRotateTimer) clearInterval(autoRotateTimer);
  const checkboxes = document.querySelectorAll('.auto-rotate-cb');
  const isEnabled = checkboxes.length > 0 && checkboxes[0].checked;
  if (isEnabled) {
    autoRotateTimer = setInterval(() => {
      // Don't auto rotate if we are currently rotating
      const btn = document.getElementById('cc-rotateBtn');
      if (btn && !btn.disabled) {
        rotateProxy('cc');
      }
    }, 3 * 60 * 1000);
  }
}

function toggleAutoRotate(checked) {
  const checkboxes = document.querySelectorAll('.auto-rotate-cb');
  checkboxes.forEach(cb => cb.checked = checked);
  resetAutoRotateTimer();
  if(checked) showToast('✅', 'Đã BẬT tự động xoay IP (3 phút)');
  else showToast('❌', 'Đã TẮT tự động xoay IP');
}

async function rotateProxy(pfx){
  const btn=document.getElementById(pfx+'-rotateBtn');btn.classList.add('spinning');btn.disabled=true;
  try{
    const r=await fetch('/api/proxy/rotate',{method:'POST'});const d=await r.json();
    if(d.success){
      showToast('✅','Đã xoay IP → '+d.ip);
      ['cc','hf'].forEach(p=>{
        document.getElementById(p+'-proxyIp').textContent=d.ip+' (Mới)';
        document.getElementById(p+'-proxyIp').className='ip status-ok';
        document.getElementById(p+'-proxyStatusIcon').textContent='✅';
      });
      btn.classList.remove('spinning');btn.disabled=false;
      resetAutoRotateTimer();
    }else {
      showToast('❌',d.error||'Xoay IP thất bại');
      btn.classList.remove('spinning');
      if(d.timeRemaining){
        startRotateCountdown(btn, d.timeRemaining);
      } else {
        btn.disabled=false;
      }
    }
  }catch(e){
    showToast('❌','Lỗi kết nối API');
    btn.classList.remove('spinning');btn.disabled=false;
  }
}

function formatGrokCards() {
  const el = document.getElementById('grk-cardsInput');
  if(!el) return;
  let lines = el.value.split('\n');
  lines = lines.map(line => {
    let s = line.trim();
    if(!s) return s;
    if(s.includes('\t')) {
      s = s.split('\t').map(x => x.trim()).filter(x => x).join(' | ');
    } else if (!s.includes('|')) {
      let p = s.split(/\s+/);
      if(p.length >= 3) {
        s = p[0] + ' | ' + p[1] + ' | ' + p.slice(2).join('');
      }
    }
    return s;
  });
  el.value = lines.join('\n');
  saveSettings();
}

async function grkChangeCardActiveTab(email) {
  const cardsText = document.getElementById('grk-cardsInput').value || '';
  let cards = cardsText.split('\n').map(c => c.trim()).filter(c => c);
  if (!cards.length) {
    showToast('❌', 'Vui lòng nhập thẻ bên tab Đổi Thẻ trước!');
    return;
  }
  
  const card = cards[Math.floor(Math.random() * cards.length)];
  showConfirmModal('Xác nhận đổi thẻ (Tab Mở)', `Bạn có chắc muốn tự động điền thẻ ${card} cho tài khoản ${email} trên cửa sổ Chrome hiện tại không?`, async () => {
    
    try {
      showToast('⏳', 'Đang gửi lệnh đổi thẻ...');
      const r = await fetch('/api/grok/billing/active_tab', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ email, card })
      });
      const d = await r.json();
      if(d.success) {
        showToast('✅', 'Đã bắt đầu điền thẻ trên trình duyệt đang mở!');
      } else {
        showToast('❌', d.error || 'Lỗi gửi lệnh đổi thẻ');
      }
    } catch(e) {
      showToast('❌', 'Lỗi kết nối tới server');
    }
  }, 'Thực Hiện');
}

async function grkChangeCardActiveTabBulk() {
  const cbs = document.querySelectorAll('.grk-acc-checkbox:checked');
  if (cbs.length === 0) {
    return showToast('⚠️', 'Vui lòng chọn ít nhất 1 tài khoản!');
  }
  
  const cardsText = document.getElementById('grk-cardsInput').value || '';
  let cards = cardsText.split('\n').map(c => c.trim()).filter(c => c);
  if (cards.length < cbs.length) {
    return showToast('❌', `Không đủ thẻ! Bạn chọn ${cbs.length} tài khoản nhưng chỉ có ${cards.length} thẻ.`);
  }

  const accs = [];
  cbs.forEach(c => accs.push(c.getAttribute('data-email')));

  showConfirmModal('Xác nhận đổi thẻ hàng loạt (Tab Mở)', `Bạn có chắc muốn tự động điền thẻ ngẫu nhiên cho ${accs.length} tài khoản trên các cửa sổ Chrome hiện tại không?`, async () => {
    for (let i = 0; i < accs.length; i++) {
      const email = accs[i];
      const card = cards[Math.floor(Math.random() * cards.length)];
      
      showToast('⏳', `Đang gửi lệnh đổi thẻ cho ${email}...`);
      try {
        await fetch('/api/grok/billing/active_tab', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ email, card })
        });
      } catch(e) {}
      await new Promise(r => setTimeout(r, 500));
    }
    showToast('✅', `Đã gửi lệnh đổi thẻ cho ${accs.length} tài khoản!`);
  }, 'Thực Hiện');
}

function startRotateCountdown(btn, seconds) {
  let rem = seconds;
  btn.disabled = true;
  btn.textContent = `⏳ Chờ ${rem}s`;
  const iv = setInterval(() => {
    rem--;
    if (rem <= 0) {
      clearInterval(iv);
      btn.textContent = '↻ Xoay IP';
      btn.disabled = false;
    } else {
      btn.textContent = `⏳ Chờ ${rem}s`;
    }
  }, 1000);
}

async function checkRunningStatus() {
  try {
    const r1 = await fetch('/api/capcut/status');
    const d1 = await r1.json();
    if(d1.is_running) {
      ccIsRunning = true;
      ccSetUI(true);
      ccStartSSE();
    }
  } catch(e) {}
  
  try {
    const r2 = await fetch('/api/higgsfield/status');
    const d2 = await r2.json();
    if(d2.is_running) {
      hfIsRunning = true;
      hfSetUI(true);
      hfStartSSE();
    }
  } catch(e) {}
  
  try {
    const r3 = await fetch('/api/gpt/status');
    const d3 = await r3.json();
    if(d3.is_running) {
      gptIsRunning = true;
      gptSetUI(true);
      gptStartSSE();
    }
  } catch(e) {}
}

window.addEventListener('hashchange', () => {
  let hash = window.location.hash.substring(1);
  if (!['capcut', 'higgsfield', 'gpt', 'gpm', 'dreamina', 'grok', 'settings'].includes(hash)) hash = 'capcut';
  switchTab(hash, false);
});

window.onload=()=>{
  let hash = window.location.hash.substring(1);
  if (!['capcut', 'higgsfield', 'gpt', 'gpm', 'dreamina', 'grok', 'settings'].includes(hash)) hash = 'capcut';
  switchTab(hash, false);

  ccLoadHotmailCount();
  ccLoadPendingLinkCount();
  ccLoadAccounts();
  hfLoadAccounts();
  gptLoadAccounts();
  gptLoadHotmailCount();
  grkLoadHotmailCount();
  grkLoadBillingCount();
  grkLoadAccounts();
  loadProxyStatus();
  setInterval(loadProxyStatus,10000);
  
  if (typeof resetAutoRotateTimer === 'function') resetAutoRotateTimer();
  
  
  // Khôi phục UI state từ localStorage
  ccSetBrowser(ccBrowser);
  if(ccHeadless) document.getElementById('cc-headlessToggle').classList.add('active');
  if(ccIncognito) document.getElementById('cc-incognitoToggle').classList.add('active');
  
  hfSetBrowser(hfBrowser);
  if(hfHeadless) document.getElementById('hf-headlessToggle').classList.add('active');
  
  gptSetBrowser(gptBrowser);
  if(gptHeadless) document.getElementById('gpt-headlessToggle').classList.add('active');
  if(gptIncognito) document.getElementById('gpt-incognitoToggle').classList.add('active');
  if(gptKeepOpen) document.getElementById('gpt-keepOpenToggle').classList.add('active');
  
  checkRunningStatus();
};

