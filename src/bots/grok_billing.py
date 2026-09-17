import time
import os
import re
import threading
import queue
import requests
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sqlite3
import undetected_chromedriver as uc

GLOBAL_STOP_EVENT = None
log = print
ACTIVE_DRIVERS = []
DRIVER_LOCK = threading.Lock()
ACCOUNTS_QUEUE = queue.Queue()
CARDS_LIST = []

def save_account(email, password):
    pass


# --- Helpers ---
def get_db_setting(key, default=""):
    try:
        conn = sqlite3.connect("data/app.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row: return row["value"]
    except: pass
    return default

def send_telegram_message(text):
    bot_token = get_db_setting("TELEGRAM_BOT_TOKEN", "8855096263:AAHuhzdQVm_ST0oT-hpCJcHWyuYsTOfsWcw")
    chat_id = get_db_setting("TELEGRAM_CHAT_ID", "7353915691")
    if not bot_token or not chat_id: return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=5)
    except: pass

def load_accounts_to_queue(limit=10):
    count = 0
    with open("data/grok_billing.txt", "r", encoding="utf-8") as f:
        for line in f:
            if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
                break
            if count >= limit:
                break
            line = line.strip()
            if not line or line.startswith("#"): continue
            
            # Hỗ trợ cả định dạng tab, dấu |, hoặc khoảng trắng
            if "\t" in line:
                parts = line.split('\t')
            elif "|" in line:
                parts = line.split('|')
            else:
                parts = line.split()
                
            if len(parts) >= 2:
                email = parts[0].strip()
                password = parts[1].strip()
                ACCOUNTS_QUEUE.put({"email": email, "password": password})
                count += 1
    return count

def setup_driver(index=1, batch_size=3, headless=False):
    cols = min(batch_size, 4)
    window_width = 1920 // cols
    window_height = 1000
    idx = (index - 1) % cols
    x = idx * window_width
    
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=en-US")
    if headless:
        options.add_argument("--headless=new")
    
    with DRIVER_LOCK:
        try:
            driver = uc.Chrome(options=options, use_subprocess=True)
        except Exception as e:
            match = re.search(r'Current browser version is (\d+)', str(e))
            if match:
                v_main = int(match.group(1))
                log(f"[Worker {index}] Lỗi version chrome, thử lại version_main={v_main}", "WARN")
                driver = uc.Chrome(options=options, use_subprocess=True, version_main=v_main)
            else:
                raise e
        try:
            driver.set_window_rect(x=x, y=0, width=window_width, height=window_height)
        except: pass
    ACTIVE_DRIVERS.append(driver)
    return driver

def worker_loop(driver, email, password, index, card_data=None):
    try:
        log(f"[{email}] Đang mở trang đăng nhập...", "INFO")
        driver.get("https://accounts.x.ai/sign-in")
        wait = WebDriverWait(driver, 20)
        
        if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set(): return False
        
        log(f"[{email}] Click Continue with email...", "INFO")
        continue_with_email_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="continue-with-email"]')))
        continue_with_email_btn.click()
        
        if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set(): return False
        
        log(f"[{email}] Nhập email...", "INFO")
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="email"], input[data-testid="email"]')))
        email_input.clear()
        email_input.send_keys(email)
        
        log(f"[{email}] Chờ giải captcha / chờ ô password...", "INFO")
        pass_input = None
        for _ in range(30):
            if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set(): return False
            try:
                pass_input = driver.find_element(By.CSS_SELECTOR, 'input[name="password"], input[data-testid="password"]')
                break
            except:
                try:
                    continue_btn = driver.find_element(By.CSS_SELECTOR, 'button[data-testid="continue"], button[type="submit"]')
                    if continue_btn.is_enabled():
                        continue_btn.click()
                except:
                    pass
            time.sleep(2)
            
        if not pass_input:
            log(f"[{email}] Quá thời gian chờ ô nhập password!", "ERR")
            return False
            
        pass_input.clear()
        pass_input.send_keys(password)
        log(f"[{email}] Đã nhập password, submit...", "INFO")
        
        log(f"[{email}] Đang chờ đăng nhập hoàn tất (giải captcha nếu có)...", "INFO")
        success_login = False
        for _ in range(30):
            if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set(): return False
            if "grok.com" in driver.current_url or "accounts.x.ai/account" in driver.current_url:
                success_login = True
                break
            try:
                continue_btn2 = driver.find_element(By.CSS_SELECTOR, 'button[data-testid="continue"], button[type="submit"]')
                if continue_btn2.is_enabled():
                    continue_btn2.click()
            except:
                pass
            time.sleep(2)
            
        if not success_login:
            log(f"[{email}] Quá thời gian chờ trang Grok!", "ERR")
            return False
        
        if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set(): return False
        
        log(f"[{email}] Đăng nhập thành công! Chuyển hướng sang grok.com...", "OK")
        if "grok.com" not in driver.current_url:
            driver.get("https://grok.com/")
            time.sleep(3) # Đợi load trang và set session
            
        log(f"[{email}] Bắt đầu lấy link billing...", "INFO")
        
        js_code = """
        var callback = arguments[arguments.length - 1];
        fetch('/rest/subscriptions/billing-portal', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => callback(data))
        .catch(error => callback({error: error.message}));
        """
        driver.set_script_timeout(10)
        result = driver.execute_async_script(js_code)
        
        if result and 'url' in result:
            billing_url = result['url']
            log(f"[{email}] Đã lấy được link Billing!", "OK")
            with open("data/grok_billing_result.txt", "a") as f:
                f.write(f"{email} | {password} | {billing_url}\n")
            
            save_account(email, password)

                
            # Xóa account khỏi grok_billing.txt
            with DRIVER_LOCK:
                try:
                    with open("data/grok_billing.txt", "r") as f:
                        lines = f.readlines()
                    with open("data/grok_billing.txt", "w") as f:
                        for line in lines:
                            if email not in line:
                                f.write(line)
                except Exception as ex:
                    log(f"[{email}] Lỗi xóa acc khỏi file: {ex}", "ERR")
                
            masked_email = email[:3] + "***" + email[email.find("@"):] if "@" in email else email[:3] + "***"
            send_telegram_message(f"💳 Lấy link Billing thành công!\nEmail: {masked_email}\nLink: {billing_url}")
            
            log(f"[{email}] Mở link Billing và giữ lại trình duyệt...", "INFO")
            driver.get(billing_url)
            
            if card_data:
                try:
                    # Parse card
                    parts = [p.strip() for p in card_data.split('|')]
                    if len(parts) >= 3:
                        cc_num = parts[0].replace(' ', '')
                        masked = f"{cc_num[:4]} **** **** {cc_num[-4:]}" if len(cc_num) >= 12 else "****"
                        log(f"[{email}] Đang nhập thẻ: {masked}", "INFO")
                        
                        cc_cvc = parts[1]
                        exp = parts[2].split('/')
                        cc_exp = f"{exp[0].strip()}{exp[1].strip()[-2:]}"

                        log(f"[{email}] Tìm nút Thêm/Sửa phương thức thanh toán...", "INFO")
                        clicked = False
                        for _ in range(15):
                            clicked = driver.execute_script("""
                                let btns = document.querySelectorAll('a[href*="/payment-methods"], a[role="button"], button[data-testid="add-payment-method-button"], div[role="button"]');
                                for (let b of btns) {
                                    if ((b.href && b.href.includes('/payment-methods')) || 
                                        (b.hasAttribute('data-testid') && b.getAttribute('data-testid') === 'add-payment-method-button')) {
                                        let ev = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
                                        b.dispatchEvent(ev);
                                        return true;
                                    }
                                    let paths = b.querySelectorAll('path');
                                    for (let path of paths) {
                                        let d = path.getAttribute('d');
                                        if (d && (d.includes('7.875') || d.includes('6.173') || d.includes('3.09'))) {
                                            let ev = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
                                            b.dispatchEvent(ev);
                                            return true;
                                        }
                                    }
                                }
                                return false;
                            """)
                            if clicked: break
                            time.sleep(1)
                            
                        if not clicked:
                            raise Exception("Không tìm thấy nút Thêm/Sửa phương thức thanh toán")
                        
                        log(f"[{email}] Chờ iframe Stripe...", "INFO")
                        iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'iframe[src*="elements-inner-payment"]')))
                        driver.switch_to.frame(iframe)
                        
                        log(f"[{email}] Đang tìm ô nhập thẻ (chờ iframe và tab Card)...", "INFO")
                        num_input = None
                        for _ in range(20):
                            try:
                                card_tabs = driver.find_elements(By.CSS_SELECTOR, 'input[value="card"], button[value="card"], [data-testid*="card"]')
                                for t in card_tabs:
                                    try: driver.execute_script("arguments[0].click();", t)
                                    except: pass
                            except: pass
                            
                            try:
                                inp = driver.find_element(By.CSS_SELECTOR, 'input[name="cardnumber"], input[autocomplete="cc-number"]')
                                if inp.is_displayed():
                                    num_input = inp
                                    break
                            except: pass
                            time.sleep(1)
                            
                        if not num_input:
                            raise Exception("Không tìm thấy ô nhập thẻ (iframe chưa load hoặc không click được tab Card)")
                        for c in cc_num: 
                            num_input.send_keys(c)
                            time.sleep(0.05)
                        
                        exp_input = driver.find_element(By.CSS_SELECTOR, 'input[name="exp-date"]')
                        for c in cc_exp: 
                            exp_input.send_keys(c)
                            time.sleep(0.05)
                        
                        cvc_input = driver.find_element(By.CSS_SELECTOR, 'input[name="cvc"]')
                        for c in cc_cvc: 
                            cvc_input.send_keys(c)
                            time.sleep(0.05)
                        
                        driver.switch_to.default_content()
                        
                        log(f"[{email}] Bấm Lưu thẻ...", "INFO")
                        save_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="confirm"]')))
                        driver.execute_script("arguments[0].click();", save_btn)
                        log(f"[{email}] Đã bấm Lưu thẻ thành công!", "OK")
                    else:
                        log(f"[{email}] Định dạng thẻ không hợp lệ: {card_data}", "ERR")
                except Exception as ex:
                    log(f"[{email}] Lỗi khi nhập thẻ: {str(ex)}", "ERR")
                    
            return True
        else:
            log(f"[{email}] Không lấy được URL: {result}", "ERR")
            return False
            
    except Exception as e:
        log(f"[{email}] Lỗi trong quá trình: {str(e)}", "ERR")
        return False

def process_account_single(index, batch_size=3, headless=False):
    if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set(): return False
    
    try:
        acc = ACCOUNTS_QUEUE.get_nowait()
    except queue.Empty:
        return False
        
    email = acc['email']
    password = acc['password']
    
    log(f"[Worker {index}] Xử lý: {email}", "INFO")
    
    driver = None
    success = False
    card_data = None
    if CARDS_LIST:
        import random
        card_data = random.choice(CARDS_LIST)

    try:
        driver = setup_driver(index=index, batch_size=batch_size, headless=headless)
        success = worker_loop(driver, email, password, index, card_data)
        return success
    except Exception as e:
        log(f"[Worker {index}] Lỗi khởi tạo trình duyệt: {e}", "ERR")
        return False
    finally:
        if driver and not success:
            try:
                driver.quit()
                ACTIVE_DRIVERS.remove(driver)
            except: pass
        ACCOUNTS_QUEUE.task_done()

TOTAL_OK = 0
TOTAL_FAIL = 0

def run(count=1, threads=1, browser_type="uc", headless=False, mail_type="billing", mail_api_source="mixmmo", open_payment=False, language="en-US"):
    global TOTAL_OK, TOTAL_FAIL
    TOTAL_OK = 0
    TOTAL_FAIL = 0
    ACTIVE_DRIVERS.clear()
    
    log("Kết nối log stream Grok (Billing Mode)...", "INFO")
    
    if not os.path.exists("data/grok_billing.txt"):
        with open("data/grok_billing.txt", "w") as f: f.write("")
        
    n = load_accounts_to_queue(count)
    log(f"Đã nạp {n} tài khoản vào hàng đợi.", "OK")
    
    if n == 0:
        log("Hàng đợi trống! Kết thúc.", "WARN")
        return
        
    worker_threads = []
    
    def worker_wrapper(idx):
        while not ACCOUNTS_QUEUE.empty():
            if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
                break
            process_account(idx, batch_size=threads, headless=headless)
            
    for i in range(threads):
        t = threading.Thread(target=worker_wrapper, args=(i+1,), daemon=True)
        worker_threads.append(t)
        t.start()
        time.sleep(1)
        
    for t in worker_threads:
        t.join()
        
    log(f"Xong! {TOTAL_OK} thành công / {TOTAL_FAIL} thất bại", "OK")
