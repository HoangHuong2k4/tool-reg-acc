#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import re
import sys
import os
import json
import shutil
import uuid
from pathlib import Path
import requests
import random
import socket
import select
import base64
import threading as _threading
from datetime import datetime

# LocalProxyRelay - TCP relay để forward proxy auth (không cần incognito)

import subprocess

from .browser_utils import LocalProxyRelay


MAC_WIFI_SERVICE = None  # sẽ tự detect khi chạy

def _get_active_network_service():
    """Tìm tên network service đang active trên Mac"""
    try:
        out = subprocess.check_output(["networksetup", "-listallnetworkservices"], text=True)
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("*") or not line:
                continue
            # Kiểm tra có IP không
            try:
                info = subprocess.check_output(
                    ["networksetup", "-getinfo", line],
                    text=True, stderr=subprocess.DEVNULL
                )
                if "IP address:" in info and "none" not in info.lower().split("IP address:")[1].split("\n")[0]:
                    return line
            except:
                pass
    except:
        pass
    return "Wi-Fi"  # fallback

def mac_set_system_proxy(host, port, user, password):
    """Set HTTP+HTTPS proxy toàn hệ thống trên Mac"""
    global MAC_WIFI_SERVICE
    if MAC_WIFI_SERVICE is None:
        MAC_WIFI_SERVICE = _get_active_network_service()
    svc = MAC_WIFI_SERVICE
    try:
        subprocess.run(["networksetup", "-setwebproxy", svc, str(host), str(port), "on", str(user), str(password)],
                      check=True, capture_output=True)
        subprocess.run(["networksetup", "-setsecurewebproxy", svc, str(host), str(port), "on", str(user), str(password)],
                      check=True, capture_output=True)
        log(f"[SysProxy] Đã set system proxy: {host}:{port} (WiFi: {svc})", "OK")
        return True
    except Exception as e:
        log(f"[SysProxy] Không set được system proxy: {e}", "WARN")
        return False

def mac_clear_system_proxy():
    """Tắt system proxy sau khi xong"""
    global MAC_WIFI_SERVICE
    svc = MAC_WIFI_SERVICE or "Wi-Fi"
    try:
        subprocess.run(["networksetup", "-setwebproxystate", svc, "off"], capture_output=True)
        subprocess.run(["networksetup", "-setsecurewebproxystate", svc, "off"], capture_output=True)
        log("[SysProxy] Đã tắt system proxy", "OK")
    except Exception as e:
        log(f"[SysProxy] Không tắt được system proxy: {e}", "WARN")


# ── Cấu hình ────────────────────────────────────────────────────────
HOTMAIL_API_URL = 'https://tools.dongvanfb.net/api/get_messages_oauth2'
HOTMAIL_FILE = "data/hotmails.txt"

CAPCUT_URL  = "https://www.capcut.com/vi-vn/signup"
OUTPUT_FILE = "data/accounts.txt"
DOB_YEAR  = "2004"
DOB_MONTH = "12"
DOB_DAY   = "12"


import queue
import threading
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait, FIRST_COMPLETED
HOTMAIL_QUEUE = queue.Queue()
FILE_LOCK = threading.Lock()
ACCOUNTS_LOCK = threading.RLock()

# ── File đánh dấu tài khoản đã đăng ký thành công ────────────────────
REGISTERED_FILE = "data/registered.jsonl"

def registered_emails():
    """Lấy tập hợp email đã xác nhận đăng ký thành công (đọc từ registered.jsonl)."""
    result = set()
    path = Path(REGISTERED_FILE)
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            try:
                entry = json.loads(line)
                if entry.get("email") and entry.get("status"):
                    result.add(entry["email"].strip().casefold())
            except (ValueError, AttributeError):
                continue
    return result

def record_registered_account(email, evidence, capcut_password=None):
    """Ghi nhận tài khoản đã đăng ký thành công vào registered.jsonl."""
    with ACCOUNTS_LOCK:
        if email.strip().casefold() not in registered_emails():
            entry = {"email": email, "status": evidence, "confirmed_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
            if capcut_password is not None:
                entry["capcut_password"] = capcut_password
            os.makedirs("data", exist_ok=True)
            with open(REGISTERED_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
        removed = prune_registered_accounts()
        log(f"✅ Đã xác nhận tài khoản {email}; lọc {removed} dòng khỏi hotmails.txt.", "OK")

def prune_registered_accounts(file_path=None):
    """Lọc email đã đăng ký thành công khỏi hotmails.txt (atomic replace)."""
    with ACCOUNTS_LOCK:
        if file_path is None:
            file_path = HOTMAIL_FILE
        path = Path(file_path)
        confirmed = registered_emails()
        if not path.exists() or not confirmed:
            return 0
        lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        kept = []
        for line in lines:
            email_col = line.split("|", 1)[0].strip().casefold()
            if line.lstrip().startswith("#") or email_col not in confirmed:
                kept.append(line)
        removed = len(lines) - len(kept)
        if not removed:
            return 0
        # Backup trước khi sửa
        backup_dir = path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / f"{path.name}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.{uuid.uuid4().hex[:8]}.bak"
        shutil.copy2(path, backup)
        # Atomic write
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp.write_text("".join(kept), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()
        log(f"📋 Đã lọc {removed} email đã đăng ký khỏi {file_path} (backup: {backup.name})", "INFO")
        return removed

def mark_hotmail_used(acc):
    with FILE_LOCK:
        try:
            with open("data/onl.txt", "a", encoding="utf-8") as f:
                f.write(acc['original_line'] + "\n")
            
            with open(HOTMAIL_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            with open(HOTMAIL_FILE, "w", encoding="utf-8") as f:
                for line in lines:
                    if line.strip() and line.strip() != acc['original_line'].strip():
                        f.write(line)
        except Exception as e:
            log(f"Lỗi khi cập nhật file: {e}", "WARN")

def mark_hotmail_failed(acc, reason="API_OR_OTP_FAILED"):
    with FILE_LOCK:
        try:
            with open("data/hotmail_failed.txt", "a", encoding="utf-8") as f:
                f.write(f"{acc.get('original_line', '')}|REASON={reason}|DATE={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            with open(HOTMAIL_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            with open(HOTMAIL_FILE, "w", encoding="utf-8") as f:
                for line in lines:
                    if line.strip() and line.strip() != acc.get('original_line', '').strip():
                        f.write(line)
            log(f"Đã loại bỏ mail lỗi {acc.get('email')} khỏi {HOTMAIL_FILE} (lưu vào data/hotmail_failed.txt)", "INFO")
        except Exception as e:
            log(f"Lỗi khi cập nhật file mail lỗi: {e}", "WARN")

class C:


    OK   = "\033[92m"   
    WARN = "\033[93m"   
    ERR  = "\033[91m"   
    INFO = "\033[96m"   
    BOLD = "\033[1m"
    RST  = "\033[0m"

def log(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    color = {"OK": C.OK, "WARN": C.WARN, "ERR": C.ERR, "INFO": C.INFO}.get(level, C.INFO)
    icon  = {"OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "INFO": "📌"}.get(level, "📌")
    print(f"{color}[{now}] {icon} {msg}{C.RST}")


# ── Hỗ trợ lấy OTP qua API ──────────────────────────────────────────

GLOBAL_STOP_EVENT = None

# ── Regex phân biệt trial 0đ chuẩn (từ Tool 2) ───────────────────────
ZERO_VND_RE = re.compile(
    r"(?<![\w.,])(?:0(?:[.,]0+)?\s*(?:₫|đ|vnđ|vnd)|(?:₫|đ|vnđ|vnd)\s*0(?:[.,]0+)?)(?![\w.,])", re.I
)
SEVEN_DAYS_RE = re.compile(r"(?<!\d)7\s*[-–]?\s*(?:ngày|ngay|days?)\b", re.I)
FREE_SEVEN_DAYS_RE = re.compile(
    r"(?<!\d)(?:7\s*[-–]?\s*(?:ngày|ngay)\s*(?:dùng thử\s*)?miễn phí"
    r"|miễn phí\s*(?:trong\s*)?7\s*(?:ngày|ngay)"
    r"|7\s*[-–]?\s*days?\s*(?:free(?:\s+trial)?|trial\s+free)"
    r"|free\s*(?:trial\s*)?(?:for\s*)?7\s*[-–]?\s*days?)\b", re.I
)

def is_trial_7d_offer(text):
    """Thẻ gói phải có CẢ thời hạn 7 ngày VÀ bằng chứng miễn phí/0đ."""
    if re.search(r"not eligible|trial.{0,20}(?:unavailable|not available)|no free trial|không đủ điều kiện|không có\s*(?:bản\s*)?dùng thử", text, re.I):
        return False
    return bool(SEVEN_DAYS_RE.search(text) and (ZERO_VND_RE.search(text) or FREE_SEVEN_DAYS_RE.search(text)))

def is_pro_pricing_card(text):
    """Xác định đây là thẻ gói Pro thật (không phải Free/Basic)."""
    return bool(re.match(r"\s*(?:CapCut\s+)?Pro\b", text, re.I)) and not bool(
        re.search(r"^\s*(?:Free|Basic|Miễn phí|Ultra|Standard|Teams?|Business|Doanh nghiệp)\s*$", text, re.I | re.M)
    )

def has_currency_price(text):
    return bool(re.search(r"\d[\d.,]*\s*(?:[đ₫]|vnd|vnđ)|(?:[đ₫]|vnd|vnđ)\s*\d|[$€£]\s*\d|\d+(?:[.,]\d+)?\s*(?:usd|eur|gbp)", text, re.I))

def is_pipopay_url(url):
    """Kiểm tra URL thuộc cashier pipopay."""
    try:
        from urllib.parse import urlsplit
        parsed = urlsplit(url or "")
        host = (parsed.hostname or "").lower()
        return parsed.scheme in ("http", "https") and (host == "pipopay.com" or host.endswith(".pipopay.com"))
    except Exception:
        return False

def extract_detected_price(card_text="", full_text="", default="không xác định"):
    """
    [TỐI ƯU Tool 2] Trích xuất mức giá từ nội dung text của card/bảng giá CapCut.
    Ưu tiên text của card trước, sau đó đến full text.
    """
    for text in [card_text, full_text]:
        if not text:
            continue
        # 1. Kiểm tra 0đ / trial 7 ngày
        if is_trial_7d_offer(text) or ZERO_VND_RE.search(text) or FREE_SEVEN_DAYS_RE.search(text):
            return "0đ"
        # 2. Kiểm tra gói 22k
        m_22k = re.search(r"(?<![\d.,])(?:₫|vnd|vnđ)?\s*(?:22[.,]000|22000)(?!\d)\s*(?:[đ₫]|vnd|vnđ)?", text, re.I)
        if m_22k:
            p = m_22k.group(0).strip()
            if not re.search(r"[đ₫vnd]", p, re.I):
                p += "đ"
            return p
        # 3. Tìm giá VNĐ có số phân cách nghìn và ký hiệu đ/₫/vnd (vd: 189.000đ, 222.000đ)
        m_vnd = re.search(r"(?:[₫đ]|vnd|vnđ)\s*\d{1,3}(?:[.,]\d{3})+(?!\d)|\b\d{1,3}(?:[.,]\d{3})+\s*(?:[₫đ]|vnd|vnđ)", text, re.I)
        if m_vnd:
            return m_vnd.group(0).strip()
        # 4. Tìm số tiền ngoại tệ (vd: $9.99, £7.99, 9.99 USD)
        m_curr = re.search(r"[\$€£¥]\s*\d+(?:[.,]\d+)?|\b\d+(?:[.,]\d+)?\s*(?:usd|eur|gbp)", text, re.I)
        if m_curr:
            return m_curr.group(0).strip()
        # 5. Tìm số hàng nghìn bất kỳ (vd: 189.000, 199.000)
        m_num = re.search(r"\b\d{1,3}(?:[.,]\d{3})+\b", text)
        if m_num:
            return m_num.group(0).strip() + "đ"
    return default

def trial_checkout_is_free(text):
    """
    [TỐI ƯU Tool 2] Xác minh trực tiếp nội dung checkout Pipopay:
    Chỉ công nhận là Trial 0đ nếu số tiền ĐẾN HẠN HÔM NAY (due today / total due) là 0đ.
    Nếu là 22k hoặc thu tiền hôm nay thì KHÔNG phải trial 0đ.
    """
    if not text:
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    due_label = re.compile(
        r"thanh toán hôm nay|(?:tổng|số) tiền (?:cần )?thanh toán|tổng cộng|đến hạn (?:hôm nay|ngay)"
        r"|\btotal(?:\s+(?:due|today|now))?\b(?!\s*(?:discount|savings|credits?))"
        r"|\bdue\s*(?:today|now)\b|\bpay\s*today\b|\bamount\s*due\b", re.I
    )
    for index, line in enumerate(lines):
        if not due_label.search(line):
            continue
        for amount_line in lines[index:index + 3]:
            if has_currency_price(amount_line):
                without_zero = ZERO_VND_RE.sub("", amount_line)
                if has_currency_price(without_zero) or not ZERO_VND_RE.search(amount_line):
                    return False
                return True
    return bool(is_trial_7d_offer(text) and (ZERO_VND_RE.search(text) or "$0" in text or "0$" in text))

def record_pricing_status(email, price_text):
    """Lưu phân loại giá tiền vào file data/status_prices.txt."""
    try:
        os.makedirs("data", exist_ok=True)
        with open("data/status_prices.txt", "a", encoding="utf-8") as f:
            f.write(f"{email}\t{price_text}\n")
    except Exception as e:
        log(f"Lỗi lưu status_prices: {e}", "WARN")


_MS_TOKEN_CACHE = {}

def _fetch_messages_webmail(refresh_token, client_id, limit=10):
    """
    Đọc thư qua Web Mail Reader API chính thức (https://web-mail-reader.vercel.app/api/mail-all).
    Tự động giải mã Microsoft OAuth và trích xuất mã OTP thông minh ngay trong response.
    """
    try:
        url = "https://web-mail-reader.vercel.app/api/mail-all"
        payload = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "limit": limit
        }
        headers = {"Content-Type": "application/json"}
        r = requests.post(url, json=payload, headers=headers, timeout=12)
        if r.status_code == 200:
            data = r.json()
            raw_msgs = data.get("messages") or []
            normalized = []
            for m in raw_msgs:
                from_addr = str(m.get("from_address") or "").strip()
                from_name = str(m.get("from_name") or "").strip()
                sender = from_addr or from_name
                subj = str(m.get("subject") or "")
                date_str = str(m.get("date") or "")
                snippet = str(m.get("snippet") or "")
                code = str(m.get("code") or "").strip()
                uid = str(m.get("id") or "")
                normalized.append({
                    "from": sender,
                    "sender": sender,
                    "from_name": from_name,
                    "from_address": from_addr,
                    "subject": subj,
                    "date": date_str,
                    "message": snippet,
                    "bodyText": snippet,
                    "code": code,
                    "uid": uid,
                    "id": uid
                })
            return normalized, None
        else:
            err_text = r.text
            try:
                err_data = r.json()
                err_text = err_data.get("error") or err_text
            except Exception:
                pass
            return [], f"WebMail API ({r.status_code}): {err_text}"
    except Exception as e:
        return [], str(e)

def _fetch_messages_direct_microsoft(refresh_token, client_id):
    """
    Đọc trực tiếp từ Microsoft Graph API chính chủ bằng refresh_token và client_id.
    Tốc độ ~0.5s, hỗ trợ cả Live OAuth endpoint (login.live.com) lẫn Microsoft Online v2.0 endpoint.
    """
    global _MS_TOKEN_CACHE
    try:
        cache_key = f"{refresh_token[:30]}_{client_id}"
        cached = _MS_TOKEN_CACHE.get(cache_key)
        now = time.time()
        access_token = None
        if cached and cached[1] > now:
            access_token = cached[0]

        if not access_token:
            # 1. Thử Live OAuth endpoint (chuẩn nhất cho tài khoản cá nhân Hotmail / Outlook mua ngoài)
            try:
                r = requests.post(
                    "https://login.live.com/oauth20_token.srf",
                    data={
                        "client_id": client_id,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10
                )
                data = r.json()
                if data.get("access_token"):
                    access_token = data.get("access_token")
                    expires_in = int(data.get("expires_in") or 3600)
                    _MS_TOKEN_CACHE[cache_key] = (access_token, now + max(300, expires_in - 60))
            except Exception:
                pass

        if not access_token:
            # 2. Thử Microsoft Online v2.0 endpoint (cho Azure AD App registered with Graph scopes)
            for token_url in (
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
            ):
                try:
                    r = requests.post(
                        token_url,
                        data={
                            "client_id": client_id,
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_token,
                            "scope": "https://graph.microsoft.com/Mail.Read offline_access"
                        },
                        timeout=10
                    )
                    data = r.json()
                    if data.get("access_token"):
                        access_token = data.get("access_token")
                        expires_in = int(data.get("expires_in") or 3600)
                        _MS_TOKEN_CACHE[cache_key] = (access_token, now + max(300, expires_in - 60))
                        break
                except Exception:
                    pass

        if not access_token:
            return [], "Không lấy được access_token từ Microsoft OAuth"

        headers = {"Authorization": f"Bearer {access_token}"}
        g_res = requests.get(
            "https://graph.microsoft.com/v1.0/me/messages?$top=15&$orderby=receivedDateTime desc",
            headers=headers,
            timeout=10
        )
        if g_res.status_code != 200:
            return [], f"Microsoft Graph API lỗi HTTP {g_res.status_code}: {g_res.text[:120]}"

        raw_msgs = g_res.json().get("value", [])
        normalized = []
        for m in raw_msgs:
            sender_addr = m.get("from", {}).get("emailAddress", {}).get("address", "")
            from_name = m.get("from", {}).get("emailAddress", {}).get("name", "")
            subj = m.get("subject", "")
            date_str = m.get("receivedDateTime", "")
            body_content = m.get("body", {}).get("content", "")
            uid = m.get("id", "")
            
            otp = ""
            m_code = re.search(r'\b(\d{6})\b', subj + ' ' + body_content)
            if m_code:
                otp = m_code.group(1)
                
            normalized.append({
                "from": sender_addr,
                "sender": sender_addr,
                "from_name": from_name,
                "from_address": sender_addr,
                "subject": subj,
                "date": date_str,
                "message": body_content,
                "bodyText": body_content,
                "code": otp,
                "uid": uid,
                "id": uid
            })
        return normalized, None
    except Exception as e:
        return [], str(e)

def _fetch_messages_from_api(email, password, refresh_token, client_id, mail_api_source):
    """Lấy danh sách messages từ API (webmail, direct, smail1s, dongvanfb, mixmmo). Trả về (list, error)."""
    try:
        # 1. Nguồn WebMail (Web Mail Reader Vercel API): Cực nhanh, ổn định và tự bóc tách OTP
        if mail_api_source in ("webmail", "web_mail_reader", "web-mail-reader", "vercel"):
            if refresh_token and client_id:
                msgs, err = _fetch_messages_webmail(refresh_token, client_id)
                if not err:
                    return msgs, None
                # Fallback sang direct Microsoft Graph
                direct_msgs, direct_err = _fetch_messages_direct_microsoft(refresh_token, client_id)
                if not direct_err:
                    return direct_msgs, None
                return msgs, err

        # 2. Nguồn Direct Microsoft Graph API
        if mail_api_source in ("direct", "microsoft"):
            if refresh_token and client_id:
                msgs, err = _fetch_messages_direct_microsoft(refresh_token, client_id)
                if not err:
                    return msgs, None
                return _fetch_messages_webmail(refresh_token, client_id)

        # 3. Nguồn Smail1s:
        # Nếu có refresh_token & client_id: ưu tiên WebMail Reader / Direct Graph
        if mail_api_source == "smail1s":
            if refresh_token and client_id:
                msgs, err = _fetch_messages_webmail(refresh_token, client_id)
                if not err:
                    return msgs, None
                direct_msgs, direct_err = _fetch_messages_direct_microsoft(refresh_token, client_id)
                if not direct_err:
                    return direct_msgs, None

            api_url = "https://smail1s.com/get_messages"
            headers = {"Content-Type": "application/json"}
            payload = {
                "mode": "oauth" if (refresh_token and client_id) else "roundcube",
                "data": f"{email}|{refresh_token}|{client_id}" if (refresh_token and client_id) else f"{email}|{password}"
            }
            try:
                resp = requests.post(api_url, headers=headers, json=payload, timeout=15)
                data = resp.json()
                d_list = data.get("data")
                if isinstance(d_list, list) and len(d_list) > 0:
                    item = d_list[0]
                    msgs = item.get("messages") or []
                    return msgs, None
            except Exception:
                pass

            if refresh_token and client_id:
                msgs, err = _fetch_messages_webmail(refresh_token, client_id)
                return msgs, err

            return [], None

        # 4. Nguồn DongVanFB
        elif mail_api_source == "dongvanfb":
            api_url = HOTMAIL_API_URL
            headers = {"Content-Type": "application/json"}
            payload = {"email": email, "pass": password, "refresh_token": refresh_token, "client_id": client_id}
            try:
                resp = requests.post(api_url, headers=headers, json=payload, timeout=15)
                data = resp.json()
                if data.get("status") or data.get("success"):
                    msgs = data.get("messages") or []
                    return msgs, None
                if ("IMAP connection failed" in str(data) or not data.get("messages")) and refresh_token and client_id:
                    msgs, err = _fetch_messages_webmail(refresh_token, client_id)
                    if not err:
                        return msgs, None
                    direct_msgs, direct_err = _fetch_messages_direct_microsoft(refresh_token, client_id)
                    return direct_msgs, direct_err
            except Exception:
                if refresh_token and client_id:
                    msgs, err = _fetch_messages_webmail(refresh_token, client_id)
                    return msgs, err
            return [], None

        # 5. Nguồn MixMMO
        else: # mixmmo
            api_url = "https://mixmmo.com/api/get-hotmail-messages.php"
            headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
            payload = {"action": "get_hotmail_messages", "account": f"{email}|{password}|{refresh_token}|{client_id}", "mode": "oauth", "folder": "inbox", "start_timestamp": "0"}
            try:
                resp = requests.post(api_url, headers=headers, data=payload, timeout=15)
                data = resp.json()
                if data.get("status") or data.get("success"):
                    msgs = data.get("messages") or []
                    return msgs, None
            except Exception:
                pass
            if refresh_token and client_id:
                msgs, err = _fetch_messages_webmail(refresh_token, client_id)
                if not err:
                    return msgs, None
                direct_msgs, direct_err = _fetch_messages_direct_microsoft(refresh_token, client_id)
                return direct_msgs, direct_err
            return [], None
    except Exception as e:
        if refresh_token and client_id:
            msgs, err = _fetch_messages_webmail(refresh_token, client_id)
            return msgs, err
        return [], str(e)

def _extract_otp_from_message(msg):
    """Trích xuất mã OTP 6 chữ số từ một tin nhắn. Trả về string OTP hoặc None."""
    otp = str(msg.get("code") or "").strip()
    if otp and otp.isdigit() and len(otp) == 6:
        return otp
    subject = str(msg.get("subject") or "")
    message = str(msg.get("message") or "")
    bodyText = str(msg.get("bodyText") or "")
    clean_message = re.sub(r'<style[^>]*>.*?</style>', ' ', message, flags=re.IGNORECASE)
    clean_message = re.sub(r'<[^>]+>', ' ', clean_message)
    import html as _html
    clean_message = _html.unescape(clean_message)
    text_to_search = subject + " " + clean_message + " " + bodyText
    match = re.search(r'(?<![#&a-zA-Z0-9])(\d{6})(?![0-9])', text_to_search)
    if match:
        return match.group(1)
    return None

def snapshot_mail_before_register(email, password, refresh_token, client_id, mail_api_source="mixmmo"):
    """
    [TỐI ƯU Tool 2] Chụp nhanh hộp thư TRƯỚC khi bấm Đăng ký.
    Trả về dict: {existing_ids: set, existing_otps: set}
    Dùng để bỏ qua OTP cũ khi polling sau này.
    """
    result = {"existing_ids": set(), "existing_otps": set()}
    try:
        messages, err = _fetch_messages_from_api(email, password, refresh_token, client_id, mail_api_source)
        capcut_found = 0
        for msg in messages:
            sender = str(msg.get("from") or msg.get("sender") or "").lower()
            if "admin@mail.capcut.com" not in sender and "capcut" not in sender:
                continue
            capcut_found += 1
            msg_id = str(msg.get("id") or msg.get("uid") or "").strip()
            msg_date = str(msg.get("date") or "")
            msg_subj = str(msg.get("subject") or "")
            sig = msg_id if msg_id else f"{msg_date}_{msg_subj}"
            result["existing_ids"].add(sig)
            otp = _extract_otp_from_message(msg)
            if otp:
                result["existing_otps"].add(otp)
        if capcut_found > 0:
            log(f"[OTP Snapshot] Phát hiện {capcut_found} thư CapCut cũ (OTP cũ: {list(result['existing_otps'])}). Sẽ bỏ qua khi polling.", "INFO")
        else:
            log(f"[OTP Snapshot] Hộp thư {email} sạch — không có thư CapCut cũ.", "INFO")
    except Exception as e:
        log(f"[OTP Snapshot] Lỗi snapshot hộp thư: {e}", "WARN")
    return result

def wait_for_otp(email, password, refresh_token, client_id, timeout=90, interval=4, after_ts=0,
                 mail_api_source="mixmmo", max_api_errors=3,
                 ignore_ids=None, ignore_otps=None):
    """
    Chờ OTP mới từ CapCut.
    ignore_ids, ignore_otps: tập hợp ID/OTP cũ đã có trước khi đăng ký (từ snapshot_mail_before_register)
    — chỉ trả về OTP mới được gửi SAU khi bấm Đăng ký.
    """
    if ignore_ids is None:
        ignore_ids = set()
    if ignore_otps is None:
        ignore_otps = set()

    log(f"Đang chờ OTP cho {email} qua {mail_api_source.upper()} API (tối đa {timeout}s)...", "INFO")
    if ignore_ids or ignore_otps:
        log(f"   Bỏ qua {len(ignore_ids)} thư cũ (OTP cũ: {list(ignore_otps)})...", "INFO")

    elapsed = 0
    consecutive_api_errors = 0
    last_skip_notice = 0
    fatal_keywords = [
        "account security interrupt", "compromised", "account is locked",
        "account is blocked", "token het han", "invalid_client", "expired_token",
        "aadsts50057", "aadsts50076", "aadsts50079", "aadsts70008"
    ]

    while elapsed < timeout:
        if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
            log("Task bị dừng bởi người dùng, thoát chờ OTP!", "WARN")
            return None
        try:
            messages, err = _fetch_messages_from_api(email, password, refresh_token, client_id, mail_api_source)
            if err is not None:
                consecutive_api_errors += 1
                raw_err = str(err).lower()
                is_fatal = any(k in raw_err for k in fatal_keywords) and ("scopes requested are unauthorized" not in raw_err)
                log(f"API Hotmail trả về lỗi ({consecutive_api_errors}/{max_api_errors}): {err}", "WARN")
                if is_fatal and consecutive_api_errors >= 2:
                    log(f"⚠️ Lỗi Token/Hotmail chết. Bỏ qua mail {email}!", "ERR")
                    return None
                if consecutive_api_errors >= max_api_errors:
                    log(f"⚠️ API lỗi liên tiếp {consecutive_api_errors} lần. Bỏ qua mail {email}!", "ERR")
                    return None
            else:
                consecutive_api_errors = 0
                has_skipped = False
                # Sort thư mới nhất trước
                sorted_msgs = sorted(messages, key=lambda m: str(m.get("date") or ""), reverse=True)
                for msg in sorted_msgs:
                    sender = str(msg.get("from") or msg.get("sender") or "").lower()
                    if "admin@mail.capcut.com" not in sender and "capcut" not in sender:
                        continue
                    msg_id = str(msg.get("id") or msg.get("uid") or "").strip()
                    msg_date = str(msg.get("date") or "")
                    msg_subj = str(msg.get("subject") or "")
                    sig = msg_id if msg_id else f"{msg_date}_{msg_subj}"
                    # Bỏ qua thư cũ đã có trước khi đăng ký
                    if sig in ignore_ids or (msg_id and msg_id in ignore_ids):
                        has_skipped = True
                        continue
                    otp = _extract_otp_from_message(msg)
                    if not otp:
                        continue
                    # Bỏ qua nếu OTP trùng cũ và không có ID riêng để phân biệt
                    if not msg_id and not msg_date and otp in ignore_otps:
                        has_skipped = True
                        continue
                    log(f"✅ Nhận được OTP MỚI: {C.BOLD}{otp}{C.RST} (Subject: {msg_subj[:50]})", "OK")
                    return otp
                if has_skipped and elapsed - last_skip_notice >= 10:
                    log("Thư CapCut cũ bị bỏ qua, đang chờ thư MỚI...", "INFO")
                    last_skip_notice = elapsed
        except Exception as e:
            consecutive_api_errors += 1
            log(f"Lỗi gọi API Hotmail ({consecutive_api_errors}/{max_api_errors}): {e}", "WARN")
            if consecutive_api_errors >= max_api_errors:
                log(f"⚠️ Không thể kết nối API Hotmail sau {consecutive_api_errors} lần thử. Bỏ qua mail {email}!", "ERR")
                return None

        time.sleep(interval)
        elapsed += interval

    log(f"Hết thời gian chờ OTP ({timeout}s) cho {email}!", "ERR")
    return None


def password_form_kind(driver):
    """
    [TỐI ƯU Tool 2] Phân biệt form Đăng nhập (email đã có) vs Đăng ký (email mới).
    Trả về: "existing" | "new" | "unknown"
    - "existing": Email đã có tài khoản CapCut → không đăng ký lại
    - "new": Email mới → tiếp tục đăng ký
    - "unknown": Không xác định được (an toàn, không bấm bừa)
    """
    from selenium.webdriver.common.by import By
    try:
        # Tìm nút submit trong form có input password
        forms = driver.find_elements(By.CSS_SELECTOR, "form")
        if not forms:
            # Không có form — thử tìm container chứa password input
            pw_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            if pw_inputs:
                forms = [driver.find_element(By.TAG_NAME, "body")]

        for form in forms:
            try:
                pw = form.find_elements(By.CSS_SELECTOR, "input[type='password']")
                if not pw:
                    continue
                btns = form.find_elements(By.CSS_SELECTOR, "button[type='submit'], button")
                for btn in btns:
                    txt = (btn.text or "").strip().lower()
                    if any(k in txt for k in ["đăng nhập", "sign in", "log in", "login"]):
                        return "existing"
                    if any(k in txt for k in ["đăng ký", "sign up", "register", "create"]):
                        return "new"
            except Exception:
                continue

        # Fallback: tìm label/heading gần nhất
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if any(k in page_text for k in ["đăng nhập vào tài khoản", "sign in to your account", "welcome back"]):
            return "existing"
        if any(k in page_text for k in ["tạo tài khoản", "create account", "create your account", "đăng ký tài khoản"]):
            return "new"
    except Exception:
        pass
    return "unknown"


def verify_trial_checkout_dom(driver, timeout=15):
    """
    [TỐI ƯU Tool 2] Xác minh trang checkout THẬT SỰ là 0đ/trial 7 ngày
    trước khi lưu vào trial_7day.txt.
    Đọc DOM cashier PipoPay để kiểm tra chắc chắn số tiền phải trả hôm nay là 0đ.
    """
    from selenium.webdriver.common.by import By
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            text_candidates = []
            if is_pipopay_url(driver.current_url):
                try:
                    text_candidates.append(("current_page", driver.find_element(By.TAG_NAME, "body").text))
                except Exception:
                    pass
            orig = driver.current_window_handle
            for h in driver.window_handles:
                try:
                    driver.switch_to.window(h)
                    if is_pipopay_url(driver.current_url):
                        text_candidates.append((f"tab_{h[:6]}", driver.find_element(By.TAG_NAME, "body").text))
                except Exception:
                    pass
            try:
                driver.switch_to.window(orig)
            except Exception:
                pass

            for label, text in text_candidates:
                if trial_checkout_is_free(text):
                    log(f"✅ verify_trial_checkout_dom: Xác minh THÀNH CÔNG gói 0đ/trial 7 ngày từ {label}.", "OK")
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


from .browser_utils import get_settings_from_db
from .browser_utils import get_rotated_proxy as _grp
def get_rotated_proxy():

    return _grp(logger_func=log)
def setup_driver(index=1, keep_open=False, use_api_proxy=True, batch_size=3, use_proxy=True, predefined_proxy=None, incognito=False, headless=False, browser_type="chrome"):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    options = Options()
    if incognito:
        options.add_argument("--incognito")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    if keep_open:
        options.add_experimental_option("detach", True)
    
    from .browser_utils import get_window_bounds
    window_width, window_height, x, y = get_window_bounds(index, batch_size, zero_based_index=True)
    
    options.add_argument(f"--window-size={window_width},{window_height}")
    options.add_argument(f"--window-position={x},{y}")
    options.add_argument("--lang=vi-VN")

    proxy = None
    PROXY_HOST = None
    PROXY_USER = ""
    PROXY_PASS = ""
    if use_proxy:
        if predefined_proxy:
            proxy = predefined_proxy
            log("Đang dùng proxy chung (Shared Proxy) cho chức năng 2...", "INFO")
        elif use_api_proxy:
            proxy = get_rotated_proxy()
            
        if proxy:
            PROXY_HOST, PROXY_PORT = proxy["host"], proxy["port"]
            PROXY_USER = proxy.get("user", "")
            PROXY_PASS = proxy.get("pass", "")
            log(f"Đang dùng Proxy API: {PROXY_HOST}:{PROXY_PORT}", "INFO")
        else:
            # Dự phòng nếu API lỗi - proxy này có thể đã chết, kiểm tra lại!
            PROXIES = [
                {"host": "180.93.2.171", "port": 3131, "user": "kierangrayson226", "pass": "odq0nda0odmzoa=="}
            ]
            proxy = random.choice(PROXIES)
            PROXY_HOST, PROXY_PORT = proxy["host"], proxy["port"]
            PROXY_USER = proxy.get("user", "")
            PROXY_PASS = proxy.get("pass", "")
            log(f"[⚠️ DỰ PHÒNG] API proxy lỗi -> dùng proxy cố định: {PROXY_HOST}:{PROXY_PORT} (có thể đã chết!)", "WARN")

    relay = None
    if PROXY_HOST:
        relay = LocalProxyRelay(
            upstream_host=PROXY_HOST,
            upstream_port=PROXY_PORT,
            username=PROXY_USER,
            password=PROXY_PASS,
            local_port=0
        ).start()
        options.add_argument(f"--proxy-server=http://127.0.0.1:{relay.local_port}")
        options.add_argument("--proxy-bypass-list=<-loopback>")
        log(f"🔗 Đã kích hoạt Local Proxy Relay: 127.0.0.1:{relay.local_port} -> {PROXY_HOST}:{PROXY_PORT}", "OK")


    if browser_type.lower() in ["firefox", "camoufox"]:
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        ff_options = FirefoxOptions()
        if headless:
            ff_options.add_argument("--headless")
        if incognito:
            ff_options.add_argument("-private")
        ff_options.add_argument(f"--width={window_width}")
        ff_options.add_argument(f"--height={window_height}")
        
        import os
        camoufox_path = os.path.expanduser("~/Library/Caches/camoufox/Camoufox.app/Contents/MacOS/camoufox")
        if browser_type.lower() == "camoufox" and os.path.exists(camoufox_path):
            ff_options.binary_location = camoufox_path
            log("Đang sử dụng trình duyệt Camoufox!", "OK")
            
        if PROXY_HOST and relay:
            ff_options.set_preference("network.proxy.type", 1)
            ff_options.set_preference("network.proxy.http", "127.0.0.1")
            ff_options.set_preference("network.proxy.http_port", relay.local_port)
            ff_options.set_preference("network.proxy.ssl", "127.0.0.1")
            ff_options.set_preference("network.proxy.ssl_port", relay.local_port)
                
        driver = webdriver.Firefox(options=ff_options)
    else:
        if headless:
            options.add_argument("--headless=new")
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            log(f"Không tự tìm được chromedriver: {e}", "WARN")
            log("Đang thử dùng webdriver-manager...", "INFO")
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service as ChromeService
                driver = webdriver.Chrome(
                    service=ChromeService(ChromeDriverManager().install()),
                    options=options
                )
            except Exception as e2:
                log(f"webdriver-manager cũng lỗi: {e2}", "ERR")
                raise

    if relay:
        driver._proxy_relay = relay
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def wait_for_element(driver, by, value, timeout=20):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.presence_of_element_located((by, value)))

def wait_clickable(driver, by, value, timeout=20):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.element_to_be_clickable((by, value)))

def set_react_input(driver, element, value):
    """Nhập giá trị vào React input (kích hoạt onChange)"""
    from selenium.webdriver.common.keys import Keys
    element.click()
    time.sleep(0.2)
    element.send_keys(Keys.CONTROL + "a")
    element.send_keys(Keys.DELETE)
    time.sleep(0.1)
    for char in value:
        element.send_keys(char)
        time.sleep(0.03)
    time.sleep(0.3)

def try_click(driver, element, label=""):
    """Click an element safely"""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)
        element.click()
        log(f"Clicked: {label}", "INFO")
        return True
    except Exception as e:
        try:
            driver.execute_script("arguments[0].click();", element)
            log(f"JS-clicked: {label}", "INFO")
            return True
        except Exception as e2:
            log(f"Không click được {label}: {e2}", "WARN")
            return False

# ────────────────────────────────────────────────────────────────────
# CÁC BƯỚC ĐĂNG KÝ
# ────────────────────────────────────────────────────────────────────

def step0_dismiss_tos(driver):
    """Bước 0: Đóng popup Terms of Service nếu xuất hiện"""
    from selenium.webdriver.common.by import By
    try:
        # Chờ tối đa 8s để popup ToS xuất hiện
        ok_btn = wait_clickable(driver, By.XPATH,
            '//button[normalize-space(text())="OK"] | //div[normalize-space(text())="OK"] | //span[normalize-space(text())="OK"]',
            timeout=8)
        try_click(driver, ok_btn, "OK (ToS dialog)")
        log("Đã đóng popup Terms of Service", "OK")
        time.sleep(1)
    except Exception:
        log("Không có popup ToS hoặc đã đóng rồi", "INFO")

def step0b_click_email_button(driver):
    """Bước 0b: Click nút 'Tiếp tục bằng email' trên trang chọn phương thức"""
    from selenium.webdriver.common.by import By

    log("Đang click 'Tiếp tục bằng email'...", "INFO")

    # Trang signup CapCut dùng div/a styled như button, tìm theo text
    selectors = [
        # XPath theo text tiếng Việt
        '//div[contains(text(),"email") or contains(text(),"Email")]',
        '//a[contains(text(),"email") or contains(text(),"Email")]',
        '//span[contains(text(),"Tiếp tục bằng email")]/..',
        # Fallback theo class CapCut
        '//div[contains(@class,"email")]',
    ]

    clicked = False
    for xpath in selectors:
        try:
            els = driver.find_elements(By.XPATH, xpath)
            for el in els:
                if el.is_displayed():
                    txt = el.text.strip()
                    if 'email' in txt.lower() and len(txt) < 60:
                        try_click(driver, el, f"Email button: '{txt}'")
                        clicked = True
                        break
        except Exception:
            pass
        if clicked:
            break

    if not clicked:
        # Thử tìm tất cả elements hiển thị có chứa chữ email
        try:
            all_els = driver.find_elements(By.XPATH, '//*[contains(translate(text(),"EMAIL","email"),"email")]')
            for el in all_els:
                if el.is_displayed() and el.text and len(el.text.strip()) < 50:
                    log(f"Thử click: '{el.text.strip()}'...", "WARN")
                    try_click(driver, el, "email fallback")
                    clicked = True
                    break
        except Exception:
            pass

    if clicked:
        log("Đã click nút Email", "OK")
        time.sleep(2)
    else:
        log("Không tìm thấy nút Email! Thử tiếp...", "WARN")

def step1_enter_email(driver, email):
    """Bước 1: Nhập email vào form và bấm Tiếp tục"""
    from selenium.webdriver.common.by import By

    log("Bước 1: Nhập email...", "INFO")

    # Chờ input email xuất hiện (sau khi click nút Email)
    email_input = wait_for_element(driver, By.CSS_SELECTOR,
        'input[type="text"], input[type="email"], input[name="signUsername"], '
        'input[placeholder*="mail"], input[placeholder*="email"], '
        'input[placeholder*="Email"], .code-input',
        timeout=20)

    set_react_input(driver, email_input, email)
    time.sleep(0.5)

    # Bấm Tiếp tục / Send code / Continue
    # CapCut dùng div/button với nhiều class khác nhau
    continue_xpaths = [
        '//button[contains(text(),"Tiếp") or contains(text(),"tiếp") or contains(text(),"Continue") or contains(text(),"Send") or contains(text(),"Gửi")]',
        '//div[contains(@id,"submit") or contains(@class,"submit") or contains(@class,"primary") or contains(@class,"confirm")]',
        '//button[@type="submit"]',
        '//button[contains(@class,"primary")]',
    ]
    clicked = False
    for xpath in continue_xpaths:
        try:
            els = driver.find_elements(By.XPATH, xpath)
            for el in els:
                if el.is_displayed() and el.is_enabled():
                    try_click(driver, el, f"Tiếp tục: '{el.text.strip()[:30]}'")
                    clicked = True
                    break
        except Exception:
            pass
        if clicked:
            break

    # Fallback: tìm button submit-button-container
    if not clicked:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, '#submit-button-container button, button[id*="submit"]')
            if btn.is_displayed():
                try_click(driver, btn, "Submit button")
                clicked = True
        except Exception:
            pass

    log("Đã nhập email và bấm Tiếp tục", "OK")
    time.sleep(2)

def step2_enter_password(driver, password):
    """Bước 2: Nhập mật khẩu và bấm Đăng ký (hoặc Đăng nhập nếu mail đã tồn tại)"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    log("Bước 2: Nhập mật khẩu...", "INFO")

    pwd_input = wait_for_element(driver, By.CSS_SELECTOR,
        'input[type="password"]', timeout=20)

    set_react_input(driver, pwd_input, password)
    time.sleep(0.5)

    # Kiểm tra loại form: email đã tồn tại hay mới
    form_kind = password_form_kind(driver)
    if form_kind == "existing":
        log("Phát hiện form ĐĂNG NHẬP (email này đã có tài khoản CapCut)", "WARN")
    elif form_kind == "new":
        log("Xác nhận form ĐĂNG KÝ mới", "INFO")

    # Tích checkbox nhận email khuyến mãi (nếu có)
    try:
        checkboxes = driver.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]')
        for cb in checkboxes:
            if cb.is_displayed() and not cb.is_selected():
                try:
                    label = cb.find_element(By.XPATH, "./ancestor::label")
                    try_click(driver, label, "Checkbox")
                except Exception:
                    try_click(driver, cb, "Checkbox (direct)")
                break
    except Exception:
        pass

    time.sleep(0.3)

    target_keywords = ["đăng ký", "register", "sign up", "tạo tài khoản", "create account"]
    if form_kind == "existing":
        target_keywords = ["đăng nhập", "log in", "login", "sign in"]

    # Ưu tiên tìm các button có text chứa từ khóa hành động (dùng . thay vì text() để lấy text trong thẻ con)
    button_candidates = []
    try:
        # Tìm các nút và phần tử button/div role=button
        found_buttons = driver.find_elements(By.XPATH, '//button | //*[@role="button"]')
        for b in found_buttons:
            try:
                if not b.is_displayed() or not b.is_enabled():
                    continue
                txt = (b.text or "").strip().lower()
                # TUYỆT ĐỐI BỎ QUA nút rỗng (icon mắt ẩn/hiện password)
                if not txt:
                    continue
                if any(kw in txt for kw in target_keywords):
                    button_candidates.append((b, txt))
            except Exception:
                continue
    except Exception:
        pass

    clicked = False
    for btn, btn_txt in button_candidates:
        if try_click(driver, btn, f"Nút: '{btn_txt}'"):
            clicked = True
            break

    # Nếu chưa click được nút phù hợp, thử submit bằng phím Enter trên ô password
    if not clicked:
        log("Thử submit bằng phím ENTER trên ô mật khẩu...", "INFO")
        try:
            pwd_input.send_keys(Keys.ENTER)
            clicked = True
            time.sleep(1)
        except Exception as e_enter:
            log(f"Không gửi được Enter: {e_enter}", "WARN")

    # Fallback cuối cùng: tìm button submit duy nhất trong form chứa password
    if not clicked:
        try:
            submit_btns = driver.find_elements(By.CSS_SELECTOR, 'button[type="submit"], #submit-button-container button')
            for sb in submit_btns:
                txt = (sb.text or "").strip().lower()
                if txt and (any(kw in txt for kw in target_keywords) or "tiếp" in txt or "next" in txt or "continue" in txt):
                    if try_click(driver, sb, f"Submit: '{txt}'"):
                        clicked = True
                        break
        except Exception:
            pass

    log("Đã nhập mật khẩu và bấm xác nhận Đăng ký", "OK")
    time.sleep(2)
    return form_kind

def step3_enter_birthday(driver):
    """Bước 3: Điền năm/tháng/ngày sinh"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    log("Bước 3: Điền ngày sinh...", "INFO")

    # Chờ màn hình ngày sinh
    try:
        wait_for_element(driver, By.CSS_SELECTOR,
            '.lv_sign_in_panel_wide-birthday-detail, .gate_birthday-picker', timeout=15)
    except Exception as e:
        if "TimeoutException" in type(e).__name__:
            url = driver.current_url.lower()
            if "my-edit" in url or "home" in url or "space" in url or "dashboard" in url:
                log("Đã đăng nhập thẳng vào tài khoản cũ, bỏ qua đăng ký!", "OK")
                return "ALREADY_LOGGED_IN"
        raise e
    time.sleep(0.1)

    # Nhập Năm
    try:
        year_input = driver.find_element(By.CSS_SELECTOR,
            '.gate_birthday-picker-input, input[placeholder="Năm"]')
        set_react_input(driver, year_input, DOB_YEAR)
        log(f"Đã nhập năm: {DOB_YEAR}", "OK")
        time.sleep(0.1)
    except Exception as e:
        log(f"Không tìm thấy ô nhập năm: {e}", "WARN")

    # Chọn Tháng (dropdown)
    try:
        selectors = driver.find_elements(By.CSS_SELECTOR, '.gate_birthday-picker-selector')
        if selectors:
            month_sel = selectors[0]
            try_click(driver, month_sel, "Month dropdown")
            time.sleep(0.2)

            # Tìm option Tháng 12
            options = driver.find_elements(By.CSS_SELECTOR,
                '.lv-select-option, [role="option"], .lv-select-item')
            clicked = False
            for opt in options:
                txt = opt.text.strip().lower()
                if txt in [DOB_MONTH, f"tháng {DOB_MONTH}", "12", "tháng 12"]:
                    if opt.is_displayed():
                        try_click(driver, opt, f"Tháng {DOB_MONTH}")
                        clicked = True
                        break
            if not clicked:
                # Fallback: click theo vị trí thứ 12
                visible_opts = [o for o in options if o.is_displayed()]
                if len(visible_opts) >= 12:
                    try_click(driver, visible_opts[11], "Tháng 12 (index)")
            time.sleep(0.1)
    except Exception as e:
        log(f"Lỗi chọn tháng: {e}", "WARN")

    # Chọn Ngày (dropdown)
    try:
        selectors = driver.find_elements(By.CSS_SELECTOR, '.gate_birthday-picker-selector')
        if len(selectors) >= 2:
            day_sel = selectors[1]
            try_click(driver, day_sel, "Day dropdown")
            time.sleep(0.2)

            options = driver.find_elements(By.CSS_SELECTOR,
                '.lv-select-option, [role="option"], .lv-select-item')
            clicked = False
            for opt in options:
                txt = opt.text.strip().lower()
                if txt in [DOB_DAY, f"ngày {DOB_DAY}", "12", "ngày 12"]:
                    if opt.is_displayed():
                        try_click(driver, opt, f"Ngày {DOB_DAY}")
                        clicked = True
                        break
            if not clicked:
                visible_opts = [o for o in options if o.is_displayed()]
                if len(visible_opts) >= 12:
                    try_click(driver, visible_opts[11], "Ngày 12 (index)")
            time.sleep(0.1)
    except Exception as e:
        log(f"Lỗi chọn ngày: {e}", "WARN")

    # Bấm Tiếp theo
    time.sleep(0.2)
    try:
        next_btn = driver.find_element(By.CSS_SELECTOR,
            '.lv_sign_in_panel_wide-birthday-next, .lv_sign_in_panel_wide-primary-button')
        if next_btn.is_enabled():
            try_click(driver, next_btn, "Tiếp theo (ngày sinh)")
        else:
            log("Nút Tiếp theo còn disabled, chờ thêm...", "WARN")
            time.sleep(1)
            # Thử lại
            if next_btn.is_enabled():
                try_click(driver, next_btn, "Tiếp theo (retry)")
    except Exception as e:
        log(f"Lỗi bấm Tiếp theo: {e}", "WARN")

    log("Hoàn tất bước ngày sinh", "OK")
    time.sleep(2)


def step4_enter_otp(driver, email, password, refresh_token, client_id, mail_api_source="mixmmo", snapshot=None):
    """
    Bước 4: Chờ OTP và nhập vào ô xác nhận
    snapshot: Dict chứa ignore_ids, ignore_otps từ snapshot_mail_before_register()
    để lọc sạch các thư/OTP cũ đã có trước khi bấm đăng ký.
    """
    from selenium.webdriver.common.by import By

    log("Bước 4: Chờ và nhập OTP...", "INFO")

    # Chờ màn hình xác nhận email
    wait_for_element(driver, By.CSS_SELECTOR,
        '.lv_sign_in_panel_wide-code-detail, .verification_code_input-wrapper', timeout=25)

    log("Màn hình xác nhận email xuất hiện. Đang lấy OTP từ API...", "INFO")

    # Chờ 3 giây để email server nhận thư
    time.sleep(3)

    ignore_ids = snapshot.get("ignore_ids", set()) if snapshot else set()
    ignore_otps = snapshot.get("ignore_otps", set()) if snapshot else set()

    otp = wait_for_otp(
        email, password, refresh_token, client_id,
        timeout=120, interval=4,
        mail_api_source=mail_api_source,
        ignore_ids=ignore_ids, ignore_otps=ignore_otps
    )

    if not otp:
        log("Không lấy được OTP!", "ERR")
        return False

    # Nhập OTP vào input ẩn (maxlength=6)
    try:
        otp_input = driver.find_element(By.CSS_SELECTOR,
            'input[maxlength="6"], .lv_sign_in_panel_wide-code-detail input')
        set_react_input(driver, otp_input, otp)
        log(f"Đã nhập OTP: {otp}", "OK")
        time.sleep(2)
        return True
    except Exception as e:
        log(f"Không tìm thấy ô nhập OTP: {e}", "ERR")
        # Thử click từng ký tự vào các ô chia nhỏ
        try:
            from selenium.webdriver.common.keys import Keys
            code_boxes = driver.find_elements(By.CSS_SELECTOR,
                '.verification_code_input-number input, input.lv-input')
            if code_boxes:
                code_boxes[0].click()
                for digit in otp:
                    driver.switch_to.active_element.send_keys(digit)
                    time.sleep(0.1)
                log(f"Đã nhập OTP qua từng ký tự: {otp}", "OK")
                return True
        except Exception as e2:
            log(f"Fallback OTP cũng lỗi: {e2}", "ERR")
        return False

def step5_open_capcut(driver):
    """Bước 5: Bấm 'Mở CapCut' để hoàn tất (bỏ qua join team)"""
    from selenium.webdriver.common.by import By
    log("Bước 5: Bấm 'Mở CapCut'...", "INFO")
    try:
        # Rút ngắn thời gian chờ popup vì đôi khi web tự chuyển thẳng luôn
        btn = wait_for_element(driver, By.CSS_SELECTOR, '#create-bottom, .lv-create-teamspace-confirm', timeout=15)
        time.sleep(1)
        try_click(driver, btn, "Mở CapCut")
        log("Đã bấm Mở CapCut!", "OK")
        time.sleep(3)
        return True
    except Exception as e:
        log("Không thấy popup Mở CapCut (có thể mạng chậm hoặc tự chuyển trang).", "INFO")
        return False

def step_skip_role_survey(driver, timeout=10):
    """Bấm Skip nếu xuất hiện modal khảo sát vai trò (Which roles best describes you?)"""
    from selenium.webdriver.common.by import By
    log("Kiểm tra modal khảo sát vai trò...", "INFO")
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Kiểm tra modal có xuất hiện không
            wrappers = driver.find_elements(By.CSS_SELECTOR, '.wrapper-qv4WiB')
            if wrappers and any(w.is_displayed() for w in wrappers):
                skip_btns = driver.find_elements(By.CSS_SELECTOR, '.skip-mrkR37')
                for btn in skip_btns:
                    if btn.is_displayed():
                        try_click(driver, btn, "Skip khảo sát vai trò")
                        log("Đã bấm Skip modal khảo sát!", "OK")
                        time.sleep(1)
                        return True
        except Exception as e:
            log(f"Lỗi kiểm tra modal khảo sát: {e}", "WARN")
        time.sleep(1)
    log("Không thấy modal khảo sát vai trò (bỏ qua).", "INFO")
    return False

def step_close_whats_new(driver, timeout=15):
    from selenium.webdriver.common.by import By
    log("Kiểm tra các popup (What's new/Modal) cần đóng...", "INFO")
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Tìm tất cả các nút đóng modal
            close_btns = driver.find_elements(By.CSS_SELECTOR, '.lv-modal-close-icon, svg.lv-icon-lv-close')
            clicked = False
            for btn in close_btns:
                if btn.is_displayed():
                    try_click(driver, btn, "Đóng modal popup")
                    log("Đã đóng một popup!", "OK")
                    time.sleep(1)
                    clicked = True
            if clicked:
                return True
        except Exception as e:
            pass
        time.sleep(1)
    log("Không thấy popup nào cần đóng (bỏ qua).", "INFO")
    return False

def step_click_upgrade(driver, timeout=10):
    """Bấm nút Upgrade ở header"""
    from selenium.webdriver.common.by import By
    log("Đang tìm nút Upgrade...", "INFO")
    start = time.time()
    while time.time() - start < timeout:
        try:
            upgrade_btns = driver.find_elements(By.CSS_SELECTOR, '[data-id="TitleBarUpgradeVip"] .LvHeaderUpgradeVipNew')
            if not upgrade_btns:
                upgrade_btns = driver.find_elements(By.CSS_SELECTOR, '[data-id="TitleBarUpgradeVip"]')
            for btn in upgrade_btns:
                if btn.is_displayed():
                    try_click(driver, btn, "Upgrade")
                    log("Đã bấm nút Upgrade!", "OK")
                    time.sleep(2)
                    return True
        except Exception as e:
            log(f"Lỗi tìm nút Upgrade: {e}", "WARN")
        time.sleep(1)
    log("Không tìm thấy nút Upgrade (bỏ qua).", "WARN")
    return False

def step5_join_team(driver, join_link):
    from selenium.webdriver.common.by import By
    log("Bước 5: Vào link Join Team...", "INFO")
    try:
        driver.get(join_link)
        time.sleep(3)
        btns = driver.find_elements(By.CSS_SELECTOR, 'button[class*="JoinPanelBtn"], button[class*="join-button"], button[type="button"].lv-btn-primary')
        clicked = False
        
        for btn in btns:
            if btn.is_displayed():
                try_click(driver, btn, "Tham gia team (CSS JoinPanelBtn)")
                clicked = True
                break
                
        if not clicked:
            join_btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'Tham gia') or contains(text(), 'Join') or contains(text(), 'Submit')]")
            for btn in join_btns:
                if btn.is_displayed() and btn.is_enabled():
                    # Tránh click vào các thẻ không phải button nếu có thể
                    try_click(driver, btn, "Tham gia team (XPath Text)")
                    clicked = True
                    break
        time.sleep(3)
        return True
    except Exception as e:
        log(f"Không tham gia được team: {e}", "WARN")
        return False

def extract_uidname(driver):
    import json
    log("Đang lấy uidname...", "INFO")
    try:
        script_content = driver.execute_script('return document.getElementById("__GTW_USER_INFO__")?.textContent;')
        if script_content:
            data = json.loads(script_content)
            if '__userInfoStringify' in data:
                inner = json.loads(data['__userInfoStringify'])
                uid = inner.get('data', {}).get('user_info', {}).get('nick_name', '')
                if uid: return uid
    except: pass
    try:
        from selenium.webdriver.common.by import By
        el = driver.find_element(By.CSS_SELECTOR, '.detail-item.nickname')
        if el: return el.text.strip()
    except: pass
    return ""

def wait_for_dashboard(driver, timeout=60):
    log("Chờ load trang dashboard (tối đa 60s)...", "INFO")
    start = time.time()
    while time.time() - start < timeout:
        try:
            url = driver.current_url
            # Chỉ khi URL chuyển qua my-cloud, my-edit, hoặc workspace thì mới tính là vào team thành công
            if "my-edit" in url or "workspace" in url or "my-cloud" in url:
                log("Đã vào workspace / team thành công", "OK")
                time.sleep(4) # Chờ cho trang load hẳn để lấy UID
                return True
        except Exception:
            pass
        time.sleep(1)
    log("Hết thời gian chờ load dashboard (mạng quá yếu)!", "WARN")
    return False

def save_account(uidname, email, password, join_link, msToken=""):
    if not uidname: uidname = email.split('@')[0]
    line = f"{uidname}\t{email}\t{password}\t{join_link}\t{msToken}"
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    log(f"Đã lưu tài khoản → {OUTPUT_FILE}", "OK")

def update_account_payment_link(email, link=None, has_trial=False, uudai=None):
    try:
        import sqlite3
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database.db"))
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            uudai_val = str(uudai) if uudai is not None else ("trial_7day" if has_trial else "")
            if link:
                cur.execute("UPDATE accounts SET join_link = ?, uudai = ? WHERE app = 'capcut' AND email = ?", (link, uudai_val, email))
            else:
                cur.execute("UPDATE accounts SET uudai = ? WHERE app = 'capcut' AND email = ?", (uudai_val, email))
            conn.commit()
            conn.close()
            if link:
                log(f"Đã lưu link thanh toán vào Database cho {email} (Ưu đãi: {uudai_val})", "OK")
    except Exception as e:
        log(f"Lỗi update DB payment link: {e}", "WARN")

ACTIVE_DRIVERS = []




def api_upgrade_vip(driver):
    from selenium.webdriver.common.by import By
    import time
    log("Đang thực hiện nhận VIP qua giao diện để lấy link cashier...", "INFO")
    
    # 1. Bấm nút Nâng cấp trên header
    clicked_header = False
    start = time.time()
    while time.time() - start < 15:
        try:
            upgrade_btns = driver.find_elements(By.CSS_SELECTOR, '[data-id="TitleBarUpgradeVip"] .LvHeaderUpgradeVipNew, .LvHeaderUpgradeVipNew')
            if not upgrade_btns:
                upgrade_btns = driver.find_elements(By.CSS_SELECTOR, '[data-id="TitleBarUpgradeVip"]')
            for btn in upgrade_btns:
                if btn.is_displayed():
                    try_click(driver, btn, "Nâng cấp (Header)")
                    clicked_header = True
                    break
            if clicked_header:
                break
        except Exception as e:
            pass
        time.sleep(1)
        
    if not clicked_header:
        log("Không tìm thấy nút Upgrade trên Header (bỏ qua).", "WARN")
        return ""
        
    time.sleep(2)
    
    # 2. Chờ modal Chọn gói hiện lên và bấm Nâng cấp (Gói Pro)
    log("Đang chờ modal Nâng cấp hiện ra...", "INFO")
    clicked_modal = False
    start = time.time()
    while time.time() - start < 15:
        try:
            action_btns = driver.find_elements(By.CSS_SELECTOR, '.subscriptionProductSection-pro button.subscriptionProductSection-actionDark, button.subscriptionProductSection-actionGradient')
            for btn in action_btns:
                if btn.is_displayed() and btn.is_enabled():
                    try_click(driver, btn, "Nâng cấp (Trong Modal Gói Pro)")
                    clicked_modal = True
                    break
            if clicked_modal:
                break
        except Exception as e:
            pass
        time.sleep(1)
        
    if not clicked_modal:
        log("Không tìm thấy nút xác nhận Nâng cấp trong Modal!", "WARN")
        return ""
        
# 3. Đợi iframe Pipo (Cashier) xuất hiện hoặc trang chuyển hướng và lấy link src
    log("Đã bấm nâng cấp, đang chờ link thanh toán xuất hiện...", "INFO")
    start = time.time()
    while time.time() - start < 20:
        try:
            # Kiểm tra URL hiện tại
            if "pipopay.com" in driver.current_url:
                log("Đã lấy được link cashier_url từ URL hiện tại!", "OK")
                return driver.current_url
                
            # Kiểm tra các tab khác
            original_window = driver.current_window_handle
            for handle in driver.window_handles:
                if handle != original_window:
                    driver.switch_to.window(handle)
                    if "pipopay.com" in driver.current_url:
                        url = driver.current_url
                        driver.switch_to.window(original_window)
                        log("Đã lấy được link cashier_url từ tab mới!", "OK")
                        return url
                    driver.switch_to.window(original_window)
                    
            # Kiểm tra iframe
            iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='pipopay.com'], iframe[src*='cashier']")
            for iframe in iframes:
                src = iframe.get_attribute("src")
                if src and "pipopay.com" in src:
                    log("Đã lấy được link cashier_url từ iframe thành công!", "OK")
                    return src
        except:
            pass
        time.sleep(1)
        
    log("Không tìm thấy link thanh toán pipopay sau khi bấm Nâng cấp!", "WARN")
    return ""
        
    time.sleep(2)
    
    # 2. Chờ modal Chọn gói hiện lên và bấm Nâng cấp (Gói Pro)
    log("Đang chờ modal Nâng cấp hiện ra...", "INFO")
    clicked_modal = False
    start = time.time()
    while time.time() - start < timeout:
        try:
            action_btns = driver.find_elements(By.CSS_SELECTOR, '.subscriptionProductSection-pro button.subscriptionProductSection-actionDark, button.subscriptionProductSection-actionGradient')
            for btn in action_btns:
                if btn.is_displayed() and btn.is_enabled():
                    try_click(driver, btn, "Nâng cấp (Trong Modal Gói Pro)")
                    clicked_modal = True
                    break
            if clicked_modal:
                log("Đã bấm nhận VIP 0đ thành công qua giao diện!", "OK")
                time.sleep(3)
                return True
        except Exception as e:
            pass
        time.sleep(1)
        
    log("Không tìm thấy nút xác nhận Nâng cấp trong Modal!", "WARN")
    return False


def step_get_payment_link(driver, email, password, save_trial_7day=False):
    import time
    for attempt in range(5):
        res = _do_get_payment_link(driver, email, password, attempt, save_trial_7day=save_trial_7day)
        if res == "TOAST_ERROR":
            log("⚠️ Phát hiện toast lỗi (lv-message-wrapper)! Mở tab mới thử lại liền...", "WARN")
            driver.execute_script("window.open('https://www.capcut.com/vi-vn/login', '_blank');")
            time.sleep(1)
            driver.switch_to.window(driver.window_handles[-1])
            try: driver.maximize_window()
            except: pass
            time.sleep(5)
            continue
        return res
    return None

def _check_cashier_trial_dom(driver):
    """
    Kiểm tra DOM trang Pipopay cashier (trong iframe, trong window khác hoặc current page)
    để phát hiện gói Trial 7 ngày theo đúng cấu trúc HTML pipo checkout:
    - 'Gói Pro theo tháng (dùng thử miễn phí 7 ngày)'
    - 'Miễn phí trong 7 ngày' / 'Dùng thử'
    - 'Bắt đầu dùng thử miễn phí' (trên pay-button)
    - 'Thời hạn dùng thử miễn phí của bạn sẽ kết thúc vào ngày...'
    - 'Đến hạn hôm nay' + 0₫
    """
    from selenium.webdriver.common.by import By
    import time

    trial_phrases = [
        "dùng thử miễn phí 7 ngày",
        "miễn phí trong 7 ngày",
        "bắt đầu dùng thử miễn phí",
        "thời hạn dùng thử miễn phí",
        "dùng thử miễn phí",
        "7-day free trial",
        "7 day free trial",
        "free trial for 7 days",
        "start free trial",
        "free for 7 days",
        "7-day trial"
    ]

    def _inspect_context(d):
        try:
            body_elem = d.find_element(By.TAG_NAME, "body")
            body_text = (body_elem.text or "").lower()
            if not body_text:
                return False, ""

            for phrase in trial_phrases:
                if phrase in body_text:
                    return True, f"Khớp cụm từ '{phrase}'"

            pay_btns = d.find_elements(By.CSS_SELECTOR, ".pay-button, .element-pay-button-wrapper button, button.pipo-button")
            for b in pay_btns:
                b_txt = (b.text or "").lower()
                if "dùng thử" in b_txt or "trial" in b_txt:
                    return True, f"Nút thanh toán: '{b_txt.strip()}'"

            summary_els = d.find_elements(By.CSS_SELECTOR, ".order-summary, .element-order-summary-pipo-list, .order-summary-value, .amount-item")
            for s in summary_els:
                s_txt = (s.text or "").lower()
                for phrase in trial_phrases:
                    if phrase in s_txt:
                        return True, f"Order summary: '{phrase}'"
                if "dùng thử" in s_txt or "trial" in s_txt:
                    return True, f"Order summary item: '{s_txt.strip()}'"

            if ("đến hạn hôm nay" in body_text or "due today" in body_text) and any(z in body_text for z in ["0₫", "0 ₫", "0đ", "0 đ", "$0", "0$"]) and ("dùng thử" in body_text or "trial" in body_text or "miễn phí" in body_text):
                return True, "Đến hạn hôm nay 0đ + có dùng thử"
        except Exception:
            pass
        return False, ""

    # 1. Quét iframe trên trang hiện tại
    try:
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='pipopay.com'], iframe[src*='cashier'], iframe[src*='agreement-cashier'], iframe")
        for iframe in iframes:
            try:
                src = iframe.get_attribute("src") or ""
                if "pipopay.com" in src or "cashier" in src or len(iframes) <= 4:
                    driver.switch_to.frame(iframe)
                    found, reason = _inspect_context(driver)
                    driver.switch_to.default_content()
                    if found:
                        return True, f"Iframe Cashier ({reason})"
            except Exception:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Quét tất cả các tab / window
    orig_handle = driver.current_window_handle
    for h in driver.window_handles:
        try:
            driver.switch_to.window(h)
            curr_url = (driver.current_url or "").lower()
            if "pipopay.com" in curr_url or "cashier" in curr_url or len(driver.window_handles) > 1:
                found, reason = _inspect_context(driver)
                if found:
                    driver.switch_to.window(orig_handle)
                    return True, f"Tab ({reason})"

                try:
                    nested_iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='pipopay.com'], iframe")
                    for n_if in nested_iframes:
                        try:
                            driver.switch_to.frame(n_if)
                            n_found, n_reason = _inspect_context(driver)
                            driver.switch_to.default_content()
                            if n_found:
                                driver.switch_to.window(orig_handle)
                                return True, f"Iframe trong Tab ({n_reason})"
                        except Exception:
                            driver.switch_to.default_content()
                except Exception:
                    pass
        except Exception:
            pass
    try:
        driver.switch_to.window(orig_handle)
    except Exception:
        pass

    # 3. Quét trực tiếp trang hiện tại
    try:
        found, reason = _inspect_context(driver)
        if found:
            return True, f"Trang hiện tại ({reason})"
    except Exception:
        pass

    return False, ""


def _do_get_payment_link(driver, email, password, attempt=0, save_trial_7day=False):
    try:
        from selenium.webdriver.common.by import By
        import time
        import os

        payment_url = None
        def _check_manual_payment(d):
            try:
                if "pipopay.com" in d.current_url or "buy.stripe.com" in d.current_url: return d.current_url
                for iframe in d.find_elements(By.CSS_SELECTOR, "iframe[src*='pipopay.com'], iframe[src*='stripe.com']"):
                    src = iframe.get_attribute("src")
                    if src and ("pipopay.com" in src or "stripe.com" in src): return src
                orig = d.current_window_handle
                for h in d.window_handles:
                    if h != orig:
                        d.switch_to.window(h)
                        if "pipopay.com" in d.current_url or "buy.stripe.com" in d.current_url:
                            u = d.current_url
                            d.switch_to.window(orig)
                            return u
                        d.switch_to.window(orig)
            except: pass
            return None

        has_7day_trial = False

        if attempt == 0:
            # Reload lại trang để React mount lại sạch, không bị rác popup
            log("Reload trang để lấy UI sạch...", "INFO")
            current_url = driver.current_url
            if "my-edit" not in current_url and "workspace" not in current_url and "capcut.com" not in current_url:
                driver.get("https://www.capcut.com/vi-vn/login")
            else:
                driver.refresh()
            time.sleep(7)

        # Kiểm tra trang bị ban "hoạt động bất thường" → mở tab mới để vượt qua
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            if "hoạt động bất thường" in page_text or "abnormal" in page_text.lower() or "không thể tiếp tục" in page_text:
                log("⚠️ Phát hiện trang BLOCK 'hoạt động bất thường'! Đang mở tab mới...", "WARN")
                driver.execute_script("window.open('https://www.capcut.com/vi-vn/login', '_blank');")
                time.sleep(3)
                driver.switch_to.window(driver.window_handles[-1])
                try: driver.maximize_window()
                except: pass
                time.sleep(6)
                log("✅ Đã mở tab mới và phóng to cửa sổ, tiếp tục lấy link trên tab sạch...", "INFO")
        except Exception as _ban_err:
            pass

        # 1. Đóng các modal onboarding nếu có (What's new, Seedance, v.v.)
        for _ in range(2):
            try:
                # Đóng nút "Bỏ qua", "Skip", "Đã hiểu", close icon
                skip_btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'Bỏ qua') or contains(text(), 'Skip') or contains(text(), 'Đã hiểu')]")
                close_btns = driver.find_elements(By.CSS_SELECTOR, '.lv-modal-close-icon, button[aria-label="close"], .skip-mrkR37')
                for btn in skip_btns + close_btns:
                    if btn.is_displayed():
                        try_click(driver, btn, f"Đóng popup/onboarding")
                        time.sleep(1)
            except:
                pass
            time.sleep(1)

        log("Đang tìm nút Upgrade trên Header...", "INFO")
        
        # 1. Bấm nút Nâng cấp trên header
        clicked_header = False
        start = time.time()
        while time.time() - start < 20:
            payment_url = _check_manual_payment(driver)
            if payment_url:
                log("Đã phát hiện link thanh toán do click tay!", "OK")
                clicked_header = True
                break
            try:
                upgrade_btns = driver.find_elements(By.CSS_SELECTOR, '[data-id="TitleBarUpgradeVip"] .LvHeaderUpgradeVipNew, .LvHeaderUpgradeVipNew')
                if not upgrade_btns:
                    upgrade_btns = driver.find_elements(By.CSS_SELECTOR, '[data-id="TitleBarUpgradeVip"]')
                for btn in upgrade_btns:
                    if btn.is_displayed():
                        try_click(driver, btn, "Nâng cấp (Header)")
                        clicked_header = True
                        break
                if clicked_header:
                    break
            except Exception as e:
                pass
            time.sleep(1)
            
        if not clicked_header:
            log("Không tìm thấy nút Upgrade trên Header (bỏ qua).", "WARN")
            return None
            
        time.sleep(3)
        
        # 2. Chờ modal Chọn gói hiện lên và bấm Nâng cấp (Gói Pro)
        log("Đang chờ modal Nâng cấp hiện ra...", "INFO")
        clicked_modal = False
        start = time.time()
        while time.time() - start < 20:
            if not payment_url:
                payment_url = _check_manual_payment(driver)
            if payment_url:
                log("Đã phát hiện link thanh toán do click tay!", "OK")
                clicked_modal = True
                break
            try:
                # CHECK TOAST
                try:
                    toasts = driver.find_elements(By.CSS_SELECTOR, '.lv-message-wrapper.lv-message-wrapper-top')
                    for t in toasts:
                        if t.is_displayed():
                            return "TOAST_ERROR"
                except: pass

                # Nếu có popup "Bỏ qua" nhảy ra đè lên, click nó
                try:
                    skip_btns = driver.find_elements(By.XPATH, "//*[text()='Bỏ qua' or text()='Skip' or text()='Đã hiểu']")
                    for s_btn in skip_btns:
                        if s_btn.is_displayed():
                            try_click(driver, s_btn, "Dismiss Onboarding Popup")
                            time.sleep(1)
                            # Bấm lại Header vì popup làm mất modal
                            h_btns = driver.find_elements(By.CSS_SELECTOR, '.LvHeaderUpgradeVipNew, [data-id="TitleBarUpgradeVip"]')
                            for hb in h_btns:
                                if hb.is_displayed():
                                    try_click(driver, hb, "Re-click Nâng cấp (Header)")
                                    time.sleep(2)
                                    break
                except:
                    pass

                # [BƯỚC 1] Nhấn vào Tab 'Tháng' (Monthly) trước khi kiểm tra giá
                try:
                    monthly_tabs = driver.find_elements(By.XPATH, "//*[contains(text(), 'Tháng') or contains(text(), 'Monthly')]")
                    for mt in monthly_tabs:
                        if mt.is_displayed():
                            try_click(driver, mt, "Chọn Tab Gói Tháng")
                            time.sleep(1)
                            break
                except Exception:
                    pass

                # [BƯỚC 2] Quét tìm thẻ Pro và xác định mức giá (0đ, 22.000đ hay khác)
                target_pro_card = None
                card_text = ""
                try:
                    pro_cards = driver.find_elements(By.CSS_SELECTOR, '.subscriptionProductSection-pro, .subscriptionProductSection, [class*="pricing-card"], [class*="plan-card"], [class*="proSection"]')
                    for c in pro_cards:
                        if c.is_displayed():
                            txt = c.text or ""
                            if is_pro_pricing_card(txt):
                                target_pro_card = c
                                card_text = txt
                                if is_trial_7d_offer(txt):
                                    break
                except Exception:
                    pass

                modal_text = ""
                try:
                    modal_el = driver.find_element(By.CSS_SELECTOR, '.lv-modal, [role="dialog"], body')
                    modal_text = modal_el.text or ""
                except Exception:
                    pass

                # Trích xuất mức giá chính xác
                detected_price = extract_detected_price(card_text, modal_text)
                is_0d = (target_pro_card is not None and is_trial_7d_offer(card_text)) or detected_price == "0đ"
                is_22k = bool(re.search(r"(?<!\d)22[.,]000(?!\d)|(?<!\d)22000(?!\d)", card_text + " " + modal_text)) or "22" in detected_price

                price_label = "0đ (Trial 7 ngày)" if is_0d else ("22,000đ" if is_22k else detected_price)
                log(f"[{email}] 📊 Mức giá CapCut phát hiện: {price_label}", "INFO")
                record_pricing_status(email, price_label)
                update_account_payment_link(email, None, has_trial=is_0d, uudai=price_label)

                # [BƯỚC 3] Nếu bật chế độ CHỈ LẤY TRIAL 7 NGÀY (save_trial_7day=True) mà KHÔNG PHẢI 0đ
                if save_trial_7day and not is_0d:
                    log(f"[{email}] ℹ️ [CHẾ ĐỘ CHỈ LẤY TRIAL 7 NGÀY] Gói là {price_label} -> BỎ QUA không lấy link (đã lưu phân loại giá)!", "INFO")
                    # Đóng modal
                    try:
                        close_btns = driver.find_elements(By.CSS_SELECTOR, '.lv-modal-close-icon, button[aria-label="close"], .skip-mrkR37')
                        for cb in close_btns:
                            if cb.is_displayed():
                                try_click(driver, cb, "Đóng modal Nâng cấp")
                                break
                    except Exception:
                        pass
                    return None

                # [BƯỚC 4] Tìm nút bấm Nâng cấp trong thẻ Pro đã xác nhận
                upgrade_btn = None
                if target_pro_card:
                    try:
                        btns = target_pro_card.find_elements(By.CSS_SELECTOR, 'button')
                        for b in btns:
                            if b.is_displayed() and b.is_enabled():
                                upgrade_btn = b
                                break
                    except Exception:
                        pass

                if not upgrade_btn:
                    action_btns = driver.find_elements(By.CSS_SELECTOR, '.subscriptionProductSection-pro button, button.subscriptionProductSection-actionDark, button.subscriptionProductSection-actionGradient, [class*="actionDark"], [class*="actionGradient"]')
                    for b in action_btns:
                        if b.is_displayed() and b.is_enabled():
                            upgrade_btn = b
                            break

                if upgrade_btn:
                    try_click(driver, upgrade_btn, "Nâng cấp (Trong Thẻ Gói Pro)")
                    clicked_modal = True
                    break
            except Exception as e:
                pass
            time.sleep(1)
            
        if not clicked_modal:
            log("Không tìm thấy nút xác nhận Nâng cấp trong Modal!", "WARN")
            return None
            
        # 3. Đợi iframe Pipo (Cashier) xuất hiện hoặc trang chuyển hướng và lấy link src
        log("Đã bấm nâng cấp, đang chờ link thanh toán xuất hiện...", "INFO")
        start = time.time()
        while time.time() - start < 30 and not payment_url:
            try:
                # CHECK TOAST
                try:
                    toasts = driver.find_elements(By.CSS_SELECTOR, '.lv-message-wrapper.lv-message-wrapper-top')
                    for t in toasts:
                        if t.is_displayed():
                            return "TOAST_ERROR"
                except: pass

                # Kiểm tra URL hiện tại
                if "pipopay.com" in driver.current_url or "buy.stripe.com" in driver.current_url:
                    log("Đã lấy được link cashier_url từ URL hiện tại!", "OK")
                    payment_url = driver.current_url
                    break
                    
                # Kiểm tra các tab khác
                original_window = driver.current_window_handle
                for handle in driver.window_handles:
                    if handle != original_window:
                        driver.switch_to.window(handle)
                        if "pipopay.com" in driver.current_url or "buy.stripe.com" in driver.current_url:
                            url = driver.current_url
                            log("Đã lấy được link cashier_url từ tab mới!", "OK")
                            payment_url = url
                            break
                        driver.switch_to.window(original_window)
                if payment_url:
                    break
                        
                # Kiểm tra iframe
                iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='pipopay.com'], iframe[src*='cashier'], iframe[src*='stripe.com']")
                for iframe in iframes:
                    src = iframe.get_attribute("src")
                    if src and ("pipopay.com" in src or "stripe.com" in src):
                        log("Đã lấy được link cashier_url từ iframe thành công!", "OK")
                        payment_url = src
                        break
                if payment_url:
                    break
            except:
                pass
            time.sleep(1)
            
        if payment_url:
            # 1. NẾU LÀ TRIAL 7 NGÀY (is_0d): BẮT BUỘC xác minh trang checkout thật sự là 0đ
            if is_0d:
                log(f"[{email}] Đang quét DOM cashier Pipopay để xác minh số tiền đến hạn hôm nay là 0đ...", "INFO")
                is_verified_0d = verify_trial_checkout_dom(driver, timeout=12)
                if is_verified_0d:
                    with open("data/trial_7day.txt", "a", encoding="utf-8") as f:
                        f.write(f"{email}\t{password}\t{payment_url}\n")
                    with open("data/success_links.txt", "a", encoding="utf-8") as f:
                        f.write(f"{email}\t{password}\t{payment_url}\n")
                    log(f"🎉 [{email}] ĐÃ XÁC MINH VÀ LƯU VÀO data/trial_7day.txt: {payment_url}", "OK")
                    update_account_payment_link(email, payment_url, has_trial=True, uudai="trial_7day")
                    return payment_url
                else:
                    log(f"⚠️ [{email}] Trang checkout Pipopay KHÔNG PHẢI 0đ! Không lưu vào trial_7day.txt.", "WARN")
                    record_pricing_status(email, "checkout không phải 0đ")
                    update_account_payment_link(email, payment_url, has_trial=False, uudai="checkout_not_0d")
                    if not save_trial_7day:
                        with open("data/success_links.txt", "a", encoding="utf-8") as f:
                            f.write(f"{email}\t{password}\t{payment_url}\n")
                    return payment_url

            # 2. GÓI TRẢ PHÍ (22.000đ hoặc giá khác):
            with open("data/success_links.txt", "a", encoding="utf-8") as f:
                f.write(f"{email}\t{password}\t{payment_url}\n")
            log(f"✅ [{email}] Đã lưu link thanh toán ({price_label}) vào data/success_links.txt: {payment_url}", "OK")
            update_account_payment_link(email, payment_url, has_trial=False, uudai=price_label)
            return payment_url

        log("Không tìm thấy link thanh toán pipopay sau khi bấm Nâng cấp!", "WARN")
        return None

    except Exception as e:
        log(f"Lỗi lấy link: {e}", "ERR")
        return None


def step_logout_capcut(driver, timeout=20):
    """
    Bước 7 & 8:
    - Tìm và click avatar / menu tài khoản CapCut trên Header
    - Bấm 'Đăng xuất' trong menu dropdown
    - Xác nhận đăng xuất trong modal xác nhận
    - Chờ 3 giây
    - Trả về True nếu xác nhận đăng xuất thành công, False nếu chưa
    """
    from selenium.webdriver.common.by import By
    import time
    log("Đang tiến hành đăng xuất khỏi CapCut...", "INFO")

    # Đóng modal/popup che màn hình nếu có
    try:
        close_btns = driver.find_elements(By.CSS_SELECTOR, '.lv-modal-close-icon, svg.lv-icon-lv-close, button[aria-label="close"], .skip-mrkR37')
        for cb in close_btns:
            if cb.is_displayed():
                try_click(driver, cb, "Đóng popup trước đăng xuất")
                time.sleep(1)
    except: pass

    # 1. Tìm và bấm Avatar trên Header
    avatar_clicked = False
    start = time.time()
    while time.time() - start < timeout:
        avatar_selectors = [
            '[data-id="TitleBarAvatar"]',
            '[data-id*="Avatar"]',
            '[data-id="TitleBarUserInfo"]',
            '[data-id*="UserInfo"]',
            '.LvHeaderAvatar',
            '.lv-header-avatar',
            '[class*="headerAvatar"]',
            '[class*="HeaderAvatar"]',
            '.lv-avatar',
            'img.lv-avatar-img',
            '.user-avatar',
            'img[class*="avatar"]',
            '[class*="user-profile"]',
            '.detail-item.nickname'
        ]
        for sel in avatar_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    if el.is_displayed():
                        try_click(driver, el, f"Avatar ({sel})")
                        avatar_clicked = True
                        time.sleep(1.5)
                        break
                if avatar_clicked:
                    break
            except: pass
        if avatar_clicked:
            break

        # Fallback Javascript click
        try:
            clicked_js = driver.execute_script('''
                var el = document.querySelector('[data-id*="Avatar"]') || 
                         document.querySelector('.lv-avatar') || 
                         document.querySelector('[class*="avatar"]') ||
                         document.querySelector('header img') ||
                         document.querySelector('.detail-item.nickname');
                if (el) { el.click(); return true; }
                return false;
            ''')
            if clicked_js:
                avatar_clicked = True
                time.sleep(1.5)
                break
        except: pass
        time.sleep(1)

    if not avatar_clicked:
        log("Không tìm thấy nút Avatar / Tài khoản trên header!", "WARN")
        return False

    # 2. Bấm 'Đăng xuất' trong Dropdown Menu
    logout_clicked = False
    start = time.time()
    while time.time() - start < 10:
        try:
            logout_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Đăng xuất') or contains(text(), 'Log out') or contains(text(), 'Logout') or contains(text(), 'Sign out')]")
            for el in logout_elements:
                if el.is_displayed():
                    try_click(driver, el, "Mục Đăng xuất")
                    logout_clicked = True
                    time.sleep(1.5)
                    break
            if logout_clicked:
                break
        except: pass

        # Fallback CSS
        try:
            items = driver.find_elements(By.CSS_SELECTOR, '.lv-dropdown-menu-item, [class*="dropdown-item"], [class*="menu-item"]')
            for it in items:
                t = it.text.lower()
                if "đăng xuất" in t or "log out" in t or "logout" in t or "sign out" in t:
                    if it.is_displayed():
                        try_click(driver, it, "Dropdown item Đăng xuất")
                        logout_clicked = True
                        time.sleep(1.5)
                        break
            if logout_clicked:
                break
        except: pass
        time.sleep(1)

    if not logout_clicked:
        log("Không tìm thấy mục Đăng xuất trong menu tài khoản!", "WARN")
        return False

    # 3. Xác nhận đăng xuất trong modal xác nhận
    confirm_clicked = False
    start = time.time()
    while time.time() - start < 10:
        try:
            confirm_btns = driver.find_elements(By.XPATH, "//div[contains(@class, 'lv-modal') or @role='dialog']//button[contains(., 'Đăng xuất') or contains(., 'Xác nhận') or contains(., 'Log out') or contains(., 'Confirm') or contains(., 'OK')]")
            if not confirm_btns:
                confirm_btns = driver.find_elements(By.CSS_SELECTOR, '.lv-modal button.lv-btn-primary, .lv-modal button.lv-btn-danger, [role="dialog"] button.lv-btn-primary')
            for cb in confirm_btns:
                if cb.is_displayed():
                    try_click(driver, cb, "Xác nhận Đăng xuất (Modal)")
                    confirm_clicked = True
                    break
            if confirm_clicked:
                break
        except: pass
        time.sleep(1)

    if not confirm_clicked:
        log("Không thấy modal xác nhận đăng xuất hoặc không bấm được nút xác nhận!", "WARN")
        return False

    # Bước 8: Xác nhận đăng xuất -> chờ 3 giây -> đóng tab tài khoản
    log("Đã bấm xác nhận đăng xuất thành công. Đang chờ 3 giây...", "OK")
    time.sleep(3)
    return True


def close_checkout_and_logout(driver, email):
    """
    Bước 7 & 8:
    7. Đóng checkout, về tab tài khoản và đăng xuất.
    8. Xác nhận đăng xuất -> chờ 3 giây -> đóng tab tài khoản.
    """
    import time
    log(f"[{email}] Bắt đầu Bước 7: Đóng checkout và chuyển về tab tài khoản...", "INFO")
    try:
        handles = driver.window_handles
        capcut_handle = None
        checkout_handles = []

        for h in handles:
            try:
                driver.switch_to.window(h)
                u = driver.current_url.lower()
                if "pipopay.com" in u or "buy.stripe.com" in u or "cashier" in u:
                    checkout_handles.append(h)
                elif "capcut.com" in u:
                    if not capcut_handle:
                        capcut_handle = h
            except: pass

        # Đóng tab checkout
        for ch in checkout_handles:
            try:
                driver.switch_to.window(ch)
                driver.close()
                log(f"[{email}] Đã đóng tab checkout PipoPay.", "INFO")
            except: pass

        # Về lại tab tài khoản Capcut
        remaining = driver.window_handles
        if capcut_handle and capcut_handle in remaining:
            driver.switch_to.window(capcut_handle)
        elif remaining:
            driver.switch_to.window(remaining[0])

        time.sleep(1.5)
        if "capcut.com" not in driver.current_url.lower():
            driver.get("https://www.capcut.com/my-edit")
            time.sleep(3)

        # Đăng xuất
        return step_logout_capcut(driver)
    except Exception as e:
        log(f"[{email}] Lỗi khi đóng checkout và đăng xuất: {e}", "WARN")
        return False


# ─── Retry lấy link cho acc đã tạo nhưng chưa lấy được link ─────────────────

NO_LINK_FILE = "data/no_link.json"

def save_pending_link(email, password, refresh_token, client_id, cookies):
    """Lưu acc thành công nhưng chưa lấy được link để retry sau."""
    import json, os
    os.makedirs("data", exist_ok=True)
    records = []
    if os.path.exists(NO_LINK_FILE):
        try:
            with open(NO_LINK_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except:
            records = []
    
    # Tránh lưu trùng email
    records = [r for r in records if r.get("email") != email]
    records.append({
        "email": email,
        "password": password,
        "refresh_token": refresh_token,
        "client_id": client_id,
        "cookies": cookies
    })
    with open(NO_LINK_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    log(f"Đã lưu acc {email} vào danh sách chờ lấy link ({NO_LINK_FILE})", "INFO")

def retry_get_payment_link_for_acc(email, password, refresh_token, client_id, cookies,
                                    headless=False, browser_type="chrome", mail_api_source="mixmmo",
                                    index=1, batch_size=1):
    """Thử lấy link thanh toán cho 1 acc đã lưu (dùng cookie, hoặc đăng nhập lại)."""
    log(f"[Retry #{index}] Đang xử lý: {email}", "INFO")
    driver = None
    try:
        proxy = get_rotated_proxy()
        driver = setup_driver(index, keep_open=False, use_api_proxy=True, batch_size=batch_size,
                              use_proxy=True, predefined_proxy=proxy,
                              headless=headless, browser_type=browser_type)
        ACTIVE_DRIVERS.append(driver)

        # Bước 1: Thử đăng nhập bằng cookie
        logged_in = False
        if cookies:
            try:
                driver.get("https://www.capcut.com")
                time.sleep(2)
                for ck in cookies:
                    try:
                        driver.add_cookie(ck)
                    except:
                        pass
                driver.get("https://www.capcut.com/vi-vn/login")
                time.sleep(5)
                url = driver.current_url
                if "my-edit" in url or "workspace" in url or "login" not in url:
                    log(f"[Retry] Cookie còn hạn! Đã đăng nhập {email} bằng cookie", "OK")
                    logged_in = True
                else:
                    log(f"[Retry] Cookie hết hạn cho {email}, sẽ đăng nhập lại...", "WARN")
            except Exception as e:
                log(f"[Retry] Lỗi load cookie: {e}", "WARN")

        # Bước 2: Đăng nhập lại bằng email/pass nếu cookie thất bại
        if not logged_in:
            try:
                driver.get("https://www.capcut.com/vi-vn/login")
                time.sleep(3)
                step0_dismiss_tos(driver)
                step0b_click_email_button(driver)
                step1_enter_email(driver, email)
                step2_enter_password(driver, password)
                # OTP nếu cần
                try:
                    from selenium.webdriver.common.by import By
                    wait_for_element(driver, By.CSS_SELECTOR, 
                        '.lv_sign_in_panel_wide-code-detail, .verification_code_input-wrapper', timeout=15)
                    log(f"[Retry] Cần OTP, đang lấy từ {mail_api_source.upper()}...", "INFO")
                    time.sleep(5)
                    otp = wait_for_otp(email, password, refresh_token, client_id, 
                                       timeout=90, interval=4, mail_api_source=mail_api_source)
                    if otp:
                        otp_input = driver.find_element(By.CSS_SELECTOR,
                            'input[maxlength="6"], .lv_sign_in_panel_wide-code-detail input')
                        set_react_input(driver, otp_input, otp)
                        log(f"[Retry] Đã nhập OTP: {otp}", "OK")
                        time.sleep(3)
                    else:
                        log(f"[Retry] Không lấy được OTP cho {email}!", "ERR")
                        return False
                except Exception:
                    pass  # Không có màn hình OTP → có thể đã đăng nhập
                
                step5_open_capcut(driver)
                if not wait_for_dashboard(driver, timeout=45):
                    log(f"[Retry] Không vào được dashboard sau đăng nhập lại!", "ERR")
                    return False
                log(f"[Retry] Đăng nhập lại thành công cho {email}", "OK")
                logged_in = True
            except Exception as e:
                log(f"[Retry] Lỗi đăng nhập lại: {e}", "ERR")
                return False

        if not logged_in:
            return False

        # Bước 3: Lấy link thanh toán
        link = step_get_payment_link(driver, email, password)
        if link:
            log(f"[Retry] ✅ Lấy được link cho {email}: {link[:60]}...", "OK")
            return True
        else:
            log(f"[Retry] Không lấy được link cho {email}", "ERR")
            return False

    except Exception as e:
        log(f"[Retry] Lỗi không mong muốn: {e}", "ERR")
        return False
    finally:
        if driver:
            try:
                if hasattr(driver, '_proxy_relay') and driver._proxy_relay:
                    driver._proxy_relay.stop()
                if driver in ACTIVE_DRIVERS: ACTIVE_DRIVERS.remove(driver)
                driver.quit()
            except: pass


def register_one_account(index, join_link=None, keep_open=False, batch_size=3, predefined_proxy=None, headless=False, browser_type="chrome", get_link=False, mail_api_source="mixmmo", incognito=False, save_trial_7day=False, **kwargs):
    try:
        acc = HOTMAIL_QUEUE.get_nowait()
    except queue.Empty:
        log(f"Acc #{index}: Hết hotmail trong hàng đợi!", "ERR")
        return False
        
    email = acc["email"]

    # [TỐI ƯU Tool 2] Bỏ qua ngay nếu email này đã đăng ký thành công trước đó
    if email.strip().casefold() in registered_emails():
        log(f"[{email}] ĐÃ ĐĂNG KÝ TRƯỚC ĐÓ (tìm thấy trong registered.jsonl) -> Bỏ qua!", "WARN")
        prune_registered_accounts()
        return True

    email_pass = acc["pass"]
    refresh_token = acc["refresh_token"]
    client_id = acc["client_id"]
    password = get_settings_from_db().get("CAPCUT_PASSWORD", "capcut123") or "capcut123"

    # [TỐI ƯU Tool 2] Chụp snapshot hòm thư trước khi đăng ký để lọc sạch OTP cũ
    snapshot = snapshot_mail_before_register(email, email_pass, refresh_token, client_id, mail_api_source)

    driver = None
    should_keep_open = keep_open and not get_link and not save_trial_7day
    try:
        max_retries = 3

        for attempt in range(max_retries):
            driver = setup_driver(index, keep_open, use_api_proxy=True, batch_size=batch_size, use_proxy=True, predefined_proxy=predefined_proxy, incognito=incognito, headless=headless, browser_type=browser_type)
            ACTIVE_DRIVERS.append(driver)
            log(f"[{email}] Bắt đầu mở trình duyệt... (Lần thử {attempt+1})", "INFO")
            
            try:
                driver.get("https://www.capcut.com/vi-vn/login")
                break
            except Exception as e:
                if "ERR_TUNNEL_CONNECTION_FAILED" in str(e) or "ERR_PROXY_CONNECTION_FAILED" in str(e) or "TimeoutException" in type(e).__name__:
                    if attempt < max_retries - 1:
                        log(f"[{email}] Lỗi kết nối/proxy ({type(e).__name__}). Đang thử lại lần {attempt+2}/{max_retries}... (Không xoay proxy chung giữa chừng)", "WARN")
                        try:
                            if hasattr(driver, '_proxy_relay') and driver._proxy_relay:
                                driver._proxy_relay.stop()
                            if driver in ACTIVE_DRIVERS: ACTIVE_DRIVERS.remove(driver)
                            driver.quit()
                        except: pass
                        time.sleep(3)
                    else:
                        raise e
                else:
                    raise e
                    
        time.sleep(3)

        step0_dismiss_tos(driver)
        step0b_click_email_button(driver)
        step1_enter_email(driver, email)
        step2_enter_password(driver, password)
        bday_status = step3_enter_birthday(driver)
        if bday_status != "ALREADY_LOGGED_IN":
            if not step4_enter_otp(driver, email, email_pass, refresh_token, client_id, mail_api_source, snapshot=snapshot):
                log(f"[{email}] Bỏ qua email này do không lấy được OTP / lỗi Hotmail API!", "WARN")
                mark_hotmail_failed(acc, reason="OTP_FAILED_OR_TOKEN_ERROR")
                return False

        msToken = ""
        try:
            for cookie in driver.get_cookies():
                if cookie['name'] == 'msToken':
                    msToken = cookie['value']
                    break
        except: pass

        should_keep_open = keep_open and not get_link and not save_trial_7day
        link = None

        if join_link:
            if bday_status != "ALREADY_LOGGED_IN":
                step5_join_team(driver, join_link)
            if not wait_for_dashboard(driver):
                log("Không thể join team (bị kẹt ở trang join) -> HỦY LƯU TÀI KHOẢN NÀY!", "ERR")
                return False
                
            uidname = extract_uidname(driver)
            save_account(uidname, email, password, join_link, msToken)
            record_registered_account(email, "signup_join_ok", capcut_password=password)
            log(f"ĐĂNG KÝ & JOIN THÀNH CÔNG! {email} (UID: {uidname})", "OK")
        else:
            if bday_status != "ALREADY_LOGGED_IN":
                step5_open_capcut(driver)
            if not wait_for_dashboard(driver):
                log("Không vào được CapCut -> HỦY LƯU!", "ERR")
                return False
                
            uidname = extract_uidname(driver)
            log(f"ĐĂNG NHẬP / ĐĂNG KÝ THÀNH CÔNG! {email} (UID: {uidname})", "OK")

            # Bước 3: Lưu tài khoản ngay sau khi tạo xong (UID + thông tin)
            save_account(uidname, email, password, "", msToken)
            record_registered_account(email, "signup_verified", capcut_password=password)

            # Bước 4: Đóng popup/hướng dẫn
            log("Đang xử lý các popup sau đăng ký...", "INFO")
            step_skip_role_survey(driver, timeout=10)
            step_close_whats_new(driver, timeout=15)

            if get_link or save_trial_7day:
                # Bước 5 & 6: Bấm nâng cấp trong thẻ Pro, lấy URL checkout và lưu file + database
                link = step_get_payment_link(driver, email, password, save_trial_7day=save_trial_7day)
                if link:
                    # Bước 7 & 8: Đóng checkout, về tab tài khoản và đăng xuất -> xác nhận đăng xuất -> chờ 3s -> đóng tab
                    logout_ok = close_checkout_and_logout(driver, email)
                    if not logout_ok:
                        log(f"[{email}] ⚠️ Chưa xác nhận đăng xuất được! Đóng tab để tránh lag máy.", "WARN")
                    else:
                        log(f"[{email}] ✅ Đã lưu link và đăng xuất thành công -> Đóng tab tài khoản.", "OK")
                    should_keep_open = False
                else:
                    log(f"[{email}] ⚠️ Chưa lưu được link checkout! Đóng tab để tránh lag máy.", "WARN")
                    should_keep_open = False
                    # Lưu cookie để retry sau
                    try:
                        cookies = driver.get_cookies()
                        save_pending_link(email, password, refresh_token, client_id, cookies)
                        log(f"Đã lưu cookie acc {email} để retry lấy link sau!", "WARN")
                    except Exception as ck_err:
                        log(f"Không lưu được cookie: {ck_err}", "WARN")

        # Chỉ đánh dấu hotmail đã dùng khi mọi thứ đều thành công
        if (not get_link and not save_trial_7day) or link:
            mark_hotmail_used(acc)
            record_registered_account(email, "completed", capcut_password=password)
            return True
        else:
            return False

    except Exception as e:
        log(f"LỖI KHÔNG MONG MUỐN: {type(e).__name__}: {e}", "ERR")
        if driver:
            try:
                driver.save_screenshot(f"error_{index}.png")
                log(f"Đã lưu ảnh màn hình lỗi: error_{index}.png", "INFO")
            except: pass
        return False
    finally:
        if driver and not should_keep_open:
            try:
                if hasattr(driver, '_proxy_relay') and driver._proxy_relay:
                    driver._proxy_relay.stop()
            except: pass
            try:
                if driver in ACTIVE_DRIVERS:
                    ACTIVE_DRIVERS.remove(driver)
            except: pass
            try:
                driver.quit()
                log("Đã đóng trình duyệt.", "INFO")
            except: pass
        elif driver and should_keep_open:
            log(f"[{email}] ℹ️ Giữ tab trình duyệt để xử lý tiếp theo quy định.", "INFO")


def load_hotmails_to_queue(limit=None):
    import os
    if not os.path.exists(HOTMAIL_FILE):
        log(f"Không tìm thấy file {HOTMAIL_FILE}", "ERR")
        return 0

    # Lọc trước email đã đăng ký thành công khỏi hotmails.txt
    pruned = prune_registered_accounts()
    if pruned:
        log(f"Đã tự động loại {pruned} tài khoản đã đăng ký trước đó khỏi {HOTMAIL_FILE}.", "INFO")

    already_done = registered_emails()

    # Xóa queue cũ (nếu có)
    while not HOTMAIL_QUEUE.empty():
        try: HOTMAIL_QUEUE.get_nowait()
        except: break

    count = 0
    with open(HOTMAIL_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = line.split("|")
            if len(parts) >= 4:
                email = parts[0].strip()
                if email.casefold() in already_done:
                    continue

                HOTMAIL_QUEUE.put({
                    "email": email,
                    "pass": parts[1].strip(),
                    "refresh_token": parts[2].strip(),
                    "client_id": parts[3].strip(),
                    "original_line": line
                })

                count += 1
                if limit and count >= limit:
                    break
    log(f"Đã tải {count} hotmail hợp lệ vào hàng đợi từ {HOTMAIL_FILE}.", "OK")
    return count

def register_multiple(count, threads, join_link, keep_open=False, get_link=False, save_trial_7day=False):
    import concurrent.futures
    results = {"ok": 0, "fail": 0}
    
    batch_size = max(1, int(threads))
    total_processed = 0
    batch_num = 0

    log(f"--- BẮT ĐẦU: Chạy tối đa {count} tài khoản theo từng lượt {batch_size} luồng ---", "WARN")

    while total_processed < count and not HOTMAIL_QUEUE.empty():
        batch_num += 1
        curr_batch = min(batch_size, count - total_processed, HOTMAIL_QUEUE.qsize())
        if curr_batch <= 0:
            break

        log(f"\n🔄 === BẮT ĐẦU LƯỢT {batch_num}: Chạy {curr_batch} tài khoản song song ===", "INFO")

        def worker(slot_idx):
            time.sleep((slot_idx % batch_size) * 2.5)
            log(f"Luồng {slot_idx+1}/{curr_batch} bắt đầu xử lý tài khoản...", "INFO")
            res = register_one_account(slot_idx + 1, join_link, keep_open, batch_size=batch_size, get_link=get_link, save_trial_7day=save_trial_7day)
            return bool(res)

        with concurrent.futures.ThreadPoolExecutor(max_workers=curr_batch) as executor:
            futures = [executor.submit(worker, i) for i in range(curr_batch)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    if res: results["ok"] += 1
                    else: results["fail"] += 1
                except:
                    results["fail"] += 1

        total_processed += curr_batch
        log(f"✅ Hoàn thành lượt {batch_num}. Tổng tích luỹ: {results['ok']} OK / {results['fail']} Lỗi.", "OK")

        if keep_open:
            break

        # Đảm bảo đóng toàn bộ trình duyệt còn sót lại sau mỗi lượt để không lag máy
        if not keep_open and ACTIVE_DRIVERS:
            for d in list(ACTIVE_DRIVERS):
                try:
                    if hasattr(d, '_proxy_relay') and d._proxy_relay:
                        d._proxy_relay.stop()
                    d.quit()
                except: pass
            ACTIVE_DRIVERS.clear()

        # Nếu còn tài khoản cần chạy tiếp -> Xoay proxy một lần và kiểm tra kết nối
        if total_processed < count and not HOTMAIL_QUEUE.empty():
            log("⏳ Đã kết thúc lượt, đang xoay proxy một lần cho lượt tiếp theo...", "INFO")
            try:
                new_p = get_rotated_proxy()
                log(f"Kiểm tra kết nối proxy mới ({new_p.get('host')}:{new_p.get('port')})...", "INFO")
                time.sleep(2)
            except Exception as e:
                log(f"Lỗi khi xoay proxy: {e}", "WARN")

    log(f"\n{'='*50}", "INFO")
    log(f"KẾT QUẢ TỔNG CỘNG: {results['ok']} thành công / {results['fail']} thất bại", "OK")
    log(f"{'='*50}\n", "INFO")

if __name__ == "__main__":
    print(f"""
{C.BOLD}{C.INFO}
╔══════════════════════════════════════════════════════╗
║      AUTO ĐĂNG KÝ TÀI KHOẢN CAPCUT (TERMINAL)        ║
║  Tích hợp: Tự động Join Team & Lưu vào Google Sheet  ║
╚══════════════════════════════════════════════════════╝
{C.RST}""")

    try:
        import selenium
    except ImportError:
        print("Đang cài đặt selenium...")
        os.system(f"{sys.executable} -m pip install selenium webdriver-manager requests -q")

    while True:
        print(f"\n{C.WARN}=== MENU CHỨC NĂNG ==={C.RST}")
        print("1. Chỉ tạo tài khoản ngẫu nhiên (Lưu vào file txt - GIỮ TAB MỞ ĐỂ TỰ THANH TOÁN)")
        print("2. Tạo tài khoản + Auto Join Team + Gửi lên Google Sheet")
        print("3. Tự động Tạo tài khoản + Đóng Popup + Lấy Link PipoPay (Treo máy)")
        choice_func = input(f"👉 Chọn 1, 2 hoặc 3: ").strip()

        if choice_func not in ["1", "2", "3"]:
            print(f"{C.ERR}Lựa chọn không hợp lệ! Vui lòng nhập 1, 2 hoặc 3.{C.RST}")
            continue

        join_link = None
        keep_open = False
        get_link = False
        try:
            if choice_func == "3":
                get_link = True
                keep_open = False
            elif choice_func == "2":
                join_link = input(f"\n{C.WARN}1. Nhập Link Join Team (Bắt buộc): {C.RST}").strip()
            else:
                keep_open = True
                
            count_input = input(f"{C.WARN}2. Nhập tổng số tài khoản muốn chạy: {C.RST}").strip()
            count = int(count_input) if count_input else 3
            
            threads_input = input(f"{C.WARN}3. Nhập số tab mở cùng lúc: {C.RST}").strip()
            threads = int(threads_input) if threads_input else 3
            
        except ValueError:
            print(f"{C.ERR}Số lượng phải là số nguyên! Thử lại.{C.RST}")
            continue

        log(f"Sẽ tạo {count} tài khoản, mở {threads} tab cùng lúc.", "INFO")

        if choice_func == "2":
            log(f"Tự động gửi thông tin lên Google Sheets và lưu vào {OUTPUT_FILE}.", "INFO")
        else:
            log(f"Chỉ lưu tài khoản vào file {OUTPUT_FILE} (Giữ tab mở để bạn tự thanh toán).", "INFO")
        print()

        loaded_count = load_hotmails_to_queue(limit=count)
        if loaded_count == 0:
            print(f"{C.ERR}Không có hotmail nào để chạy!{C.RST}")
            continue
        
        actual_count = loaded_count
        log(f"Sẽ chạy thực tế {actual_count} luồng dựa trên số lượng hotmail.", "INFO")

        if choice_func == "2":
            register_multiple(actual_count, threads, join_link, keep_open, get_link)
        else:
            # Chức năng 1: chạy từng đợt
            batch_count_idx = 1
            while not HOTMAIL_QUEUE.empty():
                log(f"--- ĐANG CHẠY ĐỢT {batch_count_idx} ---", "WARN")
                register_multiple(actual_count, threads, join_link, keep_open, get_link)
                
                if not HOTMAIL_QUEUE.empty():
                    if choice_func == "1":
                        print(f"\n{C.WARN}⚠️ Đã xong đợt {batch_count_idx}. Các tab vẫn đang mở để bạn tự thanh toán.{C.RST}")
                        input(f"{C.BOLD}👉 Bấm Enter để ĐÓNG các tab hiện tại và CHẠY ĐỢT TIẾP THEO: {C.RST}")
                    
                    if ACTIVE_DRIVERS:
                        log("Đang dọn dẹp các tab cũ trước khi qua đợt mới...", "INFO")
                        for d in ACTIVE_DRIVERS:
                            try:
                                if hasattr(d, '_proxy_relay') and d._proxy_relay:
                                    d._proxy_relay.stop()
                                d.quit()
                            except: pass
                        ACTIVE_DRIVERS.clear()
                batch_count_idx += 1

        
        print(f"\n{C.OK}✅ ĐÃ CHẠY XONG!{C.RST}")
        if not keep_open:
            print("Trình duyệt đã được tự động tắt để dọn RAM.")
        else:
            print(f"{C.WARN}⚠️ Các tab tạo tài khoản vẫn đang mở! Hãy tự tắt thủ công nếu cần.{C.RST}")
            
        choice = input(f"{C.BOLD}👉 Bấm Enter để TẠO THÊM đợt mới, hoặc gõ 'q' rồi Enter để THOÁT: {C.RST}")
        if choice.strip().lower() == 'q':
            if keep_open and ACTIVE_DRIVERS:
                log("Đang đóng toàn bộ các tab trình duyệt...", "INFO")
                for d in ACTIVE_DRIVERS:
                    try:
                        if hasattr(d, '_proxy_relay') and d._proxy_relay:
                            d._proxy_relay.stop()
                        d.quit()
                    except: pass
            print("Tạm biệt!")
            break
        else:
            if keep_open and ACTIVE_DRIVERS:
                log("Đang đóng các tab cũ trước khi mở đợt mới...", "INFO")
                for d in ACTIVE_DRIVERS:
                    try:
                        if hasattr(d, '_proxy_relay') and d._proxy_relay:
                            d._proxy_relay.stop()
                        d.quit()
                    except: pass
                ACTIVE_DRIVERS.clear()
