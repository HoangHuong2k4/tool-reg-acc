import os
import re

app_js_path = "/Users/huong/TaiNguyen/capcut-regaccc/ui/static/js/app.js"
modules_dir = "/Users/huong/TaiNguyen/capcut-regaccc/ui/static/js/modules"

if not os.path.exists(modules_dir):
    os.makedirs(modules_dir)

with open(app_js_path, "r", encoding="utf-8") as f:
    content = f.read()

# The boundaries
sections = [
    ("core", r"// ==== COMMON ===="),
    ("capcut", r"// ==== CAPCUT ===="),
    ("mailtemp", r"// ==== MAILTEMP OTP MANAGER ===="),
    ("higgsfield", r"// ==== HIGGSFIELD ===="),
    ("gpt", r"// ==== GPT ===="),
    ("gpm", r"// ==== GPM MODE ===="),
    ("dreamina", r"// ======================= DREAMINA ======================="),
    ("grok", r"// ===================== GROK ====================="),
]

# Find indices
indices = []
for name, marker in sections:
    match = re.search(re.escape(marker), content)
    if match:
        indices.append((name, match.start()))

indices.sort(key=lambda x: x[1])

# Extract chunks
chunks = {}
for i in range(len(indices)):
    name, start = indices[i]
    end = indices[i+1][1] if i + 1 < len(indices) else len(content)
    chunks[name] = content[start:end]

# Write chunks
for name, chunk in chunks.items():
    with open(os.path.join(modules_dir, f"{name}.js"), "w", encoding="utf-8") as f:
        f.write(chunk)

print("Split JS successful!")
