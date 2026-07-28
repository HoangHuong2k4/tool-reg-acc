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
        
        # Bước 1: Xin phiên thanh toán từ ChatGPT
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        checkout_url = "https://chatgpt.com/backend-api/payments/checkout"
        # Bắt đầu bằng GET như hướng dẫn
        resp1 = session.get(checkout_url, headers=headers, timeout=20)
        
        if resp1.status_code == 405:
            # Fallback sang POST nếu method not allowed
            resp1 = session.post(checkout_url, headers=headers, timeout=20)
            
        if resp1.status_code != 200:
            logger.warning(f"[MoMoCheck] Lấy checkout_session_id thất bại. Status: {resp1.status_code}")
            return False
            
        data1 = resp1.json()
        if "already have an active subscription" in str(data1).lower():
            logger.info("[MoMoCheck] Tài khoản đã có Plus.")
            return False
            
        checkout_session_id = data1.get("checkout_session_id")
        publishable_key = data1.get("publishable_key")
        if not checkout_session_id or not publishable_key:
            logger.warning("[MoMoCheck] Không tìm thấy checkout_session_id hoặc publishable_key trong response.")
            return "Lỗi Checkout"
            
        logger.info(f"[MoMoCheck] Checkout Session ID: {checkout_session_id[:10]}...")
        
        # Bước 2: Khởi tạo Stripe Payment Page (Bằng POST như gpt-upi)
        import uuid
        stripe_js_id = str(uuid.uuid4()).replace("-", "")
        init_url = f"https://api.stripe.com/v1/payment_pages/{checkout_session_id}/init"
        stripe_headers = {
            "User-Agent": headers["User-Agent"],
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://js.stripe.com",
            "Referer": f"https://js.stripe.com/v3/elements-inner-payment-{checkout_session_id}.html"
        }
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
        
        # Kiểm tra xem có phải gói 0đ không
        due = None
        if "total_summary" in data2 and "due" in data2["total_summary"]:
            due = data2["total_summary"]["due"]
        elif "invoice" in data2 and "amount_due" in data2["invoice"]:
            due = data2["invoice"]["amount_due"]
        elif "elements_options" in data2 and "amount" in data2["elements_options"]:
            due = data2["elements_options"]["amount"]
        elif "amount_due" in data2:
            due = data2["amount_due"]
            
        is_0d = False
        if isinstance(due, dict) and due.get("value") == 0:
            is_0d = True
        elif due == 0:
            is_0d = True
            
        prefix = "Gói 0đ" if is_0d else "Không 0đ"
        
        # Bỏ qua việc check momo ở init theo thiết kế (Geocoding ban đầu có thể ẩn momo)
        
        # Bước 3.1: Khởi tạo Elements Session
        elements_url = "https://api.stripe.com/v1/elements/sessions"
        elements_params = {
            "deferred_intent[payment_method_types][0]": "card",
            "deferred_intent[payment_method_types][1]": "momo",
            "deferred_intent[currency]": "vnd",
            "currency": "vnd",
            "key": publishable_key
        }
        resp3_1 = session.get(elements_url, headers=stripe_headers, params=elements_params, timeout=20)
        # Bỏ qua status check của 3.1 (dù lỗi hay không ta vẫn force tax region)
        
        # Bước 3.2: Cập nhật Tax Region (Ép về Việt Nam)
        update_tax_url = f"https://api.stripe.com/v1/payment_pages/{checkout_session_id}"
        tax_payload = {
            "tax_region[country]": "VN",
            "tax_region[postal_code]": "100000",
            "tax_region[city]": "Hanoi",
            "tax_region[line1]": "1 Trang Tien",
            "key": publishable_key
        }
        resp3_2 = session.post(update_tax_url, headers=stripe_headers, data=tax_payload, timeout=20)
        if resp3_2.status_code != 200:
            logger.warning(f"[MoMoCheck] Ép Tax Region thất bại. Status: {resp3_2.status_code}")
            return f"{prefix} - Ép Tax Lỗi"
            
        raw_due = due.get("value", 0) if isinstance(due, dict) else due
        
        # Bước 4: Chốt Thanh Toán MoMo
        confirm_url = f"https://api.stripe.com/v1/payment_pages/{checkout_session_id}/confirm"
        confirm_payload = {
            "payment_method_data[type]": "momo",
            "expected_payment_method_type": "momo",
            "payment_method_data[billing_details][name]": "Nguyen Van A",
            "payment_method_data[billing_details][email]": "a@example.com",
            "payment_method_data[billing_details][address][line1]": "1 Trang Tien",
            "payment_method_data[billing_details][address][city]": "Hanoi",
            "payment_method_data[billing_details][address][postal_code]": "100000",
            "payment_method_data[billing_details][address][country]": "VN",
            "expected_amount": str(raw_due) if raw_due is not None else "0",
            "version": "3eeb60efc5",
            "js_checksum": stripe_js_checksum(checkout_session_id),
            "rv_timestamp": stripe_rv_timestamp(),
            "_stripe_version": "2025-03-31.basil; checkout_server_update_beta=v1; checkout_manual_approval_preview=v1",
            "return_url": f"https://chatgpt.com/checkout/pay/{checkout_session_id}",
            "client_attribution_metadata[client_session_id]": stripe_js_id,
            "client_attribution_metadata[checkout_session_id]": checkout_session_id,
            "client_attribution_metadata[merchant_integration_source]": "checkout",
            "client_attribution_metadata[merchant_integration_version]": "custom",
            "client_attribution_metadata[merchant_integration_subtype]": "payment-element",
            "client_attribution_metadata[payment_intent_creation_flow]": "deferred",
            "client_attribution_metadata[payment_method_selection_flow]": "automatic",
            "key": publishable_key
        }
        resp4 = session.post(confirm_url, headers=stripe_headers, data=confirm_payload, timeout=20)
        
        if resp4.status_code != 200:
            logger.warning(f"[MoMoCheck] Chốt thanh toán MoMo thất bại. Status: {resp4.status_code}, Body: {resp4.text}")
            return f"{prefix} - Chốt Lỗi"
            
        data4 = resp4.json()
        next_action = data4.get("next_action")
        if next_action and "redirect_to_url" in next_action:
            url = next_action["redirect_to_url"].get("url")
            if url and url.startswith("http"):
                logger.info(f"[MoMoCheck] THÀNH CÔNG: Tài khoản có hỗ trợ thanh toán MoMo! ({prefix})")
                return f"{prefix} - Có MoMo"
                
        logger.info(f"[MoMoCheck] Không tìm thấy URL MoMo trong next_action. ({prefix})")
        return f"{prefix} - Ko MoMo"
        
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
