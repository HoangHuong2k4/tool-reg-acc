import re
import os

files_to_check = [
    'src/bots/capcut_hotmail.py',
    'src/bots/capcut_domain.py',
    'src/bots/dreamina_hotmail.py',
    'src/bots/higgsfield.py',
    'src/bots/gpt_selenium_utils.py'
]

for file_path in files_to_check:
    if not os.path.exists(file_path):
        continue
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Find the start of class LocalProxyRelay
    match = re.search(r'^class LocalProxyRelay:.*?(?=^[a-zA-Z#])', content, re.MULTILINE | re.DOTALL)
    if not match:
        # Try a different regex or fallback
        match = re.search(r'class LocalProxyRelay:.*?\n\n\n', content, re.DOTALL)
        
    if match:
        replacement = 'from .browser_utils import LocalProxyRelay\n\n\n'
        if file_path == 'src/bots/gpt_selenium_utils.py':
            replacement = 'from .browser_utils import LocalProxyRelay\n\n\n'
        new_content = content[:match.start()] + replacement + content[match.end():]
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Patched {file_path}")
    else:
        # Advanced parser if simple regex fails
        lines = content.split('\n')
        in_class = False
        new_lines = []
        for line in lines:
            if line.startswith('class LocalProxyRelay:'):
                in_class = True
                new_lines.append('from .browser_utils import LocalProxyRelay')
                continue
            
            if in_class:
                if line and not line.startswith(' ') and not line.startswith('\t') and not line.startswith('#'):
                    in_class = False
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print(f"Patched {file_path} using line-by-line")
