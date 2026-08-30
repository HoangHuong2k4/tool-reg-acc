def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    start_str = "def set_react_input(driver, element, value):"
    end_str = "def try_click(driver, element, label=\"\"):"
    
    start_idx = content.find(start_str)
    end_idx = content.find(end_str)
    
    new_func = """def set_react_input(driver, element, value):
    \"\"\"Nhập giá trị vào React input an toàn, kể cả khi ẩn (not reachable by keyboard).\"\"\"
    try:
        driver.execute_script(\"\"\"
            let el = arguments[0];
            let val = arguments[1];
            
            // Xóa focus, scroll
            try { el.scrollIntoView({block: 'center'}); } catch(e) {}
            
            // Cách 1: Native setter (hoạt động tốt với React 16+)
            let setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            if (!setter) {
                let proto = Object.getPrototypeOf(el);
                while (proto && !setter) {
                    setter = Object.getOwnPropertyDescriptor(proto, 'value');
                    proto = Object.getPrototypeOf(proto);
                }
            }
            if (setter && setter.set) {
                setter.set.call(el, val);
            } else {
                el.value = val;
            }
            
            // Dispatch events để React nhận diện thay đổi
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            
            // Cách 2: Nếu React 15 trở xuống, dispatch keyCode
            el.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Enter' }));
        \"\"\", element, value)
    except Exception as e:
        # Fallback: dùng send_keys qua JS thuần túy (không dùng webdriver.send_keys vì hay bị not interactable)
        try:
            driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", element, value)
        except Exception as e2:
            raise RuntimeError(f"Cannot set react input value: {e2}")

"""
    new_content = content[:start_idx] + new_func + content[end_idx:]
    with open(filepath, 'w') as f:
        f.write(new_content)

patch_file('src/bots/gpt_selenium_utils.py')
