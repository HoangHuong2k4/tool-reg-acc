# -*- coding: utf-8 -*-
"""
GPT Selenium Registration Utils - Tự động đăng ký tài khoản ChatGPT qua Selenium.

Flow đầy đủ:
  1. Mở chatgpt.com → Click Sign Up
  2. Nhập email → Submit
  3. Xử lý redirect (login → signup recovery)
  4. Click "Continue with password"
  5. Nhập password → Submit
  6. Nhập OTP (với retry + resend logic)
  7. Điền thông tin About You (random Vietnamese name)
  8. Skip Onboarding
  9. Setup 2FA (Settings → Security → MFA toggle → Trouble scanning → Extract secret → Verify)
"""
import logging
import random
import re
import time
import pyotp
import urllib.parse
import sqlite3
import os
import sys
import threading
import socket
import select
import base64
import subprocess
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ─── Screenshot directory ────────────────────────────────────────────────────
_SCREENSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "screenshots"))

# ─── Random Vietnamese Profile Generator ─────────────────────────────────────────

VIETNAMESE_FIRST_NAMES = [
    "Cataishop", "Huong", "Loan", "Yến", "Thật",
    "Tuấn", "Nam", "Long", "Linh", "Hoa",
    "Lan", "Mai", "Hải", "Sơn", "Bảo",
    "An", "Bình", "Châu", "Dương", "Hà",
]

VIETNAMESE_SURNAMES = [
    "Momo", "Lé", "Mập", "Thà", "Cute",
    "Vip", "Pro", "Xinh", "Đẹp", "Ngầu",
    "Bé", "Nhỏ", "Trùm", "Boss", "Đại",
    "Bảnh", "Chất", "Lùn", "Cao", "Mạnh",
]


def _generate_vietnamese_profile():
    """
    Sinh profile random kiểu Việt Nam.
    Returns: (full_name, age)
    """
    first = random.choice(VIETNAMESE_FIRST_NAMES)
    sur = random.choice(VIETNAMESE_SURNAMES)
    year = 2025 - random.randint(20, 30)
    age = 2025 - year
    return "{} {}".format(first, sur), age


# ─── Local Proxy Relay ────────────────────────────────────────────────────────

class LocalProxyRelay:
    """
    Local TCP proxy relay chạy trên localhost.
    Trình duyệt kết nối vào đây không cần auth,
    relay tự động thêm Proxy-Authorization và forward lên proxy thật.
    """
    def __init__(self, upstream_host, upstream_port, username, password, local_port=0):
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
        t = threading.Thread(target=self._accept_loop, daemon=True)
        t.start()
        logger.info(f"[Relay] Local proxy listening on 127.0.0.1:{self.local_port}")
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
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
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
        a.settimeout(600)
        b.settimeout(600)
        try:
            while True:
                r, _, _ = select.select([a, b], [], [], 300)
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

            auth_header = f"Proxy-Authorization: Basic {self.auth_b64}\r\n".encode()

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
        except Exception:
            pass
        finally:
            if upstream:
                try: upstream.close()
                except: pass
            if client:
                try: client.close()
                except: pass


# ─── DB Helper ────────────────────────────────────────────────────────────────

def get_db():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database.db"))
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Selenium Helper Functions ────────────────────────────────────────────────

def wait_for_element(driver, by, value, timeout=20):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.visibility_of_element_located((by, value)))


def wait_clickable(driver, by, value, timeout=20):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.element_to_be_clickable((by, value)))


def wait_any_element(driver, selectors, timeout=20):
    """Đợi bất kỳ selector nào xuất hiện, trả về element đầu tiên tìm thấy."""
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    end_time = time.time() + timeout
    while time.time() < end_time:
        for sel in selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.is_displayed():
                        return el
            except:
                pass
        time.sleep(0.5)
    return None


def set_react_input(driver, element, value):
    """Nhập giá trị vào React input siêu tốc (kích hoạt onChange) bằng JS native setter."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        element.click()
    except:
        driver.execute_script("arguments[0].focus();", element)
        
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
    driver.execute_script(js_code, element, value)


def try_click(driver, element, label=""):
    """Click element với fallback JS click."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.3)
        try:
            element.click()
        except:
            driver.execute_script("arguments[0].click();", element)
        logger.info(f"Clicked: {label}")
        return True
    except Exception as e:
        err_str = str(e).split("\n")[0] # Chỉ lấy dòng báo lỗi đầu tiên, bỏ qua stacktrace dài
        logger.debug(f"Không click được {label}: {err_str}")
        return False


def _sentinel_delay(seconds=3, label="Sentinel"):
    """Chờ Sentinel/Turnstile captcha khởi tạo xong (đã được bóp thời gian để chạy siêu tốc)."""
    # Ép thời gian chờ xuống tối đa 1.2s để chuyển bước cực nhanh
    actual_wait = min(seconds, 1.2)
    logger.info(f"[Delay] Chờ {actual_wait}s cho {label} load... (gốc: {seconds}s)")
    time.sleep(actual_wait)


def _save_screenshot(driver, label="error"):
    """Lưu screenshot khi gặp lỗi để debug."""
    try:
        os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(_SCREENSHOT_DIR, f"gpt_{label}_{ts}.png")
        driver.save_screenshot(path)
        logger.info(f"[Screenshot] Đã lưu: {path}")
    except Exception as e:
        logger.warning(f"[Screenshot] Không lưu được: {e}")


def _check_stop(stop_event):
    """Kiểm tra stop_event, raise nếu cần dừng."""
    if stop_event and stop_event.is_set():
        raise InterruptedError("Stop event triggered — dừng đăng ký")


def _fix_radix_pointer_events(driver):
    """
    Fix Radix UI pointer-events bug.
    Radix đặt body { pointer-events: none } khi mở dialog,
    cần restore lại để có thể click các element.
    """
    driver.execute_script("""
        document.body.style.pointerEvents = 'auto';
        // Restore cho tất cả ancestor elements
        let el = document.body;
        while (el) {
            el.style.pointerEvents = 'auto';
            el = el.parentElement;
        }
        // Restore cho tất cả elements có pointer-events: none
        document.querySelectorAll('*').forEach(function(e) {
            if (getComputedStyle(e).pointerEvents === 'none') {
                e.style.pointerEvents = 'auto';
            }
        });
    """)
    logger.info("[RadixFix] Đã restore pointer-events cho body và ancestors")


def _dispatch_real_click(driver, element):
    """
    Dispatch đầy đủ mouse events với tọa độ thực — bypass Radix event guards.
    """
    driver.execute_script("""
        var el = arguments[0];
        var rect = el.getBoundingClientRect();
        var cx = rect.left + rect.width / 2;
        var cy = rect.top + rect.height / 2;
        var opts = {bubbles: true, cancelable: true, clientX: cx, clientY: cy, view: window};
        el.dispatchEvent(new PointerEvent('pointerdown', opts));
        el.dispatchEvent(new MouseEvent('mousedown', opts));
        el.dispatchEvent(new PointerEvent('pointerup', opts));
        el.dispatchEvent(new MouseEvent('mouseup', opts));
        el.dispatchEvent(new MouseEvent('click', opts));
    """, element)


# ─── Init Selenium Driver ────────────────────────────────────────────────────

def init_selenium_driver(browser_type, headless, incognito, proxy, thread_id=1, batch_size=1, direct_proxy=False):
    from selenium import webdriver
    relay = None
    
    # --- Tính toán vị trí cửa sổ chia màn hình ---
    # ChatGPT UI bị lỗi layout (chuyển sang mobile view hỏng nút bấm) nếu chia 4 (width=480)
    # Nên tối đa chỉ chia 2 cột (width=960) hoặc full màn hình
    cols = 2
    SCREEN_W = 1920
    SCREEN_H = 1080
    
    # Lấy kích thước màn hình thực tế trên Windows
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            SCREEN_W = user32.GetSystemMetrics(0)
            SCREEN_H = user32.GetSystemMetrics(1)
        except:
            pass

    window_width = SCREEN_W // 2
    # Lấy 90% chiều cao màn hình để không bị lấp bởi thanh Taskbar (tương đương 90vh)
    window_height = int(SCREEN_H * 0.9)
    
    idx = (thread_id - 1) % max(1, cols)
    pos_x = idx * window_width
    pos_y = 0

    if browser_type.lower() in ["firefox", "camoufox"]:
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        ff_options = FirefoxOptions()
        if headless:
            ff_options.add_argument("--headless")
        if incognito:
            ff_options.add_argument("-private")
            
        ff_options.add_argument(f"--width={window_width}")
        ff_options.add_argument(f"--height={window_height}")
            
        camoufox_path = os.path.expanduser("~/Library/Caches/camoufox/Camoufox.app/Contents/MacOS/camoufox")
        if browser_type.lower() == "camoufox" and os.path.exists(camoufox_path):
            ff_options.binary_location = camoufox_path
            logger.info("Đang sử dụng trình duyệt Camoufox!")
            
        if proxy:
            parsed = urllib.parse.urlparse(proxy)
            if parsed.username and parsed.password:
                relay = LocalProxyRelay(parsed.hostname, parsed.port, parsed.username, parsed.password, 0).start()
                ff_options.set_preference("network.proxy.type", 1)
                ff_options.set_preference("network.proxy.http", "127.0.0.1")
                ff_options.set_preference("network.proxy.http_port", relay.local_port)
                ff_options.set_preference("network.proxy.ssl", "127.0.0.1")
                ff_options.set_preference("network.proxy.ssl_port", relay.local_port)
            else:
                ff_options.set_preference("network.proxy.type", 1)
                ff_options.set_preference("network.proxy.http", parsed.hostname)
                ff_options.set_preference("network.proxy.http_port", parsed.port)
                ff_options.set_preference("network.proxy.ssl", parsed.hostname)
                ff_options.set_preference("network.proxy.ssl_port", parsed.port)
                
        driver = webdriver.Firefox(options=ff_options)
        driver.set_window_rect(x=pos_x, y=pos_y, width=window_width, height=window_height)
    else:
        import undetected_chromedriver as uc
        chrome_options = uc.ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless=new")
        if incognito:
            chrome_options.add_argument("--incognito")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"--window-size={window_width},{window_height}")
        chrome_options.add_argument(f"--window-position={pos_x},{pos_y}")
        
        if proxy:
            parsed = urllib.parse.urlparse(proxy)
            if parsed.username and parsed.password:
                import os, tempfile, shutil, uuid
                ext_dir = os.path.join(tempfile.gettempdir(), f"proxy_ext_{uuid.uuid4().hex}")
                os.makedirs(ext_dir, exist_ok=True)
                
                manifest_json = """{
                    "version": "1.0.0",
                    "manifest_version": 2,
                    "name": "Chrome Proxy",
                    "permissions": [
                        "proxy",
                        "tabs",
                        "unlimitedStorage",
                        "storage",
                        "<all_urls>",
                        "webRequest",
                        "webRequestBlocking"
                    ],
                    "background": {
                        "scripts": ["background.js"]
                    },
                    "minimum_chrome_version":"22.0.0"
                }"""
                
                background_js = f"""
                var config = {{
                        mode: "fixed_servers",
                        rules: {{
                          singleProxy: {{
                            scheme: "http",
                            host: "{parsed.hostname}",
                            port: parseInt({parsed.port})
                          }},
                          bypassList: ["localhost"]
                        }}
                      }};
                chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
                function callbackFn(details) {{
                    return {{
                        authCredentials: {{
                            username: "{parsed.username}",
                            password: "{parsed.password}"
                        }}
                    }};
                }}
                chrome.webRequest.onAuthRequired.addListener(
                        callbackFn,
                        {{urls: ["<all_urls>"]}},
                        ['blocking']
                );
                """
                with open(os.path.join(ext_dir, "manifest.json"), "w") as f:
                    f.write(manifest_json)
                with open(os.path.join(ext_dir, "background.js"), "w") as f:
                    f.write(background_js)
                
                chrome_options.add_argument(f"--load-extension={ext_dir}")
            else:
                chrome_options.add_argument(f"--proxy-server=http://{parsed.hostname}:{parsed.port}")
                
        # Fix cho Windows: Tự động lấy version Chrome hiện tại để truyền vào uc.Chrome
        # Giúp tránh lỗi "This version of ChromeDriver only supports Chrome version X"
        # và tránh việc fallback sinh ra exception "WinError 6".
        version_main = None
        if sys.platform == "win32":
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
                version, _ = winreg.QueryValueEx(key, "version")
                version_main = int(version.split('.')[0])
            except:
                pass
                
        try:
            if version_main:
                driver = uc.Chrome(options=chrome_options, version_main=version_main)
            else:
                driver = uc.Chrome(options=chrome_options)
        except Exception as e:
            logger.warning(f"Không tự tìm được chromedriver cho UC: {e}. Thử dùng webdriver-manager...")
            from webdriver_manager.chrome import ChromeDriverManager
            # Fix: Copy options để tránh lỗi "you cannot reuse the ChromeOptions object"
            fallback_options = uc.ChromeOptions()
            for arg in chrome_options.arguments:
                fallback_options.add_argument(arg)
            if chrome_options.binary_location:
                fallback_options.binary_location = chrome_options.binary_location
            
            driver = uc.Chrome(driver_executable_path=ChromeDriverManager().install(), options=fallback_options)
    # Force window size and position for Chrome (UC often ignores options on macOS)
    if browser_type.lower() not in ["firefox", "camoufox"]:
        try:
            driver.set_window_rect(x=pos_x, y=pos_y, width=window_width, height=window_height)
        except:
            pass
            
    return driver, relay


# ─── Step Handlers ────────────────────────────────────────────────────────────

def _step_open_and_click_signup(driver, stop_event=None):
    """Bước 1: Mở chatgpt.com và click nút Sign Up."""
    logger.info("[Step1] Mở trang chủ chatgpt.com...")
    driver.get("https://chatgpt.com/")
    _sentinel_delay(3, "Trang chủ ChatGPT load")
    _check_stop(stop_event)

    # Đóng cookie consent banner nếu có
    try:
        cookie_btn = driver.find_element(
            By.XPATH,
            '//button[contains(text(), "Accept all")] | //button[contains(text(), "Reject non-essential")]'
        )
        try_click(driver, cookie_btn, "Cookie consent")
        time.sleep(1)
    except:
        pass

    logger.info("[Step1] Đợi nút Sign up...")

    # Thử nhiều selector — ChatGPT UI thay đổi thường xuyên
    signup_selectors = [
        # Selector từ tài liệu (bottom sheet mobile)
        (By.CSS_SELECTOR, '[data-mobile-auth-entry-action="signup"]'),
        (By.CSS_SELECTOR, '.wm-app-signupButton'),
        # Header button "Sign up for free" (desktop UI mới)
        (By.XPATH, '//button[contains(text(), "Sign up")]'),
        (By.XPATH, '//a[contains(text(), "Sign up")]'),
        # Fallback text-based
        (By.XPATH, '//*[contains(text(), "Sign up for free")]'),
        (By.XPATH, '//button[contains(text(), "Get started")]'),
    ]

    signup_btn = None
    for by, selector in signup_selectors:
        try:
            els = driver.find_elements(by, selector)
            for el in els:
                if el.is_displayed():
                    signup_btn = el
                    logger.info(f"[Step1] Tìm thấy nút signup bằng: {selector}")
                    break
            if signup_btn:
                break
        except:
            continue

    if not signup_btn:
        # Last resort: wait_clickable với timeout dài hơn
        try:
            signup_btn = wait_clickable(
                driver, By.XPATH,
                '//button[contains(text(), "Sign up")] | //a[contains(text(), "Sign up")] | //*[contains(text(), "Sign up for free")]',
                timeout=15
            )
        except:
            _save_screenshot(driver, "no_signup_btn")
            raise RuntimeError("Không tìm thấy nút Sign Up trên trang chatgpt.com")

    try_click(driver, signup_btn, "Sign Up")
    time.sleep(2)


def _step_enter_email(driver, email, stop_event=None):
    """Bước 2: Nhập email đăng ký và submit.
    
    Xử lý 2 trường hợp:
    - Bottom sheet trên chatgpt.com (mobile auth)
    - Redirect sang auth.openai.com/create-account (desktop header)
    """
    logger.info(f"[Step2] Điền email: {email}...")
    logger.info(f"[Step2] URL hiện tại: {driver.current_url}")

    # Đợi input email xuất hiện — thử nhiều selector
    email_input = None
    email_selectors = [
        'input[name="login_hint"]',           # Bottom sheet chatgpt.com
        '#mobile-auth-email',                  # Bottom sheet chatgpt.com (id)
        'input[name="email"]',                 # auth.openai.com/create-account
        'input[type="email"]',                 # Generic email input
    ]

    end_time = time.time() + 25
    while time.time() < end_time:
        for sel in email_selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.is_displayed():
                        email_input = el
                        logger.info(f"[Step2] Tìm thấy email input: {sel}")
                        break
            except:
                pass
            if email_input:
                break
        if email_input:
            break
        time.sleep(0.5)

    if not email_input:
        _save_screenshot(driver, "no_email_input")
        raise RuntimeError("Không tìm thấy ô nhập email")

    set_react_input(driver, email_input, email)

    # Chờ Sentinel/Turnstile khởi tạo trước khi submit
    _sentinel_delay(3, "Sentinel sau khi điền email")
    _check_stop(stop_event)

    # Submit bằng ENTER trên input
    from selenium.webdriver.common.keys import Keys
    email_input.send_keys(Keys.ENTER)

    # Fallback: click nút Continue nếu ENTER không hoạt động
    try:
        continue_btn = wait_clickable(
            driver, By.XPATH,
            '//button[@type="submit"] | //button[contains(text(), "Continue")]',
            timeout=3
        )
        try_click(driver, continue_btn, "Continue with email (fallback)")
    except:
        pass

    time.sleep(2)


def _step_handle_login_redirect(driver, stop_event=None):
    """
    Xử lý trường hợp bị redirect sang /log-in thay vì /create-account.
    Nếu phát hiện, tìm link Sign Up và click lại.
    """
    current_url = driver.current_url
    if "/log-in" in current_url:
        logger.warning("[Redirect] Bị redirect sang /log-in, đang tìm link Sign Up...")
        _sentinel_delay(2.5, "Trang login load")
        _check_stop(stop_event)
        try:
            # Tìm link sign-up trên trang login
            signup_link = wait_clickable(
                driver, By.XPATH,
                '//a[contains(@href, "/create-account")] | //a[contains(@href, "signup")] | //button[contains(text(), "Sign up")]',
                timeout=10
            )
            try_click(driver, signup_link, "Sign Up link from login page")
            time.sleep(2)
        except:
            logger.info("[Redirect] Không tìm thấy link Sign Up, thử redirect trực tiếp...")
            driver.get("https://auth.openai.com/create-account")
            _sentinel_delay(3, "Create account page load")


def _step_continue_with_password(driver, stop_event=None):
    """Bước 3: Click 'Continue with password' nếu có."""
    logger.info("[Step3] Chờ link 'Continue with password'...")
    _sentinel_delay(2.5, "Sentinel trước khi click password link")
    _check_stop(stop_event)
    try:
        pw_btn = wait_clickable(
            driver, By.XPATH,
            '//a[@href="/create-account/password"] | //button[contains(., "Continue with password")]',
            timeout=15
        )
        try_click(driver, pw_btn, "Continue with password")
        time.sleep(1)
    except:
        logger.info("[Step3] Không thấy link password, có thể đã redirect trực tiếp")


def _step_enter_password(driver, password, stop_event=None):
    """Bước 4: Nhập mật khẩu và submit."""
    logger.info("[Step4] Đang điền mật khẩu...")
    _sentinel_delay(3, "Sentinel trước khi điền password")
    _check_stop(stop_event)

    pw_input = wait_for_element(
        driver, By.CSS_SELECTOR,
        'input[name="password"], input[name="new-password"], input[type="password"]',
        timeout=20
    )
    set_react_input(driver, pw_input, password)

    _sentinel_delay(2.5, "Sentinel trước khi submit password")

    submit_pw = wait_clickable(driver, By.CSS_SELECTOR, 'button[type="submit"]', timeout=10)
    try_click(driver, submit_pw, "Submit Password")
    time.sleep(2)


def _step_enter_otp(driver, email, get_otp_callback, stop_event=None):
    """
    Bước 5: Nhập OTP từ email với retry logic.
    - Chờ 6s cho email đến
    - Retry tối đa 5 lần, mỗi lần cách 8s
    - Lần thứ 3: click nút Resend và đợi thêm 10s
    """
    logger.info("[Step5] Chờ trang nhập mã OTP...")
    code_input = wait_for_element(
        driver, By.CSS_SELECTOR,
        'input[name="code"], input[autocomplete="one-time-code"]',
        timeout=30
    )

    # Chờ email đến hộp thư (6s theo tài liệu)
    _sentinel_delay(6, "Chờ email OTP đến hộp thư")
    _check_stop(stop_event)

    if not get_otp_callback:
        raise RuntimeError("Không có hàm callback OTP!")

    otp_code = None
    max_retries = 5

    for attempt in range(1, max_retries + 1):
        _check_stop(stop_event)
        logger.info(f"[Step5] Lấy OTP lần {attempt}/{max_retries}...")

        otp_code = get_otp_callback(email)
        if otp_code:
            break

        # Lần thứ 3: click Resend
        if attempt == 3:
            logger.info("[Step5] Lần 3 — click Resend OTP...")
            try:
                resend_btn = driver.find_element(
                    By.XPATH,
                    '//button[contains(text(), "Resend")] | //a[contains(text(), "Resend")]'
                )
                try_click(driver, resend_btn, "Resend OTP")
                time.sleep(10)  # Chờ email mới
            except:
                logger.warning("[Step5] Không tìm thấy nút Resend")

        if attempt < max_retries:
            time.sleep(8)

    if not otp_code:
        raise RuntimeError(f"Không lấy được mã OTP cho {email} sau {max_retries} lần thử")

    logger.info(f"[Step5] Lấy được OTP: {otp_code}. Đang điền mã...")
    set_react_input(driver, code_input, otp_code)

    # Chờ 2s rồi click Validate (tránh click nút Resend nhầm)
    time.sleep(2)
    try:
        val_btn = wait_clickable(
            driver, By.CSS_SELECTOR,
            'button[value="validate"][name="intent"], button[value="validate"]',
            timeout=5
        )
        try_click(driver, val_btn, "Validate OTP")
    except:
        pass

    time.sleep(2)


def _step_about_you(driver, stop_event=None):
    """Bước 6: Điền thông tin cá nhân (random Vietnamese profile)."""
    logger.info("[Step6] Chờ trang about-you...")
    _check_stop(stop_event)

    name_input = wait_for_element(
        driver, By.CSS_SELECTOR, 'input[name="name"]', timeout=30
    )

    full_name, age = _generate_vietnamese_profile()
    logger.info(f"[Step6] Điền profile: {full_name}, tuổi: {age}")
    set_react_input(driver, name_input, full_name)

    try:
        age_input = wait_for_element(
            driver, By.CSS_SELECTOR, 'input[name="age"]', timeout=5
        )
        set_react_input(driver, age_input, str(age))
    except:
        logger.info("[Step6] Không tìm thấy input tuổi, bỏ qua")

    _sentinel_delay(2, "Sentinel trước khi submit about-you")

    about_submit = wait_clickable(
        driver, By.CSS_SELECTOR,
        'button[type="submit"][data-dd-action-name="Continue"], button[type="submit"]',
        timeout=10
    )
    try_click(driver, about_submit, "Submit About You")
    time.sleep(2)


def _step_skip_onboarding(driver, stop_event=None):
    """
    Bước 7: Skip onboarding — xử lý nhiều case.
    Có chờ để đảm bảo screen xuất hiện (SPA load chậm).
    """
    logger.info("[Step7] Xử lý onboarding screens...")
    _check_stop(stop_event)

    # Chờ tối đa 10s cho screen xuất hiện
    screen_appeared = False
    for _ in range(5):
        time.sleep(2)
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            if "what brings you" in body_text or "all set" in body_text or "can make mistakes" in body_text:
                screen_appeared = True
                break
        except:
            pass

    if not screen_appeared:
        logger.info("[Step7] Không thấy onboarding screen sau 10s")
        return

    max_screens = 5
    for screen in range(max_screens):
        time.sleep(1)
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        except:
            break

        # Case 1: "What brings you to ChatGPT?"
        if "what brings you" in body_text:
            logger.info("[Step7] Phát hiện 'What brings you' screen")
            try:
                skip_btn = driver.find_element(
                    By.XPATH,
                    '//button[contains(text(), "Skip")] | //a[contains(text(), "Skip")]'
                )
                try_click(driver, skip_btn, "Skip What Brings You")
                time.sleep(1.5)
                continue
            except:
                try:
                    options = driver.find_elements(By.CSS_SELECTOR, 'button[role="option"], [role="radio"], label')
                    if options:
                        try_click(driver, options[0], "Select first option")
                        time.sleep(0.5)
                    next_btn = driver.find_element(
                        By.XPATH,
                        '//button[contains(text(), "Next")] | //button[contains(text(), "Continue")]'
                    )
                    try_click(driver, next_btn, "Next after selection")
                    time.sleep(1.5)
                    continue
                except:
                    pass

        # Case 2: "You're all set" / "ChatGPT can make mistakes"
        if "all set" in body_text or "can make mistakes" in body_text:
            logger.info("[Step7] Phát hiện 'You're all set' / final screen")
            try:
                cont_btn = wait_clickable(
                    driver, By.XPATH,
                    '//div[text()="Continue"]/parent::button | //button[contains(text(), "Continue")]',
                    timeout=5
                )
                try_click(driver, cont_btn, "Welcome Continue")
                time.sleep(1.5)
                continue
            except:
                pass

        # Case 3: Bất kỳ nút Continue / Okay / Got it nào
        try:
            generic_btn = driver.find_element(
                By.XPATH,
                '//button[contains(text(), "Continue")] | //button[contains(text(), "Okay")] | //button[contains(text(), "Got it")]'
            )
            try_click(driver, generic_btn, "Generic onboarding button")
            time.sleep(1.5)
            continue
        except:
            pass

        # Thoát nếu không tìm thấy nút nào để bấm
        break

    time.sleep(1)


def _step_setup_2fa(driver, stop_event=None):
    """
    Bước 8-12: Setup 2FA (Authenticator App).
    Returns: totp_secret string hoặc raise exception
    """
    # === Navigate to Settings ===
    logger.info("[Step8] Đang truy cập Settings...")
    driver.get("https://chatgpt.com/#settings")
    time.sleep(1)
    
    # === Xử lý Modal "You're all set" nếu nó hiện trễ ở màn hình Settings ===
    try:
        late_modal = driver.find_element(By.XPATH, '//div[@role="dialog"]//button[contains(text(), "Continue") or contains(text(), "Tiếp tục")] | //button[text()="Continue"] | //button[text()="Tiếp tục"]')
        if late_modal.is_displayed():
            logger.info("[Step8.5] Đóng modal 'You're all set' hiện trễ...")
            _fix_radix_pointer_events(driver)
            try_click(driver, late_modal, "Late Continue")
            time.sleep(2)
    except:
        pass

    _check_stop(stop_event)

    # === Click Security tab ===
    logger.info("[Step9] Chọn tab Security...")
    try:
        sec_tab = wait_clickable(
            driver, By.CSS_SELECTOR,
            'button[data-testid="security-tab"]',
            timeout=20
        )
        try_click(driver, sec_tab, "Security Tab")
    except:
        # Fallback: tìm tab bằng text
        logger.info("[Step9] Fallback: tìm tab Security bằng text...")
        try:
            sec_tab = driver.find_element(
                By.XPATH,
                '//button[contains(text(), "Security")] | //button[contains(text(), "Bảo mật")]'
            )
            try_click(driver, sec_tab, "Security Tab (text fallback)")
        except:
            raise RuntimeError("Không tìm thấy tab Security")

    time.sleep(2)
    
    # Kểm tra lại modal "You're all set" vì nó có thể hiện sau khi click tab Security
    try:
        late_modal_2 = driver.find_element(By.XPATH, '//div[@role="dialog"]//button[contains(text(), "Continue") or contains(text(), "Tiếp tục")] | //button[text()="Continue"] | //button[text()="Tiếp tục"]')
        if late_modal_2.is_displayed():
            logger.info("[Step9.5] Đóng modal 'You're all set' hiện trễ sau khi chọn Security...")
            _fix_radix_pointer_events(driver)
            try_click(driver, late_modal_2, "Late Continue 2")
            time.sleep(2)
    except:
        pass

    _check_stop(stop_event)

    # === Fix Radix pointer-events trước khi click MFA toggle ===
    _fix_radix_pointer_events(driver)

    # === Bật MFA Authenticator toggle ===
    logger.info("[Step10] Bật Authenticator app toggle...")
    try:
        mfa_toggle = wait_clickable(
            driver, By.CSS_SELECTOR,
            'button[data-testid="mfa-authenticator-toggle"]',
            timeout=15
        )
        _fix_radix_pointer_events(driver)
        _dispatch_real_click(driver, mfa_toggle)
        time.sleep(1)

        # Kiểm tra toggle đã bật chưa
        toggle_state = mfa_toggle.get_attribute("data-state") or mfa_toggle.get_attribute("aria-checked")
        if toggle_state not in ("checked", "true"):
            logger.warning("[Step10] Toggle chưa bật, thử click lại...")
            _fix_radix_pointer_events(driver)
            try_click(driver, mfa_toggle, "MFA Toggle retry")
            time.sleep(1)
    except:
        # Fallback: tìm toggle bằng role switch
        logger.info("[Step10] Fallback: tìm MFA toggle bằng role switch...")
        toggles = driver.find_elements(By.CSS_SELECTOR, '[role="switch"][aria-checked="false"]')
        for t in toggles:
            if t.is_displayed():
                _fix_radix_pointer_events(driver)
                _dispatch_real_click(driver, t)
                time.sleep(1)
                break
        else:
            # Tìm button Enable/Bật trong row có text authenticator/2fa
            logger.info("[Step10] Fallback: tìm nút Enable 2FA...")
            enable_btn = driver.find_element(
                By.XPATH,
                '//button[contains(text(), "Enable")] | //button[contains(text(), "Bật")] | //button[contains(text(), "Set up")] | //button[contains(., "Multi-factor authentication")]//following-sibling::button'
            )
            _fix_radix_pointer_events(driver)
            try_click(driver, enable_btn, "Enable 2FA button")
            time.sleep(1)

    time.sleep(2)
    
    # === Xử lý UI trung gian "Tiếp tục / Continue" nếu có ===
    logger.info("[Step10.5] Kiểm tra UI trung gian 'Continue'...")
    try:
        intermediate_cont = driver.find_element(
            By.XPATH,
            '//button[text()="Continue"] | //button[text()="Tiếp tục"] | //div[@role="dialog"]//button[contains(text(), "Continue")]'
        )
        if intermediate_cont.is_displayed():
            logger.info("[Step10.5] Phát hiện nút Continue trung gian, đang click...")
            _fix_radix_pointer_events(driver)
            try_click(driver, intermediate_cont, "MFA Intermediate Continue")
            time.sleep(2)
    except:
        pass

    _check_stop(stop_event)

    # === Click "Trouble scanning?" ===
    logger.info("[Step11] Click 'Trouble scanning?' để hiện Secret key text...")
    try:
        trouble_btn = wait_clickable(
            driver, By.XPATH,
            '//button[contains(text(), "Trouble scanning?")] | //button[contains(text(), "Can\'t scan")] | //button[contains(@class, "interactive-label-accent")]',
            timeout=15
        )
        try_click(driver, trouble_btn, "Trouble Scanning")
    except:
        # Fallback XPath
        try:
            trouble_btn = driver.find_element(
                By.XPATH,
                '//button[contains(text(), "setup key")] | //a[contains(text(), "Trouble")] | //a[contains(text(), "Can\'t scan")]'
            )
            try_click(driver, trouble_btn, "Trouble Scanning (fallback)")
        except:
            logger.warning("[Step11] Không tìm thấy nút Trouble scanning, có thể đã hiện secret")

    time.sleep(2)

    # === Extract TOTP Secret ===
    logger.info("[Step12] Đang trích xuất Secret key...")
    totp_secret = _extract_totp_secret(driver)

    if not totp_secret:
        raise RuntimeError("Không trích xuất được TOTP Secret từ trang")

    logger.info(f"[Step12] Lấy được TOTP Secret: {totp_secret}")

    # === Generate và điền TOTP code ===
    totp = pyotp.TOTP(totp_secret)
    code = totp.now()
    logger.info(f"[Step12] Mã TOTP đã sinh: {code}")

    totp_input = wait_for_element(
        driver, By.CSS_SELECTOR,
        'input[name="totp_otp"], #totp_otp, input[placeholder*="6-digit"], input[autocomplete="one-time-code"]',
        timeout=10
    )
    set_react_input(driver, totp_input, code)
    time.sleep(0.4)

    # === Click Verify với retry ===
    _click_verify_with_retry(driver)

    time.sleep(1)
    return totp_secret


def _extract_totp_secret(driver):
    """
    Trích xuất TOTP Secret từ trang bằng 3 phương pháp fallback:
    1. Selector ưu tiên: div[aria-label="Copy code"], div[title="Copy code"]
    2. Tìm trong modal/dialog
    3. Fallback: scan toàn bộ body text tìm pattern Base32
    """
    # Phương pháp 1: Selector trực tiếp
    priority_selectors = [
        'div[aria-label="Copy code"][title="Copy code"]',
        'div[aria-label="Copy code"][role="button"]',
        'div[title="Copy code"][role="button"]',
        'div[title="Copy code"]',
        'div[aria-label="Copy code"]',
        '.font-mono.select-text',
    ]
    for sel in priority_selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            text = el.text.strip()
            if _is_valid_totp_secret(text):
                return text
        except:
            continue

    # Phương pháp 2: Tìm trong modal/dialog
    dialog_selectors = [
        '[aria-labelledby="enroll-totp-modal-title"]',
        '[role="dialog"][data-state="open"]',
        'div[role="dialog"]',
    ]
    for ds in dialog_selectors:
        try:
            dialog = driver.find_element(By.CSS_SELECTOR, ds)
            inner_selectors = ['[role="button"]', 'code', 'pre', 'div[title]', 'div[aria-label]']
            for iss in inner_selectors:
                try:
                    els = dialog.find_elements(By.CSS_SELECTOR, iss)
                    for el in els:
                        text = el.text.strip()
                        if _is_valid_totp_secret(text):
                            return text
                except:
                    continue
        except:
            continue

    # Phương pháp 3: Scan toàn bộ body text
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        matches = re.findall(r'[A-Z2-7]{16,}', body_text)
        for m in matches:
            if _is_valid_totp_secret(m):
                return m
    except:
        pass

    return None


def _is_valid_totp_secret(text):
    """Validate chuỗi có phải Base32 TOTP Secret hợp lệ không."""
    if not text:
        return False
    # Clean up: bỏ space, uppercase
    cleaned = text.replace(" ", "").upper()
    # Phải >= 16 ký tự và chỉ chứa A-Z2-7
    return bool(re.match(r'^[A-Z2-7]{16,}$', cleaned))


def _click_verify_with_retry(driver, max_attempts=3):
    """Click nút Verify với retry 3 lần (delay 600ms, 1500ms giữa các lần)."""
    delays = [0, 0.6, 1.5]

    for attempt in range(max_attempts):
        if attempt > 0:
            time.sleep(delays[attempt])

        try:
            # Tìm nút Verify
            buttons = driver.find_elements(By.TAG_NAME, "button")
            verify_btn = None

            for btn in buttons:
                try:
                    if not btn.is_displayed():
                        continue
                    btn_text = btn.text.strip().lower()
                    if btn_text in ("verify", "xác minh"):
                        if not btn.get_attribute("disabled"):
                            verify_btn = btn
                            break
                except:
                    continue

            if not verify_btn:
                # Fallback: CSS selector
                try:
                    verify_btn = driver.find_element(
                        By.XPATH,
                        '//div[text()="Verify"]/parent::button[not(@disabled)] | //button[contains(text(), "Verify")][not(@disabled)]'
                    )
                except:
                    pass

            if not verify_btn:
                # Fallback: primary button trong dialog
                try:
                    verify_btn = driver.find_element(
                        By.CSS_SELECTOR, 'button.btn-primary:not([disabled])'
                    )
                except:
                    pass

            if verify_btn:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", verify_btn)
                time.sleep(0.2)
                try:
                    verify_btn.click()
                except:
                    _dispatch_real_click(driver, verify_btn)
                logger.info(f"[Verify] Clicked Verify (attempt {attempt + 1})")
                return True
            else:
                logger.warning(f"[Verify] Không tìm thấy nút Verify (attempt {attempt + 1})")

        except Exception as e:
            logger.warning(f"[Verify] Lỗi click Verify (attempt {attempt + 1}): {e}")

    logger.error("[Verify] Không click được nút Verify sau 3 lần thử")
    return False


# ─── Main Registration Flow ──────────────────────────────────────────────────

def _step_check_promo(driver, stop_event=None, proxy=None):
    """
    Sử dụng API fetch từ trình duyệt để check trực tiếp gói Ưu Đãi 0đ và MoMo cực nhanh.
    Returns: (has_uudai: str, has_momo: str) - "có" hoặc "không"
    """
    has_uudai = "không"
    has_momo = "không"

    logger.info("[Promo] Kiểm tra ưu đãi Plus 1 Month Free và MoMo qua API...")
    try:
        time.sleep(1.5) # Chờ 2FA lưu xong
        
        # 1. Lấy access token bằng JS
        js_get_token = """
        var cb = arguments[0];
        fetch('/api/auth/session')
            .then(res => res.json())
            .then(data => cb({token: data.accessToken}))
            .catch(err => cb({error: err.toString()}));
        """
        driver.set_script_timeout(15)
        res = driver.execute_async_script(js_get_token)
        if "error" in res or not res.get("token"):
            logger.warning(f"[Promo] Không lấy được access_token: {res.get('error')}")
            return has_uudai, has_momo
            
        access_token = res["token"]
        
        # 2. Tạo Session Mock sử dụng proxy & cookie của driver và dùng curl_cffi để gọi API
        class SessionMock:
            def __init__(self, drv, proxy_url=None):
                self.drv = drv
                self.proxy_url = proxy_url

            def _make_cffi_session(self):
                from curl_cffi import requests
                req_session = requests.Session(impersonate="chrome120")
                if self.proxy_url:
                    req_session.proxies = {"http": self.proxy_url, "https": self.proxy_url}
                for cookie in self.drv.get_cookies():
                    req_session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
                return req_session

            def post(self, url, json=None, data=None, headers=None, timeout=None):
                req_session = self._make_cffi_session()
                try:
                    res = req_session.post(url, json=json, data=data, headers=headers, timeout=timeout)
                    return res
                except Exception as e:
                    logger.warning(f"[SessionMock] curl_cffi POST failed for {url}: {e}")
                    raise

            def get(self, url, headers=None, timeout=None):
                req_session = self._make_cffi_session()
                try:
                    res = req_session.get(url, headers=headers, timeout=timeout)
                    return res
                except Exception as e:
                    logger.warning(f"[SessionMock] curl_cffi GET failed for {url}: {e}")
                    raise

        class MockBrowserSession:
            def __init__(self, drv, proxy_url=None):
                self.session = SessionMock(drv, proxy_url)
                try:
                    self.device_id = drv.execute_script("return window.localStorage.getItem('oai-device-id')")
                except:
                    self.device_id = None
                if not self.device_id:
                    import uuid
                    self.device_id = str(uuid.uuid4())
                
                try:
                    ua = drv.execute_script("return navigator.userAgent")
                    platform = drv.execute_script("return navigator.platform")
                except:
                    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    platform = "Win32"
                self.browser_profile = {
                    "user_agent": ua,
                    "platform": platform,
                    "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    "mobile": "?0"
                }

        mock_session = MockBrowserSession(driver, proxy)
        
        # 3. Gọi momo_checker
        try:
            from src.bots.momo_checker import check_momo_payment
        except ImportError:
            try:
                from bots.momo_checker import check_momo_payment
            except ImportError:
                from momo_checker import check_momo_payment
            
        has_trial, payment_methods_str, amount_due, currency = check_momo_payment(mock_session, access_token)
        
        # Format Ưu đãi string
        if has_trial:
            has_uudai = "Có trial - 0 đ"
            logger.info("[Promo] Đã thấy ưu đãi Plus 1 Month (Giá: 0đ)!")
        else:
            if amount_due is not None:
                formatted_amount = f"{int(amount_due):,}".replace(",", ".")
                has_uudai = f"Không trial - {formatted_amount} đ"
            else:
                has_uudai = "Không trial"
            logger.info(f"[Promo] Không có ưu đãi 0đ (Trial: {has_trial}, Amount: {amount_due}).")
            
        # Lưu toàn bộ chuỗi payment_methods vào cột momo để hiển thị dạng Badge trên UI
        if payment_methods_str and payment_methods_str not in ["không", "lỗi"]:
            has_momo = payment_methods_str  # VD: "apple_pay, card, google_pay, momo"
            if "momo" in payment_methods_str.lower():
                logger.info(f"[Promo] Phát hiện MoMo trên trang thanh toán! ({payment_methods_str})")
            else:
                logger.info(f"[Promo] Không có MoMo. (Các cổng hiện có: {payment_methods_str})")
        else:
            has_momo = payment_methods_str or "không"
            
    except Exception as e:
        logger.warning(f"[Promo] Lỗi check promo API: {e}")

    return has_uudai, has_momo

ACTIVE_DRIVERS = []

def run_selenium_registration_standalone(
    email: str,
    password: str,
    proxy: str = None,
    headless: bool = False,
    browser_type: str = "chrome",
    incognito: bool = False,
    keep_open: bool = False,
    direct_proxy: bool = False,
    get_otp_callback=None,
    save_account_callback=None,
    stop_event=None,
    otp_received_event=None,
    thread_id: int = 1,
    batch_size: int = 1
) -> dict:
    """
    Run the UI-driven Selenium registration flow completely decoupled from gpt_engine.
    
    Args:
        email: Email để đăng ký
        password: Mật khẩu ChatGPT
        proxy: Proxy URL (http://user:pass@host:port)
        headless: Chạy headless mode
        browser_type: "chrome", "firefox", "camoufox"
        incognito: Chạy incognito/private mode
        get_otp_callback: Callback function nhận email, trả về OTP string
        save_account_callback: Callback function(email, password, totp_secret, has_momo)
        stop_event: threading.Event để dừng giữa chừng
        
    Returns: {"success": bool, "error": str, "totp_secret": str}
    """
    driver = None
    relay = None

    try:
        logger.info(
            f"[SeleniumUI] Khởi chạy trình duyệt cho {email}... "
            f"(Browser: {browser_type}, Headless: {headless}, Incognito: {incognito})"
        )
        driver, relay = init_selenium_driver(browser_type, headless, incognito, proxy, thread_id, batch_size, direct_proxy)
        ACTIVE_DRIVERS.append(driver)

        # ═══════════════════════════════════════════════════════════════
        # PHẦN 1: ĐĂNG KÝ TÀI KHOẢN (SIGN-UP FLOW)
        # ═══════════════════════════════════════════════════════════════

        # Bước 1: Mở chatgpt.com → Click Sign Up
        _step_open_and_click_signup(driver, stop_event)

        # Bước 2: Nhập email
        _step_enter_email(driver, email, stop_event)

        # Xử lý redirect /log-in
        _step_handle_login_redirect(driver, stop_event)

        # Bước 3: Click "Continue with password"
        _step_continue_with_password(driver, stop_event)

        # Bước 4: Nhập password
        _step_enter_password(driver, password, stop_event)

        # Bước 5: Nhập OTP (với retry + resend)
        _step_enter_otp(driver, email, get_otp_callback, stop_event)
        if otp_received_event:
            otp_received_event.set()

        # Bước 6: Điền About You (random Vietnamese profile)
        _step_about_you(driver, stop_event)

        # ═══════════════════════════════════════════════════════════════
        # PHẦN 1.5: SKIP ONBOARDING
        # ═══════════════════════════════════════════════════════════════

        # Bước 7: Skip onboarding screens
        _step_skip_onboarding(driver, stop_event)

        # ═══════════════════════════════════════════════════════════════
        # PHẦN 2: BẬT 2FA (AUTHENTICATOR APP)
        # ═══════════════════════════════════════════════════════════════

        logger.info("[SeleniumUI] Hoàn tất đăng ký, tiến hành cài đặt 2FA...")

        # Bước 8-12: Setup 2FA
        totp_secret = _step_setup_2fa(driver, stop_event)

        # ═══════════════════════════════════════════════════════════════
        # HOÀN TẤT
        # ═══════════════════════════════════════════════════════════════

        # ═══════════════════════════════════════════════════════════════
        # PHẦN 3: KIỂM TRA ƯU ĐÃI (PROMO) & MOMO
        # ═══════════════════════════════════════════════════════════════
        has_uudai, has_momo_str = _step_check_promo(driver, stop_event, proxy)

        if save_account_callback:
            # Truyền thêm tham số uudai nếu hàm hỗ trợ
            import inspect
            sig = inspect.signature(save_account_callback)
            if len(sig.parameters) >= 5:
                save_account_callback(email, password, totp_secret, has_momo_str, has_uudai)
            else:
                save_account_callback(email, password, totp_secret, has_momo_str)
        else:
            try:
                with get_db() as conn:
                    try:
                        conn.execute("ALTER TABLE accounts ADD COLUMN uudai TEXT")
                    except:
                        pass
                    conn.execute(
                        "INSERT INTO accounts (app, uid, email, password, twofa, momo, uudai) VALUES (?, '', ?, ?, ?, ?, ?)",
                        ("gpt", email, password, totp_secret, has_momo_str, has_uudai)
                    )
                    conn.commit()
            except Exception as e:
                logger.error(f"[SeleniumUI] Lỗi lưu DB: {e}")

        logger.info(f"[SeleniumUI] ✨ Tạo tài khoản thành công! Đã lưu: {email} | Ưu đãi: {has_uudai} | MoMo: {has_momo_str}")

        # Xoay proxy sau khi check xong
        try:
            import requests
            requests.post("http://127.0.0.1:5050/api/proxy/rotate", timeout=5)
            logger.info("[Proxy] Đã xoay proxy sau khi hoàn tất account.")
        except Exception as e:
            logger.warning(f"[Proxy] Lỗi gọi API xoay proxy: {e}")

        # Nếu có MoMo thì LUÔN giữ lại tab. 
        # Nếu không có MoMo thì tôn trọng nút "Tạo xong để đó" trên giao diện.
        if has_momo_str == "có":
            keep_open = True
            logger.info("[SeleniumUI] Có MoMo -> BẮT BUỘC giữ lại tab này!")
        else:
            logger.info(f"[SeleniumUI] Không có MoMo -> Giữ/đóng tab theo cài đặt giao diện (Keep Open: {keep_open}).")

        return {"success": True, "totp_secret": totp_secret, "error": None, "momo": has_momo_str, "uudai": has_uudai}

    except InterruptedError as e:
        if otp_received_event:
            otp_received_event.set()
        logger.warning(f"[SeleniumUI] Bị dừng: {e}")
        if driver:
            _save_screenshot(driver, "stopped")
        return {"success": False, "error": str(e), "totp_secret": ""}

    except Exception as e:
        if otp_received_event:
            otp_received_event.set()
        logger.error(f"[SeleniumUI] Lỗi trong quá trình đăng ký UI: {e}", exc_info=True)
        if driver:
            _save_screenshot(driver, "error")
        return {"success": False, "error": str(e), "totp_secret": ""}

    finally:
        if driver and not keep_open:
            try:
                if driver in ACTIVE_DRIVERS: ACTIVE_DRIVERS.remove(driver)
                driver.quit()
                if relay: relay.stop()
            except:
                pass
