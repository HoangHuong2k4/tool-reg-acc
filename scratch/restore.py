def restore_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    start_str = "def _step_open_and_click_signup(driver, stop_event=None):"
    end_str = "def _step_enter_email(driver, email, stop_event=None):"
    
    start_idx = content.find(start_str)
    end_idx = content.find(end_str)
    
    replacement = """def _step_open_and_click_signup(driver, stop_event=None):
    \"\"\"Bước 1: Mở chatgpt.com và click nút Sign Up.\"\"\"
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
    time.sleep(3)
    
    # Check nếu bị lọt vào màn hình session ended (nếu có click nhầm sang login)
    try:
        login_btn = driver.find_element(By.CSS_SELECTOR, 'a[data-login-web-auth-control="true"]')
        if login_btn.is_displayed():
            logger.info("[Step1] Phát hiện màn hình Your session has ended, thử click Login để reset...")
            try_click(driver, login_btn, "Reset Session Login")
            time.sleep(3)
    except:
        pass

"""
    
    new_content = content[:start_idx] + replacement + content[end_idx:]
    with open(filepath, 'w') as f:
        f.write(new_content)

restore_file('src/bots/gpt_selenium_utils.py')
