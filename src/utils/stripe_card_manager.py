import re
import os
import time
import sqlite3
import requests
import html as html_lib

STRIPE_VERSION = "2025-06-30.basil"
CARDS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "cards.txt"))


def _get_db_setting(key, default=""):
    """Đọc setting từ database.db."""
    try:
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database.db"))
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row and row["value"]:
            return row["value"]
    except Exception:
        pass
    return default


def _build_proxies(proxy_str=None):
    """
    Tạo dict proxies cho requests từ settings DB.
    Đọc LAST_PROXY_HOST/PORT/USER/PASS đã lưu sẵn trong DB.
    proxy_str: nếu truyền vào thì dùng chuỗi đó, không đọc DB.
    Tự phát hiện SOCKS5 khi port là 1080/1081.
    Trả về None nếu không có proxy.
    """
    # Tắt proxy theo yêu cầu:
    return None



class CardManager:
    def __init__(self, file_path=CARDS_FILE, card_file=None):
        self.file_path = card_file if card_file is not None else file_path
        self.cards = []
        self.failed_cards = set()
        self.load_cards()

    def count(self):
        return len(self.cards)

    def load_cards(self):
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("# Định dạng: SốThẻ|Tháng|Năm|CVC\n")
            self.cards = []
            return

        with open(self.file_path, "r", encoding="utf-8-sig") as f:
            lines = [l.strip() for l in f if l.strip()]

        cards = []
        for line in lines:
            line_clean = line.strip()
            if line_clean.startswith("#") or line_clean.startswith("//"):
                continue
            parts = re.split(r"[|,/\s\t]+", line_clean)
            if len(parts) >= 4:
                num = re.sub(r"\D", "", parts[0].strip())
                month = re.sub(r"\D", "", parts[1].strip()).zfill(2)
                year = re.sub(r"\D", "", parts[2].strip())
                if len(year) == 4:
                    year = year[-2:]
                cvc = re.sub(r"\D", "", parts[3].strip())
                if len(num) >= 12 and month.isdigit() and 1 <= int(month) <= 12 and len(year) == 2 and len(cvc) >= 3:
                    cards.append({"number": num, "exp_month": month, "exp_year": year, "cvc": cvc, "raw": line})
        self.cards = cards

    def get_card(self, index=0):
        valid = [c for c in self.cards if c["number"] not in self.failed_cards]
        pool = valid if valid else self.cards
        if not pool:
            return None
        return pool[index % len(pool)]

    def mark_failed(self, card_number, reason=""):
        self.failed_cards.add(card_number)


def get_stripe_portal_link(driver, log_func=print, timeout=30):
    """
    Tự động load lại trang https://grok.com/ để đồng bộ trạng thái thanh toán, sau đó lấy link Stripe Portal.
    """
    try:
        cur_url = driver.current_url or ""
        log_func("-> Đang tải lại https://grok.com/ để đồng bộ gói cước...", "INFO")
        driver.get("https://grok.com/")
        time.sleep(4)

        start = time.time()
        while time.time() - start < 10:
            title = (driver.title or "").lower()
            if "just a moment" in title or "attention required" in title:
                time.sleep(1)
            else:
                break

        js_code = """
        var callback = arguments[arguments.length - 1];
        fetch('/rest/subscriptions/billing-portal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ returnUrl: window.location.href || 'https://grok.com/' }),
            credentials: 'include'
        })
        .then(function(res) {
            return res.json();
        })
        .then(function(data) {
            if (data.url) {
                callback(data.url);
            } else {
                callback('ERROR:' + JSON.stringify(data));
            }
        })
        .catch(function(err) {
            callback('ERROR:' + err.message);
        });
        """
        driver.set_script_timeout(timeout)
        result = driver.execute_async_script(js_code)
        if result and str(result).startswith("https://billing.stripe.com"):
            return str(result)
        elif result and str(result).startswith("ERROR:"):
            log_func(f"-> Thử lại sau 3s (Grok đang cập nhật: {result[6:]})...", "WARN")
            time.sleep(3)
            result_retry = driver.execute_async_script(js_code)
            if result_retry and str(result_retry).startswith("https://billing.stripe.com"):
                return str(result_retry)
            return None
        return None
    except Exception as e:
        log_func(f"-> Lỗi kết nối trình duyệt: {e}", "WARN")
        return None


import threading
STRIPE_API_LOCK = threading.Lock()

def add_card_to_stripe(stripe_link, card, log_func=print, proxy=None):
    """
    Thêm thẻ mới vào tài khoản qua Stripe Billing Portal API, gán làm mặc định và gỡ thẻ cũ.
    Dùng STRIPE_API_LOCK để đảm bảo tại 1 thời điểm chỉ có 1 luồng được đổi thẻ, chống spam API Stripe từ 1 Proxy.
    proxy: chuỗi proxy (vd: http://user:pass@host:port). None = đọc từ DB key VN_PROXY.
    """
    with STRIPE_API_LOCK:
        return _add_card_to_stripe_internal(stripe_link, card, log_func, proxy)

def _add_card_to_stripe_internal(stripe_link, card, log_func=print, proxy=None):
    proxies = _build_proxies(proxy)
    if proxies:
        log_func(f"-> Dùng proxy VN: {list(proxies.values())[0].split('@')[-1]}", "INFO")
    else:
        log_func("-> Không có proxy VN, kết nối trực tiếp.", "INFO")
    masked_card = f"{card['number'][:4]}...{card['number'][-4:]}"
    log_func(f"Đang phân tích link Stripe Portal để nạp thẻ [{masked_card}]...", "INFO")

    try:
        # 1. Tải HTML của trang Stripe Portal
        resp = requests.get(stripe_link, timeout=30, proxies=proxies)
        raw_html = resp.text
        decoded = html_lib.unescape(raw_html)

        pk_match = re.search(r'(pk_live_[a-zA-Z0-9]{20,})', decoded)
        bps_match = re.search(r'(bps_1[a-zA-Z0-9]{14,})', decoded)
        ek_match = re.search(r'(ek_live_[a-zA-Z0-9_]{20,})', decoded)

        pk_live = pk_match.group(1) if pk_match else None
        bps = bps_match.group(1) if bps_match else None
        ek_live = ek_match.group(1) if ek_match else None

        if not pk_live or not bps or not ek_live:
            log_func("❌ Không tìm thấy token Stripe trong HTML! Link có thể đã hết hạn.", "ERR")
            return False, "Token missing in Stripe HTML"

        UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        portal_headers = {
            "Authorization": f"Bearer {ek_live}",
            "Stripe-Version": STRIPE_VERSION,
            "Accept": "application/json",
            "User-Agent": UA,
            "Origin": "https://billing.stripe.com",
            "Referer": "https://billing.stripe.com/"
        }
        api_headers = {
            "Authorization": f"Bearer {pk_live}",
            "Accept": "application/json",
            "User-Agent": UA,
            "Origin": "https://billing.stripe.com",
            "Referer": "https://billing.stripe.com/"
        }

        # 2. Lấy Subscription ID
        sub_resp = requests.get(
            f"https://billing.stripe.com/v1/billing_portal/sessions/{bps}/subscriptions?include_only[]=data.id",
            headers=portal_headers, timeout=30, proxies=proxies
        )
        sub_data = sub_resp.json()
        if not sub_data.get("data") or len(sub_data["data"]) == 0:
            log_func(f"❌ Không tìm thấy Subscription gói Grok: {sub_data}", "ERR")
            return False, "No active subscription found"

        sub_id = sub_data["data"][0]["id"]
        log_func(f"-> Subscription ID: {sub_id}", "INFO")

        # 3. Lấy danh sách thẻ cũ
        pm_resp = requests.get(
            f"https://billing.stripe.com/v1/billing_portal/sessions/{bps}/payment_methods",
            headers=portal_headers, timeout=30, proxies=proxies
        )
        old_pms = [pm["id"] for pm in pm_resp.json().get("data", [])]
        log_func(f"-> Thẻ hiện có ({len(old_pms)}): {', '.join(old_pms) if old_pms else 'Không có'}", "INFO")

        # 4. Tạo thẻ mới qua Stripe API
        log_func(f"-> Đang tạo Payment Method cho thẻ {masked_card}...", "INFO")
        create_pm_resp = requests.post(
            "https://api.stripe.com/v1/payment_methods",
            data={
                "type": "card",
                "card[number]": card["number"],
                "card[exp_month]": card["exp_month"],
                "card[exp_year]": card["exp_year"],
                "card[cvc]": card["cvc"]
            },
            headers=api_headers,
            timeout=30,
            proxies=proxies
        )
        pm_result = create_pm_resp.json()
        if "error" in pm_result:
            err_msg = pm_result["error"].get("message", "Lỗi tạo thẻ Stripe")
            log_func(f"❌ Stripe từ chối thẻ: {err_msg}", "ERR")
            return False, err_msg

        new_pm = pm_result["id"]
        log_func(f"-> Tạo thẻ mới thành công: {new_pm}", "OK")

        # 5. Tạo và Confirm Setup Intent để gắn thẻ vào customer
        si_resp = requests.post(
            f"https://billing.stripe.com/v1/billing_portal/sessions/{bps}/setup_intents/",
            headers=portal_headers, timeout=30, proxies=proxies
        )
        si_data = si_resp.json()
        if "error" in si_data:
            log_func(f"⚠️ Lỗi tạo Setup Intent: {si_data['error'].get('message')}", "WARN")
            return False, si_data['error'].get('message')

        si_id = si_data["id"]
        client_secret = si_data["client_secret"] if "client_secret" in si_data else si_data.get("secret")

        confirm_resp = requests.post(
            f"https://api.stripe.com/v1/setup_intents/{si_id}/confirm",
            data={
                "payment_method": new_pm,
                "client_secret": client_secret,
                "return_url": "https://billing.stripe.com"
            },
            headers=api_headers, timeout=30, proxies=proxies
        )
        confirm_data = confirm_resp.json()
        if "error" in confirm_data:
            err_msg = confirm_data['error'].get('message', 'Unknown error')
            log_func(f"⚠️ Lỗi confirm Setup Intent: {err_msg}", "WARN")
            return False, f"Card declined: {err_msg}"
            
        status = confirm_data.get("status")
        if status and status not in ["succeeded", "processing"]:
            log_func(f"⚠️ Thẻ yêu cầu xác thực thêm hoặc bị từ chối ngầm (status: {status})", "WARN")
            return False, f"Card requires action or declined: {status}"

        # 6. Gán thẻ mới làm mặc định cho Subscription
        log_func("-> Đang gán thẻ mới làm mặc định...", "INFO")
        default_url = f"https://billing.stripe.com/v1/billing_portal/sessions/{bps}/subscriptions/{sub_id}/payment_methods/{new_pm}"
        def_resp = requests.post(default_url, headers=portal_headers, timeout=30, proxies=proxies)
        if def_resp.status_code not in [200, 201]:
            log_func(f"⚠️ Phản hồi gán mặc định ({def_resp.status_code}): {def_resp.text[:100]}", "WARN")
            return False, "Failed to set default payment method"
        else:
            log_func("✅ Đã gán thẻ mới làm mặc định thành công!", "OK")

        # 7. Gỡ các thẻ cũ (sau 3 giây)
        time.sleep(3)
        cards_to_delete = [pm for pm in old_pms if pm != new_pm]
        for old_pm in cards_to_delete:
            try:
                detach_url = f"https://billing.stripe.com/v1/billing_portal/sessions/{bps}/payment_methods/{old_pm}/detach"
                det_resp = requests.post(detach_url, headers=portal_headers, timeout=30, proxies=proxies)
                if det_resp.status_code in [200, 201]:
                    log_func(f"✅ Đã gỡ bỏ thẻ cũ: {old_pm}", "OK")
                else:
                    log_func(f"ℹ️ Thẻ {old_pm} được giữ lại do quy định Stripe", "INFO")
            except Exception as ex:
                log_func(f"⚠️ Không thể gỡ thẻ {old_pm}: {ex}", "WARN")

        log_func(f"🎉 HOÀN TẤT ĐỔI THẺ CHO TÀI KHOẢN!", "OK")
        return True, new_pm

    except Exception as e:
        log_func(f"❌ Ngoại lệ khi đổi thẻ: {e}", "ERR")
        return False, str(e)


GROK_UPGRADED_FILE = "data/grok_upgraded.txt"


def save_upgraded_account(email, password="grokai123", card_info="", kakao_url="", file_path=GROK_UPGRADED_FILE):
    """Lưu tài khoản đã nâng cấp gói (Kakao) & đổi thẻ Stripe thành công vào file txt."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        line = f"{email}|{password}\n"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(line)
        return True
    except Exception as e:
        print(f"Lỗi ghi {file_path}: {e}")
        return False


def change_card_for_driver(driver, card_manager=None, index=0, log_func=print):
    """
    Tiến hành đổi thẻ Stripe trực tiếp trên 1 driver browser cụ thể (dành cho luồng tự động 1 mạch).
    """
    try:
        if card_manager is None:
            card_manager = CardManager()

        if not card_manager.cards:
            log_func("❌ Không tìm thấy thẻ hợp lệ trong data/cards.txt!", "ERR")
            return False, "No cards in data/cards.txt"

        card = card_manager.get_card(index)
        if not card:
            log_func("❌ Không có thẻ khả dụng để đổi!", "ERR")
            return False, "No available card"

        log_func("💳 Đang kết nối tới Grok để lấy link Stripe Billing Portal...", "INFO")
        stripe_link = get_stripe_portal_link(driver, log_func=log_func)
        if not stripe_link:
            log_func("❌ Không lấy được link Stripe Portal!", "ERR")
            return False, "Failed to get Stripe portal link"

        card_masked = f"{card['number'][:4]}...{card['number'][-4:]}"
        log_func(f"💳 Đã lấy link Portal! Bắt đầu gán thẻ {card_masked}...", "INFO")
        ok, msg = add_card_to_stripe(stripe_link, card, log_func=log_func)
        if ok:
            driver._last_card = card_masked
            log_func(f"🎉 TỰ ĐỘNG ĐỔI THẺ STRIPE THÀNH CÔNG! (Thẻ {card_masked})", "OK")
            drv_email = getattr(driver, "_email", None)
            drv_pass = getattr(driver, "_password", "grokai123")
            drv_kakao = getattr(driver, "_kakao_url", "")
            if drv_email:
                save_upgraded_account(drv_email, drv_pass, card_info=card_masked, kakao_url=drv_kakao)
                log_func(f"[{drv_email}] 💾 Đã lưu tài khoản nâng cấp + đổi thẻ vào data/grok_upgraded.txt", "OK")
            try:
                driver.get(stripe_link)
            except:
                pass
            return True, msg
        else:
            log_func(f"❌ Đổi thẻ Stripe thất bại: {msg}", "ERR")
            return False, msg
    except Exception as e:
        log_func(f"❌ Ngoại lệ khi đổi thẻ driver: {e}", "ERR")
        return False, str(e)
