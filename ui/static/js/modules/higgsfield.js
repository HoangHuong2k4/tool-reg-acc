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

