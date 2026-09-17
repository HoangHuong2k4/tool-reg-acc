import time
import requests
import json

masa_token = "taskp_i7u7k9Rn4K8oXqpSSSJX6YsB8f_7ZEJbO7R5PPZ_NRjKu8PgkEA1YrUp_FYkuYFg"
task_id = "1ac78fd3290c4efc9e253b2274e3306f"
query_url = "https://plus.masa168.cc/api/v1/external/producer/task-statuses/query"
headers = {
    "Authorization": f"Bearer {masa_token}",
    "Content-Type": "application/json"
}
try:
    print(f"Querying status for task_id: {task_id}")
    res = requests.post(query_url, headers=headers, json={"task_ids": [task_id]}, timeout=10)
    print("Status:", res.status_code)
    try:
        print(json.dumps(res.json(), indent=2, ensure_ascii=False))
    except:
        print(res.text)
except Exception as e:
    print("Error:", e)
