#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import os
import sys
import re
import concurrent.futures

# Xác định PROJECT_ROOT
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import module capcut_hotmail
try:
    import src.bots.capcut_hotmail as capcut
except Exception as e:
    print(f"Lỗi khi import src.bots.capcut_hotmail: {e}")
    sys.exit(1)

def extract_pay_link(line):
    """Trích xuất link thanh toán từ 1 dòng (hỗ trợ tab, space, pipe hoặc URL trần)."""
    parts = line.strip().split("\t")
    for part in parts:
        if ("cashier" in part or "pipopay" in part) and part.startswith("http"):
            return part.strip()
    match = re.search(r'https?://[^\s]+(?:cashier|pipopay)[^\s]*', line)
    if match:
        return match.group(0).strip()
    match_any = re.search(r'https?://[^\s]+', line)
    if match_any:
        return match_any.group(0).strip()
    return None

def main():
    print(f"""
{capcut.C.BOLD}{capcut.C.INFO}
╔══════════════════════════════════════════════════════╗
║             TOOL MỞ LINK THANH TOÁN (PAY)            ║
╚══════════════════════════════════════════════════════╝
{capcut.C.RST}""")
    
    # Ưu tiên data/trial_7day.txt hoặc đối số dòng lệnh nếu truyền vào
    default_file = os.path.join(PROJECT_ROOT, "data", "trial_7day.txt")
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    elif os.path.exists(default_file):
        input_file = default_file
    elif os.path.exists("trial_7day.txt"):
        input_file = "trial_7day.txt"
    elif os.path.exists(os.path.join(PROJECT_ROOT, "data", "accounts.txt")):
        input_file = os.path.join(PROJECT_ROOT, "data", "accounts.txt")
    elif os.path.exists("accounts.txt"):
        input_file = "accounts.txt"
    else:
        input_file = default_file

    done_file = os.path.join(os.path.dirname(input_file), "done.txt")
    if not os.path.exists(os.path.dirname(done_file)):
        done_file = os.path.join(PROJECT_ROOT, "data", "done.txt")

    if not os.path.exists(input_file):
        print(f"{capcut.C.ERR}Không tìm thấy file nguồn: {input_file}!{capcut.C.RST}")
        return
        
    lines_info = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            link = extract_pay_link(line)
            if link:
                lines_info.append(line)
                    
    if not lines_info:
        print(f"{capcut.C.ERR}Không tìm thấy link thanh toán nào trong {input_file}!{capcut.C.RST}")
        return
        
    print(f"{capcut.C.OK}File: {input_file}{capcut.C.RST}")
    print(f"{capcut.C.OK}Tìm thấy {len(lines_info)} tài khoản có link thanh toán.{capcut.C.RST}")
    
    batch_str = input(f"{capcut.C.WARN}Nhập số link muốn mở cùng lúc (mặc định: 4): {capcut.C.RST}").strip()
    batch_size = int(batch_str) if batch_str.isdigit() and int(batch_str) > 0 else 4

    use_proxy_str = input(f"{capcut.C.WARN}Có sử dụng Proxy không? (y/n, mặc định: y): {capcut.C.RST}").strip().lower()
    use_proxy = False if use_proxy_str == 'n' else True
    
    capcut.log(f"Sẽ chạy từng đợt, mỗi đợt {batch_size} tab (Proxy: {'BẬT' if use_proxy else 'TẮT'}).", "INFO")
    
    while lines_info:
        current_batch = lines_info[:batch_size]
        lines_info = lines_info[batch_size:]
        
        capcut.log(f"Đang xử lý đợt mới ({len(current_batch)} link)...", "WARN")
        active_drivers = []
        
        def worker(i, line_data):
            if use_proxy:
                time.sleep((i % batch_size) * 2.5) # Chờ để proxy không bị get dồn dập
            link = extract_pay_link(line_data)
            if not link:
                capcut.log(f"❌ Không trích xuất được link từ dòng #{i+1}", "ERR")
                return None
            try:
                capcut.log(f"Đang chuẩn bị trình duyệt cho link #{i+1}...", "INFO")
                driver = capcut.setup_driver(
                    index=i+1, 
                    keep_open=True, 
                    use_api_proxy=use_proxy, 
                    batch_size=batch_size, 
                    use_proxy=use_proxy, 
                    predefined_proxy=None,
                    incognito=True
                )
                driver.get(link)
                capcut.log(f"✅ Đã mở link #{i+1} thành công!", "OK")
                return driver
            except Exception as e:
                capcut.log(f"❌ Lỗi mở link #{i+1}: {e}", "ERR")
                return None
                
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = [executor.submit(worker, i, current_batch[i]) for i in range(len(current_batch))]
            for future in concurrent.futures.as_completed(futures):
                d = future.result()
                if d:
                    active_drivers.append(d)
                    
        print(f"\n{capcut.C.OK}✅ Đã mở xong đợt này! Bạn hãy tiến hành thanh toán trên các tab.{capcut.C.RST}")
        
        choice = input(f"{capcut.C.WARN}👉 Bấm Enter khi ĐÃ PAY XONG để chuyển {len(current_batch)} acc sang {os.path.basename(done_file)} và chạy tiếp (gõ 'q' để Thoát): {capcut.C.RST}").strip().lower()
        
        capcut.log("Đang tự động dọn dẹp các tab cũ và cập nhật file...", "INFO")
        
        # Đóng các trình duyệt của đợt này
        for d in active_drivers:
            try: d.quit()
            except: pass
            
        # Chuyển acc sang done.txt
        try:
            with open(done_file, "a", encoding="utf-8") as f:
                for line in current_batch:
                    f.write(line if line.endswith("\n") else line + "\n")
        except Exception as e:
            capcut.log(f"Lỗi ghi {done_file}: {e}", "ERR")
                
        # Xóa khỏi input_file
        try:
            done_links = set(extract_pay_link(l) for l in current_batch if extract_pay_link(l))
            with open(input_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            with open(input_file, "w", encoding="utf-8") as f:
                for line in all_lines:
                    lnk = extract_pay_link(line)
                    if (lnk and lnk in done_links) or (line.strip() in [c.strip() for c in current_batch]):
                        continue
                    f.write(line)
        except Exception as e:
            capcut.log(f"Lỗi cập nhật {input_file}: {e}", "ERR")
        
        print(f"{capcut.C.OK}Đã chuyển {len(current_batch)} acc sang {done_file}!{capcut.C.RST}\n")
        
        if choice == 'q':
            break

    print(f"{capcut.C.OK}Đã hoàn tất toàn bộ link!{capcut.C.RST}")

if __name__ == "__main__":
    main()

