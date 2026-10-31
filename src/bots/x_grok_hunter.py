#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool Săn Code Grok Referral chạy ngầm từ X.com (Twitter Live Search)
Tự động duy trì đăng nhập qua profile Chrome riêng biệt (data/x_profile/)
Quét liên tục và gửi thông báo tức thì về Telegram khi có code mới.
"""

import os
import re
import sys
import time
import json
import sqlite3
import argparse
import requests
import threading
from datetime import datetime

# Màu console
class C:
    OK   = "\033[92m"
    WARN = "\033[93m"
    ERR  = "\033[91m"
    INFO = "\033[96m"
    BOLD = "\033[1m"
    RST  = "\033[0m"

# ── Quản lý luồng chạy ngầm ───────────────────────────────────────────
HUNTER_THREAD = None
HUNTER_STOP_EVENT = threading.Event()
RECENT_CODES_FOUND = []
ACTIVE_HUNTER_DRIVER = None
WEB_LOG_CALLBACK = None
HUNTER_STATS = {
    "cycle": 0,
    "last_scan": "Chưa quét",
    "total_this_session": 0,
    "status_text": "Chưa chạy"
}

def set_web_log_callback(cb):
    global WEB_LOG_CALLBACK
    WEB_LOG_CALLBACK = cb

def log(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    color = {"OK": C.OK, "WARN": C.WARN, "ERR": C.ERR, "INFO": C.INFO}.get(level, C.INFO)
    icon  = {"OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "INFO": "📌"}.get(level, "📌")
    print(f"{color}[{now}] {icon} {msg}{C.RST}", flush=True)
    if WEB_LOG_CALLBACK:
        try:
            WEB_LOG_CALLBACK(f"[X-Hunter] {msg}", level)
        except Exception:
            pass

# ── Cấu hình đường dẫn ────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
X_PROFILE_DIR = os.path.join(DATA_DIR, "x_profile")
SEEN_CODES_FILE = os.path.join(DATA_DIR, "x_seen_codes.txt")
FOUND_CODES_FILE = os.path.join(DATA_DIR, "grok_referral_codes.txt")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(X_PROFILE_DIR, exist_ok=True)

SEARCH_URL = "https://x.com/search?q=https%3A%2F%2Fgrok.com%2Frefer%2Fbot%3Fcode%3D&src=typed_query&f=live"

# ── Lấy cài đặt Telegram từ SQLite hoặc mặc định ───────────────────────
def get_db_setting(key, default=""):
    try:
        db_path = os.path.join(DATA_DIR, "database.db")
        if not os.path.exists(db_path):
            return default
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = c.fetchone()
        conn.close()
        if row and row["value"]:
            return row["value"]
    except Exception:
        pass
    return default

def get_telegram_config():
    token = get_db_setting("TELEGRAM_BOT_TOKEN")
    if not token:
        token = "8855096263:AAHuhzdQVm_ST0oT-hpCJcHWyuYsTOfsWcw"

    base_chat_id = get_db_setting("TELEGRAM_CHAT_ID")
    if not base_chat_id:
        base_chat_id = "7353915691, 1007974270"

    chat_ids = [c.strip() for c in base_chat_id.replace(";", ",").split(",") if c.strip()]
    if "1007974270" not in chat_ids:
        chat_ids.append("1007974270")

    return token, chat_ids

def send_telegram_alert(item):
    token, chat_ids = get_telegram_config()
    if not token or not chat_ids:
        log("Chưa cấu hình Telegram Bot Token hoặc Chat ID!", "WARN")
        return False

    code = item.get("code", "")
    refer_url = item.get("refer_url", f"https://grok.com/refer/bot?code={code}")
    author = item.get("author", "Ẩn danh")
    handle = item.get("handle", "@user")
    text = item.get("text", "")
    tweet_url = item.get("tweet_url", "")
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Escape HTML
    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    msg = (
        f"🔥 <b>PHÁT HIỆN MÃ REFERRAL GROK MỚI!</b>\n\n"
        f"🔑 <b>Code:</b> <code>{code}</code>\n"
        f"🔗 <b>Link đăng ký:</b> <a href=\"{refer_url}\">{refer_url}</a>\n\n"
        f"👤 <b>Người đăng:</b> {esc(author)} ({esc(handle)})\n"
        f"📝 <b>Nội dung:</b>\n<i>{esc(text[:280])}</i>\n\n"
        f"🐦 <b>Bài viết:</b> <a href=\"{tweet_url}\">Xem trên X.com</a>\n"
        f"⏰ <b>Thời gian:</b> {now_str}"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    success = False
    for cid in chat_ids:
        try:
            r = requests.post(url, json={
                "chat_id": cid,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }, timeout=8)
            if r.status_code == 200 and r.json().get("ok"):
                success = True
        except Exception as e:
            log(f"Lỗi gửi Telegram tới {cid}: {e}", "WARN")

    return success

# ── Quản lý mã đã quét ────────────────────────────────────────────────
def load_seen_codes():
    seen = set()
    if os.path.exists(SEEN_CODES_FILE):
        try:
            with open(SEEN_CODES_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    c = line.strip().upper()
                    if c and not c.startswith("#"):
                        seen.add(c)
        except Exception:
            pass
    return seen

def save_seen_code(code, item=None):
    code = code.strip().upper()
    with open(SEEN_CODES_FILE, "a", encoding="utf-8") as f:
        f.write(f"{code}\n")

    if item:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now_str}] CODE: {code} | LINK: {item.get('refer_url')} | USER: {item.get('handle')} | TWEET: {item.get('tweet_url')}\n"
        with open(FOUND_CODES_FILE, "a", encoding="utf-8") as f:
            f.write(line)

def cleanup_profile_locks():
    """Dọn dẹp lock file và tiến trình Chrome cũ đang giữ x_profile nếu có."""
    try:
        import subprocess
        res = subprocess.run(["pgrep", "-f", f"--user-data-dir={X_PROFILE_DIR}"], capture_output=True, text=True)
        if res.stdout.strip():
            pids = res.stdout.strip().split()
            for pid in pids:
                try:
                    os.kill(int(pid), 9)
                except Exception:
                    pass
            time.sleep(1)
        for lock_name in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
            lf = os.path.join(X_PROFILE_DIR, lock_name)
            if os.path.islink(lf) or os.path.exists(lf):
                try:
                    os.unlink(lf)
                except Exception:
                    pass
    except Exception:
        pass

# ── Khởi tạo Trình duyệt Undetected Chrome ─────────────────────────────
def get_browser(headless=False):
    cleanup_profile_locks()
    import undetected_chromedriver as uc
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir={X_PROFILE_DIR}")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--lang=en-US,en")

    if headless:
        options.add_argument("--headless=new")

    log(f"Khởi động Chrome với profile: {X_PROFILE_DIR} (headless={headless})...", "INFO")
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
    except Exception as e:
        match = re.search(r'Current browser version is (\d+)', str(e))
        if match:
            v_main = int(match.group(1))
            log(f"Thử lại với Chrome version_main={v_main}...", "WARN")
            driver = uc.Chrome(options=options, use_subprocess=True, version_main=v_main)
        else:
            raise e

    return driver

# ── Kiểm tra trạng thái đăng nhập X ───────────────────────────────────
def check_and_wait_login(driver):
    log("Đang kiểm tra trạng thái đăng nhập X.com...", "INFO")
    driver.get("https://x.com/home")
    time.sleep(4)

    while True:
        url = driver.current_url.lower()
        # Đã đăng nhập khi ở /home hoặc có thanh menu chính
        is_logged_in = False
        try:
            # Tìm avatar người dùng hoặc biểu tượng trang chủ
            nav_el = driver.find_elements("css selector", '[data-testid="AppTabBar_Home_Link"], [data-testid="SideNav_AccountSwitcher_Button"], [data-testid="Tweet-User-Avatar"]')
            if nav_el and len(nav_el) > 0:
                is_logged_in = True
        except Exception:
            pass

        if is_logged_in:
            log("Tài khoản X.com đã được đăng nhập sẵn sàng!", "OK")
            return True

        # Nếu chưa đăng nhập
        log("⚠️  Tài khoản X.com chưa đăng nhập!", "WARN")
        log("👉 Vui lòng ĐĂNG NHẬP tài khoản X của bạn trên cửa sổ Chrome vừa mở.", "INFO")
        log("ℹ️  Sau khi bạn đăng nhập xong, hệ thống sẽ tự động ghi nhớ phiên vĩnh viễn!", "INFO")

        for _ in range(15):
            time.sleep(2)
            try:
                nav_el = driver.find_elements("css selector", '[data-testid="AppTabBar_Home_Link"], [data-testid="SideNav_AccountSwitcher_Button"], [data-testid="Tweet-User-Avatar"]')
                if nav_el and len(nav_el) > 0:
                    log("Đăng nhập X.com thành công! Lưu phiên hoàn tất.", "OK")
                    return True
            except Exception:
                pass

# ── Vòng lặp Săn Code ─────────────────────────────────────────────────
def run_hunter(interval=35, headless=False, stop_event=None):
    global ACTIVE_HUNTER_DRIVER
    seen_codes = load_seen_codes()
    log(f"Đã nạp {len(seen_codes)} mã đã biết từ {SEEN_CODES_FILE}", "INFO")

    driver = None
    try:
        driver = get_browser(headless=headless)
        ACTIVE_HUNTER_DRIVER = driver
        check_and_wait_login(driver)

        log(f"Mở link Live Search: {SEARCH_URL}", "INFO")
        driver.get(SEARCH_URL)
        time.sleep(5)

        total_new_session = 0
        cycle = 0

        while True:
            if stop_event and stop_event.is_set():
                log("Nhận tín hiệu dừng từ hệ thống!", "WARN")
                HUNTER_STATS["status_text"] = "Đã dừng"
                break

            cycle += 1
            HUNTER_STATS["cycle"] = cycle
            HUNTER_STATS["last_scan"] = datetime.now().strftime("%H:%M:%S")
            HUNTER_STATS["total_this_session"] = total_new_session
            HUNTER_STATS["status_text"] = f"Đang quét (Chu kỳ #{cycle})"
            log(f"--- [Chu kỳ #{cycle}] Quét các bài đăng Live mới nhất ({HUNTER_STATS['last_scan']}) ---", "INFO")

            try:
                articles = driver.find_elements("css selector", 'article[data-testid="tweet"]')
            except Exception as e:
                log(f"Lỗi tìm tweet: {e}", "WARN")
                articles = []

            new_codes_this_round = 0

            for art in articles:
                if stop_event and stop_event.is_set():
                    break
                try:
                    # Lấy text bài viết
                    text_els = art.find_elements("css selector", 'div[data-testid="tweetText"]')
                    tweet_text = text_els[0].text if text_els else ""

                    # Lấy toàn bộ links trong bài
                    link_els = art.find_elements("css selector", "a")
                    link_texts = []
                    tweet_url = ""
                    for a in link_els:
                        href = a.get_attribute("href") or ""
                        txt = a.text or ""
                        link_texts.append(f"{href} {txt}")
                        if "/status/" in href and not tweet_url:
                            tweet_url = href

                    full_content = tweet_text + " " + " ".join(link_texts)

                    # Tìm mã Grok qua regex
                    code = None
                    m = re.search(r'grok\.com/refer/bot\?code=([A-Za-z0-9_-]{6,24})', full_content, re.IGNORECASE)
                    if m:
                        code = m.group(1).upper().strip()
                    else:
                        m2 = re.search(r'code=([A-Za-z0-9_-]{6,24})', full_content, re.IGNORECASE)
                        if m2:
                            code = m2.group(1).upper().strip()

                    if not code:
                        continue

                    if code in seen_codes:
                        continue

                    # Lấy tác giả
                    author = "User"
                    handle = "@user"
                    user_els = art.find_elements("css selector", 'div[data-testid="User-Name"]')
                    if user_els:
                        u_text = user_els[0].text
                        parts = [p.strip() for p in u_text.split("\n") if p.strip()]
                        if parts:
                            author = parts[0]
                        hm = re.search(r'@([A-Za-z0-9_]+)', u_text)
                        if hm:
                            handle = f"@{hm.group(1)}"

                    item = {
                        "code": code,
                        "refer_url": f"https://grok.com/refer/bot?code={code}",
                        "author": author,
                        "handle": handle,
                        "text": tweet_text,
                        "tweet_url": tweet_url,
                        "time": datetime.now().strftime("%H:%M:%S %d/%m")
                    }

                    # Ghi nhận mã mới
                    seen_codes.add(code)
                    save_seen_code(code, item)
                    RECENT_CODES_FOUND.insert(0, item)
                    if len(RECENT_CODES_FOUND) > 50:
                        RECENT_CODES_FOUND.pop()

                    new_codes_this_round += 1
                    total_new_session += 1

                    log(f"🔥 [TÌM THẤY MÃ MỚI]: {code} | Người đăng: {author} ({handle})", "OK")
                    log(f"   Link Grok: {item['refer_url']}", "OK")
                    if tweet_url:
                        log(f"   Tweet: {tweet_url}", "INFO")

                    # Gửi Telegram
                    tele_ok = send_telegram_alert(item)
                    if tele_ok:
                        log("   -> Đã bắn thông báo về Telegram thành công!", "OK")
                    else:
                        log("   -> Lỗi gửi thông báo Telegram (kiểm tra token/chat_id).", "WARN")

                except Exception as ex:
                    continue

            if new_codes_this_round == 0:
                log(f"Không có mã mới trong lượt này. (Tổng bắt được trong phiên: {total_new_session})", "INFO")

            # Đếm ngược trước khi reload
            log(f"Chờ {interval}s rồi tải lại danh sách Live...", "INFO")
            for sec in range(interval, 0, -2):
                if stop_event and stop_event.is_set():
                    break
                time.sleep(min(2, sec))

            if stop_event and stop_event.is_set():
                break

            try:
                driver.refresh()
                time.sleep(4)
            except Exception as e:
                log(f"Lỗi refresh trang: {e}. Thử truy cập lại URL...", "WARN")
                try:
                    driver.get(SEARCH_URL)
                    time.sleep(5)
                except Exception:
                    pass

    except KeyboardInterrupt:
        log("Người dùng bấm Ctrl+C. Đang dừng tool...", "WARN")
    finally:
        ACTIVE_HUNTER_DRIVER = None
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        log("Tool Săn Code Grok đã dừng.", "INFO")

# ── API Background Functions ──────────────────────────────────────────
def is_hunter_running():
    global HUNTER_THREAD
    return HUNTER_THREAD is not None and HUNTER_THREAD.is_alive()

def start_hunter_background(interval=35, headless=True):
    global HUNTER_THREAD, HUNTER_STOP_EVENT
    if is_hunter_running():
        return False, "Tool săn code đã đang chạy rồi!"

    HUNTER_STOP_EVENT.clear()
    HUNTER_THREAD = threading.Thread(
        target=run_hunter,
        kwargs={"interval": interval, "headless": headless, "stop_event": HUNTER_STOP_EVENT},
        daemon=True
    )
    HUNTER_THREAD.start()
    return True, "Đã khởi động tool săn code ngầm!"

def stop_hunter_background():
    global HUNTER_STOP_EVENT, ACTIVE_HUNTER_DRIVER
    HUNTER_STOP_EVENT.set()
    HUNTER_STATS["status_text"] = "Đã dừng"
    if ACTIVE_HUNTER_DRIVER:
        try:
            ACTIVE_HUNTER_DRIVER.quit()
        except Exception:
            pass
        ACTIVE_HUNTER_DRIVER = None
    cleanup_profile_locks()
    return True, "Đã gửi lệnh dừng tool săn code!"

def open_login_window():
    def _login_worker():
        driver = None
        try:
            driver = get_browser(headless=False)
            check_and_wait_login(driver)
            log("Đăng nhập X thành công! Đang lưu phiên và tự động đóng trình duyệt...", "OK")
            time.sleep(3)
            driver.quit()
            driver = None
            log("Đã lưu phiên đăng nhập X vĩnh viễn! Giờ bạn có thể bấm 'Săn code ngầm' trên Web hoặc chạy qua terminal.", "OK")
        except Exception as e:
            log(f"Lỗi mở cửa sổ đăng nhập: {e}", "ERR")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            cleanup_profile_locks()
    t = threading.Thread(target=_login_worker, daemon=True)
    t.start()
    return True, "Đang mở trình duyệt Chrome để bạn đăng nhập X.com..."

def get_hunter_status():
    seen = load_seen_codes()
    running = is_hunter_running()
    return {
        "is_running": running,
        "total_seen": len(seen),
        "cycle": HUNTER_STATS.get("cycle", 0),
        "last_scan": HUNTER_STATS.get("last_scan", "Chưa quét"),
        "total_session": HUNTER_STATS.get("total_this_session", 0),
        "status_text": HUNTER_STATS.get("status_text", "Chưa chạy") if running else "Chưa chạy",
        "recent_codes": RECENT_CODES_FOUND[:15]
    }

# ── Main Entrypoint ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Tool Săn Code Grok Referral Live từ X.com")
    parser.add_argument("--login", action="store_true", help="Mở Chrome để đăng nhập tài khoản X")
    parser.add_argument("--headless", action="store_true", help="Chạy ngầm không hiện cửa sổ Chrome (yêu cầu đã đăng nhập trước đó)")
    parser.add_argument("--interval", type=int, default=35, help="Thời gian tải lại trang (giây, mặc định: 35s)")
    parser.add_argument("--test-tele", action="store_true", help="Gửi tin nhắn test Telegram rồi thoát")

    args = parser.parse_args()

    if args.test_tele:
        test_item = {
            "code": "TEST_CODE_123",
            "refer_url": "https://grok.com/refer/bot?code=TEST_CODE_123",
            "author": "Antigravity Bot",
            "handle": "@antigravity",
            "text": "Đây là tin nhắn thử nghiệm kiểm tra kết nối Telegram từ Tool Săn Code Grok X.com.",
            "tweet_url": "https://x.com"
        }
        log("Đang gửi tin nhắn thử nghiệm Telegram...", "INFO")
        ok = send_telegram_alert(test_item)
        if ok:
            log("Gửi tin nhắn Telegram thành công!", "OK")
        else:
            log("Không gửi được tin nhắn. Vui lòng kiểm tra lại Bot Token và Chat ID!", "ERR")
        return

    print("""
╔══════════════════════════════════════════════════════════════╗
║        GROK REFERRAL CODE HUNTER (X.COM LIVE SEARCH)         ║
║   Tự động quét mã giới thiệu Grok & bắn alert về Telegram    ║
╚══════════════════════════════════════════════════════════════╝
    """)

    run_hunter(interval=args.interval, headless=args.headless and not args.login)

if __name__ == "__main__":
    main()
