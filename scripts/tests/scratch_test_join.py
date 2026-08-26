import requests

def test_join():
    url = "https://edit-api-sg.capcut.com/cc/v1/workspace/join"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json={})
    print(resp.status_code, resp.text)

test_join()
