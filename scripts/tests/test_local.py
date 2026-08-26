import requests
import json
try:
    res = requests.get("http://localhost:5050/api/proxy/status")
    print(res.json())
except Exception as e:
    print("Cannot connect to local server", e)
