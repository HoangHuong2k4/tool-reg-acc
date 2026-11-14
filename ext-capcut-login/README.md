# 🚀 CapCut Auto Login Extension

Extension Chrome (Manifest V3) tự động đăng nhập siêu tốc tài khoản CapCut từ danh sách hoặc đồng bộ trực tiếp từ Web Tool (Port 5050).

---

## ✨ Tính Năng Nổi Bật

1. **⚡ Đồng bộ 1 chạm từ Web Tool (Port 5050)**:
   - Tự động lấy danh sách tài khoản vừa tạo thành công từ tool CapCut đang chạy (`http://127.0.0.1:5050/api/capcut/accounts`), không cần copy/paste thủ công.
2. **📋 Hỗ trợ nhập hàng loạt thủ công (Bulk Import)**:
   - Hỗ trợ mọi định dạng: `email|pass`, `email----pass`, `email:pass`, hoặc format file `data/accounts.txt` của tool (`uid \t email \t pass \t link \t msToken`).
3. **🚀 Tự động đăng nhập siêu tốc (Auto Fill & Submit)**:
   - Tự động vượt qua popup điều khoản (Terms of Service).
   - Tự động bấm nút "Tiếp tục bằng email" (Continue with email).
   - Tự động điền Email và bấm Tiếp tục.
   - Tự động điền Mật khẩu và bấm Đăng nhập.
   - Tự động bỏ qua các popup khảo sát (Skip role survey) và thông báo mới sau khi vào.
4. **🎈 Widget nổi tiện lợi trên trang CapCut**:
   - Hiển thị trực tiếp tài khoản đang chọn ở góc dưới màn hình `capcut.com`.
   - Có nút **[🚀 Đăng nhập ngay]** và **[⏭️ Đổi Acc]** tiện lợi.
   - Có thể kéo thả di chuyển hoặc thu gọn tùy ý.
5. **🔢 Quản lý hàng đợi & Đánh dấu tài khoản**:
   - Đánh dấu tài khoản đã đăng nhập (`used`), hiển thị số lượng tài khoản còn lại ngay trên icon Extension (Badge).
   - Tự động chuyển sang tài khoản kế tiếp khi đăng nhập xong.

---

## 🛠️ Hướng Dẫn Cài Đặt (Vào Chrome / Edge / Cốc Cốc / GPM)

1. Mở trình duyệt, truy cập đường dẫn: `chrome://extensions/`
2. Bật công tắc **"Chế độ dành cho nhà phát triển" (Developer mode)** ở góc trên bên phải.
3. Bấm vào nút **"Tải tiện ích đã giải nén" (Load unpacked)**.
4. Chọn thư mục:
   ```
   /Users/huong/TaiNguyen/capcut-regaccc/ext-capcut-login
   ```
5. Ghim (Pin) biểu tượng **CapCut Auto Login** lên thanh công cụ trình duyệt để tiện sử dụng.

---

## 📖 Cách Sử Dụng

### Cách 1: Đồng bộ từ Web Tool (Khuyên dùng)
1. Mở Extension trên thanh công cụ.
2. Chuyển sang tab **"📋 Quản lý Acc"**.
3. Bấm nút **"🔄 Lấy từ Web Tool (Port 5050)"** -> Toàn bộ tài khoản vừa reg sẽ được nạp vào.
4. Chuyển về tab **"🚀 Đăng nhập"** và bấm **"🚀 Mở CapCut & Đăng nhập ngay"**!

### Cách 2: Nhập danh sách tài khoản thủ công
1. Vào tab **"📋 Quản lý Acc"**.
2. Dán danh sách vào ô văn bản (VD: `abc@outlook.com|capcut123`).
3. Bấm **"📥 Thêm vào danh sách"**.
4. Vào `https://www.capcut.com/vi-vn/login`, extension sẽ tự động điền và đăng nhập!

