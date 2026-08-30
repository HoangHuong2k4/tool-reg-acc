#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT Gmail94 Bot - Đăng ký ChatGPT dùng Gmail mua từ Gmail94 API.

Mỗi Gmail mua được tạo ra 4 biến thể email:
  abc@gmail.com
  abc@googlemail.com
  abc+1@gmail.com
  abc+1@googlemail.com

→ 1 lần mua Gmail = 4 tài khoản ChatGPT.
  OTP của tất cả 4 biến thể đều về cùng 1 inbox (cùng order_id).

API Gmail94:
  - Mua Gmail:  POST https://gmail94.com/api/otp/create?token=TOKEN&service=chatgpt
  - Đọc OTP:   GET  https://gmail94.com/api/otp/read?token=TOKEN&order_id=ORDER_ID&service=chatgpt
"""

import os
import sys
import queue
import threading
import time
import requests
import logging
from datetime import datetime
from typing import Optional, Dict, Set, Tuple

# ─── Paths ───────────────────────────────────────────────────────────────────
_BOT_DIR        = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR       = os.path.abspath(os.path.join(_BOT_DIR, "..", ".."))
_DATA_DIR       = os.path.join(_ROOT_DIR, "data")
from src.bots.gpt_selenium_utils import run_selenium_registration_standalone

# ─── File paths ───────────────────────────────────────────────────────────────
ONL_FILE = os.path.join(_DATA_DIR, "gmail94-gpt-done.txt")

# ─── State ────────────────────────────────────────────────────────────────────
FILE_LOCK     = threading.Lock()
TASK_QUEUE    = queue.Queue()
CHECK_MOMO    = True
GMAIL94_TOKEN = ""   # Được set bởi app.py từ Settings DB
GMAIL94_PASSWORD = "" # Mật khẩu ảo được set bởi app.py
GLOBAL_STOP_EVENT = threading.Event()

# ─── Patchable hooks (bị app.py override) ─────────────────────────────────────
def log(msg, level="INFO"):
    # type: (str, str) -> None
    now = datetime.now().strftime("%H:%M:%S")
    print("[{}] [{}] {}".format(now, level, msg))

def get_rotated_proxy():
    # type: () -> Optional[dict]
    return None

def save_account(email, password, totp_secret, has_momo=False, has_uudai=False):
    # type: (str, str, str, bool) -> None
    pass


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _format_proxy(proxy_dict):
    # type: (Optional[dict]) -> Optional[str]
    if not proxy_dict:
        return None
    host = proxy_dict.get("host", "")
    port = proxy_dict.get("port", "")
    user = proxy_dict.get("user", "")
    pw   = proxy_dict.get("pass", "")
    if user and pw:
        return "http://{}:{}@{}:{}".format(user, pw, host, port)
    return "http://{}:{}".format(host, port) if host else None


def expand_gmail_variants(email):
    # type: (str) -> list
    """
    Từ 1 Gmail tạo ra 4 biến thể email:
      abc@gmail.com          → đăng ký GPT #1
      abc@googlemail.com     → đăng ký GPT #2
      abc+1@gmail.com        → đăng ký GPT #3
      abc+1@googlemail.com   → đăng ký GPT #4

    Tất cả 4 cùng nhận mail về 1 inbox → dùng chung order_id của Gmail94.
    """
    if "@" not in email:
        return [email]
    local, _ = email.split("@", 1)
    base = local.split("+")[0]  # bỏ suffix +xxx nếu có sẵn
    return [
        "{}@gmail.com".format(base),
        "{}@googlemail.com".format(base),
        "{}+1@gmail.com".format(base),
        "{}+1@googlemail.com".format(base),
    ]


def _save_done(email, order_id):
    # type: (str, str) -> None
    with FILE_LOCK:
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            with open(ONL_FILE, "a", encoding="utf-8") as f:
                f.write("{}|{}\n".format(email, order_id))
        except Exception as e:
            log("Loi ghi done file: {}".format(e), "WARN")


# ─── Gmail94 API ──────────────────────────────────────────────────────────────

def gmail94_buy(token):
    # type: (str) -> Optional[Dict]
    """
    Mua 1 Gmail mới từ Gmail94 cho service chatgpt.
    Trả về dict {"email": ..., "order_id": ...} hoặc None nếu lỗi.
    """
    url = "https://gmail94.com/api/otp/create"
    params = {"token": token, "service": "chatgpt"}
    try:
        resp = requests.get(url, params=params, timeout=30)
        raw = resp.text.strip() if resp.text else ""

        if not raw:
            log("Gmail94 mua loi: Response rong (HTTP {})".format(resp.status_code), "ERR")
            return None

        try:
            data = resp.json()
        except Exception:
            log("Gmail94 mua loi: Response khong phai JSON (HTTP {}): {}".format(
                resp.status_code, raw[:300]), "ERR")
            return None

        # API tra ve: {"success":true,"data":{"email":"...","order_id":"..."}}
        if data.get("success") and "data" in data and data["data"].get("email"):
            email = data["data"]["email"]
            order_id = data["data"].get("order_id", "")
            log("Gmail94 mua thanh cong: {} (order: {})".format(email, order_id), "OK")
            return {"email": email, "order_id": str(order_id)}
        else:
            err = data.get("msg") or data.get("message") or data.get("error") or str(data)
            log("Gmail94 mua that bai: {}".format(err), "ERR")
            return None
    except requests.exceptions.Timeout:
        log("Gmail94 mua loi: Timeout (30s)", "ERR")
        return None
    except Exception as e:
        log("Gmail94 mua loi exception: {}".format(e), "ERR")
        return None


def gmail94_read_otp(token, order_id, timeout=120, interval=5, seen_otps=None):
    # type: (str, str, int, int, Optional[Set]) -> Optional[str]
    """
    Polling đọc OTP từ Gmail94 cho order_id.
    - seen_otps: set các OTP đã dùng — tránh trả lại OTP cũ khi đăng ký biến thể tiếp theo.
    """
    if seen_otps is None:
        seen_otps = set()
    url = "https://gmail94.com/api/otp/read"
    params = {"token": token, "order_id": order_id, "service": "chatgpt"}
    elapsed = 0
    while elapsed < timeout:
        try:
            resp = requests.get(url, params=params, timeout=20)
            raw = resp.text.strip() if resp.text else ""

            if not raw:
                log("Gmail94 OTP: Response rong ({}/{}s)".format(elapsed, timeout), "INFO")
            else:
                try:
                    data = resp.json()
                except Exception:
                    log("Gmail94 OTP: Response khong phai JSON: {}".format(raw[:200]), "WARN")
                    data = {}

                if data.get("success") and data.get("otp"):
                    otp = str(data["otp"]).strip()
                    if otp in seen_otps:
                        log("Gmail94 OTP '{}' da dung roi, cho ma moi ({}/{}s)...".format(
                            otp, elapsed, timeout), "INFO")
                    else:
                        seen_otps.add(otp)
                        log("Gmail94 OTP nhan duoc: {}".format(otp), "OK")
                        return otp
                else:
                    msg = data.get("msg") or data.get("message") or "Chua co ma"
                    log("Gmail94 OTP cho ({}/{}s): {}".format(elapsed, timeout, msg), "INFO")
        except requests.exceptions.Timeout:
            log("Gmail94 OTP: Request timeout ({}/{}s)".format(elapsed, timeout), "WARN")
        except Exception as e:
            log("Gmail94 read OTP loi: {}".format(e), "WARN")
        time.sleep(interval)
        elapsed += interval
    log("Gmail94: Het thoi gian cho OTP ({}s)".format(timeout), "ERR")
    return None



# ─── Log Forwarding cho Web UI ──────────────────────────────────────────────

class WebUILogHandler(logging.Handler):
    def emit(self, record):
        if record.name.startswith(("urllib3", "requests", "selenium", "WDM")):
            return
        level_map = {
            logging.DEBUG: "INFO",
            logging.INFO: "INFO",
            logging.WARNING: "WARN",
            logging.ERROR: "ERR",
            logging.CRITICAL: "ERR",
        }
        lvl = level_map.get(record.levelno, "INFO")
        prefix = record.name.split(".")[-1]
        msg = "[{}] {}".format(prefix, record.getMessage())
        import sys
        print("WEBUI HANDLER RECEIVED: {}".format(msg), file=sys.stderr)
        log(msg, lvl)


_web_ui_handler = WebUILogHandler()
_web_ui_handler.setLevel(logging.INFO)
logging.getLogger("").addHandler(_web_ui_handler)


# ─── Registration State ───────────────────────────────────────────────────────

# email -> order_id (để hook OTP lookup)
GMAIL94_ORDER_MAP  = {}  # type: Dict[str, str]
# order_id -> set of used OTPs (tránh tái sử dụng OTP giữa các biến thể)
GMAIL94_SEEN_OTPS  = {}  # type: Dict[str, Set[str]]


def custom_wait_for_otp(email_addr, after_ts, **kwargs):
    """Hook thay thế wait_for_otp của gpt_engine — dùng Gmail94 API."""
    order_id = GMAIL94_ORDER_MAP.get(email_addr)
    if not order_id:
        log("[OTP-Hook] Khong tim thay order_id cho: {}".format(email_addr), "ERR")
        return None

    # Lấy seen_otps chung cho cả order (shared giữa 4 biến thể)
    seen = GMAIL94_SEEN_OTPS.setdefault(order_id, set())

    log("[OTP-Hook] Poll OTP Gmail94 cho {} (order {}, da dung: {})...".format(
        email_addr, order_id, len(seen)), "INFO")
    return gmail94_read_otp(GMAIL94_TOKEN, order_id, timeout=180, interval=5, seen_otps=seen)


def _setup_gpt_engine():
    """(Deprecated) Removed gpt_engine hooks"""
    pass

def _register_single_email(email, order_id, thread_id, proxy_url, browser_type="chrome", headless=False, incognito=False, keep_open=False, direct_proxy=False, otp_received_event=None):
    # type: (str, str, int, Optional[str], str, bool, bool, bool, ...) -> bool
    """Đăng ký 1 tài khoản ChatGPT bằng standalone playwright."""
    GMAIL94_ORDER_MAP[email] = order_id
    try:
        password = getattr(sys.modules[__name__], "GPT_PASSWORD", "chatgpt123@@")
        res = run_selenium_registration_standalone(
            email=email,
            password=password,
            proxy=proxy_url,
            headless=headless,
            browser_type=browser_type,
            incognito=incognito, keep_open=keep_open, direct_proxy=direct_proxy,
            get_otp_callback=lambda e: custom_wait_for_otp(e, time.time()),
            save_account_callback=save_account,
            stop_event=GLOBAL_STOP_EVENT,
            otp_received_event=otp_received_event,
            thread_id=thread_id,
            batch_size=4
        )

        if res.get("success"):
            totp = res.get("totp_secret") or ""
            log("[Thread-{}] OK: {} | 2FA: {}".format(
                thread_id, email, "co" if totp else "khong"
            ), "OK")
            # Save account already handled by callback
            _save_done(email, order_id)
            return True
        else:
            err = res.get("error", "Unknown")
            log("[Thread-{}] FAIL: {} -- {}".format(thread_id, email, err), "ERR")
            return False

    except Exception as e:
        import traceback
        log("[Thread-{}] Exception: {} -- {}: {}".format(
            thread_id, email, type(e).__name__, e), "ERR")
        log(traceback.format_exc(), "ERR")
        return False
    finally:
        GMAIL94_ORDER_MAP.pop(email, None)


def register_one_purchase(thread_id, browser_type="chrome", headless=False, incognito=False, keep_open=False, direct_proxy=False, on_result=None, **kwargs):
    # type: (int, str, bool, bool, bool, callable, ...) -> Tuple[int, int]
    """
    Mua 1 Gmail từ Gmail94 → tạo 4 biến thể email → đăng ký 4 tài khoản ChatGPT.

    Trả về tuple (so_thanh_cong, so_that_bai) — tối đa (4, 0).
    """
    token = GMAIL94_TOKEN
    if not token:
        log("[Thread-{}] Chua cau hinh Gmail94 Token!".format(thread_id), "ERR")
        if on_result: on_result(False)
        return (0, 1)

    # Bước 1: Mua Gmail
    log("[Thread-{}] [Gmail94] Dang mua Gmail...".format(thread_id), "INFO")
    purchase = gmail94_buy(token)
    if not purchase:
        log("[Thread-{}] Khong mua duoc Gmail.".format(thread_id), "ERR")
        if on_result: on_result(False)
        return (0, 1)

    base_email = purchase["email"]
    order_id   = purchase["order_id"]
    variants   = expand_gmail_variants(base_email)

    log("[Thread-{}] Gmail: {} → {} bien the: {}".format(
        thread_id, base_email, len(variants), ", ".join(variants)), "INFO")

    proxy_url = _format_proxy(get_rotated_proxy())
    ok = 0
    fail = 0

    import threading

    # Bước 3: Đăng ký tuần tự 4 biến thể
    threads = []
    
    def _run_variant(email, idx):
        nonlocal ok, fail
        # Tạo event để báo hiệu đã nhập xong OTP
        otp_event = threading.Event()
        
        def _thread_worker():
            nonlocal ok, fail
            s = _register_single_email(
                email, order_id, (thread_id - 1) * 4 + idx + 1, proxy_url, 
                browser_type, headless, incognito, 
                keep_open=keep_open, direct_proxy=direct_proxy, otp_received_event=otp_event
            )
            if s: ok += 1
            else: fail += 1
            if on_result:
                on_result(s)
                
        t = threading.Thread(target=_thread_worker)
        threads.append(t)
        t.start()
        
        # Chờ tối đa 3 phút cho OTP. Nếu có OTP (hoặc lỗi), nó sẽ set()
        otp_event.wait(timeout=180)

    for i, variant_email in enumerate(variants):
        if GLOBAL_STOP_EVENT.is_set():
            log("[Thread-{}] Dừng do stop event".format(thread_id), "WARN")
            break
        log("[Thread-{}] [{}/{}] Dang ky: {}".format(
            thread_id, i + 1, len(variants), variant_email), "INFO")
            
        _run_variant(variant_email, i)

    # Chờ tất cả các luồng hoàn tất (2FA, lưu DB...)
    for t in threads:
        t.join()

    # Dọn dẹp seen_otps cho order này
    GMAIL94_SEEN_OTPS.pop(order_id, None)

    log("[Thread-{}] [Gmail94] Xong 1 Gmail ({} thanh cong / {} that bai)".format(
        thread_id, ok, fail), "OK" if ok > 0 else "WARN")
    return (ok, fail)


# ─── Backward-compat (single account) ────────────────────────────────────────

def register_one_account(thread_id, browser_type="chrome", headless=False, incognito=False, keep_open=False, direct_proxy=False, **kwargs):
    # type: (int, str, bool, bool) -> bool
    """
    Alias cũ — mua 1 Gmail và đăng ký cả 4 biến thể.
    Trả về True nếu ít nhất 1 thành công.
    """
    ok, fail = register_one_purchase(thread_id, browser_type, headless, incognito, keep_open=keep_open, direct_proxy=direct_proxy)
    return ok > 0
