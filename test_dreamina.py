import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options = webdriver.ChromeOptions()
driver = webdriver.Chrome(options=options)
driver.get("https://dreamina.capcut.com/ai-tool/home?need_login=true")
time.sleep(10)

print("--- ALL SPANS ---")
spans = driver.find_elements(By.TAG_NAME, "span")
for s in spans:
    if "email" in s.text.lower() or "mail" in s.text.lower() or "continue" in s.text.lower() or "sign" in s.text.lower():
         print("SPAN:", s.text.strip(), "Class:", s.get_attribute("class"))

print("--- ALL DIVS (first 50 chars of text) ---")
divs = driver.find_elements(By.TAG_NAME, "div")
for d in divs:
    try:
        t = d.text.lower()
        if t and ("email" in t or "sign up" in t) and len(t) < 50:
             print("DIV:", t.replace('\n', ' '), "Class:", d.get_attribute("class"))
    except:
        pass

driver.quit()
