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

import pymysql

# ─── Cấu hình Database ───────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "auto_register",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}

def get_db():
    return pymysql.connect(**DB_CONFIG)

def load_settings():
    settings = {
        "PROXY_API_TOKEN": "",
        "PROXY_MERCHANT": "",
        "PROXY_ID": ""
    }
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT `key`, `value` FROM settings")
                for row in cursor.fetchall():
                    settings[row['key']] = row['value']
    except Exception as e:
        print("Lỗi load settings:", e)
    return settings

# Biến lưu trữ Proxy server hiện hành
PROXY_HOST       = "180.93.2.171"
PROXY_PORT       = 3131
PROXY_USER       = "kierangrayson226"
PROXY_PASS       = "odq0nda0odmzoa=="

CAPCUT_HOTMAIL_FILE = os.path.join(os.path.dirname(__file__), "hotmails.txt")

# ─── Flask App ────────────────────────────────────────────────────────────────
app = Flask(__name__)

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
            with conn.cursor() as cursor:
                for k, v in data.items():
                    cursor.execute("INSERT INTO settings (`key`, `value`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `value`=VALUES(`value`)", (k, v))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── Proxy ─────────────────────────────────────────────────────────────────────
@app.route("/api/proxy/status")
def proxy_status():
    try:
        proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        r = requests.get("https://ipinfo.io/ip", proxies={"http": proxy_url, "https": proxy_url}, timeout=10)
        return jsonify({"ip": r.text.strip(), "ok": True})
    except Exception as e:
        return jsonify({"ip": None, "ok": False, "error": str(e)})

@app.route("/api/proxy/rotate", methods=["POST"])
def proxy_rotate():
    global PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS
    settings = load_settings()
    headers = {
        "Authorization": f"Bearer {settings.get('PROXY_API_TOKEN', '')}",
        "x-merchant-id": settings.get('PROXY_MERCHANT', '')
    }
    try:
        url = f"https://proxyquick.click/api/v2/proxies/{settings.get('PROXY_ID', '')}/rotate"
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        if data.get("status") == "success":
            proxy_str = data.get("proxy", "")
            new_ip = data.get("ip", "")
            parts = proxy_str.split(":")
            if len(parts) >= 4:
                PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS = parts[0], int(parts[1]), parts[2], parts[3]
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
            with conn.cursor() as cursor:
                if session_only:
                    cursor.execute("SELECT id, uid, email, password FROM accounts WHERE app='capcut' AND id > %s ORDER BY id ASC", (state_capcut.last_start_id,))
                else:
                    cursor.execute("SELECT id, uid, email, password FROM accounts WHERE app='capcut' ORDER BY id ASC")
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
            with conn.cursor() as cursor:
                if session_only:
                    cursor.execute("SELECT uid, email, password, join_link, ms_token FROM accounts WHERE app='capcut' AND id > %s ORDER BY id ASC", (state_capcut.last_start_id,))
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
            with conn.cursor() as cursor:
                if session_only:
                    cursor.execute("SELECT email, password FROM accounts WHERE app='capcut' AND id > %s ORDER BY id ASC", (state_capcut.last_start_id,))
                else:
                    cursor.execute("SELECT email, password FROM accounts WHERE app='capcut' ORDER BY id ASC")
                for row in cursor.fetchall():
                    text += f"{row['email']}|{row['password']}\n"
    except Exception:
        pass
    return text, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/api/capcut/accounts/clear", methods=["POST"])
def capcut_accounts_clear():
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
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
            with conn.cursor() as cursor:
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

def _run_capcut_task(mode, count, threads, join_link, mail_type, browser_type="chrome", headless=False):
    try:
        import importlib.util
        if mail_type == "domain":
            file_path = os.path.join(os.path.dirname(__file__), "auto_register_capcut-new.py")
        else:
            file_path = os.path.join(os.path.dirname(__file__), "auto_register_capcut-hotmail.py")
            
        spec = importlib.util.spec_from_file_location("bot_capcut", file_path)
        bot = importlib.util.module_from_spec(spec)
        sys.modules["bot_capcut"] = bot
        spec.loader.exec_module(bot)
        state_capcut.module = bot
        
        bot.log = state_capcut.log
        bot.get_rotated_proxy = patched_get_proxy
        
        # Patch save_account to use DB
        def capcut_save_db(uid, email, password, *args, **kwargs):
            jl = args[0] if len(args) > 0 else kwargs.get("join_link", "")
            msToken = args[1] if len(args) > 1 else kwargs.get("msToken", "")
            try:
                with get_db() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("INSERT INTO accounts (app, uid, email, password, join_link, ms_token) VALUES (%s, %s, %s, %s, %s, %s)", 
                                       ("capcut", uid, email, password, jl, msToken))
                    conn.commit()
            except Exception as e:
                state_capcut.log(f"Lỗi lưu DB: {e}", "ERR")
                
        bot.save_account = capcut_save_db
        
        done = {"ok": 0, "fail": 0}
        
        if mail_type == "hotmail":
            bot.load_hotmails_to_queue(limit=count)
            def worker(i):
                time.sleep((i % threads) * 2.5)
                while not bot.HOTMAIL_QUEUE.empty() and not state_capcut.task_stop.is_set():
                    res = bot.register_one_account(i, join_link if mode == 2 else None, keep_open=True, batch_size=threads, headless=headless, browser_type=browser_type)
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
                    res = bot.register_one_account(i, join_link if mode == 2 else None, keep_open=True, batch_size=threads, headless=headless, browser_type=browser_type)
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
            state_capcut.log_queue.put(json.dumps({"type": "done", "ok": done["ok"], "fail": done["fail"]}))
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
            with conn.cursor() as cursor:
                cursor.execute("SELECT email, password FROM accounts WHERE app='higgsfield' ORDER BY id DESC")
                accounts = cursor.fetchall()
    except Exception:
        pass
    return jsonify({"accounts": accounts})

@app.route("/api/higgsfield/accounts/raw")
def higgsfield_accounts_raw():
    text = ""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
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
            with conn.cursor() as cursor:
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
    keep_open = not headless

    state_higgsfield.task_stop.clear()
    while not state_higgsfield.log_queue.empty():
        try: state_higgsfield.log_queue.get_nowait()
        except: break

    state_higgsfield.is_running = True
    state_higgsfield.task_thread = threading.Thread(target=_run_higgsfield_task, args=(count, threads, headless, browser_type, keep_open), daemon=True)
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

def _run_higgsfield_task(count, threads, headless, browser_type, keep_open):
    try:
        import auto_register_higgsfield as bot
        state_higgsfield.module = bot
        bot.log = state_higgsfield.log
        bot.get_rotated_proxy = patched_get_proxy
        
        # Patch save_account to use DB
        def higgsfield_save_db(email, password):
            try:
                with get_db() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("INSERT INTO accounts (app, email, password) VALUES (%s, %s, %s)", ("higgsfield", email, password))
                    conn.commit()
            except Exception as e:
                state_higgsfield.log(f"Lỗi lưu DB: {e}", "ERR")
                
        bot.save_account = higgsfield_save_db

        done = {"ok": 0, "fail": 0}
        def worker(i):
            time.sleep((i % threads) * 2.5)
            if state_higgsfield.task_stop.is_set(): return
            res = bot.register_one_account(i, keep_open=keep_open, batch_size=threads, use_proxy=True, headless=headless, browser_type=browser_type)
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
