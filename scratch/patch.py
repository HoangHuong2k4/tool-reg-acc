def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    start_str = "def _step_open_and_click_signup(driver, stop_event=None):"
    end_str = "def _step_enter_email(driver, email, stop_event=None):"
    
    start_idx = content.find(start_str)
    end_idx = content.find(end_str)
    
    replacement = """def _step_open_and_click_signup(driver, stop_event=None):
    \"\"\"Bước 1: Mở auth.openai.com/create-account.
    Xử lý lỗi 'Your session has ended' khi chạy ẩn danh.\"\"\"
    logger.info("[Step1] Mở trang đăng ký auth.openai.com...")
    driver.get("https://auth.openai.com/create-account")
    _sentinel_delay(4, "Trang auth load")
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

    # Kiểm tra xem có bị lỗi "Your session has ended" không
    try:
        login_btn = driver.find_element(By.CSS_SELECTOR, 'a[data-login-web-auth-control="true"], a[href*="login_with"]')
        if login_btn.is_displayed():
            logger.info("[Step1] Bị lỗi 'Your session has ended', đang bấm Login để reset phiên...")
            try_click(driver, login_btn, "Reset Session Login")
            time.sleep(4)
            _check_stop(stop_event)
            logger.info("[Step1] Truy cập lại trang đăng ký...")
            driver.get("https://auth.openai.com/create-account")
            time.sleep(5)
            _check_stop(stop_event)
    except:
        pass

"""
    
    new_content = content[:start_idx] + replacement + content[end_idx:]
    with open(filepath, 'w') as f:
        f.write(new_content)

patch_file('src/bots/gpt_selenium_utils.py')
