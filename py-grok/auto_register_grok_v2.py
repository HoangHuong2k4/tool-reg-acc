#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import re
import sys
import os
import requests
import random
import string
import threading
from datetime import datetime

# Lock để tránh lỗi đụng độ file chromedriver của undetected_chromedriver khi khởi chạy đa luồng
DRIVER_LOCK = threading.Lock()

# ── Cấu hình ────────────────────────────────────────────────────────
BASE_URL    = "https://regmail.phh.info.vn"
API_KEY     = "1dec9d51e8707e9bf1fa7756612830c676f65a42a1009851580ec0a82384abd8"
PASSWORD    = "grokai123"
GROK_URL    = "https://accounts.x.ai/sign-up"
OUTPUT_FILE = "grokv1.txt"

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
    resp = requests.post(f"{BASE_URL}/api/emails/create", headers=API_HEADERS, timeout=10)
    data = resp.json()
    if data.get("success") and data.get("email"):
        log(f"Đã tạo email: {C.BOLD}{data['email']}{C.RST}", "OK")
        return data["email"]
    raise Exception(f"Không tạo được email: {data}")

def get_latest_email(email_address):
    resp = requests.get(f"{BASE_URL}/api/emails/latest", headers=API_HEADERS, params={"email": email_address}, timeout=10)
    data = resp.json()
    if data.get("success") and data.get("email"):
        return data["email"]
    return None

def extract_xai_code(text):
    if not text:
        return None
    match = re.search(r'\b([A-Z0-9]{3})-?([A-Z0-9]{3})\b', text, re.IGNORECASE)
    if match:
        return (match.group(1) + match.group(2)).upper()
    return None

def wait_for_otp(email_address, timeout=120, interval=4):
    log(f"Đang chờ OTP cho {email_address} (tối đa {timeout}s)...", "INFO")
    elapsed = 0
    while elapsed < timeout:
        mail = get_latest_email(email_address)
        if mail:
            subject = mail.get("subject", "")
            text_body = mail.get("text", "")
            
            code = extract_xai_code(subject)
            if not code:
                code = extract_xai_code(text_body)
                
            if code:
                log(f"Nhận được mã OTP xAI: {C.BOLD}{code}{C.RST}", "OK")
                return code
            log("Nhận được email nhưng chưa có OTP, chờ thêm...", "WARN")
        time.sleep(interval)
        elapsed += interval
    log("Hết thời gian chờ OTP!", "ERR")
    return None

def delete_mailbox(email_address):
    try:
        requests.delete(f"{BASE_URL}/api/emails/address/{email_address}", headers=API_HEADERS, timeout=10)
        log(f"Đã dọn hòm thư: {email_address}", "OK")
    except Exception as e:
        log(f"Lỗi xóa mail: {e}", "WARN")

def setup_driver(index=1, keep_open=False):
    try:
        import undetected_chromedriver as uc
    except ImportError:
        import os, sys
        os.system(f"{sys.executable} -m pip install undetected-chromedriver -q")
        import undetected_chromedriver as uc
        
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=vi-VN")
    
    window_width = 700; window_height = 1000
    idx = index - 1
    col = idx % 4
    x = col * 490
    y = 0
    
    options.add_argument(f"--window-size={window_width},{window_height}")
    options.add_argument(f"--window-position={x},{y}")

    with DRIVER_LOCK:
        driver = uc.Chrome(options=options, use_subprocess=True)
        
    try:
        driver.set_window_rect(x=x, y=y, width=window_width, height=window_height)
    except Exception:
        pass
        
    return driver

def try_click(driver, element, label=""):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)
        element.click()
        log(f"Clicked: {label}", "INFO")
        return True
    except:
        try:
            driver.execute_script("arguments[0].click();", element)
            log(f"JS-clicked: {label}", "INFO")
            return True
        except Exception as e:
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

def save_account(email, password):
    line = f"{email}\t{password}"
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    log(f"Đã lưu tài khoản → {OUTPUT_FILE}", "OK")

def is_element_present(driver, By, value):
    try:
        els = driver.find_elements(By, value)
        for el in els:
            if el.is_displayed():
                return el
        return None
    except:
        return None

def worker_loop(driver, email, password):
    from selenium.webdriver.common.by import By
    log(f"[{email}] Bắt đầu vòng lặp xử lý tự động theo URL (V2)...", "INFO")
    
    otp_fetched = False
    last_state = ""
    saved = False
    
    # Bắt đầu
    for _ in range(3):
        try:
            driver.get(GROK_URL)
            break
        except:
            time.sleep(2)
            
    while True:
        try:
            handles = driver.window_handles
            if handles:
                driver.switch_to.window(handles[-1])
            url = driver.current_url
        except Exception:
            time.sleep(2)
            continue
            
        current_state = "UNKNOWN"
            
        if "accounts.x.ai" in url:
            if "/account" in url:
                current_state = "ACCOUNT_DASHBOARD"
                if current_state != last_state: 
                    log(f"[{email}] Đã vào dashboard account. Chuyển sang Grok...", "OK")
                    if not saved:
                        save_account(email, password)
                        saved = True
                    driver.get("https://grok.com/?q=&reasoningMode=none&voice=false#subscribe")
                    time.sleep(3)
                    
            elif is_element_present(driver, By.CSS_SELECTOR, 'input[name="givenName"]'):
                current_state = "STEP3_NAMES"
                if current_state != last_state: log(f"[{email}] Trang điền Tên/Pass...", "INFO")
                try:
                    fname_input = is_element_present(driver, By.CSS_SELECTOR, 'input[name="givenName"]')
                    lname_input = is_element_present(driver, By.CSS_SELECTOR, 'input[name="familyName"]')
                    pass_input = is_element_present(driver, By.CSS_SELECTOR, 'input[name="password"]')
                    
                    if fname_input and not fname_input.get_attribute("value"):
                        fname = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=6))
                        set_react_input(driver, fname_input, fname)
                    if lname_input and not lname_input.get_attribute("value"):
                        lname = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=6))
                        set_react_input(driver, lname_input, lname)
                    if pass_input and not pass_input.get_attribute("value"):
                        set_react_input(driver, pass_input, password)
                        
                    btns = driver.find_elements(By.XPATH, "//button[@type='submit' and (contains(., 'Complete sign up') or contains(., 'Hoàn tất') or contains(., 'Complete'))]")
                    if btns and btns[0].is_displayed():
                        try_click(driver, btns[0], "Complete sign up")
                        time.sleep(3)
                except: pass
                    
            elif is_element_present(driver, By.CSS_SELECTOR, 'input[name="code"]'):
                current_state = "STEP2_OTP"
                if current_state != last_state: log(f"[{email}] Trang nhập OTP...", "INFO")
                
                if not otp_fetched:
                    otp = wait_for_otp(email, timeout=120, interval=4)
                    if otp:
                        otp_fetched = True
                        try:
                            inp = is_element_present(driver, By.CSS_SELECTOR, 'input[name="code"]')
                            if inp: set_react_input(driver, inp, otp)
                        except: pass
                    else:
                        log(f"[{email}] Hết hạn chờ OTP, dừng luồng.", "ERR")
                        return False
                else:
                    # Đã điền OTP, bấm verify
                    btns = driver.find_elements(By.XPATH, "//button[@type='submit' and (contains(., 'Confirm email') or contains(., 'Xác nhận') or contains(., 'Verify'))]")
                    if btns and btns[0].is_displayed():
                        try_click(driver, btns[0], "Confirm email")
                        time.sleep(2)
            
            elif is_element_present(driver, By.XPATH, "//button[contains(., 'Sign up with email')]"):
                current_state = "STEP1_EMAIL_BTN"
                if current_state != last_state: log(f"[{email}] Trang chọn Sign up with email...", "INFO")
                btn = is_element_present(driver, By.XPATH, "//button[contains(., 'Sign up with email')]")
                if btn: try_click(driver, btn, "Sign up with email btn")
                
            elif is_element_present(driver, By.CSS_SELECTOR, 'input[name="email"], input[type="email"]'):
                current_state = "STEP1_EMAIL_INPUT"
                if current_state != last_state: log(f"[{email}] Trang nhập email...", "INFO")
                try:
                    inp = is_element_present(driver, By.CSS_SELECTOR, 'input[name="email"], input[type="email"]')
                    if inp and not inp.get_attribute("value"):
                        set_react_input(driver, inp, email)
                    elif inp and inp.get_attribute("value") == email:
                        btns = driver.find_elements(By.XPATH, "//button[@type='submit' and (contains(., 'Sign up') or contains(., 'Tiếp tục') or contains(., 'Next') or contains(., 'Continue'))]")
                        if btns and btns[0].is_displayed():
                            try_click(driver, btns[0], "Sign up Next")
                except: pass
                
        elif "grok.com" in url:
            current_state = "GROK_SUBSCRIBE"
            if current_state != last_state: log(f"[{email}] Trang Grok Subscribe...", "INFO")
            
            btns = driver.find_elements(By.CSS_SELECTOR, 'button[data-testid="plan-cta-supergrok"]')
            if btns and btns[0].is_displayed():
                try_click(driver, btns[0], "Claim $0.00 offer")
                time.sleep(2)
            
        elif "checkout.stripe.com" in url:
            current_state = "STRIPE_CHECKOUT"
            if current_state != last_state: log(f"[{email}] Trang Stripe Checkout...", "INFO")
            
            try:
                # Force click Crypto using JS equivalent to extension
                driver.execute_script('''
                    var radio = document.getElementById("payment-method-accordion-item-title-crypto");
                    if (radio && !radio.checked) {
                        radio.checked = true;
                        radio.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    var btn = document.querySelector('[data-testid="crypto-accordion-item-button"]');
                    if (btn) btn.click();
                ''')
                
                trial_btns = driver.find_elements(By.CSS_SELECTOR, 'button[data-testid="hosted-payment-submit-button"]')
                if trial_btns and trial_btns[0].is_displayed():
                    try_click(driver, trial_btns[0], "Start trial")
                    time.sleep(3)
            except: pass
            
        elif "crypto.stripe.com" in url:
            current_state = "STRIPE_CRYPTO"
            if current_state != last_state: log(f"[{email}] Trang Crypto Stripe...", "INFO")
            
            okx_btns = driver.find_elements(By.XPATH, "//span[contains(text(), 'OKX Wallet')] | //button[contains(., 'OKX Wallet')]")
            if okx_btns and okx_btns[0].is_displayed():
                try_click(driver, okx_btns[0], "OKX Wallet")
                log(f"[{email}] Đã chọn OKX Wallet! Hoàn thành luồng.", "OK")
                return True 
            
        last_state = current_state
        time.sleep(2) # Lặp liên tục mỗi 2s để tự động phục hồi nếu web chậm

ACTIVE_DRIVERS = []

def register_one_account(index, keep_open=False):
    email = None
    driver = None
    try:
        email = create_random_email()
        if not email: return False

        driver = setup_driver(index, keep_open)
        if keep_open: ACTIVE_DRIVERS.append(driver)
        
        result = worker_loop(driver, email, PASSWORD)
        return result

    except Exception as e:
        log(f"LỖI KHÔNG MONG MUỐN: {e}", "ERR")
        return False
    finally:
        if email: delete_mailbox(email)
        if driver and not keep_open:
            try: driver.quit()
            except: pass

def register_multiple(count, threads, keep_open=False):
    import concurrent.futures
    results = {"ok": 0, "fail": 0}
    
    def worker(i):
        return register_one_account(i, keep_open)

    for batch_start in range(0, count, threads):
        batch_end = min(batch_start + threads, count)
        current_batch_count = batch_end - batch_start
        log(f"--- ĐỢT MỚI: Luồng {batch_start+1} đến {batch_end} ({current_batch_count} tab) ---", "WARN")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=current_batch_count) as executor:
            futures = [executor.submit(worker, i+1) for i in range(batch_start, batch_end)]
            for future in concurrent.futures.as_completed(futures):
                if future.result(): results["ok"] += 1
                else: results["fail"] += 1

    log(f"\n{'='*50}\nKẾT QUẢ: {results['ok']} thành công / {results['fail']} thất bại\n{'='*50}\n", "OK")

if __name__ == "__main__":
    print(f"""
{C.BOLD}{C.INFO}
╔══════════════════════════════════════════════════════╗
║      AUTO ĐĂNG KÝ GROK V2 (STATE MACHINE - MAC)      ║
║   Không dùng sleep tĩnh, tự theo dõi URL và xử lý!   ║
╚══════════════════════════════════════════════════════╝
{C.RST}""")

    try:
        import selenium
    except ImportError:
        os.system(f"{sys.executable} -m pip install selenium requests -q")

    while True:
        try:
            c = input(f"{C.WARN}Nhập tổng số tài khoản muốn chạy (mặc định 3): {C.RST}").strip()
            count = int(c) if c else 3
            t = input(f"{C.WARN}Nhập số tab mở cùng lúc (mặc định 3): {C.RST}").strip()
            threads = int(t) if t else 3
        except ValueError:
            count = 3; threads = 3

        register_multiple(count, threads, keep_open=True)
        
        choice = input(f"\n{C.BOLD}👉 Bấm Enter để TẠO THÊM đợt mới, hoặc 'q' để THOÁT: {C.RST}")
        if choice.strip().lower() == 'q':
            if ACTIVE_DRIVERS:
                for d in ACTIVE_DRIVERS:
                    try: d.quit()
                    except: pass
            print("Tạm biệt!")
            break
