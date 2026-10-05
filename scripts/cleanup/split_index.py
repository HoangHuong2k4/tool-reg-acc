import os

index_path = "/Users/huong/TaiNguyen/capcut-regaccc/ui/templates/index.html"
components_dir = "/Users/huong/TaiNguyen/capcut-regaccc/ui/templates/components"

if not os.path.exists(components_dir):
    os.makedirs(components_dir)

with open(index_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

def find_line(lines, search_str, start_idx=0):
    for i in range(start_idx, len(lines)):
        if search_str in lines[i]:
            return i
    return -1

# Tab boundaries
tab_capcut = find_line(lines, 'id="tab-capcut"')
tab_higgsfield = find_line(lines, 'id="tab-higgsfield"')
tab_gpt = find_line(lines, 'id="tab-gpt"')
tab_gpm = find_line(lines, 'id="tab-gpm"')
tab_dreamina = find_line(lines, 'id="tab-dreamina"')
tab_grok = find_line(lines, 'id="tab-grok"')
tab_settings = find_line(lines, 'id="tab-settings"')
toast_container = find_line(lines, 'id="toast-container"')

# Extract parts
header_and_nav = lines[:tab_capcut]

capcut_content = lines[tab_capcut:tab_higgsfield]
higgsfield_content = lines[tab_higgsfield:tab_gpt]
gpt_content = lines[tab_gpt:tab_gpm]
gpm_content = lines[tab_gpm:tab_dreamina]
dreamina_content = lines[tab_dreamina:tab_grok]
grok_content = lines[tab_grok:tab_settings]
settings_content = lines[tab_settings:toast_container]

footer_and_modals = lines[toast_container:]

# Write components
def write_comp(filename, content_lines):
    with open(os.path.join(components_dir, filename), "w", encoding="utf-8") as f:
        f.writelines(content_lines)

write_comp("navbar.html", header_and_nav) # Wait, navbar has <html><head>... maybe just keep it in index.html, or split further.
write_comp("tab_capcut.html", capcut_content)
write_comp("tab_higgsfield.html", higgsfield_content)
write_comp("tab_gpt.html", gpt_content)
write_comp("tab_gpm.html", gpm_content)
write_comp("tab_dreamina.html", dreamina_content)
write_comp("tab_grok.html", grok_content)
write_comp("tab_settings.html", settings_content)

# We can also extract modals and footer.
# Actually, the header and navbar should probably just stay in index.html, and we just replace the tab contents.

new_index = []
new_index.extend(header_and_nav)
new_index.append("  {% include 'components/tab_capcut.html' %}\n")
new_index.append("  {% include 'components/tab_higgsfield.html' %}\n")
new_index.append("  {% include 'components/tab_gpt.html' %}\n")
new_index.append("  {% include 'components/tab_gpm.html' %}\n")
new_index.append("  {% include 'components/tab_dreamina.html' %}\n")
new_index.append("  {% include 'components/tab_grok.html' %}\n")
new_index.append("  {% include 'components/tab_settings.html' %}\n")
new_index.extend(footer_and_modals)

with open(index_path, "w", encoding="utf-8") as f:
    f.writelines(new_index)

print("Split successful!")
