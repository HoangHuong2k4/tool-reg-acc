#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CapCut Auto Register Bot - Gmail94 Edition
Đăng ký tài khoản CapCut bằng Gmail mua tự động từ Gmail94 API (Service 'capcut' / 29).
Tích hợp vào Web UI (app.py).
"""

import os
import sys
import time
import re
import json
import sqlite3
import threading
import requests
from datetime import datetime

# ── Import modules & helper từ CapCut Hotmail ──────────────────────────────
from src.bots import capcut_hotmail as ch

# ── Cấu hình & Trạng thái ──────────────────────────────────────────────────
_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.abspath(os.path.join(_BOT_DIR, "..", ".."))
OUTPUT_FILE = os.path.join(_ROOT_DIR, "data", "accounts.txt")

GMAIL94_TOKEN = ""
GLOBAL_STOP_EVENT = threading.Event()
ACTIVE_DRIVERS = []


def get_db_setting(key, default=""):
    try:
        db_path = os.path.join(_ROOT_DIR, "data", "database.db")
        if not os.path.exists(db_path):
            return default
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row and row["value"]:
            return row["value"]
    except Exception as e:
        log(f"Lỗi đọc DB ({key}): {e}", "WARN")
    return default


def log(msg, level="INFO"):
    ch.log(msg, level)


def get_rotated_proxy():
    return ch.get_rotated_proxy()


def save_account(uidname, email, password, join_link="", msToken=""):
    """Lưu tài khoản vào accounts.txt (sẽ bị app.py override bằng capcut_save_db)."""
    with ch.ACCOUNTS_LOCK:
        try:
            os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(f"{email}\t{password}\t{uidname}\t{join_link}\t{msToken}\n")
        except Exception as e:
            log(f"Lỗi lưu file accounts.txt: {e}", "WARN")


def update_account_payment_link(email, link=None, has_trial=False, uudai=None):
    """Cập nhật link thanh toán vào DB (sẽ bị app.py override)."""
    ch.update_account_payment_link(email, link=link, has_trial=has_trial, uudai=uudai)


def sync_module_hooks():
    """Đồng bộ các hooks và biến toàn cục với module capcut_hotmail."""
    ch.log = log
    ch.ACTIVE_DRIVERS = ACTIVE_DRIVERS
    ch.GLOBAL_STOP_EVENT = GLOBAL_STOP_EVENT
    ch.get_rotated_proxy = get_rotated_proxy
    ch.save_account = save_account
    ch.update_account_payment_link = update_account_payment_link


# ── Gmail94 API: Mua Gmail & Đọc mã OTP ───────────────────────────────────

def gmail94_buy(token=None):
    """
    Mua 1 Gmail mới từ Gmail94 cho service CapCut (Thử 'capcut' trước, fallback '29').
    Trả về dict {"email": ..., "order_id": ...} hoặc None nếu lỗi.
    """
    if not token:
        token = GMAIL94_TOKEN or get_db_setting("GMAIL94_TOKEN")
    if not token:
        log("Chưa cấu hình GMAIL94_TOKEN trong Cài đặt!", "ERR")
        return None

    url = "https://gmail94.com/api/otp/create"
    last_err = ""

    # Thử service 'capcut' (chuẩn API) trước, nếu lỗi thử '29' (ID service trên web)
    for s in ["capcut", "29"]:
        try:
            params = {"token": token, "service": s}
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 200 and resp.text:
                try:
                    data = resp.json()
                except Exception:
                    continue
                if data.get("success") and "data" in data and data["data"].get("email"):
                    email = data["data"]["email"].strip()
                    order_id = str(data["data"].get("order_id", "")).strip()
                    log(f"Gmail94 mua thành công: {email} (order: {order_id})", "OK")
                    return {"email": email, "order_id": order_id}
                else:
                    last_err = data.get("msg") or data.get("message") or data.get("error") or str(data)
                    log(f"Gmail94 mua service '{s}': {last_err}", "WARN")
        except Exception as e:
            last_err = str(e)
            log(f"Gmail94 mua lỗi exception ({s}): {e}", "WARN")

    if last_err:
        log(f"Gmail94 phản hồi lỗi mua: {last_err}", "ERR")
    return None


def gmail94_read_otp(token=None, order_id="", timeout=120, interval=4):
    """
    Polling đọc mã OTP từ Gmail94 cho order_id.
    Timeout mặc định: 120s (2 phút).
    """
    if not token:
        token = GMAIL94_TOKEN or get_db_setting("GMAIL94_TOKEN")

    url = "https://gmail94.com/api/otp/read"
    log(f"Đang chờ OTP CapCut từ Gmail94 (Order: {order_id}, tối đa {timeout}s)...", "INFO")
    start_time = time.time()
    last_log_time = start_time

    while time.time() - start_time < timeout:
        if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
            log("Nhận tín hiệu DỪNG toàn hệ thống, ngưng chờ OTP.", "WARN")
            return None

        elapsed = int(time.time() - start_time)
        if time.time() - last_log_time >= 15:
            last_log_time = time.time()
            log(f"Đang đợi OTP từ Gmail94... ({elapsed}/{timeout}s)", "INFO")

        for s in ["capcut", "29"]:
            try:
                params = {"token": token, "order_id": order_id, "service": s}
                resp = requests.get(url, params=params, timeout=15)
                if resp.status_code == 200 and resp.text:
                    try:
                        data = resp.json()
                    except Exception:
                        continue

                    # Kiểm tra otp trực tiếp
                    otp_val = None
                    if data.get("success"):
                        if data.get("otp"):
                            otp_val = data["otp"]
                        elif isinstance(data.get("data"), dict) and data["data"].get("otp"):
                            otp_val = data["data"]["otp"]

                    if otp_val:
                        # Trích xuất 6 chữ số
                        m = re.search(r'\b\d{6}\b', str(otp_val))
                        if m:
                            code = m.group(0)
                            log(f"✅ Đã nhận được OTP từ Gmail94: {code}", "OK")
                            return code
                        else:
                            # Nếu otp ngắn hơn hoặc dạng chuỗi số
                            clean = "".join(filter(str.isdigit, str(otp_val)))
                            if len(clean) == 6:
                                log(f"✅ Đã nhận được OTP từ Gmail94: {clean}", "OK")
                                return clean
            except Exception as e:
                # Lỗi mạng tạm thời, tiếp tục polling
                pass

        time.sleep(interval)

    log(f"Hết thời gian chờ OTP từ Gmail94 ({timeout}s)!", "ERR")
    return None


def step4_enter_otp_gmail94(driver, email, order_id, token=None):
    """
    Bước 4: Chờ màn hình OTP của CapCut, đọc mã từ Gmail94 và điền vào form.
    """
    from selenium.webdriver.common.by import By

    log(f"[{email}] Bước 4: Chờ màn hình nhập OTP...", "INFO")

    try:
        ch.wait_for_element(driver, By.CSS_SELECTOR,
            '.lv_sign_in_panel_wide-code-detail, .verification_code_input-wrapper', timeout=25)
    except Exception as e:
        log(f"[{email}] Không thấy màn hình yêu cầu OTP ({e})", "WARN")
        return False

    log(f"[{email}] Màn hình xác nhận email xuất hiện. Đang lấy OTP từ Gmail94...", "INFO")
    time.sleep(3)

    otp = gmail94_read_otp(token=token, order_id=order_id, timeout=120, interval=4)
    if not otp:
        log(f"[{email}] Không lấy được OTP từ Gmail94!", "ERR")
        return False

    # Nhập OTP vào ô
    try:
        otp_input = driver.find_element(By.CSS_SELECTOR,
            'input[maxlength="6"], .lv_sign_in_panel_wide-code-detail input')
        ch.set_react_input(driver, otp_input, otp)
        log(f"[{email}] Đã nhập OTP thành công: {otp}", "OK")
        time.sleep(2)
        return True
    except Exception as e:
        log(f"[{email}] Không tìm thấy ô nhập OTP trực tiếp ({e}), thử nhập từng ô nhỏ...", "WARN")
        try:
            code_boxes = driver.find_elements(By.CSS_SELECTOR,
                '.verification_code_input-number input, input.lv-input')
            if code_boxes:
                code_boxes[0].click()
                for digit in otp:
                    driver.switch_to.active_element.send_keys(digit)
                    time.sleep(0.1)
                log(f"[{email}] Đã nhập OTP qua từng ký tự: {otp}", "OK")
                time.sleep(2)
                return True
        except Exception as e2:
            log(f"[{email}] Nhập OTP thất bại: {e2}", "ERR")
        return False


# ── Đăng ký 1 tài khoản CapCut bằng Gmail94 ──────────────────────────────

def register_one_account(index, join_link=None, keep_open=False, batch_size=3,
                         predefined_proxy=None, headless=False, browser_type="chrome",
                         get_link=False, mail_api_source="gmail94", incognito=False,
                         save_trial_7day=False, **kwargs):
    """
    Quy trình đăng ký 1 tài khoản CapCut bằng Gmail mua từ Gmail94:
    1. Mua Gmail từ Gmail94 API (service: capcut / 29)
    2. Khởi tạo browser
    3. Điền email, password, ngày sinh
    4. Lấy OTP từ Gmail94 API và điền vào CapCut
    5. Join team (nếu có join_link) hoặc mở trang CapCut / Lấy link trial 7 ngày
    """
    sync_module_hooks()

    if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
        log(f"Acc #{index}: Hệ thống đang dừng, bỏ qua đăng ký.", "WARN")
        return False

    token = GMAIL94_TOKEN or get_db_setting("GMAIL94_TOKEN")
    if not token:
        log(f"Acc #{index}: Chưa cấu hình GMAIL94_TOKEN trong Cài đặt!", "ERR")
        return False

    # 1. Mua Gmail từ Gmail94
    log(f"Acc #{index}: Đang mua Gmail từ Gmail94 (service CapCut)...", "INFO")
    bought = gmail94_buy(token)
    if not bought:
        log(f"Acc #{index}: Mua email Gmail94 thất bại!", "ERR")
        return False

    email = bought["email"]
    order_id = bought["order_id"]
    password = get_db_setting("CAPCUT_PASSWORD", "capcut123") or "capcut123"

    driver = None
    should_keep_open = keep_open and not get_link and not save_trial_7day

    try:
        max_retries = 3
        for attempt in range(max_retries):
            if GLOBAL_STOP_EVENT and GLOBAL_STOP_EVENT.is_set():
                return False

            driver = ch.setup_driver(
                index=index,
                keep_open=keep_open,
                use_api_proxy=True,
                batch_size=batch_size,
                use_proxy=True,
                predefined_proxy=predefined_proxy,
                incognito=incognito,
                headless=headless,
                browser_type=browser_type
            )
            ACTIVE_DRIVERS.append(driver)
            log(f"[{email}] Bắt đầu mở trình duyệt... (Lần thử {attempt+1})", "INFO")

            try:
                driver.get("https://www.capcut.com/vi-vn/login")
                break
            except Exception as e:
                if "ERR_TUNNEL_CONNECTION_FAILED" in str(e) or "ERR_PROXY_CONNECTION_FAILED" in str(e) or "TimeoutException" in type(e).__name__:
                    if attempt < max_retries - 1:
                        log(f"[{email}] Lỗi kết nối/proxy ({type(e).__name__}). Đang thử lại lần {attempt+2}/{max_retries}...", "WARN")
                        try:
                            if hasattr(driver, '_proxy_relay') and driver._proxy_relay:
                                driver._proxy_relay.stop()
                            if driver in ACTIVE_DRIVERS:
                                ACTIVE_DRIVERS.remove(driver)
                            driver.quit()
                        except: pass
                        time.sleep(3)
                    else:
                        raise e
                else:
                    raise e

        time.sleep(3)

        # Các bước đăng ký CapCut
        ch.step0_dismiss_tos(driver)
        ch.step0b_click_email_button(driver)
        ch.step1_enter_email(driver, email)
        ch.step2_enter_password(driver, password)
        bday_status = ch.step3_enter_birthday(driver)

        if bday_status != "ALREADY_LOGGED_IN":
            otp_ok = step4_enter_otp_gmail94(driver, email, order_id, token=token)
            if not otp_ok:
                log(f"[{email}] Bỏ qua email này do không lấy được OTP / lỗi nhập OTP!", "WARN")
                return False

        msToken = ""
        try:
            for cookie in driver.get_cookies():
                if cookie['name'] == 'msToken':
                    msToken = cookie['value']
                    break
        except: pass

        link = None

        if join_link:
            if bday_status != "ALREADY_LOGGED_IN":
                ch.step5_join_team(driver, join_link)
            if not ch.wait_for_dashboard(driver):
                log(f"[{email}] Không thể join team (bị kẹt ở trang join) -> HỦY LƯU!", "ERR")
                return False

            uidname = ch.extract_uidname(driver)
            save_account(uidname, email, password, join_link, msToken)
            ch.record_registered_account(email, "signup_join_ok", capcut_password=password)
            log(f"ĐĂNG KÝ & JOIN THÀNH CÔNG! {email} (UID: {uidname})", "OK")
            return True
        else:
            if bday_status != "ALREADY_LOGGED_IN":
                ch.step5_open_capcut(driver)
            if not ch.wait_for_dashboard(driver):
                log(f"[{email}] Không vào được CapCut -> HỦY LƯU!", "ERR")
                return False

            uidname = ch.extract_uidname(driver)
            log(f"ĐĂNG NHẬP / ĐĂNG KÝ THÀNH CÔNG! {email} (UID: {uidname})", "OK")

            # Lưu tài khoản ngay sau khi tạo xong
            save_account(uidname, email, password, "", msToken)
            ch.record_registered_account(email, "signup_verified", capcut_password=password)

            # Đóng popup / survey
            log("Đang xử lý các popup sau đăng ký...", "INFO")
            ch.step_skip_role_survey(driver, timeout=10)
            ch.step_close_whats_new(driver, timeout=15)

            if get_link or save_trial_7day:
                link = ch.step_get_payment_link(driver, email, password, save_trial_7day=save_trial_7day)
                if link:
                    logout_ok = ch.close_checkout_and_logout(driver, email)
                    if not logout_ok:
                        log(f"[{email}] ⚠️ Chưa xác nhận đăng xuất được! Đóng tab để tránh lag máy.", "WARN")
                    else:
                        log(f"[{email}] ✅ Đã lưu link và đăng xuất thành công -> Đóng tab.", "OK")
                    should_keep_open = False
                else:
                    log(f"[{email}] ⚠️ Chưa lưu được link checkout! Đóng tab để tránh lag máy.", "WARN")
                    should_keep_open = False

            return True

    except Exception as e:
        log(f"[{email if 'email' in locals() else 'Acc'}] Lỗi trong quá trình đăng ký: {e}", "ERR")
        return False
    finally:
        if driver and not should_keep_open:
            try:
                if hasattr(driver, '_proxy_relay') and driver._proxy_relay:
                    driver._proxy_relay.stop()
                if driver in ACTIVE_DRIVERS:
                    ACTIVE_DRIVERS.remove(driver)
                driver.quit()
            except Exception:
                pass

