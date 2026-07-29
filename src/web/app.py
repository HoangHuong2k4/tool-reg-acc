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
        try:
            conn.execute("ALTER TABLE accounts ADD COLUMN twofa TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE accounts ADD COLUMN momo TEXT")
        except sqlite3.OperationalError:
            pass

        
        default_settings = {
            "PROXY_TYPE": "proxyquick",
            "PROXY_API_TOKEN": "proxyquick6_9df2f4385910e1a5d4bf45498a783abf845ba8776cb2642cb31839a1740b29ef",
            "PROXY_MERCHANT": "a20f20d6-9512-40fd-9a12-eeff809fdaeb",
            "PROXY_ID": "953319",
            "PROXYXOAY_KEY": ""
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
        "PROXYXOAY_KEY": ""
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
            PROXY_V3_INDEX = (PROXY_V3_INDEX + 1) % len(proxies)
            current_proxy_line = proxies[PROXY_V3_INDEX]
            
            if "|" in current_proxy_line:
                p_str, url = current_proxy_line.split("|", 1)
            else:
                p_str, url = "", current_proxy_line
            
            r = requests.get(url.strip(), timeout=15)
            data = r.json()
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
                msg = data.get("message", str(data))
                time_rem = data.get("timeRemaining")
                return jsonify({"success": False, "error": msg, "timeRemaining": time_rem})
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
    browser_type = data.get("browser_type", "chrome")
    headless = bool(data.get("headless", False))

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
    state_capcut.task_thread = threading.Thread(target=_run_capcut_task, args=(mode, count, threads, join_link, mail_type, browser_type, headless), daemon=True)
    state_capcut.task_thread.start()
    return jsonify({"success": True})

@app.route("/api/capcut/task/stop", methods=["POST"])
def capcut_task_stop():
    state_capcut.task_stop.set()
    capcut_close_browsers()
    return jsonify({"success": True})

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

def _run_capcut_task(mode, count, threads, join_link, mail_type, browser_type, headless):
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
                    res = bot.register_one_account(i, join_link if mode == 2 else None, keep_open=(mode == 1), batch_size=threads, headless=headless, browser_type=browser_type, get_link=(mode == 3))
                    state_capcut.log_queue.put(json.dumps({"type": "result", "success": bool(res)}))
                    if res: done["ok"] += 1
                    else: done["fail"] += 1

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
                futures = [ex.submit(worker, i+1) for i in range(threads)]
                concurrent.futures.wait(futures)
        else:
            def worker(i):
                try:
                    time.sleep((i % threads) * 2.5)
                    if state_capcut.task_stop.is_set(): return
                    res = bot.register_one_account(i, join_link if mode == 2 else None, keep_open=(mode == 1), batch_size=threads, headless=headless, browser_type=browser_type, get_link=(mode == 3))
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
    try:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT email, password, twofa, momo FROM accounts WHERE app='gpt' ORDER BY id ASC")
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
            cursor.execute("SELECT email, password, twofa FROM accounts WHERE app='gpt' ORDER BY id ASC")
            for row in cursor.fetchall():
                text += f"{row['email']}\t{row['password']}\t{row['twofa'] or ''}\n"
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
            cursor.execute("SELECT email, password, twofa FROM accounts WHERE app='gpt' ORDER BY id ASC")
            for row in cursor.fetchall():
                text += f"{row['email']}|{row['password']}|{row['twofa'] or ''}\n"
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
    check_momo = data.get("check_momo", True)

    state_gpt.task_stop.clear()
    while not state_gpt.log_queue.empty():
        try: state_gpt.log_queue.get_nowait()
        except: break

    state_gpt.is_running = True
    state_gpt.task_thread = threading.Thread(target=_run_gpt_task, args=(count, threads, mail_type, check_momo), daemon=True)
    state_gpt.task_thread.start()
    return jsonify({"success": True})

@app.route("/api/gpt/task/stop", methods=["POST"])
def gpt_task_stop():
    state_gpt.task_stop.set()
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

def _run_gpt_task(count, threads, mail_type, check_momo=True):
    state_gpt.check_momo = check_momo
    import importlib
    try:
        state_gpt.module = importlib.import_module("src.bots.gpt_hotmail")
        bot = state_gpt.module
        bot.log = state_gpt.log
        bot.get_rotated_proxy = patched_get_proxy
        
        # Patch để dừng OTP ngang
        import src.bots.capcut_hotmail as ch
        ch.GLOBAL_STOP_EVENT = state_gpt.task_stop

        # Đẩy config MoMo xuống bot
        bot.CHECK_MOMO = state_gpt.check_momo

        # Patch save_account to use DB
        def gpt_save_db(email, password, totp_secret, has_momo=False):
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    momo_str = str(has_momo) if isinstance(has_momo, str) else ("có" if has_momo else "không")
                    cursor.execute("INSERT INTO accounts (app, uid, email, password, twofa, momo) VALUES (?, '', ?, ?, ?, ?)", 
                                   ("gpt", email, password, totp_secret, momo_str))
                    conn.commit()
            except Exception as e:
                state_gpt.log(f"Lỗi lưu DB: {e}", "ERR")
                
        bot.save_account = gpt_save_db


        done = {"ok": 0, "fail": 0}
        
        bot.load_hotmails_to_queue(limit=count)
        def worker(i):
            time.sleep((i % threads) * 2.5)
            while not bot.HOTMAIL_QUEUE.empty() and not state_gpt.task_stop.is_set():
                res = bot.register_one_account(i)
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
            state_gpt.log(f"✅ Xong! {done['ok']} thành công / {done['fail']} thất bại", "OK")
            state_gpt.log_queue.put(json.dumps({"type": "done", "ok": done["ok"], "fail": done["fail"]}))
    except Exception as e:
        state_gpt.log(f"Lỗi task: {type(e).__name__}: {e}", "ERR")
        state_gpt.log_queue.put(json.dumps({"type": "done", "ok": 0, "fail": 0}))
    finally:
        state_gpt.is_running = False

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
