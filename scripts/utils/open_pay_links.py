#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import os
import sys
import importlib.util
import concurrent.futures

# Import file main để dùng lại hàm setup_driver và proxy
try:
    spec = importlib.util.spec_from_file_location("capcut_main", "auto_register_capcut-hotmail.py")
    capcut = importlib.util.module_from_spec(spec)
    sys.modules["capcut_main"] = capcut
    spec.loader.exec_module(capcut)
except Exception as e:
    print(f"Lỗi khi import auto_register_capcut-hotmail.py: {e}")
    sys.exit(1)

def main():
    print(f"""
{capcut.C.BOLD}{capcut.C.INFO}
╔══════════════════════════════════════════════════════╗
║             TOOL MỞ LINK THANH TOÁN (PROXY)          ║
╚══════════════════════════════════════════════════════╝
{capcut.C.RST}""")
    
    if not os.path.exists("accounts.txt"):
        print(f"{capcut.C.ERR}Không tìm thấy file accounts.txt!{capcut.C.RST}")
        return
        
    lines_info = []
    with open("accounts.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 4:
                link = parts[3]
                if "cashier" in link or "pipopay" in link:
                    lines_info.append(line)
                    
    if not lines_info:
        print(f"{capcut.C.ERR}Không có link thanh toán nào trong accounts.txt!{capcut.C.RST}")
        return
        
    print(f"{capcut.C.OK}Tìm thấy {len(lines_info)} tài khoản có link thanh toán.{capcut.C.RST}")
    
    batch_str = input(f"{capcut.C.WARN}Nhập số link muốn mở cùng lúc (vd: 4 hoặc 5): {capcut.C.RST}").strip()
    batch_size = int(batch_str) if batch_str.isdigit() and int(batch_str) > 0 else 4
    
    capcut.log(f"Sẽ chạy từng đợt, mỗi đợt {batch_size} tab.", "INFO")
    
    while lines_info:
        current_batch = lines_info[:batch_size]
        lines_info = lines_info[batch_size:]
        
        capcut.log(f"Đang xử lý đợt mới ({len(current_batch)} link)...", "WARN")
        active_drivers = []
        
        def worker(i, line_data):
            time.sleep((i % batch_size) * 2.5) # Chờ để proxy không bị get dồn dập
            link = line_data.strip().split("\t")[3]
            try:
                capcut.log(f"Đang lấy Proxy và mở trình duyệt cho link #{i+1}...", "INFO")
                # Gọi setup_driver với keep_open=True để giữ tab không tắt, và incognito=True
                driver = capcut.setup_driver(
                    index=i+1, 
                    keep_open=True, 
                    use_api_proxy=True, 
                    batch_size=batch_size, 
                    use_proxy=True, 
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
        
        choice = input(f"{capcut.C.WARN}👉 Bấm Enter khi ĐÃ PAY XONG để chuyển {len(current_batch)} acc sang done.txt và chạy đợt tiếp theo (gõ 'q' để Thoát): {capcut.C.RST}").strip().lower()
        
        capcut.log("Đang tự động dọn dẹp các tab cũ và cập nhật file...", "INFO")
        
        # Đóng các trình duyệt của đợt này
        for d in active_drivers:
            try: d.quit()
            except: pass
            
        # Chuyển acc sang done.txt
        with open("done.txt", "a", encoding="utf-8") as f:
            for line in current_batch:
                f.write(line)
                
        # Xóa khỏi accounts.txt (Đọc lại file để không làm mất các dòng không có link)
        try:
            with open("accounts.txt", "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            with open("accounts.txt", "w", encoding="utf-8") as f:
                for line in all_lines:
                    if line not in current_batch:
                        f.write(line)
        except Exception as e:
            capcut.log(f"Lỗi cập nhật accounts.txt: {e}", "ERR")
        
        print(f"{capcut.C.OK}Đã chuyển {len(current_batch)} acc sang done.txt!{capcut.C.RST}\n")
        
        if choice == 'q':
            break

    print(f"{capcut.C.OK}Đã hoàn tất toàn bộ link!{capcut.C.RST}")

if __name__ == "__main__":
    main()
