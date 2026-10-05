// ==== GPT ====
let gptMailType='outlook', gptFilter='ALL', gptLogs=[], gptOk=0, gptFail=0, gptTotal=0;
let gptBrowser = localStorage.getItem('gptBrowser') || 'chrome';
let gptHeadless = (localStorage.getItem('gptHeadless') === 'true');
let gptIncognito = (localStorage.getItem('gptIncognito') === 'true');
let gptKeepOpen = (localStorage.getItem('gptKeepOpen') === 'true');

function gptSetBrowser(b) {
  gptBrowser = b;
  localStorage.setItem('gptBrowser', b);
  document.getElementById('gpt-browserChrome').classList.toggle('active', b === 'chrome');
  document.getElementById('gpt-browserFirefox').classList.toggle('active', b === 'firefox');
  document.getElementById('gpt-browserCamoufox').classList.toggle('active', b === 'camoufox');
}

function gptToggleHeadless() {
  gptHeadless = !gptHeadless;
  localStorage.setItem('gptHeadless', gptHeadless);
  document.getElementById('gpt-headlessToggle').classList.toggle('active', gptHeadless);
}

function gptToggleIncognito() {
  gptIncognito = !gptIncognito;
  localStorage.setItem('gptIncognito', gptIncognito);
  document.getElementById('gpt-incognitoToggle').classList.toggle('active', gptIncognito);
}

function gptToggleKeepOpen() {
  gptKeepOpen = !gptKeepOpen;
  localStorage.setItem('gptKeepOpen', gptKeepOpen);
  document.getElementById('gpt-keepOpenToggle').classList.toggle('active', gptKeepOpen);
}

let gptApiSource = 'dongvanfb';
function gptSetApiSource(src) {
  gptApiSource = src;
  document.getElementById('gpt-sourceDongvanfb').classList.toggle('active', src === 'dongvanfb');
  document.getElementById('gpt-sourceMixmmo').classList.toggle('active', src === 'mixmmo');
}

function gptSetMailType(m){
  gptMailType = m;
  document.getElementById('gpt-mailHotmail').classList.toggle('active', m === 'outlook');
  document.getElementById('gpt-mailGmail94').classList.toggle('active', m === 'gmail94');
  const d_otpgmail_g = document.getElementById('gpt-mailOtpgmailGmail');
  if(d_otpgmail_g) d_otpgmail_g.classList.toggle('active', m === 'otpgmail_gmail');
  const d_otpgmail_i = document.getElementById('gpt-mailOtpgmailIcloud');
  if(d_otpgmail_i) d_otpgmail_i.classList.toggle('active', m === 'otpgmail_icloud');
  const d_btn = document.getElementById('gpt-mailDomain');
  if(d_btn) d_btn.classList.toggle('active', m === 'domain');
  
  const lbl = document.getElementById('gpt-countLabel');
  const hint = document.getElementById('gpt-countHint');
  
  if(m === 'gmail94' || m === 'otpgmail_gmail' || m === 'otpgmail_icloud'){
    if(lbl) {
      lbl.innerHTML = `Số Gmail cần mua: <span id="gpt-count-val">1</span> <span style="font-size:11px; font-weight:normal; color:var(--muted);">(Mỗi 1 Gmail sẽ tạo thành 4 mail, chạy bằng ${gptBrowser})</span>`;
      if(m === 'otpgmail_gmail' || m === 'otpgmail_icloud') {
        lbl.innerHTML = `Số lượng cần mua: <span id="gpt-count-val">1</span> <span style="font-size:11px; font-weight:normal; color:var(--muted);">(Mỗi 1 order = 1 ChatGPT, chạy bằng ${gptBrowser})</span>`;
      }
    }
    if(hint) hint.style.display = 'block';
    gptUpdateCountHint();
    if (gptCreationMethod === 'api') {
      gptSetCreationMethod('selenium');
    }
  } else {
    if(lbl) lbl.textContent = 'Số lượng tài khoản cần tạo';
    if(hint) hint.style.display = 'none';
  }
  
  // Hien/an hotmail file group
  const hotmailGroup = document.getElementById('gpt-hotmailGroup');
  if(hotmailGroup) hotmailGroup.style.display = (m === 'outlook') ? 'block' : 'none';
  const apiGroup = document.getElementById('gpt-apiSourceGroup');
  if(apiGroup) apiGroup.style.display = (m === 'outlook') ? 'block' : 'none';
}

function gptUpdateCountHint(){
  if(gptMailType !== 'gmail94' && gptMailType !== 'otpgmail_gmail' && gptMailType !== 'otpgmail_icloud') return;
  const count = parseInt(document.getElementById('gpt-count').value) || 0;
  const valEl = document.getElementById('gpt-count-val');
  if(valEl) valEl.textContent = isNaN(count) ? 1 : count;
  const total = (gptMailType === 'gmail94') ? count * 4 : count;
  const el = document.getElementById('gpt-countHintTotal');
  if(el) el.textContent = total;
}

async function gptLoadHotmailCount(){
  try{
    const r=await fetch('/api/gpt/hotmail/count');const d=await r.json();
    const cnt = d.count || 0;
    document.getElementById('gpt-statHotmail').textContent = cnt;
    document.getElementById('gpt-hotmailCountBadge').textContent = cnt;
    document.getElementById('gpt-hotmailCountLabel').textContent = cnt;
  }catch(e){}
}

async function gptUploadHotmail(input){
  const file=input.files[0];if(!file)return;
  const fd=new FormData();fd.append('file',file);
  try{
    const r=await fetch('/api/gpt/hotmail/upload',{method:'POST',body:fd});const d=await r.json();
    showToast('✅','Đã upload: '+d.count+' hotmail GPT');
    gptLoadHotmailCount();
  }catch(e){showToast('❌','Upload thất bại');}
}

window.gptHideSensitive = false;
function gptToggleHide() {
    window.gptHideSensitive = !window.gptHideSensitive;
    gptLoadAccounts();
    const btn = document.getElementById('gptToggleHideBtn');
    if (btn) {
        btn.innerHTML = window.gptHideSensitive ? '👁️ Mở' : '🙈 Ẩn';
    }
}

function playMomoSound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        for (let i = 0; i < 20; i++) {
            const t = ctx.currentTime + i * 0.4; // 0.4s delay between each "ting"
            
            const osc1 = ctx.createOscillator();
            const gain1 = ctx.createGain();
            osc1.connect(gain1);
            gain1.connect(ctx.destination);
            osc1.type = 'sine';
            osc1.frequency.setValueAtTime(880, t); 
            gain1.gain.setValueAtTime(0, t);
            gain1.gain.linearRampToValueAtTime(0.5, t + 0.05);
            gain1.gain.exponentialRampToValueAtTime(0.01, t + 0.5);
            osc1.start(t);
            osc1.stop(t + 0.5);
            
            const osc2 = ctx.createOscillator();
            const gain2 = ctx.createGain();
            osc2.connect(gain2);
            gain2.connect(ctx.destination);
            osc2.type = 'sine';
            osc2.frequency.setValueAtTime(1318.51, t + 0.15); 
            gain2.gain.setValueAtTime(0, t + 0.15);
            gain2.gain.linearRampToValueAtTime(0.5, t + 0.2);
            gain2.gain.exponentialRampToValueAtTime(0.01, t + 0.8);
            osc2.start(t + 0.15);
            osc2.stop(t + 0.8);
        }
    } catch(e) {
        console.log("Audio not supported");
    }
}

function playApplePaySound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        // 3 nốt nhạc như âm chuộng iPhone
        const notes = [1174.66, 1318.51, 1567.98]; // D6, E6, G6
        notes.forEach((freq, i) => {
            const t = ctx.currentTime + i * 0.18;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, t);
            gain.gain.setValueAtTime(0, t);
            gain.gain.linearRampToValueAtTime(0.4, t + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.01, t + 0.5);
            osc.start(t);
            osc.stop(t + 0.5);
        });
    } catch(e) { console.log('Audio not supported'); }
}

let gptCurrentTab = 'session';
function gptSetTab(tab) {
    gptCurrentTab = tab;
    
    // update tab UI if the elements exist
    const tabSession = document.getElementById('gptTabSession');
    const tabAll = document.getElementById('gptTabAll');
    if(tabSession && tabAll) {
        tabSession.style.background = tab === 'session' ? 'var(--primary)' : 'var(--bg-card)';
        tabSession.style.color = tab === 'session' ? 'white' : 'var(--text)';
        
        tabAll.style.background = tab === 'all' ? 'var(--primary)' : 'var(--bg-card)';
        tabAll.style.color = tab === 'all' ? 'white' : 'var(--text)';
    }
    
    gptLoadAccounts();
}

let gptAllAccountsData = [];

async function gptLoadAccounts(){
  try{
    const r=await fetch(`/api/gpt/accounts?session=${gptCurrentTab === 'session'}`);const d=await r.json();
    const tbody=document.getElementById('gpt-accountsBody');
    if(!d.accounts||d.accounts.length===0){
      gptAllAccountsData = [];
      tbody.innerHTML='<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:20px;">Chưa có tài khoản nào</td></tr>';
      return;
    }
    // Lưu toàn bộ để Copy Filter có thể copy hết
    gptAllAccountsData = d.accounts.slice().reverse();
    // Render toàn bộ ra UI để lúc lọc/copy theo giao diện không bị thiếu
    tbody.innerHTML=gptAllAccountsData.map(a=>{
      const twofa = a.twofa || '';
      
      // 1. Format Trial (Ưu Đãi)
      let uudaiHtml = '<span style="color:var(--muted)">—</span>';
      if (a.uudai && a.uudai !== 'không') {
          const raw = a.uudai.toLowerCase();
          const badgeStyle = "display:inline-block;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:600;white-space:nowrap;";
          if (raw.includes('có trial') || raw.includes('gói 0') || /(?:^|\D)0\s*đ/.test(raw)) {
              uudaiHtml = `<span style="${badgeStyle}background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.3);color:#00d4ff;">✓ Trial 0đ</span>`;
          } else {
              // Lấy số tiền từ chuỗi "Không trial - 522.500 đ" → "522.500đ"
              const match = a.uudai.match(/([\d.,]+)\s*đ/);
              const amount = match ? match[1] + 'đ' : a.uudai;
              uudaiHtml = `<span style="${badgeStyle}background:rgba(255,215,0,0.08);border:1px solid rgba(255,215,0,0.2);color:#ffd700;">${amount}</span>`;
          }
      }
      
      // 2. Format Payment Methods - badge riêng cho từng loại
      const pms = (a.momo && a.momo !== 'không' && a.momo !== 'lỗi') ? a.momo.toLowerCase() : '';
      const hasMomo = pms.includes('momo') || pms === 'có';
      const hasApplePayOnly = pms.includes('apple_pay_only');
      const hasGooglePay = pms.includes('google_pay_present') || (pms.includes('google_pay') && !pms.includes('apple_pay_only'));

      let momoHtml = '';
      if (hasApplePayOnly) {
          momoHtml = `<span style="display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:rgba(16,185,129,0.18);color:#10b981;border:1px solid rgba(16,185,129,0.4);">🍎 Apple Pay Only</span>`;
          if (hasMomo) {
              momoHtml += ` <span style="display:inline-block;padding:2px 6px;border-radius:10px;font-size:10px;font-weight:600;background:rgba(168,85,247,0.18);color:#d8b4fe;border:1px solid rgba(168,85,247,0.4);">MoMo</span>`;
          }
      } else if (hasGooglePay && !hasMomo) {
          momoHtml = `<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:rgba(59,130,246,0.12);color:#60a5fa;border:1px solid rgba(59,130,246,0.3);">🤖 Google Pay</span>`;
      } else if (hasMomo) {
          momoHtml = `<span style="display:inline-block;padding:2px 10px;border-radius:10px;font-size:10px;font-weight:600;background:rgba(168,85,247,0.18);color:#d8b4fe;border:1px solid rgba(168,85,247,0.4);">✓ Có MoMo</span>`;
      } else {
          momoHtml = `<span style="color:var(--muted);font-size:11px;">Không</span>`;
      }
      
      // Highlight dòng theo trạng thái
      const rowStyle = hasApplePayOnly ? 'background: rgba(16,185,129,0.07);' : (hasMomo ? 'background: rgba(168,85,247,0.06);' : '');

      
      // Masking logic
      let displayEmail = a.email;
      let displayPass = a.password;
      let display2FA = twofa;
      
      if (window.gptHideSensitive) {
          if (displayEmail.includes('@')) {
              const parts = displayEmail.split('@');
              displayEmail = parts[0].substring(0, 3) + '*****@' + parts[1];
          }
          displayPass = '***';
          if (display2FA) display2FA = '***';
      }
      
      return `<tr style="${rowStyle}">
        <td onclick="navigator.clipboard.writeText('${escHtml(a.email)}');showToast('📋','Đã copy Email!');" style="cursor:pointer;" title="Click để copy Email">${escHtml(displayEmail)}</td>
        <td onclick="navigator.clipboard.writeText('${escHtml(a.password)}');showToast('📋','Đã copy Mật khẩu!');" style="cursor:pointer;" title="Click để copy Mật khẩu"><code style="color:var(--muted)">${escHtml(displayPass)}</code></td>
        <td onclick="navigator.clipboard.writeText('${escHtml(twofa)}');showToast('📋','Đã copy 2FA!');" style="cursor:pointer;" title="Click để copy 2FA"><code style="color:var(--accent);font-size:10px;">${display2FA ? escHtml(display2FA) : '<span style="color:var(--muted)">N/A</span>'}</code></td>
        <td>${momoHtml}</td>
        <td>${uudaiHtml}</td>
        <td><div style="display:flex;align-items:center;gap:6px;"><span class="tag tag-ok" style="margin:0;">✅ OK</span><button class="copy-btn" title="Copy (Tab Separated)" onclick="navigator.clipboard.writeText('${escHtml(a.email)}\\t${escHtml(a.password)}\\t${escHtml(twofa)}');showToast('📋','Đã copy!');"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button></div></td>
      </tr>`;
    }).join('');
    gptFilterAccounts();
  }catch(e){}
}

async function gptCopyAccounts(){
  try{const r=await fetch('/api/gpt/accounts/raw_ep');const t=await r.text();await navigator.clipboard.writeText(t);showToast('📋','Đã copy (Email|Pass|2FA|MoMo|Uudai)!');}catch(e){}
}

// Copy các dòng đang visible sau khi filter, tính chuẩn theo giao diện (UI)
async function gptCopyFiltered() {
  try {
    const tbody = document.getElementById('gpt-accountsBody');
    if (!tbody) return;
    
    const trs = tbody.getElementsByTagName('tr');
    const copiedLines = [];
    
    for (let i = 0; i < trs.length; i++) {
      const tr = trs[i];
      if (tr.style.display !== 'none' && !tr.innerText.includes('Chưa có tài khoản nào')) {
        const tds = tr.getElementsByTagName('td');
        if (tds.length >= 5) {
          const email = tds[0].textContent.trim();
          const pass = tds[1].textContent.trim();
          const twofa = tds[2].textContent.trim();
          // Cột 3 và 4 chứa HTML có span, lấy textContent để có chuỗi sạch
          const momo = tds[3].textContent.trim();
          const uudai = tds[4].textContent.trim();
          
          copiedLines.push(`${email}\t${pass}\t${twofa}\t${momo}\t${uudai}`);
        }
      }
    }
    
    if (copiedLines.length === 0) {
      showToast('⚠️', 'Không có tài khoản nào khớp với bộ lọc!');
      return;
    }
    
    const text = copiedLines.join('\n');
    await navigator.clipboard.writeText(text);
    showToast('📋', `Đã copy ${copiedLines.length} tài khoản từ bảng! (Dạng Tab Excel)`);
  } catch(e) {
    showToast('❌', 'Lỗi copy: ' + e.message);
  }
}

// Toggle ẩn/hiện thông tin nhạy cảm
window.gptHideSensitive = false;
function gptToggleHide() {
  window.gptHideSensitive = !window.gptHideSensitive;
  const btn = document.getElementById('gptToggleHideBtn');
  if (btn) btn.textContent = window.gptHideSensitive ? '👁️ Hiện' : '🙈 Ẩn';
  gptLoadAccounts();
}


async function gptClearAccounts(){
  showConfirmModal('Xóa tài khoản GPT', 'Bạn có chắc chắn muốn xóa toàn bộ danh sách tài khoản GPT đã tạo?', async () => {
    try{await fetch('/api/gpt/accounts/clear',{method:'POST'});showToast('🗑️','Đã xóa danh sách!');gptLoadAccounts();}catch(e){}
  });
}

function gptRefreshAccounts() {
    gptLoadAccounts();
}

let gptCreationMethod = 'selenium';
function gptSetCreationMethod(method) {
    gptCreationMethod = method;
    document.querySelectorAll('#gpt-creationSelenium, #gpt-creationApi').forEach(el => el.classList.remove('active'));
    document.getElementById(method === 'api' ? 'gpt-creationApi' : 'gpt-creationSelenium').classList.add('active');
}

async function gptStartTask(){

  if(gptIsRunning)return;
  const count=parseInt(document.getElementById('gpt-count').value)||1;
  const threads=parseInt(document.getElementById('gpt-workers').value)||1;
  const checkMomo=document.getElementById('gpt-checkMomo').checked;
  const checkApplePay=document.getElementById('gpt-checkApplePay') ? document.getElementById('gpt-checkApplePay').checked : false;

  // Gmail94: mỗi lần mua 1 Gmail sẽ tạo 4 biến thể GPT
  // OTPGmail: 1 mail = 1 biến thể
  gptOk=0;gptFail=0;
  if (gptMailType === 'gmail94') {
    gptTotal = count * 4;
  } else if (gptMailType === 'otpgmail_gmail' || gptMailType === 'otpgmail_icloud') {
    gptTotal = count;
  } else {
    gptTotal = count;
  }
  gptUpdateStats();

  const r=await fetch('/api/gpt/task/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count,threads,mail_type:gptMailType,creation_method:gptCreationMethod,check_momo:checkMomo,check_apple_pay_ui:checkApplePay,mail_api_source:gptApiSource,keep_open:gptKeepOpen,driver_mode:'playwright_ui',browser_type:gptBrowser,headless:gptHeadless,incognito:gptIncognito})});
  const d=await r.json();
  if(!d.success){showToast('❌',d.error);return;}
  gptIsRunning=true;gptSetUI(true);gptStartSSE();
}

async function gptStopTask(){
  gptIsRunning=false; gptSetUI(false); if(gptEvt)gptEvt.close();
  await fetch('/api/gpt/task/stop',{method:'POST'});
  showToast('⏹','Đã dừng GPT.');
}

async function gptCloseBrowsers(){
  try{await fetch('/api/gpt/task/close_browsers',{method:'POST'});showToast('💥','Đã đóng tất cả trình duyệt GPT!');}catch(e){}
}

function gptStartSSE(){
  if(gptEvt)gptEvt.close(); gptEvt=new EventSource('/api/gpt/task/stream');
  gptEvt.onmessage=(e)=>{
    const data=JSON.parse(e.data);
    if(data.type==='log')gptAddLog(data);
    else if(data.type==='result'){if(data.success)gptOk++;else gptFail++;gptUpdateStats();if(data.success)gptLoadAccounts();}
    else if(data.type==='done'){gptIsRunning=false;gptSetUI(false);gptEvt.close();showToast('✅','GPT Xong!');gptLoadAccounts();}
    else if(data.type==='stopped'){gptIsRunning=false;gptSetUI(false);gptEvt.close();showToast('⏹','GPT Đã dừng.');}
  };
}

function gptAddLog(data) {
    gptLogs.push(data);
    if(gptLogs.length > 2000) gptLogs.shift();
    if(gptFilter === 'ALL' || data.level === gptFilter) gptRenderLog(data);
    
    if(data.type === 'waiting_gmail94') {
      const w = document.getElementById('gpt-gmail94-waiting');
      if(w) w.style.display = data.status ? 'flex' : 'none';
    }
    if(data.type === 'waiting_otpgmail') {
      const w = document.getElementById('gpt-otpgmail-waiting');
      if(w) w.style.display = data.status ? 'flex' : 'none';
    }

    // Play ting ting sound if MoMo is detected
    if(data.msg && data.msg.includes('Phát hiện MoMo')) {
        playMomoSound();
    }

    // Badge "Đang chờ mail..." khi Gmail94 hết stock
    const badge = document.getElementById('gpt-waitingMailBadge');
    if (badge && data.msg) {
      if (data.msg.includes('Chua co Gmail')) {
        // Trích số lần retry từ log: "...lan X, thu lai..."
        const m = data.msg.match(/lan (\d+)/);
        const attempt = m ? parseInt(m[1]) : '?';
        document.getElementById('gpt-waitingMailInfo').textContent =
          `Hết stock, đang chờ... (lần thử ${attempt}) — tự retry mỗi 15s`;
        badge.style.display = 'flex';
      } else if (
        data.msg.includes('Gmail94 mua thanh cong') ||
        data.msg.includes('Dung do stop event') ||
        data.level === 'OK'
      ) {
        badge.style.display = 'none';
      }
    }
}
function gptRenderLog(data){
  const wrap=document.getElementById('gpt-logWrap');
  if(!wrap) return;
  const icons={OK:'✅',ERR:'❌',WARN:'⚠️',INFO:'📌'}; const classes={OK:'log-ok',ERR:'log-err',WARN:'log-warn',INFO:'log-info'};
  const div=document.createElement('div'); div.className='log-entry '+(classes[data.level]||'log-info');
  div.innerHTML=`<span class="log-time">${data.time}</span><span class="log-icon">${icons[data.level]||'📌'}</span><span class="log-msg">${escHtml(data.msg)}</span>`;
  wrap.appendChild(div);wrap.scrollTop=wrap.scrollHeight;
}
function gptUpdateStats(){
  document.getElementById('gpt-statOk').textContent=gptOk; document.getElementById('gpt-statFail').textContent=gptFail;
  const pct=gptTotal>0?Math.round(((gptOk+gptFail)/gptTotal)*100):0;
  document.getElementById('gpt-statPct').textContent=pct+'%'; document.getElementById('gpt-progressBar').style.width=pct+'%';
}
function gptSetUI(running){
  document.getElementById('gpt-startBtn').style.display=running?'none':'inline-block'; document.getElementById('gpt-stopBtn').style.display=running?'inline-block':'none';
  const dot=document.getElementById('gpt-statusDot'), txt=document.getElementById('gpt-statusText');
  if(running){dot.className='dot running';txt.textContent='Đang chạy...';}else{dot.className='dot';txt.textContent='Idle';}
  // Ẩn badge khi dừng/kết thúc
  if (!running) {
    const badge = document.getElementById('gpt-waitingMailBadge');
    if (badge) badge.style.display = 'none';
  }
}


