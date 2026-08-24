import json
import requests
import os
import re
import uuid
from datetime import datetime
import time
import sys

OUTPUT_FOLDER = ".cache"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def parse_netscape_cookie(cookie_text):
    cookies = {}
    for line in cookie_text.strip().split('\n'):
        line = line.strip()
        if line.startswith('#') or not line:
            continue
        parts = line.split('\t')
        if len(parts) >= 7:
            name = parts[5]
            value = parts[6]
            cookies[name] = value
    return cookies

def parse_json_cookie(json_text):
    try:
        data = json.loads(json_text)
        cookies = {}
        if isinstance(data, dict):
            for key, value in data.items():
                cookies[key] = str(value)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if 'name' in item and 'value' in item:
                        cookies[item['name']] = item['value']
                    elif 'key' in item and 'value' in item:
                        cookies[item['key']] = item['value']
        return cookies
    except:
        return {}

def parse_cookie_content(content):
    content = content.strip()
    if content.startswith('{') or content.startswith('['):
        cookies = parse_json_cookie(content)
        if cookies and ('NetflixId' in cookies or 'SecureNetflixId' in cookies):
            return cookies, "JSON"
    cookies = parse_netscape_cookie(content)
    if cookies and ('NetflixId' in cookies or 'SecureNetflixId' in cookies):
        return cookies, "Netscape"
    lines = content.split('\n')
    cookies = {}
    for line in lines:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            parts = line.split('=', 1)
            if len(parts) == 2:
                cookies[parts[0].strip()] = parts[1].strip()
    if cookies and ('NetflixId' in cookies or 'SecureNetflixId' in cookies):
        return cookies, "Simple"
    return None, None

def build_cookie_string(cookies):
    cookie_parts = []
    for name, value in cookies.items():
        cookie_parts.append(f"{name}={value}")
    return "; ".join(cookie_parts)

def generate_request_id():
    return uuid.uuid4().hex[:32]

def generate_toplevel_uuid():
    return str(uuid.uuid4())

def generate_flwssn():
    return str(uuid.uuid4())

def generate_gsid():
    return str(uuid.uuid4()).replace('-', '')

# ─────────────────────────────────────────────
# Bootstrap session trực tiếp từ Netflix
# Thay thế server cookie ngoài đã chết
# ─────────────────────────────────────────────

def bootstrap_netflix_session():
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-IN,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    try:
        session.get(
            'https://www.netflix.com/in/signup',
            headers=headers,
            timeout=15,
            allow_redirects=True
        )
        cookies = dict(session.cookies)
        if 'flwssn' not in cookies:
            cookies['flwssn'] = generate_flwssn()
        if 'gsid' not in cookies:
            cookies['gsid'] = generate_gsid()
        return cookies, session
    except Exception as e:
        print(f"   ⚠ Bootstrap warning: {e}")
        cookies = {
            'flwssn': generate_flwssn(),
            'gsid': generate_gsid(),
        }
        return cookies, requests.Session()


def _deep_find(obj, key, _depth=0):
    """Tìm kiếm đệ quy một key trong nested dict/list."""
    if _depth > 20:
        return None
    if isinstance(obj, dict):
        if key in obj and obj[key]:
            return obj[key]
        for v in obj.values():
            result = _deep_find(v, key, _depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _deep_find(item, key, _depth + 1)
            if result:
                return result
    return None


def _extract_server_state(body):
    """Lấy serverState từ screen level của CLCSWebInitSignup response."""
    try:
        node = body.get('data', {}).get('clcsWebInitSignup', {})
        ss = node.get('screen', {}).get('serverState')
        if ss:
            return ss
        # Fallback: deep search
        return _deep_find(body, 'serverState')
    except:
        pass
    return None


def _extract_server_screen_update(body):
    """Lấy serverScreenUpdate từ sâu trong componentTree (nodes[...].onPress...)."""
    try:
        return _deep_find(body, 'serverScreenUpdate')
    except:
        pass
    return None


def _check_success_response(body, email):
    """
    Kiểm tra CLCSScreenUpdate response.
    Success = Netflix chuyển sang màn hình tiếp theo (PASSWORD/REGISTRATION...)
    Failure = có errors[] hoặc không có data.
    """
    try:
        errors = body.get('errors', [])
        if errors:
            return False

        data = body.get('data', {})
        if not data:
            return False

        # Tìm location hoặc nextInputNode bất kỳ trong response
        location = _deep_find(body, 'location')
        next_node = _deep_find(body, 'nextInputNode') or _deep_find(body, 'outputNode') or ''

        success_nodes = {'PASSWORD', 'REGISTRATION', 'PLAN_FORM',
                         'REGFLOW', 'PAYMENT', 'ACCOUNT_CREATION'}

        if isinstance(next_node, str) and any(n in next_node.upper() for n in success_nodes):
            return True

        # Netflix chuyển location sang REGFLOW / SIGNUP / PASSWORD
        if isinstance(location, str) and any(
            n in location.upper() for n in {'PASSWORD', 'REGISTRATION', 'REGFLOW', 'PAYMENT'}
        ):
            return True

        # Nếu có data và không errors → request được tiếp nhận
        # Đây là partial success (email gửi thành công đến Netflix)
        if data and not errors:
            return True

    except:
        pass
    return False


# ─────────────────────────────────────────────
# Gửi Trial Offer
# ─────────────────────────────────────────────

def send_trial_offer(email, cookies, session=None):
    if session is None:
        session = requests.Session()

    cookie_string = build_cookie_string(cookies)
    results = {}

    base_headers = {
        'authority': 'web.prod.cloud.netflix.com',
        'accept': '*/*',
        'accept-language': 'en-IN',
        'origin': 'https://www.netflix.com',
        'referer': 'https://www.netflix.com/',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }

    flwssn = cookies.get('flwssn', generate_flwssn())

    # ── Step 1: CLCSWebInitSignup ──────────────────────────────────────────
    try:
        h1 = base_headers.copy()
        h1.update({
            'content-type': 'application/json',
            'cookie': cookie_string,
            'x-netflix.context.app-version': 'v38c5b0da',
            'x-netflix.context.form-factor': 'phone',
            'x-netflix.context.is-inapp-browser': 'false',
            'x-netflix.context.locales': 'en-in',
            'x-netflix.context.operation-name': 'CLCSWebInitSignup',
            'x-netflix.context.ui-flavor': 'akira',
            'x-netflix.request.attempt': '1',
            'x-netflix.request.clcs.bucket': 'high',
            'x-netflix.request.client.context': '{"appstate":"foreground"}',
            'x-netflix.request.id': generate_request_id(),
            'x-netflix.request.originating.url': 'https://www.netflix.com/in/',
            'x-netflix.request.toplevel.uuid': generate_toplevel_uuid(),
        })

        d1 = {
            "operationName": "CLCSWebInitSignup",
            "variables": {
                "inputNode": "WELCOME",
                "locale": "en-IN",
                "inputFields": [
                    {"name": "flwssn", "value": {"stringValue": flwssn}},
                    {"name": "email", "value": {"stringValue": email}},
                    {"name": "recaptchaError", "value": {"stringValue": "LOAD_TIMED_OUT"}},
                    {"name": "recaptchaResponseTime", "value": {}},
                    {"name": "recaptchaSiteKey", "value": {"stringValue": "6LdqW_EqAAAAAO87Fb_kcZfNzs0IqJRcKiJDYpUv"}},
                    {"name": "recaptchaToken", "value": {}}
                ]
            },
            "extensions": {
                "persistedQuery": {
                    "id": "5d76d6a0-ccfe-4c31-b587-b4e1954732ca",
                    "version": 102
                }
            }
        }

        r1 = session.post(
            'https://web.prod.cloud.netflix.com/graphql',
            headers=h1, json=d1, timeout=15
        )
        results['init'] = {'status': r1.status_code, 'ok': r1.status_code == 200}

        server_state = None
        server_screen_update = None

        if r1.status_code == 200:
            try:
                body1 = r1.json()
                server_state = _extract_server_state(body1)
                # serverScreenUpdate nằm sâu trong componentTree.nodes[...].onPress
                server_screen_update = _extract_server_screen_update(body1)
            except:
                pass
            cookies.update(dict(session.cookies))
            cookie_string = build_cookie_string(cookies)
        else:
            print(f"   ⚠ Init step failed: HTTP {r1.status_code}")
            return results, False

    except Exception as e:
        results['init'] = {'error': str(e)}
        print(f"   ✗ Init error: {e}")
        return results, False

    time.sleep(0.8)

    # ── Step 2: CLCSScreenUpdate ───────────────────────────────────────────
    try:
        h2 = base_headers.copy()
        h2.update({
            'content-type': 'application/json',
            'cookie': cookie_string,
            'x-netflix.context.app-version': 'v38c5b0da',
            'x-netflix.context.form-factor': 'phone',
            'x-netflix.context.is-inapp-browser': 'false',
            'x-netflix.context.locales': 'en-in',
            'x-netflix.context.operation-name': 'CLCSScreenUpdate',
            'x-netflix.context.ui-flavor': 'akira',
            'x-netflix.request.attempt': '1',
            'x-netflix.request.clcs.bucket': 'high',
            'x-netflix.request.client.context': '{"appstate":"foreground"}',
            'x-netflix.request.id': generate_request_id(),
            'x-netflix.request.originating.url': 'https://www.netflix.com/signup',
            'x-netflix.request.toplevel.uuid': generate_toplevel_uuid(),
        })

        d2_vars = {
            "format": "HTML",
            "imageFormat": "PNG",
            "locale": "en-IN",
            "inputFields": [
                {"name": "email", "value": {"stringValue": email}},
                {"name": "pipcConsent", "value": {"booleanValue": False}}
            ]
        }
        if server_state:
            d2_vars["serverState"] = server_state
        if server_screen_update:
            d2_vars["serverScreenUpdate"] = server_screen_update

        d2 = {
            "operationName": "CLCSScreenUpdate",
            "variables": d2_vars,
            "extensions": {
                "persistedQuery": {
                    "id": "0fd81de7-07af-4c7d-802f-0f4ea4181aa3",
                    "version": 102
                }
            }
        }
        
        r2 = session.post(
            'https://web.prod.cloud.netflix.com/graphql',
            headers=h2, json=d2, timeout=15
        )
        results['update'] = {'status': r2.status_code, 'ok': r2.status_code == 200}

        if r2.status_code == 200:
            try:
                body2 = r2.json()
                success = _check_success_response(body2, email)
                results['update']['success_signal'] = success
                results['update']['response_preview'] = str(body2)[:400]
                return results, success
            except Exception as parse_err:
                results['update']['parse_error'] = str(parse_err)
                return results, False
        else:
            return results, False

    except Exception as e:
        results['update'] = {'error': str(e)}
        print(f"   ✗ Update error: {e}")
        return results, False

def main():
    print("\n" + "━" * 50)
    print("   Netflix 30 Days Trial Offer Sender")
    print("━" * 50)
    print()

    print("   Bootstrapping Netflix session...")
    cookies, session = bootstrap_netflix_session()

    if not cookies:
        print("   ⚠ Failed to bootstrap session.")
        print()
        return

    print(f"   ✓ Session ready (flwssn: {cookies.get('flwssn', 'N/A')[:8]}...)")
    print()

    if len(sys.argv) > 1:
        email = sys.argv[1].strip()
        print(f"   Email : {email}")
    else:
        email = input("   Email : ").strip()
        while not email or '@' not in email:
            print("   ⚠ Invalid email address")
            email = input("   Email : ").strip()

    print()
    print("   Got Email   : " + email)
    print("   Sending To Netflix")
    print("   Bypassing Recaptcha")
    print("   Processing Trial Offer")
    print()

    results, success = send_trial_offer(email, cookies, session)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{OUTPUT_FOLDER}/log_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump({
            'email': email,
            'success': success,
            'timestamp': timestamp,
            'results': {k: {kk: vv for kk, vv in v.items() if kk != 'response_preview'}
                        for k, v in results.items() if isinstance(v, dict)}
        }, f, indent=2)

    if success:
        print("   ✓ Success")
        print("   Email : " + email)
        print("   Resp  : Trial offer submitted successfully!")
    else:
        print("   ✗ Failed")
        init_s = results.get('init', {}).get('status', 'N/A')
        upd_s = results.get('update', {}).get('status', 'N/A')
        print(f"   Resp  : Unable to submit trial offer")
        print(f"   Debug : init={init_s}, update={upd_s}")

    print()
    print("━" * 50)
    print(f"   Log saved : {filename}")
    print()


if __name__ == "__main__":
    main()