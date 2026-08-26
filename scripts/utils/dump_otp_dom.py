import time
from selenium import webdriver
from selenium.webdriver.common.by import By

options = webdriver.ChromeOptions()
driver = webdriver.Chrome(options=options)
driver.get("https://dreamina.capcut.com/ai-tool/home?need_login=true")

print("=====================================================")
print("Vui lòng tự thao tác trên trình duyệt đang mở:")
print("1. Click Continue with email")
print("2. Click Sign up")
print("3. Nhập 1 email (có thể gõ bừa email) và password")
print("4. Nhấn Continue để tới màn hình nhập OTP")
print("=====================================================")
input("SAU KHI ĐÃ TỚI MÀN HÌNH OTP, HÃY NHẤN ENTER TẠI ĐÂY...")

try:
    print("\nĐang lấy HTML của form OTP...")
    inputs = driver.find_elements(By.TAG_NAME, "input")
    print(f"Tìm thấy {len(inputs)} thẻ input trên trang:")
    for idx, inp in enumerate(inputs):
        print(f"\n--- Input {idx+1} ---")
        print("Outer HTML:", inp.get_attribute("outerHTML"))
        print("is_displayed:", inp.is_displayed())
        
    print("\nĐang tìm các thẻ liên quan tới OTP (verification/code)...")
    code_els = driver.find_elements(By.XPATH, "//*[contains(@class, 'code') or contains(@class, 'verification') or contains(@class, 'otp')]")
    print(f"Tìm thấy {len(code_els)} thẻ class chứa code/verification/otp:")
    for el in code_els:
        print(el.tag_name, el.get_attribute("class"))
except Exception as e:
    print("Lỗi:", e)

driver.quit()
