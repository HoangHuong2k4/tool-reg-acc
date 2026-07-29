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
        payment_methods = data2.get("ordered_payment_method_types", [])
        if not payment_methods:
            payment_methods = data2.get("payment_method_types", [])
        logger.info(f"[MoMoCheck] Payment methods available: {payment_methods}")
        
        has_momo = "momo" in payment_methods
        momo_str = "Có MoMo" if has_momo else "Không MoMo"
        
        # Kiểm tra xem có phải gói 0đ không
        due = None
        for item in data2.get("display_items", []):
            if item.get("type") == "custom":
                due = item.get("custom", {}).get("amount")
                break
        
        is_0d = False
        if isinstance(due, dict) and due.get("value") == 0:
            is_0d = True
        elif due == 0:
            is_0d = True
        
        if due == 0:
            return f"Gói 0đ - {momo_str}"
        elif due is not None:
            return f"Gói {due} - {momo_str}"
        else:
            return f"Có Trial - {momo_str}" if is_0d else "Không 0đ"
        
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
