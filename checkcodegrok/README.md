# 🎯 Grok Code Hunter (Extension Chrome)

Extension Chrome chuyên dụng để **săn mã giới thiệu Grok Bot (Referral Code)** trực tiếp từ trang Live Search của **X.com (Twitter)** và **tự động gửi thông báo tức thì về Telegram**.

---

## 🌟 Tính Năng Nổi Bật

1. **Tự động bắt mã Live:**
   - Liên tục quét các bài đăng mới nhất trên trang tìm kiếm X.com:
     `https://x.com/search?q=https%3A%2F%2Fgrok.com%2Frefer%2Fbot%3Fcode%3D&src=typed_query&f=live`
   - Nhận diện chính xác định dạng mã Grok referral (`code=...` hoặc `https://grok.com/refer/bot?code=...`).

2. **Gửi tin nhắn Telegram tự động & ngay lập tức:**
   - Ngay khi phát hiện bài đăng mới có mã chưa từng xuất hiện, extension sẽ lập tức bắn tin nhắn về Telegram kèm:
     - 🔑 **Mã Referral**
     - 🔗 **Link đăng ký trực tiếp**
     - 👤 **Tên và @handle người đăng**
     - 📝 **Trích đoạn nội dung bài viết**
     - 🐦 **Link dẫn thẳng tới Tweet gốc**
     - ⏰ **Thời gian bắt được**

3. **Cơ chế chống gửi trùng (Deduplication):**
   - Lưu trữ danh sách mã và ID bài viết đã quét trong bộ nhớ cục bộ (`chrome.storage.local`), đảm bảo không spam tin nhắn trùng lặp.

4. **Tự động tải lại trang (Auto-Reload Countdown):**
   - Đếm ngược theo chu kỳ tùy chỉnh (mặc định 45 giây) và tự động F5 trang để nạp các tweet Live mới nhất từ máy chủ X.com.
   - Có thể tạm dừng (Pause) hoặc tải lại ngay lập tức (Reload Now).

5. **Widget nổi tiện lợi trên giao diện X.com:**
   - Hiển thị bảng điều khiển mini ngay góc trên bên phải trang X.com với bộ đếm ngược, số mã đã bắt trong phiên và nút copy mã nhanh.

---

## 🚀 Hướng Dẫn Cài Đặt (Chỉ Mất 30 Giây)

1. Mở trình duyệt Chrome (hoặc Brave, Edge, Cốc Cốc, v.v.).
2. Truy cập vào đường dẫn:
   ```text
   chrome://extensions/
   ```
3. Bật công tắc **"Chế độ cho nhà phát triển" (Developer mode)** ở góc trên bên phải màn hình.
4. Bấm vào nút **"Tải tiện ích đã giải nén" (Load unpacked)** ở góc trên bên trái.
5. Chọn thư mục:
   ```text
   /Users/huong/TaiNguyen/capcut-regaccc/checkcodegrok
   ```
6. Extension sẽ xuất hiện trên thanh công cụ của Chrome với tên **Grok Code Hunter**!

---

## ⚙️ Hướng Dẫn Sử Dụng

1. Bấm vào biểu tượng extension trên thanh công cụ:
   - Token Telegram và Chat ID đã được **điền sẵn mặc định** theo cấu hình của bạn:
     - **Bot Token:** `8855096263:AAHuhzdQVm_ST0oT-hpCJcHWyuYsTOfsWcw`
     - **Chat ID:** `7353915691, 1007974270`
   - Bấm **"📩 Test Telegram"** để kiểm tra tin nhắn thử nghiệm.
2. Bấm nút màu xanh **"🌐 Mở trang Live Search X.com"**.
3. Tab tìm kiếm X.com sẽ mở ra:
   - Hãy đăng nhập tài khoản X.com của bạn (nếu chưa đăng nhập).
   - Bạn sẽ thấy widget **Grok Hunter** màu xanh ở góc trên bên phải.
   - Cứ để tab đó hoạt động, extension sẽ tự động săn code và gửi tin nhắn về Telegram mỗi khi có người chia sẻ mã mới!

