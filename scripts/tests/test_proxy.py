import requests

key = "veEFwpBSXbFdvFqDosYXAk"
url = f"https://proxyxoay.shop/api/get.php?key={key}&&nhamang=random&&tinhthanh=0&whitelist="
print("API URL:", url)
try:
    r = requests.get(url, timeout=15)
    data = r.json()
    print("API Response:", data)
    
    if data.get("status") == 100:
        proxy_str = data.get("proxyhttp", "")
        parts = proxy_str.split(":")
        PROXY_HOST = parts[0]
        PROXY_PORT = int(parts[1])
        PROXY_USER = parts[2] if len(parts) > 2 else ""
        PROXY_PASS = parts[3] if len(parts) > 3 else ""
        
        if PROXY_USER and PROXY_PASS:
            proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        else:
            proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}"
            
        print("Testing proxy:", proxy_url)
        res = requests.get("https://ipinfo.io/ip", proxies={"http": proxy_url, "https": proxy_url}, timeout=10)
        print("IP Check Response:", res.text.strip())
except Exception as e:
    print("Error:", e)
