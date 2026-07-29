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
  try {
    const r = await fetch('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    const d = await r.json();
    if(d.success) showToast('✅', 'Đã lưu cấu hình!');
    else showToast('❌', 'Lỗi lưu cấu hình');
  } catch(e) { showToast('❌', 'Lỗi kết nối'); }
}

async function loadProxyStatus(){
  try{
    const r=await fetch('/api/proxy/status');const d=await r.json();
    ['cc','hf','gpt'].forEach(pfx=>{
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
    }, 5 * 60 * 1000);
  }
}

function toggleAutoRotate(checked) {
  const checkboxes = document.querySelectorAll('.auto-rotate-cb');
  checkboxes.forEach(cb => cb.checked = checked);
  resetAutoRotateTimer();
  if(checked) showToast('✅', 'Đã BẬT tự động xoay IP (5 phút)');
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
  
  hfSetBrowser(hfBrowser);
  if(hfHeadless) document.getElementById('hf-headlessToggle').classList.add('active');
  
  checkRunningStatus();
};

// ==== CAPCUT ====
let ccMode=1, ccMailType='hotmail', ccMailApiSource='dongvanfb', ccBrowser=localStorage.getItem('ccBrowser')||'chrome', ccHeadless=(localStorage.getItem('ccHeadless')==='true'), ccFilter='ALL', ccLogs=[], ccOk=0, ccFail=0, ccTotal=0;
function ccSetMode(m){ccMode=m;document.getElementById('cc-mode1').classList.toggle('active',m===1);document.getElementById('cc-mode2').classList.toggle('active',m===2);if(document.getElementById('cc-mode3'))document.getElementById('cc-mode3').classList.toggle('active',m===3);document.getElementById('cc-joinLinkGroup').style.display=m===2?'block':'none';}
function ccSetMailType(m){
  ccMailType=m;
  document.getElementById('cc-mailHotmail').classList.toggle('active',m==='hotmail');
  document.getElementById('cc-mailDomain').classList.toggle('active',m==='domain');
  document.getElementById('cc-hotmailGroup').style.display=m==='hotmail'?'block':'none';
  if(document.getElementById('cc-apiSourceGroup')) document.getElementById('cc-apiSourceGroup').style.display=m==='hotmail'?'block':'none';
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
  const r=await fetch('/api/capcut/retry_links/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({browser_type:ccBrowser,headless:ccHeadless,mail_api_source:ccMailApiSource,threads})});
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
  if(ccMode===2 && !jl){showToast('⚠️','Vui lòng nhập Link Join Team!');return;}
  try{
    const r=await fetch('/api/capcut/task/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:ccMode,count,threads,join_link:jl,mail_type:ccMailType,mail_api_source:ccMailApiSource,browser_type:ccBrowser,headless:ccHeadless})});
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

function gptSetMailType(m){
  gptMailType = m;
  // Only hotmail is supported
  document.getElementById('gpt-mailHotmail').classList.toggle('active', true);
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

async function gptLoadAccounts(){
  try{
    const r=await fetch('/api/gpt/accounts');const d=await r.json();
    const tbody=document.getElementById('gpt-accountsBody');
    if(!d.accounts||d.accounts.length===0){
      tbody.innerHTML='<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:20px;">Chưa có tài khoản nào</td></tr>';
      return;
    }
    tbody.innerHTML=d.accounts.slice().reverse().slice(0,50).map(a=>{
      const twofa = a.twofa || '';
      const momoHtml = (a.momo === 'có') ? '<span style="color:#d82d8b;font-weight:bold;">Có</span>' : '<span style="color:var(--muted)">Không</span>';
      return `<tr><td>${escHtml(a.email)}</td><td><code style="color:var(--muted)">${escHtml(a.password)}</code></td><td><code style="color:var(--accent);font-size:10px;">${escHtml(twofa)||'<span style="color:var(--muted)">N/A</span>'}</code></td><td>${momoHtml}</td><td><div style="display:flex;align-items:center;gap:6px;"><span class="tag tag-ok" style="margin:0;">✅ OK</span><button class="copy-btn" title="Copy Email|Pass|2FA" onclick="navigator.clipboard.writeText('${escHtml(a.email)}|${escHtml(a.password)}|${escHtml(twofa)}');showToast('📋','Đã copy!');"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button></div></td></tr>`;
    }).join('');
  }catch(e){}
}

async function gptCopyAccounts(){
  try{const r=await fetch('/api/gpt/accounts/raw_ep');const t=await r.text();await navigator.clipboard.writeText(t);showToast('📋','Đã copy (Email|Pass|2FA)!');}catch(e){}
}

async function gptClearAccounts(){
  showConfirmModal('Xóa tài khoản GPT', 'Bạn có chắc chắn muốn xóa toàn bộ danh sách tài khoản GPT đã tạo?', async () => {
    try{await fetch('/api/gpt/accounts/clear',{method:'POST'});showToast('🗑️','Đã xóa danh sách!');gptLoadAccounts();}catch(e){}
  });
}

function gptRefreshAccounts() {
    gptLoadAccounts();
}

async function gptStartTask(){
  if(gptIsRunning)return;
  const count=parseInt(document.getElementById('gpt-count').value)||1;
  const threads=parseInt(document.getElementById('gpt-workers').value)||1;
  const checkMomo=document.getElementById('gpt-checkMomo').checked;
  
  gptOk=0;gptFail=0;gptTotal=count;gptUpdateStats();
  const r=await fetch('/api/gpt/task/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count,threads,mail_type:gptMailType,check_momo:checkMomo})});
  const d=await r.json();
  if(!d.success){showToast('❌',d.error);return;}
  gptIsRunning=true;gptSetUI(true);gptStartSSE();
}

async function gptStopTask(){
  gptIsRunning=false; gptSetUI(false); if(gptEvt)gptEvt.close();
  await fetch('/api/gpt/task/stop',{method:'POST'});
  showToast('⏹','Đã dừng GPT.');
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

function gptAddLog(data){gptLogs.push(data);if(gptLogs.length>2000)gptLogs.shift();if(gptFilter==='ALL'||data.level===gptFilter)gptRenderLog(data);}
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
