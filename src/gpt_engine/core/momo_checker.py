import logging
import json
from typing import Tuple

logger = logging.getLogger(__name__)

def check_momo_payment(session, access_token: str) -> bool:
    """
    Trích xuất Link thanh toán Momo từ ChatGPT thông qua Stripe API.
    Dựa trên luồng quy định ở qr-extraction-flow.md
    """
    try:
        logger.info("[MoMoCheck] Bắt đầu check Momo payment...")
        
        # Bước 0: Xin Account ID + check eligible_promo_campaigns (trial info)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }
        
        acc_url = "https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27?timezone_offset_min=-420"
        resp_acc = session.get(acc_url, headers=headers, timeout=20)
        
        # Detect trial từ eligible_promo_campaigns (đây là nguồn đáng tin nhất)
        account_has_trial = False
        if resp_acc.status_code == 200:
            acc_data = resp_acc.json()
            # Lấy account_id từ default hoặc account_ordering
            acc_id = None
            if "account_ordering" in acc_data and acc_data["account_ordering"]:
                acc_id = acc_data["account_ordering"][0]
            if acc_id:
                headers["chatgpt-account-id"] = acc_id
            
            # Check eligible_promo_campaigns
            accounts = acc_data.get("accounts") or {}
            for _key, acc_val in accounts.items():
                if not isinstance(acc_val, dict):
                    continue
                promo_campaigns = acc_val.get("eligible_promo_campaigns") or {}
                plus_promo = promo_campaigns.get("plus") or {}
                if plus_promo:
                    metadata = plus_promo.get("metadata") or {}
                    discount = metadata.get("discount") or {}
                    pct = discount.get("percentage", 0)
                    promo_type = metadata.get("promotion_type", "")
                    if pct >= 100 or promo_type in ("discount", "free_trial", "trial"):
                        account_has_trial = True
                        logger.info(f"[MoMoCheck] ✅ Trial 0đ từ eligible_promo_campaigns! ({plus_promo.get('id')})")
                        break
                
        # Bước 1: Xin phiên thanh toán từ ChatGPT
        checkout_url = "https://chatgpt.com/backend-api/payments/checkout"
        payload_co = {
            "entry_point": "all_plans_pricing_modal",
            "plan_name": "chatgptplusplan",
            "locale": "vi",
            "billing_details": {"country": "VN", "currency": "VND"},
            "payment_method_types": ["card", "link", "momo"],
            "checkout_ui_mode": "custom",
            "cancel_url": "https://chatgpt.com/#pricing",
        }
        # Gọi POST tạo checkout
        resp1 = session.post(checkout_url, headers=headers, json=payload_co, timeout=20)
        
        if resp1.status_code == 405 or resp1.status_code == 400:
            # Fallback sang GET nếu POST không cho phép
            resp1 = session.get(checkout_url, headers=headers, timeout=20)
            
        if resp1.status_code != 200:
            logger.warning(f"[MoMoCheck] Lấy checkout_session_id thất bại. Status: {resp1.status_code}, Body: {resp1.text[:200]}")
            return False
            
        data1 = resp1.json()
        if "already have an active subscription" in str(data1).lower():
            logger.info("[MoMoCheck] Tài khoản đã có Plus.")
            return False
            
        checkout_session_id = data1.get("checkout_session_id")
        publishable_key = data1.get("publishable_key")
        client_secret = data1.get("customer_session_client_secret") or data1.get("client_secret")
        
        if not publishable_key:
            logger.warning("[MoMoCheck] Không tìm thấy publishable_key trong response.")
            return "Lỗi Checkout"
            
        import uuid
        import urllib.parse
        stripe_js_id = str(uuid.uuid4()).replace("-", "")
        
        stripe_headers = {
            "User-Agent": headers["User-Agent"],
            "Accept": "application/json",
            "Origin": "https://js.stripe.com",
        }
        
        data2 = {}
        if client_secret:
            logger.info(f"[MoMoCheck] Dùng elements/sessions API với Client Secret.")
            stripe_headers["Referer"] = "https://js.stripe.com/"
            
            params = {
                "customer_session_client_secret": client_secret,
                "key": publishable_key,
                "type": "deferred_intent",
                "deferred_intent[mode]": "subscription",
                "deferred_intent[amount]": "0",
                "deferred_intent[currency]": "vnd",
                "deferred_intent[setup_future_usage]": "off_session",
                "deferred_intent[payment_method_types][0]": "link",
                "deferred_intent[payment_method_types][1]": "momo",
                "deferred_intent[payment_method_types][2]": "card",
                "currency": "vnd",
                "locale": "en-GB",
                "browser_timezone": "Asia/Saigon",
                "_stripe_version": "2025-03-31.basil",
            }
            url = f"https://api.stripe.com/v1/elements/sessions?{urllib.parse.urlencode(params)}"
            resp2 = session.get(url, headers=stripe_headers, timeout=20)
            
            if resp2.status_code != 200:
                logger.warning(f"[MoMoCheck] Stripe Elements API thất bại. Status: {resp2.status_code}")
                return "Stripe Elements Lỗi"
                
            data2 = resp2.json()
            # Lấy payment methods từ nhiều fields (Elements API)
            pref = data2.get("payment_method_preference", {})
            payment_methods = pref.get("ordered_payment_method_types", [])
            if not payment_methods:
                payment_methods = data2.get("ordered_payment_method_types_and_wallets", [])
            if not payment_methods:
                specs = data2.get("payment_method_specs") or []
                payment_methods = [s["type"] for s in specs if isinstance(s, dict) and s.get("type")]
                
        elif checkout_session_id:
            logger.info(f"[MoMoCheck] Dùng payment_pages/init API (cũ) với Checkout Session ID: {checkout_session_id[:10]}...")
            stripe_headers["Content-Type"] = "application/x-www-form-urlencoded"
            stripe_headers["Referer"] = f"https://js.stripe.com/v3/elements-inner-payment-{checkout_session_id}.html"
            
            init_url = f"https://api.stripe.com/v1/payment_pages/{checkout_session_id}/init"
            init_payload = {
                "key": publishable_key,
                "browser_locale": "vn",
                "browser_timezone": "Asia/Ho_Chi_Minh",
                "eid": "NA",
                "redirect_type": "url"
            }
            resp2 = session.post(init_url, headers=stripe_headers, data=init_payload, timeout=20)
            if resp2.status_code != 200:
                logger.warning(f"[MoMoCheck] Stripe Init thất bại. Status: {resp2.status_code}")
                return "Stripe Init Lỗi"
                
            data2 = resp2.json()
            payment_methods = data2.get("ordered_payment_method_types", [])
            if not payment_methods:
                payment_methods = data2.get("payment_method_types", [])
        else:
            logger.warning("[MoMoCheck] Không tìm thấy client_secret hay checkout_session_id.")
            return "Lỗi Checkout"
            
        logger.info(f"[MoMoCheck] Payment methods available: {payment_methods}")
        
        has_momo = "momo" in payment_methods
        momo_str = "Có MoMo" if has_momo else "Không MoMo"
        
        # Trial: ưu tiên từ Account API (eligible_promo_campaigns)
        # Fallback: kiểm tra display_items (API cũ)
        is_0d = account_has_trial
        if not is_0d:
            due = None
            for item in data2.get("display_items", []):
                if item.get("type") == "custom":
                    due = item.get("custom", {}).get("amount")
                    break
            if isinstance(due, dict) and due.get("value") == 0:
                is_0d = True
            elif due == 0:
                is_0d = True
        
        if is_0d:
            return f"Gói 0đ - {momo_str}"
        else:
            return momo_str
        
    except Exception as e:
        logger.error(f"[MoMoCheck] Lỗi check MoMo: {str(e)}") 
        return f"Lỗi: {str(e)}"

def stripe_xor_base64_encode(value: str) -> str:
    import base64
    import urllib.parse
    padding_len = (3 - (len(value) % 3)) % 3
    padded = value + (" " * padding_len)
    xored_bytes = bytearray()
    for char in padded:
        xored_bytes.append(5 ^ ord(char))
    b64_str = base64.b64encode(xored_bytes).decode('ascii')
    return urllib.parse.quote(b64_str, safe='~()*!.\'')

def stripe_shift_printable(value: str, offset: int = 11) -> str:
    shifted = ""
    for char in value:
        shifted += chr(((ord(char) - 32 + offset) % 95) + 32)
    return shifted

def stripe_js_checksum(id_str: str) -> str:
    import json
    payload = json.dumps({"id": id_str}, separators=(',', ':'))
    return stripe_shift_printable(stripe_xor_base64_encode(payload), 11)

def stripe_rv_timestamp() -> str:
    import json
    STRIPE_RV_TS = "2024-01-01 00:00:00 -0000"
    STRIPE_RV = "3eeb60efc554e1de356807017990ea438f6b156a"
    STRIPE_SV = "971bc6188a741072452a935de1be7526fa781f1e88e8adb8447145c67b902767"
    payload = json.dumps({"rvTs": STRIPE_RV_TS, "rv": STRIPE_RV, "sv": STRIPE_SV}, separators=(',', ':'))
    return stripe_shift_printable(stripe_xor_base64_encode(payload), 11)
