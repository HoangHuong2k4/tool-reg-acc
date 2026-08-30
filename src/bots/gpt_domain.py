#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT Domain Bot - Tích hợp gpt_engine lấy mail ảo từ regmail.phh.info.vn
"""

import os
import sys
import queue
import threading
import time
import re
import requests
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# ─── Paths ───────────────────────────────────────────────────────────────────
_BOT_DIR   = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR  = os.path.abspath(os.path.join(_BOT_DIR, "..", ".."))
_DATA_DIR  = os.path.join(_ROOT_DIR, "data")

from src.bots.gpt_selenium_utils import run_selenium_registration_standalone

# ─── Queue & State ────────────────────────────────────────────────────────────
HOTMAIL_QUEUE = queue.Queue()   # type: queue.Queue
FILE_LOCK     = threading.Lock()
ACCOUNT_DATA  = {}              # type: Dict[str, dict]
CHECK_MOMO    = True
GLOBAL_STOP_EVENT = threading.Event()

# ─── Patchable hooks (bị app.py override) ─────────────────────────────────────
def log(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    print("[{}] [{}] {}".format(now, level, msg))

def get_rotated_proxy():
    return None

def save_account(email, password, totp_secret, has_momo=False, has_uudai=False):
    pass

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _format_proxy(proxy_dict):
    if not proxy_dict:
        return None
    host = proxy_dict.get("host", "")
    port = proxy_dict.get("port", "")
    user = proxy_dict.get("user", "")
    pw   = proxy_dict.get("pass", "")
    if user and pw:
        return "http://{}:{}@{}:{}".format(user, pw, host, port)
    return "http://{}:{}".format(host, port) if host else None

# ─── Domain Mail API ─────────────────────────────────────────────────────────
BASE_URL    = "https://regmail.phh.info.vn"
API_KEY     = "1dec9d51e8707e9bf1fa7756612830c676f65a42a1009851580ec0a82384abd8"

API_HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def create_random_email():
    try:
        resp = requests.post(f"{BASE_URL}/api/emails/create", headers=API_HEADERS, proxies={"http": None, "https": None}, timeout=10)
        data = resp.json()
        if data.get("success") and data.get("email"):
            log(f"Đã tạo email: {data['email']}", "OK")
            return data["email"]
        log(f"Không tạo được email: {data}", "WARN")
    except Exception as e:
        log(f"Lỗi gọi API tạo email: {e}", "ERR")
    return None

# Override OTP Wait in email_provider
def get_latest_otp(email_address):
    """
    Lấy OTP mới nhất từ API domain mail.
    
    API response format:
    {
        "success": true,
        "emails": [
            {
                "id": 78452,
                "from_email": "noreply@tm.openai.com",
                "subject": "Your temporary ChatGPT verification code",
                "text": "... 359976 ...",
                "otp": "359976",
                "received_at": "2026-08-30T06:10:36.000Z"
            }
        ]
    }
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/api/emails/latest",
            headers=API_HEADERS,
            params={"email": email_address},
            proxies={"http": None, "https": None},
            timeout=15
        )
        data = resp.json()
        
        if not data.get("success"):
            return None
        
        # Format mới: data["emails"] là array
        emails = data.get("emails", [])
        if emails:
            for email_obj in emails:
                # Ưu tiên field "otp" trực tiếp
                otp = email_obj.get("otp")
                if otp:
                    otp = str(otp).strip()
                    if re.match(r'^\d{6}$', otp):
                        return otp
                
                # Fallback: tìm 6 số trong text body
                text = email_obj.get("text", "")
                subject = email_obj.get("subject", "")
                from_email = email_obj.get("from_email", "")
                
                # Chỉ xử lý email từ OpenAI/ChatGPT
                if "openai" in from_email.lower() or "chatgpt" in subject.lower() or "openai" in subject.lower():
                    match = re.search(r'\b(\d{6})\b', text)
                    if match:
                        return match.group(1)
        
        # Format cũ fallback: data["email"] là object
        email_obj = data.get("email")
        if email_obj:
            otp = email_obj.get("otp")
            if otp:
                otp = str(otp).strip()
                if re.match(r'^\d{6}$', otp):
                    return otp
            body = email_obj.get("body", "") or email_obj.get("text", "")
            match = re.search(r'\b(\d{6})\b', body)
            if match:
                return match.group(1)
                
    except Exception as e:
        log(f"Lỗi gọi API lấy OTP: {e}", "WARN")
    return None

def wait_for_otp_domain(email_address, start_time, max_wait=60):
    log(f"Đang chờ OTP cho {email_address}...", "INFO")
    t0 = time.time()
    while time.time() - t0 < max_wait:
        if getattr(GLOBAL_STOP_EVENT, 'is_set', lambda: False)():
            return None
        otp = get_latest_otp(email_address)
        if otp:
            log(f"Đã nhận OTP: {otp}", "OK")
            return otp
        time.sleep(3)
    log("Hết thời gian chờ OTP", "WARN")
    return None

def load_hotmails_to_queue(limit=1):
    while not HOTMAIL_QUEUE.empty():
        try: HOTMAIL_QUEUE.get_nowait()
        except queue.Empty: break
    ACCOUNT_DATA.clear()
    
    for _ in range(limit):
        email = create_random_email()
        if not email:
            continue
        acc = {
            "email": email,
            "password": getattr(sys.modules[__name__], "GPT_PASSWORD", "chatgpt123@@"),
            "client_id": "",
            "refresh_token": ""
        }
        HOTMAIL_QUEUE.put(acc)
        ACCOUNT_DATA[email] = acc

def register_one_account(thread_id, batch_size=1, browser_type="chrome", headless=False, incognito=False, max_retries=2, keep_open=False, direct_proxy=False, **kwargs):
    if HOTMAIL_QUEUE.empty():
        return False
        
    try:
        acc = HOTMAIL_QUEUE.get_nowait()
    except queue.Empty:
        return False

    email = acc["email"]
    password = acc["password"]
    log(f"[Thread-{thread_id}] Bắt đầu đăng ký GPT: {email}", "INFO")

    proxy_dict = get_rotated_proxy()
    proxy_str = _format_proxy(proxy_dict)
    
    try:
        for attempt in range(1, max_retries + 1):
            if GLOBAL_STOP_EVENT.is_set():
                log(f"[Thread-{thread_id}] Dừng do stop event", "WARN")
                return False

            if attempt > 1:
                log(f"[Thread-{thread_id}] Thử lại lần {attempt}/{max_retries}: {email}", "INFO")
                time.sleep(5)

            res = run_selenium_registration_standalone(
                email=email,
                password=password,
                proxy=proxy_str,
                headless=headless,
                browser_type=browser_type,
                incognito=incognito, keep_open=keep_open, direct_proxy=direct_proxy,
                get_otp_callback=lambda e: wait_for_otp_domain(e, time.time(), max_wait=120),
                save_account_callback=save_account,
                thread_id=thread_id, batch_size=batch_size,
                stop_event=GLOBAL_STOP_EVENT
            )

            if res.get("success"):
                totp = res.get("totp_secret") or ""
                log(f"[Thread-{thread_id}] ✅ Thành công: {email} | 2FA: {'có' if totp else 'không'}", "OK")
                return True

            err = res.get("error", "Unknown")
            # Retry nếu lỗi liên quan OTP timeout, không retry lỗi khác
            if "OTP" in err and attempt < max_retries:
                log(f"[Thread-{thread_id}] ⚠️ Lỗi OTP, sẽ thử lại: {err}", "WARN")
                continue

            log(f"[Thread-{thread_id}] ❌ Thất bại: {email} — {err}", "ERR")
            return False

        return False

    except Exception as e:
        log(f"[Thread-{thread_id}] Lỗi worker: {e}", "ERR")
        return False
    finally:
        HOTMAIL_QUEUE.task_done()
