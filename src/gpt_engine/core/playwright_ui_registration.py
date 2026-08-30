# -*- coding: utf-8 -*-
import logging
import random
import time
import pyotp
import urllib.parse
from playwright.sync_api import sync_playwright
from core.email_provider import wait_for_otp
from core.account_export import save_account_data
from config import USER_AGENT

logger = logging.getLogger(__name__)

def run_playwright_registration(email: str, proxy: str = None, headless: bool = False, browser_type: str = "chrome", incognito: bool = False) -> bool:
    """
    Run the UI-driven Playwright registration flow.
    """
    pw = sync_playwright().start()
    
    # Configure Proxy
    proxy_server = None
    if proxy:
        try:
            parsed = urllib.parse.urlparse(proxy)
            proxy_server = {
                "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                "username": parsed.username or "",
                "password": parsed.password or ""
            }
        except Exception as e:
            logger.error(f"[PlaywrightUI] Lỗi parse proxy: {e}")
        
    logger.info(f"[PlaywrightUI] Khởi chạy trình duyệt cho {email}... (Browser: {browser_type}, Headless: {headless}, Incognito: {incognito})")
    
    if browser_type.lower() == "firefox" or browser_type.lower() == "camoufox":
        browser = pw.firefox.launch(headless=headless, args=["--no-sandbox"])
    else:
        browser = pw.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    
    context_args = {
        "proxy": proxy_server,
        "user_agent": USER_AGENT or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    context = browser.new_context(**context_args)
    
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    page = context.new_page()
    
    try:
        logger.info(f"[PlaywrightUI] Mở trang chủ chatgpt.com...")
        page.goto("https://chatgpt.com/")
        
        logger.info(f"[PlaywrightUI] Đợi nút Sign up...")
        page.wait_for_selector('[data-mobile-auth-entry-action="signup"]', timeout=30000)
        page.click('[data-mobile-auth-entry-action="signup"]')
        
        logger.info(f"[PlaywrightUI] Điền email: {email}...")
        page.wait_for_selector('input[name="login_hint"]', timeout=15000)
        page.fill('input[name="login_hint"]', email)
        page.click('button[type="submit"]')
        
        logger.info(f"[PlaywrightUI] Chờ chuyển hướng xác thực email...")
        page.wait_for_selector('a[href="/create-account/password"], button:has-text("Continue with password")', timeout=30000)
        page.click('a[href="/create-account/password"], button:has-text("Continue with password")')
        
        # Lấy pass
        try:
            from bots.gpt_gmail94 import GMAIL94_PASSWORD
            password = GMAIL94_PASSWORD
            if not password: raise Exception()
        except:
            password = "Passw0rd123!@#"

        logger.info(f"[PlaywrightUI] Đang điền mật khẩu...")
        page.wait_for_selector('input[name="password"], input[type="password"]', timeout=15000)
        page.fill('input[name="password"], input[type="password"]', password)
        page.click('button[type="submit"]')
        
        logger.info(f"[PlaywrightUI] Quay lại trang xác minh mã OTP, đang lấy mã từ Gmail...")
        page.wait_for_selector('input[name="code"]', timeout=30000)
        
        otp_code = wait_for_otp(email, time.time())
        if not otp_code:
            logger.error(f"[PlaywrightUI] Không lấy được mã OTP cho {email}.")
            return False
            
        logger.info(f"[PlaywrightUI] Lấy được OTP: {otp_code}. Đang điền mã...")
        page.fill('input[name="code"]', otp_code)
        
        try:
            page.click('button[value="validate"]', timeout=3000)
        except:
            pass

        logger.info(f"[PlaywrightUI] Chờ trang about-you...")
        page.wait_for_selector('input[name="name"]', timeout=30000)
        page.fill('input[name="name"]', "Nguyen Tuan")
        
        try:
            page.wait_for_selector('input[name="age"]', timeout=3000)
            page.fill('input[name="age"]', str(random.randint(20, 35)))
        except:
            pass
            
        page.click('button[type="submit"]')
        
        logger.info(f"[PlaywrightUI] Hoàn tất đăng ký, tiến hành cài đặt 2FA...")
        page.wait_for_selector('text="You\'re all set" , text="ChatGPT"', timeout=30000)
        
        try:
            page.click('button:has-text("Continue")', timeout=5000)
        except:
            pass
            
        logger.info(f"[PlaywrightUI] Đang truy cập Settings...")
        page.goto("https://chatgpt.com/#settings")
        
        logger.info(f"[PlaywrightUI] Chọn tab Security...")
        page.wait_for_selector('[data-testid="security-tab"]', timeout=15000)
        page.click('[data-testid="security-tab"]')
        
        logger.info(f"[PlaywrightUI] Bật Authenticator app...")
        page.wait_for_selector('[data-testid="mfa-authenticator-toggle"]', timeout=10000)
        page.click('[data-testid="mfa-authenticator-toggle"]')
        
        logger.info(f"[PlaywrightUI] Đang lấy mã Secret TOTP...")
        page.wait_for_selector('button:has-text("Trouble scanning?")', timeout=10000)
        page.click('button:has-text("Trouble scanning?")')
        
        secret_el = page.wait_for_selector('.font-mono.select-text', timeout=10000)
        totp_secret = secret_el.inner_text().strip()
        logger.info(f"[PlaywrightUI] Lấy được TOTP Secret: {totp_secret}")
        
        totp = pyotp.TOTP(totp_secret)
        code = totp.now()
        
        logger.info(f"[PlaywrightUI] Đang điền mã TOTP: {code}...")
        page.fill('input[name="totp_otp"]', code)
        page.click('button:has-text("Verify")')
        
        time.sleep(3)
        
        save_account_data(email, password, totp_secret, has_momo=False)
        logger.info(f"[PlaywrightUI] ✨ Tạo tài khoản thành công! Đã lưu: {email}")
        
        return True
        
    except Exception as e:
        logger.error(f"[PlaywrightUI] Lỗi trong quá trình đăng ký UI: {e}", exc_info=True)
        return False
    finally:
        context.close()
        browser.close()
        pw.stop()
