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
  // Gmail94 token & password
  const gmail94Input = document.getElementById('setting-gmail94-token');
  if(gmail94Input) {
    data.GMAIL94_TOKEN = gmail94Input.value.trim();
  }
  const gmail94PassInput = document.getElementById('setting-gmail94-password');
  if(gmail94PassInput) {
    data.GMAIL94_PASSWORD = gmail94PassInput.value.trim();
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
  if (!['capcut', 'higgsfield', 'gpt', 'settings'].includes(hash)) hash = 'capcut';
  switchTab(hash, false);
});

window.onload=()=>{
  let hash = window.location.hash.substring(1);
  if (!['capcut', 'higgsfield', 'gpt', 'settings'].includes(hash)) hash = 'capcut';
  switchTab(hash, false);

  ccLoadHotmailCount();
  ccLoadPendingLinkCount();
  ccLoadAccounts();
  hfLoadAccounts();
  gptLoadAccounts();
  gptLoadHotmailCount();
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

// ==== CAPCUT ====
let ccMode=3, ccMailType='hotmail', ccMailApiSource='dongvanfb', ccBrowser=localStorage.getItem('ccBrowser')||'chrome', ccHeadless=(localStorage.getItem('ccHeadless')==='true'), ccIncognito=(localStorage.getItem('ccIncognito')==='true'), ccFilter='ALL', ccLogs=[], ccOk=0, ccFail=0, ccTotal=0;
function ccSetMode(m){ccMode=m;[1,2,3,4].forEach(i=>{const el=document.getElementById('cc-mode'+i);if(el)el.classList.toggle('active',m===i);});document.getElementById('cc-joinLinkGroup').style.display=(m===2||m===4)?'block':'none';const isApiMode=m===4;document.getElementById('cc-browserGroup').style.display=isApiMode?'none':'block';document.getElementById('cc-headlessGroup').style.display=isApiMode?'none':'block';}
function ccSetMailType(m){
  ccMailType=m;
  document.getElementById('cc-mailHotmail').classList.toggle('active',m==='hotmail');
  document.getElementById('cc-mailDomain').classList.toggle('active',m==='domain');
  document.getElementById('cc-hotmailGroup').style.display=m==='hotmail'?'block':'none';
  if(document.getElementById('cc-apiSourceGroup')) document.getElementById('cc-apiSourceGroup').style.display=m==='hotmail'?'block':'none';
  // Ẩn nút API Mode nếu chọn Hotmail (vì API Mode chỉ dùng Mail Domain)
  const mode4Btn = document.getElementById('cc-mode4');
  if(mode4Btn) mode4Btn.style.display = m==='hotmail'?'none':'block';
  // Nếu đang ở mode 4 mà chuyển sang hotmail, reset về mode 1
  if(m==='hotmail' && ccMode===4) ccSetMode(1);
}
function ccSetApiSource(s){
  ccMailApiSource=s;
  document.getElementById('cc-sourceDongvanfb').classList.toggle('active',s==='dongvanfb');
  document.getElementById('cc-sourceMixmmo').classList.toggle('active',s==='mixmmo');
}
function ccSetBrowser(b){
  ccBrowser=b;
  localStorage.setItem('ccBrowser', b);
  document.getElementById('cc-browserChrome').classList.remove('active');
  document.getElementById('cc-browserFirefox').classList.remove('active');
  document.getElementById('cc-browserCamoufox').classList.remove('active');
  if(b==='chrome') document.getElementById('cc-browserChrome').classList.add('active');
  if(b==='firefox') document.getElementById('cc-browserFirefox').classList.add('active');
  if(b==='camoufox') document.getElementById('cc-browserCamoufox').classList.add('active');
}
function ccToggleHeadless(){
  ccHeadless=!ccHeadless;
  localStorage.setItem('ccHeadless', ccHeadless);
  document.getElementById('cc-headlessToggle').classList.toggle('active',ccHeadless);
}
function ccToggleIncognito() {
  ccIncognito=!ccIncognito;
  localStorage.setItem('ccIncognito', ccIncognito);
  document.getElementById('cc-incognitoToggle').classList.toggle('active',ccIncognito);
}
async function ccLoadHotmailCount(){
  try{const r=await fetch('/api/capcut/hotmail/count');const d=await r.json();
    document.getElementById('cc-statHotmail').textContent=d.count;
    document.getElementById('cc-hotmailCountBadge').textContent=d.count;
    document.getElementById('cc-hotmailCountLabel').textContent=d.count;
  }catch(e){}
}
async function ccLoadPendingLinkCount(){
  try{const r=await fetch('/api/capcut/pending_links/count');const d=await r.json();
    const n=d.count||0;
    document.getElementById('cc-pendingLinkCount').textContent=n;
    document.getElementById('cc-pendingLinkCount2').textContent=n;
  }catch(e){}
}
async function ccRetryLinks(){
  if(ccIsRunning){showToast('\u26a0\ufe0f','C\u00f3 task \u0111ang ch\u1ea1y, h\u00e3y d\u1eebng tr\u01b0\u1edbc!');return;}
  const threads=parseInt(document.getElementById('cc-retryThreads').value)||2;
  const r=await fetch('/api/capcut/retry_links/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({browser_type:ccBrowser,headless:ccHeadless,mail_api_source:ccMailApiSource,threads,incognito:ccIncognito})});
  const d=await r.json();
  if(!d.success){showToast('\u274c',d.error||'L\u1ed7i kh\u1eddi \u0111\u1ed9ng retry');return;}
  ccIsRunning=true;ccSetUI(true);ccStartSSE();
  showToast('\ud83d\udd04','\u0110\u00e3 b\u1eaft \u0111\u1ea7u retry '+d.total+' acc v\u1edbi '+threads+' lu\u1ed3ng!');
}
async function ccUploadHotmail(input){
  const file=input.files[0];if(!file)return;
  const fd=new FormData();fd.append('file',file);
  try{const r=await fetch('/api/capcut/hotmail/upload',{method:'POST',body:fd});const d=await r.json();
    showToast('✅','Đã upload: '+d.count+' hotmail');ccLoadHotmailCount();
  }catch(e){showToast('❌','Upload thất bại');}
}
let ccAccountsTab = 'session';
function ccSetAccountsTab(tab){
  ccAccountsTab = tab;
  document.getElementById('cc-tabAccountsSession').classList.toggle('active', tab==='session');
  document.getElementById('cc-tabAccountsAll').classList.toggle('active', tab==='all');
  ccLoadAccounts();
}
async function ccLoadAccounts(){
  try{
    const r=await fetch('/api/capcut/accounts?session=' + (ccAccountsTab==='session'));const d=await r.json();
    const tbody=document.getElementById('cc-accountsBody');
    if(!d.accounts||d.accounts.length===0){tbody.innerHTML='<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:20px;">Chưa có tài khoản nào</td></tr>';return;}
    tbody.innerHTML=d.accounts.slice().reverse().slice(0,50).map(a=>{
      const link = a.join_link || '';
      const displayLink = link.length > 30 ? link.substring(0, 30) + '...' : link;
      const linkHtml = link ? `<a href="${escHtml(link)}" target="_blank" style="font-size:12px;color:var(--accent);text-decoration:none;">${escHtml(displayLink)}</a>` : '<span style="color:var(--muted)">-</span>';
      
      return `<tr><td style="color:var(--accent)">${escHtml(a.uid||'–')}</td><td>${escHtml(a.email)}</td><td><code style="color:var(--muted)">${escHtml(a.password)}</code><br/>${linkHtml}</td><td><div style="display:flex;align-items:center;gap:6px;"><span class="tag tag-ok" style="margin:0;">✅ OK</span><button class="copy-btn" title="Copy Email | Pass | Link" onclick="navigator.clipboard.writeText('${escHtml(a.email)}\\t${escHtml(a.password)}\\t${escHtml(link)}');showToast('📋','Đã copy (có link)!');"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button></div></td></tr>`;
    }).join('');
  }catch(e){}
}
async function ccCopyAccounts(){
  try{const r=await fetch('/api/capcut/accounts/raw?session=' + (ccAccountsTab==='session'));const t=await r.text();
  if(!t.trim()){showToast('⚠️','Không có dữ liệu!');return;}
  await navigator.clipboard.writeText(t);showToast('📋','Đã copy (Full)!');}catch(e){}
}
async function ccCopyAccountsEP(){
  try{const r=await fetch('/api/capcut/accounts/raw_ep?session=' + (ccAccountsTab==='session'));const t=await r.text();
  if(!t.trim()){showToast('⚠️','Không có dữ liệu!');return;}
  await navigator.clipboard.writeText(t);showToast('📋','Đã copy (Email|Pass)!');}catch(e){}
}
async function ccCopyAccountsEPL(){
  try{const r=await fetch('/api/capcut/accounts/raw_epl?session=' + (ccAccountsTab==='session'));const t=await r.text();
  if(!t.trim()){showToast('⚠️','Không có dữ liệu!');return;}
  await navigator.clipboard.writeText(t);showToast('📋','Đã copy (Email|Pass|Link)!');}catch(e){}
}
async function ccClearAccounts(){
  showConfirmModal('Xóa tài khoản CapCut', 'Bạn có chắc chắn muốn xóa toàn bộ danh sách tài khoản CapCut đã tạo?', async () => {
    try{await fetch('/api/capcut/accounts/clear',{method:'POST'});showToast('🗑️','Đã xóa danh sách!');ccLoadAccounts();}catch(e){}
  });
}
async function ccStartTask(){
  if(ccIsRunning)return;
  const count=parseInt(document.getElementById('cc-count').value)||1;
  const threads=parseInt(document.getElementById('cc-threads').value)||1;
  const jl=document.getElementById('cc-joinLink').value.trim();
  if((ccMode===2||ccMode===4) && !jl){showToast('⚠️','Vui lòng nhập Link Join Team!');return;}
  try{
    const r=await fetch('/api/capcut/task/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:ccMode,count,threads,join_link:jl,mail_type:ccMailType,mail_api_source:ccMailApiSource,browser_type:ccBrowser,headless:ccHeadless,incognito:ccIncognito})});
    const d=await r.json();
    if(!d.success){showToast('❌',d.error);return;}
    ccIsRunning=true;ccSetUI(true);ccStartSSE();
  } catch(e) {showToast('❌', 'Lỗi khởi chạy');}
}
async function ccStopTask(){
  ccIsRunning=false; ccSetUI(false); if(ccEvt)ccEvt.close();
  await fetch('/api/capcut/task/stop',{method:'POST'});
  showToast('⏹','Đã dừng CapCut và đóng trình duyệt.');
}
async function ccCloseBrowsers(){
  try{await fetch('/api/capcut/task/close_browsers',{method:'POST'});showToast('💥','Đã đóng tất cả trình duyệt CapCut!');}catch(e){}
}
function ccStartSSE(){
  if(ccEvt)ccEvt.close(); ccEvt=new EventSource('/api/capcut/task/stream');
  ccEvt.onmessage=(e)=>{
    const data=JSON.parse(e.data);
    if(data.type==='log')ccAddLog(data);
    else if(data.type==='result'){if(data.success)ccOk++;else ccFail++;ccUpdateStats();if(data.success)ccLoadAccounts();}
    else if(data.type==='done'){ccIsRunning=false;ccSetUI(false);ccEvt.close();showToast('✅','CapCut Xong!');ccLoadHotmailCount();ccLoadAccounts();ccLoadPendingLinkCount();}
    else if(data.type==='pending_count_update'){ccLoadPendingLinkCount();ccLoadAccounts();}
    else if(data.type==='stopped'){ccIsRunning=false;ccSetUI(false);ccEvt.close();showToast('⏹','CapCut Đã dừng.');}
  };
}
function ccAddLog(data){ccLogs.push(data);if(ccLogs.length>2000)ccLogs.shift();if(ccFilter==='ALL'||data.level===ccFilter)ccRenderLog(data);}
function ccRenderLog(data){
  const wrap=document.getElementById('cc-logWrap');
  const icons={OK:'✅',ERR:'❌',WARN:'⚠️',INFO:'📌'}; const classes={OK:'log-ok',ERR:'log-err',WARN:'log-warn',INFO:'log-info'};
  const div=document.createElement('div'); div.className='log-entry '+(classes[data.level]||'log-info');
  div.innerHTML=`<span class="log-time">${data.time}</span><span class="log-icon">${icons[data.level]||'📌'}</span><span class="log-msg">${escHtml(data.msg)}</span>`;
  wrap.appendChild(div);wrap.scrollTop=wrap.scrollHeight;
}
function ccSetFilter(f,el){ccFilter=f;document.querySelectorAll('#tab-capcut .log-filter-btn').forEach(b=>b.classList.remove('active'));el.classList.add('active');document.getElementById('cc-logWrap').innerHTML='';ccLogs.filter(l=>f==='ALL'||l.level===f).forEach(ccRenderLog);}
function ccClearLog(){ccLogs=[];document.getElementById('cc-logWrap').innerHTML='';}
function ccUpdateStats(){
  document.getElementById('cc-statOk').textContent=ccOk; document.getElementById('cc-statFail').textContent=ccFail;
  const pct=ccTotal>0?Math.round(((ccOk+ccFail)/ccTotal)*100):0;
  document.getElementById('cc-statPct').textContent=pct+'%'; document.getElementById('cc-progressBar').style.width=pct+'%';
}
function ccSetUI(running){
  document.getElementById('cc-startBtn').style.display=running?'none':'flex'; document.getElementById('cc-stopBtn').style.display=running?'flex':'none';
  const dot=document.getElementById('cc-statusDot'), txt=document.getElementById('cc-statusText');
  if(running){dot.className='dot running';txt.textContent='Đang chạy...';}else{dot.className='dot';txt.textContent='Idle';}
}

// ==== HIGGSFIELD ====
let hfBrowser=localStorage.getItem('hfBrowser')||'chrome', hfHeadless=(localStorage.getItem('hfHeadless')==='true'), hfFilter='ALL', hfLogs=[], hfOk=0, hfFail=0, hfTotal=0;
function hfSetBrowser(b){
  hfBrowser=b;
  localStorage.setItem('hfBrowser', b);
  document.getElementById('hf-browserChrome').classList.toggle('active',b==='chrome');
  document.getElementById('hf-browserFirefox').classList.toggle('active',b==='firefox');
  document.getElementById('hf-browserCamoufox').classList.toggle('active',b==='camoufox');
}
function hfToggleHeadless(){
  hfHeadless=!hfHeadless;
  localStorage.setItem('hfHeadless', hfHeadless);
  document.getElementById('hf-headlessToggle').classList.toggle('active',hfHeadless);
}
async function hfLoadAccounts(){
  try{
    const r=await fetch('/api/higgsfield/accounts');const d=await r.json();
    const tbody=document.getElementById('hf-accountsBody');
    if(!d.accounts||d.accounts.length===0){tbody.innerHTML='<tr><td colspan="3" style="text-align:center;color:var(--muted);padding:20px;">Chưa có tài khoản nào</td></tr>';return;}
    tbody.innerHTML=d.accounts.slice().reverse().slice(0,50).map(a=>`<tr><td>${escHtml(a.email)}</td><td><code style="color:var(--muted)">${escHtml(a.password)}</code></td><td><div style="display:flex;align-items:center;gap:6px;"><span class="tag tag-ok" style="margin:0;">✅ OK</span><button class="copy-btn" title="Copy Email|Pass" onclick="navigator.clipboard.writeText('${escHtml(a.email)}|${escHtml(a.password)}');showToast('📋','Đã copy!');"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button></div></td></tr>`).join('');
  }catch(e){}
}
async function hfCopyAccounts(){
  try{const r=await fetch('/api/higgsfield/accounts/raw');const t=await r.text();await navigator.clipboard.writeText(t);showToast('📋','Đã copy!');}catch(e){}
}
async function hfClearAccounts(){
  showConfirmModal('Xóa tài khoản Higgsfield', 'Bạn có chắc chắn muốn xóa toàn bộ danh sách tài khoản Higgsfield đã tạo?', async () => {
    try{await fetch('/api/higgsfield/accounts/clear',{method:'POST'});showToast('🗑️','Đã xóa danh sách!');hfLoadAccounts();}catch(e){}
  });
}
async function hfStartTask(){
  if(hfIsRunning)return;
  const count=parseInt(document.getElementById('hf-count').value)||1;
  const threads=parseInt(document.getElementById('hf-threads').value)||1;
  hfOk=0;hfFail=0;hfTotal=count;hfUpdateStats();
  const r=await fetch('/api/higgsfield/task/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count,threads,headless:hfHeadless,browser_type:hfBrowser})});
  const d=await r.json();
  if(!d.success){showToast('❌',d.error);return;}
  hfIsRunning=true;hfSetUI(true);hfStartSSE();
}
async function hfStopTask(){
  hfIsRunning=false; hfSetUI(false); if(hfEvt)hfEvt.close();
  await fetch('/api/higgsfield/task/stop',{method:'POST'});
  showToast('⏹','Đã dừng Higgsfield và đóng trình duyệt.');
}
async function hfCloseBrowsers(){
  try{await fetch('/api/higgsfield/task/close_browsers',{method:'POST'});showToast('💥','Đã đóng tất cả trình duyệt Higgsfield!');}catch(e){}
}
function hfStartSSE(){
  if(hfEvt)hfEvt.close(); hfEvt=new EventSource('/api/higgsfield/task/stream');
  hfEvt.onmessage=(e)=>{
    const data=JSON.parse(e.data);
    if(data.type==='log')hfAddLog(data);
    else if(data.type==='result'){if(data.success)hfOk++;else hfFail++;hfUpdateStats();if(data.success)hfLoadAccounts();}
    else if(data.type==='done'){hfIsRunning=false;hfSetUI(false);hfEvt.close();showToast('✅','Higgsfield Xong!');hfLoadAccounts();}
    else if(data.type==='stopped'){hfIsRunning=false;hfSetUI(false);hfEvt.close();showToast('⏹','Higgsfield Đã dừng.');}
  };
}
function hfAddLog(data){hfLogs.push(data);if(hfLogs.length>2000)hfLogs.shift();if(hfFilter==='ALL'||data.level===hfFilter)hfRenderLog(data);}
function hfRenderLog(data){
  const wrap=document.getElementById('hf-logWrap');
  const icons={OK:'✅',ERR:'❌',WARN:'⚠️',INFO:'📌'}; const classes={OK:'log-ok',ERR:'log-err',WARN:'log-warn',INFO:'log-info'};
  const div=document.createElement('div'); div.className='log-entry '+(classes[data.level]||'log-info');
  div.innerHTML=`<span class="log-time">${data.time}</span><span class="log-icon">${icons[data.level]||'📌'}</span><span class="log-msg">${escHtml(data.msg)}</span>`;
  wrap.appendChild(div);wrap.scrollTop=wrap.scrollHeight;
}
function hfSetFilter(f,el){hfFilter=f;document.querySelectorAll('#tab-higgsfield .log-filter-btn').forEach(b=>b.classList.remove('active'));el.classList.add('active');document.getElementById('hf-logWrap').innerHTML='';hfLogs.filter(l=>f==='ALL'||l.level===f).forEach(hfRenderLog);}
function hfClearLog(){hfLogs=[];document.getElementById('hf-logWrap').innerHTML='';}
function hfUpdateStats(){
  document.getElementById('hf-statOk').textContent=hfOk; document.getElementById('hf-statFail').textContent=hfFail;
  const pct=hfTotal>0?Math.round(((hfOk+hfFail)/hfTotal)*100):0;
  document.getElementById('hf-statPct').textContent=pct+'%'; document.getElementById('hf-progressBar').style.width=pct+'%';
}
function hfSetUI(running){
  document.getElementById('hf-startBtn').style.display=running?'none':'flex'; document.getElementById('hf-stopBtn').style.display=running?'flex':'none';
  const dot=document.getElementById('hf-statusDot'), txt=document.getElementById('hf-statusText');
  if(running){dot.className='dot running';txt.textContent='Đang chạy...';}else{dot.className='dot';txt.textContent='Idle';}
}

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
  const d_btn = document.getElementById('gpt-mailDomain');
  if(d_btn) d_btn.classList.toggle('active', m === 'domain');
  
  // Hien/an hotmail file group
  const hotmailGroup = document.getElementById('gpt-hotmailGroup');
  if(hotmailGroup) hotmailGroup.style.display = (m === 'outlook') ? 'block' : 'none';
  const apiGroup = document.getElementById('gpt-apiSourceGroup');
  if(apiGroup) apiGroup.style.display = (m === 'outlook') ? 'block' : 'none';
  // Cap nhat label va hint cho count input
  const lbl = document.getElementById('gpt-countLabel');
  const hint = document.getElementById('gpt-countHint');
  if(m === 'gmail94'){
    if(lbl) lbl.textContent = 'Số Gmail cần mua (mỗi Gmail = 4 GPT)';
    if(hint) hint.style.display = 'block';
    gptUpdateCountHint();
  } else {
    if(lbl) lbl.textContent = 'Số lượng tài khoản cần tạo';
    if(hint) hint.style.display = 'none';
  }
}

function gptUpdateCountHint(){
  if(gptMailType !== 'gmail94') return;
  const count = parseInt(document.getElementById('gpt-count').value) || 0;
  const total = count * 4;
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
        const audio = new Audio('/static/nhac_chuong_pokemon_black_and_white_tiktok-www_tiengdong_com.mp3');
        audio.play();
        setTimeout(() => {
            audio.pause();
            audio.currentTime = 0;
        }, 10000);
    } catch(e) {
        console.log("Audio not supported");
    }
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
      
      // 2. Format Payment Methods (MoMo) - chỉ hiện Có/Không
      const pms = (a.momo && a.momo !== 'không' && a.momo !== 'lỗi') ? a.momo.toLowerCase() : '';
      const hasMomo = pms.includes('momo') || pms === 'có'; // Fallback cho DB cũ

      let momoHtml = '';
      if (hasMomo) {
          momoHtml = `<span style="display:inline-block;padding:2px 10px;border-radius:10px;font-size:10px;font-weight:600;background:rgba(168,85,247,0.18);color:#d8b4fe;border:1px solid rgba(168,85,247,0.4);">✓ Có MoMo</span>`;
      } else {
          momoHtml = `<span style="color:var(--muted);font-size:11px;">Không</span>`;
      }
      
      // Highlight màu dòng nếu có MoMo
      const rowStyle = hasMomo ? 'background: rgba(168,85,247,0.06);' : '';
      
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

  // Gmail94: mỗi lần mua 1 Gmail sẽ tạo 4 biến thể GPT
  gptOk=0;gptFail=0;
  gptTotal = (gptMailType === 'gmail94') ? count * 4 : count;
  gptUpdateStats();

  const r=await fetch('/api/gpt/task/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count,threads,mail_type:gptMailType,creation_method:gptCreationMethod,check_momo:checkMomo,mail_api_source:gptApiSource,keep_open:gptKeepOpen,driver_mode:'playwright_ui',browser_type:gptBrowser,headless:gptHeadless,incognito:gptIncognito})});
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
    
    // Play ting ting sound if MoMo is detected
    if(data.msg && data.msg.includes('Phát hiện MoMo')) {
        playMomoSound();
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
}

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
            
            if (badgeFilter === 'momo') badgeMatch = hasMomo;
            else if (badgeFilter === 'trial') badgeMatch = hasTrial;
            else if (badgeFilter === 'momo_trial') badgeMatch = hasMomo && hasTrial;
            else if (badgeFilter === 'trial_no_momo') badgeMatch = hasTrial && !hasMomo;
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

