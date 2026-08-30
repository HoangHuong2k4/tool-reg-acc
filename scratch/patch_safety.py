def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    old_code = """logger.info("[Step9] Fallback: tìm tab Security bằng text...")
        try:
            sec_tab = driver.find_element(
                By.XPATH,
                '//button[contains(text(), "Security")] | //button[contains(text(), "Bảo mật")]'
            )
            try_click(driver, sec_tab, "Security Tab (text fallback)")
        except:
            raise RuntimeError("Không tìm thấy tab Security")"""
            
    new_code = """logger.info("[Step9] Fallback: tìm tab Security/Safety bằng text...")
        try:
            sec_tab = driver.find_element(
                By.XPATH,
                '//button[contains(text(), "Security")] | //button[contains(text(), "Bảo mật")] | //*[contains(text(), "Safety")] | //*[contains(text(), "An toàn")]'
            )
            try_click(driver, sec_tab, "Safety/Security Tab (text fallback)")
        except:
            raise RuntimeError("Không tìm thấy tab Security/Safety")"""
            
    content = content.replace(old_code, new_code)
    
    with open(filepath, 'w') as f:
        f.write(content)

patch_file('src/bots/gpt_selenium_utils.py')
