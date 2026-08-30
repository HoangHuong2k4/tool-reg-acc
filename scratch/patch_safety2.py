def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    old_code = """logger.info("[Step9] Fallback: tìm tab Security/Safety bằng text...")
        try:
            sec_tab = driver.find_element(
                By.XPATH,
                '//button[contains(text(), "Security")] | //button[contains(text(), "Bảo mật")] | //*[contains(text(), "Safety")] | //*[contains(text(), "An toàn")]'
            )"""
            
    new_code = """logger.info("[Step9] Fallback: tìm tab Security/Safety bằng text...")
        try:
            sec_tab = wait_clickable(
                driver, By.XPATH,
                '//button[contains(text(), "Security")] | //button[contains(text(), "Bảo mật")] | //button[.//text()[contains(., "Safety")]] | //div[text()="Safety"] | //div[text()="An toàn"]',
                timeout=5
            )"""
            
    content = content.replace(old_code, new_code)
    
    with open(filepath, 'w') as f:
        f.write(content)

patch_file('src/bots/gpt_selenium_utils.py')
