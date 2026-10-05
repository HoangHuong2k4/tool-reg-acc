import time, os, requests

MASA_TOKEN = "taskp_i7u7k9Rn4K8oXqpSSSJX6YsB8f_7ZEJbO7R5PPZ_NRjKu8PgkEA1YrUp_FYkuYFg"
URLS = [
    "https://pay.nicepay.co.kr/v1/checkout/pay/VVQwMDA0MjY4Zw==/fpmandate_Q3J1Z2xSWWFIQndVeTc3eVQ0TlJzU2hCTm9ib3BUZGFSczVsaGlYc3p3VSMSFwoVYWNjdF8xUGtzZGRISm9oeXZJRDJj",
    "https://pay.nicepay.co.kr/v1/checkout/pay/VVQwMDA0MjY4Zw==/fpmandate_Und4N1dWYzc5ZS0wbWx0a1pkLTJJVFN5LUhhMGdGRnpFeDAxbVA5bTNPbyMSFwoVYWNjdF8xUGtzZGRISm9oeXZJRDJj"
]

for url in URLS:
    headers = {
        "Authorization": f"Bearer {MASA_TOKEN}",
        "Idempotency-Key": f"task_{int(time.time())}_{os.urandom(4).hex()}",
        "Content-Type": "application/json"
    }
    data = {
        "channel": "kakao",
        "urls": [url]
    }
    res = requests.post("https://plus.masa168.cc/api/v1/external/producer/submissions", headers=headers, json=data)
    print(f"Sent {url[-15:]} -> Status: {res.status_code}, Resp: {res.text}")
