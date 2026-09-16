#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT OTPGmail Bot - Đăng ký ChatGPT dùng mail mua từ otpgmail.net API.

Workflow:
1. Mua 1 email mới từ OTPGmail (hỗ trợ cả gmail và icloud)
2. Selenium/Playwright tự động đăng ký 1 acc với email đó.
3. Liên tục lấy mã OTP qua API.
4. Lưu tài khoản.

API OTPGmail:
  - Mua mail:  POST https://otpgmail.net/v1/orders
  - Đọc OTP:   GET  https://otpgmail.net/v1/orders/{orderId}
"""

import os
import sys
import json
import uuid
import queue
import threading
import time
import requests
import logging
from datetime import datetime
from typing import Optional, Dict, Set, Tuple, Any

# ─── Paths ───────────────────────────────────────────────────────────────────
_BOT_DIR        = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR       = os.path.abspath(os.path.join(_BOT_DIR, "..", ".."))
_DATA_DIR       = os.path.join(_ROOT_DIR, "data")
from src.bots.gpt_selenium_utils import run_selenium_registration_standalone

# ─── File paths ───────────────────────────────────────────────────────────────
ONL_FILE = os.path.join(_DATA_DIR, "otpgmail-gpt-done.txt")

# ─── State ────────────────────────────────────────────────────────────────────
FILE_LOCK     = threading.Lock()
TASK_QUEUE    = queue.Queue()
CHECK_MOMO    = True
OTPGMAIL_TOKEN = ""   # Được set bởi app.py từ Settings DB
OTPGMAIL_PASSWORD = "" # Mật khẩu ảo được set bởi app.py
OTPGMAIL_DOMAIN = "gmail.com" # "gmail.com" hoặc "icloud.com"
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
    # type: (str, str, str, bool, bool) -> None
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


def _save_done(email, order_id):
    # type: (str, str) -> None
    with FILE_LOCK:
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            with open(ONL_FILE, "a", encoding="utf-8") as f:
                f.write("{}|{}\n".format(email, order_id))
        except Exception as e:
            log("Loi ghi done file: {}".format(e), "WARN")


# ─── OTPGmail API ─────────────────────────────────────────────────────────────

def otpgmail_buy(token, domain="gmail.com"):
    # type: (str, str) -> Optional[Dict]
    """
    Mua 1 mail mới từ OTPGmail cho service chatgpt (dr).
    Trả về dict {"email": ..., "order_id": ...} hoặc None nếu lỗi.
    """
    url = "https://otpgmail.net/v1/orders"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4())
    }
    payload = {
        "service": "dr",
        "quantity": 1,
        "domain": domain
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        raw = resp.text.strip() if resp.text else ""

        if not raw:
            log("OTPGmail mua loi: Response rong (HTTP {})".format(resp.status_code), "ERR")
            return None

        try:
            data = resp.json()
        except Exception:
            log("OTPGmail mua loi: Response khong phai JSON (HTTP {}): {}".format(
                resp.status_code, raw[:300]), "ERR")
            return None

        if data.get("success") and "data" in data and len(data["data"]) > 0:
            email = data["data"][0].get("email")
            order_id = data["data"][0].get("orderId", "")
            log("OTPGmail mua thanh cong: {} (order: {})".format(email, order_id), "OK")
            return {"email": email, "order_id": str(order_id)}
        else:
            err = ""
            if "error" in data:
                err = f"{data['error'].get('code')}: {data['error'].get('message')}"
            else:
                err = str(data)
            log("OTPGmail mua that bai: {}".format(err), "ERR")
            return None
    except requests.exceptions.Timeout:
        log("OTPGmail mua loi: Timeout (30s)", "ERR")
        return None
    except Exception as e:
        log("OTPGmail mua loi exception: {}".format(e), "ERR")
        return None


def otpgmail_read_otp(token, order_id, timeout=120, interval=5, seen_otps=None):
    # type: (str, str, int, int, Optional[Set]) -> Optional[str]
    """
    Polling đọc OTP từ OTPGmail cho order_id.
    - seen_otps: set các OTP đã dùng — tránh lấy lại mã cũ.
    """
    if seen_otps is None:
        seen_otps = set()
    url = f"https://otpgmail.net/v1/orders/{order_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    elapsed = 0
    while elapsed < timeout:
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            raw = resp.text.strip() if resp.text else ""
            if not raw:
                log("OTPGmail OTP: Response rong ({}/{}s)".format(elapsed, timeout), "INFO")
            else:
                try:
                    data = resp.json()
                    if data.get("success") and "data" in data:
                        otp_list = data["data"].get("otp", [])
                        if otp_list:
                            latest_otp = otp_list[-1].get("code")
                            if latest_otp and latest_otp not in seen_otps:
                                log("OTPGmail OTP nhan duoc: {}".format(latest_otp), "OK")
                                return latest_otp
                        
                        status = data["data"].get("status")
                        if status == "cancelled":
                            log(f"OTPGmail OTP: Đơn {order_id} đã bị hủy.", "ERR")
                            return None
                        elif status == "waiting_code":
                            log("OTPGmail OTP cho ({}/{}s): Chua co ma".format(elapsed, timeout), "INFO")
                    else:
                        err = data.get("error", {}).get("message", str(data))
                        log("OTPGmail OTP chua co ma: {}".format(err), "INFO")
                except Exception:
                    log("OTPGmail OTP: Response khong phai JSON: {}".format(raw[:200]), "WARN")
        except requests.exceptions.Timeout:
            log("OTPGmail OTP read timeout, retrying...", "WARN")
        except Exception as e:
            log("OTPGmail OTP read exception: {}".format(e), "WARN")

        time.sleep(interval)
        elapsed += interval

    log("OTPGmail: Het thoi gian cho OTP ({}s)".format(timeout), "ERR")
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

def _setup_gpt_engine():
    """(Deprecated) Removed gpt_engine hooks"""
    pass

def _register_single_email(email, order_id, thread_id, proxy_url, browser_type="chrome", headless=False, incognito=False, keep_open=False, direct_proxy=False, otp_received_event=None, seen_otps=None):
    # type: (str, str, int, Optional[str], str, bool, bool, bool, bool, Any, Set) -> bool
    """Đăng ký 1 tài khoản ChatGPT bằng standalone playwright."""
    if seen_otps is None:
        seen_otps = set()
    try:
        password = getattr(sys.modules[__name__], "OTPGMAIL_PASSWORD", "chatgpt123@@")

        def custom_wait_for_otp(email_addr, after_ts, **kwargs):
            log("[OTP-Hook] Poll OTP OTPGmail cho {} (order {}, da dung: {})...".format(
                email_addr, order_id, len(seen_otps)), "INFO")
            code = otpgmail_read_otp(OTPGMAIL_TOKEN, order_id, timeout=60, interval=5, seen_otps=seen_otps)
            if code:
                seen_otps.add(code)
            return code

        res = run_selenium_registration_standalone(
            email=email,
            password=password,
            proxy=proxy_url,
            headless=headless,
            browser_type=browser_type,
            incognito=incognito, keep_open=keep_open, direct_proxy=direct_proxy,
            get_otp_callback=custom_wait_for_otp,
            save_account_callback=save_account,
            stop_event=GLOBAL_STOP_EVENT,
            otp_received_event=otp_received_event,
            thread_id=thread_id,
            batch_size=1
        )

        if res.get("success"):
            totp = res.get("totp_secret") or ""
            log("[Thread-{}] OK: {} | 2FA: {}".format(
                thread_id, email, "co" if totp else "khong"
            ), "OK")
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


def register_one_purchase(thread_id, browser_type="chrome", headless=False, incognito=False, keep_open=False, direct_proxy=False, on_result=None, **kwargs):
    # type: (int, str, bool, bool, bool, callable, ...) -> Tuple[int, int]
    """
    1 lượt chạy: Mua 1 mail từ OTPGmail, sau đó đăng ký 1 ChatGPT.

    Trả về tuple (so_thanh_cong, so_that_bai) — tối đa (1, 0).
    """
    global OTPGMAIL_TOKEN, OTPGMAIL_PASSWORD, OTPGMAIL_DOMAIN
    token = OTPGMAIL_TOKEN
    if not token:
        log("[Thread-{}] Chua cau hinh OTPGmail Token!".format(thread_id), "ERR")
        if on_result: on_result(False)
        return (0, 1)

    log("[Thread-{}] [OTPGmail] Dang mua mail ({}) ...".format(thread_id, OTPGMAIL_DOMAIN), "INFO")
    purchase = None
    _buy_attempt = 0
    _BUY_RETRY_DELAY = 15  

    while not GLOBAL_STOP_EVENT.is_set():
        _buy_attempt += 1
        purchase = otpgmail_buy(token, domain=OTPGMAIL_DOMAIN)
        if purchase:
            break  
        log("[Thread-{}] [OTPGmail] Chua mua duoc mail (lan {}), thu lai sau {}s...".format(
                thread_id, _buy_attempt, _BUY_RETRY_DELAY
            ), "WARN")
        GLOBAL_STOP_EVENT.wait(timeout=_BUY_RETRY_DELAY)

    if not purchase:
        log("[Thread-{}] [OTPGmail] Dung do stop event, khong mua duoc mail.".format(thread_id), "ERR")
        if on_result: on_result(False)
        return (0, 1)

    base_email = purchase["email"]
    order_id   = purchase["order_id"]

    log("[Thread-{}] Bat dau dang ky cho mail: {} (order: {})".format(
        thread_id, base_email, order_id), "INFO")

    proxy_url = _format_proxy(get_rotated_proxy())
    
    import threading
    otp_event = threading.Event()
    seen_otps = set()
    
    success = _register_single_email(
        base_email, order_id, thread_id, proxy_url, 
        browser_type, headless, incognito, 
        keep_open=keep_open, direct_proxy=direct_proxy, 
        otp_received_event=otp_event, seen_otps=seen_otps
    )

    if success:
        log("[Thread-{}] [OTPGmail] Xong 1 mail (1 thanh cong / 0 that bai)".format(thread_id), "OK")
        if on_result: on_result(True)
        return (1, 0)
    else:
        log("[Thread-{}] [OTPGmail] Xong 1 mail (0 thanh cong / 1 that bai)".format(thread_id), "WARN")
        if on_result: on_result(False)
        return (0, 1)



# ─── Backward-compat (single account) ────────────────────────────────────────

def register_one_account(thread_id, browser_type="chrome", headless=False, incognito=False, keep_open=False, direct_proxy=False, **kwargs):
    # type: (int, str, bool, bool) -> bool
    """
    Alias cũ — mua 1 Gmail và đăng ký cả 4 biến thể.
    Trả về True nếu ít nhất 1 thành công.
    """
    ok, fail = register_one_purchase(thread_id, browser_type, headless, incognito, keep_open=keep_open, direct_proxy=direct_proxy)
    return ok > 0
