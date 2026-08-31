#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web UI Server Chung cho CapCut và Higgsfield
Chạy: python3 web_app.py
Mở:   http://localhost:5050
"""

import sys, os, json, time, queue, threading, requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

# Đảm bảo import được module từ 'src' bằng cách add root dir vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import sqlite3

# ─── Cấu hình Database ───────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "database.db")

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = dict_factory
    return conn

def setup_db_if_not_exists():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                `key` TEXT PRIMARY KEY,
                `value` TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app TEXT NOT NULL,
                uid TEXT,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                join_link TEXT,
                ms_token TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mail_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                mail_type TEXT DEFAULT 'hotmail',
                content TEXT NOT NULL,
                item_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("ALTER TABLE accounts ADD COLUMN twofa TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE accounts ADD COLUMN momo TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE accounts ADD COLUMN uudai TEXT")
        except sqlite3.OperationalError:
            pass

        
        default_settings = {
            "PROXY_TYPE": "proxyquick",
            "PROXY_API_TOKEN": "proxyquick6_9df2f4385910e1a5d4bf45498a783abf845ba8776cb2642cb31839a1740b29ef",
            "PROXY_MERCHANT": "a20f20d6-9512-40fd-9a12-eeff809fdaeb",
            "PROXY_ID": "953319",
            "PROXYXOAY_KEY": "",
            "CAPCUT_PASSWORD": "capcut123",
            "GPM_API_URL": "http://127.0.0.1:19995",
            "GMAIL94_TOKEN": ""
        }
        for k, v in default_settings.items():
            conn.execute("INSERT OR IGNORE INTO settings (`key`, `value`) VALUES (?, ?)", (k, v))
        conn.commit()

setup_db_if_not_exists()

def load_settings():
    settings = {
        "PROXY_TYPE": "proxyquick",
        "PROXY_API_TOKEN": "",
        "PROXY_MERCHANT": "",
        "PROXY_ID": "",
        "PROXYXOAY_KEY": "",
        "CAPCUT_PASSWORD": "capcut123",
        "GPM_API_URL": "http://127.0.0.1:19995",
        "GMAIL94_TOKEN": "",
        "GMAIL94_PASSWORD": ""
    }
    try:
        with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT `key`, `value` FROM settings")
                for row in cursor.fetchall():
                    settings[row['key']] = row['value']
    except Exception as e:
        print("Lỗi load settings:", e)
    return settings

# Biến lưu trữ Proxy server hiện hành
_init_settings = load_settings()
PROXY_HOST       = _init_settings.get("LAST_PROXY_HOST", "180.93.2.171")
PROXY_PORT       = int(_init_settings.get("LAST_PROXY_PORT", 3131))
PROXY_USER       = _init_settings.get("LAST_PROXY_USER", "kierangrayson226")
PROXY_PASS       = _init_settings.get("LAST_PROXY_PASS", "odq0nda0odmzoa==")
PROXY_V3_INDEX   = -1

CAPCUT_HOTMAIL_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "hotmails.txt")
GPT_HOTMAIL_FILE    = os.path.join(os.path.dirname(__file__), "..", "..", "data", "hotmail-gpt.txt")

# ─── Flask App ────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="../../ui/templates", static_folder="../../ui/static")

# ─── Global state ─────────────────────────────────────────────────────────────
class BotState:
    def __init__(self, bot_name):
        self.name = bot_name
        self.log_queue = queue.Queue()
        self.task_stop = threading.Event()
        self.task_thread = None
        self.is_running = False
        self.module = None
        self.last_start_id = 0

    def log(self, msg, level="INFO"):
        now = datetime.now().strftime("%H:%M:%S")
        entry = {"type": "log", "level": level, "time": now, "msg": msg}
        self.log_queue.put(json.dumps(entry))
        icons = {"OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "INFO": "📌"}
        print(f"[{self.name}] [{now}] {icons.get(level,'📌')} {msg}")

state_capcut = BotState("CapCut")
state_higgsfield = BotState("Higgsfield")
state_gpt = BotState("GPT")
state_gpm = BotState("GPM")
state_dreamina = BotState("Dreamina")

def patched_get_proxy():
    print(f"[Proxy] Dùng proxy: {PROXY_HOST}:{PROXY_PORT}")
    return {"host": PROXY_HOST, "port": PROXY_PORT, "user": PROXY_USER, "pass": PROXY_PASS}

# ─── Routes ───────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(load_settings())

@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.json or {}
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            for k, v in data.items():
                cursor.execute("INSERT INTO settings (`key`, `value`) VALUES (?, ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (k, v))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── Proxy ─────────────────────────────────────────────────────────────────────
@app.route("/api/proxy/status")
def proxy_status():
    try:
        settings = load_settings()
        proxy_type = settings.get("PROXY_TYPE", "proxyquick")
        if PROXY_USER and PROXY_PASS:
            proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        else:
            proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}"
        r = requests.get("https://ipinfo.io/ip", proxies={"http": proxy_url, "https": proxy_url}, timeout=10)
        return jsonify({"ip": r.text.strip(), "ok": True, "type": proxy_type})
    except Exception as e:
        settings = load_settings()
        return jsonify({"ip": None, "ok": False, "error": str(e), "type": settings.get("PROXY_TYPE", "proxyquick")})

@app.route("/api/proxy/rotate", methods=["POST"])
def proxy_rotate():
    global PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS
    settings = load_settings()
    proxy_type = settings.get('PROXY_TYPE', 'proxyquick')
    
    try:
        if proxy_type == 'proxyxoay':
            proxyxoay_key = settings.get('PROXYXOAY_KEY', '')
            url = f"https://proxyxoay.shop/api/get.php?key={proxyxoay_key}&&nhamang=random&&tinhthanh=0&whitelist="
            r = requests.get(url, timeout=15)
            data = r.json()
            if data.get("status") == 100:
                proxy_str = data.get("proxyhttp", "")
                parts = proxy_str.split(":")
                PROXY_HOST = parts[0]
                PROXY_PORT = int(parts[1])
                PROXY_USER = parts[2] if len(parts) > 2 else ""
                PROXY_PASS = parts[3] if len(parts) > 3 else ""
                
                with get_db() as conn:
                    conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_HOST', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (PROXY_HOST,))
                    conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_PORT', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (str(PROXY_PORT),))
                    conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_USER', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (PROXY_USER,))
                    conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_PASS', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (PROXY_PASS,))
                    conn.commit()
                
                new_ip = data.get("ip", PROXY_HOST)
                return jsonify({"success": True, "ip": new_ip, "proxy": proxy_str})
            else:
                msg = data.get("message", str(data))
                # proxyxoay doesn't always provide timeRemaining explicitly, we can extract from message if needed
                import re
                m = re.search(r'(\d+)\s*s', msg)
                time_rem = int(m.group(1)) if m else 0
                return jsonify({"success": False, "error": msg, "timeRemaining": time_rem})
        elif proxy_type == 'proxyquick_v3':
            proxy_list_str = settings.get('PROXY_V3_LIST', '')
            proxies = [p.strip() for p in proxy_list_str.strip().split('\n') if p.strip()]
            if not proxies:
                return jsonify({"success": False, "error": "Danh sách ProxyQuick v3 trống!"})
            
            global PROXY_V3_INDEX
            last_error_msg = "Tất cả proxy v3 đều lỗi xoay."
            last_time_rem = 0
            
            for _ in range(len(proxies)):
                PROXY_V3_INDEX = (PROXY_V3_INDEX + 1) % len(proxies)
                current_proxy_line = proxies[PROXY_V3_INDEX]
                
                if "|" in current_proxy_line:
                    p_str, url = current_proxy_line.split("|", 1)
                else:
                    p_str, url = "", current_proxy_line
                
                try:
                    r = requests.get(url.strip(), timeout=15)
                    data = r.json()
                except Exception as e:
                    last_error_msg = str(e)
                    continue
                    
                if data.get("status") == "success" or data.get("message") == "Xoay proxy thành công":
                    proxy_str = data.get("proxy", p_str.strip())
                    new_ip = data.get("ip", proxy_str.split(':')[0] if proxy_str else "")
                    parts = proxy_str.split(":")
                    if len(parts) >= 4:
                        PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS = parts[0], int(parts[1]), parts[2], parts[3]
                        with get_db() as conn:
                            conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_HOST', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (PROXY_HOST,))
                            conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_PORT', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (str(PROXY_PORT),))
                            conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_USER', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (PROXY_USER,))
                            conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_PASS', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (PROXY_PASS,))
                            conn.commit()
                    return jsonify({"success": True, "ip": new_ip, "proxy": proxy_str})
                else:
                    last_error_msg = data.get("message", str(data))
                    last_time_rem = data.get("timeRemaining", 0)
                    
            return jsonify({"success": False, "error": f"Lỗi tất cả Proxy v3. Lỗi cuối: {last_error_msg}", "timeRemaining": last_time_rem})
        else:
            headers = {
                "Authorization": f"Bearer {settings.get('PROXY_API_TOKEN', '')}",
                "x-merchant-id": settings.get('PROXY_MERCHANT', '')
            }
            url = f"https://proxyquick.click/api/v2/proxies/{settings.get('PROXY_ID', '')}/rotate"
            r = requests.get(url, headers=headers, timeout=15)
            data = r.json()
            if data.get("status") == "success":
                proxy_str = data.get("proxy", "")
                new_ip = data.get("ip", "")
                parts = proxy_str.split(":")
                if len(parts) >= 4:
                    PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS = parts[0], int(parts[1]), parts[2], parts[3]
                    with get_db() as conn:
                        conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_HOST', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (PROXY_HOST,))
                        conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_PORT', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (str(PROXY_PORT),))
                        conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_USER', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (PROXY_USER,))
                        conn.execute("INSERT INTO settings (`key`, `value`) VALUES ('LAST_PROXY_PASS', ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", (PROXY_PASS,))
                        conn.commit()
                return jsonify({"success": True, "ip": new_ip, "proxy": proxy_str})
            
            # Nếu lỗi (ví dụ: chưa tới thời gian xoay)
            msg = data.get("message", str(data))
            time_rem = data.get("timeRemaining")
            return jsonify({"success": False, "error": msg, "timeRemaining": time_rem})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ─── CAPCUT API ───────────────────────────────────────────────────────────────
@app.route("/api/capcut/hotmail/count")
def capcut_hotmail_count():
    if not os.path.exists(CAPCUT_HOTMAIL_FILE): return jsonify({"count": 0})
    with open(CAPCUT_HOTMAIL_FILE, "r", encoding="utf-8") as f:
        return jsonify({"count": sum(1 for l in f if l.strip())})

@app.route("/api/capcut/hotmail/upload", methods=["POST"])
def capcut_hotmail_upload():
    f = request.files.get("file")
    if not f: return jsonify({"error": "No file"}), 400
    lines = [l.strip() for l in f.read().decode("utf-8").splitlines() if l.strip()]
    with open(CAPCUT_HOTMAIL_FILE, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    return jsonify({"count": len(lines)})

@app.route("/api/capcut/accounts")
def capcut_accounts():
    accounts = []
    session_only = request.args.get('session', 'false').lower() == 'true'
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            if session_only:
                cursor.execute("SELECT id, uid, email, password, join_link FROM accounts WHERE app='capcut' AND id > ? ORDER BY id ASC", (state_capcut.last_start_id,))
            else:
                cursor.execute("SELECT id, uid, email, password, join_link FROM accounts WHERE app='capcut' ORDER BY id ASC")
            accounts = cursor.fetchall()
    except Exception as e:
        print("Lỗi get accounts:", e)
    return jsonify({"accounts": accounts})

@app.route("/api/capcut/accounts/raw")
def capcut_accounts_raw():
    text = ""
    session_only = request.args.get('session', 'false').lower() == 'true'
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            if session_only:
                cursor.execute("SELECT uid, email, password, join_link, ms_token FROM accounts WHERE app='capcut' AND id > ? ORDER BY id ASC", (state_capcut.last_start_id,))
            else:
                cursor.execute("SELECT uid, email, password, join_link, ms_token FROM accounts WHERE app='capcut' ORDER BY id ASC")
            for row in cursor.fetchall():
                    jl = row.get('join_link', '') or ''
                    ms = row.get('ms_token', '') or ''
                    text += f"{row['uid']}\t{row['email']}\t{row['password']}\t{jl}\t{ms}\n"
    except Exception:
        pass
    return text, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/capcut/accounts/raw_ep")
def capcut_accounts_raw_ep():
    text = ""
    session_only = request.args.get('session', 'false').lower() == 'true'
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            if session_only:
                cursor.execute("SELECT email, password FROM accounts WHERE app='capcut' AND id > ? ORDER BY id ASC", (state_capcut.last_start_id,))
            else:
                cursor.execute("SELECT email, password FROM accounts WHERE app='capcut' ORDER BY id ASC")
            for row in cursor.fetchall():
                    text += f"{row['email']}|{row['password']}\n"
    except Exception:
        pass
    return text, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/capcut/accounts/raw_epl")
def capcut_accounts_raw_epl():
    text = ""
    session_only = request.args.get('session', 'false').lower() == 'true'
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            if session_only:
                cursor.execute("SELECT email, password, join_link FROM accounts WHERE app='capcut' AND id > ? ORDER BY id ASC", (state_capcut.last_start_id,))
            else:
                cursor.execute("SELECT email, password, join_link FROM accounts WHERE app='capcut' ORDER BY id ASC")
            for row in cursor.fetchall():
                jl = row.get('join_link', '') or ''
                text += f"{row['email']}\t{row['password']}\t{jl}\n"
    except Exception:
        pass
    return text, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/capcut/accounts/clear", methods=["POST"])
def capcut_accounts_clear():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE app='capcut'")
            conn.commit()
    except Exception:
        pass
    return jsonify({"success": True})

@app.route("/api/capcut/status")
def capcut_status():
    return jsonify({"is_running": state_capcut.is_running})

@app.route("/api/capcut/task/start", methods=["POST"])
def capcut_task_start():
    if state_capcut.is_running:
        return jsonify({"success": False, "error": "Đang chạy rồi!"})
    data = request.json or {}
    mode = int(data.get("mode", 1))
    count = int(data.get("count", 1))
    threads = int(data.get("threads", 1))
    join_link = data.get("join_link", "")
    mail_type = data.get("mail_type", "hotmail")
    mail_api_source = data.get("mail_api_source", "mixmmo")
    browser_type = data.get("browser_type", "chrome")
    headless = bool(data.get("headless", False))
    incognito = bool(data.get("incognito", False))

    state_capcut.task_stop.clear()
    while not state_capcut.log_queue.empty():
        try: state_capcut.log_queue.get_nowait()
        except: break

    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) as max_id FROM accounts WHERE app='capcut'")
            row = cursor.fetchone()
            state_capcut.last_start_id = row['max_id'] if row and row['max_id'] else 0
    except Exception as e:
        print("Lỗi get max id:", e)

    state_capcut.is_running = True
    state_capcut.task_thread = threading.Thread(target=_run_capcut_task, args=(mode, count, threads, join_link, mail_type, mail_api_source, browser_type, headless, incognito), daemon=True)
    state_capcut.task_thread.start()
    return jsonify({"success": True})

@app.route("/api/capcut/task/stop", methods=["POST"])
def capcut_task_stop():
    state_capcut.task_stop.set()
    capcut_close_browsers()
    return jsonify({"success": True})

@app.route("/api/capcut/pending_links/count")
def pending_links_count():
    import json, os
    path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "no_link.json")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                records = json.load(f)
            return jsonify({"count": len(records)})
    except:
        pass
    return jsonify({"count": 0})

@app.route("/api/capcut/pending_links/list")
def pending_links_list():
    """Trả về danh sách acc trong hàng đợi retry (chỉ email + password)."""
    import json, os
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "no_link.json"))
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                records = json.load(f)
            return jsonify({"success": True, "records": [
                {"email": r.get("email",""), "password": r.get("password",""), "has_cookie": bool(r.get("cookies"))}
                for r in records
            ]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "records": []})
    return jsonify({"success": True, "records": []})

@app.route("/api/capcut/pending_links/delete", methods=["POST"])
def pending_links_delete():
    """Xóa một acc khỏi hàng đợi retry theo email."""
    import json, os
    data = request.json or {}
    email = data.get("email", "").strip().lower()
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "no_link.json"))
    try:
        records = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                records = json.load(f)
        before = len(records)
        records = [r for r in records if r.get("email","").lower() != email]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True, "deleted": before - len(records), "remaining": len(records)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/capcut/pending_links/add_manual", methods=["POST"])
def pending_links_add_manual():
    """Thêm thủ công danh sách acc (email + pass) vào hàng đợi retry lấy link."""
    import json, os
    data = request.json or {}
    lines_raw = data.get("accounts", "")
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "no_link.json"))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Parse từng dòng: email password | email\tpassword | email|password
    added = 0
    skipped = 0
    try:
        records = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                records = json.load(f)

        existing_emails = {r.get("email", "").lower() for r in records}

        for line in lines_raw.splitlines():
            line = line.strip()
            if not line: continue
            # Hỗ trợ các dấu phân cách: tab, |, space
            import re
            parts = re.split(r'[\t|]| {2,}', line, maxsplit=1)
            if len(parts) < 2:
                parts = line.split(" ", 1)
            if len(parts) < 2: continue
            email = parts[0].strip()
            password = parts[1].strip()
            if not email or not password: continue

            if email.lower() in existing_emails:
                skipped += 1
                continue

            records.append({
                "email": email,
                "password": password,
                "refresh_token": "",
                "client_id": "",
                "cookies": []  # Rỗng → bot sẽ đăng nhập lại bằng email/pass
            })
            existing_emails.add(email.lower())
            added += 1

        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True, "added": added, "skipped": skipped, "total": len(records)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/capcut/retry_links/start", methods=["POST"])
def retry_links_start():
    if state_capcut.is_running:
        return jsonify({"success": False, "error": "Đang có task khác chạy!"})
    data = request.json or {}
    browser_type = data.get("browser_type", "chrome")
    headless = bool(data.get("headless", False))
    incognito = bool(data.get("incognito", False))
    mail_api_source = data.get("mail_api_source", "mixmmo")
    threads = int(data.get("threads", 2))

    # Check count before starting
    import json as _json, os as _os
    no_link_path = _os.path.join(_os.path.dirname(__file__), "..", "..", "data", "no_link.json")
    total = 0
    if _os.path.exists(no_link_path):
        try:
            with open(no_link_path, "r", encoding="utf-8") as f:
                total = len(_json.load(f))
        except: pass

    if total == 0:
        return jsonify({"success": False, "error": "Không có acc nào chờ lấy link!"})

    state_capcut.task_stop.clear()
    while not state_capcut.log_queue.empty():
        try: state_capcut.log_queue.get_nowait()
        except: break

    state_capcut.is_running = True
    state_capcut.task_thread = threading.Thread(
        target=_run_retry_links_task,
        args=(browser_type, headless, mail_api_source, threads, incognito),
        daemon=True
    )
    state_capcut.task_thread.start()
    return jsonify({"success": True, "total": total, "threads": threads})

def _run_retry_links_task(browser_type, headless, mail_api_source, threads=2, incognito=False):
    import importlib, json, os, concurrent.futures, threading as _threading
    try:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)

        mod = importlib.import_module("src.bots.capcut_hotmail")
        state_capcut.module = mod
        mod.log = state_capcut.log
        import src.bots.capcut_hotmail as ch
        ch.GLOBAL_STOP_EVENT = state_capcut.task_stop
        mod.get_rotated_proxy = patched_get_proxy

        no_link_path = os.path.join(root_dir, "data", "no_link.json")
        if not os.path.exists(no_link_path):
            state_capcut.log("Không có acc nào trong danh sách chờ lấy link!", "WARN")
            return

        with open(no_link_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        total = len(records)
        state_capcut.log(f"🚀 Bắt đầu retry lấy link cho {total} acc với {threads} luồng song song...", "INFO")

        succeeded = []
        failed = []
        lock = _threading.Lock()

        def retry_worker(rec, idx):
            if state_capcut.task_stop.is_set():
                with lock: failed.append(rec)
                return
            email = rec.get("email", "")
            password = rec.get("password", "")
            refresh_token = rec.get("refresh_token", "")
            client_id = rec.get("client_id", "")
            cookies = rec.get("cookies", [])

            state_capcut.log(f"[{idx}/{total}] Đang retry: {email}", "INFO")
            # Stagger: mỗi luồng chờ khác nhau để không mở Chrome đồng loạt
            stagger = ((idx - 1) % threads) * 2.5
            if stagger > 0:
                time.sleep(stagger)

            ok = mod.retry_get_payment_link_for_acc(
                email, password, refresh_token, client_id, cookies,
                headless=headless, browser_type=browser_type, mail_api_source=mail_api_source,
                index=idx, batch_size=threads, incognito=incognito
            )
            state_capcut.log_queue.put(json.dumps({"type": "result", "success": ok}))
            with lock:
                if ok:
                    # Lấy link vừa lưu từ success_links.txt
                    link = ""
                    try:
                        sl_path = os.path.join(root_dir, "data", "success_links.txt")
                        if os.path.exists(sl_path):
                            with open(sl_path, "r", encoding="utf-8") as slf:
                                for line in slf:
                                    parts = line.strip().split("\t")
                                    if len(parts) >= 3 and parts[0] == email:
                                        link = parts[2]
                    except Exception:
                        pass

                    # Upsert vào DB: cập nhật join_link nếu đã có, hoặc insert mới
                    try:
                        with get_db() as dbc:
                            dbc.execute("""
                                INSERT INTO accounts (app, uid, email, password, join_link, ms_token)
                                VALUES ('capcut', ?, ?, ?, ?, '')
                                ON CONFLICT DO NOTHING
                            """, (email.split('@')[0], email, password, link))
                            # Nếu đã tồn tại thì update link
                            dbc.execute("""
                                UPDATE accounts SET join_link=? WHERE app='capcut' AND email=? AND (join_link IS NULL OR join_link='')
                            """, (link, email))
                            dbc.commit()
                        state_capcut.log(f"✅ Đã cập nhật acc {email} vào DB với link!", "OK")
                    except Exception as dbe:
                        state_capcut.log(f"Không lưu được vào DB: {dbe}", "WARN")

                    succeeded.append(email)
                else:
                    failed.append(rec)

        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [executor.submit(retry_worker, rec, i+1) for i, rec in enumerate(records)]
            concurrent.futures.wait(futures)

        # Cập nhật lại file: chỉ giữ lại các acc CHƯA lấy được link
        with open(no_link_path, "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)

        state_capcut.log(f"✅ Retry xong: {len(succeeded)} thành công / {len(failed)} thất bại / còn {len(failed)} acc chờ", "OK")
        # Cập nhật lại số acc chờ trên UI
        state_capcut.log_queue.put(json.dumps({"type": "pending_count_update"}))
        state_capcut.log_queue.put(json.dumps({"type": "done"}))
    except Exception as e:
        state_capcut.log(f"Lỗi retry task: {e}", "ERR")
    finally:
        state_capcut.is_running = False


@app.route("/api/capcut/task/close_browsers", methods=["POST"])
def capcut_close_browsers():
    if state_capcut.module and hasattr(state_capcut.module, "ACTIVE_DRIVERS"):
        for d in state_capcut.module.ACTIVE_DRIVERS:
            try: d.quit()
            except: pass
        state_capcut.module.ACTIVE_DRIVERS.clear()
        
    # Xử lý đóng luôn cho Higgsfield nếu có
    if hasattr(sys.modules.get("bot_higgsfield"), "ACTIVE_DRIVERS"):
        for d in sys.modules["bot_higgsfield"].ACTIVE_DRIVERS:
            try: d.quit()
            except: pass
        sys.modules["bot_higgsfield"].ACTIVE_DRIVERS.clear()

    return jsonify({"success": True})

@app.route("/api/capcut/task/stream")
def capcut_task_stream():
    def generate():
        yield f"data: {json.dumps({'type':'log','level':'INFO','time':datetime.now().strftime('%H:%M:%S'),'msg':'🔗 Kết nối log stream...'})}\n\n"
        while True:
            try:
                msg = state_capcut.log_queue.get(timeout=25)
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type':'ping'})}\n\n"
    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

def _run_capcut_task(mode, count, threads, join_link, mail_type, mail_api_source, browser_type, headless, incognito=False):
    import importlib
    try:
        mod_name = "src.bots.capcut_hotmail" if mail_type == "hotmail" else "src.bots.capcut_domain"
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
            
        state_capcut.module = importlib.import_module(mod_name)
        bot = state_capcut.module
        bot.log = state_capcut.log
        
        # Patch để dừng OTP ngang
        import src.bots.capcut_hotmail as ch
        ch.GLOBAL_STOP_EVENT = state_capcut.task_stop
        
        bot.get_rotated_proxy = patched_get_proxy
        
        # Patch save_account to use DB
        def capcut_save_db(uid, email, password, *args, **kwargs):
            jl = args[0] if len(args) > 0 else kwargs.get("join_link", "")
            msToken = args[1] if len(args) > 1 else kwargs.get("msToken", "")
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO accounts (app, uid, email, password, join_link, ms_token) VALUES (?, ?, ?, ?, ?, ?)", 
                                   ("capcut", uid, email, password, jl, msToken))
                    conn.commit()
            except Exception as e:
                state_capcut.log(f"Lỗi lưu DB: {e}", "ERR")
                
        def capcut_update_link(email, link):
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE accounts SET join_link = ? WHERE app = 'capcut' AND email = ?", (link, email))
                    conn.commit()
            except Exception as e:
                state_capcut.log(f"Lỗi update DB link: {e}", "ERR")
                
        state_capcut.module.save_account = capcut_save_db
        if hasattr(state_capcut.module, 'update_account_payment_link'):
            state_capcut.module.update_account_payment_link = capcut_update_link
        bot = state_capcut.module
        
        done = {"ok": 0, "fail": 0}
        
        if mail_type == "hotmail":
            bot.load_hotmails_to_queue(limit=count)
            def worker(i):
                time.sleep((i % threads) * 2.5)
                while not bot.HOTMAIL_QUEUE.empty() and not state_capcut.task_stop.is_set():
                    res = bot.register_one_account(i, join_link if mode == 2 else None, keep_open=(mode == 1), batch_size=threads, headless=headless, browser_type=browser_type, get_link=(mode == 3), mail_api_source=mail_api_source, incognito=incognito)
                    state_capcut.log_queue.put(json.dumps({"type": "result", "success": bool(res)}))
                    if res: done["ok"] += 1
                    else: done["fail"] += 1

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
                futures = [ex.submit(worker, i+1) for i in range(threads)]
                concurrent.futures.wait(futures)
        elif mode != 4:
            def worker(i):
                try:
                    time.sleep((i % threads) * 2.5)
                    if state_capcut.task_stop.is_set(): return
                    res = bot.register_one_account(i, join_link if mode == 2 else None, keep_open=(mode == 1), batch_size=threads, headless=headless, browser_type=browser_type, get_link=(mode == 3), mail_api_source=mail_api_source, incognito=incognito)
                    state_capcut.log_queue.put(json.dumps({"type": "result", "success": bool(res)}))
                    if res: done["ok"] += 1
                    else: done["fail"] += 1
                except Exception as e:
                    state_capcut.log(f"Worker Error: {e}", "ERR")
                    raise e

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
                futures = [ex.submit(worker, idx+1) for idx in range(count)]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        print("Exception in domain mail worker:", e)
                    if state_capcut.task_stop.is_set(): break

        # ==== MODE 4: API Mode (Không mở Chrome để đăng ký, chỉ join team) ====
        if mode == 4:
            proxy_dict = bot.get_rotated_proxy() if hasattr(bot, 'get_rotated_proxy') else None
            def api_worker(i):
                try:
                    if state_capcut.task_stop.is_set(): return
                    import time as _t; _t.sleep((i % threads) * 1.5)
                    res = bot.register_one_account_api(i, join_link, count, proxy_dict)
                    state_capcut.log_queue.put(json.dumps({"type": "result", "success": bool(res)}))
                    if res: done["ok"] += 1
                    else: done["fail"] += 1
                except Exception as e:
                    state_capcut.log(f"API Worker Error: {e}", "ERR")

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
                futures = [ex.submit(api_worker, idx + 1) for idx in range(count)]
                for future in concurrent.futures.as_completed(futures):
                    try: future.result()
                    except Exception as e: print("Exception in api_worker:", e)
                    if state_capcut.task_stop.is_set(): break

        if state_capcut.task_stop.is_set():
            state_capcut.log_queue.put(json.dumps({"type": "stopped"}))
        else:
            state_capcut.log(f"✅ Xong! {done['ok']} thành công / {done['fail']} thất bại", "OK")
            state_capcut.log_queue.put(json.dumps({"type": "done", "ok": done['ok'], "fail": done['fail']}))
    except Exception as e:
        state_capcut.log(f"Lỗi task: {type(e).__name__}: {e}", "ERR")
        state_capcut.log_queue.put(json.dumps({"type": "done", "ok": 0, "fail": 0}))
    finally:
        state_capcut.is_running = False


# ─── HIGGSFIELD API ───────────────────────────────────────────────────────────
@app.route("/api/higgsfield/accounts")
def higgsfield_accounts():
    accounts = []
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT email, password FROM accounts WHERE app='higgsfield' ORDER BY id ASC")
            accounts = [dict(row) for row in cursor.fetchall()]
    except Exception:
        pass
    return jsonify({"accounts": accounts})

@app.route("/api/higgsfield/accounts/raw")
def higgsfield_accounts_raw():
    text = ""
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT email, password FROM accounts WHERE app='higgsfield' ORDER BY id ASC")
            for row in cursor.fetchall():
                    text += f"{row['email']}\t{row['password']}\n"
    except Exception:
        pass
    return text, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/higgsfield/accounts/clear", methods=["POST"])
def higgsfield_accounts_clear():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE app='higgsfield'")
            conn.commit()
    except Exception:
        pass
    return jsonify({"success": True})

@app.route("/api/higgsfield/status")
def higgsfield_status():
    return jsonify({"is_running": state_higgsfield.is_running})

@app.route("/api/higgsfield/task/start", methods=["POST"])
def higgsfield_task_start():
    if state_higgsfield.is_running:
        return jsonify({"success": False, "error": "Đang chạy rồi!"})
    data = request.json or {}
    count = int(data.get("count", 1))
    threads = int(data.get("threads", 1))
    headless = bool(data.get("headless", False))
    browser_type = data.get("browser_type", "chrome")

    state_higgsfield.task_stop.clear()
    while not state_higgsfield.log_queue.empty():
        try: state_higgsfield.log_queue.get_nowait()
        except: break

    state_higgsfield.is_running = True
    state_higgsfield.task_thread = threading.Thread(target=_run_higgsfield_task, args=(count, threads, browser_type, headless), daemon=True)
    state_higgsfield.task_thread.start()
    return jsonify({"success": True})

@app.route("/api/higgsfield/task/stop", methods=["POST"])
def higgsfield_task_stop():
    state_higgsfield.task_stop.set()
    higgsfield_close_browsers()
    return jsonify({"success": True})

@app.route("/api/higgsfield/task/close_browsers", methods=["POST"])
def higgsfield_close_browsers():
    if state_higgsfield.module and hasattr(state_higgsfield.module, "ACTIVE_DRIVERS"):
        for d in state_higgsfield.module.ACTIVE_DRIVERS:
            try: d.quit()
            except: pass
        state_higgsfield.module.ACTIVE_DRIVERS.clear()
    return jsonify({"success": True})

@app.route("/api/higgsfield/task/stream")
def higgsfield_task_stream():
    def generate():
        yield f"data: {json.dumps({'type':'log','level':'INFO','time':datetime.now().strftime('%H:%M:%S'),'msg':'🔗 Kết nối log stream...'})}\n\n"
        while True:
            try:
                msg = state_higgsfield.log_queue.get(timeout=25)
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type':'ping'})}\n\n"
    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

def _run_higgsfield_task(count, threads, browser_type, headless):
    import importlib
    try:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
            
        state_higgsfield.module = importlib.import_module("src.bots.higgsfield")
        bot = state_higgsfield.module
        bot.log = state_higgsfield.log
        bot.get_rotated_proxy = patched_get_proxy
        
        # Patch save_account to use DB
        def higgsfield_save_db(email, password):
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO accounts (app, uid, email, password) VALUES (?, '', ?, ?)", 
                                   ("higgsfield", email, password))
                    conn.commit()
            except Exception as e:
                state_higgsfield.log(f"Lỗi lưu DB: {e}", "ERR")
                
        bot.save_account = higgsfield_save_db

        done = {"ok": 0, "fail": 0}
        def worker(i):
            time.sleep((i % threads) * 2.5)
            if state_higgsfield.task_stop.is_set(): return
            res = bot.register_one_account(i, keep_open=False, batch_size=threads, use_proxy=True, headless=headless, browser_type=browser_type)
            state_higgsfield.log_queue.put(json.dumps({"type": "result", "success": bool(res)}))
            if res: done["ok"] += 1
            else: done["fail"] += 1

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
            futures = [ex.submit(worker, idx+1) for idx in range(count)]
            for future in concurrent.futures.as_completed(futures):
                if state_higgsfield.task_stop.is_set(): break

        if state_higgsfield.task_stop.is_set():
            state_higgsfield.log_queue.put(json.dumps({"type": "stopped"}))
        else:
            state_higgsfield.log(f"✅ Xong! {done['ok']} thành công / {done['fail']} thất bại", "OK")
            state_higgsfield.log_queue.put(json.dumps({"type": "done", "ok": done["ok"], "fail": done["fail"]}))
    except Exception as e:
        state_higgsfield.log(f"Lỗi task: {type(e).__name__}: {e}", "ERR")
        state_higgsfield.log_queue.put(json.dumps({"type": "done", "ok": 0, "fail": 0}))
    finally:
        state_higgsfield.is_running = False

# ─── GPT API ──────────────────────────────────────────────────────────────────
@app.route("/api/gpt/accounts")
def gpt_accounts():
    accounts = []
    session_only = request.args.get('session', 'false').lower() == 'true'
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if session_only:
                cursor.execute("SELECT email, password, twofa, momo, uudai FROM accounts WHERE app='gpt' AND id > ? ORDER BY id ASC", (state_gpt.last_start_id,))
            else:
                cursor.execute("SELECT email, password, twofa, momo, uudai FROM accounts WHERE app='gpt' ORDER BY id ASC")
            accounts = [dict(row) for row in cursor.fetchall()]
    except Exception:
        pass
    return jsonify({"accounts": accounts})

@app.route("/api/gpt/accounts/raw")
def gpt_accounts_raw():
    text = ""
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT email, password, twofa, momo, uudai FROM accounts WHERE app='gpt' ORDER BY id ASC")
            for row in cursor.fetchall():
                text += f"{row['email']}\t{row['password']}\t{row['twofa'] or ''}\t{row['momo'] or 'không'}\t{row['uudai'] or 'không'}\n"
    except Exception:
        pass
    return text, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/gpt/accounts/raw_ep")
def gpt_accounts_raw_ep():
    text = ""
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT email, password, twofa, momo, uudai FROM accounts WHERE app='gpt' ORDER BY id ASC")
            for row in cursor.fetchall():
                text += f"{row['email']}\t{row['password']}\t{row['twofa'] or ''}\t{row['momo'] or 'không'}\t{row['uudai'] or 'không'}\n"
    except Exception:
        pass
    return text, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/gpt/hotmail/count")
def gpt_hotmail_count():
    count = 0
    if os.path.exists(GPT_HOTMAIL_FILE):
        with open(GPT_HOTMAIL_FILE, "r", encoding="utf-8") as f:
            count = sum(
                1 for l in f
                if l.strip() and not l.strip().startswith("#") and ("----" in l or "|" in l)
            )
    return jsonify({"count": count})

@app.route("/api/gpt/hotmail/upload", methods=["POST"])
def gpt_hotmail_upload():
    f = request.files.get("file")
    if not f: return jsonify({"error": "No file"}), 400
    lines = [l.strip() for l in f.read().decode("utf-8").splitlines() if l.strip()]
    with open(GPT_HOTMAIL_FILE, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    valid_count = sum(1 for l in lines if not l.startswith("#") and ("----" in l or "|" in l))
    return jsonify({"count": valid_count})

@app.route("/api/gpt/accounts/clear", methods=["POST"])
def gpt_accounts_clear():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE app='gpt'")
            conn.commit()
    except Exception:
        pass
    return jsonify({"success": True})

@app.route("/api/gpt/status")
def gpt_status():
    return jsonify({"is_running": state_gpt.is_running})

@app.route("/api/gpt/task/start", methods=["POST"])
def gpt_task_start():
    if state_gpt.is_running:
        return jsonify({"success": False, "error": "Đang chạy rồi!"})
    data = request.json or {}
    count = int(data.get("count", 1))
    threads = int(data.get("threads", 1))
    mail_type = data.get("mail_type", "outlook")
    creation_method = data.get("creation_method", "selenium")
    check_momo = data.get("check_momo", True)
    mail_api_source = data.get("mail_api_source", "dongvanfb")
    
    driver_mode = data.get("driver_mode", "playwright_ui")
    browser_type = data.get("browser_type", "chrome")
    headless = data.get("headless", False)
    incognito = data.get("incognito", False)
    keep_open = data.get("keep_open", False)
    
    import sys, os
    gpt_engine_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "gpt_engine"))
    if gpt_engine_dir not in sys.path:
        sys.path.insert(0, gpt_engine_dir)
        
    import config.roxybrowser as _roxy_cfg
    _roxy_cfg.REGISTRATION_DRIVER = driver_mode
    _roxy_cfg.BROWSER_USE_HEADLESS = headless
    _roxy_cfg.BROWSER_TYPE = browser_type
    _roxy_cfg.BROWSER_INCOGNITO = incognito

    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) as max_id FROM accounts WHERE app='gpt'")
            row = cursor.fetchone()
            state_gpt.last_start_id = row['max_id'] if row and row['max_id'] else 0
    except Exception:
        pass

    state_gpt.task_stop.clear()
    while not state_gpt.log_queue.empty():
        try: state_gpt.log_queue.get_nowait()
        except: break

    state_gpt.is_running = True
    state_gpt.task_thread = threading.Thread(
        target=_run_gpt_task, 
        args=(count, threads, mail_type, check_momo, browser_type, headless, incognito, mail_api_source, keep_open, creation_method), 
        daemon=True
    )
    state_gpt.task_thread.start()
    return jsonify({"success": True})

@app.route("/api/gpt/task/stop", methods=["POST"])
def gpt_task_stop():
    state_gpt.task_stop.set()
    return jsonify({"success": True})

@app.route("/api/gpt/task/close_browsers", methods=["POST"])
def gpt_close_browsers():
    try:
        from src.bots.gpt_selenium_utils import ACTIVE_DRIVERS
        for d in ACTIVE_DRIVERS:
            try: d.quit()
            except: pass
        ACTIVE_DRIVERS.clear()
    except Exception as e:
        pass
    return jsonify({"success": True})

@app.route("/api/gpt/task/stream")
def gpt_task_stream():
    def generate():
        yield f"data: {json.dumps({'type':'log','level':'INFO','time':datetime.now().strftime('%H:%M:%S'),'msg':'🔗 Kết nối log stream...'})}\n\n"
        while True:
            try:
                msg = state_gpt.log_queue.get(timeout=25)
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type':'ping'})}\n\n"
    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

def _run_gpt_task(count, threads, mail_type, check_momo=True, browser_type="chrome", headless=False, incognito=False, mail_api_source="dongvanfb", keep_open=False, creation_method="selenium"):
    state_gpt.check_momo = check_momo
    state_gpt.browser_type = browser_type
    state_gpt.headless = headless
    state_gpt.incognito = incognito
    import importlib
    try:
        # ── Chọn bot module theo mail_type và creation_method ────────────────
        if creation_method == "api":
            if mail_type != "outlook":
                state_gpt.log("API V2 hiện tại chỉ hỗ trợ Hotmail/Outlook. Đang dùng Hotmail thay thế.", "WARN")
            state_gpt.module = importlib.import_module("src.bots.gpt_api_v2")
        else:
            if mail_type == "gmail94":
                state_gpt.module = importlib.import_module("src.bots.gpt_gmail94")
            elif mail_type == "domain":
                state_gpt.module = importlib.import_module("src.bots.gpt_domain")
            else:
                state_gpt.module = importlib.import_module("src.bots.gpt_hotmail")

        bot = state_gpt.module
        bot.log = state_gpt.log
        bot.get_rotated_proxy = patched_get_proxy

        # Patch để dừng OTP ngang
        try:
            import src.bots.capcut_hotmail as ch
            ch.GLOBAL_STOP_EVENT = state_gpt.task_stop
        except Exception:
            pass

        # Đẩy config MoMo và Password xuống bot
        cfg = load_settings()
        bot.CHECK_MOMO = state_gpt.check_momo
        bot.GPT_PASSWORD = cfg.get("GMAIL94_PASSWORD", "chatgpt123@@").strip()
        if not bot.GPT_PASSWORD:
            bot.GPT_PASSWORD = "chatgpt123@@"

        # Nếu dùng Gmail94: inject token từ Settings DB
        if mail_type == "gmail94":
            token = cfg.get("GMAIL94_TOKEN", "").strip()
            if not token:
                state_gpt.log("Gmail94 Token chưa được cấu hình! Vào Settings để nhập.", "ERR")
                state_gpt.log_queue.put(json.dumps({"type": "done", "ok": 0, "fail": 0}))
                return
            bot.GMAIL94_TOKEN = token
            bot.GMAIL94_PASSWORD = cfg.get("GMAIL94_PASSWORD", "")
            state_gpt.log(f"[Gmail94] Đang dùng token: {token[:8]}...", "INFO")

        # Patch save_account to use DB
        def gpt_save_db(email, password, totp_secret, has_momo=False, has_uudai=False):
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    momo_str = str(has_momo) if isinstance(has_momo, str) else ("có" if has_momo else "không")
                    uudai_str = str(has_uudai) if isinstance(has_uudai, str) else ("có" if has_uudai else "không")
                    cursor.execute("INSERT INTO accounts (app, uid, email, password, twofa, momo, uudai) VALUES (?, '', ?, ?, ?, ?, ?)",
                                   ("gpt", email, password, totp_secret, momo_str, uudai_str))
                    conn.commit()
            except Exception as e:
                state_gpt.log(f"Lỗi lưu DB: {e}", "ERR")

        bot.save_account = gpt_save_db

        done = {"ok": 0, "fail": 0}

        if mail_type == "gmail94":
            # Gmail94: count = số Gmail cần mua (mỗi Gmail = 4 biến thể GPT)
            # Chia đều số lần mua Gmail cho các thread
            per_thread = max(1, (count + threads - 1) // threads)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
                futures = []
                remaining_count = count
                for idx in range(threads):
                    this_count = min(per_thread, remaining_count)
                    if this_count <= 0:
                        break
                    remaining_count -= this_count
                    def _worker_g94(i=idx+1, c=this_count):
                        time.sleep((i % threads) * 3.0)
                        local = 0
                        while local < c and not state_gpt.task_stop.is_set():
                            def _on_res(s):
                                state_gpt.log_queue.put(json.dumps({"type": "result", "success": s}))
                            
                            ok_n, fail_n = bot.register_one_purchase(
                                i, 
                                browser_type=state_gpt.browser_type, 
                                headless=state_gpt.headless, 
                                incognito=state_gpt.incognito, 
                                keep_open=keep_open,
                                on_result=_on_res
                            )
                            done["ok"]   += ok_n
                            done["fail"] += fail_n
                            local += 1
                    futures.append(ex.submit(_worker_g94))
                concurrent.futures.wait(futures)
        else:
            # Hotmail: load từ file và dùng HOTMAIL_QUEUE
            bot.load_hotmails_to_queue(limit=count)
            def worker(i):
                time.sleep((i % threads) * 2.5)
                while not bot.HOTMAIL_QUEUE.empty() and not state_gpt.task_stop.is_set():
                    res = bot.register_one_account(i, browser_type=state_gpt.browser_type, headless=state_gpt.headless, incognito=state_gpt.incognito, mail_api_source=mail_api_source, keep_open=keep_open)
                    state_gpt.log_queue.put(json.dumps({"type": "result", "success": bool(res)}))
                    if res: done["ok"] += 1
                    else: done["fail"] += 1

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
                futures = [ex.submit(worker, idx+1) for idx in range(threads)]
                concurrent.futures.wait(futures)

        if state_gpt.task_stop.is_set():
            state_gpt.log_queue.put(json.dumps({"type": "stopped"}))
        else:
            state_gpt.log(f"Xong! {done['ok']} thanh cong / {done['fail']} that bai", "OK")
            state_gpt.log_queue.put(json.dumps({"type": "done", "ok": done["ok"], "fail": done["fail"]}))
    except Exception as e:
        state_gpt.log(f"Loi task: {type(e).__name__}: {e}", "ERR")
        state_gpt.log_queue.put(json.dumps({"type": "done", "ok": 0, "fail": 0}))
    finally:
        state_gpt.is_running = False


# ─── Gmail94 Token API ────────────────────────────────────────────────────────
@app.route("/api/gpt/gmail94/token", methods=["GET"])
def gmail94_token_get():
    cfg = load_settings()
    token = cfg.get("GMAIL94_TOKEN", "")
    # Mask token khi tra ve
    masked = token[:8] + "..." + token[-4:] if len(token) > 12 else ("***" if token else "")
    return jsonify({"has_token": bool(token), "masked": masked})


@app.route("/api/gpt/gmail94/token", methods=["POST"])
def gmail94_token_set():
    data = request.json or {}
    token = data.get("token", "").strip()
    if not token:
        return jsonify({"success": False, "error": "Token khong duoc de trong!"})
    try:
        with get_db() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (`key`, `value`) VALUES (?, ?)",
                         ("GMAIL94_TOKEN", token))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ─── GPM API & AUTOMATION ─────────────────────────────────────────────────────
@app.route("/api/gpm/profiles")
def gpm_profiles():
    api_url = request.args.get("api_url") or load_settings().get("GPM_API_URL", "http://127.0.0.1:19995")
    from src.bots.capcut_gpm import GpmClient
    client = GpmClient(api_url)
    res = client.list_profiles()
    return jsonify(res)

@app.route("/api/gpm/profile/create", methods=["POST"])
def gpm_profile_create():
    data = request.json or {}
    name = data.get("name", "").strip() or f"CapCut_{datetime.now().strftime('%H%M%S')}"
    group_id = data.get("group_id", "").strip()
    raw_proxy = data.get("raw_proxy", "").strip()
    api_url = data.get("api_url") or load_settings().get("GPM_API_URL", "http://127.0.0.1:19995")
    from src.bots.capcut_gpm import GpmClient
    client = GpmClient(api_url)
    res = client.create_profile(name, group_id=group_id, raw_proxy=raw_proxy)
    return jsonify(res)

@app.route("/api/gpm/profile/start", methods=["POST"])
def gpm_profile_start():
    data = request.json or {}
    profile_id = data.get("profile_id", "").strip()
    api_url = data.get("api_url") or load_settings().get("GPM_API_URL", "http://127.0.0.1:19995")
    if not profile_id:
        return jsonify({"success": False, "error": "Chưa chọn profile ID"})
    from src.bots.capcut_gpm import GpmClient
    client = GpmClient(api_url)
    res = client.start_profile(profile_id)
    return jsonify(res)

@app.route("/api/gpm/profile/stop", methods=["POST"])
def gpm_profile_stop():
    data = request.json or {}
    profile_id = data.get("profile_id", "").strip()
    api_url = data.get("api_url") or load_settings().get("GPM_API_URL", "http://127.0.0.1:19995")
    if not profile_id:
        return jsonify({"success": False, "error": "Chưa chọn profile ID"})
    from src.bots.capcut_gpm import GpmClient
    client = GpmClient(api_url)
    res = client.close_profile(profile_id)
    return jsonify(res)

@app.route("/api/gpm/status")
def gpm_status():
    return jsonify({"is_running": state_gpm.is_running})

@app.route("/api/gpm/task/start", methods=["POST"])
def gpm_task_start():
    if state_gpm.is_running:
        return jsonify({"success": False, "error": "Đang chạy task GPM khác rồi!"})
    data = request.json or {}
    raw_pids = data.get("profile_ids", [])
    if isinstance(raw_pids, str):
        profile_ids = [p.strip() for p in raw_pids.replace(",", "\n").splitlines() if p.strip()]
    else:
        profile_ids = [str(p).strip() for p in raw_pids if str(p).strip()]

    if not profile_ids:
        return jsonify({"success": False, "error": "Vui lòng chọn hoặc nhập ít nhất 1 GPM Profile ID!"})

    threads = int(data.get("threads", 1))
    mail_type = data.get("mail_type", "hotmail")
    mail_api_source = data.get("mail_api_source", "mixmmo")
    mode = int(data.get("mode", 1))
    join_link = data.get("join_link", "")
    gpm_api_url = data.get("gpm_api_url") or load_settings().get("GPM_API_URL", "http://127.0.0.1:19995")

    state_gpm.task_stop.clear()
    while not state_gpm.log_queue.empty():
        try: state_gpm.log_queue.get_nowait()
        except: break

    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) as max_id FROM accounts WHERE app IN ('capcut', 'capcut_gpm')")
            row = cursor.fetchone()
            state_gpm.last_start_id = row['max_id'] if row and row['max_id'] else 0
    except Exception:
        pass

    state_gpm.is_running = True
    state_gpm.task_thread = threading.Thread(
        target=_run_gpm_task,
        args=(profile_ids, threads, mail_type, mail_api_source, mode, join_link, gpm_api_url),
        daemon=True
    )
    state_gpm.task_thread.start()
    return jsonify({"success": True, "count": len(profile_ids)})

@app.route("/api/gpm/task/stop", methods=["POST"])
def gpm_task_stop():
    state_gpm.task_stop.set()
    if hasattr(state_gpm.module, "ACTIVE_DRIVERS"):
        for d in state_gpm.module.ACTIVE_DRIVERS:
            try: d.quit()
            except: pass
        state_gpm.module.ACTIVE_DRIVERS.clear()
    return jsonify({"success": True})

@app.route("/api/gpm/task/stream")
def gpm_task_stream():
    def generate():
        yield f"data: {json.dumps({'type':'log','level':'INFO','time':datetime.now().strftime('%H:%M:%S'),'msg':'🔗 Kết nối log stream GPM...'})}\n\n"
        while True:
            try:
                msg = state_gpm.log_queue.get(timeout=25)
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type':'ping'})}\n\n"
    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

def _run_gpm_task(profile_ids, threads, mail_type, mail_api_source, mode, join_link, gpm_api_url):
    import importlib
    try:
        state_gpm.module = importlib.import_module("src.bots.capcut_gpm")
        bot = state_gpm.module
        bot.log = state_gpm.log
        bot.GLOBAL_STOP_EVENT = state_gpm.task_stop

        def gpm_save_db(uid, email, password, *args, **kwargs):
            jl = args[0] if len(args) > 0 else kwargs.get("join_link", "")
            msToken = args[1] if len(args) > 1 else kwargs.get("msToken", "")
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO accounts (app, uid, email, password, join_link, ms_token) VALUES (?, ?, ?, ?, ?, ?)", 
                                   ("capcut_gpm", uid, email, password, jl, msToken))
                    conn.commit()
            except Exception as e:
                state_gpm.log(f"Lỗi lưu DB: {e}", "ERR")

        if mail_type == "hotmail":
            import src.bots.capcut_hotmail as ch
            ch.load_hotmails_to_queue(limit=len(profile_ids))

        res = bot.register_gpm_multiple(
            profile_ids=profile_ids,
            threads=threads,
            mail_type=mail_type,
            mode=mode,
            join_link=join_link,
            mail_api_source=mail_api_source,
            gpm_api_url=gpm_api_url,
            get_link=(mode == 3)
        )

        state_gpm.log_queue.put(json.dumps({"type": "done", "ok": res["ok"], "fail": res["fail"]}))
    except Exception as e:
        state_gpm.log(f"Lỗi GPM Task: {e}", "ERR")
        state_gpm.log_queue.put(json.dumps({"type": "done", "ok": 0, "fail": 0}))
    finally:
        state_gpm.is_running = False

@app.route("/api/gpm/accounts")
def gpm_accounts():
    accounts = []
    session_only = request.args.get('session', 'false').lower() == 'true'
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            if session_only:
                cursor.execute("SELECT id, uid, email, password, join_link FROM accounts WHERE app IN ('capcut_gpm', 'capcut') AND id > ? ORDER BY id ASC", (state_gpm.last_start_id,))
            else:
                cursor.execute("SELECT id, uid, email, password, join_link FROM accounts WHERE app IN ('capcut_gpm', 'capcut') ORDER BY id ASC")
            accounts = cursor.fetchall()
    except Exception as e:
        print("Lỗi get gpm accounts:", e)
    return jsonify({"accounts": accounts})

@app.route("/api/gpm/accounts/clear", methods=["POST"])
def gpm_accounts_clear():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE app='capcut_gpm'")
            conn.commit()
    except Exception:
        pass
    return jsonify({"success": True})

# ─── MAIL LIST PERSISTENCE API ──────────────────────────────────────────────────
@app.route("/api/maillists", methods=["GET"])
def maillists_get():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, mail_type, content, item_count, created_at FROM mail_lists ORDER BY id DESC")
            rows = cursor.fetchall()
            lists = [dict(r) for r in rows]
            return jsonify({"success": True, "data": lists})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/maillists", methods=["POST"])
def maillists_save():
    data = request.json or {}
    title = data.get("title", "").strip() or f"Mail List {datetime.now().strftime('%d/%m %H:%M')}"
    mail_type = data.get("mail_type", "hotmail")
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"success": False, "error": "Nội dung danh sách trống!"})
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    item_count = len(lines)
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO mail_lists (title, mail_type, content, item_count) VALUES (?, ?, ?, ?)",
                           (title, mail_type, content, item_count))
            conn.commit()
            return jsonify({"success": True, "id": cursor.lastrowid, "message": "Lưu danh sách mail thành công!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/maillists/<int:list_id>", methods=["DELETE"])
def maillists_delete(list_id):
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM mail_lists WHERE id = ?", (list_id,))
            conn.commit()
            return jsonify({"success": True, "message": "Đã xóa danh sách mail!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ─── DREAMINA API ────────────────────────────────────────────────────────────
@app.route("/api/dreamina/accounts")
def dreamina_accounts():
    accounts = []
    session_only = request.args.get('session', 'false').lower() == 'true'
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if session_only:
                cursor.execute("SELECT email, password FROM accounts WHERE app='dreamina' AND id > ? ORDER BY id ASC", (state_dreamina.last_start_id,))
            else:
                cursor.execute("SELECT email, password FROM accounts WHERE app='dreamina' ORDER BY id ASC")
            accounts = [dict(row) for row in cursor.fetchall()]
    except Exception:
        pass
    return jsonify({"accounts": accounts})

@app.route("/api/dreamina/accounts/raw")
def dreamina_accounts_raw():
    text = ""
    session_only = request.args.get('session', 'false').lower() == 'true'
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if session_only:
                cursor.execute("SELECT email, password FROM accounts WHERE app='dreamina' AND id > ? ORDER BY id ASC", (state_dreamina.last_start_id,))
            else:
                cursor.execute("SELECT email, password FROM accounts WHERE app='dreamina' ORDER BY id ASC")
            for row in cursor.fetchall():
                text += f"{row['email']}\t{row['password']}\n"
    except Exception:
        pass
    return text, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/dreamina/accounts/raw_ep")
def dreamina_accounts_raw_ep():
    text = ""
    session_only = request.args.get('session', 'false').lower() == 'true'
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if session_only:
                cursor.execute("SELECT email, password FROM accounts WHERE app='dreamina' AND id > ? ORDER BY id ASC", (state_dreamina.last_start_id,))
            else:
                cursor.execute("SELECT email, password FROM accounts WHERE app='dreamina' ORDER BY id ASC")
            for row in cursor.fetchall():
                text += f"{row['email']}|{row['password']}\n"
    except Exception:
        pass
    return text, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/dreamina/accounts/clear", methods=["POST"])
def dreamina_accounts_clear():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE app='dreamina'")
            conn.commit()
    except Exception:
        pass
    return jsonify({"success": True})

@app.route("/api/dreamina/hotmail/count")
def dreamina_hotmail_count():
    count = 0
    if os.path.exists(CAPCUT_HOTMAIL_FILE):
        with open(CAPCUT_HOTMAIL_FILE, "r", encoding="utf-8") as f:
            count = sum(1 for l in f if l.strip() and "|" in l)
    return jsonify({"count": count})

@app.route("/api/dreamina/hotmail/upload", methods=["POST"])
def dreamina_hotmail_upload():
    f = request.files.get("file")
    if not f: return jsonify({"error": "No file"}), 400
    lines = [l.strip() for l in f.read().decode("utf-8").splitlines() if l.strip()]
    with open(CAPCUT_HOTMAIL_FILE, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    valid_count = sum(1 for l in lines if "|" in l)
    return jsonify({"count": valid_count})

@app.route("/api/dreamina/status")
def dreamina_status():
    return jsonify({"is_running": state_dreamina.is_running})

@app.route("/api/dreamina/task/start", methods=["POST"])
def dreamina_task_start():
    if state_dreamina.is_running:
        return jsonify({"success": False, "error": "Đang chạy rồi!"})
    data = request.json or {}
    count = int(data.get("count", 1))
    threads = int(data.get("threads", 1))
    headless = bool(data.get("headless", False))
    browser_type = data.get("browser_type", "chrome")
    mail_api_source = data.get("mail_api_source", "mixmmo")

    state_dreamina.task_stop.clear()
    while not state_dreamina.log_queue.empty():
        try: state_dreamina.log_queue.get_nowait()
        except: break

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MAX(id) FROM accounts WHERE app='dreamina'")
            row = cur.fetchone()
            state_dreamina.last_start_id = row[0] if row and row[0] else 0
    except:
        state_dreamina.last_start_id = 0

    state_dreamina.is_running = True
    state_dreamina.task_thread = threading.Thread(
        target=_run_dreamina_task,
        args=(count, threads, browser_type, headless, mail_api_source),
        daemon=True
    )
    state_dreamina.task_thread.start()
    return jsonify({"success": True})

@app.route("/api/dreamina/task/stop", methods=["POST"])
def dreamina_task_stop():
    state_dreamina.task_stop.set()
    dreamina_close_browsers()
    return jsonify({"success": True})

@app.route("/api/dreamina/task/close_browsers", methods=["POST"])
def dreamina_close_browsers():
    if state_dreamina.module and hasattr(state_dreamina.module, "ACTIVE_DRIVERS"):
        for d in state_dreamina.module.ACTIVE_DRIVERS:
            try: d.quit()
            except: pass
        state_dreamina.module.ACTIVE_DRIVERS.clear()
    return jsonify({"success": True})

@app.route("/api/dreamina/task/stream")
def dreamina_task_stream():
    def generate():
        yield f"data: {json.dumps({'type':'log','level':'INFO','time':datetime.now().strftime('%H:%M:%S'),'msg':'Ket noi log stream Dreamina...'})}\n\n"
        while True:
            try:
                msg = state_dreamina.log_queue.get(timeout=25)
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'type':'ping'})}\n\n"
    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

def _run_dreamina_task(count, threads, browser_type, headless, mail_api_source):
    import importlib
    try:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)

        state_dreamina.module = importlib.import_module("src.bots.dreamina_hotmail")
        bot = state_dreamina.module
        bot.log = state_dreamina.log
        bot.get_rotated_proxy = patched_get_proxy
        bot.GLOBAL_STOP_EVENT = state_dreamina.task_stop

        # Patch save_account to use DB
        def dreamina_save_db(email, password):
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO accounts (app, uid, email, password) VALUES (?, '', ?, ?)",
                                   ("dreamina", email, password))
                    conn.commit()
                state_dreamina.log_queue.put(json.dumps({"type": "account", "email": email, "password": password}))
            except Exception as e:
                state_dreamina.log(f"Lỗi lưu DB: {e}", "ERR")

        bot.save_account = dreamina_save_db

        bot.load_hotmails_to_queue(limit=count)

        done = {"ok": 0, "fail": 0}
        def worker(i):
            time.sleep((i % threads) * 2.5)
            while not bot.HOTMAIL_QUEUE.empty() and not state_dreamina.task_stop.is_set():
                res = bot.register_one_account(i, keep_open=False, batch_size=threads,
                                               use_proxy=True, headless=headless,
                                               browser_type=browser_type,
                                               mail_api_source=mail_api_source)
                state_dreamina.log_queue.put(json.dumps({"type": "result", "success": bool(res)}))
                if res: done["ok"] += 1
                else: done["fail"] += 1

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
            futures = [ex.submit(worker, idx+1) for idx in range(threads)]
            concurrent.futures.wait(futures)

        if state_dreamina.task_stop.is_set():
            state_dreamina.log_queue.put(json.dumps({"type": "stopped"}))
        else:
            state_dreamina.log(f"✅ Xong! {done['ok']} thành công / {done['fail']} thất bại", "OK")
            state_dreamina.log_queue.put(json.dumps({"type": "done", "ok": done["ok"], "fail": done["fail"]}))
    except Exception as e:
        state_dreamina.log(f"Lỗi task Dreamina: {type(e).__name__}: {e}", "ERR")
        state_dreamina.log_queue.put(json.dumps({"type": "done", "ok": 0, "fail": 0}))
    finally:
        state_dreamina.is_running = False

def _auto_proxy_rotator():
    import time
    import requests
    while True:
        time.sleep(180)
        try:
            requests.post("http://127.0.0.1:5050/api/proxy/rotate", timeout=20)
        except:
            pass

threading.Thread(target=_auto_proxy_rotator, daemon=True).start()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════╗
║   Combined Auto Register - Web UI Server         ║
║   (CapCut + Higgsfield)                          ║
╚══════════════════════════════════════════════════╝
🌐  Mở trình duyệt: http://localhost:5050
⏹  Ctrl+C để dừng server
""")
    sys.path.insert(0, os.path.dirname(__file__))
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
