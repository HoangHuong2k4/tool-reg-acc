import re

with open("src/bots/capcut_hotmail.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add step_get_payment_link
step_link_code = """
def step_get_payment_link(driver, email):
    try:
        import json
        log("Đang chờ 5s cho my-edit load...", "INFO")
        time.sleep(5)
        
        # Đóng popup
        try:
            close_btns = driver.find_elements(By.XPATH, "//div[contains(@class, 'close')] | //button[contains(@class, 'close')] | //*[name()='svg'][contains(@class, 'close')] | //img[contains(@class, 'close')]")
            for btn in close_btns:
                try:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
                except: pass
        except: pass
        
        time.sleep(2)
        
        # Bấm Nâng cấp
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            wait = WebDriverWait(driver, 10)
            pro_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'tham gia pro') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'nâng cấp') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'join pro') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'upgrade') or @data-testid='upgrade-btn']")))
            driver.execute_script("arguments[0].click();", pro_btn)
            time.sleep(3)
        except Exception as e:
            log("Không tự bấm được nút Pro", "WARN")
            
        # Bấm Mua
        try:
            buy_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'mua') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'get') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'purchase') or contains(@class, 'pay-btn')]")))
            driver.execute_script("arguments[0].click();", buy_btn)
        except: pass
        
        log("Đang dò tìm link PipoPay trong 60s...", "INFO")
        payment_url = None
        for _ in range(60):
            for handle in driver.window_handles:
                driver.switch_to.window(handle)
                if "pipopay.com" in driver.current_url or "buy.stripe.com" in driver.current_url:
                    payment_url = driver.current_url
                    break
            if payment_url: break
            
            try:
                logs = driver.get_log("performance")
                for entry in logs:
                    try:
                        log_json = json.loads(entry["message"])["message"]
                        if log_json.get("method") == "Network.responseReceived":
                            resp = log_json["params"]["response"]
                            url = resp.get("url", "")
                            if "init_trade" in url or "batch_get" in url:
                                request_id = log_json["params"]["requestId"]
                                body_info = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                                body = json.loads(body_info["body"])
                                cashier_url = body.get("data", {}).get("pipo_aggregate_pay_info", {}).get("cashier_url")
                                if not cashier_url:
                                    cashier_url = json.dumps(body)
                                if cashier_url and ("pipopay" in cashier_url or "http" in cashier_url):
                                    payment_url = cashier_url
                                    break
                    except: continue
            except: pass
            
            if payment_url: break
            time.sleep(1)
            
        if payment_url:
            log(f"Lấy link thành công: {payment_url}", "OK")
            import os
            os.makedirs("data", exist_ok=True)
            with open("data/success_links.txt", "a", encoding="utf-8") as f:
                f.write(f"{email} | {payment_url}\n")
            return payment_url
        else:
            log("Không lấy được link thanh toán", "ERR")
            return None
    except Exception as e:
        log(f"Lỗi lấy link: {e}", "ERR")

"""
if "def step_get_payment_link" not in content:
    content = content.replace("def register_one_account", step_link_code + "\ndef register_one_account")

# 2. Update register_one_account signature
content = content.replace('def register_one_account(index, join_link=None, keep_open=False, batch_size=3, predefined_proxy=None, headless=False, browser_type="chrome"):', 'def register_one_account(index, join_link=None, keep_open=False, batch_size=3, predefined_proxy=None, headless=False, browser_type="chrome", get_link=False):')

# 3. Add call to step_get_payment_link in register_one_account
target_after_close = """            step_skip_role_survey(driver, timeout=10)
            step_close_whats_new(driver, timeout=15)"""
if "if get_link:" not in content and target_after_close in content:
    content = content.replace(target_after_close, target_after_close + """
            if get_link:
                step_get_payment_link(driver, email)""")

# 4. Update register_multiple signature
content = content.replace('def register_multiple(count, threads, join_link, keep_open=False):', 'def register_multiple(count, threads, join_link, keep_open=False, get_link=False):')
content = content.replace('res = register_one_account(i, join_link, keep_open, batch_size=threads, predefined_proxy=shared_proxy)', 'res = register_one_account(i, join_link, keep_open, batch_size=threads, predefined_proxy=shared_proxy, get_link=get_link)')

# 5. Update menu
old_menu = """        print("1. Chỉ tạo tài khoản ngẫu nhiên (Lưu vào file txt - GIỮ TAB MỞ ĐỂ TỰ THANH TOÁN)")
        print("2. Tạo tài khoản + Auto Join Team + Gửi lên Google Sheet")
        choice_func = input(f"👉 Chọn 1 hoặc 2: ").strip()

        if choice_func not in ["1", "2"]:
            print(f"{C.ERR}Lựa chọn không hợp lệ! Vui lòng nhập 1 hoặc 2.{C.RST}")"""

new_menu = """        print("1. Chỉ tạo tài khoản ngẫu nhiên (Lưu vào file txt - GIỮ TAB MỞ ĐỂ TỰ THANH TOÁN)")
        print("2. Tạo tài khoản + Auto Join Team + Gửi lên Google Sheet")
        print("3. Tự động Tạo tài khoản + Đóng Popup + Lấy Link PipoPay (Treo máy)")
        choice_func = input(f"👉 Chọn 1, 2 hoặc 3: ").strip()

        if choice_func not in ["1", "2", "3"]:
            print(f"{C.ERR}Lựa chọn không hợp lệ! Vui lòng nhập 1, 2 hoặc 3.{C.RST}")"""
if old_menu in content:
    content = content.replace(old_menu, new_menu)

# 6. Update choice logic
old_logic = """        try:
            if choice_func == "2":"""
new_logic = """        get_link = False
        try:
            if choice_func == "3":
                get_link = True
                keep_open = False
            elif choice_func == "2":"""
if old_logic in content:
    content = content.replace(old_logic, new_logic)

# 7. Update register_multiple calls
content = content.replace("register_multiple(actual_count, threads, join_link, keep_open)", "register_multiple(actual_count, threads, join_link, keep_open, get_link)")

# 8. Update batch loop blocker
old_blocker = """                if not HOTMAIL_QUEUE.empty():
                    print(f"\\n{C.WARN}⚠️ Đã xong đợt {batch_count_idx}. Các tab vẫn đang mở để bạn tự thanh toán.{C.RST}")
                    input(f"{C.BOLD}👉 Bấm Enter để ĐÓNG các tab hiện tại và CHẠY ĐỢT TIẾP THEO: {C.RST}")
                    
                    if ACTIVE_DRIVERS:
                        log("Đang đóng các tab cũ...", "INFO")
                        for d in ACTIVE_DRIVERS:
                            try: d.quit()
                            except: pass
                        ACTIVE_DRIVERS.clear()"""

new_blocker = """                if not HOTMAIL_QUEUE.empty():
                    if choice_func == "1":
                        print(f"\\n{C.WARN}⚠️ Đã xong đợt {batch_count_idx}. Các tab vẫn đang mở để bạn tự thanh toán.{C.RST}")
                        input(f"{C.BOLD}👉 Bấm Enter để ĐÓNG các tab hiện tại và CHẠY ĐỢT TIẾP THEO: {C.RST}")
                    
                    if ACTIVE_DRIVERS:
                        log("Đang dọn dẹp các tab cũ trước khi qua đợt mới...", "INFO")
                        for d in ACTIVE_DRIVERS:
                            try: d.quit()
                            except: pass
                        ACTIVE_DRIVERS.clear()"""
if old_blocker in content:
    content = content.replace(old_blocker, new_blocker)

with open("src/bots/capcut_hotmail.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied successfully.")
