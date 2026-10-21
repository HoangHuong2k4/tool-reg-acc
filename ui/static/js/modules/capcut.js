// ==== CAPCUT ====
let ccMode=3, ccMailType='hotmail', ccMailApiSource='dongvanfb', ccDomainSource='phhinfi', ccBrowser=localStorage.getItem('ccBrowser')||'chrome', ccHeadless=(localStorage.getItem('ccHeadless')==='true'), ccIncognito=(localStorage.getItem('ccIncognito')==='true'), ccSaveTrial7day=(localStorage.getItem('ccSaveTrial7day')==='true'), ccFilter='ALL', ccLogs=[], ccOk=0, ccFail=0, ccTotal=0;
function ccSetMode(m){ccMode=m;[1,2,3,4].forEach(i=>{const el=document.getElementById('cc-mode'+i);if(el)el.classList.toggle('active',m===i);});document.getElementById('cc-joinLinkGroup').style.display=(m===2||m===4)?'block':'none';const isApiMode=m===4;document.getElementById('cc-browserGroup').style.display=isApiMode?'none':'block';document.getElementById('cc-headlessGroup').style.display=isApiMode?'none':'block';}
function ccSetMailType(m){
  ccMailType=m;
  document.getElementById('cc-mailHotmail').classList.toggle('active',m==='hotmail');
  document.getElementById('cc-mailDomain').classList.toggle('active',m==='domain');
  document.getElementById('cc-hotmailGroup').style.display=m==='hotmail'?'block':'none';
  if(document.getElementById('cc-apiSourceGroup')) document.getElementById('cc-apiSourceGroup').style.display=m==='hotmail'?'block':'none';
  // Show/hide domain source selector
  const domainSourceGroup = document.getElementById('cc-domainSourceGroup');
  if(domainSourceGroup) domainSourceGroup.style.display=m==='domain'?'block':'none';
  // Ẩn nút API Mode nếu chọn Hotmail (vì API Mode chỉ dùng Mail Domain)
  const mode4Btn = document.getElementById('cc-mode4');
  if(mode4Btn) mode4Btn.style.display = m==='hotmail'?'none':'block';
  // Nếu đang ở mode 4 mà chuyển sang hotmail, reset về mode 1
  if(m==='hotmail' && ccMode===4) ccSetMode(1);
}
function ccSetDomainSource(src){
  ccDomainSource=src;
  document.getElementById('cc-domainPhhinfi').classList.toggle('active',src==='phhinfi');
  document.getElementById('cc-domainMailtemp').classList.toggle('active',src==='mailtemp');
  const infoEl=document.getElementById('cc-mailtempInfo');
  if(infoEl) infoEl.style.display=src==='mailtemp'?'block':'none';
  // Show/hide mailtemp section
  mtShowSection(src==='mailtemp');
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
function ccToggleTrial7day(checked) {
  ccSaveTrial7day = !!checked;
  localStorage.setItem('ccSaveTrial7day', ccSaveTrial7day);
}
function ccInitTrialCheckbox() {
  const cb = document.getElementById('cc-saveTrial7day');
  if (cb) cb.checked = ccSaveTrial7day;
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', ccInitTrialCheckbox);
} else {
  ccInitTrialCheckbox();
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
      const isTrial = (a.uudai === 'trial_7day');
      const trialBadge = isTrial ? '<span class="tag" style="margin:0;background:rgba(234,179,8,0.2);color:#eab308;border:1px solid #eab308;font-size:10px;">🎁 Trial 7D</span>' : '';
      
      return `<tr><td style="color:var(--accent)">${escHtml(a.uid||'–')}</td><td>${escHtml(a.email)}</td><td><code style="color:var(--muted)">${escHtml(a.password)}</code><br/>${linkHtml}</td><td><div style="display:flex;align-items:center;gap:6px;"><span class="tag tag-ok" style="margin:0;">✅ OK</span>${trialBadge}<button class="copy-btn" title="Copy Email | Pass | Link" onclick="navigator.clipboard.writeText('${escHtml(a.email)}\\t${escHtml(a.password)}\\t${escHtml(link)}');showToast('📋','Đã copy (có link)!');"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button></div></td></tr>`;
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
async function ccCopyTrial7day(){
  try{
    const r=await fetch('/api/capcut/accounts/raw_trial_7day?session=' + (ccAccountsTab==='session'));
    const t=await r.text();
    if(!t.trim()){showToast('⚠️','Chưa có link Trial 7 ngày nào!');return;}
    await navigator.clipboard.writeText(t);showToast('🎉','Đã copy danh sách link Trial 7 ngày!');
  }catch(e){showToast('❌','Lỗi copy link Trial!');}
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
  const saveTrial7day = document.getElementById('cc-saveTrial7day') ? document.getElementById('cc-saveTrial7day').checked : ccSaveTrial7day;
  if((ccMode===2||ccMode===4) && !jl){showToast('⚠️','Vui lòng nhập Link Join Team!');return;}
  try{
    const r=await fetch('/api/capcut/task/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:ccMode,count,threads,join_link:jl,mail_type:ccMailType,mail_api_source:ccMailApiSource,mail_domain_source:ccDomainSource,browser_type:ccBrowser,headless:ccHeadless,incognito:ccIncognito,save_trial_7day:saveTrial7day})});
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

