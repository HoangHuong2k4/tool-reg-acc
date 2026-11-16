#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CapCut Pro Checker - Universal Edition (Hỗ trợ cả Hotmail OAuth2 & AtomicMail)
Tự động quét và phát hiện thư xác nhận gói Pro monthly của CapCut từ các nguồn hòm thư.
Phân biệt chính xác giữa gói Pro đang hoạt động và gói ĐÃ BỊ HOÀN TIỀN / HỦY ĐƠN.
"""

import time
import json
import hashlib
import uuid
import queue
import threading
import requests
from typing import Optional, Dict, Any, List

# Import reader từ capcut_hotmail để tái sử dụng tối đa logic đọc Hotmail
from src.bots import capcut_hotmail as ch

REFUND_KEYWORDS = [
    "hoàn tiền", "đã được hoàn tiền", "đã bị hủy", "bị hủy", "hủy vì đơn hàng này đã được hoàn tiền",
    "bị hủy vì đơn hàng này đã được hoàn tiền",
    "refund", "refunded", "has been refunded", "was refunded", "order is refunded",
    "canceled", "cancelled", "cancellation", "order is cancelled", "order was cancelled",
    "order is canceled", "order was canceled"
]


class AtomicMailClient:
    API_BASE = "https://api.atomicmail.io/v1"

    def __init__(self, timeout: int = 15):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://atomicmail.io",
            "Referer": "https://atomicmail.io/app/login",
        })
        self.timeout = timeout
        self.user_id = None
        self.access_token = None

    @staticmethod
    def hash_password(password: str) -> str:
        password = password.strip()
        if len(password) == 64 and all(c in "0123456789abcdefABCDEF" for c in password):
            return password.lower()
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def extract_username(email_or_user: str) -> tuple:
        email_or_user = email_or_user.strip()
        if "@" in email_or_user:
            username, domain = email_or_user.split("@", 1)
            domain = domain.lower()
            if domain == "atomicmail.io":
                return username.strip(), False
            else:
                return email_or_user.lower(), True
        return email_or_user, False

    def sign_in(self, email_or_user: str, password_raw: str, device_id: Optional[str] = None) -> Dict[str, Any]:
        username, is_enterprise = self.extract_username(email_or_user)
        pw_hash = self.hash_password(password_raw)

        if not device_id:
            device_id = uuid.uuid4().hex

        payload = {
            "isEnterprise": is_enterprise,
            "username": username,
            "password": pw_hash,
            "platform": "web",
            "deviceId": device_id
        }

        url = f"{self.API_BASE}/auth/sign-in"
        resp = self.session.post(url, json=payload, timeout=self.timeout)

        if resp.status_code == 401 and len(password_raw.strip()) == 64:
            alt_hash = hashlib.sha256(password_raw.strip().encode("utf-8")).hexdigest()
            payload["password"] = alt_hash
            resp = self.session.post(url, json=payload, timeout=self.timeout)

        try:
            data = resp.json()
        except Exception:
            raise Exception(f"HTTP {resp.status_code}: Không parse được JSON ({resp.text[:100]})")

        if resp.status_code not in (200, 201) or not data.get("success", False):
            err_msg = data.get("error") or data.get("message") or f"Lỗi đăng nhập (HTTP {resp.status_code})"
            raise Exception(err_msg)

        self.user_id = data.get("id")
        self.access_token = data.get("accessToken")

        if self.user_id:
            self.session.headers["x-user-id"] = self.user_id
        if self.access_token:
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"

        return data

    def get_mailboxes(self) -> List[Dict[str, Any]]:
        url = f"{self.API_BASE}/mailboxes"
        resp = self.session.get(url, timeout=self.timeout)
        try:
            data = resp.json()
        except Exception:
            raise Exception(f"HTTP {resp.status_code}: Lỗi lấy danh sách mailbox")

        if resp.status_code != 200 or not data.get("success", False):
            raise Exception(data.get("error", f"Không lấy được mailboxes (HTTP {resp.status_code})"))

        return data.get("results", [])

    def get_inbox_id(self) -> str:
        mailboxes = self.get_mailboxes()
        for mb in mailboxes:
            if mb.get("path") == "INBOX" or mb.get("name") == "INBOX":
                return mb.get("id")
        if mailboxes:
            return mailboxes[0].get("id")
        raise Exception("Không tìm thấy mailbox nào trong tài khoản")

    def get_messages(self, mailbox_id: str) -> List[Dict[str, Any]]:
        url = f"{self.API_BASE}/mailboxes/{mailbox_id}/messages"
        resp = self.session.get(url, timeout=self.timeout)
        try:
            data = resp.json()
        except Exception:
            raise Exception(f"HTTP {resp.status_code}: Lỗi lấy danh sách messages")

        if resp.status_code != 200 or not data.get("success", False):
            raise Exception(data.get("error", f"Không lấy được messages (HTTP {resp.status_code})"))

        return data.get("results", [])

    def scan_capcut_status(self, mailbox_id: str, keyword: str = "Pro monthly") -> tuple:
        """
        Quét danh sách thư, trả về (status, message_dict):
        status có thể là 'REFUNDED', 'FOUND', 'NONE'
        """
        messages = self.get_messages(mailbox_id)
        kw = keyword.strip().lower()

        # Sắp xếp mới nhất lên đầu
        sorted_msgs = sorted(messages or [], key=lambda x: str(x.get("date") or ""), reverse=True)

        matched_refund = None
        matched_pro = None

        for msg in sorted_msgs:
            msg_str = json.dumps(msg, ensure_ascii=False).lower()
            from_addr = ""
            if isinstance(msg.get("from"), dict):
                from_addr = msg["from"].get("address", "") or msg["from"].get("name", "")
            else:
                from_addr = str(msg.get("from") or "")

            is_capcut = ("capcut" in msg_str or "pipopay" in msg_str or "noreply@email.capcut.com" in from_addr.lower())
            is_refund = any(rk in msg_str for rk in REFUND_KEYWORDS)

            if is_capcut and is_refund and not matched_refund:
                matched_refund = {
                    "id": msg.get("id"),
                    "subject": msg.get("subject", ""),
                    "date": msg.get("date", ""),
                    "intro": msg.get("intro", ""),
                    "from": from_addr,
                    "raw_message": msg
                }

            if kw in msg_str and not is_refund and not matched_pro:
                matched_pro = {
                    "id": msg.get("id"),
                    "subject": msg.get("subject", ""),
                    "date": msg.get("date", ""),
                    "intro": msg.get("intro", ""),
                    "from": from_addr,
                    "raw_message": msg
                }

        if matched_refund:
            return "REFUNDED", matched_refund
        if matched_pro:
            return "FOUND", matched_pro
        return "NONE", None


def parse_account_line(line: str) -> dict:
    """
    Tự động phân tích dòng tài khoản:
    1. Hotmail OAuth2: email | pass | refresh_token | client_id (hoặc ----)
    2. AtomicMail: email | pass
    """
    line = line.strip()
    if not line:
        return {"type": "empty", "email": "", "password": ""}

    for sep in ["----", "|", "\t", ":"]:
        if sep in line:
            parts = [p.strip() for p in line.split(sep) if p.strip()]
            if len(parts) >= 2:
                oauth_token = None
                client_id = None
                email = None
                password = ""

                for p in parts:
                    if "@" in p and not email:
                        email = p
                    elif (p.startswith("M.C") or "MsaArtifacts" in p or len(p) > 60) and not oauth_token:
                        oauth_token = p
                    elif len(p) == 36 and p.count("-") == 4 and not client_id:
                        client_id = p
                    elif not password:
                        password = p

                if oauth_token:
                    if not client_id:
                        client_id = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
                    return {
                        "type": "hotmail",
                        "email": email or parts[0],
                        "password": password,
                        "refresh_token": oauth_token,
                        "client_id": client_id
                    }
                else:
                    return {
                        "type": "atomicmail",
                        "email": parts[0],
                        "password": parts[1] if len(parts) > 1 else ""
                    }

    return {"type": "atomicmail", "email": line, "password": ""}


class CapCutCheckerManager:
    """Quản lý phiên chạy kiểm tra tài khoản hàng loạt đa luồng."""
    def __init__(self):
        self.results = []
        self.stats = {"total": 0, "done": 0, "found": 0, "refunded": 0, "fail": 0}
        self.lock = threading.Lock()

    def check_single_account(self, line: str, keyword: str = "Pro monthly") -> Dict[str, Any]:
        info = parse_account_line(line)
        email = info.get("email", "")
        password = info.get("password", "")

        row_res = {
            "email": email,
            "password": password,
            "type": info.get("type", "unknown"),
            "status": "FAIL",
            "status_text": "Thất bại",
            "mailbox_id": "",
            "date": "",
            "intro": "",
            "subject": "",
            "from": "",
            "raw_message": None,
            "error": ""
        }

        if not email:
            row_res["error"] = "Dòng trống"
            return row_res

        kw = keyword.strip().lower()

        # === TRƯỜNG HỢP 1: HOTMAIL / OUTLOOK OAUTH2 ===
        if info.get("type") == "hotmail":
            refresh_token = info.get("refresh_token")
            client_id = info.get("client_id")
            row_res["mailbox_id"] = "Microsoft Graph"

            try:
                # 1. Thử đọc qua Web Mail Reader API
                msgs, err = ch._fetch_messages_webmail(refresh_token, client_id, limit=20)
                
                # 2. Nếu lỗi hoặc rỗng, thử fallback direct Microsoft Graph
                if (err or not msgs) and hasattr(ch, '_fetch_messages_direct_microsoft'):
                    d_msgs, d_err = ch._fetch_messages_direct_microsoft(refresh_token, client_id, expected_email=email)
                    if d_msgs and not d_err:
                        msgs = d_msgs
                        err = None

                if err and not msgs:
                    row_res["status"] = "FAIL"
                    row_res["status_text"] = "Lỗi Token/API"
                    row_res["error"] = str(err)
                    row_res["intro"] = str(err)
                    return row_res

                # Sắp xếp thư mới nhất lên đầu
                sorted_msgs = sorted(msgs or [], key=lambda x: str(x.get("date") or ""), reverse=True)

                matched_refund = None
                matched_pro = None

                for m in sorted_msgs:
                    subj = str(m.get("subject") or "")
                    msg_body = str(m.get("message") or m.get("bodyText") or m.get("snippet") or "")
                    full_text = f"{subj} {msg_body}".lower()
                    from_sender = str(m.get("from_address") or m.get("from") or "").lower()

                    is_capcut = ("capcut" in full_text or "pipopay" in full_text or "noreply@email.capcut.com" in from_sender)
                    is_refund = any(rk in full_text for rk in REFUND_KEYWORDS)

                    if is_capcut and is_refund:
                        if not matched_refund:
                            matched_refund = m

                    if kw in full_text and not is_refund:
                        if not matched_pro:
                            matched_pro = m

                # Nếu phát hiện thư hoàn tiền / hủy đơn hàng:
                if matched_refund:
                    row_res["status"] = "REFUNDED"
                    row_res["status_text"] = "Đã hoàn tiền"
                    row_res["date"] = str(matched_refund.get("date") or "")
                    row_res["subject"] = str(matched_refund.get("subject") or "")
                    row_res["from"] = str(matched_refund.get("from_address") or matched_refund.get("from") or "CapCut Team")
                    row_res["intro"] = str(matched_refund.get("message") or matched_refund.get("bodyText") or matched_refund.get("snippet") or "")
                    row_res["raw_message"] = matched_refund
                elif matched_pro:
                    row_res["status"] = "FOUND"
                    row_res["status_text"] = "Tìm thấy Pro"
                    row_res["date"] = str(matched_pro.get("date") or "")
                    row_res["subject"] = str(matched_pro.get("subject") or "")
                    row_res["from"] = str(matched_pro.get("from_address") or matched_pro.get("from") or "CapCut Team")
                    row_res["intro"] = str(matched_pro.get("message") or matched_pro.get("bodyText") or matched_pro.get("snippet") or "")
                    row_res["raw_message"] = matched_pro
                else:
                    row_res["status"] = "LOGIN_OK"
                    row_res["status_text"] = "Đọc được mail (Chưa có Pro)"
                    row_res["intro"] = f"Có {len(msgs or [])} thư trong hộp mail nhưng không có '{keyword}'"

            except Exception as e:
                row_res["status"] = "FAIL"
                row_res["status_text"] = "Lỗi ngoại lệ"
                row_res["error"] = str(e)
                row_res["intro"] = str(e)

            return row_res

        # === TRƯỜNG HỢP 2: ATOMICMAIL ===
        else:
            client = AtomicMailClient()
            try:
                client.sign_in(email, password)
                inbox_id = client.get_inbox_id()
                row_res["mailbox_id"] = inbox_id

                status_type, matched = client.scan_capcut_status(inbox_id, keyword=keyword)
                if status_type == "REFUNDED":
                    row_res["status"] = "REFUNDED"
                    row_res["status_text"] = "Đã hoàn tiền"
                    row_res["date"] = matched.get("date", "")
                    row_res["subject"] = matched.get("subject", "")
                    row_res["intro"] = matched.get("intro", "")
                    row_res["from"] = matched.get("from", "")
                    row_res["raw_message"] = matched.get("raw_message")
                elif status_type == "FOUND":
                    row_res["status"] = "FOUND"
                    row_res["status_text"] = "Tìm thấy Pro"
                    row_res["date"] = matched.get("date", "")
                    row_res["subject"] = matched.get("subject", "")
                    row_res["intro"] = matched.get("intro", "")
                    row_res["from"] = matched.get("from", "")
                    row_res["raw_message"] = matched.get("raw_message")
                else:
                    row_res["status"] = "LOGIN_OK"
                    row_res["status_text"] = "Đăng nhập OK (Chưa có Pro)"
                    row_res["intro"] = f"Không có thư chứa '{keyword}'"

            except Exception as e:
                row_res["status"] = "FAIL"
                row_res["status_text"] = "Lỗi đăng nhập/API"
                row_res["error"] = str(e)
                row_res["intro"] = str(e)

            return row_res

    parse_account_line = staticmethod(parse_account_line)

    def check_via_web(self, line: str, default_password: str = "capcut123", headless: bool = True, timeout: int = 60, log_cb=None) -> Dict[str, Any]:
        """
        Đăng nhập trực tiếp CapCut Web bằng Selenium Chrome để kiểm tra chính xác trạng thái VIP/Pro.
        Tự động tách email từ dòng chứa token dài (email|pass|token|clientId hoặc bất kỳ).
        """
        import re
        acc_info = parse_account_line(line)
        email = acc_info.get("email") or ""
        if not email:
            m = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", line)
            if m:
                email = m.group(0)
            else:
                email = line.split("|")[0].split("----")[0].strip()

        pwd = acc_info.get("password") or ""
        if not pwd or pwd.lower() in ("x", "null", "none", "-"):
            pwd = default_password or "capcut123"

        return check_capcut_web_login(email=email, password=pwd, headless=headless, timeout=timeout, log_cb=log_cb)


def set_react_input(driver, element, value: str):
    """Nhập giá trị vào React input và kích hoạt đầy đủ native value setter cùng sự kiện onChange/input"""
    js_code = """
    let element = arguments[0];
    let value = arguments[1];
    let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    if (!nativeInputValueSetter) {
        nativeInputValueSetter = Object.getOwnPropertyDescriptor(element.constructor.prototype, 'value').set;
    }
    nativeInputValueSetter.call(element, value);
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    """
    driver.execute_script(js_code, element, str(value))


def check_capcut_web_login(email: str, password: str = "capcut123", headless: bool = True, timeout: int = 60, log_cb=None) -> Dict[str, Any]:
    """
    Tự động mở trình duyệt Chrome (chế độ ẩn/incognito/headless),
    điều hướng tới trang login của CapCut, điền email, password (mặc định 'capcut123'),
    đăng nhập và gọi API subscription để kiểm tra Pro.
    """
    import datetime
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    def _log(msg, level="INFO"):
        if log_cb:
            log_cb(msg, level)
        else:
            print(f"[{level}] {msg}")

    options = Options()
    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--incognito")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--window-size=1280,820")
    options.add_argument("--lang=vi-VN,vi")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

    driver = None
    res = {
        "email": email,
        "password": password,
        "type": "capcut_web",
        "status": "FAIL",
        "status_text": "Chưa xác định",
        "date": "",
        "subject": "",
        "mailbox_id": "CapCut Web",
        "intro": "",
        "error": None,
        "raw_response": None
    }

    try:
        _log(f"[{email}] 🌐 Khởi động trình duyệt ({'Chạy ngầm' if headless else 'Mở cửa sổ trực tiếp'})...", "INFO")
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e_drv:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service as ChromeService
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        login_url = "https://www.capcut.com/vi-vn/login?enter_from=log_out&current_page=work_space"
        _log(f"[{email}] Đang mở trang đăng nhập CapCut...", "INFO")
        driver.get(login_url)

        wait = WebDriverWait(driver, 15)

        # 1. Bấm nút "Tiếp tục bằng email"
        _log(f"[{email}] Đang tìm nút 'Tiếp tục bằng email'...", "INFO")
        email_btn = None
        email_selectors = [
            (By.CSS_SELECTOR, ".lv_third_part_sign_in_expand_new-button"),
            (By.CSS_SELECTOR, ".lv_third_part_sign_in_expand-icon-email"),
            (By.XPATH, "//*[contains(text(), 'Tiếp tục bằng email') or contains(text(), 'Continue with email')]"),
            (By.XPATH, "//div[contains(@class, 'lv_third_part_sign_in_expand')]//svg[contains(@class, 'email')]/..")
        ]

        start_t = time.time()
        while time.time() - start_t < 15:
            for by_type, selector in email_selectors:
                try:
                    elems = driver.find_elements(by_type, selector)
                    for el in elems:
                        if el.is_displayed():
                            email_btn = el
                            break
                    if email_btn: break
                except: pass
            if email_btn: break
            time.sleep(0.5)

        if email_btn:
            driver.execute_script("arguments[0].click();", email_btn)
            _log(f"[{email}] Đã bấm 'Tiếp tục bằng email'.", "INFO")
        else:
            _log(f"[{email}] Tiếp tục tìm input email...", "INFO")

        time.sleep(1.5)

        # 2. Nhập Email bằng set_react_input và bấm "Tiếp tục"
        _log(f"[{email}] Nhập email...", "INFO")
        username_inp = wait.until(EC.visibility_of_element_located((
            By.CSS_SELECTOR, "input[name='username'], .lv_email_entry_view-input, input[type='email']"
        )))
        set_react_input(driver, username_inp, email.strip())
        time.sleep(0.5)

        # Bấm nút Tiếp tục
        next_btn = None
        for by_t, sel in [
            (By.CSS_SELECTOR, ".lv_email_entry_view-btn"),
            (By.CSS_SELECTOR, "button.lv_sign_in_panel_wide-primary-button"),
            (By.XPATH, "//button[contains(., 'Tiếp tục') or contains(., 'Continue')]")
        ]:
            try:
                btns = driver.find_elements(by_t, sel)
                for b in btns:
                    if b.is_displayed():
                        next_btn = b
                        break
                if next_btn: break
            except: pass

        if next_btn:
            driver.execute_script("arguments[0].click();", next_btn)
            _log(f"[{email}] Đã bấm 'Tiếp tục' (Email).", "INFO")
        else:
            username_inp.submit()

        time.sleep(2)

        # 3. Nhập Password bằng set_react_input và bấm "Đăng nhập"
        _log(f"[{email}] Nhập mật khẩu ('{password}')...", "INFO")
        pwd_inp = wait.until(EC.visibility_of_element_located((
            By.CSS_SELECTOR, "input[name='password'], input[type='password']"
        )))
        set_react_input(driver, pwd_inp, password.strip())
        time.sleep(0.5)

        login_btn = None
        for by_t, sel in [
            (By.CSS_SELECTOR, ".lv_sign_in_panel_wide-sign-in-button"),
            (By.XPATH, "//button[contains(., 'Đăng nhập') or contains(., 'Sign in') or contains(., 'Log in')]"),
            (By.CSS_SELECTOR, "button.lv_sign_in_panel_wide-primary-button")
        ]:
            try:
                btns = driver.find_elements(by_t, sel)
                for b in btns:
                    if b.is_displayed():
                        login_btn = b
                        break
                if login_btn: break
            except: pass

        if login_btn:
            driver.execute_script("arguments[0].click();", login_btn)
            _log(f"[{email}] Đã bấm 'Đăng nhập'.", "INFO")
        else:
            pwd_inp.submit()

        # 4. Chờ đăng nhập và cảnh báo Captcha nếu xuất hiện
        _log(f"[{email}] Đang chờ đăng nhập và xử lý xác thực...", "INFO")
        login_success = False
        captcha_notified = False
        login_start = time.time()

        while time.time() - login_start < timeout:
            curr_url = driver.current_url.lower()

            # 1. Kiểm tra đăng nhập thành công qua URL hoặc cookies session
            if any(k in curr_url for k in ["workspace", "my-edit", "profile", "creator"]):
                login_success = True
                break

            try:
                cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
                if "sessionid" in cookies or "sid_guard" in cookies:
                    login_success = True
                    break
            except: pass

            # 2. Kiểm tra Captcha
            try:
                if any(x in driver.page_source for x in ["secsdk-captcha-drag-icon", "captcha-verify-image", "verify-bar", "secsdk_captcha"]):
                    if not captcha_notified:
                        _log(f"[{email}] ⚠️ PHÁT HIỆN CAPTCHA! Bạn có thể kéo giải trực tiếp trên trình duyệt...", "WARN")
                        captcha_notified = True
            except: pass

            # 3. Kiểm tra lỗi sai mật khẩu hoặc tài khoản không tồn tại
            if time.time() - login_start > 4.0:
                try:
                    # Kiểm tra các phần tử hiển thị lỗi trực tiếp trên form
                    err_elems = driver.find_elements(By.CSS_SELECTOR, ".lv_sign_in_panel_wide-error, .lv_sign_in_panel_wide-error-message, .lv_sign_in_panel_wide-pwd-error, .lv-form-item-explain-error, .lv-message-notice-content")
                    for ee in err_elems:
                        if ee.is_displayed():
                            txt = ee.text.lower()
                            if any(k in txt for k in ["mật khẩu", "password", "không chính xác", "incorrect"]):
                                res["status"] = "FAIL"
                                res["status_text"] = "Sai mật khẩu"
                                res["error"] = "Mật khẩu CapCut không chính xác"
                                res["intro"] = "Mật khẩu CapCut không chính xác"
                                _log(f"[{email}] ❌ Mật khẩu CapCut không chính xác!", "ERR")
                                return res
                            if any(k in txt for k in ["không tồn tại", "not exist", "chưa đăng ký"]):
                                res["status"] = "FAIL"
                                res["status_text"] = "Chưa có tài khoản CapCut"
                                res["error"] = "Tài khoản chưa đăng ký CapCut"
                                res["intro"] = "Tài khoản chưa từng đăng ký CapCut"
                                _log(f"[{email}] ❌ Tài khoản chưa đăng ký CapCut!", "ERR")
                                return res
                except: pass

            time.sleep(1.5)

        if not login_success:
            res["status"] = "FAIL"
            res["status_text"] = "Hết thời gian chờ đăng nhập"
            res["error"] = "Timeout chờ đăng nhập hoặc dính Captcha"
            res["intro"] = "Timeout chờ đăng nhập hoặc dính Captcha"
            _log(f"[{email}] ❌ Hết thời gian chờ đăng nhập CapCut.", "ERR")
            return res

        _log(f"[{email}] ✅ Đăng nhập CapCut thành công! Đang chờ dashboard tải hoàn chỉnh...", "OK")
        time.sleep(4)

        # 5. Gọi API kiểm tra Pro trực tiếp trong phiên trình duyệt (có cơ chế retry và credentials)
        _log(f"[{email}] Đang gọi API kiểm tra gói Pro...", "INFO")
        js_code = """
        const cb = arguments[arguments.length - 1];
        (async () => {
            let uInfo = null, sInfo = null;

            // 1. Gọi subscription_infos (API v3 của CapCut Web có thông tin đầy đủ về gói Pro)
            for (let i = 0; i < 3; i++) {
                try {
                    const r2 = await fetch('https://commerce-api-sg.capcut.com/commerce/v3/trade/subscription_infos', {
                        method: 'POST',
                        credentials: 'include',
                        headers: { 'Content-Type': 'application/json', 'appid': '348188' },
                        body: JSON.stringify({ "app_id": 348188, "scene": ["vip"] })
                    });
                    sInfo = await r2.json();
                    if (sInfo && (sInfo.ret === '0' || sInfo.data || sInfo.response)) break;
                } catch(e) { sInfo = { error: String(e) }; }
                await new Promise(r => setTimeout(r, 1200));
            }

            // 2. Thử gọi thêm user_info (API v1)
            for (let i = 0; i < 2; i++) {
                try {
                    const r1 = await fetch('https://commerce-api-sg.capcut.com/commerce/v1/subscription/user_info', {
                        method: 'POST',
                        credentials: 'include',
                        headers: { 'Content-Type': 'application/json', 'appid': '348188' },
                        body: '{}'
                    });
                    uInfo = await r1.json();
                    if (uInfo && (uInfo.ret === '0' || uInfo.data)) break;
                } catch(e) { uInfo = { error: String(e) }; }
                await new Promise(r => setTimeout(r, 1000));
            }

            cb({ uInfo, sInfo });
        })();
        """

        api_res = driver.execute_async_script(js_code)
        res["raw_response"] = api_res

        uInfo = (api_res or {}).get("uInfo") or {}
        sInfo = (api_res or {}).get("sInfo") or {}

        def _extract_dict(val):
            if isinstance(val, dict):
                return val
            if isinstance(val, str):
                try:
                    p = json.loads(val)
                    if isinstance(p, dict):
                        return p
                except:
                    pass
            return {}

        uData = _extract_dict(uInfo.get("data"))
        if not uData:
            uData = _extract_dict(uInfo.get("response"))

        sData = _extract_dict(sInfo.get("data"))
        if not sData:
            sData = _extract_dict(sInfo.get("response"))

        vip_group = _extract_dict(_extract_dict(sData.get("subscription_user_infos", {})).get("vip", {}))

        curr_ts = int(time.time())
        is_vip = False
        product_name = "Pro monthly"
        end_time_ts = 0
        payment_method = ""
        has_sub_order = False

        # 1. Trích xuất thông tin lịch sử gói cước từ subscription_infos (v3)
        sub_infos = vip_group.get("subscription_infos") or []
        if sub_infos:
            has_sub_order = True
            si0 = sub_infos[0]
            sku = (si0.get("sku_info") or {}).get("sku_name") or si0.get("display_subscription_info")
            if sku:
                product_name = sku
            if si0.get("payment_method"):
                payment_method = si0.get("payment_method")

        # 2. Kiểm tra quyền lợi VIP THỰC TẾ đang có hiệu lực (vip_infos)
        # Chỉ khi vip_infos có mục is_vip == True thì tài khoản mới THỰC SỰ có Pro đang dùng
        vip_infos = vip_group.get("vip_infos") or []
        for vi in vip_infos:
            if vi.get("is_vip") is True or vi.get("vip_level") in ("vip", "pro"):
                v_end = int(vi.get("vip_end_time") or 0)
                # Phải còn thời hạn hoặc không giới hạn (0)
                if v_end == 0 or v_end > curr_ts:
                    is_vip = True
                    end_time_ts = max(end_time_ts, v_end)

        # 3. Kiểm tra bổ trợ từ uData (API v1) nếu có
        if uData:
            cur_level = uData.get("cur_vip_level")
            flag = uData.get("flag")
            u_end = int(uData.get("end_time") or uData.get("cur_level_end_time") or 0)
            if (cur_level == "vip" or flag is True) and (u_end == 0 or u_end > curr_ts):
                is_vip = True
                end_time_ts = max(end_time_ts, u_end)
            if uData.get("product_id"):
                product_name = uData.get("product_id")

        date_str = ""
        if end_time_ts:
            try:
                dt = datetime.datetime.fromtimestamp(int(end_time_ts))
                date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                date_str = str(end_time_ts)

        res["date"] = date_str

        if is_vip:
            res["status"] = "FOUND"
            res["status_text"] = "Pro monthly"
            method_str = f" ({payment_method})" if payment_method else ""
            res["subject"] = f"CapCut VIP Active - Hạn đến: {date_str}{method_str}"
            res["intro"] = f"Gói: {product_name}{method_str} | Hạn dùng: {date_str}"
            _log(f"[{email}] 🟢 TÌM THẤY 'Pro monthly' (Active Pro)! Hạn đến: {date_str}{method_str}", "OK")
        elif has_sub_order:
            # Có đơn hàng gói Pro trong quá khứ nhưng vip_infos trống -> Đã bị hoàn tiền / thu hồi gói
            res["status"] = "REFUNDED"
            res["status_text"] = "Đã hoàn tiền / Thu hồi"
            method_str = f" ({payment_method})" if payment_method else ""
            res["subject"] = f"Đơn CapCut đã hoàn tiền / Thu hồi Pro{method_str}"
            res["intro"] = f"Gói: {product_name}{method_str} | VIP đã bị thu hồi hoặc hoàn tiền"
            _log(f"[{email}] ⚠️ ĐÃ HOÀN TIỀN / THU HỒI PRO! (Gói: {product_name}{method_str})", "WARN")
        else:
            res["status"] = "LOGIN_OK"
            res["status_text"] = "Chưa có Pro"
            res["subject"] = "Đăng nhập OK - Chưa có gói VIP/Pro hoạt động"
            res["intro"] = "Không tìm thấy gói Pro/VIP còn hạn sử dụng"
            _log(f"[{email}] ℹ️ Đăng nhập OK nhưng tài khoản không có gói Pro/VIP hoạt động.", "INFO")

        return res

    except Exception as e:
        res["status"] = "FAIL"
        res["status_text"] = "Lỗi kiểm tra"
        res["error"] = str(e)
        res["intro"] = str(e)
        _log(f"[{email}] ❌ Lỗi ngoại lệ: {e}", "ERR")
        return res
    finally:
        # Nếu headless thì tự đóng, nếu không headless để cửa sổ cho người dùng xem
        if headless and driver:
            try: driver.quit()
            except: pass


checker_manager = CapCutCheckerManager()
