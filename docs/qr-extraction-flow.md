# Quy trình trích xuất Link / QR thanh toán từ Access Token (Chi tiết MoMo & Stripe)

Tài liệu này giải thích chi tiết luồng logic (nghiệp vụ) và kỹ thuật (code) để đi từ một `accessToken` của tài khoản ChatGPT đến việc trích xuất được link thanh toán (hoặc mã QR) của Stripe, đặc biệt tập trung vào **cách lọc và ép buộc cổng thanh toán MoMo**.

---

## 1. Logic luồng (Mô tả miệng)

Để lấy được mã QR hoặc link thanh toán cho khách hàng nạp Plus qua **MoMo**, hệ thống phải "đóng giả" trình duyệt thực hiện qua 4 bước chính:

1. **Vào ChatGPT xin phiên thanh toán:** Dùng `accessToken` của khách để yêu cầu ChatGPT tạo một phiên mua Plus. Lấy về `checkout_session_id`.
2. **Khởi tạo trang thanh toán với Stripe (Init):** Gửi `checkout_session_id` sang Stripe. Stripe sẽ dò IP của Proxy để phán đoán quốc gia (Geocoding). 
   - *Lưu ý cực kỳ quan trọng:* Nếu Proxy đang dùng ở Ấn Độ (IN), Stripe sẽ ẩn MoMo và chỉ trả về `card`, `upi`. Do đó, **ta KHÔNG ĐƯỢC chặn lỗi nếu Stripe ban đầu không trả về `"momo"`**.
3. **Bẻ khóa vị trí (Bypass Geocoding) & Lọc phương thức MoMo:** Mặc kệ Stripe ban đầu nói gì, ta chủ động báo lại cho Stripe: *"Tôi muốn thanh toán bằng VND và khu vực tính thuế của tôi là Việt Nam (VN)"*. Nhờ đó, Stripe sẽ "mở khóa" lại cổng MoMo.
4. **Bấm nút Thanh toán (Confirm):** Gửi yêu cầu chốt đơn thanh toán bằng cổng MoMo (`type=momo`). Stripe duyệt thành công sẽ trả về hành động tiếp theo (`next_action`), chứa đường link chuyển hướng đến trang thanh toán của MoMo.

---

## 2. Technical Flow (Chi tiết Dev & Data truyền đi)

Dưới đây là chi tiết luồng code đang chạy (trong `chatgpt-upi.ts` - hàm `extractMomoPaymentFromCredentialWithProxy`).

### Bước 1: Yêu cầu Checkout từ OpenAI (`callCheckout`)
- **Thao tác:** Gửi request GET tới `https://chatgpt.com/backend-api/payments/checkout`.
- **Kết quả thu được:**
  - `checkout_session_id` (Ví dụ: `cs_live_a1...`)
  - `publishable_key` (Ví dụ: `pk_live_...`)
  - Nếu báo lỗi `already have an active subscription` -> Dừng tiến trình vì acc đã có Plus.

### Bước 2: Khởi tạo Stripe Payment Page (`callStripeInit`)
- **Thao tác:** Gửi request GET tới `https://api.stripe.com/v1/payment_pages/{checkout_session_id}/init`
- **Xử lý Dữ liệu:** Check xem có **Free Trial 100%** không từ object `subscription_data`.
- **Logic quan trọng (Bỏ qua lọc Geocoding ban đầu):** 
  ```javascript
  const paymentMethods = freeTrialStatus.paymentMethodTypes;
  // BỎ QUA check if (!paymentMethods.includes("momo"))
  // Vì IP Proxy có thể là US/IN, Stripe sẽ không trả về momo ở đây.
  // Ta sẽ ép buộc Stripe mở Momo ở các bước sau!
  ```

### Bước 3: Khởi tạo Elements Session & Ép Quốc Gia về VN
**3.1. Gọi Elements Session (`callMomoStripeElementsSession`)**
- **Thao tác:** Gửi request GET tới `https://api.stripe.com/v1/elements/sessions`.
- **Tham số bắt buộc (Để ép hệ thống chuẩn bị cổng MoMo):**
  - `"deferred_intent[payment_method_types][0]": "card"`
  - `"deferred_intent[payment_method_types][1]": "momo"`
  - `"deferred_intent[currency]": "vnd"`
  - `"currency": "vnd"`

**3.2. Cập nhật Tax Region (`callMomoStripeUpdateTaxRegion`)**
- **Thao tác:** Gửi request POST tới `https://api.stripe.com/v1/payment_pages/{checkout_session_id}`.
- **Payload ép quốc gia:**
  ```json
  {
    "tax_region[country]": "VN",
    "tax_region[postal_code]": "100000",
    "tax_region[city]": "Hanoi",
    "tax_region[line1]": "1 Trang Tien"
  }
  ```
- **Mục đích:** Khẳng định địa chỉ thanh toán là Việt Nam. Thao tác này giúp override lại cái IP Geocoding (ví dụ Ấn Độ) ở bước 2, chính thức "mở khóa" MoMo ở Backend của Stripe.

### Bước 4: Chốt Thanh Toán MoMo (`callMomoStripeConfirm`)
- **Thao tác:** Gửi request POST tới `https://api.stripe.com/v1/payment_pages/{checkout_session_id}/confirm`.
- **Payload chỉ định MoMo:**
  - `payment_method_data[type]: "momo"`
  - `expected_payment_method_type: "momo"`
  - `payment_method_data[billing_details][address][country]: "VN"`
- **Phản hồi:** Trả về HTTP 200 kèm theo JSON chi tiết về giao dịch, trong đó chứa `next_action`.

---

## 3. Cách check và lấy Link / QR từ JSON Stripe (`next_action`)

Sau khi chạy xong Bước 4, ta phải đọc dữ liệu JSON trả về để tìm đường link thanh toán. Hàm xử lý: `collectMomoPaymentArtifact`.

### Trường hợp 1: Chuyển hướng lấy link (Đúng với MoMo, iDeal)
Với ví điện tử MoMo, Stripe sẽ không sinh ảnh QR ngay mà trả về một **đường link chuyển hướng**.
- **Cách tìm trong JSON:** Tồn tại biến `next_action.redirect_to_url.url`.
- **Code mẫu:**
  ```javascript
  const url = response.next_action?.redirect_to_url?.url;
  
  if (url && url.startsWith("http")) {
      // 1. Lưu url này vào DB làm paymentUrl.
      // 2. Hệ thống dùng thư viện 'qrcode' sinh ra Buffer ảnh QR từ cái url này.
      const qrPngBuffer = await QRCode.toBuffer(url, { width: 400 });
      return { paymentUrl: url, qrPngBuffer };
  } else {
      throw new Error("Không tìm thấy URL thanh toán Momo trong phản hồi Stripe");
  }
  ```

### Trường hợp 2: Native QR Code của Stripe (Mở rộng cho UPI)
Chỉ áp dụng khi trích xuất UPI. Stripe trả thẳng dữ liệu QR.
- **Cách tìm:** `next_action.upi_handle_redirect_or_display_qr_code`.
- **Dữ liệu lấy:** 
  - `action.qr_code.image_url_png` (Link tải ảnh PNG)
  - `action.hosted_instructions_url` (Link trang có QR)

### Tổng kết luồng Fail:
Nếu phản hồi JSON **KHÔNG CÓ** `next_action`, hoặc Stripe báo lỗi `error.message` (ví dụ: thẻ không hợp lệ, quốc gia không hỗ trợ):
- Quá trình trích xuất thất bại.
- Mã code sẽ ghi log ra file (như `stripe_confirm_momo_debug.json`) để dev kiểm tra xem Stripe đang chửi lỗi gì.
