#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grok Auto Register Bot - Domain Mail Edition
Đăng ký tài khoản Grok (x.ai) bằng mail domain (regmail.phh.info.vn API).
Tích hợp vào Web UI (app.py).
"""
import time
import re
import os
import requests
import random
import string
import threading
from datetime import datetime
import sqlite3

def get_db_setting(key, default=""):
    try:
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database.db"))
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row and row["value"]:
            return row["value"]
    except Exception as e:
        print(f"Lỗi đọc DB ({key}):", e)
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

# ── Cấu hình ────────────────────────────────────────────────────────
BASE_URL = "https://regmail.phh.info.vn"
API_KEY  = "rm_36414c094209fea1370de45ec4e48c30783e896ceba0c1659bbba6f82590613c"
GROK_URL = "https://accounts.x.ai/sign-up"
OUTPUT_FILE = "data/grok_accounts.txt"
PASSWORD = "grokai123"

API_HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

import random
import queue
from src.utils.masa_api import submit_to_masa_api

# Cờ báo dừng chung cho toàn hệ thống
DRIVER_LOCK = threading.Lock()
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


def create_random_email():
    resp = requests.post(f"{BASE_URL}/api/emails/create", headers=API_HEADERS, proxies={"http": None, "https": None}, timeout=10)
    data = resp.json()
    if data.get("success") and data.get("email"):
        log(f"Đã tạo email domain: {data['email']}", "OK")
        return data["email"]
    raise Exception(f"Không tạo được email: {data}")


def get_latest_email(email_address):
    resp = requests.get(f"{BASE_URL}/api/emails/latest", headers=API_HEADERS, params={"email": email_address}, proxies={"http": None, "https": None}, timeout=10)
    data = resp.json()
    if data.get("success") and data.get("email"):
        return data["email"]
    return None


def delete_mailbox(email_address):
    try:
        requests.delete(f"{BASE_URL}/api/emails/address/{email_address}", headers=API_HEADERS, proxies={"http": None, "https": None}, timeout=10)
        log(f"Đã xóa hòm thư: {email_address}", "OK")
    except Exception as e:
        log(f"Lỗi xóa mail: {e}", "WARN")


def wait_for_otp_domain(email_address, timeout=120, interval=4):
    log(f"Chờ OTP xAI cho {email_address} (tối đa {timeout}s)...", "INFO")
    elapsed = 0
    while elapsed < timeout:
        if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
            return None
        mail = get_latest_email(email_address)
        if mail:
            subject = mail.get("subject", "")
            text_body = mail.get("text", "")
            code = _extract_xai_code(subject)
            if not code:
                code = _extract_xai_code(text_body)
            if code:
                log(f"Nhận OTP xAI: {code}", "OK")
                return code
            log("Nhận email nhưng chưa có OTP...", "WARN")
        time.sleep(interval)
        elapsed += interval
    log("Hết thời gian chờ OTP!", "ERR")
    return None


def _extract_xai_code(text):
    if not text:
        return None
    match = re.search(r'\b(\d{3})-?(\d{3})\b', text)
    if match:
        return match.group(1) + match.group(2)
    return None


def save_account(email, password):
    line = f"{email}\t{password}"
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    log(f"Đã lưu tài khoản Grok → {OUTPUT_FILE}", "OK")


from .browser_utils import get_rotated_proxy as _grp
def get_rotated_proxy():
    return _grp(logger_func=log)



def setup_driver(index=1, keep_open=False, batch_size=3, headless=False, browser_type="uc", use_proxy=False, language="en-US"):
    DRIVER_LOCK = threading.Lock()
    from .browser_utils import get_window_bounds
    window_width, window_height, x, y = get_window_bounds(index, batch_size, zero_based_index=False, grid_2x2=True)

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
        driver.set_window_position(x, y)
        return driver

    # Chrome / UC (undetected_chromedriver) — bypass Cloudflare x.ai
    try:
        import undetected_chromedriver as uc
        def _build_uc_options():
            opts = uc.ChromeOptions()
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            if "vi" in language:
                lang_pref = "vi-VN,vi,en-US,en"
            elif "ko" in language:
                lang_pref = "ko-KR,ko,en-US,en"
            else:
                lang_pref = "en-US,en"
            opts.add_argument(f"--lang={language}")
            opts.add_argument(f"--accept-lang={lang_pref}")
            if not hasattr(opts, "_uc_prefs"):
                opts._uc_prefs = {}
            opts.add_experimental_option('prefs', {'intl.accept_languages': lang_pref})
            opts.add_argument(f"--window-size={window_width},{window_height}")
            opts.add_argument(f"--window-position={x},{y}")
            if headless:
                opts.add_argument("--headless=new")
            return opts

        with DRIVER_LOCK:
            from src.bots.x_grok_hunter import get_installed_chrome_version
            v_main = get_installed_chrome_version()
            try:
                if v_main:
                    driver = uc.Chrome(options=_build_uc_options(), use_subprocess=True, version_main=v_main)
                else:
                    driver = uc.Chrome(options=_build_uc_options(), use_subprocess=True)
            except Exception as e:
                import re
                match = re.search(r'Current browser version is (\d+)', str(e))
                if match:
                    v_main = int(match.group(1))
                    log(f"[Worker {index}] Lỗi version chrome, thử lại với version_main={v_main}", "WARN")
                    driver = uc.Chrome(options=_build_uc_options(), use_subprocess=True, version_main=v_main)
                else:
                    raise e
            try:
                driver.set_window_rect(x=x, y=y, width=window_width, height=window_height)
            except:
                pass
        log(f"[Worker {index}] Dùng Undetected Chrome (Vị trí: x={x}, y={y}, kích thước={window_width}x{window_height})", "INFO")
    except ImportError:
        log("undetected_chromedriver chưa cài, dùng Selenium Chrome thường.", "WARN")
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(f"--lang={language}")
        options.add_argument(f"--window-size={window_width},{window_height}")
        options.add_argument(f"--window-position={x},{y}")
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
            driver.set_window_rect(x=x, y=y, width=window_width, height=window_height)
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


def worker_loop(driver, email, password, open_payment=False, apple_pay=False, language="en-US", refer_link="", payment_mode="masa", **kwargs):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    log(f"[{email}] Bắt đầu đăng ký Grok referral (domain)...", "INFO")
    masked_email = email[:3] + "***" + email[email.find("@"):] if "@" in email else email[:3] + "***"
    send_telegram_message(f"⏳ Bắt đầu đăng ký Grok referral:\nEmail: {masked_email}")

    # ── State tracking ────────────────────────────────────
    otp_fetched = False
    otp_entered = False
    confirm_retries = 0
    email_submitted = False
    otp_submitted = False
    account_created = False
    age_submitted = False
    email_sent_time = 0
    invalid_otps = set()
    last_tried_otp = ""
    saved = False
    last_state = ""
    stuck_count = 0

    # ── Xác định URL bắt đầu (referral link) ──────────────
    target_url = refer_link.strip() if (refer_link and refer_link.strip()) else "https://grok.com/refer/bot?code=GMED5B6WV9GC"
    log(f"[{email}] Truy cập Grok referral: {target_url}", "INFO")
    for _ in range(3):
        try:
            driver.get(target_url)
            time.sleep(3)
            try:
                driver.execute_script("document.body.style.zoom='90%';")
            except:
                pass
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

        state = "CHECKING"

        # ── 1. ĐÃ TỚI TRANG PLANS (HOÀN TẤT) ─────────────────
        # CHỈ ĐƯỢC COI LÀ HOÀN TẤT KHI ĐÃ TẠO TÀI KHOẢN XONG (account_created hoặc age_submitted)!
        if (account_created or age_submitted) and ("/plans" in url or (saved and "grok.com" in url)):
            if not saved:
                save_account(email, password)
                saved = True
            log(f"[{email}] ✅ Đã tạo tài khoản thành công ({url})! Hoàn tất.", "OK")
            masked_email = email[:3] + "***" + email[email.find("@"):] if "@" in email else email[:3] + "***"
            send_telegram_message(f"🎉 Đăng ký Grok referral thành công!\nEmail: {masked_email}")
            return True

        # ── 2. NÚT 'Choose a plan' (Free trial not available) ──
        # CHỈ ĐƯỢC BẤM KHI ĐÃ QUA BƯỚC TẠO TÀI KHOẢN (không bấm nhầm link header/footer của trang ban đầu)
        if account_created or age_submitted:
            trial_title = _find(driver, By.CSS_SELECTOR, '[data-testid="referral-trial-title"]')
            choose_plan_btn = _find(driver, By.CSS_SELECTOR, '[data-testid="referral-trial-choose-plan"]')
            if not choose_plan_btn and trial_title:
                choose_plan_btn = _find(driver, By.XPATH, "//a[contains(., 'Choose a plan')] | //button[contains(., 'Choose a plan')]")
            if choose_plan_btn:
                state = "CHOOSE_PLAN"
                if state != last_state:
                    log(f"[{email}] Màn hình thông báo Trial không khả dụng -> Click 'Choose a plan'...", "INFO")
                try_click(driver, choose_plan_btn, "Choose a plan")
                time.sleep(3)
                last_state = state
                stuck_count = 0
                continue

        # ── 3. BƯỚC OTP ("Check your email") ──────────────────
        otp_inp = _find(driver, By.CSS_SELECTOR, 'input[data-input-otp="true"], input[autocomplete="one-time-code"]')
        if not otp_inp:
            has_otp_text = _find(driver, By.XPATH, "//*[contains(text(), 'Check your email')]")
            if has_otp_text:
                otp_inp = _find(driver, By.CSS_SELECTOR, 'input[name="code"], input[inputmode="numeric"]')

        if otp_inp:
            state = "CHECK_EMAIL_OTP"
            email_submitted = True
            if state != last_state:
                log(f"[{email}] Màn hình 'Check your email' -> Chờ lấy mã OTP mới...", "INFO")

            if not otp_fetched:
                if email_sent_time > 0 and (time.time() - email_sent_time) < 5:
                    time.sleep(4)

                otp = wait_for_otp_domain(email, timeout=120, interval=4)
                if otp:
                    clean_otp = re.sub(r'\D', '', str(otp))
                    if len(clean_otp) == 6:
                        otp = clean_otp
                    if otp in invalid_otps:
                        time.sleep(3)
                        continue
                    otp_fetched = True
                    last_tried_otp = otp
                    log(f"[{email}] Nhận mã OTP mới: {otp}. Đang nhập vào form...", "OK")
                    try:
                        driver.execute_script("""
                            var el = arguments[0];
                            el.focus();
                            el.click();
                            el.value = '';
                        """, otp_inp)
                        time.sleep(0.3)
                    except: pass
                    for ch in otp:
                        otp_inp.send_keys(ch)
                        time.sleep(0.15)
                    otp_entered = True
                    time.sleep(1)

                    try:
                        driver.execute_script("""
                            var el = arguments[0];
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        """, otp_inp)
                    except: pass
                    time.sleep(1)

                    v_btn = _find(driver, By.XPATH, "//button[@type='submit'] | //button[contains(., 'Verify') or contains(., 'Confirm') or contains(., 'Continue') or contains(., 'Xác minh') or contains(., 'Tiếp tục')]")
                    if not v_btn:
                        v_btn = _find(driver, By.CSS_SELECTOR, "form button[type='submit'], button[type='submit']")
                    if v_btn:
                        log(f"[{email}] Bấm nút Verify/Continue OTP...", "INFO")
                        try_click(driver, v_btn, "Verify OTP")
                        otp_submitted = True
                        time.sleep(3)
                else:
                    log(f"[{email}] Không lấy được OTP! Dừng.", "ERR")
                    return False
            elif otp_entered:
                is_invalid = driver.execute_script("return document.body.innerText.toLowerCase().includes('invalid') || document.body.innerText.toLowerCase().includes('expired') || document.body.innerText.toLowerCase().includes('incorrect');")
                if is_invalid:
                    log(f"[{email}] Mã OTP {last_tried_otp} bị sai hoặc hết hạn! Bấm gửi lại mã mới...", "WARN")
                    if last_tried_otp:
                        invalid_otps.add(last_tried_otp)
                    resend_btn = _find(driver, By.XPATH, "//button[contains(., 'Resend') or contains(., 'Request a new one')]")
                    if resend_btn:
                        try_click(driver, resend_btn, "Resend")
                        email_sent_time = time.time()
                        time.sleep(4)
                    otp_fetched = False
                    otp_entered = False
                    continue

                v_btn = _find(driver, By.XPATH, "//button[@type='submit'] | //button[contains(., 'Verify') or contains(., 'Confirm') or contains(., 'Continue') or contains(., 'Xác minh') or contains(., 'Tiếp tục')]")
                if not v_btn:
                    v_btn = _find(driver, By.CSS_SELECTOR, "form button[type='submit'], button[type='submit']")
                if v_btn:
                    confirm_retries += 1
                    if confirm_retries > 3:
                        log(f"[{email}] Lỗi xác nhận OTP nhiều lần! Dừng.", "ERR")
                        return False
                    log(f"[{email}] Click lại nút Verify ({confirm_retries}/3)...", "WARN")
                    try_click(driver, v_btn, "Verify OTP")
                    time.sleep(3)

            last_state = state
            stuck_count = 0
            continue

        # ── 4. BƯỚC ĐIỀN TÊN + MẬT KHẨU ("Create account") ─────
        pw_inp = _find(driver, By.CSS_SELECTOR, 'input#signup-password, input[autocomplete="new-password"], input[data-testid="password"], input[name="password"]')
        first_inp = _find(driver, By.CSS_SELECTOR, 'input#signup-given-name, input[autocomplete="given-name"], input[data-testid="givenName"], input[name="givenName"]')
        if pw_inp and first_inp:
            state = "CREATE_ACCOUNT"
            if state != last_state:
                log(f"[{email}] Màn hình 'Create account' -> Điền tên, mật khẩu, chờ Turnstile...", "INFO")

            if not first_inp.get_attribute("value"):
                _set_react_value(driver, first_inp, _rand_name(5))
                time.sleep(0.2)

            last_inp = _find(driver, By.CSS_SELECTOR, 'input#signup-family-name, input[autocomplete="family-name"], input[data-testid="familyName"], input[name="familyName"]')
            if last_inp and not last_inp.get_attribute("value"):
                _set_react_value(driver, last_inp, _rand_name(6))
                time.sleep(0.2)

            if not pw_inp.get_attribute("value"):
                _set_react_value(driver, pw_inp, password)
                time.sleep(0.3)

            # Chờ Cloudflare Turnstile hoặc form sẵn sàng
            try:
                cf_val = driver.execute_script(
                    "var el = document.querySelector('input[name=\"cf-turnstile-response\"]'); return el ? el.value : '';"
                )
                create_btn = _find(driver, By.XPATH, "//button[@type='submit' and (contains(., 'Create account') or contains(., 'Complete sign up') or contains(., 'Tạo tài khoản'))]")
                if not create_btn:
                    create_btn = _find(driver, By.CSS_SELECTOR, "form button[type='submit'], button[type='submit']")

                is_btn_ready = False
                if create_btn:
                    try:
                        dis = create_btn.get_attribute("disabled")
                        aria_dis = create_btn.get_attribute("aria-disabled")
                        is_btn_ready = (dis is None or dis == "false") and aria_dis != "true"
                    except:
                        is_btn_ready = True

                if (cf_val and len(cf_val) > 20) or is_btn_ready:
                    if create_btn:
                        log(f"[{email}] Turnstile OK / Nút submit sẵn sàng! Bấm 'Create account'...", "OK")
                        try_click(driver, create_btn, "Create account")
                        account_created = True
                        time.sleep(4)
                else:
                    log(f"[{email}] Đang chờ Turnstile giải captcha...", "INFO")
                    time.sleep(2)
            except Exception as ex:
                log(f"[{email}] Lỗi kiểm tra Turnstile: {ex}", "WARN")

            last_state = state
            stuck_count = 0
            continue

        # ── 5. BƯỚC AGE GATE ("How old are you?") ──────────────
        how_old_title = _find(driver, By.XPATH, "//h1[contains(., 'How old are you') or contains(., 'bao nhiêu tuổi')] | //*[contains(text(), 'How old are you') or contains(text(), 'bao nhiêu tuổi')]")
        if how_old_title:
            age_inp = _find(driver, By.CSS_SELECTOR, 'input#_r_9_, input[maxlength="3"], input[inputmode="numeric"]')
            if not age_inp:
                age_inp = _find(driver, By.XPATH, "//label[contains(., 'Age')]/following::input[1]")
            if age_inp:
                state = "AGE_GATE"
                account_created = True
                if state != last_state:
                    log(f"[{email}] Màn hình 'How old are you?' -> Điền tuổi trên 18...", "INFO")

                name_inp = _find(driver, By.CSS_SELECTOR, 'input[autocomplete="name"], input#_r_8_')
                if name_inp and not name_inp.get_attribute("value"):
                    _set_react_value(driver, name_inp, f"{_rand_name(5)} {_rand_name(6)}")
                    time.sleep(0.2)

                rand_age = str(random.randint(21, 29))
                _set_react_value(driver, age_inp, rand_age)
                time.sleep(0.5)

                cont_btn = _find(driver, By.XPATH, "//button[@type='submit' and (contains(., 'Continue') or contains(., 'Tiếp tục'))]")
                if not cont_btn:
                    cont_btn = _find(driver, By.CSS_SELECTOR, "form button[type='submit']")
                if cont_btn:
                    try_click(driver, cont_btn, "Age Continue")
                    age_submitted = True
                    time.sleep(3)
                last_state = state
                stuck_count = 0
                continue

        # ── 6. FORM NHẬP EMAIL ────────────────────────────────
        email_inp = _find(driver, By.CSS_SELECTOR, 'input#auth-email, input[data-testid="email"], input[autocomplete="email"], input[type="email"]')
        if email_inp:
            state = "ENTER_EMAIL"
            if state != last_state:
                log(f"[{email}] Thấy form đăng ký -> Nhập email: {email}...", "INFO")
            try:
                _set_react_value(driver, email_inp, email)
                time.sleep(0.5)
                cont_btn = _find(driver, By.XPATH, "//form//button[@type='submit' and (contains(., 'Continue') or contains(., 'Sign up'))]")
                if not cont_btn:
                    cont_btn = _find(driver, By.CSS_SELECTOR, "form button[type='submit']")
                if cont_btn:
                    log(f"[{email}] Bấm nút Continue gửi email...", "INFO")
                    try_click(driver, cont_btn, "Email Continue")
                    email_submitted = True
                    email_sent_time = time.time()
                    time.sleep(4)
            except Exception as ex:
                log(f"[{email}] Lỗi nhập email: {ex}", "WARN")

            last_state = state
            stuck_count = 0
            continue

        # ── 7. NÚT 'Start your 14 day free trial' / Nhận ưu đãi Referral ────
        # Chỉ bấm khi chưa submit email
        if not email_submitted:
            trial_btn = _find(driver, By.CSS_SELECTOR, '[data-testid="referral-trial-sign-up"], [data-testid*="referral-trial"], [data-testid*="referral"]')
            if not trial_btn:
                trial_btn = _find(driver, By.XPATH, 
                    "//button[contains(., 'Start your 14 day free trial') or contains(., 'free trial') or contains(., 'Free trial') or contains(., 'Claim') or contains(., 'claim') or contains(., 'ưu đãi') or contains(., 'dùng thử') or contains(., 'Get started') or contains(., 'Try Grok') or contains(., 'Accept invite') or contains(., 'Accept referral') or contains(., '14일')] "
                    "| //a[contains(., 'Start your 14 day free trial') or contains(., 'free trial') or contains(., 'Free trial') or contains(., 'Claim') or contains(., 'claim') or contains(., 'ưu đãi') or contains(., 'dùng thử') or contains(., 'Get started') or contains(., 'Try Grok') or contains(., 'Accept invite') or contains(., 'Accept referral') or contains(., '14일')] "
                    "| //*[@role='button' and (contains(., 'free trial') or contains(., 'Claim') or contains(., 'ưu đãi') or contains(., 'dùng thử') or contains(., 'trial'))]"
                )

            # Nếu chưa thấy mà đang ở link refer, cuộn trang xuống nhẹ để kích hoạt tải phần tử
            if not trial_btn and "refer" in url:
                try:
                    driver.execute_script("window.scrollBy(0, 250);")
                except:
                    pass

            if trial_btn:
                state = "START_TRIAL"
                if state != last_state:
                    log(f"[{email}] Thấy nút Nhận ưu đãi / Start free trial -> Click...", "INFO")
                try_click(driver, trial_btn, "Start trial / Nhận ưu đãi")
                time.sleep(3)
                last_state = state
                stuck_count = 0
                continue

        # ── 8. NÚT 'Sign up with email' (nếu có lựa chọn) ────
        signup_email_btn = _find(driver, By.XPATH, "//button[.//text()[contains(., 'Sign up with email')]]")
        if signup_email_btn:
            state = "CHOOSE_EMAIL_METHOD"
            if state != last_state:
                log(f"[{email}] Click 'Sign up with email'...", "INFO")
            try_click(driver, signup_email_btn, "Sign up with email")
            time.sleep(2)
            last_state = state
            stuck_count = 0
            continue

        # ── 9. Dashboard (chỉ khi đã qua bước tạo acc) ────────
        if (account_created or age_submitted) and "accounts.x.ai" in url and (url.endswith("/account") or "/account/" in url or url.endswith("/dashboard") or "/dashboard/" in url):
            state = "DASHBOARD"
            if not saved:
                save_account(email, password)
                saved = True
            log(f"[{email}] ✅ Đã vào dashboard! Đăng ký thành công.", "OK")
            masked_email = email[:3] + "***" + email[email.find("@"):] if "@" in email else email[:3] + "***"
            send_telegram_message(f"🎉 Đăng ký Grok thành công!\nEmail: {masked_email}\nĐã vào Dashboard. Giữ nguyên tab trình duyệt.")
            return True

        # Đang loading / chờ
        stuck_count += 1
        if stuck_count % 10 == 0:
            log(f"[{email}] Đang chờ trang tải hoặc phản hồi ({stuck_count}s)...", "INFO")
        if stuck_count > 60:
            log(f"[{email}] Timeout chờ giao diện phản hồi (URL: {url})!", "ERR")
            return False

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
            var el = arguments[0];
            var val = arguments[1];
            el.focus();
            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        """, element, str(value))
        time.sleep(0.1)
    except Exception:
        pass
    # Nếu React chưa nhận giá trị, fallback gõ bằng send_keys
    try:
        if element.get_attribute("value") != str(value):
            from selenium.webdriver.common.keys import Keys
            element.click()
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.DELETE)
            for ch in str(value):
                element.send_keys(ch)
                time.sleep(0.02)
    except:
        pass


def register_one_account(index, count=1, keep_open=False, batch_size=3, headless=False, browser_type="uc", use_proxy=False, open_payment=False, apple_pay=False, language="en-US", refer_link="", payment_mode="masa", **kwargs):
    global ACTIVE_DRIVERS
    email = None
    driver = None
    try:
        email = create_random_email()
        if not email:
            return False
        password = PASSWORD
        log(f"[Worker {index}] Đăng ký Grok domain với: {email}", "INFO")
        driver = setup_driver(index, keep_open=False, batch_size=batch_size,
                              headless=headless, browser_type=browser_type, use_proxy=use_proxy, language=language)
        ACTIVE_DRIVERS[email] = driver
        result = worker_loop(driver, email, password, refer_link=refer_link, **kwargs)
        if result:
            log(f"[{email}] ✅ Đăng ký Grok domain thành công! Đã lưu tài khoản.", "OK")
        else:
            log(f"[{email}] ❌ Đăng ký Grok domain thất bại!", "ERR")
        try:
            driver.quit()
            ACTIVE_DRIVERS.pop(email, None)
        except:
            pass
        return result
    except Exception as e:
        log(f"LỖI worker Grok domain {index}: {e}", "ERR")
        return False
    finally:
        if email:
            delete_mailbox(email)
