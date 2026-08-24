#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto đăng ký tài khoản Dreamina (dreamina.capcut.com) bằng Hotmail
Flow: Mở trang → Continue with email → Sign up → Nhập email/pass → OTP (alphanumeric) → Birthday → Done
"""
import time
import re
import os
import requests
import random
import socket
import select
import base64
import threading as _threading
import subprocess
import queue
import threading
from datetime import datetime

# ─────────────────── LocalProxyRelay ──────────────────────────────────────────
class LocalProxyRelay:
    def __init__(self, upstream_host, upstream_port, username, password, local_port):
        self.upstream_host = upstream_host
        self.upstream_port = int(upstream_port)
        self.auth_b64 = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.local_port = local_port
        self._sock = None
        self._running = False

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self.local_port))
        self.local_port = self._sock.getsockname()[1]
        self._sock.listen(64)
        self._sock.settimeout(1.0)
        self._running = True
        t = _threading.Thread(target=self._accept_loop, daemon=True)
        t.start()
        log(f"[Relay] Local proxy listening on 127.0.0.1:{self.local_port}", "OK")
        return self

    def stop(self):
        self._running = False
        if self._sock:
            try: self._sock.close()
            except: pass

    def _accept_loop(self):
        while self._running:
            try:
                client, _ = self._sock.accept()
                _threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _recv_headers(self, sock):
        data = b""
        sock.settimeout(10)
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk: break
            data += chunk
            if len(data) > 65536: break
        return data

    def _tunnel(self, a, b):
        a.settimeout(60); b.settimeout(60)
        try:
            while True:
                r, _, _ = select.select([a, b], [], [], 30)
                if not r: break
                for s in r:
                    other = b if s is a else a
                    chunk = s.recv(65536)
                    if not chunk: return
                    other.sendall(chunk)
        except Exception: pass
        finally:
            for s in (a, b):
                try: s.close()
                except: pass

    def _handle_client(self, client):
        upstream = None
        try:
            raw = self._recv_headers(client)
            if not raw: return
            first_line = raw.split(b"\r\n")[0].decode(errors="replace")
            upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            upstream.settimeout(15)
            upstream.connect((self.upstream_host, self.upstream_port))
            auth_header = (f"Proxy-Authorization: Basic {self.auth_b64}\r\n").encode()
            if b"\r\n\r\n" in raw:
                head, body = raw.split(b"\r\n\r\n", 1)
                lines = head.split(b"\r\n")
                lines = [l for l in lines if not l.lower().startswith(b"proxy-authorization:")]
                modified = b"\r\n".join(lines) + b"\r\n" + auth_header + b"\r\n" + body
            else:
                modified = raw + auth_header + b"\r\n"
            upstream.sendall(modified)
            if first_line.upper().startswith("CONNECT "):
                resp = b""
                while b"\r\n\r\n" not in resp:
                    chunk = upstream.recv(4096)
                    if not chunk: break
                    resp += chunk
                if b" 407 " in resp.split(b"\r\n")[0]:
                    client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    return
                client.sendall(resp)
                if b"200" in resp.split(b"\r\n")[0]:
                    self._tunnel(client, upstream)
            else:
                self._tunnel(client, upstream)
        except Exception as e:
            log(f"[Relay] Loi ket noi proxy: {e}", "WARN")
        finally:
            for s in (client, upstream):
                if s:
                    try: s.close()
                    except: pass


# ─────────────────── Cấu hình ─────────────────────────────────────────────────
HOTMAIL_API_URL = 'https://tools.dongvanfb.net/api/get_messages_oauth2'
HOTMAIL_FILE    = "data/hotmails.txt"
DREAMINA_URL    = "https://dreamina.capcut.com/ai-tool/home?need_login=true"
OUTPUT_FILE     = "data/dreamina_accounts.txt"
DOB_YEAR        = "2000"
DOB_MONTH       = "6"
DOB_DAY         = "15"
PASSWORD        = "Dreamina123@@"

HOTMAIL_QUEUE = queue.Queue()
FILE_LOCK = threading.Lock()
GLOBAL_STOP_EVENT = None


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
            log(f"Loi cap nhat file: {e}", "WARN")


# ─────────────────── OTP (alphanumeric như QKAHPP) ────────────────────────────
def wait_for_otp_dreamina(email, password, refresh_token, client_id,
                           timeout=120, interval=4, mail_api_source="mixmmo"):
    api_url = HOTMAIL_API_URL if mail_api_source == "dongvanfb" else "https://mixmmo.com/api/get-hotmail-messages.php"
    log(f"Dang cho OTP Dreamina cho {email} (toi da {timeout}s)...", "INFO")

    if mail_api_source == "dongvanfb":
        headers = {"Content-Type": "application/json"}
        payload = {"email": email, "pass": password, "refresh_token": refresh_token, "client_id": client_id}
    else:
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        payload = {
            "action": "get_hotmail_messages",
            "account": f"{email}|{password}|{refresh_token}|{client_id}",
            "mode": "oauth",
            "folder": "inbox",
            "start_timestamp": "0"
        }

    elapsed = 0
    while elapsed < timeout:
        if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
            log("Task bi dung, thoat cho OTP!", "WARN")
            return None
        try:
            if mail_api_source == "dongvanfb":
                resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
            else:
                resp = requests.post(api_url, headers=headers, data=payload, timeout=60)

            data = resp.json()
            if data.get("status") or data.get("success"):
                if data.get("messages"):
                    for msg in data["messages"]:
                        subject = msg.get("subject", "")
                        message = msg.get("message", "")
                        bodyText = msg.get("bodyText", "")

                        clean_msg = re.sub(r'<style[^>]*>.*?</style>', ' ', message, flags=re.IGNORECASE)
                        clean_msg = re.sub(r'<[^>]+>', ' ', clean_msg)
                        text_to_search = subject + " " + clean_msg + " " + bodyText

                        # Dreamina OTP: "Your verification code: QKAHPP" - 4-8 ky tu chu/so
                        match = re.search(r'(?:verification code|code)[:\s]+([A-Z0-9]{4,8})', text_to_search, re.IGNORECASE)
                        if match:
                            otp = match.group(1).strip()
                            log(f"Nhan duoc OTP Dreamina: {otp}", "OK")
                            return otp

                        # Fallback: tim chu hoa lien nhau 4-8 ky tu
                        match2 = re.search(r'\b([A-Z]{4,8})\b', text_to_search)
                        if match2:
                            otp = match2.group(1).strip()
                            log(f"Nhan duoc OTP (fallback chu): {otp}", "OK")
                            return otp

                        # Fallback: 6 chu so thuan
                        match3 = re.search(r'\b(\d{6})\b', text_to_search)
                        if match3:
                            otp = match3.group(1)
                            log(f"Nhan duoc OTP (so): {otp}", "OK")
                            return otp
            else:
                log(f"API Hotmail tra ve loi: {data}", "WARN")
        except Exception as e:
            log(f"Loi goi API Hotmail: {e}", "WARN")

        time.sleep(interval)
        elapsed += interval

    log("Het thoi gian cho OTP!", "ERR")
    return None


# ─────────────────── Proxy ────────────────────────────────────────────────────
def get_settings_from_db():
    import sqlite3
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database.db"))
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `value` FROM settings")
        settings = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return settings
    except Exception:
        return {}


def get_rotated_proxy():
    FALLBACK_PROXY = {"host": "180.93.2.171", "port": 3131, "user": "kierangrayson226", "pass": "odq0nda0odmzoa=="}
    try:
        settings = get_settings_from_db()
        proxy_type = settings.get("PROXY_TYPE", "proxyquick")
        if proxy_type == "proxyxoay":
            key = settings.get("PROXYXOAY_KEY", "")
            url = f"https://proxyxoay.shop/api/get.php?key={key}&&nhamang=random&&tinhthanh=0&whitelist="
            resp = requests.get(url, timeout=15).json()
            if resp.get("status") == 100:
                parts = resp.get("proxyhttp", "").split(":")
                return {"host": parts[0], "port": int(parts[1]), "user": "", "pass": ""}
        else:
            token = settings.get("PROXY_API_TOKEN", "")
            merchant = settings.get("PROXY_MERCHANT", "")
            proxy_id = settings.get("PROXY_ID", "953319")
            headers = {"Authorization": f"Bearer {token}", "x-merchant-id": merchant}
            url = f"https://proxyquick.click/api/v2/proxies/{proxy_id}/rotate"
            resp = requests.get(url, headers=headers, proxies={"http": None, "https": None}, timeout=15).json()
            if resp.get("status") == "success":
                parts = resp.get("proxy", "").split(":")
                if len(parts) >= 4:
                    return {"host": parts[0], "port": int(parts[1]), "user": parts[2], "pass": parts[3]}
    except Exception as e:
        log(f"Loi goi API proxy: {e}", "ERR")
    return FALLBACK_PROXY


# ─────────────────── Selenium helpers ─────────────────────────────────────────
def setup_driver(index=1, keep_open=False, batch_size=3, use_proxy=True,
                 predefined_proxy=None, headless=False, browser_type="chrome"):
    from selenium import webdriver

    cols = min(batch_size, 4)
    SCREEN_W = 1920; SCREEN_H = 1080
    window_width  = SCREEN_W // cols
    window_height = SCREEN_H
    idx = (index - 1) % cols
    x = idx * window_width; y = 0

    PROXY_HOST = None; PROXY_PORT = None; PROXY_USER = ""; PROXY_PASS = ""
    relay = None
    if use_proxy:
        proxy = predefined_proxy or get_rotated_proxy()
        if proxy:
            PROXY_HOST = proxy["host"]
            PROXY_PORT = proxy["port"]
            PROXY_USER = proxy.get("user", "")
            PROXY_PASS = proxy.get("pass", "")
            log(f"Dung Proxy: {PROXY_HOST}:{PROXY_PORT}", "INFO")

    if browser_type.lower() in ["firefox", "camoufox"]:
        from selenium.webdriver.firefox.options import Options as FxOptions
        options = FxOptions()
        if headless: options.add_argument("--headless")
        options.add_argument(f"--width={window_width}")
        options.add_argument(f"--height={window_height}")
        camoufox_path = os.path.expanduser("~/Library/Caches/camoufox/Camoufox.app/Contents/MacOS/camoufox")
        if browser_type.lower() == "camoufox" and os.path.exists(camoufox_path):
            options.binary_location = camoufox_path
        if PROXY_HOST:
            if PROXY_USER and PROXY_PASS:
                relay = LocalProxyRelay(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, 0).start()
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", "127.0.0.1")
                options.set_preference("network.proxy.http_port", relay.local_port)
                options.set_preference("network.proxy.ssl", "127.0.0.1")
                options.set_preference("network.proxy.ssl_port", relay.local_port)
            else:
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", PROXY_HOST)
                options.set_preference("network.proxy.http_port", int(PROXY_PORT))
                options.set_preference("network.proxy.ssl", PROXY_HOST)
                options.set_preference("network.proxy.ssl_port", int(PROXY_PORT))
        try:
            driver = webdriver.Firefox(options=options)
        except Exception:
            from webdriver_manager.firefox import GeckoDriverManager
            from selenium.webdriver.firefox.service import Service as FxService
            driver = webdriver.Firefox(service=FxService(GeckoDriverManager().install()), options=options)
        driver.set_window_position(x, y)
    else:
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        options = ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if keep_open: options.add_experimental_option("detach", True)
        if headless: options.add_argument("--headless=new")
        options.add_argument(f"--window-size={window_width},{window_height}")
        options.add_argument(f"--window-position={x},{y}")
        options.add_argument("--lang=en-US")

        if PROXY_HOST:
            if PROXY_USER and PROXY_PASS:
                relay = LocalProxyRelay(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS, 0).start()
                options.add_argument(f"--proxy-server=http://127.0.0.1:{relay.local_port}")
                options.add_argument("--proxy-bypass-list=<-loopback>")
            else:
                options.add_argument(f"--proxy-server=http://{PROXY_HOST}:{PROXY_PORT}")

        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            log(f"Khong tu tim duoc chromedriver: {e}", "WARN")
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service as ChromeService
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def wait_for_element(driver, by, value, timeout=20):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))


def set_react_input(driver, element, value):
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
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)
        element.click()
        log(f"Clicked: {label}", "INFO")
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", element)
            log(f"JS-clicked: {label}", "INFO")
            return True
        except Exception as e2:
            log(f"Khong click duoc {label}: {e2}", "WARN")
            return False


# ─────────────────── CÁC BƯỚC ĐĂNG KÝ DREAMINA ───────────────────────────────

def step1_open_and_click_email(driver):
    from selenium.webdriver.common.by import By
    log("Buoc 1: Mo trang Dreamina...", "INFO")
    driver.get(DREAMINA_URL)
    time.sleep(5)

    selectors = [
        (By.XPATH, "//div[contains(@class, 'lv_new_third_part_sign_in_expand-wrapper') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'email')]"),
        (By.XPATH, "//span[contains(@class, 'lv_new_third_part_sign_in_expand-label') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'email')]"),
        (By.XPATH, "//button[contains(., 'Continue with email')]"),
        (By.XPATH, "//button[contains(., 'email')]"),
        (By.CSS_SELECTOR, ".login-method-button-VeHf_D"),
    ]
    for by, sel in selectors:
        try:
            els = driver.find_elements(by, sel)
            for el in els:
                if el.is_displayed():
                    txt = el.text.strip().lower()
                    if "email" in txt or txt == "": # Sometimes spans don't have text property working well
                        try_click(driver, el, "Continue with email")
                        log("Da click 'Continue with email'!", "OK")
                        time.sleep(2)
                        return True
        except Exception:
            pass

    log("Khong tim thay nut 'Continue with email'!", "ERR")
    return False


def step2_click_sign_up(driver):
    from selenium.webdriver.common.by import By
    log("Buoc 2: Tim nut 'Sign up'...", "INFO")

    selectors = [
        (By.XPATH, "//span[@role='button' and contains(., 'Sign up')]"),
        (By.XPATH, "//span[contains(@class, 'inline-link') and contains(text(), 'Sign up')]"),
        (By.XPATH, "//*[contains(text(), 'Sign up') and (@role='button' or @tabindex='0')]"),
    ]
    for by, sel in selectors:
        try:
            els = driver.find_elements(by, sel)
            for el in els:
                if el.is_displayed():
                    txt = el.text.strip()
                    if "sign up" in txt.lower() and len(txt) < 20:
                        try_click(driver, el, f"Sign up: '{txt}'")
                        log("Da click 'Sign up'!", "OK")
                        time.sleep(2)
                        return True
        except Exception:
            pass

    log("Khong tim thay nut 'Sign up'!", "ERR")
    return False


def step3_fill_signup_form(driver, email, password):
    from selenium.webdriver.common.by import By
    log(f"Buoc 3: Nhap email '{email}' va password...", "INFO")

    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Create an account')]"))
        )
        log("Form 'Create an account' xuat hien!", "OK")
    except Exception:
        log("Khong thay form 'Create an account', thu tiep...", "WARN")

    time.sleep(0.5)

    # Nhap email
    email_input = None
    for sel in ["input[type='email']", "input[name='username']", "input[autocomplete='username']"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.is_displayed():
                email_input = el
                break
        except Exception:
            pass

    if not email_input:
        log("Khong tim thay o email!", "ERR")
        return False

    set_react_input(driver, email_input, email)
    log(f"Da nhap email: {email}", "OK")
    time.sleep(0.3)

    # Nhap password
    pwd_input = None
    for sel in ["input[type='password']", "input[autocomplete='new-password']"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.is_displayed():
                pwd_input = el
                break
        except Exception:
            pass

    if not pwd_input:
        log("Khong tim thay o password!", "ERR")
        return False

    set_react_input(driver, pwd_input, password)
    log("Da nhap password!", "OK")
    time.sleep(0.3)

    # Bam Continue
    clicked = False
    for by, sel in [
        (By.CSS_SELECTOR, ".continue-button-HO73V2"),
        (By.XPATH, "//button[contains(@class,'continue-button')]"),
        (By.XPATH, "//button[.//span[text()='Continue']]"),
        (By.XPATH, "//button[contains(@class,'lv-btn-primary')]"),
    ]:
        try:
            els = driver.find_elements(by, sel)
            for el in els:
                if el.is_displayed() and el.is_enabled():
                    try_click(driver, el, "Continue (signup)")
                    clicked = True
                    break
        except Exception:
            pass
        if clicked: break

    if not clicked:
        log("Khong click duoc nut Continue!", "ERR")
        return False

    log("Da submit form dang ky!", "OK")
    time.sleep(3)
    return True


def step4_enter_otp(driver, email, password, refresh_token, client_id, mail_api_source="mixmmo"):
    from selenium.webdriver.common.by import By
    log("Buoc 4: Cho man hinh nhap OTP...", "INFO")

    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                "input.verification-code-input-RsZsPB, input[maxlength='6'][autocomplete='one-time-code']"))
        )
        log("Man hinh nhap OTP xuat hien!", "OK")
    except Exception as e:
        log(f"Khong thay man hinh OTP: {e}", "ERR")
        return False

    time.sleep(5)

    otp = wait_for_otp_dreamina(email, password, refresh_token, client_id,
                                 timeout=120, interval=4, mail_api_source=mail_api_source)
    if not otp:
        log("Khong lay duoc OTP!", "ERR")
        return False

    entered = False
    for sel in [
        "input.verification-code-input-RsZsPB",
        "input[maxlength='6'][autocomplete='one-time-code']",
        "input[maxlength='6']",
        ".lv_sign_in_panel_wide-code-detail input",
        "input[name='code']"
    ]:
        try:
            otp_input = driver.find_element(By.CSS_SELECTOR, sel)
            set_react_input(driver, otp_input, otp)
            log(f"Da nhap OTP: {otp}", "OK")
            entered = True
            break
        except Exception:
            pass

    if not entered:
        log("Khong tim thay o nhap OTP! Thu click tung o...", "WARN")
        try:
            from selenium.webdriver.common.keys import Keys
            code_boxes = driver.find_elements(By.CSS_SELECTOR,
                '.verification_code_input-number input, input.lv-input, .lv_new_third_part_sign_in_expand-code_input_wrap input')
            if code_boxes:
                code_boxes[0].click()
                for digit in otp:
                    driver.switch_to.active_element.send_keys(digit)
                    time.sleep(0.1)
                log(f"Da nhap OTP qua tung ky tu: {otp}", "OK")
                entered = True
        except Exception as e:
            pass
        
    if not entered:
        log("Khong tim thay o nhap OTP!", "ERR")
        return False

    time.sleep(3)
    return True


def step5_enter_birthday(driver):
    from selenium.webdriver.common.by import By
    log("Buoc 5: Dien ngay sinh...", "INFO")

    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                ".gate_birthday-picker, .lv_sign_in_panel_wide-birthday-detail"))
        )
    except Exception:
        log("Khong thay man hinh birthday, bo qua...", "WARN")
        return True

    time.sleep(0.5)

    # Nhap Nam
    try:
        year_input = driver.find_element(By.CSS_SELECTOR,
            ".gate_birthday-picker-input, input[placeholder='Year']")
        set_react_input(driver, year_input, DOB_YEAR)
        log(f"Da nhap nam: {DOB_YEAR}", "OK")
        time.sleep(0.2)
    except Exception as e:
        log(f"Khong tim thay o nhap nam: {e}", "WARN")

    # Chon Thang (dropdown)
    try:
        selectors_el = driver.find_elements(By.CSS_SELECTOR, ".gate_birthday-picker-selector")
        if selectors_el:
            month_sel = selectors_el[0]
            try_click(driver, month_sel, "Month dropdown")
            time.sleep(0.5)
            options = driver.find_elements(By.CSS_SELECTOR,
                ".lv-select-option, [role='option'], .lv-select-item")
            clicked = False
            for opt in options:
                if opt.is_displayed():
                    txt = opt.text.strip()
                    if txt == DOB_MONTH or txt == str(int(DOB_MONTH)):
                        try_click(driver, opt, f"Thang {DOB_MONTH}")
                        clicked = True
                        break
            if not clicked:
                visible_opts = [o for o in options if o.is_displayed()]
                target_idx = int(DOB_MONTH) - 1
                if len(visible_opts) > target_idx:
                    try_click(driver, visible_opts[target_idx], f"Thang {DOB_MONTH} (index)")
            time.sleep(0.2)
    except Exception as e:
        log(f"Loi chon thang: {e}", "WARN")

    # Chon Ngay (dropdown)
    try:
        selectors_el = driver.find_elements(By.CSS_SELECTOR, ".gate_birthday-picker-selector")
        if len(selectors_el) >= 2:
            day_sel = selectors_el[1]
            try_click(driver, day_sel, "Day dropdown")
            time.sleep(0.5)
            options = driver.find_elements(By.CSS_SELECTOR,
                ".lv-select-option, [role='option'], .lv-select-item")
            clicked = False
            for opt in options:
                if opt.is_displayed():
                    txt = opt.text.strip()
                    if txt == DOB_DAY or txt == str(int(DOB_DAY)):
                        try_click(driver, opt, f"Ngay {DOB_DAY}")
                        clicked = True
                        break
            if not clicked:
                visible_opts = [o for o in options if o.is_displayed()]
                target_idx = int(DOB_DAY) - 1
                if len(visible_opts) > target_idx:
                    try_click(driver, visible_opts[target_idx], f"Ngay {DOB_DAY} (index)")
            time.sleep(0.2)
    except Exception as e:
        log(f"Loi chon ngay: {e}", "WARN")

    # Bam Continue (birthday)
    time.sleep(0.3)
    clicked = False
    for by, sel in [
        (By.CSS_SELECTOR, ".lv_sign_in_panel_wide-birthday-next, .lv_sign_in_panel_wide-primary-button"),
        (By.XPATH, "//button[.//span[text()='Continue']]"),
    ]:
        try:
            els = driver.find_elements(by, sel)
            for el in els:
                if el.is_enabled():
                    try_click(driver, el, "Continue (birthday)")
                    clicked = True
                    break
        except Exception:
            pass
        if clicked: break

    if not clicked:
        log("Khong click duoc nut Continue (birthday), thu tiep...", "WARN")

    log("Hoan tat buoc ngay sinh!", "OK")
    time.sleep(3)
    return True


def wait_for_home_dreamina(driver, timeout=60):
    log("Cho vao trang chinh Dreamina...", "INFO")
    start = time.time()
    while time.time() - start < timeout:
        url = driver.current_url
        if "dreamina.capcut.com" in url and "need_login" not in url:
            from selenium.webdriver.common.by import By
            try:
                login_panels = driver.find_elements(By.CSS_SELECTOR, ".dreamina-oversea-login-panel")
                if not login_panels or not any(p.is_displayed() for p in login_panels):
                    log(f"Da vao trang chinh Dreamina: {url}", "OK")
                    return True
            except Exception:
                pass
        time.sleep(2)
    log("Het thoi gian cho trang chinh Dreamina!", "WARN")
    return True  # Continue anyway


def save_account(email, password):
    line = f"{email}\t{password}"
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    log(f"Da luu tai khoan -> {OUTPUT_FILE}: {email}", "OK")


# ─────────────────── Main flow ────────────────────────────────────────────────
ACTIVE_DRIVERS = []


def register_one_account(index, keep_open=False, batch_size=3, use_proxy=True,
                          predefined_proxy=None, headless=False, browser_type="chrome",
                          mail_api_source="mixmmo"):
    driver = None
    acc = None
    try:
        try:
            acc = HOTMAIL_QUEUE.get_nowait()
        except queue.Empty:
            log(f"[{index}] Het hotmail trong queue!", "WARN")
            return False

        email       = acc["email"]
        email_pass  = acc["pass"]
        refresh_token = acc["refresh_token"]
        client_id   = acc["client_id"]

        settings = get_settings_from_db()
        password = settings.get("DREAMINA_PASSWORD", PASSWORD)

        log(f"[{index}] Bat dau dang ky Dreamina voi: {email}", "INFO")

        driver = setup_driver(index, keep_open=keep_open, batch_size=batch_size,
                              use_proxy=use_proxy, predefined_proxy=predefined_proxy,
                              headless=headless, browser_type=browser_type)
        if not headless:
            ACTIVE_DRIVERS.append(driver)

        if not step1_open_and_click_email(driver):
            log(f"[{index}] Khong mo duoc trang Dreamina!", "ERR")
            return False

        if not step2_click_sign_up(driver):
            log(f"[{index}] Khong click duoc Sign up!", "ERR")
            return False

        if not step3_fill_signup_form(driver, email, password):
            log(f"[{index}] Khong dien duoc form dang ky!", "ERR")
            return False

        if not step4_enter_otp(driver, email, email_pass, refresh_token, client_id, mail_api_source):
            log(f"[{index}] Khong xac nhan duoc OTP!", "ERR")
            return False

        step5_enter_birthday(driver)
        wait_for_home_dreamina(driver, timeout=30)
        save_account(email, password)
        mark_hotmail_used(acc)

        log(f"[{index}] DANG KY DREAMINA THANH CONG! Email: {email}", "OK")
        return True

    except Exception as e:
        log(f"[{index}] LOI: {type(e).__name__}: {e}", "ERR")
        if driver:
            try:
                driver.save_screenshot(f"dreamina_error_{index}.png")
            except: pass
        return False
    finally:
        if driver and not keep_open:
            try:
                if driver in ACTIVE_DRIVERS: ACTIVE_DRIVERS.remove(driver)
                driver.quit()
                log("Da dong trinh duyet.", "INFO")
            except: pass


def load_hotmails_to_queue(limit=None):
    if not os.path.exists(HOTMAIL_FILE):
        log(f"Khong tim thay file {HOTMAIL_FILE}", "ERR")
        return 0

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
                HOTMAIL_QUEUE.put({
                    "email": parts[0].strip(),
                    "pass": parts[1].strip(),
                    "refresh_token": parts[2].strip(),
                    "client_id": parts[3].strip(),
                    "original_line": line
                })
                count += 1
                if limit and count >= limit:
                    break
    log(f"Da tai {count} hotmail tu file {HOTMAIL_FILE}.", "OK")
    return count


def register_multiple(count, threads, keep_open=False, headless=False,
                       browser_type="chrome", mail_api_source="mixmmo"):
    import concurrent.futures
    results = {"ok": 0, "fail": 0}

    def worker(i):
        time.sleep((i % threads) * 2.5)
        local_ok = 0; local_fail = 0
        while not HOTMAIL_QUEUE.empty():
            if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
                break
            res = register_one_account(i, keep_open=keep_open, batch_size=threads,
                                        use_proxy=True, headless=headless,
                                        browser_type=browser_type,
                                        mail_api_source=mail_api_source)
            if res: local_ok += 1
            else: local_fail += 1
        return local_ok, local_fail

    log(f"--- BAT DAU: {count} hotmail, {threads} luong ---", "WARN")
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(worker, i+1) for i in range(threads)]
        for future in concurrent.futures.as_completed(futures):
            ok, fail = future.result()
            results["ok"] += ok
            results["fail"] += fail

    log(f"KET QUA: {results['ok']} thanh cong / {results['fail']} that bai", "OK")
    return results
