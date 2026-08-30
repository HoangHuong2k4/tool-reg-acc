def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    old_str = "driver.execute_script(\"document.querySelector('button[aria-label=\"Profile\"]').click();\")"
    
    # Actually wait, maybe I wrote "document.querySelector('button[aria-label="Profile"]').click();"
    # Let me just replace by line number!
