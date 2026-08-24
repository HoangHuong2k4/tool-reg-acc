#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module Tự Động Đăng Ký CapCut trên GPM-Login Profiles
Tích hợp GPM-Login API (v3 / v2)
"""

import time
import sys
import os
import requests
import json
import concurrent.futures
import threading
from datetime import datetime

ACTIVE_DRIVERS = []
GLOBAL_STOP_EVENT = threading.Event()

def log(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    icons = {"OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "INFO": "📌"}
    print(f"[CapCut-GPM] [{now}] {icons.get(level,'📌')} {msg}")

class GpmClient:
    def __init__(self, api_url="http://127.0.0.1:19995"):
        self.api_url = api_url.rstrip("/")

    def list_profiles(self):
        """Lấy danh sách profile từ GPM API (thử v3 trước, sau đó v2)."""
        endpoints = [
            f"{self.api_url}/api/v3/profiles",
            f"{self.api_url}/v2/profiles",
            f"{self.api_url}/api/v3/profiles?mode=all"
        ]
        for url in endpoints:
            try:
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    profiles = []
                    if isinstance(data, list):
                        profiles = data
                    elif isinstance(data, dict):
                        if "data" in data and isinstance(data["data"], list):
                            profiles = data["data"]
                        elif "profiles" in data and isinstance(data["profiles"], list):
                            profiles = data["profiles"]
                    
                    parsed = []
                    for p in profiles:
                        pid = str(p.get("id") or p.get("profile_id") or p.get("Id") or "")
                        name = str(p.get("name") or p.get("profile_name") or p.get("Name") or pid)
                        raw_proxy = str(p.get("raw_proxy") or p.get("proxy") or p.get("Proxy") or "")
                        if pid:
                            parsed.append({
                                "id": pid,
                                "name": name,
                                "raw_proxy": raw_proxy,
                                "created_at": p.get("created_at") or p.get("created_time") or ""
                            })
                    if parsed:
                        return {"success": True, "profiles": parsed}
            except Exception as e:
                log(f"Lỗi thử endpoint {url}: {e}", "WARN")
                continue
        return {"success": False, "error": "Không thể kết nối đến GPM API hoăc không tìm thấy profiles!", "profiles": []}

    def create_profile(self, name, group_id="", raw_proxy=""):
        """Tạo 1 profile GPM mới hoàn toàn."""
        endpoints = [
            f"{self.api_url}/api/v3/profiles/create",
            f"{self.api_url}/api/v1/profiles/create",
        ]
        payload = {
            "name": name,
            "browser_type": "chrome",
        }
        if group_id:
            payload["group_id"] = group_id
        if raw_proxy:
            payload["raw_proxy"] = raw_proxy
        for url in endpoints:
            try:
                res = requests.post(url, json=payload, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("success"):
                        prof_data = data.get("data", {})
                        pid = ""
                        if isinstance(prof_data, dict):
                            pid = str(prof_data.get("id") or prof_data.get("profile_id") or "")
                        else:
                            pid = str(prof_data)
                        if pid:
                            return {"success": True, "profile_id": pid}
            except Exception as e:
                log(f"Lỗi tạo profile {url}: {e}", "WARN")
                continue
        return {"success": False, "error": f"Không thể tạo profile GPM mới: {name}"}

    def start_profile(self, profile_id, win_pos=None, win_size=None):
        """Mở 1 profile GPM và nhận về selenium remote debug address."""
        params = {"id": profile_id}
        if win_pos:
            params["win_pos"] = win_pos
        if win_size:
            params["win_size"] = win_size

        urls = [
            (f"{self.api_url}/api/v3/profiles/start", params),
            (f"{self.api_url}/v2/start", params),
            (f"{self.api_url}/api/v3/profiles/start?id={profile_id}", {})
        ]
        
        for url, p in urls:
            try:
                res = requests.get(url, params=p, timeout=20)
                if res.status_code == 200:
                    data = res.json()
                    address = None
                    driver_path = None
                    if data.get("success") or data.get("status") == 1 or data.get("status") is True:
                        info = data.get("data") or data
                        address = info.get("selenium_remote_debug_address") or info.get("remote_debug_address") or info.get("debugger_address")
                        driver_path = info.get("driver_path") or info.get("chromedriver_path")
                    elif isinstance(data, dict):
                        address = data.get("selenium_remote_debug_address") or data.get("remote_debug_address")
                        driver_path = data.get("driver_path")

                    if address:
                        return {"success": True, "remote_debug_address": address, "driver_path": driver_path, "raw": data}
            except Exception as e:
                log(f"Lỗi mở profile {profile_id} tại {url}: {e}", "WARN")
                continue
        return {"success": False, "error": f"Không thể mở GPM Profile {profile_id}!"}

    def close_profile(self, profile_id):
        """Đóng 1 profile GPM."""
        urls = [
            f"{self.api_url}/api/v3/profiles/close?id={profile_id}",
            f"{self.api_url}/v2/stop?id={profile_id}"
        ]
        for url in urls:
            try:
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    return {"success": True}
            except Exception:
                pass
        return {"success": False, "error": f"Không thể đóng profile {profile_id}"}


def setup_gpm_driver(remote_debug_address, driver_path=None):
    """Kết nối Selenium tới trình duyệt Chrome GPM đã mở qua remote_debug_address."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    options = Options()
    options.add_experimental_option("debuggerAddress", remote_debug_address)
    
    if driver_path and os.path.exists(driver_path):
        service = Service(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    ACTIVE_DRIVERS.append(driver)
    return driver


def register_one_gpm_account(profile_id, gpm_api_url="http://127.0.0.1:19995", mail_type="hotmail", mode=1, join_link="", mail_api_source="dongvanfb", get_link=False, index=1, batch_size=1):
    """Quy trình đăng ký 1 tài khoản CapCut trên 1 GPM Profile."""
    if GLOBAL_STOP_EVENT.is_set():
        log(f"Đã có lệnh dừng, bỏ qua GPM profile {profile_id}", "WARN")
        return False

    log(f"[{index}] 🚀 Khởi chạy GPM Profile ID: {profile_id}", "INFO")
    gpm = GpmClient(gpm_api_url)

    if profile_id in ("create", "new", "create_new"):
        create_res = gpm.create_profile(f"[CapCut_{index}] Auto_Reg_{datetime.now().strftime('%M%S')}")
        if create_res.get("success"):
            profile_id = create_res.get("profile_id")
            log(f"[{index}] ✅ Đã tự động tạo Profile GPM mới: {profile_id}", "OK")
        else:
            log(f"[{index}] ❌ Không thể tự động tạo Profile GPM mới: {create_res.get('error')}", "ERR")
            return False
    
    # Mở GPM profile
    start_res = gpm.start_profile(profile_id)
    if not start_res.get("success"):
        log(f"[{index}] ❌ Không mở được GPM profile {profile_id}: {start_res.get('error')}", "ERR")
        return False

    remote_debug_address = start_res.get("remote_debug_address")
    driver_path = start_res.get("driver_path")
    log(f"[{index}] ✅ Đã mở GPM Profile {profile_id} -> Debug Address: {remote_debug_address}", "OK")

    driver = None
    try:
        driver = setup_gpm_driver(remote_debug_address, driver_path)
        
        import src.bots.capcut_hotmail as bot_hotmail
        import src.bots.capcut_domain as bot_domain
        bot_mod = bot_hotmail if mail_type == "hotmail" else bot_domain

        # Lấy mail từ queue
        if mail_type == "hotmail":
            if not hasattr(bot_hotmail, "HOTMAIL_QUEUE") or bot_hotmail.HOTMAIL_QUEUE.empty():
                log(f"[{index}] ❌ Hết Hotmail trong hàng đợi!", "ERR")
                return False
            acc = bot_hotmail.HOTMAIL_QUEUE.get_nowait()
            email, password, refresh_token, client_id = acc
            log(f"[{index}] 📌 Mail: {email}", "INFO")
        else:
            if not hasattr(bot_domain, "DOMAIN_MAIL_QUEUE") or bot_domain.DOMAIN_MAIL_QUEUE.empty():
                log(f"[{index}] ❌ Hết Mail Domain trong hàng đợi!", "ERR")
                return False
            acc = bot_domain.DOMAIN_MAIL_QUEUE.get_nowait()
            email = acc.get("email")
            password = acc.get("password", "Capcut123@")
            refresh_token = ""
            client_id = ""
            log(f"[{index}] 📌 Mail Domain: {email}", "INFO")

        # Bước 0: Dismiss TOS
        log(f"[{index}] 📌 Bước 0: Mở CapCut & bỏ qua TOS...", "INFO")
        bot_mod.step0_dismiss_tos(driver)

        # Bước 0b: Bấm nút Email
        bot_mod.step0b_click_email_button(driver)

        # Bước 1: Nhập email
        log(f"[{index}] 📌 Bước 1: Nhập email {email}...", "INFO")
        if not bot_mod.step1_enter_email(driver, email):
            log(f"[{index}] ❌ Lỗi nhập email", "ERR")
            if mail_type == "hotmail":
                bot_hotmail.HOTMAIL_QUEUE.put(acc)
            return False

        # Bước 2: Nhập password
        log(f"[{index}] 📌 Bước 2: Nhập mật khẩu...", "INFO")
        if not bot_mod.step2_enter_password(driver, password):
            log(f"[{index}] ❌ Lỗi nhập mật khẩu", "ERR")
            return False

        # Bước 3: Điền ngày sinh
        log(f"[{index}] 📌 Bước 3: Điền ngày sinh...", "INFO")
        bot_mod.step3_enter_birthday(driver)

        # Bước 4: Nhận và điền OTP
        log(f"[{index}] 📌 Bước 4: Chờ và nhập OTP...", "INFO")
        if mail_type == "hotmail":
            otp_ok = bot_hotmail.step4_enter_otp(driver, email, password, refresh_token, client_id, mail_api_source=mail_api_source)
        else:
            otp_ok = bot_domain.step4_enter_otp(driver, email)

        if not otp_ok:
            log(f"[{index}] ❌ Lỗi OTP cho {email}", "ERR")
            return False

        # Bước 5: Đăng ký thành công & vào Dashboard
        uidname = bot_mod.extract_uidname(driver)
        log(f"[{index}] ✅ ĐĂNG KÝ THÀNH CÔNG! {email} (UID: {uidname}) [GPM Profile: {profile_id}]", "OK")

        bot_mod.step5_open_capcut(driver)
        bot_mod.step_skip_role_survey(driver)
        bot_mod.step_close_whats_new(driver)

        # Mode 2: Join Team
        if mode == 2 and join_link:
            log(f"[{index}] 📌 Mode 2: Join team {join_link}...", "INFO")
            bot_mod.step5_join_team(driver, join_link)

        # Lưu tài khoản
        if hasattr(bot_mod, "save_account"):
            bot_mod.save_account(uidname, email, password, join_link if mode == 2 else "")

        # Đánh dấu đã dùng hotmail
        if mail_type == "hotmail" and hasattr(bot_mod, "mark_hotmail_used"):
            bot_mod.mark_hotmail_used(acc)

        # Mode 3 hoặc get_link: Lấy link thanh toán / join
        if (mode == 3 or get_link) and hasattr(bot_mod, "step_get_payment_link"):
            log(f"[{index}] 📌 Mode 3: Đang lấy link...", "INFO")
            link_ok = bot_mod.step_get_payment_link(driver, email, password)
            if link_ok:
                log(f"[{index}] ✅ Đã lấy link thành công cho {email}!", "OK")
            else:
                log(f"[{index}] ⚠️ Không lấy được link cho {email}", "WARN")

        return True

    except Exception as e:
        log(f"[{index}] ❌ Lỗi ngoại lệ trên GPM profile {profile_id}: {e}", "ERR")
        return False
    finally:
        if driver:
            try:
                ACTIVE_DRIVERS.remove(driver)
            except ValueError:
                pass


def register_gpm_multiple(profile_ids, threads=1, mail_type="hotmail", mode=1, join_link="", mail_api_source="dongvanfb", gpm_api_url="http://127.0.0.1:19995", get_link=False):
    """Chạy đa luồng tự động đăng ký CapCut trên danh sách GPM Profile IDs."""
    total_profiles = len(profile_ids)
    if total_profiles == 0:
        log("Không có GPM Profile ID nào được chọn!", "WARN")
        return {"ok": 0, "fail": 0}

    log(f"🚀 Bắt đầu Reg CapCut trên {total_profiles} GPM Profiles với {threads} luồng song song...", "INFO")
    
    GLOBAL_STOP_EVENT.clear()
    succeeded = 0
    failed = 0
    lock = threading.Lock()

    def gpm_worker(p_id, idx):
        nonlocal succeeded, failed
        if GLOBAL_STOP_EVENT.is_set():
            with lock:
                failed += 1
            return
        
        ok = register_one_gpm_account(
            profile_id=p_id,
            gpm_api_url=gpm_api_url,
            mail_type=mail_type,
            mode=mode,
            join_link=join_link,
            mail_api_source=mail_api_source,
            get_link=get_link,
            index=idx,
            batch_size=threads
        )
        with lock:
            if ok:
                succeeded += 1
            else:
                failed += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(gpm_worker, pid, i + 1) for i, pid in enumerate(profile_ids)]
        concurrent.futures.wait(futures)

    log(f"🏁 Hoàn tất: {succeeded} thành công / {failed} thất bại!", "OK")
    return {"ok": succeeded, "fail": failed}
