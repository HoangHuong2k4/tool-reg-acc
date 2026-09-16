import time
import os
import re
import threading
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import undetected_chromedriver as uc

def get_driver():
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=en-US")
    # Không chạy headless để dễ debug test
    options.add_experimental_option("detach", True)
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
        return driver
    except Exception as e:
        match = re.search(r'Current browser version is (\d+)', str(e))
        if match:
            v_main = int(match.group(1))
            print(f"[*] Lỗi version chrome, thử lại với version_main={v_main}")
            return uc.Chrome(options=options, use_subprocess=True, version_main=v_main)
        else:
            raise e

def login_and_get_billing(email, password):
    driver = get_driver()
    try:
        print(f"\n[{email}] Mở trang đăng nhập...")
        driver.get("https://accounts.x.ai/sign-in")
        
        # Nhập Email
        wait = WebDriverWait(driver, 20)
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        email_input.send_keys(email)
        print(f"[{email}] Đã nhập email, click Continue...")
        
        # Click Continue-with-email
        continue_btn = driver.find_element(By.CSS_SELECTOR, '[data-testid="continue-with-email"]')
        continue_btn.click()
        
        # Nhập Password
        print(f"[{email}] Chờ nhập password...")
        pass_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
        pass_input.send_keys(password)
        print(f"[{email}] Đã nhập password, submit...")
        
        pass_input.submit()
        
        # Chờ đăng nhập xong (đến trang grok.com)
        print(f"[{email}] Đang chờ đăng nhập hoàn tất...")
        wait.until(EC.url_contains("grok.com"))
        print(f"[{email}] Đăng nhập thành công! Đang lấy link billing qua API...")
        
        # Lấy link API
        js_code = """
        var callback = arguments[arguments.length - 1];
        fetch('/rest/subscriptions/billing-portal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
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
            print(f"[{email}] LẤY LINK THÀNH CÔNG: {billing_url}")
            
            with open("data/grok_billing_result.txt", "a") as f:
                f.write(f"{email}|{password}|{billing_url}\n")
                
            driver.execute_script(f"window.open('{billing_url}', '_blank');")
            print(f"[{email}] Đã mở tab chứa link thanh toán!")
        else:
            print(f"[{email}] Lỗi khi lấy API: {result}")
            
    except Exception as e:
        print(f"[{email}] Gặp lỗi trong quá trình chạy: {e}")
    
    print(f"[{email}] XONG. Giữ trình duyệt để bạn kiểm tra.")

if __name__ == "__main__":
    if not os.path.exists("data/grok_billing.txt"):
        print("Vui lòng tạo file data/grok_billing.txt và nhập danh sách (mỗi dòng: email\\tpassword)")
        exit()
        
    with open("data/grok_billing.txt", "r") as f:
        lines = f.read().splitlines()
        
    for line in lines:
        parts = line.split('\t')
        if len(parts) >= 2:
            email = parts[0].strip()
            password = parts[1].strip()
            login_and_get_billing(email, password)
        else:
            print(f"Dòng không đúng định dạng: {line}")
