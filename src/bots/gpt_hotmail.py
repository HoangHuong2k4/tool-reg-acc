#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT Hotmail Bot - Tích hợp gpt_engine (copy từ turb-gpt-free-register-main).

File hotmail đầu vào (data/hotmail-gpt.txt hoặc data/hotmails.txt):
  Format: email|password|refresh_token|client_id
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

# ─── File paths ───────────────────────────────────────────────────────────────
HOTMAIL_GPT_FILE = os.path.join(_DATA_DIR, "hotmail-gpt.txt")
HOTMAIL_OLD_FILE = os.path.join(_DATA_DIR, "hotmails.txt")
ONL_FILE         = os.path.join(_DATA_DIR, "onl.txt")

# ─── Queue & State ────────────────────────────────────────────────────────────
HOTMAIL_QUEUE = queue.Queue()   # type: queue.Queue
FILE_LOCK     = threading.Lock()
ACCOUNT_DATA  = {}              # type: Dict[str, dict]
CHECK_MOMO    = True

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
    """Chuyển dict proxy → URL string."""
    if not proxy_dict:
        return None
    host = proxy_dict.get("host", "")
    port = proxy_dict.get("port", "")
    user = proxy_dict.get("user", "")
    pw   = proxy_dict.get("pass", "")
    if user and pw:
        return "http://{}:{}@{}:{}".format(user, pw, host, port)
    return "http://{}:{}".format(host, port) if host else None


def _mark_used(original_line):
    # type: (str) -> None
    """Ghi email đã dùng vào onl.txt và xóa khỏi file nguồn."""
    with FILE_LOCK:
        try:
            with open(ONL_FILE, "a", encoding="utf-8") as f:
                f.write(original_line.strip() + "\n")

            for fpath in (HOTMAIL_GPT_FILE, HOTMAIL_OLD_FILE):
                if not os.path.exists(fpath):
                    continue
                with open(fpath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                stripped_target = original_line.strip()
                new_lines = [
                    l for l in lines
                    if l.strip() and l.strip() != stripped_target
                ]
                with open(fpath, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
        except Exception as e:
            log("Lỗi khi đánh dấu email đã dùng: {}".format(e), "WARN")


# ─── Queue Management ────────────────────────────────────────────────────────

def load_hotmails_to_queue(limit=999):
    # type: (int) -> None
    """
    Load email từ hotmail-gpt.txt (hoặc hotmails.txt nếu không có).
    Format: email|password|refresh_token|client_id (pipe)
    """
    # Xóa queue cũ
    while not HOTMAIL_QUEUE.empty():
        try:
            HOTMAIL_QUEUE.get_nowait()
        except queue.Empty:
            break
    ACCOUNT_DATA.clear()

    # Ưu tiên hotmail-gpt.txt, fallback sang hotmails.txt
    source_file = HOTMAIL_GPT_FILE if os.path.exists(HOTMAIL_GPT_FILE) else HOTMAIL_OLD_FILE
    if not os.path.exists(source_file):
        log("Không tìm thấy file hotmail: {}".format(source_file), "ERR")
        return

    count = 0
    with open(source_file, "r", encoding="utf-8") as f:
        for raw_line in f:
            if count >= limit:
                break
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                continue

            email         = parts[0]
            password      = parts[1]
            refresh_token = parts[2]
            client_id     = parts[3] if len(parts) >= 4 else "9e5f94bc-e8a4-4e73-b8be-63364c29d753"

            acc = {
                "email":         email,
                "password":      password,
                "client_id":     client_id,
                "refresh_token": refresh_token,
                "original_line": line,
            }
            HOTMAIL_QUEUE.put(acc)
            ACCOUNT_DATA[email] = acc
            count += 1

    log("Đã load {} hotmail vào hàng đợi từ {}.".format(count, os.path.basename(source_file)), "INFO")


def _inject_to_gpt_db(accounts):
    # type: (List[dict]) -> None
    """(Deprecated) Removed gpt_engine DB inject"""
    pass


# ─── Log Forwarding cho Web UI ──────────────────────────────────────────────
import logging

class WebUILogHandler(logging.Handler):
    def emit(self, record):
        # Bỏ qua các log rác của thư viện mạng
        if record.name.startswith("urllib3") or record.name.startswith("requests") or record.name.startswith("selenium") or record.name.startswith("WDM"):
            return
            
        level_map = {
            logging.DEBUG: "INFO",
            logging.INFO: "INFO",
            logging.WARNING: "WARN",
            logging.ERROR: "ERR",
            logging.CRITICAL: "ERR",
        }
        lvl = level_map.get(record.levelno, "INFO")
        
        # Lấy tên module để làm prefix
        prefix = record.name.split('.')[-1]
        msg = f"[{prefix}] {record.getMessage()}"
        
        # Gọi thẳng log() của gpt_hotmail (sẽ được UI ghi đè)
        import sys
        print(f"WEBUI HANDLER RECEIVED: {msg}", file=sys.stderr)
        log(msg, lvl)

_web_ui_handler = WebUILogHandler()
_web_ui_handler.setLevel(logging.INFO)
logging.getLogger("").addHandler(_web_ui_handler)

# ─── Registration ─────────────────────────────────────────────────────────────

GLOBAL_HOTMAIL_ACCOUNTS = {}
GLOBAL_STOP_EVENT = threading.Event()
SEEN_OTPS = {}

def get_otp_callback_hotmail(email_addr, after_ts=0, mail_api_source="dongvanfb"):
    if email_addr not in ACCOUNT_DATA:
        return None
        
    log(f"[OTP-Hook] Đang lấy mã OTP cho {email_addr} từ API {mail_api_source.upper()} (với logic OpenAI)...", "INFO")
    
    def wait_for_otp(email, password, refresh_token, client_id, timeout=120, interval=4, mail_api_source="dongvanfb"):
        import requests, time, re
        
        api_url = "https://tools.dongvanfb.net/api/get_messages_oauth2" if mail_api_source == "dongvanfb" else "https://mixmmo.com/api/get-hotmail-messages.php"
        
        if mail_api_source == "dongvanfb":
            headers = {"Content-Type": "application/json"}
            payload = {
                "email": email,
                "pass": password,
                "refresh_token": refresh_token,
                "client_id": client_id
            }
        else:
            headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
            payload = {
                "action": "get_hotmail_messages",
                "account": f"{email}|{password}|{refresh_token}|{client_id}",
                "mode": "oauth",
                "folder": "inbox",
                "start_timestamp": "0"
            }
        
        seen_otps = SEEN_OTPS.setdefault(email, set())
        elapsed = 0
        while elapsed < timeout:
            try:
                resp = requests.post(api_url, headers=headers, data=payload if mail_api_source != "dongvanfb" else None, json=payload if mail_api_source == "dongvanfb" else None, timeout=20)
                data = resp.json()
                
                messages = []
                if mail_api_source == "dongvanfb" and data.get("status"):
                    messages = data.get("messages", [])
                elif mail_api_source == "mixmmo" and data.get("success"):
                    messages = data.get("data", [])
                    
                for msg in messages:
                    subject = msg.get("subject", "")
                    message = msg.get("message", "") if mail_api_source == "dongvanfb" else msg.get("body", "")
                    
                    clean_message = re.sub(r'<style[^>]*>.*?</style>', ' ', message, flags=re.IGNORECASE)
                    clean_message = re.sub(r'<[^>]+>', ' ', clean_message)
                    text_to_search = subject + " " + clean_message
                    otp = None
                    if "openai" in text_to_search.lower() or "chatgpt" in text_to_search.lower():
                        match = re.search(r'\b(\d{6})\b', text_to_search)
                        if match:
                            otp = match.group(1)
                    
                    if otp and otp not in seen_otps:
                        seen_otps.add(otp)
                        log(f"Nhận được OTP ({mail_api_source.upper()}): {otp}", "OK")
                        return otp
            except Exception as e:
                log(f"Lỗi gọi API {mail_api_source.upper()}: {e}", "WARN")
                
            time.sleep(interval)
            elapsed += interval
        
        log(f"Hết thời gian chờ OTP {mail_api_source.upper()}!", "ERR")
        return None
    
    acc = ACCOUNT_DATA[email_addr]
    return wait_for_otp(
        email=acc["email"],
        password=acc["password"],
        refresh_token=acc["refresh_token"],
        client_id=acc["client_id"],
        timeout=180,
        interval=4,
        mail_api_source=mail_api_source
    )

def register_one_account(thread_id, batch_size=1, browser_type="chrome", headless=False, incognito=False, max_retries=2, mail_api_source="dongvanfb", keep_open=False, direct_proxy=False):
    # type: (int, str, bool, bool, int, str) -> bool
    """
    Lấy một email từ queue, chạy đăng ký ChatGPT bằng standalone Selenium,
    lưu kết quả và đánh dấu email đã dùng.
    Hỗ trợ retry khi lỗi OTP và dừng giữa chừng qua GLOBAL_STOP_EVENT.
    """
    if HOTMAIL_QUEUE.empty():
        return False

    acc   = HOTMAIL_QUEUE.get()
    email = acc["email"]
    GLOBAL_HOTMAIL_ACCOUNTS[email] = acc
    log("[Thread-{}] Bắt đầu đăng ký GPT: {}".format(thread_id, email), "INFO")

    proxy_url = _format_proxy(get_rotated_proxy())

    try:
        for attempt in range(1, max_retries + 1):
            if GLOBAL_STOP_EVENT.is_set():
                log(f"[Thread-{thread_id}] Dừng do stop event", "WARN")
                return False

            if attempt > 1:
                log(f"[Thread-{thread_id}] Thử lại lần {attempt}/{max_retries}: {email}", "INFO")
                time.sleep(5)
            
            # Dùng mật khẩu từ settings (mặc định chatgpt123@@) để đồng nhất
            gpt_password = getattr(sys.modules[__name__], "GPT_PASSWORD", "chatgpt123@@")
            res = run_selenium_registration_standalone(
                email=email,
                password=gpt_password,
                proxy=proxy_url,
                headless=headless,
                browser_type=browser_type,
                incognito=incognito, keep_open=keep_open, direct_proxy=direct_proxy,
                get_otp_callback=lambda e: get_otp_callback_hotmail(e, time.time(), mail_api_source),
                save_account_callback=save_account,
                thread_id=thread_id, batch_size=batch_size,
                stop_event=GLOBAL_STOP_EVENT
            )

            if res.get("success"):
                totp = res.get("totp_secret") or ""
                log("[Thread-{}] ✅ Thành công: {} | 2FA: {}".format(
                    thread_id, email, "có" if totp else "không"), "OK")
                # Save account callback already called inside
                _mark_used(acc["original_line"])
                return True

            err = res.get("error", "Unknown")
            # Retry nếu lỗi liên quan OTP timeout, không retry lỗi khác
            if "OTP" in err and attempt < max_retries:
                log(f"[Thread-{thread_id}] ⚠️ Lỗi OTP, sẽ thử lại: {err}", "WARN")
                continue

            log("[Thread-{}] ❌ Thất bại: {} — {}".format(thread_id, email, err), "ERR")
            return False

        return False

    except Exception as e:
        import traceback
        log("[Thread-{}] ❌ Exception: {} — {}: {}".format(
            thread_id, email, type(e).__name__, e), "ERR")
        log(traceback.format_exc(), "ERR")
        return False
    finally:
        GLOBAL_HOTMAIL_ACCOUNTS.pop(email, None)
        try:
            HOTMAIL_QUEUE.task_done()
        except ValueError:
            pass

