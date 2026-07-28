import os
import sys
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'gpt_engine'))
from core.session import BrowserSession
from core.momo_checker import check_momo_payment
from config.browser import BROWSER_PROFILE_POOL

logging.basicConfig(level=logging.INFO)

def main():
    token_file = "/app/capcut-regaccc/src/gpt_engine/注册成功的token.txt"
    if not os.path.exists(token_file):
        print(f"Token file {token_file} not found.")
        return

    with open(token_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    
    if not lines:
        print("No tokens found.")
        return
        
    access_token = lines[-1]  # Get the last registered token
    print(f"Testing with token: {access_token[:20]}...")
    
    # Init session
    proxy = "http://qf_181156_yQ_f-zone-resi-region-sg-sid-1:qf_181156_yQ_f@103.216.74.218:1080"
    session = BrowserSession(proxy_url=proxy, account_id="test")
    session.init_session(BROWSER_PROFILE_POOL[0])
    
    res = check_momo_payment(session, access_token, proxy_url=proxy)
    print("MOMO RESULT:", res)

if __name__ == "__main__":
    main()
