# Tài liệu Tích hợp API Gmail94 (Mail API)

Tài liệu này ghi chú lại các Endpoint (đường dẫn) API của Gmail94 đang được sử dụng trong hệ thống Auto-GPT Extension, bao gồm cách thức hoạt động và mã nguồn mẫu.

## 1. Mua Gmail Mới (Create Order)
- **Endpoint**: `https://gmail94.com/api/otp/create`
- **Method**: `POST` (Tuy nhiên API của Gmail94 cũng hỗ trợ cấu trúc tham số trực tiếp trên URL)
- **Tham số**:
  - `token`: API Key của tài khoản Gmail94 (ví dụ: `6ed66b29e94b907ec3e1d7b116965bc3a1f54b01cbecd5e706767858206fed13`)
  - `service`: Tên dịch vụ cần mua (ở đây là `chatgpt`)
- **Phản hồi thành công**:
  ```json
  {
    "success": true,
    "email": "abcxyz@gmail.com",
    "order_id": "123456"
  }
  ```

### Mã nguồn (Trích từ `background.js`)
```javascript
// Action: 'gmail94_buy'
fetch(`https://gmail94.com/api/otp/create?token=${encodeURIComponent(token)}&service=chatgpt`, {
  method: 'POST'
})
.then(r => r.json())
.then(data => {
  if (data.success && data.email) {
    sendResponse({ success: true, email: data.email, order_id: data.order_id });
  } else {
    sendResponse({ success: false, error: data.msg || 'Không rõ lỗi' });
  }
})
.catch(err => {
  sendResponse({ success: false, error: err.toString() });
});
```

---

## 2. Đọc mã OTP (Read OTP)
- **Endpoint**: `https://gmail94.com/api/otp/read`
- **Method**: `GET`
- **Tham số**:
  - `token`: API Key của tài khoản
  - `order_id`: ID đơn hàng nhận được lúc Mua Gmail
  - `service`: `chatgpt`
- **Phản hồi thành công**:
  ```json
  {
    "success": true,
    "otp": "123456"
  }
  ```
  *(Lưu ý: Nếu OTP chưa về, API sẽ trả về `{ success: false, msg: "Chưa có mã" }`. Khi đó ta cần viết một vòng lặp (Polling) gọi lại sau mỗi vài giây.)*

### Mã nguồn (Trích từ `background.js`)
```javascript
// Action: 'gmail94_readOtp' (hoặc 'gmail94_pollOtp' dùng để tự động vòng lặp)
fetch(`https://gmail94.com/api/otp/read?token=${encodeURIComponent(token)}&order_id=${encodeURIComponent(order_id)}&service=chatgpt`)
.then(r => r.json())
.then(data => {
  if (data.success && data.otp) {
    sendResponse({ success: true, otp: data.otp });
  } else {
    sendResponse({ success: false, error: data.msg || 'Chưa có mã' });
  }
})
.catch(err => {
  sendResponse({ success: false, error: err.toString() });
});
```

---

## 3. Lấy Danh sách Gmail Đã Mua (List Rented Emails)
- **Endpoint**: `https://gmail94.com/buy-otp-gmail/rented-emails`
- **Method**: `GET`
- **Lưu ý Quan trọng**: 
  - Đây **KHÔNG** phải là API công khai dùng Token. 
  - Endpoint này là API nội bộ của trang web Gmail94, do đó yêu cầu phải gửi kèm Cookies phiên đăng nhập (`credentials: 'include'`).
  - Phải gắn headers `Accept: application/json` và `X-Requested-With: XMLHttpRequest` để máy chủ trả về JSON thay vì trả về giao diện HTML.
- **Tham số**:
  - `page`: Trang hiện tại (mặc định: `1`)

### Mã nguồn (Trích từ `background.js`)
```javascript
// Action: 'gmail94_list'
fetch(`https://gmail94.com/buy-otp-gmail/rented-emails?page=${page}`, {
  credentials: 'include', // Gửi kèm Cookie phiên làm việc trên trình duyệt
  headers: {
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest' // Ép trả về API JSON thay vì HTML Login
  }
})
.then(async r => {
  const text = await r.text();
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new Error("Phản hồi không phải JSON. Vui lòng đăng nhập vào trang gmail94.com trên trình duyệt.");
  }
})
.then(data => {
  if (data.message === "Unauthenticated.") {
     sendResponse({ success: false, error: "Chưa đăng nhập Gmail94! Vui lòng mở trang gmail94.com và đăng nhập trước." });
     return;
  }
  // Trả về dữ liệu list mail và phân trang
  sendResponse({ success: true, data: data?.data || [], pagination: data?.pagination || null });
})
.catch(err => {
  sendResponse({ success: false, error: err.toString() });
});
```
