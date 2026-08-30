def restore_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # RESTORE set_react_input
    start_str_react = "def set_react_input(driver, element, value):"
    end_str_react = "def try_click(driver, element, label=\"\"):"
    start_idx_react = content.find(start_str_react)
    end_idx_react = content.find(end_str_react)

    original_react = """def set_react_input(driver, element, value):
    \"\"\"Nhập giá trị vào React input (kích hoạt onChange) an toàn, chống lỗi ElementNotInteractableError.\"\"\"
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        import time
        time.sleep(0.2)
    except:
        pass
        
    js_script = \"\"\"
        let input = arguments[0];
        let val = arguments[1];
        let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        if (nativeInputValueSetter) {
            nativeInputValueSetter.call(input, val);
        } else {
            input.value = val;
        }
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    \"\"\"
    try:
        driver.execute_script(js_script, element, value)
    except Exception as e:
        # Fallback to standard send_keys if JS fails
        try:
            from selenium.webdriver.common.keys import Keys
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.DELETE)
            element.send_keys(value)
        except Exception as e2:
            raise RuntimeError(f"Cannot set input value: {e2}")
            
"""
    content = content[:start_idx_react] + original_react + content[end_idx_react:]

    # RESTORE _step_setup_2fa
    start_str_2fa = "def _step_setup_2fa(driver, stop_event=None):"
    end_str_2fa = "def _extract_totp_secret(driver):"
    start_idx_2fa = content.find(start_str_2fa)
    end_idx_2fa = content.find(end_str_2fa)

    original_2fa = """def _step_setup_2fa(driver, stop_event=None):
    \"\"\"
    Bước 8-12: Setup 2FA (Authenticator App).
    Returns: totp_secret string hoặc raise exception
    \"\"\"
    # === Navigate to Settings ===
    logger.info("[Step8] Đang truy cập Settings...")
    driver.get("https://chatgpt.com/#settings")
    time.sleep(3)
    
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
            driver, By.XPATH,
            '//button[@role="switch"] | //button[contains(text(), "Enable")] | //button[contains(text(), "Bật")]',
            timeout=10
        )
        try_click(driver, mfa_toggle, "MFA Toggle")
        time.sleep(2)
        
        # Kiểm tra xem toggle đã bật chưa, nếu chưa thì click lại (cố chấp click)
        if mfa_toggle.get_attribute("aria-checked") == "false":
            logger.warning("[Step10] Toggle chưa bật, thử click lại...")
            try_click(driver, mfa_toggle, "MFA Toggle Retry")
            time.sleep(2)
    except:
        logger.info("[Step10] Fallback: tìm MFA toggle bằng role switch...")
        try:
            switches = driver.find_elements(By.CSS_SELECTOR, 'button[role="switch"]')
            if switches:
                try_click(driver, switches[0], "MFA Switch fallback")
                time.sleep(2)
            else:
                logger.info("[Step10] Fallback: tìm nút Enable 2FA...")
                btn = driver.find_element(By.XPATH, '//button[contains(text(), "Enable 2FA")]')
                try_click(driver, btn, "Enable 2FA button")
                time.sleep(2)
        except Exception as e:
            _save_screenshot(driver, "no_mfa_toggle")
            raise RuntimeError(f"Không tìm thấy nút bật MFA: {e}")

    _check_stop(stop_event)

    # === Chờ và xử lý màn hình "Continue" nếu có (trước khi hiện QR/Secret) ===
    logger.info("[Step10.5] Kiểm tra UI trung gian 'Continue'...")
    try:
        continue_btn = wait_clickable(
            driver, By.XPATH,
            '//div[@role="dialog"]//button[contains(text(), "Continue") or contains(text(), "Tiếp tục")]',
            timeout=3
        )
        if continue_btn:
            logger.info("[Step10.5] Phát hiện nút Continue trung gian, đang click...")
            try_click(driver, continue_btn, "Intermediate Continue")
            time.sleep(2)
    except:
        pass

    # === Click Trouble scanning ===
    logger.info("[Step11] Click 'Trouble scanning?' để hiện Secret key text...")
    try:
        trouble_btn = wait_clickable(
            driver, By.XPATH,
            '//button[contains(text(), "Trouble scanning")] | //div[contains(text(), "Trouble scanning")] | //button[contains(text(), "scan")]',
            timeout=10
        )
        try_click(driver, trouble_btn, "Trouble Scanning")
        time.sleep(2)
    except Exception as e:
        # Có thể UI mới đã hiện sẵn text, chỉ warning
        logger.warning("[Step11] Không tìm thấy nút Trouble scanning, có thể đã hiện secret")

    _check_stop(stop_event)

    # === Lấy Secret Key ===
    logger.info("[Step12] Đang trích xuất Secret key...")
    totp_secret = _extract_totp_secret(driver)

    # Generate code
    import pyotp
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

    time.sleep(3)
    return totp_secret

"""
    content = content[:start_idx_2fa] + original_2fa + content[end_idx_2fa:]

    with open(filepath, 'w') as f:
        f.write(content)

restore_file('src/bots/gpt_selenium_utils.py')
