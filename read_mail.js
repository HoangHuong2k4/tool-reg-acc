// ── URL config ──
var IS_LOCAL = (location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.hostname === '');
var BASE     = IS_LOCAL ? 'http://localhost:3000' : 'https://tools.dongvanfb.net';
var BASE_API = IS_LOCAL ? 'http://localhost:3000' : 'https://api.dongvanfb.net';
var URL_MAIL   = BASE     + '/api/get_messages_oauth2';
var URL_OAUTH  = BASE_API + '/api/getOauth2';

// Stored oauth2 results for "send to mail" feature
var oauth2Results = [];

// Stats for mail panel
var mailStats = { total: 0, ok: 0, err: 0, msgs: 0 };

// ── Panel switch ──
function switchPanel(name) {
  document.querySelectorAll('.panel').forEach(function(el) { el.classList.remove('active'); });
  document.querySelectorAll('.topbar-tab').forEach(function(el) { el.classList.remove('active'); });
  document.getElementById('panel-' + name).classList.add('active');
  event.currentTarget.classList.add('active');
}

// ── Clipboard ──
function pasteClipboard(id) {
  if (navigator.clipboard && navigator.clipboard.readText) {
    navigator.clipboard.readText().then(function(t) {
      document.getElementById(id).value = t;
    }).catch(function() { alert('Dan thu cong Ctrl+V.'); });
  } else { alert('Dan thu cong Ctrl+V.'); }
}

// ── Progress ──
function setProgress(prefix, pct, msg) {
  document.getElementById('prog-' + prefix).style.display = 'block';
  document.getElementById('progBar-' + prefix).style.width = pct + '%';
  document.getElementById('progText-' + prefix).textContent = msg;
}

// ── Escape HTML ──
function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Parse input lines ──
function parseMailAccounts(raw) {
  var accounts = [];
  raw.split('\n').forEach(function(line) {
    line = line.trim();
    if (!line) return;
    var parts = line.split('|');
    if (parts.length < 4) return;
    accounts.push({
      email:         parts[0].trim(),
      pass:          parts[1].trim(),
      refresh_token: parts.slice(2, parts.length - 1).join('|').trim(),
      client_id:     parts[parts.length - 1].trim()
    });
  });
  return accounts;
}

// ═══════════════════════════════════════════
// GET OAUTH2
// ═══════════════════════════════════════════
function clearOauth2() {
  document.getElementById('oauth2ResultCard').style.display = 'none';
  document.getElementById('oauth2Tbody').innerHTML = '';
  document.getElementById('btnUseInMail').style.display = 'none';
  document.getElementById('prog-oauth2').style.display = 'none';
  oauth2Results = [];
}

async function startGetOauth2() {
  var raw    = document.getElementById('oauth2Input').value.trim();
  var apikey = document.getElementById('apikeyInput').value.trim();
  if (!raw)    { alert('Vui long nhap danh sach tai khoan!'); return; }
  if (!apikey) { alert('Vui long nhap API Key!'); return; }

  var lines = raw.split('\n').map(function(l) { return l.trim(); }).filter(Boolean);
  var accs  = [];
  lines.forEach(function(line) {
    var p = line.split('|');
    if (p.length >= 2) accs.push({ email: p[0].trim(), pass: p.slice(1).join('|').trim() });
  });
  if (!accs.length) { alert('Khong tim thay tai khoan hop le!'); return; }

  oauth2Results = [];
  var tbody = document.getElementById('oauth2Tbody');
  tbody.innerHTML = '';
  document.getElementById('oauth2ResultCard').style.display = 'block';
  document.getElementById('btnUseInMail').style.display = 'none';

  var btn = document.getElementById('btnGetOauth');
  btn.disabled = true;

  for (var i = 0; i < accs.length; i++) {
    var acc = accs[i];
    var pct = Math.round((i / accs.length) * 100);
    setProgress('oauth2', pct, '[' + (i+1) + '/' + accs.length + '] ' + acc.email);

    // Insert pending row
    var tr = document.createElement('tr');
    tr.id = 'orow-' + i;
    tr.innerHTML =
      '<td class="cell-email">' + esc(acc.email) + '</td>' +
      '<td class="cell-token" id="otoken-' + i + '">Dang lay...</td>' +
      '<td class="cell-token" id="ocid-' + i + '"></td>' +
      '<td class="cell-status"><span class="badge badge-wait" id="ostatd-' + i + '">⏳</span></td>' +
      '<td><button class="btn-copy" id="ocopy-' + i + '" style="display:none" onclick="copyOauthRow(' + i + ')">Copy</button></td>';
    tbody.appendChild(tr);

    await fetchOauth2(acc, apikey, i);
  }

  setProgress('oauth2', 100, 'Hoan tat ' + accs.length + ' tai khoan');
  btn.disabled = false;

  if (oauth2Results.some(function(r) { return r.ok; })) {
    document.getElementById('btnUseInMail').style.display = 'inline-flex';
  }
}

async function fetchOauth2(acc, apikey, idx) {
  try {
    var res  = await fetch(URL_OAUTH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: acc.email, password: acc.pass, apikey: apikey })
    });
    var data = await res.json();

    if (data.status && data.oauth2) {
      // oauth2 = "refresh_token|client_id"
      var parts = data.oauth2.split('|');
      var clientId      = parts[parts.length - 1];
      var refreshToken  = parts.slice(0, parts.length - 1).join('|');

      document.getElementById('otoken-' + idx).textContent  = refreshToken;
      document.getElementById('ocid-' + idx).textContent    = clientId;
      document.getElementById('ostatd-' + idx).className    = 'badge badge-ok';
      document.getElementById('ostatd-' + idx).textContent  = 'OK';
      document.getElementById('ocopy-' + idx).style.display = 'inline-block';

      oauth2Results[idx] = {
        ok: true,
        email: acc.email,
        pass: acc.pass,
        refresh_token: refreshToken,
        client_id: clientId,
        raw: data.oauth2
      };
    } else {
      var errMsg = data.message || data.error || JSON.stringify(data);
      document.getElementById('otoken-' + idx).textContent  = errMsg;
      document.getElementById('ostatd-' + idx).className    = 'badge badge-err';
      document.getElementById('ostatd-' + idx).textContent  = 'Loi';
      oauth2Results[idx] = { ok: false, email: acc.email };
    }
  } catch(e) {
    document.getElementById('otoken-' + idx).textContent = 'Loi ket noi: ' + e.message;
    document.getElementById('ostatd-' + idx).className   = 'badge badge-err';
    document.getElementById('ostatd-' + idx).textContent = 'Loi';
    oauth2Results[idx] = { ok: false, email: acc.email };
  }
}

function copyOauthRow(idx) {
  var r = oauth2Results[idx];
  if (!r || !r.ok) return;
  var text = r.email + '|' + r.pass + '|' + r.refresh_token + '|' + r.client_id;
  navigator.clipboard.writeText(text).then(function() {
    var btn = document.getElementById('ocopy-' + idx);
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(function() { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1500);
  }).catch(function() { alert(text); });
}

function sendToMail() {
  var lines = oauth2Results
    .filter(function(r) { return r && r.ok; })
    .map(function(r) { return r.email + '|' + r.pass + '|' + r.refresh_token + '|' + r.client_id; });
  document.getElementById('mailInput').value = lines.join('\n');

  // Switch to mail tab
  document.querySelectorAll('.panel').forEach(function(el) { el.classList.remove('active'); });
  document.querySelectorAll('.topbar-tab').forEach(function(el) { el.classList.remove('active'); });
  document.getElementById('panel-mail').classList.add('active');
  document.querySelectorAll('.topbar-tab')[1].classList.add('active');
}

// ═══════════════════════════════════════════
// READ MAIL
// ═══════════════════════════════════════════
function clearMail() {
  document.getElementById('mailResults').innerHTML = '';
  document.getElementById('mailStats').style.display = 'none';
  document.getElementById('prog-mail').style.display = 'none';
  mailStats = { total: 0, ok: 0, err: 0, msgs: 0 };
}

function updateStats() {
  document.getElementById('mailStats').style.display = 'flex';
  document.getElementById('stat-total').textContent = mailStats.total;
  document.getElementById('stat-ok').textContent    = mailStats.ok;
  document.getElementById('stat-err').textContent   = mailStats.err;
  document.getElementById('stat-msgs').textContent  = mailStats.msgs;
}

async function startReadMail() {
  var raw = document.getElementById('mailInput').value.trim();
  if (!raw) { alert('Vui long nhap danh sach tai khoan!'); return; }

  var accounts = parseMailAccounts(raw);
  if (!accounts.length) { alert('Khong tim thay tai khoan hop le! (Can du 4 truong: email|pass|refresh_token|client_id)'); return; }

  document.getElementById('mailResults').innerHTML = '';
  mailStats = { total: accounts.length, ok: 0, err: 0, msgs: 0 };

  var btn = document.getElementById('btnReadMail');
  btn.disabled = true;
  updateStats();

  for (var i = 0; i < accounts.length; i++) {
    setProgress('mail', Math.round((i / accounts.length) * 100), '[' + (i+1) + '/' + accounts.length + '] ' + accounts[i].email);
    await renderMailAccount(accounts[i]);
  }

  setProgress('mail', 100, 'Hoan tat ' + accounts.length + ' tai khoan');
  btn.disabled = false;
}

function renderMailAccount(acc) {
  return new Promise(function(resolve) {
    var sid = 'sid_' + Math.random().toString(36).substr(2, 9);

    var block = document.createElement('div');
    block.className = 'account-block';

    var header = document.createElement('div');
    header.className = 'acct-header';

    var emailEl = document.createElement('div');
    emailEl.className = 'acct-email';
    emailEl.textContent = acc.email;

    var badge = document.createElement('span');
    badge.className = 'badge badge-wait';
    badge.id = 'abadge-' + sid;
    badge.textContent = '⏳ Dang tai...';

    var countEl = document.createElement('span');
    countEl.className = 'acct-count';
    countEl.id = 'acount-' + sid;

    header.appendChild(emailEl);
    header.appendChild(badge);
    header.appendChild(countEl);

    var listEl = document.createElement('div');
    listEl.id = 'alist-' + sid;
    var loadingMsg = document.createElement('div');
    loadingMsg.className = 'empty-msg';
    loadingMsg.textContent = 'Dang ket noi...';
    listEl.appendChild(loadingMsg);

    block.appendChild(header);
    block.appendChild(listEl);
    document.getElementById('mailResults').appendChild(block);

    fetch(URL_MAIL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: acc.email, pass: acc.pass, refresh_token: acc.refresh_token, client_id: acc.client_id })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.status) {
        badge.className = 'badge badge-err';
        badge.textContent = 'X Loi';
        listEl.innerHTML = '';
        var errEl = document.createElement('div');
        errEl.className = 'err-msg';
        errEl.textContent = 'Loi: ' + (data.message || data.error || JSON.stringify(data));
        listEl.appendChild(errEl);
        mailStats.err++;
        updateStats();
        resolve();
        return;
      }

      badge.className = 'badge badge-ok';
      badge.textContent = '✓ OK';
      mailStats.ok++;

      var messages = data.messages || [];
      mailStats.msgs += messages.length;
      countEl.textContent = messages.length + ' mail';
      updateStats();

      listEl.innerHTML = '';
      if (!messages.length) {
        var empty = document.createElement('div');
        empty.className = 'empty-msg';
        empty.textContent = 'Hop thu trong';
        listEl.appendChild(empty);
        resolve();
        return;
      }

      messages.forEach(function(msg, idx) {
        var itemId = sid + '_' + idx;
        var code   = extractCode(msg.message || '');
        var item   = document.createElement('div');
        item.className = 'mail-item';

        var summary = document.createElement('div');
        summary.className = 'mail-summary';
        summary.addEventListener('click', function() { toggleMail(itemId); });

        var subjEl = document.createElement('div');
        subjEl.className = 'mail-subj';
        subjEl.textContent = msg.subject || '(Khong co tieu de)';

        var dateEl = document.createElement('div');
        dateEl.className = 'mail-date';
        dateEl.textContent = msg.date || '';

        var fromEl = document.createElement('div');
        fromEl.className = 'mail-from';
        fromEl.textContent = msg.from || '';

        summary.appendChild(subjEl);
        summary.appendChild(dateEl);
        summary.appendChild(fromEl);

        if (code) {
          var pill = document.createElement('div');
          var cspan = document.createElement('span');
          cspan.className = 'mail-code-pill';
          cspan.textContent = 'CODE: ' + code;
          pill.appendChild(cspan);
          summary.appendChild(pill);
        }

        // Body panel
        var bodyWrap = document.createElement('div');
        bodyWrap.className = 'mail-body-wrap';
        bodyWrap.id = 'body-' + itemId;

        var tabBar = document.createElement('div');
        tabBar.className = 'mail-tabs';

        var btnHtml = document.createElement('button');
        btnHtml.className = 'mail-tab active';
        btnHtml.id = 'mtab-html-' + itemId;
        btnHtml.textContent = 'HTML Preview';
        btnHtml.addEventListener('click', function(e) { e.stopPropagation(); switchMailTab(itemId, 'html'); });

        var btnRaw = document.createElement('button');
        btnRaw.className = 'mail-tab';
        btnRaw.id = 'mtab-raw-' + itemId;
        btnRaw.textContent = 'Raw';
        btnRaw.addEventListener('click', function(e) { e.stopPropagation(); switchMailTab(itemId, 'raw'); });

        tabBar.appendChild(btnHtml);
        tabBar.appendChild(btnRaw);

        var content = document.createElement('div');
        content.className = 'mail-content';

        var iframeBox = document.createElement('div');
        iframeBox.className = 'iframe-box';
        iframeBox.id = 'mtab-html-box-' + itemId;
        var iframe = document.createElement('iframe');
        iframe.id = 'mframe-' + itemId;
        iframe.setAttribute('sandbox', 'allow-same-origin allow-popups');
        iframeBox.appendChild(iframe);

        var rawBox = document.createElement('div');
        rawBox.className = 'raw-txt';
        rawBox.id = 'mtab-raw-box-' + itemId;
        rawBox.style.display = 'none';
        rawBox.textContent = msg.message || '';

        content.appendChild(iframeBox);
        content.appendChild(rawBox);
        bodyWrap.appendChild(tabBar);
        bodyWrap.appendChild(content);
        item.appendChild(summary);
        item.appendChild(bodyWrap);
        listEl.appendChild(item);
      });

      resolve();
    })
    .catch(function(err) {
      badge.className = 'badge badge-err';
      badge.textContent = 'X Loi';
      listEl.innerHTML = '';
      var errEl = document.createElement('div');
      errEl.className = 'err-msg';
      errEl.textContent = 'Loi ket noi: ' + err.message;
      listEl.appendChild(errEl);
      mailStats.err++;
      updateStats();
      resolve();
    });
  });
}

function toggleMail(itemId) {
  var bodyWrap = document.getElementById('body-' + itemId);
  if (!bodyWrap) return;
  var open = bodyWrap.classList.contains('open');
  if (!open) {
    bodyWrap.classList.add('open');
    var frame = document.getElementById('mframe-' + itemId);
    if (frame && !frame._loaded) {
      frame._loaded = true;
      var rawEl = document.getElementById('mtab-raw-box-' + itemId);
      var html  = extractHtmlFromMime(rawEl ? rawEl.textContent : '');
      try {
        var doc = frame.contentDocument || frame.contentWindow.document;
        doc.open(); doc.write(html); doc.close();
      } catch(e) { frame.srcdoc = html; }
    }
  } else {
    bodyWrap.classList.remove('open');
  }
}

function switchMailTab(itemId, tab) {
  var htmlBox = document.getElementById('mtab-html-box-' + itemId);
  var rawBox  = document.getElementById('mtab-raw-box-'  + itemId);
  var btnH    = document.getElementById('mtab-html-' + itemId);
  var btnR    = document.getElementById('mtab-raw-'  + itemId);
  if (tab === 'html') {
    htmlBox.style.display = ''; rawBox.style.display = 'none';
    btnH.classList.add('active'); btnR.classList.remove('active');
  } else {
    htmlBox.style.display = 'none'; rawBox.style.display = '';
    btnH.classList.remove('active'); btnR.classList.add('active');
  }
}

// ── MIME / Code helpers ──
function extractHtmlFromMime(raw) {
  var m = raw.match(/Content-Transfer-Encoding:\s*base64[\r\n]+([\s\S]+?)(?=\r?\n--|\n--|$)/i);
  if (m) {
    try {
      var dec = atob(m[1].replace(/[\r\n\s]/g, ''));
      if (dec.toLowerCase().indexOf('<html') !== -1) return dec;
    } catch(e) {}
  }
  var hm = raw.match(/<html[\s\S]*?<\/html>/i);
  if (hm) return hm[0];
  return '<html><body><pre style="font:12px monospace;word-break:break-all;white-space:pre-wrap;padding:12px">' +
    raw.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</pre></body></html>';
}

function extractCode(raw) {
  var text = raw;
  var b64 = raw.match(/Content-Transfer-Encoding:\s*base64[\r\n]+([\s\S]+?)(?=\r?\n--|\n--|$)/i);
  if (b64) { try { text = atob(b64[1].replace(/[\r\n\s]/g, '')); } catch(e) {} }
  text = text.replace(/<[^>]+>/g, ' ');
  var patterns = [/(?:code|OTP|verification)[^\d]*(\d{4,8})/i, /\b(\d{6,8})\b/];
  for (var i = 0; i < patterns.length; i++) {
    var m = text.match(patterns[i]);
    if (m && m[1]) return m[1];
  }
  return null;
}
