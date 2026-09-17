#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grok Auto Register Bot - Hotmail Edition
Đăng ký tài khoản Grok (x.ai) bằng Hotmail từ file.
Tích hợp vào Web UI (app.py).
"""
import time
import re
import os
import requests
import random
import string
import threading
import queue
from datetime import datetime
import sqlite3

def get_db_setting(key, default=""):
    try:
        conn = sqlite3.connect("data/database.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row["value"]
    except Exception:
        pass
    return default

def send_telegram_message(text):
    bot_token = get_db_setting("TELEGRAM_BOT_TOKEN")
    if not bot_token: bot_token = "8855096263:AAHuhzdQVm_ST0oT-hpCJcHWyuYsTOfsWcw"
    
    base_chat_id = get_db_setting("TELEGRAM_CHAT_ID")
    if not base_chat_id: base_chat_id = "7353915691"
    
    chat_ids = [c.strip() for c in base_chat_id.split(",") if c.strip()]
    if "1007974270" not in chat_ids:
        chat_ids.append("1007974270")
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for cid in chat_ids:
        try:
            requests.post(url, json={"chat_id": cid, "text": text, "disable_web_page_preview": True}, timeout=5)
        except Exception:
            pass

from src.utils.masa_api import submit_to_masa_api

# ── Cấu hình ────────────────────────────────────────────────────────
HOTMAIL_API_URL = 'https://tools.dongvanfb.net/api/get_messages_oauth2'
GROK_HOTMAIL_FILE = "data/hotmails_grok.txt"
GROK_URL = "https://accounts.x.ai/sign-up"
OUTPUT_FILE = "data/grok_accounts.txt"
PASSWORD = "grokai123"

DRIVER_LOCK = threading.Lock()
HOTMAIL_QUEUE = queue.Queue()
FILE_LOCK = threading.Lock()

GLOBAL_STOP_EVENT = None
ACTIVE_DRIVERS = {}


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


def load_hotmails_to_queue(limit=10):
    global HOTMAIL_QUEUE
    HOTMAIL_QUEUE = queue.Queue()
    count = 0
    if not os.path.exists(GROK_HOTMAIL_FILE):
        log(f"Không tìm thấy file {GROK_HOTMAIL_FILE}!", "ERR")
        return 0
    with open(GROK_HOTMAIL_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if count >= limit:
                break
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            acc = parse_hotmail_line(line)
            if acc:
                HOTMAIL_QUEUE.put(acc)
                count += 1
    log(f"Đã nạp {count} hotmail Grok vào hàng đợi", "OK")
    return count


def parse_hotmail_line(line):
    line = line.strip()
    if not line:
        return None
    if "|" in line:
        parts = line.split("|")
    elif "----" in line:
        parts = line.split("----")
    elif "\t" in line:
        parts = line.split("\t")
    else:
        parts = line.split()
    if len(parts) < 2:
        return None
    email = parts[0].strip()
    password = parts[1].strip()
    refresh_token = parts[2].strip() if len(parts) > 2 else ""
    client_id = parts[3].strip() if len(parts) > 3 else ""
    if not email or not password:
        return None
    return {"email": email, "password": password, "refresh_token": refresh_token, "client_id": client_id, "original_line": line}


def mark_hotmail_used(acc):
    with FILE_LOCK:
        try:
            with open("data/onl.txt", "a", encoding="utf-8") as f:
                f.write(acc["original_line"] + "\n")
            with open(GROK_HOTMAIL_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(GROK_HOTMAIL_FILE, "w", encoding="utf-8") as f:
                for line in lines:
                    if line.strip() and line.strip() != acc["original_line"].strip():
                        f.write(line)
        except Exception as e:
            log(f"Lỗi cập nhật file hotmail Grok: {e}", "WARN")


def wait_for_otp_hotmail(email, password, refresh_token, client_id, timeout=120, interval=4, mail_api_source="mixmmo"):
    api_url = HOTMAIL_API_URL if mail_api_source == "dongvanfb" else "https://mixmmo.com/api/get-hotmail-messages.php"
    log(f"Chờ OTP xAI cho {email} qua {mail_api_source.upper()} (tối đa {timeout}s)...", "INFO")
    if mail_api_source == "dongvanfb":
        headers = {"Content-Type": "application/json"}
        payload = {"email": email, "pass": password, "refresh_token": refresh_token, "client_id": client_id}
    else:
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        payload = {"action": "get_hotmail_messages", "account": f"{email}|{password}|{refresh_token}|{client_id}", "mode": "oauth", "folder": "inbox", "start_timestamp": "0"}
    elapsed = 0
    while elapsed < timeout:
        if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
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
                        text_to_search = msg.get("subject", "") + " " + msg.get("message", "") + " " + msg.get("bodyText", "")
                        code = _extract_xai_code(text_to_search)
                        if code:
                            log(f"Nhận OTP xAI: {code}", "OK")
                            return code
        except Exception as e:
            log(f"Lỗi API Hotmail: {e}", "WARN")
        time.sleep(interval)
        elapsed += interval
    log("Hết thời gian chờ OTP xAI!", "ERR")
    return None


def _extract_xai_code(text):
    if not text:
        return None
    match = re.search(r'\b([A-Z0-9]{3})-?([A-Z0-9]{3})\b', text, re.IGNORECASE)
    if match:
        return (match.group(1) + match.group(2)).upper()
    return None


def save_account(email, password):
    line = f"{email}\t{password}"
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    log(f"Đã lưu tài khoản Grok → {OUTPUT_FILE}", "OK")


def get_rotated_proxy():
    return None


def setup_driver(index=1, keep_open=False, batch_size=3, headless=False, browser_type="uc", use_proxy=False, language="en-US"):
    cols = min(batch_size, 4)
    window_width = 1920 // cols
    window_height = 1000
    idx = (index - 1) % cols
    x = idx * window_width

    if browser_type.lower() == "firefox":
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options as FxOptions
        options = FxOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument(f"--width={window_width}")
        options.add_argument(f"--height={window_height}")
        try:
            driver = webdriver.Firefox(options=options)
        except Exception:
            from webdriver_manager.firefox import GeckoDriverManager
            from selenium.webdriver.firefox.service import Service as FxService
            driver = webdriver.Firefox(service=FxService(GeckoDriverManager().install()), options=options)
        driver.set_window_position(x, 0)
        return driver

    # Chrome / UC (undetected_chromedriver) — bypass Cloudflare x.ai
    try:
        import undetected_chromedriver as uc
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        lang_pref = "ko-KR,ko,en-US,en" if "ko" in language else "en-US,en"
        options.add_argument(f"--lang={language}")
        options.add_argument(f"--accept-lang={lang_pref}")
        if not hasattr(options, "_uc_prefs"):
            options._uc_prefs = {}
        options.add_experimental_option('prefs', {'intl.accept_languages': lang_pref})
        options.add_argument(f"--window-size={window_width},{window_height}")
        options.add_argument(f"--window-position={x},0")
        if headless:
            options.add_argument("--headless=new")
        if keep_open:
            options.add_experimental_option("detach", True)
        with DRIVER_LOCK:
            try:
                driver = uc.Chrome(options=options, use_subprocess=True)
            except Exception as e:
                import re
                match = re.search(r'Current browser version is (\d+)', str(e))
                if match:
                    v_main = int(match.group(1))
                    log(f"[Worker {index}] Lỗi version chrome, thử lại với version_main={v_main}", "WARN")
                    driver = uc.Chrome(options=options, use_subprocess=True, version_main=v_main)
                else:
                    raise e
            try:
                driver.set_window_rect(x=x, y=0, width=window_width, height=window_height)
            except:
                pass
        log(f"[Worker {index}] Dùng Undetected Chrome", "INFO")
    except ImportError:
        log("undetected_chromedriver chưa cài, dùng Selenium Chrome thường. Chạy: pip install undetected-chromedriver", "WARN")
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        lang_pref = "ko-KR,ko,en-US,en" if "ko" in language else "en-US,en"
        options.add_argument(f"--lang={language}")
        options.add_argument(f"--accept-lang={lang_pref}")
        options.add_experimental_option('prefs', {'intl.accept_languages': lang_pref})
        options.add_argument(f"--window-size={window_width},{window_height}")
        options.add_argument(f"--window-position={x},0")
        if headless:
            options.add_argument("--headless=new")
        if keep_open:
            options.add_experimental_option("detach", True)
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service as ChromeService
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        try:
            driver.set_window_rect(x=x, y=0, width=window_width, height=window_height)
        except:
            pass
    return driver


def try_click(driver, element, label=""):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)
        element.click()
        return True
    except:
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except:
            return False


def set_react_input(driver, element, value):
    from selenium.webdriver.common.keys import Keys
    try:
        element.click()
        time.sleep(0.2)
        element.send_keys(Keys.CONTROL + "a")
        element.send_keys(Keys.DELETE)
        time.sleep(0.1)
        for char in value:
            element.send_keys(char)
            time.sleep(0.03)
        time.sleep(0.3)
    except:
        pass


def is_element_present(driver, By, selector):
    try:
        els = driver.find_elements(By, selector)
        for el in els:
            if el.is_displayed():
                return el
        return None
    except:
        return None


def worker_loop(driver, email, password, acc_info, mail_api_source="mixmmo", open_payment=False, language="en-US"):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    log(f"[{email}] Bắt đầu đăng ký Grok (hotmail)...", "INFO")
    masked_email = email[:3] + "***" + email[email.find("@"):] if "@" in email else email[:3] + "***"
    send_telegram_message(f"⏳ Bắt đầu đăng ký Grok cho tài khoản:\nEmail: {masked_email}")

    # ── State tracking ────────────────────────────────────
    otp_fetched = False
    otp_entered = False
    confirm_retries = 0
    names_filled = False
    saved = False
    last_state = ""
    stuck_count = 0

    # ── Mở trang đăng ký ─────────────────────────────────
    for _ in range(3):
        try:
            driver.get(GROK_URL)
            time.sleep(3)
            break
        except:
            time.sleep(2)

    while True:
        if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
            log(f"[{email}] Task bị dừng!", "WARN")
            return False

        try:
            handles = driver.window_handles
            if handles:
                driver.switch_to.window(handles[-1])
            url = driver.current_url
        except:
            time.sleep(2)
            continue

        # ── Xác định trạng thái hiện tại ─────────────────
        state = "LOADING"

        if "accounts.x.ai" in url:

            # --- Dashboard: tạo acc thành công ---
            if url.endswith("/account") or "/account/" in url or url.endswith("/dashboard") or "/dashboard/" in url:
                state = "DASHBOARD"
                if state != last_state:
                    log(f"[{email}] ✅ Đã vào dashboard! Đăng ký thành công.", "OK")
                    if not saved:
                        save_account(email, password)
                        saved = True
                time.sleep(2)
                if open_payment:
                    log(f"[{email}] Mở link thanh toán...", "INFO")
                    try:
                        driver.get("https://grok.com")
                        log(f"[{email}] Chờ 5 giây cho trang chủ tải...", "INFO")
                        time.sleep(5)
                        
                        log(f"[{email}] Tìm nút đen xác nhận điều khoản...", "INFO")
                        try:
                            # Nút confirm thường là button có class/text cụ thể
                            confirm_btn = _find(driver, By.XPATH, "//button[contains(., 'Confirm') or contains(., 'Agree') or contains(., '확인')]")
                            if not confirm_btn:
                                confirm_btn = _find(driver, By.CSS_SELECTOR, "button[data-slot='button']")
                            
                            if confirm_btn:
                                try_click(driver, confirm_btn)
                                log(f"[{email}] Đã bấm xác nhận điều khoản!", "OK")
                            else:
                                log(f"[{email}] Không tìm thấy nút xác nhận, bỏ qua...", "WARN")
                        except Exception as e:
                            log(f"[{email}] Lỗi khi bấm xác nhận: {e}", "ERR")
                            
                        log(f"[{email}] Chờ 4 giây hoàn tất xác nhận...", "INFO")
                        time.sleep(4)
                        
                        payment_url = "https://www.google.com/url?q=https://click.email.grok.com/f/a/D44YCrJINRlgI2nErQ2N4w~~/AAQRxRA~/o0ricJbDY0rYPxCddFIDNRk2rG8EhS26KMn4apYEY-nr5FVszrYVqzImlPsu8vfrgKF0FDNuaRbdv6FpHk28pqS1U_QbRThaJXq2gQ5kS6Kq7PHN-qbhqmI_S0v4c8kwZLpv5MxoCt4-NHuKiAbRNfuKPaKKadwrK5qyXW_4DV1SmDj5rbIN58HAqOsDJvZ-txKf9S5c34i5kRa3cvXLZorKvePXynuJgcjyNYlFAV4brCqx9YfZ3Z_BUQyMWuXKZ5JA_JUVoqaxMmhKIEYLegWBe__10w_McQJSnoGwLvmHAOlVMZ0F5HNP-vOv97LJ6Dx_K4DkAG4PTT5S3sa2ruUinHy0N6kNLDFqGishvN7zb_NyaCc6vZZNHXbB1oiafAQlED9USuI_1dpIfm8IUNnCJ-3TVkFOtU5o3b4bBKk~&source=gmail&ust=1788539378411000&usg=AOvVaw1j8Snr-3bNvMemb1zmc57D"
                        driver.switch_to.new_window('tab')
                        driver.get(payment_url)
                        
                        start_time = time.time()
                        while time.time() - start_time < 30:
                            current_url = driver.current_url
                            
                            if "/tos-gate" in current_url:
                                log(f"[{email}] Đang xác nhận TOS, chờ 5s...", "INFO")
                                time.sleep(5)
                                tos_btn = _find(driver, By.CSS_SELECTOR, "button[data-slot='button']")
                                if tos_btn:
                                    try_click(driver, tos_btn)
                                    time.sleep(3)
                                    driver.get(payment_url)
                                    time.sleep(2)
                                    continue
                            
                            redirect_link = _find(driver, By.CSS_SELECTOR, 'a[href^="/goto?url="], a[href^="/url?q="]')
                            if redirect_link:
                                try_click(driver, redirect_link)
                                time.sleep(2)
                                continue
                                
                            claim_btn = _find(driver, By.XPATH, "//button[contains(., 'Claim') or contains(., '무료 혜택 받기')]")
                            if claim_btn:
                                try_click(driver, claim_btn)
                                log(f"[{email}] Đã click Claim offer!", "INFO")
                                time.sleep(5)
                                continue
                                
                            # Stripe Checkout
                            if "checkout.stripe.com" in current_url:
                                kakao_btn = _find(driver, By.CSS_SELECTOR, '[data-testid="kakao_pay-accordion-item"]')
                                if kakao_btn:
                                    try_click(driver, kakao_btn)
                                    time.sleep(1)
                                
                                submit_btn = _find(driver, By.CSS_SELECTOR, 'button[data-testid="hosted-payment-submit-button"]')
                                if submit_btn:
                                    try_click(driver, submit_btn)
                                    log(f"[{email}] Đã chọn KakaoPay và thanh toán Stripe!", "OK")
                                    time.sleep(5)
                                    if "nicepay.co.kr" in driver.current_url:
                                        log(f"[{email}] Đã chuyển qua cổng NicePay thành công!", "OK")
                                        final_link = driver.current_url
                                        masked_email = email[:3] + "***" + email[email.find("@"):] if "@" in email else email[:3] + "***"
                                        msg = f"🎉 Đăng ký thành công!\nEmail: {masked_email}\nLink thanh toán NicePay:\n{final_link}"
                                        send_telegram_message(msg)
                                        masa_token = get_db_setting("MASA_TOKEN", "")
                                        submit_to_masa_api(final_link, email, masa_token, send_telegram_message, lambda txt, lvl="INFO": log(f"[{email}] {txt}", lvl))
                                    break
                                
                            time.sleep(1)
                    except Exception as e:
                        log(f"[{email}] Lỗi mở link thanh toán: {str(e)}", "ERR")
                return True

            # --- Bước 4: Điền tên + mật khẩu + Turnstile ---
            elif _find(driver, By.CSS_SELECTOR, 'input[data-testid="givenName"], input[name="givenName"]'):
                state = "STEP4_COMPLETE"
                if state != last_state:
                    log(f"[{email}] Bước 4: Điền tên, mật khẩu, chờ Turnstile...", "INFO")

                if not names_filled:
                    try:
                        # First name
                        f_inp = _find(driver, By.CSS_SELECTOR, 'input[data-testid="givenName"], input[name="givenName"]')
                        if f_inp and not f_inp.get_attribute("value"):
                            _set_react_value(driver, f_inp, _rand_name())

                        # Last name
                        l_inp = _find(driver, By.CSS_SELECTOR, 'input[data-testid="familyName"], input[name="familyName"]')
                        if l_inp and not l_inp.get_attribute("value"):
                            _set_react_value(driver, l_inp, _rand_name())

                        # Password
                        p_inp = _find(driver, By.CSS_SELECTOR, 'input[data-testid="password"], input[name="password"]')
                        if p_inp and not p_inp.get_attribute("value"):
                            _set_react_value(driver, p_inp, password)

                        names_filled = True
                        log(f"[{email}] Đã điền tên và mật khẩu, chờ Turnstile...", "INFO")
                    except Exception as ex:
                        log(f"[{email}] Lỗi điền tên: {ex}", "WARN")

                # Chờ Turnstile hoàn thành (cf-turnstile-response có giá trị)
                try:
                    cf_val = driver.execute_script(
                        "var el = document.querySelector('input[name=\"cf-turnstile-response\"]'); return el ? el.value : '';"
                    )
                    if cf_val and len(cf_val) > 20:
                        log(f"[{email}] Turnstile OK! Click Complete sign up...", "INFO")
                        btn = _find(driver, By.XPATH, "//button[@type='submit' and contains(., 'Complete sign up')]")
                        if btn:
                            try_click(driver, btn, "Complete sign up")
                            time.sleep(4)
                        else:
                            log(f"[{email}] Không tìm thấy nút Complete sign up!", "WARN")
                    else:
                        log(f"[{email}] Chờ Turnstile... (còn chờ)", "INFO")
                except Exception as ex:
                    log(f"[{email}] Lỗi check Turnstile: {ex}", "WARN")

            # --- Bước 3: OTP 6 số ---
            elif _find(driver, By.CSS_SELECTOR, 'input[data-input-otp="true"], input[name="code"]'):
                state = "STEP3_OTP"
                if state != last_state:
                    log(f"[{email}] Bước 3: Chờ OTP xAI 6 số...", "INFO")

                if not otp_fetched:
                    otp = wait_for_otp_hotmail(
                        acc_info["email"], acc_info["password"],
                        acc_info["refresh_token"], acc_info["client_id"],
                        timeout=120, interval=4, mail_api_source=mail_api_source
                    )
                    if otp:
                        otp_fetched = True
                        log(f"[{email}] OTP = {otp}, đang nhập...", "INFO")
                        # Nhập vào input[data-input-otp] (OTP widget ẩn)
                        try:
                            otp_inp = driver.find_element(By.CSS_SELECTOR, 'input[data-input-otp="true"]')
                            driver.execute_script("arguments[0].focus();", otp_inp)
                            time.sleep(0.3)
                            # Send từng ký tự
                            for ch in otp:
                                otp_inp.send_keys(ch)
                                time.sleep(0.1)
                            otp_entered = True
                            log(f"[{email}] Đã nhập OTP {otp}", "OK")
                            time.sleep(1)
                            # Click Confirm email
                            btn = _find(driver, By.XPATH, "//button[@type='submit' and contains(., 'Confirm email')]")
                            if btn:
                                try_click(driver, btn, "Confirm email")
                                time.sleep(3)
                        except Exception as ex:
                            log(f"[{email}] Lỗi nhập OTP: {ex}", "WARN")
                    else:
                        log(f"[{email}] Không nhận được OTP! Dừng.", "ERR")
                        return False

                elif otp_entered:
                    # Vẫn còn trên trang OTP sau khi đã nhập → thử click Confirm lại
                    btn = _find(driver, By.XPATH, "//button[@type='submit' and contains(., 'Confirm email')]")
                    if btn:
                        confirm_retries += 1
                        if confirm_retries > 3:
                            log(f"[{email}] Lỗi xác nhận OTP nhiều lần (có thể mail lỗi/OTP sai)! Bỏ qua.", "ERR")
                            return False
                        log(f"[{email}] Click lại Confirm email... ({confirm_retries}/3)", "WARN")
                        try_click(driver, btn, "Confirm email")
                        time.sleep(3)

            # --- Bước 2: Nhập email ---
            elif _find(driver, By.CSS_SELECTOR, 'input[data-testid="email"], input[name="email"]'):
                state = "STEP2_EMAIL"
                if state != last_state:
                    log(f"[{email}] Bước 2: Nhập email...", "INFO")
                try:
                    inp = _find(driver, By.CSS_SELECTOR, 'input[data-testid="email"], input[name="email"]')
                    if inp:
                        # Set value bằng JS React-compatible
                        _set_react_value(driver, inp, email)
                        time.sleep(0.5)
                        # Click Sign up ngay sau khi nhập email
                        btn = _find(driver, By.XPATH, "//button[@type='submit' and contains(., 'Sign up')]")
                        if btn:
                            log(f"[{email}] Click Sign up...", "INFO")
                            try_click(driver, btn, "Sign up")
                            time.sleep(3)
                except Exception as ex:
                    log(f"[{email}] Lỗi nhập email: {ex}", "WARN")

            # --- Bước 1: Click "Sign up with email" ---
            elif _find(driver, By.XPATH, "//button[.//text()[contains(., 'Sign up with email')]]"):
                state = "STEP1_CHOOSE"
                if state != last_state:
                    log(f"[{email}] Bước 1: Click 'Sign up with email'...", "INFO")
                btn = _find(driver, By.XPATH, "//button[.//text()[contains(., 'Sign up with email')]]")
                if btn:
                    try_click(driver, btn, "Sign up with email")
                    time.sleep(2)

            else:
                # Đang loading / Cloudflare challenge
                state = "WAITING"
                if state != last_state:
                    log(f"[{email}] Đang chờ trang load / bypass Cloudflare...", "INFO")
                stuck_count += 1
                if stuck_count > 60:  # 2 phút vẫn chưa vào được
                    log(f"[{email}] Timeout chờ trang x.ai (blocked?)!", "ERR")
                    return False

        elif saved:
            # Đã lưu, trang khác (redirect) → thành công
            return True

        else:
            state = "OTHER"
            stuck_count += 1
            if stuck_count > 30:
                log(f"[{email}] Timeout ở trang lạ: {url}", "ERR")
                return False

        if state != "WAITING" and state != "OTHER":
            stuck_count = 0

        last_state = state
        time.sleep(2)


# ── Helper functions ─────────────────────────────────────────────────

def _find(driver, By, selector):
    """Tìm element hiển thị đầu tiên. Trả về element hoặc None."""
    try:
        els = driver.find_elements(By, selector)
        for el in els:
            try:
                if el.is_displayed():
                    return el
            except:
                pass
        return None
    except:
        return None


def _rand_name(length=6):
    """Tạo tên ngẫu nhiên."""
    return ''.join(random.choices(string.ascii_lowercase, k=1)).upper() + \
           ''.join(random.choices(string.ascii_lowercase, k=length - 1))


def _type_into(driver, element, value):
    """Xóa sạch và gõ từng ký tự vào input (dùng cho input thường)."""
    from selenium.webdriver.common.keys import Keys
    try:
        driver.execute_script("arguments[0].click(); arguments[0].focus();", element)
        time.sleep(0.2)
        # Xóa nội dung cũ
        element.send_keys(Keys.CONTROL + "a")
        time.sleep(0.05)
        element.send_keys(Keys.DELETE)
        time.sleep(0.1)
        # Gõ từng ký tự
        for ch in str(value):
            element.send_keys(ch)
            time.sleep(0.04)
        time.sleep(0.2)
    except:
        _set_react_value(driver, element, value)


def _set_react_value(driver, element, value):
    """Set value cho React controlled input bằng nativeInputValueSetter."""
    try:
        driver.execute_script("""
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(arguments[0], arguments[1]);
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        """, element, str(value))
        time.sleep(0.1)
    except:
        # Fallback: gõ từng phím
        from selenium.webdriver.common.keys import Keys
        try:
            element.click()
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.DELETE)
            for ch in str(value):
                element.send_keys(ch)
                time.sleep(0.03)
        except:
            pass


def register_one_account(index, keep_open=False, batch_size=3, headless=False,
                         browser_type="uc", mail_api_source="mixmmo", use_proxy=False, open_payment=False, language="en-US"):
    global ACTIVE_DRIVERS
    acc = None
    driver = None
    try:
        try:
            acc = HOTMAIL_QUEUE.get_nowait()
        except queue.Empty:
            log(f"[Worker {index}] Hết hotmail trong queue!", "WARN")
            return False

        email = acc["email"]
        password = PASSWORD
        log(f"[Worker {index}] Đăng ký Grok với: {email}", "INFO")

        driver = setup_driver(index, keep_open=keep_open, batch_size=batch_size,
                              headless=headless, browser_type=browser_type, use_proxy=use_proxy, language=language)
        if keep_open or open_payment:
            ACTIVE_DRIVERS[email] = driver

        result = worker_loop(driver, email, password, acc, mail_api_source=mail_api_source, open_payment=open_payment, language=language)
        if result:
            mark_hotmail_used(acc)
            log(f"[{email}] ✅ Đăng ký Grok thành công!", "OK")
        else:
            log(f"[{email}] ❌ Đăng ký Grok thất bại!", "ERR")
        return result
    except Exception as e:
        log(f"LỖI worker Grok {index}: {e}", "ERR")
        return False
    finally:
        if driver and not (keep_open or open_payment):
            try:
                driver.quit()
            except:
                pass
