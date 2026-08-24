"""
Netflix Trial Mail Checker
Dùng API web-mail-reader.vercel.app để đọc inbox từng account
và kiểm tra có mail từ Netflix hay không → biết acc có trial chưa.

Format onl.txt: email|password|refresh_token|client_id
"""
import sys, os, json, time, requests
from datetime import datetime

INPUT_FILE  = "data/onl.txt"
RESULT_FILE = ".cache/mail_check_result.json"
API_BASE    = "https://web-mail-reader.vercel.app"
BATCH_SIZE  = 50   # số acc gửi 1 lần qua stream API
DELAY       = 0.5  # delay giữa các batch

NETFLIX_SENDERS = [
    'netflix.com',
    'account.netflix.com',
    'info@account.netflix.com',
    'netflix',
]

def read_accounts(path):
    accounts = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = line.split('|')
            if len(parts) < 3: continue
            email         = parts[0].strip()
            password      = parts[1].strip() if len(parts) > 1 else ''
            refresh_token = parts[2].strip() if len(parts) > 2 else ''
            client_id     = parts[3].strip() if len(parts) > 3 else '9e5f94bc-e8a4-4e73-b8be-63364c29d753'
            if '@' in email and refresh_token:
                accounts.append({
                    'email': email,
                    'password': password,
                    'refresh_token': refresh_token,
                    'client_id': client_id,
                })
    return accounts

def load_done():
    if os.path.exists(RESULT_FILE):
        with open(RESULT_FILE, 'r') as f:
            try: return json.load(f)
            except: return {}
    return {}

def save(results):
    os.makedirs(".cache", exist_ok=True)
    with open(RESULT_FILE, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def has_netflix_mail(messages):
    """Kiểm tra trong danh sách mail có mail từ Netflix không."""
    netflix_mails = []
    for msg in messages:
        from_addr = (msg.get('from_address') or '').lower()
        from_name = (msg.get('from_name') or '').lower()
        subject   = (msg.get('subject') or '').lower()

        is_netflix = any(s in from_addr or s in from_name for s in NETFLIX_SENDERS)
        is_netflix = is_netflix or 'netflix' in subject

        if is_netflix:
            netflix_mails.append({
                'subject':  msg.get('subject', ''),
                'from':     msg.get('from_address', ''),
                'date':     msg.get('date', ''),
                'snippet':  msg.get('snippet', '')[:100],
            })
    return netflix_mails

def check_batch_stream(batch):
    """
    Gọi /api/read-mail-stream cho một batch accounts.
    Trả về dict {email: result}
    """
    payload = {
        "accounts": [
            {
                "email":         acc['email'],
                "refresh_token": acc['refresh_token'],
                "client_id":     acc['client_id'],
            }
            for acc in batch
        ]
    }

    batch_results = {}

    try:
        resp = requests.post(
            f"{API_BASE}/api/read-mail-stream",
            json=payload,
            stream=True,
            timeout=60,
            headers={'Content-Type': 'application/json'}
        )

        if resp.status_code != 200:
            for acc in batch:
                batch_results[acc['email']] = {
                    'status': 'api_error',
                    'detail': f'HTTP {resp.status_code}'
                }
            return batch_results

        # Parse NDJSON stream
        for line in resp.iter_lines():
            if not line: continue
            try:
                data = json.loads(line.decode('utf-8') if isinstance(line, bytes) else line)
                email   = data.get('email', '')
                status  = data.get('status', '')
                messages = data.get('messages', [])

                if status == 'ok':
                    netflix_mails = has_netflix_mail(messages)
                    if netflix_mails:
                        batch_results[email] = {
                            'status':        'HAS_NETFLIX_MAIL',
                            'netflix_mails': netflix_mails,
                            'total_msgs':    len(messages),
                        }
                    else:
                        batch_results[email] = {
                            'status':     'NO_NETFLIX_MAIL',
                            'total_msgs': len(messages),
                        }
                else:
                    batch_results[email] = {
                        'status': 'error',
                        'detail': data.get('error', 'unknown'),
                    }
            except Exception as e:
                pass

    except Exception as e:
        for acc in batch:
            if acc['email'] not in batch_results:
                batch_results[acc['email']] = {
                    'status': 'exception',
                    'detail': str(e)[:100],
                }

    return batch_results


def main():
    accounts = read_accounts(INPUT_FILE)
    total    = len(accounts)

    print(f"\n{'━'*58}")
    print(f"   Netflix Mail Checker — {total} accounts")
    print(f"   API: {API_BASE}")
    print(f"{'━'*58}\n")

    results  = load_done()
    done_set = set(results.keys())
    pending  = [a for a in accounts if a['email'] not in done_set]

    print(f"   Đã check: {len(done_set)} | Còn lại: {len(pending)}\n")

    if not pending:
        _print_summary(results)
        return

    # Chia batch
    batches = [pending[i:i+BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    processed = 0

    for bi, batch in enumerate(batches, 1):
        print(f"   Batch {bi}/{len(batches)} — {len(batch)} accounts...")

        batch_res = check_batch_stream(batch)
        results.update(batch_res)
        save(results)

        # In kết quả batch
        for email, res in batch_res.items():
            status = res.get('status', '')
            if status == 'HAS_NETFLIX_MAIL':
                mails = res.get('netflix_mails', [])
                print(f"   🟢 {email}")
                for m in mails:
                    print(f"       → [{m['date'][:10]}] {m['subject']}")
            elif status == 'NO_NETFLIX_MAIL':
                print(f"   ⚪ {email}  (no Netflix mail, {res.get('total_msgs',0)} msgs)")
            else:
                print(f"   🔴 {email}  ({status}: {res.get('detail','')})")

        processed += len(batch)
        print(f"   Progress: {len(done_set)+processed}/{total}\n")

        if bi < len(batches):
            time.sleep(DELAY)

    print(f"{'━'*58}")
    _print_summary(results)
    print(f"   Results saved: {RESULT_FILE}")
    print(f"{'━'*58}\n")


def _print_summary(results):
    has_nf   = [e for e,v in results.items() if v.get('status')=='HAS_NETFLIX_MAIL']
    no_nf    = [e for e,v in results.items() if v.get('status')=='NO_NETFLIX_MAIL']
    errors   = [e for e,v in results.items() if v.get('status') not in ('HAS_NETFLIX_MAIL','NO_NETFLIX_MAIL')]

    print(f"\n   ━━ Summary ({len(results)} checked) ━━")
    print(f"   🟢 Có mail Netflix (đã/đang dùng) : {len(has_nf)}")
    print(f"   ⚪ Không có mail Netflix           : {len(no_nf)}")
    print(f"   🔴 Lỗi / token hết hạn             : {len(errors)}")

    if has_nf:
        print(f"\n   ── 🟢 Accounts có mail Netflix ──")
        for e in has_nf:
            mails = results[e].get('netflix_mails', [])
            subj  = mails[0].get('subject', '') if mails else ''
            print(f"   {e}  →  \"{subj}\"")


if __name__ == "__main__":
    main()
