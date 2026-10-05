import os
import re

utils_code = '''
def get_settings_from_db():
    import sqlite3
    import os
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database.db"))
    settings = {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `value` FROM settings")
        settings = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
    except Exception:
        pass
    return settings

def get_rotated_proxy(logger_func=None):
    import requests
    import random
    FALLBACK_PROXY  = {"host": "180.93.2.171", "port": 3131, "user": "kierangrayson226", "pass": "odq0nda0odmzoa=="}
    
    def _log(msg, level="INFO"):
        if logger_func:
            logger_func(msg, level)
        else:
            print(f"[{level}] {msg}")

    try:
        settings = get_settings_from_db()
        proxy_type = settings.get("PROXY_TYPE", "proxyquick")
        if proxy_type == "proxyxoay":
            key = settings.get("PROXYXOAY_KEY", "")
            url = f"https://proxyxoay.shop/api/get.php?key={key}&&nhamang=random&&tinhthanh=0&whitelist="
            _log("Đang xoay IP qua ProxyXoay.shop API...", "INFO")
            resp = requests.get(url, timeout=15).json()
            if resp.get("status") == 100:
                proxy_str = resp.get("proxyhttp", "")
                parts = proxy_str.split(":")
                _log(f"Xoay IP thành công → {parts[0]}:{parts[1]}", "OK")
                return {"host": parts[0], "port": int(parts[1]), "user": "", "pass": ""}
            else:
                _log(f"API xoay proxy lỗi: {resp} → dùng proxy cố định", "WARN")
        else:
            token = settings.get("PROXY_API_TOKEN", "")
            merchant = settings.get("PROXY_MERCHANT", "")
            proxy_id = settings.get("PROXY_ID", "953319")
            headers = {"Authorization": f"Bearer {token}", "x-merchant-id": merchant}
            url = f"https://proxyquick.click/api/v2/proxies/{proxy_id}/rotate"
            _log("Đang xoay IP qua ProxyQuick API v2...", "INFO")
            resp = requests.get(url, headers=headers, proxies={"http": None, "https": None}, timeout=15).json()
            if resp.get("status") == "success":
                proxy_str = resp.get("proxy", "")
                parts = proxy_str.split(":")
                if len(parts) >= 4:
                    _log(f"Xoay IP thành công → {resp.get('ip', '')}", "OK")
                    return {"host": parts[0], "port": int(parts[1]), "user": parts[2], "pass": parts[3]}
            _log(f"API xoay proxy lỗi: {resp} → dùng proxy cố định", "WARN")
    except Exception as e:
        _log(f"Lỗi gọi API proxy: {e}", "ERR")
    
    _log(f"Dùng proxy cố định: {FALLBACK_PROXY['host']}:{FALLBACK_PROXY['port']}", "OK")
    return FALLBACK_PROXY
'''

# 1. Append to browser_utils.py
with open("src/bots/browser_utils.py", "a", encoding="utf-8") as f:
    f.write("\n" + utils_code)

# 2. Patch bots to remove get_rotated_proxy and get_settings_from_db
bot_files = [f for f in os.listdir("src/bots") if f.endswith(".py") and f != "browser_utils.py" and f != "__init__.py"]

for bf in bot_files:
    filepath = os.path.join("src/bots", bf)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Search and remove get_settings_from_db()
    content = re.sub(r'def get_settings_from_db\(\):.*?(?=def |\n\n\n)', '', content, flags=re.DOTALL)
    
    # Search and remove get_rotated_proxy()
    # We need to make sure we replace the calls as well, or just define a local wrapper
    match = re.search(r'def get_rotated_proxy\(\):.*?(?=def |\n\n\n)', content, flags=re.DOTALL)
    if match:
        wrapper = """from .browser_utils import get_rotated_proxy as _grp
def get_rotated_proxy():
    return _grp(logger_func=log)
"""
        content = content[:match.start()] + wrapper + content[match.end():]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")

