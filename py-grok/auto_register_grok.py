#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import re
import sys
import os
import requests
import random
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
            
            # Theo MAIL_API_GUIDE.md, tìm OTP có dạng xAI code (ví dụ IC7-P42)
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

    # Bọc lock ở đây để tránh lỗi [Errno 2] No such file or directory của undetected_chromedriver
    with DRIVER_LOCK:
        driver = uc.Chrome(options=options, use_subprocess=True)
        
    # Ép buộc kích thước và vị trí qua lệnh WebDriver (chắc ăn 100% trên MacOS)
    try:
        driver.set_window_rect(x=x, y=y, width=window_width, height=window_height)
    except Exception:
        pass
        
    return driver

def wait_for_element(driver, by, value, timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        try:
            elements = driver.find_elements(by, value)
            if elements:
                return elements[0]
        except Exception:
            try:
                handles = driver.window_handles
                if handles:
                    driver.switch_to.window(handles[-1])
            except:
                pass
        time.sleep(1)
    raise Exception(f"Timeout waiting for {value}")

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
            log(f"Không click được {label}: {e}", "WARN")
            return False

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



def save_account(email, password):
    line = f"{email}\t{password}"
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    log(f"Đã lưu tài khoản → {OUTPUT_FILE}", "OK")

# ────────────────────────────────────────────────────────────────────────
# CÁC BƯỚC ĐĂNG KÝ BÊN DƯỚI CẦN CẬP NHẬT LẠI SELECTOR CSS CHO ĐÚNG FORM GROK
# ────────────────────────────────────────────────────────────────────────

def step1_enter_email(driver, email):
    from selenium.webdriver.common.by import By
    log("Bước 1: Bấm Sign up with email và nhập email...", "INFO")
    
    try:
        signup_email_btn = wait_for_element(driver, By.XPATH, "//button[contains(., 'Sign up with email')]", timeout=45)
        try_click(driver, signup_email_btn, "Sign up with email")
    except Exception as e:
        log(f"Không tìm thấy nút Sign up with email: {e}", "WARN")

    email_input = wait_for_element(driver, By.CSS_SELECTOR, 'input[name="email"], input[type="email"]', timeout=30)
    set_react_input(driver, email_input, email)
    
    next_btns = driver.find_elements(By.XPATH, "//button[@type='submit' and contains(., 'Sign up')] | //button[contains(., 'Tiếp tục') or contains(., 'Next') or contains(., 'Continue')]")
    if next_btns:
        for btn in next_btns:
            if btn.is_displayed():
                try_click(driver, btn, "Sign up Button")
                break
    time.sleep(2)

def step2_enter_otp(driver, email):
    from selenium.webdriver.common.by import By
    log("Bước 2: Chờ và nhập OTP...", "INFO")
    
    otp = wait_for_otp(email, timeout=120, interval=4)
    if not otp: return False

    try:
        otp_input = wait_for_element(driver, By.CSS_SELECTOR, 'input[name="code"]', timeout=10)
        set_react_input(driver, otp_input, otp)
        
        # Bấm Confirm email
        verify_btns = driver.find_elements(By.XPATH, "//button[@type='submit' and contains(., 'Confirm email')] | //button[contains(., 'Xác nhận') or contains(., 'Verify')]")
        if verify_btns:
            try_click(driver, verify_btns[0], "Confirm email Button")
        time.sleep(3)
        return True
    except Exception as e:
        log(f"Lỗi nhập OTP: {e}", "ERR")
        return False

def step3_complete_signup(driver, password):
    from selenium.webdriver.common.by import By
    import random
    import string
    
    log("Bước 3: Nhập Tên và Mật khẩu...", "INFO")
    try:
        first_name = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=6))
        last_name = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=6))
        
        # Nhập First name
        fname_input = wait_for_element(driver, By.CSS_SELECTOR, 'input[name="givenName"]', timeout=20)
        set_react_input(driver, fname_input, first_name)
        
        # Nhập Last name
        lname_input = driver.find_element(By.CSS_SELECTOR, 'input[name="familyName"]')
        set_react_input(driver, lname_input, last_name)
        
        # Nhập password
        pwd_input = driver.find_element(By.CSS_SELECTOR, 'input[name="password"]')
        set_react_input(driver, pwd_input, password)
        
        # Bấm Complete sign up
        complete_btns = driver.find_elements(By.XPATH, "//button[@type='submit' and contains(., 'Complete sign up')] | //button[contains(., 'Hoàn tất') or contains(., 'Complete')]")
        if complete_btns:
            try_click(driver, complete_btns[0], "Complete sign up Button")
        time.sleep(3)
        return True
    except Exception as e:
        log(f"Lỗi nhập thông tin (Bước 3): {e}", "ERR")
        return False

def step4_subscribe_grok(driver):
    from selenium.webdriver.common.by import By
    log("Bước 4: Mở tab mới để Subscribe Grok...", "INFO")
    try:
        # Mở tab mới
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        
        # Chuyển trang
        driver.get("https://grok.com/?q=&reasoningMode=none&voice=false#subscribe")
        log("Đợi tải trang gói cước...", "INFO")
        time.sleep(10)
        
        # Bấm Claim $0.00 offer
        claim_btns = driver.find_elements(By.CSS_SELECTOR, 'button[data-testid="plan-cta-supergrok"]')
        if claim_btns:
            try_click(driver, claim_btns[0], "Claim $0.00 offer")
            time.sleep(7)
        else:
            log("Không tìm thấy nút Claim offer!", "WARN")
            
        # Bấm Crypto Payment Method
        log("Chọn phương thức thanh toán Crypto...", "INFO")
        try:
            # Cuộn trang đến phần chọn payment method
            driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(1)
            
            # Cố gắng click bằng nhiều cách để đảm bảo React nhận diện
            driver.execute_script('''
                // Cách 1: Click vào radio button
                var radio = document.getElementById("payment-method-accordion-item-title-crypto");
                if (radio) {
                    radio.checked = true;
                    radio.dispatchEvent(new Event('change', { bubbles: true }));
                    radio.dispatchEvent(new Event('input', { bubbles: true }));
                    radio.click();
                }
                
                // Cách 2: Click vào thẻ button bọc ngoài
                var btn = document.querySelector('[data-testid="crypto-accordion-item-button"]');
                if (btn) btn.click();
            ''')
            log("Đã thử force-click nút Crypto qua JS.", "INFO")
            time.sleep(2)
        except Exception as e:
            log(f"Lỗi khi chọn Crypto: {e}", "WARN")
        
        # Bấm Start trial / Subscribe
        try:
            trial_btn = wait_for_element(driver, By.CSS_SELECTOR, 'button[data-testid="hosted-payment-submit-button"]', timeout=10)
            try_click(driver, trial_btn, "Start trial")
            log("Đợi chuyển hướng sang cổng thanh toán Crypto (tối đa 30s)...", "INFO")
        except Exception as e:
            log(f"Không tìm thấy nút Start trial: {e}", "WARN")
        
        # Chọn OKX Wallet
        try:
            okx_btn = wait_for_element(driver, By.XPATH, "//span[contains(text(), 'OKX Wallet')] | //button[contains(., 'OKX Wallet')] | //*[contains(text(), 'OKX Wallet')]", timeout=30)
            try_click(driver, okx_btn, "OKX Wallet")
            log("Đã chọn OKX Wallet, giữ nguyên tab.", "OK")
        except:
            log("Không tìm thấy nút OKX Wallet trong thời gian quy định.", "WARN")
            
        time.sleep(2)
        return True
    except Exception as e:
        log(f"Lỗi ở bước Subscribe: {e}", "ERR")
        return False

ACTIVE_DRIVERS = []

def register_one_account(index, keep_open=False):
    email = None
    driver = None
    password = PASSWORD

    try:
        email = create_random_email()
        if not email:
            log(f"Acc #{index}: Hết email khả dụng!", "ERR")
            return False

        driver = setup_driver(index, keep_open)
        if keep_open:
            ACTIVE_DRIVERS.append(driver)
        log(f"[{email}] Bắt đầu mở trình duyệt...", "INFO")
        
        # Fix lỗi uc mở tab trắng nhưng không get URL, và catch lỗi văng web view
        for _ in range(3):
            try:
                if driver.window_handles:
                    driver.switch_to.window(driver.window_handles[-1])
                driver.get(GROK_URL)
                time.sleep(3)
                url = driver.current_url
                if "x.ai" in url or "sign-up" in url:
                    break
                log("Trình duyệt kẹt ở New Tab, thử tải lại link...", "WARN")
            except Exception as e:
                log("Mất kết nối với trình duyệt do Turnstile tải lại, thử lại...", "WARN")
                time.sleep(2)
            
        log(f"Đã mở {GROK_URL}, đợi trang tải và xử lý Turnstile (chờ 30s)...", "INFO")
        time.sleep(30)

        # ─── THỰC HIỆN CÁC BƯỚC ĐĂNG KÝ (BẠN CẦN CHỈNH SỬA LẠI CSS SELECTOR Ở TRÊN ĐỂ CHẠY ĐÚNG) ───
        step1_enter_email(driver, email)
        if not step2_enter_otp(driver, email):
            return False
        if not step3_complete_signup(driver, password):
            return False

        # Chờ trang web tự động chuyển hướng về /account để xác nhận đăng ký xong
        log("Đợi hệ thống xử lý và chuyển về trang quản lý tài khoản...", "INFO")
        start_wait = time.time()
        while time.time() - start_wait < 30:
            if "/account" in driver.current_url:
                break
            time.sleep(1)
        
        if "/account" not in driver.current_url:
            log("Không thấy chuyển về trang /account, tiếp tục chạy nhưng có thể lỗi...", "WARN")
        else:
            log("Đã vào trang /account thành công!", "OK")
            time.sleep(2)

        # Sau khi hoàn tất (xác nhận thành công), lưu tài khoản
        save_account(email, password)

        log(f"ĐĂNG KÝ THÀNH CÔNG! {email} | {password}", "OK")
        
        # Bước 4: Mua gói và chọn OKX
        step4_subscribe_grok(driver)
        
        return True

    except Exception as e:
        log(f"LỖI KHÔNG MONG MUỐN: {e}", "ERR")
        return False
    finally:
        if email: delete_mailbox(email)
        if driver and not keep_open:
            try:
                driver.quit()
                log("Đã đóng trình duyệt.", "INFO")
            except: pass

def register_multiple(count, threads, keep_open=False):
    import concurrent.futures
    results = {"ok": 0, "fail": 0}
    
    def worker(i):
        log(f"BẮT ĐẦU LUỒNG {i}/{count}", "INFO")
        return register_one_account(i, keep_open)

    for batch_start in range(0, count, threads):
        batch_end = min(batch_start + threads, count)
        current_batch_count = batch_end - batch_start
        log(f"--- BẮT ĐẦU ĐỢT: Chạy luồng {batch_start+1} đến {batch_end} ({current_batch_count} tab) ---", "WARN")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=current_batch_count) as executor:
            futures = [executor.submit(worker, i+1) for i in range(batch_start, batch_end)]
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
║        AUTO ĐĂNG KÝ TÀI KHOẢN GROK (TERMINAL)        ║
║                 Tích hợp: Lấy OTP xAI                ║
╚══════════════════════════════════════════════════════╝
{C.RST}""")

    try:
        import selenium
    except ImportError:
        print("Đang cài đặt selenium...")
        os.system(f"{sys.executable} -m pip install selenium requests -q")

    while True:
        try:
            count_input = input(f"{C.WARN}Nhập tổng số tài khoản muốn chạy (mặc định 3): {C.RST}").strip()
            count = int(count_input) if count_input else 3
            
            threads_input = input(f"{C.WARN}Nhập số tab mở cùng lúc (mặc định 3): {C.RST}").strip()
            threads = int(threads_input) if threads_input else 3
        except ValueError:
            print(f"{C.ERR}Số lượng phải là số nguyên! Đang dùng mặc định 3 tài khoản, 3 luồng.{C.RST}")
            count = 3
            threads = 3

        log(f"Sẽ tạo {count} tài khoản, mở {threads} tab cùng lúc.", "INFO")
        log(f"Lưu vào {OUTPUT_FILE} và GIỮ TRÌNH DUYỆT MỞ.", "INFO")
        print()

        register_multiple(count, threads, keep_open=True)
        
        print(f"\n{C.OK}✅ ĐÃ CHẠY XONG LÔ NÀY!{C.RST}")
        print(f"{C.WARN}⚠️ Các tab tạo tài khoản vẫn đang mở! Hãy tự tắt thủ công nếu cần.{C.RST}")
        
        choice = input(f"{C.BOLD}👉 Bấm Enter để TẠO THÊM đợt mới, hoặc gõ 'q' rồi Enter để THOÁT: {C.RST}")
        if choice.strip().lower() == 'q':
            if ACTIVE_DRIVERS:
                log("Đang đóng toàn bộ các tab trình duyệt...", "INFO")
                for d in ACTIVE_DRIVERS:
                    try: d.quit()
                    except: pass
            print("Tạm biệt!")
            break
