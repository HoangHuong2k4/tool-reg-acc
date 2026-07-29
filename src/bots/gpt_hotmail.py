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

# Thêm src/ và gpt_engine vào sys.path để config và core có thể được import đúng cách
_SRC_DIR = os.path.abspath(os.path.join(_BOT_DIR, ".."))
_GPT_ENGINE_DIR = os.path.join(_SRC_DIR, "gpt_engine")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
if _GPT_ENGINE_DIR not in sys.path:
    sys.path.insert(0, _GPT_ENGINE_DIR)

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

def save_account(email, password, totp_secret, has_momo=False):
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
    """Inject email vào DB nội bộ của gpt_engine."""
    try:
        from gpt_engine.core.db import import_outlook_accounts
        records = [
            {
                "email":         a["email"],
                "password":      a["password"],
                "client_id":     a["client_id"],
                "refresh_token": a["refresh_token"],
            }
            for a in accounts
        ]
        inserted, skipped = import_outlook_accounts(records)
        log("Đã inject {} email vào DB (bỏ qua {} trùng)".format(inserted, skipped), "INFO")
    except Exception as e:
        log("Lỗi inject email vào DB: {}".format(e), "WARN")


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
SEEN_OTPS = {}

def custom_wait_for_otp(email_addr, after_ts, **kwargs):
    acc = GLOBAL_HOTMAIL_ACCOUNTS.get(email_addr)
    if not acc:
        log(f"[OTP-Hook] Không tìm thấy thông tin tài khoản cho {email_addr}", "ERR")
        return None
        
    log(f"[OTP-Hook] Đang lấy mã OTP cho {email_addr} từ API DongVanFB (với logic OpenAI)...", "INFO")
    
    def mixmmo_wait(email, password, refresh_token, client_id, timeout=120, interval=4, after_ts=0):
        import requests, time, re
        headers = {"Content-Type": "application/json"}
        payload = {
            "email": email,
            "pass": password,
            "refresh_token": refresh_token,
            "client_id": client_id
        }
        
        seen_otps = SEEN_OTPS.setdefault(email, set())
        
        elapsed = 0
        while elapsed < timeout:
            try:
                resp = requests.post("https://tools.dongvanfb.net/api/get_messages_oauth2", headers=headers, json=payload, timeout=20)
                data = resp.json()
                
                if data.get("status"):
                    messages = data.get("messages")
                    
                    if messages:
                        for msg in messages:
                            subject = msg.get("subject", "")
                            message = msg.get("message", "")
                            
                            # Sử dụng logic của gpt_engine để trích xuất OTP chính xác nhất (tránh lấy nhầm 6 số khác)
                            from gpt_engine.core.otp_utils import extract_otp
                            
                            # Giả lập format tin nhắn để truyền vào hàm extract_otp
                            simulated_email_dict = {
                                "subject": subject,
                                "text": message,
                                "content": message
                            }
                            otp = extract_otp(simulated_email_dict)
                            
                            if not otp:
                                # Fallback regex nếu hàm trên không lấy được
                                clean_message = re.sub(r'<style[^>]*>.*?</style>', ' ', message, flags=re.IGNORECASE)
                                clean_message = re.sub(r'<[^>]+>', ' ', clean_message)
                                text_to_search = subject + " " + clean_message
                                # Tìm "code is XXXXXX" hoặc các pattern tương tự
                                if "openai" in text_to_search.lower() or "chatgpt" in text_to_search.lower():
                                    match = re.search(r'\b(\d{6})\b', text_to_search)
                                    if match:
                                        otp = match.group(1)
                            
                            if otp and otp not in seen_otps:
                                seen_otps.add(otp)
                                log(f"Nhận được OTP DongVanFB: {otp}", "OK")
                                return otp
            except Exception as e:
                log(f"Lỗi gọi API DongVanFB: {e}", "WARN")
                
            time.sleep(interval)
            elapsed += interval
        
        log("Hết thời gian chờ OTP DongVanFB!", "ERR")
        return None
    
    return mixmmo_wait(
        email=acc["email"],
        password=acc["password"],
        refresh_token=acc["refresh_token"],
        client_id=acc["client_id"],
        timeout=180,
        interval=4,
        after_ts=after_ts
    )

def register_one_account(thread_id):
    # type: (int) -> bool
    """
    Lấy một email từ queue, inject vào DB gpt_engine, chạy đăng ký ChatGPT,
    lưu kết quả và đánh dấu email đã dùng.
    """
    if HOTMAIL_QUEUE.empty():
        return False

    acc   = HOTMAIL_QUEUE.get()
    email = acc["email"]
    GLOBAL_HOTMAIL_ACCOUNTS[email] = acc
    log("[Thread-{}] Bắt đầu đăng ký GPT: {}".format(thread_id, email), "INFO")

    # Inject email vào DB của gpt_engine
    _inject_to_gpt_db([acc])

    proxy_url = _format_proxy(get_rotated_proxy())

    try:
        from gpt_engine.main import run_registration, configure_logging
        import gpt_engine.config.email as _email_cfg

        # Khởi tạo hook wait_for_otp của gpt_engine để sử dụng API dongvanfb
        from gpt_engine.core import email_provider
        import gpt_engine.main as gem
        
        gem_logger = logging.getLogger("gpt_engine")
        if _web_ui_handler not in gem_logger.handlers:
            gem_logger.addHandler(_web_ui_handler)
            gem_logger.setLevel(logging.INFO)
            gem_logger.propagate = False

        # Thiết lập trực tiếp trên module được import trong main
        import gpt_engine.config.twofa as _twofa_cfg
        gem._email_cfg.USE_EMAIL_SERVICE = True
        _email_cfg.USE_EMAIL_SERVICE = True
        gem._twofa_cfg.ENABLE_2FA = True
        _twofa_cfg.ENABLE_2FA = True


        email_provider.wait_for_otp = custom_wait_for_otp
        gem.wait_for_otp = custom_wait_for_otp
        try:
            import core.email_provider as core_ep  # type: ignore
            core_ep.wait_for_otp = custom_wait_for_otp
        except Exception:
            pass

        from gpt_engine.main import run_registration, configure_logging, generate_display_name
        configure_logging(verbose=False)
        result = run_registration(
            email=email,
            name=generate_display_name(),
            proxy=proxy_url,
            batch_dir=None,
            check_momo=CHECK_MOMO,
        )

        if result and result.get("success"):
            totp = result.get("totp_secret") or ""
            has_momo = result.get("has_momo", False)
            momo_display = str(has_momo) if isinstance(has_momo, str) else ("có" if has_momo else "không")
            log("[Thread-{}] ✅ Thành công: {} | 2FA: {} | MoMo: {}".format(
                thread_id, email, "có" if totp else "không", momo_display), "OK")
            save_account(email, acc["password"], totp, has_momo)
            _mark_used(acc["original_line"])
            return True
        else:
            err = result.get("error", "Unknown") if result else "No result"
            log("[Thread-{}] ❌ Thất bại: {} — {}".format(thread_id, email, err), "ERR")
            return False

    except Exception as e:
        import traceback
        log("[Thread-{}] ❌ Exception: {} — {}: {}".format(
            thread_id, email, type(e).__name__, e), "ERR")
        log(traceback.format_exc(), "ERR")
        return False
