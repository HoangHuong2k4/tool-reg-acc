# Hướng dẫn quy trình mua Mail và lấy OTP từ API Gmail94 cho GPT Bot

Tài liệu này mô tả chi tiết cách module `gpt_gmail94.py` tương tác với API của Gmail94 để mua email và đăng ký tài khoản ChatGPT.

## 1. Cơ chế tối ưu (1 Email = 4 Tài khoản)

Để tiết kiệm chi phí, hệ thống áp dụng cơ chế tạo biến thể email. Khi mua thành công **1 Gmail gốc** (ví dụ: `abc@gmail.com`), bot sẽ tự động tạo ra **4 biến thể** (sử dụng hàm `expand_gmail_variants`):

1. `abc@gmail.com`
2. `abc@googlemail.com`
3. `abc+1@gmail.com`
4. `abc+1@googlemail.com`

**Đặc điểm quan trọng:**
Tất cả 4 email này khi dùng để đăng ký ChatGPT đều sẽ nhận mã OTP gửi về **cùng một hộp thư (inbox) gốc**. Do đó, chúng sử dụng chung một `order_id` khi truy vấn lấy OTP từ Gmail94.

---

## 2. Quy trình Mua Mail (API Create)

Hàm chịu trách nhiệm: `gmail94_buy(token)`

- **Endpoint API:** `GET https://gmail94.com/api/otp/create`
- **Tham số (Params):** 
  - `token`: API Token của người dùng (lấy từ cấu hình).
  - `service`: `chatgpt`
- **Hoạt động:**
  - Gửi request đến API để yêu cầu cấp 1 email mới.
  - Nếu thành công, API trả về JSON chứa `email` và `order_id`. 
    - Ví dụ: `{"success": true, "data": {"email": "abc@gmail.com", "order_id": "123456"}}`
  - Bot lưu lại cặp `email` và `order_id` này để sử dụng cho bước lấy OTP.
  - **Retry Mechanism:** Nếu hết email tạm thời, hệ thống tự động chờ 15 giây và thử mua lại liên tục cho đến khi nhận được email (trong hàm `register_one_purchase`).

---

## 3. Quy trình Lấy mã OTP (API Read)

Hàm chịu trách nhiệm: `gmail94_read_otp(...)` kết hợp với hook `custom_wait_for_otp`

- **Endpoint API:** `GET https://gmail94.com/api/otp/read`
- **Tham số (Params):**
  - `token`: API Token.
  - `order_id`: ID đơn hàng lấy từ bước mua mail.
  - `service`: `chatgpt`
- **Cơ chế chống trùng lặp OTP (Seen OTPs):**
  - Vì 4 biến thể email cùng nhận thư về 1 inbox (`order_id`), Gmail94 sẽ trả về tất cả các OTP có trong hộp thư đó.
  - Để đảm bảo biến thể số 2 không dùng nhầm mã OTP của biến thể số 1, hệ thống lưu một danh sách các mã đã sử dụng (`GMAIL94_SEEN_OTPS`).
  - Khi API trả về một OTP, bot sẽ kiểm tra xem mã này đã nằm trong danh sách `seen_otps` chưa. 
    - Nếu có: Bỏ qua và tiếp tục chờ mã mới.
    - Nếu chưa: Lưu mã vào `seen_otps` và trả về cho trình duyệt Selenium nhập vào.
- **Hoạt động Polling:** Bot thực hiện gọi API lặp lại (mỗi 5 giây) cho đến khi lấy được mã thành công hoặc hết thời gian chờ (timeout mặc định 60 giây).

---

## 4. Tóm tắt luồng thực thi tổng thể (Flow)

Luồng chạy chính nằm tại hàm `register_one_purchase`:

1. Gọi `gmail94_buy()` để mua mail gốc.
2. Dùng `expand_gmail_variants()` để sinh ra 4 email con.
3. Tạo ra các luồng (Thread) để mở trình duyệt chạy đăng ký cho từng biến thể email.
4. Khi trình duyệt yêu cầu OTP, nó gọi hook `custom_wait_for_otp` -> Gọi `gmail94_read_otp()` để ping API lấy mã.
5. Khi hoàn thành, ghi log và lưu trạng thái thành công/thất bại của từng tài khoản. Dọn dẹp bộ nhớ đệm `seen_otps`.
