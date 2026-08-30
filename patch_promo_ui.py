import urllib.parse

def generate_new_check_promo():
    return '''
def _step_check_promo(driver, stop_event=None):
    """
    Truy cập trang pricing của ChatGPT, kiểm tra có promo (0đ) không thông qua UI.
    Nếu có, click "Claim free offer", check MoMo ở trang thanh toán.
    Returns: (has_uudai: str, has_momo: str) - "có" hoặc "không"
    """
    has_uudai = "không"
    has_momo = "không"

    logger.info("[Promo] Kiểm tra ưu đãi Plus 1 Month Free...")
    try:
        time.sleep(1.5) # Chờ 2FA lưu xong
        
        # Dùng JS để chuyển hướng, đảm bảo React Router nhận diện
        driver.execute_script("window.location.href = 'https://chatgpt.com/?promo_campaign=plus-1-month-free#pricing';")
        time.sleep(3)
        _check_stop(stop_event)

        pricing_selectors = '[data-testid="plus-pricing-modal-column-top-half"], #plus-pricing, [data-testid="select-plan-button-plus-upgrade"]'
        
        try:
            wait_for_element(driver, By.CSS_SELECTOR, pricing_selectors, timeout=15)
        except Exception:
            logger.warning("[Promo] Không tìm thấy modal Pricing. Thử tải lại trang...")
            driver.refresh()
            time.sleep(3)
            try:
                wait_for_element(driver, By.CSS_SELECTOR, pricing_selectors, timeout=15)
            except Exception:
                logger.warning("[Promo] Vẫn không tải được trang Pricing sau khi refresh.")
                _save_screenshot(driver, "promo_failed")
                return has_uudai, has_momo

        claim_btn = None
        try:
            btns = driver.find_elements(By.XPATH, '//button[contains(., "Claim free offer")] | //button[contains(., "0")]')
            for b in btns:
                if b.is_displayed():
                    claim_btn = b
                    break
        except Exception:
            pass

        if not claim_btn:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, '[data-testid="select-plan-button-plus-upgrade"]')
                if "claim free offer" in btn.text.lower() or "0" in btn.text:
                    claim_btn = btn
            except:
                pass

        if claim_btn:
            has_uudai = "có"
            logger.info("[Promo] Đã thấy ưu đãi! Đang click 'Claim free offer'...")
            _fix_radix_pointer_events(driver)
            try_click(driver, claim_btn, "Claim Promo")

            time.sleep(4) # Chờ trang Stripe load iframe
            _check_stop(stop_event)
            logger.info("[Promo] Kiểm tra phương thức MoMo trên trang checkout...")
            try:
                found_momo = False
                for _ in range(8):
                    _check_stop(stop_event)
                    # 1. Thử tìm ngoài iframe
                    momo_tabs = driver.find_elements(By.CSS_SELECTOR, 'button[data-testid="momo"], #momo-tab, [value="momo"]')
                    if momo_tabs and any(t.is_displayed() for t in momo_tabs):
                        found_momo = True
                        break
                    
                    # 2. Thử duyệt qua các iframe (Stripe checkout)
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        try:
                            driver.switch_to.frame(iframe)
                            inner_tabs = driver.find_elements(By.CSS_SELECTOR, 'button[data-testid="momo"], #momo-tab, [value="momo"]')
                            if inner_tabs and any(t.is_displayed() for t in inner_tabs):
                                found_momo = True
                            driver.switch_to.default_content()
                            if found_momo: break
                        except Exception:
                            try: driver.switch_to.default_content()
                            except: pass
                    
                    if found_momo: break
                    time.sleep(1.5)

                if found_momo:
                    has_momo = "có"
                    logger.info("[Promo] Phát hiện MoMo trên trang checkout!")
                else:
                    logger.info("[Promo] Không có MoMo.")
            except Exception as e:
                logger.warning(f"[Promo] Lỗi load Checkout: {e}")
        else:
            logger.info("[Promo] Không có ưu đãi 0đ (chỉ hiện Upgrade to Plus).")
            has_uudai = "không"
            has_momo = "không"

    except Exception as e:
        logger.warning(f"[Promo] Lỗi check promo: {e}")

    return has_uudai, has_momo
'''

if __name__ == '__main__':
    with open('src/bots/gpt_selenium_utils.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    import re
    # Remove the old _step_check_promo function
    new_content = re.sub(r'def _step_check_promo\(driver, stop_event=None\):.*?return has_uudai, has_momo', generate_new_check_promo().strip(), content, flags=re.DOTALL)
    
    with open('src/bots/gpt_selenium_utils.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Patched successfully")
