import urllib.parse
import json

def generate_new_check_promo():
    return '''
def _step_check_promo(driver, stop_event=None):
    """
    Sử dụng API fetch nội bộ (thừa hưởng token & cloudflare bypass của trình duyệt) 
    để check trực tiếp gói Ưu Đãi 0đ và MoMo cực nhanh (mô phỏng GPTPromoOS).
    Returns: (has_uudai: str, has_momo: str) - "có" hoặc "không"
    """
    has_uudai = "không"
    has_momo = "không"

    logger.info("[Promo] Kiểm tra ưu đãi Plus 1 Month Free và MoMo qua API nội bộ (Siêu tốc)...")
    try:
        js_code = """
        var cb = arguments[0];
        (async () => {
            try {
                // 1. Lấy Access Token
                let sessionRes = await fetch('/api/auth/session');
                if (!sessionRes.ok) return cb({error: "Lỗi auth/session: " + sessionRes.status});
                let session = await sessionRes.json();
                let accessToken = session.accessToken;
                if (!accessToken) return cb({error: "Không tìm thấy access token"});
                
                // 2. Gọi Checkout API
                let checkoutRes = await fetch('/backend-api/payments/checkout', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + accessToken
                    },
                    body: JSON.stringify({
                        entry_point: "all_plans_pricing_modal",
                        plan_name: "chatgptplusplan",
                        billing_details: {country: "VN", currency: "VND"},
                        promo_campaign: {promo_campaign_id: "plus-1-month-free", is_coupon_from_query_param: true},
                        prefetch: true,
                        checkout_ui_mode: "custom"
                    })
                });
                if (!checkoutRes.ok) return cb({error: "Lỗi Checkout API: " + checkoutRes.status});
                let checkout = await checkoutRes.json();
                let cs_id = checkout.checkout_session_id || checkout.cs_id;
                let pub_key = checkout.publishable_key;
                if (!cs_id || !pub_key) return cb({error: "Checkout thiếu session_id hoặc pub_key"});
                
                // 3. Gọi Stripe Init API
                let stripeRes = await fetch('https://api.stripe.com/v1/payment_pages/' + cs_id + '/init', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: 'key=' + encodeURIComponent(pub_key) + '&browser_locale=en-US&_stripe_version=2020-08-27'
                });
                if (!stripeRes.ok) return cb({error: "Lỗi Stripe API: " + stripeRes.status});
                let stripeInfo = await stripeRes.json();
                
                cb({success: true, stripe_info: stripeInfo});
            } catch(e) {
                cb({error: e.toString()});
            }
        })();
        """
        
        driver.set_script_timeout(15)
        result = driver.execute_async_script(js_code)
        
        if result.get("error"):
            logger.warning(f"[Promo] API check thất bại: {result['error']}")
            return has_uudai, has_momo
            
        stripe_info = result.get("stripe_info", {})
        
        # Parse MoMo
        payment_methods = []
        specs = stripe_info.get("payment_method_specs") or []
        for spec in specs:
            if isinstance(spec, dict) and "type" in spec:
                payment_methods.append(spec["type"])
        
        pref = stripe_info.get("payment_method_preference") or {}
        ordered = pref.get("ordered_payment_method_types") or []
        for m in ordered:
            if m not in payment_methods:
                payment_methods.append(m)
                
        # Parse Trial/Promo (0đ)
        amount_due = None
        total_summary = stripe_info.get("total_summary") or {}
        if "due" in total_summary:
            amount_due = total_summary["due"]
        else:
            amount_due = stripe_info.get("amount_total")
            
        if amount_due is not None:
            try: amount_due = float(amount_due)
            except: pass
            
        # Kiểm tra kết quả
        if amount_due == 0 or amount_due == 0.0:
            has_uudai = "có"
            logger.info("[Promo] Đã thấy ưu đãi Plus 1 Month (Giá: 0đ)!")
        else:
            logger.info(f"[Promo] Không có ưu đãi 0đ (Giá hiện tại: {amount_due}).")
            
        if any("momo" in str(m).lower() for m in payment_methods):
            has_momo = "có"
            logger.info("[Promo] Phát hiện MoMo trên trang thanh toán!")
        else:
            logger.info(f"[Promo] Không có MoMo. (Các cổng hiện có: {payment_methods})")
            
    except Exception as e:
        logger.warning(f"[Promo] Lỗi khi chạy JS check promo: {e}")

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
