import requests

def test_api():
    url = "https://edit-api-sg.capcut.com/cc/v1/workspace/mget_workspace_info"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        # Note: missing cookies, just want to see if it responds with "invalid session"
    }
    resp = requests.post(url, headers=headers, json={})
    print(resp.status_code, resp.text)

test_api()
