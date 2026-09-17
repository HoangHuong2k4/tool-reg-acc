import time
import os
import requests
import json

masa_token = "taskp_i7u7k9Rn4K8oXqpSSSJX6YsB8f_7ZEJbO7R5PPZ_NRjKu8PgkEA1YrUp_FYkuYFg"
url = "https://pay.nicepay.co.kr/v1/checkout/pay/VVQwMDA0MjY4Zw==/fpmandate_NzBCZmdYMEZkZVBKTXBKbmpqSkh6TEJwd1FoOXNucUtPbWg0RFVSRHVzYyMSFwoVYWNjdF8xUGtzZGRISm9oeXZJRDJj"

api_url = "https://plus.masa168.cc/api/v1/external/producer/submissions"
headers = {
    "Authorization": f"Bearer {masa_token}",
    "Idempotency-Key": f"task_{int(time.time())}_{os.urandom(4).hex()}",
    "Content-Type": "application/json"
}
data = {
    "channel": "kakao",
    "items": [{"url": url, "jwt": ""}]
}

try:
    print(f"Sending request to {api_url} with jwt=\"\"...")
    res = requests.post(api_url, headers=headers, json=data, timeout=10)
    print("Status:", res.status_code)
    try:
        print(json.dumps(res.json(), indent=2, ensure_ascii=False))
    except:
        print(res.text)
        
    if res.status_code == 422:
        # try another format
        data2 = {
            "channel": "kakao",
            "urls": [url]
        }
        print("\nSending request with urls=[url]...")
        res2 = requests.post(api_url, headers=headers, json=data2, timeout=10)
        print("Status:", res2.status_code)
        try:
            print(json.dumps(res2.json(), indent=2, ensure_ascii=False))
        except:
            print(res2.text)
            
except Exception as e:
    print("Error:", e)
