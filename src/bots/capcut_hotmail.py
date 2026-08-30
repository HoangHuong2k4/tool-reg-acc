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
HOTMAIL_API_URL = 'https://tools.dongvanfb.net/api/get_messages_oauth2'
HOTMAIL_FILE = "data/hotmails.txt"

CAPCUT_URL  = "https://www.capcut.com/vi-vn/signup"
OUTPUT_FILE = "data/accounts.txt"
DOB_YEAR  = "2004"
DOB_MONTH = "12"
DOB_DAY   = "12"


import queue
import threading
HOTMAIL_QUEUE = queue.Queue()
FILE_LOCK = threading.Lock()

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

def wait_for_otp(email, password, refresh_token, client_id, timeout=120, interval=4, after_ts=0, mail_api_source="mixmmo"):
    api_url = HOTMAIL_API_URL if mail_api_source == "dongvanfb" else "https://mixmmo.com/api/get-hotmail-messages.php"
    log(f"Đang chờ OTP cho {email} qua {mail_api_source.upper()} API (tối đa {timeout}s)...", "INFO")
    
    if mail_api_source == "dongvanfb":
        headers = {"Content-Type": "application/json"}
        payload = {
            "email": email,
            "pass": password,
            "refresh_token": refresh_token,
            "client_id": client_id,
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
    
    elapsed = 0
    while elapsed < timeout:
        if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
            log("Task bị dừng bởi người dùng, thoát chờ OTP!", "WARN")
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
                        otp = msg.get("code", "").strip()
                        if otp and otp.isdigit() and len(otp) == 6:
                            log(f"Nhận được OTP: {C.BOLD}{otp}{C.RST}", "OK")
                            return otp
                            
                        subject = msg.get("subject", "")
                        message = msg.get("message", "")
                        bodyText = msg.get("bodyText", "")
                        
                        clean_message = re.sub(r'<style[^>]*>.*?</style>', ' ', message, flags=re.IGNORECASE)
                        clean_message = re.sub(r'<[^>]+>', ' ', clean_message)
                        text_to_search = subject + " " + clean_message + " " + bodyText
                        
                        match = re.search(r'\b(\d{6})\b', text_to_search)
                        if match:
                            otp = match.group(1)
                            log(f"Nhận được OTP: {C.BOLD}{otp}{C.RST}", "OK")
                            return otp
            else:
                log(f"API Hotmail trả về lỗi: {data}", "WARN")
                
        except Exception as e:
            log(f"Lỗi gọi API Hotmail: {e}", "WARN")
            
        time.sleep(interval)
        elapsed += interval
    
    log("Hết thời gian chờ OTP!", "ERR")
    return None

def get_settings_from_db():
    import sqlite3
    import os
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database.db"))
    settings = {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `value` FROM settings")
        settings = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
    except Exception:
        pass
    return settings

def get_rotated_proxy():
    FALLBACK_PROXY  = {"host": "180.93.2.171", "port": 3131, "user": "kierangrayson226", "pass": "odq0nda0odmzoa=="}
    # Thử đọc settings từ DB
    try:
        settings = get_settings_from_db()
        
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
    log(f"Dùng proxy cố định: {FALLBACK_PROXY['host']}:{FALLBACK_PROXY['port']}", "OK")
    return FALLBACK_PROXY

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
    
    # Chia đều màn hình theo số tab (max 4 cột, thừa thì chồng lên)
    cols = min(batch_size, 2)       # số cột thực tế
    SCREEN_W = 1920; SCREEN_H = 1080
    window_width  = SCREEN_W // cols
    window_height = SCREEN_H
    idx = index % cols        # tab > 4 sẽ chồng lên cột 0..3
    x = idx * window_width
    y = 0
    
    options.add_argument(f"--window-size={window_width},{window_height}")
    options.add_argument(f"--window-position={x},{y}")
    options.add_argument("--lang=vi-VN")

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
            # Dự phòng nếu API lỗi - proxy này có thể đã chết, kiểm tra lại!
            PROXIES = [
                {"host": "180.93.2.171", "port": 3131, "user": "kierangrayson226", "pass": "odq0nda0odmzoa=="}
            ]
            proxy = random.choice(PROXIES)
            PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS = proxy["host"], proxy["port"], proxy["user"], proxy["pass"]
            log(f"[⚠️ DỰ PHÒNG] API proxy lỗi -> dùng proxy cứ: {PROXY_HOST}:{PROXY_PORT} (có thể đã chết!)", "WARN")

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
        if incognito:
            ff_options.add_argument("-private")
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


def step4_enter_otp(driver, email, password, refresh_token, client_id, mail_api_source="mixmmo"):
    """Bước 4: Chờ OTP và nhập vào ô xác nhận"""
    from selenium.webdriver.common.by import By

    log("Bước 4: Chờ và nhập OTP...", "INFO")

    # Chờ màn hình xác nhận email
    wait_for_element(driver, By.CSS_SELECTOR,
        '.lv_sign_in_panel_wide-code-detail, .verification_code_input-wrapper', timeout=25)

    log("Màn hình xác nhận email xuất hiện. Đang lấy OTP từ API...", "INFO")

    # Chờ 5 giây để email server nhận thư
    time.sleep(5)

    otp = wait_for_otp(email, password, refresh_token, client_id, timeout=120, interval=4, mail_api_source=mail_api_source)

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

def update_account_payment_link(email, link):
    pass # File handling for success_links.txt is already done in step_get_payment_link

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


def step_get_payment_link(driver, email, password):
    import time
    for attempt in range(5):
        res = _do_get_payment_link(driver, email, password, attempt)
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

def _do_get_payment_link(driver, email, password, attempt=0):
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

                # Tìm nút thanh toán trong modal
                action_btns = driver.find_elements(By.CSS_SELECTOR, '.subscriptionProductSection-pro button.subscriptionProductSection-actionDark, button.subscriptionProductSection-actionGradient, button.subscriptionProductSection-actionDark')
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
            os.makedirs("data", exist_ok=True)
            with open("data/success_links.txt", "a", encoding="utf-8") as f:
                f.write(f"{email}\t{password}\t{payment_url}\n")
            return payment_url



        log("Không tìm thấy link thanh toán pipopay sau khi bấm Nâng cấp!", "WARN")
        return None

    except Exception as e:
        log(f"Lỗi lấy link: {e}", "ERR")
        return None


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
                if driver in ACTIVE_DRIVERS: ACTIVE_DRIVERS.remove(driver)
                driver.quit()
            except: pass


def register_one_account(index, join_link=None, keep_open=False, batch_size=3, predefined_proxy=None, headless=False, browser_type="chrome", get_link=False, mail_api_source="mixmmo", incognito=False, **kwargs):
    try:
        acc = HOTMAIL_QUEUE.get_nowait()
    except queue.Empty:
        log(f"Acc #{index}: Hết hotmail trong hàng đợi!", "ERR")
        return False
        
    email = acc["email"]

    email_pass = acc["pass"]
    refresh_token = acc["refresh_token"]
    client_id = acc["client_id"]
    password = get_settings_from_db().get("CAPCUT_PASSWORD", "capcut123") or "capcut123"

    driver = None
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
                        log(f"[{email}] Lỗi kết nối/proxy, đang đổi proxy và thử lại... ({type(e).__name__})", "WARN")
                        try:
                            import requests
                            requests.post("http://127.0.0.1:5050/api/proxy/rotate", timeout=5)
                            log("Đã yêu cầu API nội bộ xoay proxy mới!", "INFO")
                        except Exception as re_err:
                            log(f"Không thể gọi API xoay proxy: {re_err}", "WARN")

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
        bday_status = step3_enter_birthday(driver)
        if bday_status != "ALREADY_LOGGED_IN":
            if not step4_enter_otp(driver, email, email_pass, refresh_token, client_id, mail_api_source):
                return False

        msToken = ""
        try:
            for cookie in driver.get_cookies():
                if cookie['name'] == 'msToken':
                    msToken = cookie['value']
                    break
        except: pass

        if join_link:
            if bday_status != "ALREADY_LOGGED_IN":
                step5_join_team(driver, join_link)
            if not wait_for_dashboard(driver):
                log("Không thể join team (bị kẹt ở trang join) -> HỦY LƯU TÀI KHOẢN NÀY!", "ERR")
                return False
                
            uidname = extract_uidname(driver)
            save_account(uidname, email, password, join_link, msToken)
            log(f"ĐĂNG KÝ & JOIN THÀNH CÔNG! {email} (UID: {uidname})", "OK")
        else:
            if bday_status != "ALREADY_LOGGED_IN":
                step5_open_capcut(driver)
            if not wait_for_dashboard(driver):
                log("Không vào được CapCut -> HỦY LƯU!", "ERR")
                return False
                
            uidname = extract_uidname(driver)
            log(f"ĐĂNG NHẬP / ĐĂNG KÝ THÀNH CÔNG! {email} (UID: {uidname})", "OK")

            # Lưu tài khoản NGAY sau khi tạo xong (không cần chờ link thanh toán)
            save_account(uidname, email, password, "", msToken)

            # Xử lý các popup sau đăng ký (chỉ chạy cho chức năng 1)
            log("Đang xử lý các popup sau đăng ký...", "INFO")
            step_skip_role_survey(driver, timeout=10)
            step_close_whats_new(driver, timeout=15)
            if get_link:
                link = step_get_payment_link(driver, email, password)
                if not link:
                    # Lưu cookie để retry sau
                    try:
                        cookies = driver.get_cookies()
                        save_pending_link(email, password, refresh_token, client_id, cookies)
                        log(f"Đã lưu cookie acc {email} để retry lấy link sau!", "WARN")
                    except Exception as ck_err:
                        log(f"Không lưu được cookie: {ck_err}", "WARN")

        # Chỉ đánh dấu hotmail đã dùng (trừ khỏi hotmails.txt) khi mọi thứ đều thành công
        mark_hotmail_used(acc)
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
        if driver and not keep_open:
            try:
                if driver in ACTIVE_DRIVERS: ACTIVE_DRIVERS.remove(driver)
                driver.quit()
                log("Đã đóng trình duyệt.", "INFO")
            except: pass


def load_hotmails_to_queue(limit=None):
    import os
    if not os.path.exists(HOTMAIL_FILE):
        log(f"Không tìm thấy file {HOTMAIL_FILE}", "ERR")
        return 0
    
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
    log(f"Đã tải {count} hotmail từ file {HOTMAIL_FILE}.", "OK")
    return count

def register_multiple(count, threads, join_link, keep_open=False, get_link=False):

    import concurrent.futures
    results = {"ok": 0, "fail": 0}
    
    shared_proxy = None
    if join_link:
        log("Chức năng 2: Đang lấy 1 proxy dùng chung cho tất cả các tab...", "INFO")
        shared_proxy = get_rotated_proxy()
        
    def worker(i):
        log(f"BẮT ĐẦU LUỒNG {i}/{threads}", "INFO")
        # Stagger mở tab để tránh proxy bị quá tải (ERR_TUNNEL_CONNECTION_FAILED)
        time.sleep((i % threads) * 2.5) 
        local_ok = 0
        local_fail = 0
        while not HOTMAIL_QUEUE.empty():
            res = register_one_account(i, join_link, keep_open, batch_size=threads, predefined_proxy=shared_proxy, get_link=get_link)
            if res: local_ok += 1
            else: local_fail += 1
            if keep_open:
                break
        return local_ok, local_fail

    log(f"--- BẮT ĐẦU ĐỢT: Chạy tối đa {count} tài khoản với {threads} luồng liên tục ---", "WARN")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(worker, i+1) for i in range(threads)]
        for future in concurrent.futures.as_completed(futures):
            ok, fail = future.result()
            results["ok"] += ok
            results["fail"] += fail

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
                            try: d.quit()
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
                    try: d.quit()
                    except: pass
            print("Tạm biệt!")
            break
        else:
            if keep_open and ACTIVE_DRIVERS:
                log("Đang đóng các tab cũ trước khi mở đợt mới...", "INFO")
                for d in ACTIVE_DRIVERS:
                    try: d.quit()
                    except: pass
                ACTIVE_DRIVERS.clear()
