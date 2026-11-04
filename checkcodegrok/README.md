# Grok Auto Link Opener Pro (v3.0)

Extension chuyên dụng **Tự động nhận link Grok Referral từ Tool Python ngầm và mở link trên tab Grok**.

---

### 🌟 Ưu điểm vượt trội:
- **HOÀN TOÀN KHÔNG CẦN ĐĂNG NHẬP X.COM:**
  - Tool Python (`x_grok_hunter.py` / Web UI) đã chạy ngầm và làm toàn bộ việc quét X.com.
  - Các profile Chrome chỉ cần cài extension này và **đăng nhập Grok**.
  - Không lo bị checkpoint X, không ngốn RAM mở tab tìm kiếm.
- **Tốc độ mở siêu tốc:**
  - Khi Tool Python bắt được mã mới (<15m), mã lập tức được phát thẳng tới tất cả các profile Chrome đang mở Grok qua Relay/Server.
  - Extension tự động điều hướng tab Grok sang: `https://grok.com/refer/bot?code=...` để húp ưu đãi.
- **Có nút Test trực tiếp:** Trong popup có nút **🧪 Test mở thử link** để bạn kiểm tra xem tab Grok có tự nhảy link chuẩn xác chưa.

---

### 🚀 Hướng dẫn sử dụng:

1. **Khởi động Relay:**
   - Trên Mac: Bấm đúp file `start-relay.command` (hoặc chạy `./start-relay.sh`).
   - Trên Windows: Bấm đúp file `START-RELAY.cmd`.
2. **Cài Extension vào Profile Chrome / GPM:**
   - Vào `chrome://extensions` → Bật **Developer mode** → Bấm **Load unpacked**.
   - Chọn thư mục: `checkcodegrok`.
3. **Mở tab Grok:**
   - Mở sẵn 1 tab `https://grok.com/` và đăng nhập tài khoản Grok của profile đó.
   - Bấm vào icon Extension → Bấm **📌 Ghim tab Grok đang mở** (hoặc để mặc định tự chọn).
4. **Bật Tool Python:**
   - Bật **Săn code ngầm** trên Web UI (tab Grok) hoặc chạy terminal `python3 run_x_hunter.py --headless`.
   - Xong! Mỗi khi Tool Python bắt được mã mới, tất cả profile sẽ tự động nhảy vào link referral để nhận ưu đãi!
