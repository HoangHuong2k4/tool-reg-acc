#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

# LocalProxyRelay - TCP relay để forward proxy auth (không cần incognito)

import subprocess

class LocalProxyRelay:
    """
    Local TCP proxy relay chạy trên localhost.
    Chrome kết nối vào đây không cần auth,
    relay tự động thêm Proxy-Authorization và forward lên proxy thật.
    """
    def __init__(self, upstream_host, upstream_port, username, password, local_port):
        self.upstream_host = upstream_host
        self.upstream_port = int(upstream_port)
        self.auth_b64 = base64.b64encode(
            f"{username}:{password}".encode()
        ).decode()
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
                _threading.Thread(
                    target=self._handle_client,
                    args=(client,),
                    daemon=True
                ).start()
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

            auth_header = (
                f"Proxy-Authorization: Basic {self.auth_b64}\r\n"
            ).encode()

            if b"\r\n\r\n" in raw:
                head, body = raw.split(b"\r\n\r\n", 1)
                lines = head.split(b"\r\n")
                lines = [l for l in lines
                         if not l.lower().startswith(b"proxy-authorization:")]
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
                
                # NẾU proxy trả về 407 (Sai pass/hết hạn), KHÔNG trả về cho Chrome (sẽ dính popup)
                # Thay vào đó trả về 502 để Chrome văng ERR_TUNNEL_CONNECTION_FAILED -> Tự động Retry
                if b" 407 " in resp.split(b"\r\n")[0]:
                    client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    return
                    
                client.sendall(resp)
                if b"200" in resp.split(b"\r\n")[0]:
                    self._tunnel(client, upstream)
            else:
                self._tunnel(client, upstream)

        except Exception as e:
            log(f"[Relay] Lỗi kết nối proxy: {e}", "WARN")
        finally:
            for s in (client, upstream):
                if s:
                    try: s.close()
                    except: pass

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
BASE_URL    = "https://regmail.phh.info.vn"
API_KEY     = "1dec9d51e8707e9bf1fa7756612830c676f65a42a1009851580ec0a82384abd8"
PASSWORD    = "capcut123"
CAPCUT_URL  = "https://www.capcut.com/vi-vn/signup"
OUTPUT_FILE = "accounts.txt"
DOB_YEAR  = "2004"
DOB_MONTH = "12"
DOB_DAY   = "12"

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

def create_random_email():
    resp = requests.post(f"{BASE_URL}/api/emails/create", headers=API_HEADERS, proxies={"http": None, "https": None}, timeout=10)
    data = resp.json()
    if data.get("success") and data.get("email"):
        log(f"Đã tạo email: {C.BOLD}{data['email']}{C.RST}", "OK")
        return data["email"]
    raise Exception(f"Không tạo được email: {data}")

def get_latest_email(email_address):
    resp = requests.get(f"{BASE_URL}/api/emails/latest", headers=API_HEADERS, params={"email": email_address}, proxies={"http": None, "https": None}, timeout=10)
    data = resp.json()
    if data.get("success") and data.get("email"):
        return data["email"]
    return None

def wait_for_otp(email_address, timeout=120, interval=4):
    log(f"Đang chờ OTP cho {email_address} (tối đa {timeout}s)...", "INFO")
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
                log(f"Nhận được OTP: {C.BOLD}{otp}{C.RST}", "OK")
                return otp
            log("Nhận được email nhưng chưa có OTP, chờ thêm...", "WARN")
        time.sleep(interval)
        elapsed += interval
    log("Hết thời gian chờ OTP!", "ERR")
    return None

def delete_mailbox(email_address):
    try:
        requests.delete(f"{BASE_URL}/api/emails/address/{email_address}", headers=API_HEADERS, proxies={"http": None, "https": None}, timeout=10)
        log(f"Đã dọn hòm thư: {email_address}", "OK")
    except Exception as e:
        log(f"Lỗi xóa mail: {e}", "WARN")

def get_rotated_proxy():
    # Thử đọc settings từ DB
    try:
        import sqlite3
        import os
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database.db"))
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `value` FROM settings")
        settings = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        proxy_type = settings.get("PROXY_TYPE", "proxyquick")
        if proxy_type == "proxyxoay":
            key = settings.get("PROXYXOAY_KEY", "")
            url = f"https://proxyxoay.shop/api/get.php?key={key}&&nhamang=random&&tinhthanh=0&whitelist="
            log("Đang xoay IP qua ProxyXoay.shop API...", "INFO")
            resp = requests.get(url, timeout=15).json()
            if resp.get("status") == 100:
                proxy_str = resp.get("proxyhttp", "")
                parts = proxy_str.split(":")
                log(f"Xoay IP thành công → {parts[0]}:{parts[1]}", "OK")
                return {"host": parts[0], "port": int(parts[1]), "user": "", "pass": ""}
            else:
                log(f"API xoay proxy lỗi: {resp} → dùng proxy cố định", "WARN")
        else:
            token = settings.get("PROXY_API_TOKEN", "")
            merchant = settings.get("PROXY_MERCHANT", "")
            proxy_id = settings.get("PROXY_ID", "953319")
            headers = {"Authorization": f"Bearer {token}", "x-merchant-id": merchant}
            url = f"https://proxyquick.click/api/v2/proxies/{proxy_id}/rotate"
            log("Đang xoay IP qua ProxyQuick API v2...", "INFO")
            resp = requests.get(url, headers=headers, proxies={"http": None, "https": None}, timeout=15).json()
            if resp.get("status") == "success":
                proxy_str = resp.get("proxy", "")
                parts = proxy_str.split(":")
                if len(parts) >= 4:
                    log(f"Xoay IP thành công → {resp.get('ip', '')}", "OK")
                    return {"host": parts[0], "port": int(parts[1]), "user": parts[2], "pass": parts[3]}
            log(f"API xoay proxy lỗi: {resp} → dùng proxy cố định", "WARN")
    except Exception as e:
        log(f"Lỗi gọi API proxy: {e}", "ERR")
    return None

def setup_driver(index=1, keep_open=False, use_api_proxy=True, batch_size=3, use_proxy=True, predefined_proxy=None, is_func2=False, shared_relay_port=None, headless=False, browser_type="chrome"):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    options = Options()
    if is_func2:
        options.add_argument("--incognito")
    else:
        # Không dùng --incognito: tránh bị CapCut phát hiện và không load được Extension
        pass
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    if keep_open:
        options.add_experimental_option("detach", True)
    
    # Chia đều màn hình theo số tab (max 4 cột, thừa thì chồng lên)
    cols = min(batch_size, 4)       # số cột thực tế
    SCREEN_W = 1920; SCREEN_H = 1080
    window_width  = SCREEN_W // cols
    window_height = SCREEN_H
    idx = (index - 1) % cols        # tab > 4 sẽ chồng lên cột 0..3
    x = idx * window_width
    y = 0
    
    options.add_argument(f"--window-size={window_width},{window_height}")
    options.add_argument(f"--window-position={x},{y}")
    options.add_argument("--lang=vi-VN")

    if shared_relay_port:
        options.add_argument(f"--proxy-server=http://127.0.0.1:{shared_relay_port}")
        options.add_argument("--proxy-bypass-list=<-loopback>")
        PROXY_HOST = None
        PROXY_USER = None
        PROXY_PASS = None
        PROXY_PORT = None
        use_proxy = False

    proxy = None
    PROXY_HOST = None
    if use_proxy:
        if predefined_proxy:
            proxy = predefined_proxy
            log("Đang dùng proxy chung (Shared Proxy) cho chức năng 2...", "INFO")
        elif use_api_proxy:
            proxy = get_rotated_proxy()
            
        if proxy:
            PROXY_HOST, PROXY_PORT = proxy["host"], proxy["port"]
            PROXY_USER, PROXY_PASS = proxy["user"], proxy["pass"]
            log(f"Đang dùng Proxy API: {PROXY_HOST}:{PROXY_PORT}", "INFO")
        else:
            # Dự phòng nếu API lỗi
            PROXIES = [
                {"host": "180.93.2.171", "port": 3131, "user": "kierangrayson226", "pass": "odq0nda0odmzoa=="}
            ]
            proxy = random.choice(PROXIES)
            PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS = proxy["host"], proxy["port"], proxy["user"], proxy["pass"]
            log(f"Đang dùng Proxy dự phòng: {PROXY_HOST}:{PROXY_PORT}", "INFO")

    if PROXY_HOST:
        if PROXY_USER and PROXY_PASS:
            relay = LocalProxyRelay(
                upstream_host=PROXY_HOST,
                upstream_port=PROXY_PORT,
                username=PROXY_USER,
                password=PROXY_PASS,
                local_port=0
            ).start()
            options.add_argument(f"--proxy-server=http://127.0.0.1:{relay.local_port}")
            options.add_argument("--proxy-bypass-list=<-loopback>")
        else:
            options.add_argument(f"--proxy-server=http://{PROXY_HOST}:{PROXY_PORT}")


    if browser_type.lower() in ["firefox", "camoufox"]:
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        ff_options = FirefoxOptions()
        if headless:
            ff_options.add_argument("--headless")
        ff_options.add_argument(f"--width={window_width}")
        ff_options.add_argument(f"--height={window_height}")
        
        import os
        camoufox_path = os.path.expanduser("~/Library/Caches/camoufox/Camoufox.app/Contents/MacOS/camoufox")
        if browser_type.lower() == "camoufox" and os.path.exists(camoufox_path):
            ff_options.binary_location = camoufox_path
            log("Đang sử dụng trình duyệt Camoufox!", "OK")
            
        if PROXY_HOST:
            if PROXY_USER and PROXY_PASS:
                ff_options.set_preference("network.proxy.type", 1)
                ff_options.set_preference("network.proxy.http", "127.0.0.1")
                ff_options.set_preference("network.proxy.http_port", relay.local_port)
                ff_options.set_preference("network.proxy.ssl", "127.0.0.1")
                ff_options.set_preference("network.proxy.ssl_port", relay.local_port)
            else:
                ff_options.set_preference("network.proxy.type", 1)
                ff_options.set_preference("network.proxy.http", PROXY_HOST)
                ff_options.set_preference("network.proxy.http_port", PROXY_PORT)
                ff_options.set_preference("network.proxy.ssl", PROXY_HOST)
                ff_options.set_preference("network.proxy.ssl_port", PROXY_PORT)
                
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
    """Bước 2: Nhập mật khẩu và bấm Đăng ký"""
    from selenium.webdriver.common.by import By

    log("Bước 2: Nhập mật khẩu...", "INFO")

    pwd_input = wait_for_element(driver, By.CSS_SELECTOR,
        'input[type="password"]', timeout=20)

    set_react_input(driver, pwd_input, password)
    time.sleep(0.5)

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

    # Bấm Đăng ký / Register / Sign up
    signup_xpaths = [
        '//button[contains(text(),"Đăng ký") or contains(text(),"Register") or contains(text(),"Sign up")]',
        '//button[@type="submit"]',
        '//button[contains(@class,"primary") or contains(@class,"submit") or contains(@class,"sign")]',
        '//div[contains(@id,"submit")]/button',
    ]
    for attempt in range(3):
        for xpath in signup_xpaths:
            try:
                els = driver.find_elements(By.XPATH, xpath)
                for el in els:
                    if el.is_displayed() and el.is_enabled():
                        try_click(driver, el, f"Đăng ký: '{el.text.strip()[:20]}'")
            except Exception:
                pass
        time.sleep(1)

    log("Đã nhập mật khẩu và bấm Đăng ký", "OK")
    time.sleep(2)

def step3_enter_birthday(driver):
    """Bước 3: Điền năm/tháng/ngày sinh"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    log("Bước 3: Điền ngày sinh...", "INFO")

    # Chờ màn hình ngày sinh
    wait_for_element(driver, By.CSS_SELECTOR,
        '.lv_sign_in_panel_wide-birthday-detail, .gate_birthday-picker', timeout=20)
    time.sleep(0.5)

    # Nhập Năm
    try:
        year_input = driver.find_element(By.CSS_SELECTOR,
            '.gate_birthday-picker-input, input[placeholder="Năm"]')
        set_react_input(driver, year_input, DOB_YEAR)
        log(f"Đã nhập năm: {DOB_YEAR}", "OK")
        time.sleep(0.5)
    except Exception as e:
        log(f"Không tìm thấy ô nhập năm: {e}", "WARN")

    # Chọn Tháng (dropdown)
    try:
        selectors = driver.find_elements(By.CSS_SELECTOR, '.gate_birthday-picker-selector')
        if selectors:
            month_sel = selectors[0]
            try_click(driver, month_sel, "Month dropdown")
            time.sleep(0.8)

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
            time.sleep(0.5)
    except Exception as e:
        log(f"Lỗi chọn tháng: {e}", "WARN")

    # Chọn Ngày (dropdown)
    try:
        selectors = driver.find_elements(By.CSS_SELECTOR, '.gate_birthday-picker-selector')
        if len(selectors) >= 2:
            day_sel = selectors[1]
            try_click(driver, day_sel, "Day dropdown")
            time.sleep(0.8)

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
            time.sleep(0.5)
    except Exception as e:
        log(f"Lỗi chọn ngày: {e}", "WARN")

    # Bấm Tiếp theo
    time.sleep(0.5)
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

def step4_enter_otp(driver, email):
    """Bước 4: Chờ OTP và nhập vào ô xác nhận"""
    from selenium.webdriver.common.by import By

    log("Bước 4: Chờ và nhập OTP...", "INFO")

    # Chờ màn hình xác nhận email
    wait_for_element(driver, By.CSS_SELECTOR,
        '.lv_sign_in_panel_wide-code-detail, .verification_code_input-wrapper', timeout=25)

    log("Màn hình xác nhận email xuất hiện. Đang lấy OTP từ API...", "INFO")

    # Chờ 5 giây để email server nhận thư
    time.sleep(5)

    otp = wait_for_otp(email, timeout=120, interval=4)
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

def step_close_whats_new(driver, timeout=10):
    """Đóng modal 'What's new' nếu xuất hiện"""
    from selenium.webdriver.common.by import By
    log("Kiểm tra modal 'What's new'...", "INFO")
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Kiểm tra modal featuresTab có xuất hiện không
            modals = driver.find_elements(By.CSS_SELECTOR, '.featuresTab')
            if modals and any(m.is_displayed() for m in modals):
                close_btns = driver.find_elements(By.CSS_SELECTOR, '.lv-modal-close-icon')
                for btn in close_btns:
                    if btn.is_displayed():
                        try_click(driver, btn, "Đóng modal What's new")
                        log("Đã đóng modal 'What's new'!", "OK")
                        time.sleep(1)
                        return True
        except Exception as e:
            log(f"Lỗi kiểm tra modal What's new: {e}", "WARN")
        time.sleep(1)
    log("Không thấy modal 'What's new' (bỏ qua).", "INFO")
    return False

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

ACTIVE_DRIVERS = []

def register_one_account(index, join_link=None, keep_open=False, batch_size=3, predefined_proxy=None, shared_relay_port=None, headless=False, browser_type="chrome", get_link=False, **kwargs):
    email = None
    driver = None
    password = PASSWORD

    try:
        email = create_random_email()
        if not email:
            log(f"Acc #{index}: Hết email khả dụng!", "ERR")
            return False

        max_retries = 3
        for attempt in range(max_retries):
            is_func2 = bool(join_link)
            driver = setup_driver(index, keep_open, use_api_proxy=True, batch_size=batch_size, use_proxy=True, predefined_proxy=predefined_proxy, is_func2=is_func2, shared_relay_port=shared_relay_port, headless=headless, browser_type=browser_type)
            ACTIVE_DRIVERS.append(driver)
            log(f"[{email}] Bắt đầu mở trình duyệt... (Lần thử {attempt+1})", "INFO")
            
            try:
                driver.get("https://www.capcut.com/vi-vn/login")
                break
            except Exception as e:
                if "ERR_TUNNEL_CONNECTION_FAILED" in str(e) or "ERR_PROXY_CONNECTION_FAILED" in str(e) or "TimeoutException" in type(e).__name__:
                    if attempt < max_retries - 1:
                        log(f"[{email}] Lỗi kết nối/proxy, đang đổi proxy và thử lại... ({type(e).__name__})", "WARN")
                        try:
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
        step3_enter_birthday(driver)
        if not step4_enter_otp(driver, email):
            return False

        msToken = ""
        try:
            for cookie in driver.get_cookies():
                if cookie['name'] == 'msToken':
                    msToken = cookie['value']
                    break
        except: pass

        if join_link:
            step5_join_team(driver, join_link)
            # Nếu KHÔNG chuyển qua trang my-cloud (nghĩa là lỗi full team hoặc web đứng)
            if not wait_for_dashboard(driver):
                log("Không thể join team (bị kẹt ở trang join) -> HỦY LƯU TÀI KHOẢN NÀY!", "ERR")
                return False
                
            uidname = extract_uidname(driver)
            save_account(uidname, email, password, join_link, msToken)
            log(f"ĐĂNG KÝ THÀNH CÔNG! {email} (UID: {uidname})", "OK")
        else:
            step5_open_capcut(driver)
            if not wait_for_dashboard(driver):
                log("Không vào được CapCut -> HỦY LƯU!", "ERR")
                return False
                
            uidname = extract_uidname(driver)
            log(f"ĐĂNG KÝ THÀNH CÔNG! {email} (UID: {uidname})", "OK")

            # Các bước sau đăng ký thành công (chỉ chạy cho chức năng 1)
            log("Đang xử lý các popup sau đăng ký...", "INFO")
            step_skip_role_survey(driver, timeout=10)
            step_close_whats_new(driver, timeout=10)
            
            cashier_link = api_upgrade_vip(driver)
            save_account(uidname, email, password, cashier_link, msToken)

        return True

    except Exception as e:
        log(f"LỖI KHÔNG MONG MUỐN: {type(e).__name__}: {e}", "ERR")
        if driver:
            try:
                driver.save_screenshot(f"error_{index}.png")
                log(f"Đã lưu ảnh màn hình lỗi: error_{index}.png", "INFO")
            except: pass
        return False
    finally:
        if email: delete_mailbox(email)
        if driver and not keep_open:
            try:
                if driver in ACTIVE_DRIVERS: ACTIVE_DRIVERS.remove(driver)
                driver.quit()
                log("Đã đóng trình duyệt.", "INFO")
            except: pass

def register_multiple(count, threads, join_link, keep_open=False):
    import concurrent.futures
    results = {"ok": 0, "fail": 0}
    
    shared_proxy = None
    shared_relay_port = None
    relay = None
    if join_link:
        log("Chức năng 2: Chạy chế độ ẩn danh và dùng 1 proxy cố định chung cho các tab...", "INFO")
        shared_proxy = {"host": "180.93.2.171", "port": 3131, "user": "kierangrayson226", "pass": "odq0nda0odmzoa=="}
        # Tự động auth bằng extension nên không cần relay nữa
        shared_relay_port = None
        
    def worker(i, b_size):
        log(f"BẮT ĐẦU LUỒNG {i}/{count}", "INFO")
        # Stagger mở tab để tránh proxy bị quá tải (ERR_TUNNEL_CONNECTION_FAILED)
        time.sleep((i % b_size) * 2.5) 
        return register_one_account(i, join_link, keep_open, batch_size=b_size, predefined_proxy=shared_proxy, shared_relay_port=shared_relay_port)

    for batch_start in range(0, count, threads):
        batch_end = min(batch_start + threads, count)
        current_batch_count = batch_end - batch_start
        log(f"--- BẮT ĐẦU ĐỢT: Chạy luồng {batch_start+1} đến {batch_end} ({current_batch_count} tab) ---", "WARN")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=current_batch_count) as executor:
            futures = [executor.submit(worker, i+1, current_batch_count) for i in range(batch_start, batch_end)]
            for future in concurrent.futures.as_completed(futures):
                if future.result(): results["ok"] += 1
                else: results["fail"] += 1

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
        print("1. Chỉ tạo tài khoản ngẫu nhiên (Lưu vào file txt - KHÔNG TỰ ĐÓNG TRÌNH DUYỆT)")
        print("2. Tạo tài khoản + Auto Join Team + Gửi lên Google Sheet")
        choice_func = input(f"👉 Chọn 1 hoặc 2: ").strip()

        if choice_func not in ["1", "2"]:
            print(f"{C.ERR}Lựa chọn không hợp lệ! Vui lòng nhập 1 hoặc 2.{C.RST}")
            continue

        join_link = None
        keep_open = False
        try:
            if choice_func == "2":
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
            log(f"Chỉ lưu tài khoản vào file {OUTPUT_FILE} (Giữ trình duyệt mở).", "INFO")
        print()

        register_multiple(count, threads, join_link, keep_open)
        
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
                    try: d.quit()
                    except: pass
            print("Tạm biệt!")
            break
