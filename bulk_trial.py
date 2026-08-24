"""
Bulk Netflix Trial Sender
Đọc email từ data/onl.txt (format: email|pass|token)
Gửi trial offer cho từng email, có delay, resume nếu bị ngắt.
"""
import sys
import os
import time
import json
from datetime import datetime

# Import từ NetflixTrial.py
sys.path.insert(0, os.path.dirname(__file__))
from NetflixTrial import bootstrap_netflix_session, send_trial_offer

INPUT_FILE = "data/onl.txt"
RESULT_FILE = ".cache/bulk_result.json"
DELAY = 2.0       # giây giữa mỗi email
REBATCH = 50      # re-bootstrap session sau mỗi N email

def load_done():
    """Load danh sách email đã xử lý (để resume)."""
    if os.path.exists(RESULT_FILE):
        with open(RESULT_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_results(results):
    os.makedirs(".cache", exist_ok=True)
    with open(RESULT_FILE, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def read_emails(path):
    emails = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('|')
            email = parts[0].strip()
            if '@' in email:
                emails.append(email)
    return emails

def main():
    emails = read_emails(INPUT_FILE)
    total = len(emails)
    print(f"\n{'━'*52}")
    print(f"   Netflix Bulk Trial Sender — {total} emails")
    print(f"{'━'*52}\n")

    results = load_done()
    done_emails = set(results.keys())
    pending = [e for e in emails if e not in done_emails]

    print(f"   ✓ Đã xử lý trước: {len(done_emails)}")
    print(f"   → Còn lại       : {len(pending)}")
    print()

    if not pending:
        print("   Tất cả email đã được xử lý!")
        _print_summary(results)
        return

    print("   Bootstrapping Netflix session...")
    cookies, session = bootstrap_netflix_session()
    print(f"   ✓ Session ready\n")

    ok_count = 0
    fail_count = 0
    start_time = time.time()

    for i, email in enumerate(pending, 1):
        # Re-bootstrap session định kỳ để tránh expire
        if i > 1 and (i - 1) % REBATCH == 0:
            print(f"\n   ↻ Re-bootstrapping session at #{i}...")
            cookies, session = bootstrap_netflix_session()
            print(f"   ✓ Session refreshed\n")

        try:
            _, success = send_trial_offer(email, cookies.copy(), session)
        except Exception as e:
            print(f"   [{i}/{len(pending)}] ✗ ERROR {email}: {e}")
            success = False

        status = "✓" if success else "✗"
        if success:
            ok_count += 1
        else:
            fail_count += 1

        results[email] = {
            "success": success,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # In tiến độ
        elapsed = time.time() - start_time
        speed = i / elapsed if elapsed > 0 else 0
        eta = (len(pending) - i) / speed if speed > 0 else 0
        print(f"   [{i:>4}/{len(pending)}] {status} {email:<35} | ✓{ok_count} ✗{fail_count} | ETA: {int(eta//60)}m{int(eta%60)}s")

        # Lưu sau mỗi email
        save_results(results)

        if i < len(pending):
            time.sleep(DELAY)

    print()
    print(f"{'━'*52}")
    _print_summary(results)
    print(f"   Results saved: {RESULT_FILE}")
    print(f"{'━'*52}\n")

def _print_summary(results):
    ok = sum(1 for v in results.values() if v.get('success'))
    fail = len(results) - ok
    print(f"   ━━ Summary ━━")
    print(f"   Total   : {len(results)}")
    print(f"   Success : {ok}")
    print(f"   Failed  : {fail}")
    if len(results):
        print(f"   Rate    : {ok/len(results)*100:.1f}%")

if __name__ == "__main__":
    main()
