#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto đăng ký tài khoản Higgsfield.ai
Flow: Mở trang → Sign up → Continue with Email → Nhập email/pass → OTP → Quiz → Done
"""
import time
import re
import sys
import os
import requests
import random
import socket
import select
import base64
import threading as _threading
from datetime import datetime
import subprocess

# ─────────────────── LocalProxyRelay ───────────────────────────────────────
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
            if not chunk:
                break
            data += chunk
            if len(data) > 65536:
                break
        return data

    def _tunnel(self, a, b):
        a.settimeout(60)
        b.settimeout(60)
        try:
            while True:
                r, _, _ = select.select([a, b], [], [], 30)
                if not r:
                    break
                for s in r:
                    other = b if s is a else a
                    chunk = s.recv(65536)
                    if not chunk:
                        return
                    other.sendall(chunk)
        except Exception:
            pass
        finally:
            for s in (a, b):
                try: s.close()
                except: pass

    def _handle_client(self, client):
        upstream = None
        try:
            raw = self._recv_headers(client)
            if not raw:
                return
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
                    if not chunk:
                        break
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

# ─────────────────── Cấu hình ───────────────────────────────────────────────
BASE_URL       = "https://regmail.phh.info.vn"
API_KEY        = "1dec9d51e8707e9bf1fa7756612830c676f65a42a1009851580ec0a82384abd8"
PASSWORD       = "Higgsfield123@@"
HIGGSFIELD_URL = "https://higgsfield.ai/"
OUTPUT_FILE    = "higgsfield_accounts.txt"

API_HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

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

# ─────────────────── Email API ───────────────────────────────────────────────
def create_random_email():
    resp = requests.post(f"{BASE_URL}/api/emails/create", headers=API_HEADERS, proxies={"http": None, "https": None}, timeout=10)
    data = resp.json()
    if data.get("success") and data.get("email"):
        log(f"Da tao email: {C.BOLD}{data['email']}{C.RST}", "OK")
        return data["email"]
    raise Exception(f"Khong tao duoc email: {data}")

def get_latest_email(email_address):
    resp = requests.get(f"{BASE_URL}/api/emails/latest", headers=API_HEADERS, params={"email": email_address}, proxies={"http": None, "https": None}, timeout=10)
    data = resp.json()
    if data.get("success") and data.get("email"):
        return data["email"]
    return None

def wait_for_otp(email_address, timeout=120, interval=4):
    log(f"Dang cho OTP cho {email_address} (toi da {timeout}s)...", "INFO")
    elapsed = 0
    while elapsed < timeout:
        mail = get_latest_email(email_address)
        if mail:
            otp = mail.get("otp")
            if not otp:
                subject = mail.get("subject", "") + " " + mail.get("text", "")
                match = re.search(r'\b(\d{6})\b', subject)
                if match: otp = match.group(1)
            if otp:
                log(f"Nhan duoc OTP: {C.BOLD}{otp}{C.RST}", "OK")
                return otp
            log("Co email nhung chua co OTP, cho them...", "WARN")
        time.sleep(interval)
        elapsed += interval
    log("Het thoi gian cho OTP!", "ERR")
    return None

def delete_mailbox(email_address):
    try:
        requests.delete(f"{BASE_URL}/api/emails/address/{email_address}", headers=API_HEADERS, proxies={"http": None, "https": None}, timeout=10)
        log(f"Da don hom thu: {email_address}", "OK")
    except Exception as e:
        log(f"Loi xoa mail: {e}", "WARN")

# ─────────────────── Proxy ───────────────────────────────────────────────────
def get_rotated_proxy():
    api_url = "https://proxyquick.click/api/v3/users/rotatev2?token=MTc4MjU3MjM2NjU3MDtkaWFuYWJlYXR0eTg5NTthcGktcHJveHktNC5ob21lcHJveHkudm4%3D_260cea8382eefa12c3e111ba07dcc6001d02fadf"
    try:
        log("Dang xoay/lay proxy tu API...", "INFO")
        resp = requests.get(api_url, proxies={"http": None, "https": None}, timeout=15)
        data = resp.json()
        if data.get("proxy"):
            parts = data["proxy"].split(":")
            if len(parts) >= 4:
                return {"host": parts[0], "port": int(parts[1]), "user": parts[2], "pass": parts[3]}
            elif len(parts) >= 2:
                return {"host": parts[0], "port": int(parts[1]), "user": "", "pass": ""}
        log(f"Loi lay proxy: {data.get('message', data)}", "WARN")
    except Exception as e:
        log(f"Loi goi API proxy: {e}", "ERR")
    return None

# ─────────────────── Selenium helpers ────────────────────────────────────────
def setup_driver(index=1, keep_open=False, use_proxy=True, batch_size=3, headless=False, browser_type="chrome"):
    from selenium import webdriver
    import random
    
    cols = min(batch_size, 4)
    SCREEN_W = 1920; SCREEN_H = 1080
    window_width  = SCREEN_W // cols
    window_height = SCREEN_H
    idx = (index - 1) % cols
    x = idx * window_width
    y = 0
    
    PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS = None, None, None, None
    if use_proxy:
        proxy = get_rotated_proxy()
        if proxy:
            PROXY_HOST = proxy["host"]
            PROXY_PORT = proxy["port"]
            PROXY_USER = proxy.get("user", "")
            PROXY_PASS = proxy.get("pass", "")
            log(f"Dang dung Proxy API: {PROXY_HOST}:{PROXY_PORT}", "INFO")
        else:
            FALLBACK_PROXIES = [
                {"host": "180.93.2.171", "port": 3131, "user": "kierangrayson226", "pass": "odq0nda0odmzoa=="}
            ]
            proxy = random.choice(FALLBACK_PROXIES)
            PROXY_HOST = proxy["host"]
            PROXY_PORT = proxy["port"]
            PROXY_USER = proxy["user"]
            PROXY_PASS = proxy["pass"]
            log(f"Dang dung Proxy du phong: {PROXY_HOST}:{PROXY_PORT}", "WARN")

    if browser_type.lower() in ["firefox", "camoufox"]:
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        options = FirefoxOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument(f"--width={window_width}")
        options.add_argument(f"--height={window_height}")
        
        # Use Camoufox if explicitly requested or if we find it
        import os
        camoufox_path = os.path.expanduser("~/Library/Caches/camoufox/Camoufox.app/Contents/MacOS/camoufox")
        if browser_type.lower() == "camoufox" and os.path.exists(camoufox_path):
            options.binary_location = camoufox_path
            log("Dang su dung trinh duyet Camoufox!", "OK")
        elif browser_type.lower() == "camoufox":
            log("Chua tim thay Camoufox, dung tam Firefox goc!", "WARN")
        
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
        except Exception as e:
            log(f"Khong tu tim duoc geckodriver: {e}", "WARN")
            from webdriver_manager.firefox import GeckoDriverManager
            from selenium.webdriver.firefox.service import Service as FirefoxService
            driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)
            
        driver.set_window_position(x, y)
        
    else:
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if keep_open and not headless:
            options.add_experimental_option("detach", True)
            
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

def wait_clickable(driver, by, value, timeout=20):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))

def set_input(driver, element, value):
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

# ─────────────────── Các bước đăng ký ───────────────────────────────────────

def step1_open_signup(driver):
    """Bước 1: Mở trang Higgsfield và bấm Sign up"""
    from selenium.webdriver.common.by import By
    log("Buoc 1: Mo trang Higgsfield...", "INFO")
    driver.get(HIGGSFIELD_URL)
    time.sleep(4)
    log("Cho UI load va tim nut Sign up...", "INFO")
    selectors = [
        (By.CSS_SELECTOR, "button.hfnav-auth-signup"),
        (By.CSS_SELECTOR, "button.hfnav-auth.hfnav-auth-signup"),
        (By.XPATH, "//button[contains(@class,'hfnav-auth-signup')]"),
        (By.XPATH, "//button[contains(text(),'Sign up') or contains(text(),'sign up')]"),
    ]
    for by, sel in selectors:
        try:
            btn = wait_clickable(driver, by, sel, timeout=15)
            if btn and btn.is_displayed():
                try_click(driver, btn, "Sign up")
                log("Da click nut Sign up!", "OK")
                time.sleep(2.5)
                return True
        except Exception:
            pass
    log("Khong tim thay nut Sign up!", "ERR")
    return False

def step2_click_email(driver):
    """Bước 2: Click 'Continue with Email'"""
    from selenium.webdriver.common.by import By
    log("Buoc 2: Cho dialog va click 'Continue with Email'...", "INFO")
    try:
        wait_for_element(driver, By.CSS_SELECTOR, "[role='dialog']", timeout=15)
        log("Dialog dang ky da hien ra!", "OK")
    except Exception:
        log("Khong thay dialog, thu tiep...", "WARN")
    time.sleep(2)
    # Tìm nút chứa text "Continue with Email" - ưu tiên button có icon email (path duy nhất)
    selectors = [
        (By.XPATH, "//button[contains(.,'Continue with Email')]"),
        (By.XPATH, "//button[contains(text(),'Continue with Email')]"),
        (By.XPATH, "//button[.//path[contains(@d,'M3.75 4C2.7835 4')]]"),
    ]
    for by, sel in selectors:
        try:
            els = driver.find_elements(by, sel)
            for el in els:
                if el.is_displayed():
                    try_click(driver, el, "Continue with Email")
                    log("Da click 'Continue with Email'!", "OK")
                    time.sleep(2)
                    return True
        except Exception:
            pass
    # Fallback: tìm tất cả button chứa "Email"
    try:
        all_btns = driver.find_elements(By.XPATH, "//button[contains(.,'Email')]")
        for btn in all_btns:
            if btn.is_displayed():
                txt = btn.text.strip()
                if "email" in txt.lower():
                    log(f"Fallback click: '{txt}'", "WARN")
                    try_click(driver, btn, "Email fallback")
                    time.sleep(2)
                    return True
    except Exception:
        pass
    log("Khong tim thay nut 'Continue with Email'!", "ERR")
    return False

def step3_fill_form(driver, email, password):
    """Bước 3: Nhập email và password vào form đăng ký"""
    from selenium.webdriver.common.by import By
    log(f"Buoc 3: Nhap email '{email}' va password...", "INFO")
    # Chờ form hiện ra
    email_input = None
    for sel in ["input[type='email']", "input[name='email']", "input[placeholder='Email']"]:
        try:
            email_input = wait_for_element(driver, By.CSS_SELECTOR, sel, timeout=15)
            if email_input:
                break
        except Exception:
            pass
    if not email_input:
        log("Khong tim thay o email!", "ERR")
        return False
    set_input(driver, email_input, email)
    log(f"Da nhap email: {email}", "OK")
    time.sleep(0.5)
    # Nhập password
    pwd_input = None
    for sel in ["input[type='password']", "input[name='password']"]:
        try:
            pwd_input = driver.find_element(By.CSS_SELECTOR, sel)
            if pwd_input:
                break
        except Exception:
            pass
    if not pwd_input:
        log("Khong tim thay o password!", "ERR")
        return False
    set_input(driver, pwd_input, password)
    log("Da nhap password!", "OK")
    time.sleep(0.5)
    # Submit form
    clicked = False
    for by, sel in [
        (By.CSS_SELECTOR, "input[type='submit']"),
        (By.XPATH, "//input[@type='submit']"),
        (By.XPATH, "//button[@type='submit']"),
    ]:
        try:
            els = driver.find_elements(by, sel)
            for el in els:
                if el.is_displayed() and el.is_enabled():
                    try_click(driver, el, "Submit form")
                    clicked = True
                    break
        except Exception:
            pass
        if clicked:
            break
    if clicked:
        log("Da submit form dang ky!", "OK")
        time.sleep(3)
        return True
    log("Khong click duoc nut submit!", "ERR")
    return False

def step4_enter_otp(driver, email):
    """Bước 4: Chờ và nhập OTP"""
    from selenium.webdriver.common.by import By
    log("Buoc 4: Cho man hinh xac nhan OTP...", "INFO")
    
    otp_appeared = False
    for attempt in range(8):  # Try for up to 40 seconds
        try:
            otp_inputs = driver.find_elements(By.CSS_SELECTOR, "input[name='code'], input[placeholder='Code']")
            if otp_inputs and otp_inputs[0].is_displayed():
                log("Man hinh nhap OTP da hien!", "OK")
                otp_appeared = True
                break
        except: pass
        
        # Check if the submit button is still there (meaning we are stuck on the form)
        try:
            submit_btns = driver.find_elements(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
            for btn in submit_btns:
                if btn.is_displayed() and btn.is_enabled():
                    log("Van con form dang ky (loi CAPTCHA?), dang thu click lai Submit...", "WARN")
                    try_click(driver, btn, "Submit form (Retry)")
                    break
        except: pass
        
        time.sleep(5)
        
    if not otp_appeared:
        log("Khong thay man hinh OTP ro rang (co the bi block boi CAPTCHA), bo qua acc nay...", "ERR")
        return False
        
    # Chờ 5s để email đến
    time.sleep(5)
    otp = wait_for_otp(email, timeout=120, interval=4)
    if not otp:
        log("Khong lay duoc OTP!", "ERR")
        return False
    # Nhập OTP
    entered = False
    for sel in ["input[name='code']", "input[placeholder='Code']", "input[type='text']"]:
        try:
            otp_input = driver.find_element(By.CSS_SELECTOR, sel)
            if otp_input.is_displayed():
                set_input(driver, otp_input, otp)
                log(f"Da nhap OTP: {otp}", "OK")
                entered = True
                break
        except Exception:
            pass
    if not entered:
        log("Khong tim thay o nhap OTP!", "ERR")
        return False
    # Submit OTP bằng Enter
    time.sleep(0.5)
    try:
        from selenium.webdriver.common.keys import Keys
        otp_input = driver.find_element(By.CSS_SELECTOR, "input[name='code'], input[placeholder='Code']")
        otp_input.send_keys(Keys.RETURN)
        log("Da nhan Enter xac nhan OTP!", "OK")
    except Exception:
        try:
            submit = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
            driver.execute_script("arguments[0].click();", submit)
            log("Da click submit OTP!", "OK")
        except Exception as e:
            log(f"Khong submit duoc OTP: {e}", "WARN")
    time.sleep(4)
    return True

def check_and_handle_error_page(driver):
    """Phát hiện trang lỗi 'Oops / Something went wrong' → tự động reload"""
    from selenium.webdriver.common.by import By
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        error_keywords = ["something went wrong", "oops", "went wrong"]
        if not any(kw in body_text.lower() for kw in error_keywords):
            return False  # Không có lỗi
        log("Phat hien loi 'Something went wrong'! Tu dong reload trang...", "WARN")
        driver.refresh()
        time.sleep(4)
        log("Da reload xong!", "OK")
        return True
    except Exception:
        return False



def step5_complete_quiz(driver):
    """Bước 5: Quiz - click option rồi bấm tiếp tục, lặp đến khi hết quiz (tối đa 30 bước)"""
    from selenium.webdriver.common.by import By

    # Các từ bị blacklist khỏi fallback "any button"
    BTN_BLACKLIST = {"back", "cancel", "close", "x", "retry", "discord", "skip", "report"}

    log("Buoc 5: Xu ly quiz welcome...", "INFO")
    time.sleep(3)

    for quiz_step in range(30):
        current_url = driver.current_url
        log(f"Quiz buoc {quiz_step+1}: {current_url}", "INFO")

        # Đã thoát khỏi quiz → xong
        if "quiz" not in current_url and "welcome" not in current_url:
            log("Da qua het quiz, vao trang chinh!", "OK")
            return True

        # Kiểm tra và xử lý trang lỗi trước khi làm gì khác
        if check_and_handle_error_page(driver):
            log("Da xu ly loi, tiep tuc quiz...", "INFO")
            time.sleep(2)
            continue  # Bỏ qua bước này, lặp lại để check URL mới

        time.sleep(1.5)

        # --- Bước A: Click đại option đầu tiên tìm được ---
        option_clicked = False

        # Loại quiz emoji/reaction (Strongly Agree / Agree / ...)
        for label in ["Strongly Agree", "Agree"]:
            try:
                btns = [b for b in driver.find_elements(By.XPATH,
                    f"//button[@aria-label='{label}']") if b.is_displayed()]
                if btns:
                    try_click(driver, btns[0], f"Quiz emoji: {label}")
                    log(f"Da chon: '{label}'", "OK")
                    option_clicked = True
                    time.sleep(1)
                    break
            except Exception:
                pass

        # Loại quiz thông thường (aria-pressed)
        if not option_clicked:
            for xpath in ["//button[@aria-pressed='false']", "//button[@aria-pressed]"]:
                try:
                    opts = [o for o in driver.find_elements(By.XPATH, xpath) if o.is_displayed()]
                    if opts:
                        try_click(driver, opts[0], f"Quiz opt: '{opts[0].text.strip()[:30]}'")
                        log(f"Da chon option: '{opts[0].text.strip()[:40]}'", "OK")
                        option_clicked = True
                        time.sleep(1)
                        break
                except Exception:
                    pass

        # ── Bước B: Bấm nút tiếp tục ────────────────────────────────────
        nav_keywords = ["continue", "next", "get started", "start", "done",
                        "finish", "submit", "proceed", "confirm"]
        continued = False

        # Ưu tiên: button không phải option, có keyword nav
        try:
            for btn in driver.find_elements(By.XPATH,
                    "//button[not(@aria-pressed) and not(@aria-label)]"):
                if not btn.is_displayed() or not btn.is_enabled():
                    continue
                txt = btn.text.strip().lower()
                if txt and any(kw in txt for kw in nav_keywords):
                    try_click(driver, btn, f"Quiz nav: '{btn.text.strip()}'")
                    continued = True
                    time.sleep(2.5)
                    break
        except Exception:
            pass

        # button[type=submit]
        if not continued:
            try:
                for btn in driver.find_elements(By.CSS_SELECTOR, "button[type='submit']"):
                    if btn.is_displayed() and btn.is_enabled():
                        try_click(driver, btn, "Quiz submit")
                        continued = True
                        time.sleep(2.5)
                        break
            except Exception:
                pass

        # Fallback cuối: bất kỳ button nào không bị blacklist
        if not continued:
            try:
                for btn in driver.find_elements(By.XPATH,
                        "//button[not(@aria-pressed) and not(@aria-label)]"):
                    if not btn.is_displayed() or not btn.is_enabled():
                        continue
                    txt = btn.text.strip()
                    if txt and txt.lower() not in BTN_BLACKLIST:
                        try_click(driver, btn, f"Quiz fallback: '{txt[:30]}'")
                        continued = True
                        time.sleep(2.5)
                        break
            except Exception:
                pass

        if not continued:
            log("Khong tim thay nut tiep theo quiz buoc nay, thu lai...", "WARN")
            time.sleep(2)
            if "quiz" not in driver.current_url and "welcome" not in driver.current_url:
                log("Da thoat quiz!", "OK")
                return True
            try:
                from selenium.webdriver.common.keys import Keys
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.RETURN)
                time.sleep(2)
            except Exception:
                pass
            # Không break - tiếp tục vòng lặp

    log("Ket thuc xu ly quiz (het 30 buoc).", "INFO")
    return True



def wait_for_home(driver, timeout=60):
    log("Cho vao trang chinh Higgsfield...", "INFO")
    start = time.time()
    while time.time() - start < timeout:
        url = driver.current_url
        if "higgsfield.ai" in url and "quiz" not in url and "/login" not in url:
            log(f"Da vao trang chinh: {url}", "OK")
            return True
        time.sleep(2)
    log("Het thoi gian cho trang chinh!", "WARN")
    return False

def step6_open_pricing(driver):
    """Bước 6: Mở trang pricing sau khi đăng ký xong"""
    log("Buoc 6: Mo trang pricing...", "INFO")
    try:
        driver.get("https://higgsfield.ai/pricing")
        time.sleep(3)
        log("Da mo trang: https://higgsfield.ai/pricing", "OK")
    except Exception as e:
        log(f"Loi mo trang pricing: {e}", "WARN")

def save_account(email, password):
    line = f"{email}\t{password}"
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    log(f"Da luu tai khoan -> {OUTPUT_FILE}: {email}", "OK")

# ─────────────────── Main flow ───────────────────────────────────────────────
ACTIVE_DRIVERS = []

def register_one_account(index, keep_open=False, batch_size=3, use_proxy=True, headless=False, browser_type="chrome"):
    email = None
    driver = None
    password = PASSWORD
    try:
        email = create_random_email()
        if not email:
            log(f"Acc #{index}: Khong tao duoc email!", "ERR")
            return False
        log(f"[{index}] Dang dang ky voi email: {email}", "INFO")
        driver = setup_driver(index, keep_open, use_proxy=use_proxy, batch_size=batch_size, headless=headless, browser_type=browser_type)
        if not headless:
            ACTIVE_DRIVERS.append(driver)
        if not step1_open_signup(driver):
            log(f"[{index}] Khong mo duoc trang Sign up!", "ERR")
            return False
        if not step2_click_email(driver):
            log(f"[{index}] Khong click duoc Continue with Email!", "ERR")
            return False
        if not step3_fill_form(driver, email, password):
            log(f"[{index}] Khong dien duoc form!", "ERR")
            return False
        if not step4_enter_otp(driver, email):
            log(f"[{index}] Khong xac nhan duoc OTP!", "ERR")
            return False
            
        if headless:
            save_account(email, password)
            log(f"[{index}] DANG KY THANH CONG! Email: {email}", "OK")
            return True
            
        step5_complete_quiz(driver)
        wait_for_home(driver, timeout=30)
        save_account(email, password)
        log(f"[{index}] DANG KY THANH CONG! Email: {email}", "OK")
        step6_open_pricing(driver)
        return True
    except Exception as e:
        log(f"[{index}] LOI KHONG MONG MUON: {type(e).__name__}: {e}", "ERR")
        if driver:
            try:
                driver.save_screenshot(f"higgsfield_error_{index}.png")
                log(f"Da luu anh loi: higgsfield_error_{index}.png", "INFO")
            except: pass
        return False
    finally:
        if email:
            delete_mailbox(email)
        if driver and not keep_open:
            try:
                if driver in ACTIVE_DRIVERS: ACTIVE_DRIVERS.remove(driver)
                driver.quit()
                log("Da dong trinh duyet.", "INFO")
            except: pass

def register_multiple(count, threads, keep_open=False, use_proxy=True, headless=False, browser_type="chrome"):
    import concurrent.futures
    results = {"ok": 0, "fail": 0}
    def worker(i):
        log(f"BAT DAU LUONG {i}/{count}", "INFO")
        time.sleep((i % threads) * 2.5)
        return register_one_account(i, keep_open, batch_size=threads, use_proxy=use_proxy, headless=headless, browser_type=browser_type)
    for batch_start in range(0, count, threads):
        batch_end = min(batch_start + threads, count)
        current_batch = batch_end - batch_start
        log(f"--- DOT: Luong {batch_start+1}>{batch_end} ({current_batch} tab) ---", "WARN")
        with concurrent.futures.ThreadPoolExecutor(max_workers=current_batch) as executor:
            futures = [executor.submit(worker, i+1) for i in range(batch_start, batch_end)]
            for future in concurrent.futures.as_completed(futures):
                if future.result(): results["ok"] += 1
                else: results["fail"] += 1
    log(f"\n{'='*50}", "INFO")
    log(f"KET QUA: {results['ok']} thanh cong / {results['fail']} that bai", "OK")
    log(f"{'='*50}\n", "INFO")

# ─────────────────── Entry point ─────────────────────────────────────────────
if __name__ == "__main__":
    print(f"""
{C.BOLD}{C.INFO}
╔══════════════════════════════════════════════════════╗
║      AUTO DANG KY TAI KHOAN HIGGSFIELD.AI             ║
║  Email ngau nhien + OTP tu dong + Quiz tu dong        ║
╚══════════════════════════════════════════════════════╝
{C.RST}""")
    try:
        import selenium
    except ImportError:
        print("Dang cai dat selenium...")
        os.system(f"{sys.executable} -m pip install selenium webdriver-manager requests -q")

    while True:
        print(f"\n{C.WARN}=== MENU ==={C.RST}")
        print("1. Tao tai khoan (giu trinh duyet mo sau khi xong)")
        print("2. Tao tai khoan (tu dong trinh duyet)")
        choice_func = input("👉 Chon 1 hoac 2: ").strip()
        if choice_func not in ["1", "2"]:
            print(f"{C.ERR}Lua chon khong hop le!{C.RST}")
            continue
        keep_open = (choice_func == "1")
        try:
            count = int(input(f"{C.WARN}So tai khoan muon tao: {C.RST}").strip() or "1")
            threads = int(input(f"{C.WARN}So tab mo cung luc: {C.RST}").strip() or "1")
            use_proxy_input = input(f"{C.WARN}Dung proxy? (y/n, mac dinh y): {C.RST}").strip().lower()
            use_proxy = use_proxy_input != "n"
        except ValueError:
            print(f"{C.ERR}So luong phai la so nguyen!{C.RST}")
            continue
        log(f"Se tao {count} tai khoan, {threads} tab cung luc, proxy={'Co' if use_proxy else 'Khong'}.", "INFO")
        log(f"Password mac dinh: {PASSWORD}", "INFO")
        log(f"Ket qua luu vao: {OUTPUT_FILE}", "INFO")
        print()
        register_multiple(count, threads, keep_open, use_proxy, headless=False, browser_type="chrome")
        print(f"\n{C.OK}✅ DA CHAY XONG!{C.RST}")
        if keep_open:
            print(f"{C.WARN}⚠️ Cac tab van mo! Tat thu cong neu can.{C.RST}")
        choice = input(f"{C.BOLD}👉 Enter de tao tiep, 'q' de thoat: {C.RST}")
        if choice.strip().lower() == "q":
            if keep_open and ACTIVE_DRIVERS:
                log("Dang dong tat ca trinh duyet...", "INFO")
                for d in ACTIVE_DRIVERS:
                    try: d.quit()
                    except: pass
            print("Tam biet!")
            break
