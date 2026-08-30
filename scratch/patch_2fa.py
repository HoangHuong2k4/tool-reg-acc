def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    # Patch set_react_input
    old_js = "let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;"
    new_js = """let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        if (!nativeInputValueSetter) {
            let proto = Object.getPrototypeOf(input);
            while (proto && !nativeInputValueSetter) {
                let desc = Object.getOwnPropertyDescriptor(proto, 'value');
                if (desc && desc.set) nativeInputValueSetter = desc.set;
                proto = Object.getPrototypeOf(proto);
            }
        }"""
    content = content.replace(old_js, new_js)
    
    # Patch settings navigation
    old_settings = """logger.info("[Step8] Đang truy cập Settings...")
    driver.get("https://chatgpt.com/#settings")
    time.sleep(3)"""
    
    new_settings = """logger.info("[Step8] Đang truy cập Settings...")
    # Thử click menu Profile -> Settings trước
    try:
        driver.execute_script("document.querySelector('button[aria-label=\"Profile\"]').click();")
        import time; time.sleep(1)
        driver.execute_script("Array.from(document.querySelectorAll('div, span')).find(e => e.innerText === 'Settings' || e.innerText === 'Cài đặt').click();")
        time.sleep(2)
    except:
        pass
    
    # Kể cả click được hay không, force hash URL để chắc chắn
    driver.execute_script("window.location.hash = 'settings'; window.dispatchEvent(new HashChangeEvent('hashchange'));")
    time.sleep(3)"""
    
    content = content.replace(old_settings, new_settings)
    
    # Patch _step_enter_email (just in case they need to click Log in on chatgpt.com)
    # This was already patched in the previous step for auth.openai.com
    
    with open(filepath, 'w') as f:
        f.write(content)

patch_file('src/bots/gpt_selenium_utils.py')
