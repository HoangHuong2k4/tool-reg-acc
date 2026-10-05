import re

with open('src/bots/gpt_selenium_utils.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Modify the cols logic
pattern_cols = r'max_cols = 2\s+cols = min\(batch_size, max_cols\)\s+SCREEN_W = 1920; SCREEN_H = 1080\s+window_width = SCREEN_W // max\(1, cols\)'
replacement_cols = '''cols = 2
    SCREEN_W = 1920; SCREEN_H = 1080
    window_width = SCREEN_W // 2'''

if re.search(pattern_cols, content):
    content = re.sub(pattern_cols, replacement_cols, content)
    print("Patched cols logic")
else:
    print("Cols logic pattern not found")

# 2. Add driver.set_window_rect for Chrome
pattern_chrome = r'(driver = uc\.Chrome\(.*?\)\s+)(?=return driver, relay)'
# We have two uc.Chrome calls in try-except block
# Let's just insert it before `return driver, relay`

pattern_return = r'(\s+return driver, relay)'
replacement_return = r'''
    # Force window size and position for Chrome (UC often ignores options on macOS)
    if browser_type.lower() not in ["firefox", "camoufox"]:
        try:
            driver.set_window_rect(x=pos_x, y=pos_y, width=window_width, height=window_height)
        except:
            pass\1'''

if re.search(pattern_return, content):
    content = re.sub(pattern_return, replacement_return, content)
    print("Patched Chrome window rect")
else:
    print("Chrome window rect pattern not found")

with open('src/bots/gpt_selenium_utils.py', 'w', encoding='utf-8') as f:
    f.write(content)
