from __future__ import annotations
import base64
import json
import logging
import random
import time
import uuid

logger = logging.getLogger(__name__)

def fnv1a_32(text: str) -> str:
    value = 2166136261
    for char in text:
        value ^= ord(char)
        value = (value * 16777619) & 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 2246822507) & 0xFFFFFFFF
    value ^= value >> 13
    value = (value * 3266489909) & 0xFFFFFFFF
    value ^= value >> 16
    return format(value & 0xFFFFFFFF, "08x")

class SentinelTokenGenerator:
    MAX_ATTEMPTS = 500000

    def __init__(self, session):
        self.device_id = session.device_id
        self.profile = session.browser_profile
        self.user_agent = self.profile.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.sid = getattr(session, "sentinel_sid", None) or str(uuid.uuid4())

    def _config(self):
        screen = self.profile.get("screen", "1920x1080")
        perf_now = random.uniform(1000, 50000)
        return [
            screen,
            time.strftime(
                "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)",
                time.gmtime(),
            ),
            4294705152,
            random.random(),
            self.user_agent,
            "https://sentinel.openai.com/sentinel/20260124ceb8/sdk.js",
            None,
            None,
            "en-US",
            "en-US,en",
            random.random(),
            f"{random.choice(['vendor', 'plugins', 'hardwareConcurrency'])}-undefined",
            random.choice(["location", "implementation", "documentURI"]),
            random.choice(["Object", "Function", "Array"]),
            perf_now,
            self.sid,
            "",
            8,
            time.time() * 1000 - perf_now,
        ]

    @staticmethod
    def _encode(data):
        raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
        return base64.b64encode(raw).decode()

    def requirements_token(self):
        config = self._config()
        config[3] = 1
        config[9] = round(random.uniform(5, 50))
        return "gAAAAAC" + self._encode(config)

    def proof_token(self, seed, difficulty):
        started = time.time()
        config = self._config()
        difficulty = str(difficulty or "0")
        for nonce in range(self.MAX_ATTEMPTS):
            config[3] = nonce
            config[9] = round((time.time() - started) * 1000)
            encoded = self._encode(config)
            if fnv1a_32(seed + encoded)[: len(difficulty)] <= difficulty:
                return "gAAAAAB" + encoded + "~S"
        return None

def build_sentinel_token(session):
    generator = SentinelTokenGenerator(session)
    req_body = json.dumps({
        "p": generator.requirements_token(),
        "id": session.device_id,
        "flow": "chatgpt_checkout",
    })
    
    headers = {
        "Content-Type": "text/plain;charset=UTF-8",
        "Referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html",
        "Origin": "https://sentinel.openai.com",
        "User-Agent": generator.user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    profile = session.browser_profile
    if "sec_ch_ua" in profile:
        headers["sec-ch-ua"] = profile["sec_ch_ua"]
    if "mobile" in profile:
        headers["sec-ch-ua-mobile"] = profile["mobile"]
    if "platform" in profile:
        headers["sec-ch-ua-platform"] = profile["platform"]
        
    response = session.session.post(
        "https://sentinel.openai.com/backend-api/sentinel/req",
        data=req_body,
        headers=headers,
        timeout=25,
    )
    
    if response.status_code != 200:
        raise RuntimeError(f"Sentinel HTTP {response.status_code}: {response.text[:120]}")
        
    challenge = response.json()
    proof = challenge.get("proofofwork") or {}
    if proof.get("required"):
        token = generator.proof_token(proof.get("seed") or "", proof.get("difficulty"))
        if not token:
            raise RuntimeError(f"Sentinel PoW fail")
    else:
        token = generator.requirements_token()
        
    return json.dumps({
        "p": token,
        "t": "",
        "c": challenge["token"],
        "id": session.device_id,
        "flow": "chatgpt_checkout",
    }, separators=(",", ":"))

def collect_payment_methods(pm_types, wallets):
    def normalize(value):
        method = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if "link" in method:
            return "link"
        if "google_pay" in method or "googlepay" in method or "gpay" in method:
            return "google_pay"
        if "apple_pay" in method or "applepay" in method:
            return "apple_pay"
        return method

    methods = {normalize(m) for m in pm_types if m}
    methods.update(
        normalize(w.get("id") if isinstance(w, dict) else w)
        for w in wallets
        if w
        and (not isinstance(w, dict) or w.get("enabled") is True)
        and (not isinstance(w, dict) or w.get("id"))
    )
    
    ALLOWED = {"apple_pay", "google_pay", "card", "momo"}
    filtered = [m for m in methods if m in ALLOWED]
    return sorted(filtered)

def extract_payment_methods(stripe_info):
    pm_types = (
        (stripe_info.get("elements_options") or {}).get("payment_method_types")
        or stripe_info.get("payment_method_types")
        or []
    )
    return collect_payment_methods(
        pm_types,
        stripe_info.get("enabled_third_party_wallets") or [],
    )

def extract_trial(stripe_info):
    total_summary = stripe_info.get("total_summary") or {}
    amount_due = total_summary.get("due")
    if amount_due is None:
        amount_due = stripe_info.get("amount_total")
    try:
        amount_due = float(amount_due)
        if amount_due.is_integer():
            amount_due = int(amount_due)
    except (TypeError, ValueError):
        amount_due = None
    currency = str(
        stripe_info.get("currency") or total_summary.get("currency") or "vnd"
    ).upper()
    return amount_due, currency, amount_due == 0 if amount_due is not None else None

def check_momo_payment(session, access_token: str) -> bool:
    """
    Trích xuất Link thanh toán Momo từ ChatGPT thông qua Stripe API.
    """
    try:
        logger.info("[MoMoCheck] Bắt đầu check Momo payment...")
        sentinel_token = build_sentinel_token(session)
        
        profile = session.browser_profile
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "openai-sentinel-token": sentinel_token,
            "Referer": "https://chatgpt.com/?promo_campaign=plus-1-month-free",
            "Origin": "https://chatgpt.com",
            "oai-device-id": session.device_id,
            "User-Agent": profile.get("user_agent", ""),
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }
        
        if "sec_ch_ua" in profile:
            headers["sec-ch-ua"] = profile["sec_ch_ua"]
        if "mobile" in profile:
            headers["sec-ch-ua-mobile"] = profile["mobile"]
        if "platform" in profile:
            headers["sec-ch-ua-platform"] = profile["platform"]
            
        checkout_res = session.session.post(
            "https://chatgpt.com/backend-api/payments/checkout",
            json={
                "entry_point": "all_plans_pricing_modal",
                "plan_name": "chatgptplusplan",
                "billing_details": {"country": "VN", "currency": "VND"},
                "promo_campaign": {
                    "promo_campaign_id": "plus-1-month-free",
                    "is_coupon_from_query_param": True,
                },
                "prefetch": True,
                "checkout_ui_mode": "custom",
                "cancel_url": "https://chatgpt.com/#pricing",
            },
            headers=headers,
            timeout=35,
        )
        
        if checkout_res.status_code != 200 and checkout_res.status_code != 211 and checkout_res.status_code != 201:
            logger.warning(f"[MoMoCheck] Lấy checkout_session_id thất bại. Status: {checkout_res.status_code}, Response: {checkout_res.text[:120]}")
            return False, "lỗi", None, None
            
        checkout_data = checkout_res.json()
        logger.info(f"[MoMoCheck] Full Checkout Data: {checkout_data}")
        session_id = checkout_data.get("checkout_session_id") or checkout_data.get("cs_id")
        publishable_key = checkout_data.get("publishable_key")
        if not session_id:
            logger.warning("[MoMoCheck] Checkout thiếu session_id")
            return False, "lỗi", None, None
            
        provider = checkout_data.get("checkout_provider")
        if provider == "open_ai" or str(session_id).startswith("oaics_"):
            pm_types = checkout_data.get("payment_method_types") or []
            custom_pms = checkout_data.get("custom_payment_methods") or []
            payment_methods = collect_payment_methods(pm_types + custom_pms, [])
            logger.info(f"[MoMoCheck] OpenAI provider detected. Payment methods directly: {payment_methods}")
            if "card" in payment_methods:
                if "apple_pay" not in payment_methods:
                    payment_methods.append("apple_pay")
                if "google_pay" not in payment_methods:
                    payment_methods.append("google_pay")
            
            ALLOWED = {"apple_pay", "google_pay", "card", "momo"}
            payment_methods = sorted([m for m in payment_methods if m in ALLOWED])
            if payment_methods:
                return False, ", ".join(payment_methods), None, None
            return False, "không", None, None
            
        if not publishable_key:
            logger.warning("[MoMoCheck] Checkout thiếu publishable_key cho Stripe provider")
            return False, "lỗi", None, None
            
        logger.info(f"[MoMoCheck] Stripe provider detected. Checkout Session ID: {session_id} | Publishable Key: {publishable_key}")
        
        # Stripe Init
        STRIPE_VERSION = "2025-03-31.basil; checkout_server_update_beta=v1; checkout_manual_approval_preview=v1"
        stripe_headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://js.stripe.com",
            "Referer": f"https://js.stripe.com/v3/elements-inner-payment-{session_id}.html",
            "User-Agent": profile.get("user_agent", ""),
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        if "sec_ch_ua" in profile:
            stripe_headers["sec-ch-ua"] = profile["sec_ch_ua"]
        if "mobile" in profile:
            stripe_headers["sec-ch-ua-mobile"] = profile["mobile"]
        if "platform" in profile:
            stripe_headers["sec-ch-ua-platform"] = profile["platform"]
            
        stripe_res = session.session.post(
            f"https://api.stripe.com/v1/payment_pages/{session_id}/init",
            data={
                "key": publishable_key,
                "browser_locale": "en-US",
                "browser_timezone": "Asia/Ho_Chi_Minh",
                "elements_session_client[client_betas][0]": "custom_checkout_server_updates_1",
                "elements_session_client[client_betas][1]": "custom_checkout_manual_approval_1",
                "elements_session_client[elements_init_source]": "custom_checkout",
                "elements_session_client[referrer_host]": "chatgpt.com",
                "elements_session_client[stripe_js_id]": uuid.uuid4().hex,
                "elements_session_client[locale]": "en-US",
                "elements_session_client[is_aggregation_expected]": "false",
                "_stripe_version": STRIPE_VERSION,
            },
            headers=stripe_headers,
            timeout=40,
        )
        
        if stripe_res.status_code != 200:
            logger.warning(f"[MoMoCheck] Stripe Init thất bại. Status: {stripe_res.status_code}, Response: {stripe_res.text[:1000]}")
            return False, "lỗi", None, None
            
        stripe_info = stripe_res.json()
        payment_methods = extract_payment_methods(stripe_info)
        amount_due, currency, has_trial = extract_trial(stripe_info)
        
        logger.info(f"[MoMoCheck] Payment methods from Stripe: {payment_methods}, Has Trial: {has_trial}, Amount: {amount_due} {currency}")
        
        if "card" in payment_methods:
            if "apple_pay" not in payment_methods:
                payment_methods.append("apple_pay")
            if "google_pay" not in payment_methods:
                payment_methods.append("google_pay")
        
        ALLOWED = {"apple_pay", "google_pay", "card", "momo"}
        payment_methods = sorted([m for m in payment_methods if m in ALLOWED])
        
        if payment_methods:
            return has_trial, ", ".join(payment_methods), amount_due, currency
        return has_trial, "không", amount_due, currency
        
    except Exception as e:
        logger.error(f"[MoMoCheck] Lỗi check MoMo: {str(e)}")
        return False, "lỗi", None, None
