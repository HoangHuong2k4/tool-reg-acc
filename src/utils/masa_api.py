import time
import os
import requests
import threading
import json
import re

MASA_PENDING_TASKS = {}
MASA_POLLER_STARTED = False
MASA_LOCK = threading.Lock()

def find_status_for_task(data, tid):
    """Đệ quy tìm kiếm trạng thái (status) của một task_id trong JSON trả về."""
    if isinstance(data, dict):
        if str(data.get("task_id")) == str(tid) or str(data.get("id")) == str(tid):
            return str(data.get("status", "")).upper()
        for v in data.values():
            s = find_status_for_task(v, tid)
            if s: return s
    elif isinstance(data, list):
        for item in data:
            s = find_status_for_task(item, tid)
            if s: return s
    return None

def extract_task_id(data):
    """Tìm task_id đầu tiên trong JSON trả về của API submissions."""
    if isinstance(data, dict):
        if "task_id" in data and data["task_id"]:
            return str(data["task_id"])
        if "id" in data and data["id"]:
            return str(data["id"])
        for v in data.values():
            s = extract_task_id(v)
            if s: return s
    elif isinstance(data, list):
        for item in data:
            s = extract_task_id(item)
            if s: return s
    return None

def start_masa_poller(masa_token, send_telegram_func):
    global MASA_POLLER_STARTED
    with MASA_LOCK:
        if MASA_POLLER_STARTED: return
        MASA_POLLER_STARTED = True
        
    def poller():
        query_url = "https://plus.masa168.cc/api/v1/external/producer/task-statuses/query"
        while True:
            time.sleep(10)
            with MASA_LOCK:
                task_ids = list(MASA_PENDING_TASKS.keys())
            
            if not task_ids:
                continue
                
            headers = {
                "Authorization": f"Bearer {masa_token}",
                "Content-Type": "application/json"
            }
            try:
                res = requests.post(query_url, headers=headers, json={"task_ids": task_ids[:100]}, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    with MASA_LOCK:
                        for tid in task_ids[:100]:
                            if tid not in MASA_PENDING_TASKS: continue
                            info = MASA_PENDING_TASKS[tid]
                            
                            status = find_status_for_task(data, tid)
                            if status:
                                if status in ["SUCCESS", "SUCCEEDED", "COMPLETED", "DONE"]:
                                    info["log_func"](f"✅ Masa168 báo: THANH TOÁN THÀNH CÔNG cho {info['email']}!", "OK")
                                    send_telegram_func(f"✅ DONE ACC: {info['email']}\nMasa168 đã thanh toán thành công!")
                                    
                                    # Kích hoạt đổi thẻ tự động trên trình duyệt đang mở
                                    try:
                                        info["log_func"](f"⚡ Tự động lấy thẻ và chuyển sang Stripe Billing Portal...", "INFO")
                                        requests.post("http://127.0.0.1:5050/api/grok/billing/active_tab", json={"email": info['email']}, timeout=5)
                                    except Exception as ex:
                                        info["log_func"](f"⚠️ Lỗi kích hoạt đổi thẻ tự động: {str(ex)}", "WARN")
                                        
                                    del MASA_PENDING_TASKS[tid]
                                elif status in ["FAIL", "FAILED", "ERROR", "TIMEOUT"]:
                                    info["log_func"](f"❌ Masa168 báo: THANH TOÁN THẤT BẠI cho {info['email']}!", "ERR")
                                    send_telegram_func(
                                        f"❌ Masa168 báo THANH TOÁN THẤT BẠI!\n"
                                        f"Email: {info['email']}\nTask ID: {tid}\n"
                                        f"👉 Link NicePay để quét tay:\n{info['url']}"
                                    )
                                    del MASA_PENDING_TASKS[tid]
                            
                            if tid in MASA_PENDING_TASKS and time.time() - info["added_time"] > 300:
                                info["log_func"](f"❌ Masa168 QUÁ THỜI GIAN chờ thanh toán cho {info['email']}", "ERR")
                                send_telegram_func(
                                    f"⏰ Masa168 QUÁ THỜI GIAN chờ (5 phút)!\n"
                                    f"Email: {info['email']}\nTask ID: {tid}\n"
                                    f"👉 Link NicePay để quét tay:\n{info['url']}"
                                )
                                del MASA_PENDING_TASKS[tid]
                else:
                    print("Masa168 API query failed:", res.status_code, res.text)
            except Exception as e:
                print("Masa168 poller exception:", str(e))
                
    threading.Thread(target=poller, daemon=True).start()

def submit_to_masa_api(url, email, masa_token, send_telegram_func, log_func):
    # Luôn gửi link NicePay qua Telegram trước, dù có token hay không
    masked_email = email[:3] + "***" + email[email.find("@"):] if "@" in email else email[:3] + "***"
    send_telegram_func(
        f"💳 Link thanh toán NicePay:\nEmail: {masked_email}\n{url}"
    )

    if not masa_token:
        log_func("⚠️ Không có MASA_TOKEN — đã gửi link NicePay qua Telegram để quét tay!", "WARN")
        return
        
    start_masa_poller(masa_token, send_telegram_func)
    
    api_url = "https://plus.masa168.cc/api/v1/external/producer/submissions"
    headers = {
        "Authorization": f"Bearer {masa_token}",
        "Idempotency-Key": f"task_{int(time.time())}_{os.urandom(4).hex()}",
        "Content-Type": "application/json"
    }
    data = {
        "channel": "kakao",
        "urls": [url]
    }
    try:
        res = requests.post(api_url, headers=headers, json=data, timeout=10)
        if res.status_code in [200, 201]:
            res_data = res.json()
            task_id = extract_task_id(res_data)
            if task_id:
                log_func(f"✅ Đã gửi link thanh toán lên Masa168 (Task: {task_id}). Đang chờ kết quả...", "OK")
                with MASA_LOCK:
                    MASA_PENDING_TASKS[task_id] = {
                        "url": url,
                        "email": email,
                        "log_func": log_func,
                        "added_time": time.time()
                    }
            else:
                log_func(f"✅ Đã gửi link lên Masa168 thành công, nhưng không tìm thấy Task ID để chờ. RAW: {res.text}", "WARN")
        else:
            log_func(f"❌ Lỗi khi gửi Masa168 (HTTP {res.status_code}): {res.text}", "ERR")
            send_telegram_func(
                f"❌ Lỗi gửi Masa168 (HTTP {res.status_code})!\n"
                f"Email: {masked_email}\n"
                f"👉 Link NicePay để quét tay đã được gửi ở trên."
            )
    except Exception as e:
        log_func(f"❌ Lỗi kết nối Masa168: {str(e)}", "ERR")
        send_telegram_func(
            f"❌ Lỗi kết nối Masa168: {str(e)}\n"
            f"Email: {masked_email}\n"
            f"👉 Link NicePay để quét tay đã được gửi ở trên."
        )
