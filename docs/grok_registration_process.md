# Quy trình Tự Động Hóa Đăng Ký Grok & Lấy Offer SuperGrok (A-Z)

Tài liệu này mô tả chi tiết toàn bộ quy trình kỹ thuật và các bước thực thi của hệ thống auto đăng ký Grok (x.ai) và nhận ưu đãi SuperGrok hoàn toàn tự động bằng Python + Undetected ChromeDriver.

## 1. Chuẩn Bị & Khởi Tạo
- **Nguồn Email:** Hỗ trợ 2 loại là Hotmail (đọc qua API DongVanFB/MixMMO) hoặc Domain Catch-all.
- **Proxy:** Xoay proxy liên tục sau mỗi tài khoản hoặc batch để tránh bị ban IP (hỗ trợ ProxyQuick, ProxyXoay, v.v.).
- **Trình Duyệt:** Khởi chạy `undetected-chromedriver` để bypass các cơ chế chống bot của Cloudflare.
- **Ngôn ngữ (Locale):** Ép trình duyệt sử dụng ngôn ngữ Hàn Quốc (`ko-KR`) bằng argument `--lang=ko-KR` để hiển thị cổng thanh toán KakaoPay.

## 2. Các Bước Đăng Ký x.ai
1. **Truy cập:** Mở trang `https://grok.com` (hoặc `accounts.x.ai/sign-up`).
2. **Bước 1 (Bắt đầu):** Click vào nút **"Sign up with email"**.
3. **Bước 2 (Nhập Email):** Điền địa chỉ email (Hotmail/Domain) vào ô Input và nhấn **"Sign up"**.
4. **Bước 3 (Lấy & Nhập OTP):** 
   - Hệ thống tiến hành vòng lặp chờ tối đa 120 giây để lấy mã OTP 6 số từ API đọc mail.
   - Khi có OTP, tự động gửi từng ký tự vào ô xác nhận.
   - *(Lưu ý: Nếu bị kẹt ở bước OTP do lỗi mail/mã sai, tool sẽ chỉ thử click "Confirm" tối đa 3 lần rồi bỏ qua để tránh spam).*
5. **Bước 4 (Thông tin cá nhân & Mật khẩu):**
   - Tạo tên (First Name, Last Name) ngẫu nhiên.
   - Nhập mật khẩu cố định hoặc sinh tự động.
6. **Bước 5 (Bypass Cloudflare Turnstile):**
   - Hệ thống sẽ liên tục kiểm tra giá trị của thẻ input `cf-turnstile-response`. 
   - Chờ đến khi Cloudflare cấp mã token hợp lệ (tự động bypass).
   - Nhấn **"Complete sign up"**.
7. **Thành công:** Kiểm tra việc load vào trang Dashboard để ghi nhận đăng ký hoàn tất.

## 3. Quy Trình Thanh Toán SuperGrok (Lấy URL Thanh Toán Cuối)
Ngay sau khi đăng ký thành công, bot sẽ tự động giữ tab và chuyển sang giai đoạn xử lý link offer:
1. **Mở link ưu đãi:** Trình duyệt tự động tạo 1 tab mới (để tránh popup blocker) và truy cập vào link offer của Google Redirect (chứa link `click.email.grok.com`).
2. **Xử lý Redirect & TOS:**
   - Nếu gặp link Google báo chuyển hướng, tự động click tiếp tục.
   - Nếu gặp trang **TOS Gate** (`/tos-gate`), tự động nhấn "Xác nhận" và tải lại link offer.
3. **Click nút Claim Offer:**
   - Hệ thống quét trang tìm nút bấm có chữ **"Claim"** hoặc **"무료 혜택 받기"** (nhận ưu đãi miễn phí bằng tiếng Hàn).
   - Click để chuyển sang trang Stripe Checkout.
4. **Stripe Checkout (KakaoPay):**
   - Tại trang `checkout.stripe.com`, tự động click chọn phương thức thanh toán **KakaoPay**.
   - Click nút **"평가판 시작"** (Bắt đầu dùng thử / Submit).
5. **Chờ cổng NicePay:**
   - Đợi trình duyệt xử lý và chuyển hướng qua cổng thanh toán cuối cùng của Hàn Quốc: `pay.nicepay.co.kr`.

## 4. Gửi Thông Báo Telegram & Kết Thúc
1. **Lấy URL cuối:** Trích xuất URL `pay.nicepay.co.kr` (kèm token) từ trình duyệt.
2. **Gửi Telegram:**
   - Bot gọi API Telegram, gửi nội dung bao gồm: Email vừa đăng ký và URL thanh toán NicePay.
   - Thông số Token và Chat ID được lấy trực tiếp từ Cài đặt trên giao diện Web.
3. **Lưu dữ liệu:** Lưu trạng thái thành công vào cơ sở dữ liệu (`data/grok_accounts.txt` hoặc DB nội bộ).
4. **Đóng trình duyệt:** Giải phóng tài nguyên và chuyển sang vòng lặp đăng ký tài khoản tiếp theo.

---
> [!NOTE] 
> **Điểm mấu chốt chống lỗi:**
> - Sử dụng vòng lặp 30s siêu chắc chắn ở bước thanh toán để tự động click các nút "tiếp tục" ở mọi màn hình chặn ngang.
> - Xử lý dứt điểm tình trạng spam confirm email bằng bộ đếm giới hạn (tối đa 3 lần).
> - Mọi cài đặt từ giao diện (Số luồng, Mở thanh toán, Ngôn ngữ) đều được inject trực tiếp vào bot logic.
