# 📖 Tài liệu: Auto Đăng Ký Tài Khoản Higgsfield.AI

> Script: `auto_register_higgsfield.py`  
> Ngày tạo: 2026-07-18  
> Mục đích: Tự động tạo hàng loạt tài khoản trên [higgsfield.ai](https://higgsfield.ai) bằng email tạm thời và xác minh OTP tự động.

---

## 📋 Mục Lục

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Cấu hình](#2-cấu-hình)
3. [Cách chạy](#3-cách-chạy)
4. [Luồng đăng ký chi tiết](#4-luồng-đăng-ký-chi-tiết)
5. [Kiến trúc & Các module](#5-kiến-trúc--các-module)
6. [Xử lý Proxy](#6-xử-lý-proxy)
7. [Output](#7-output)
8. [Xử lý lỗi](#8-xử-lý-lỗi)
9. [FAQ](#9-faq)

---

## 1. Yêu cầu hệ thống

| Thứ | Yêu cầu |
|-----|---------|
| **Python** | 3.8+ |
| **Thư viện** | `selenium`, `webdriver-manager`, `requests` |
| **Trình duyệt** | Google Chrome (phiên bản mới nhất) |
| **OS** | macOS / Linux / Windows |

### Cài đặt thư viện:
```bash
pip install selenium webdriver-manager requests
```

> Script tự động cài nếu thiếu `selenium` khi chạy lần đầu.

---

## 2. Cấu hình

Các hằng số ở đầu file `auto_register_higgsfield.py`:

```python
BASE_URL       = "https://regmail.phh.info.vn"   # API tạo email tạm
API_KEY        = "1dec9d51e8707e9bf1..."           # API key mail
PASSWORD       = "Higgsfield123@@"                 # Password mặc định cho mọi tài khoản
HIGGSFIELD_URL = "https://higgsfield.ai/"          # URL đăng ký
OUTPUT_FILE    = "higgsfield_accounts.txt"         # File lưu kết quả
```

---

## 3. Cách chạy

```bash
cd /Users/huong/TaiNguyen/capcut-regaccc
python3 auto_register_higgsfield.py
```

### Menu tương tác:

```
╔══════════════════════════════════════════════════════╗
║      AUTO DANG KY TAI KHOAN HIGGSFIELD.AI             ║
║  Email ngau nhien + OTP tu dong + Quiz tu dong        ║
╚══════════════════════════════════════════════════════╝

=== MENU ===
1. Tao tai khoan (giu trinh duyet mo sau khi xong)
2. Tao tai khoan (tu dong trinh duyet)

👉 Chon 1 hoac 2:
```

| Lựa chọn | Mô tả |
|----------|-------|
| **1** | Giữ Chrome mở sau khi đăng ký xong (dùng để kiểm tra thủ công) |
| **2** | Tự đóng Chrome sau khi xong (chạy hàng loạt) |

Sau đó nhập:
- **Số tài khoản** muốn tạo
- **Số tab** mở cùng lúc (chạy song song)
- **Dùng proxy?** `y` / `n` (mặc định `y`)

---

## 4. Luồng đăng ký chi tiết

```
┌─────────────────────────────────────────────────────────────────┐
│                    LUỒNG ĐĂNG KÝ 1 TÀI KHOẢN                   │
└─────────────────────────────────────────────────────────────────┘

 [API]  Tạo email tạm ngẫu nhiên
   │
   ▼
 [BƯỚC 1]  Mở https://higgsfield.ai/
            Chờ UI load → Click button.hfnav-auth-signup ("Sign up")
   │
   ▼
 [BƯỚC 2]  Dialog đăng ký hiện ra
            Click "Continue with Email"
   │
   ▼
 [BƯỚC 3]  Form "Create an account"
            ├─ Nhập Email (từ API)
            ├─ Nhập Password: Higgsfield123@@
            └─ Click Submit ("Continue with Email")
   │
   ▼
 [BƯỚC 4]  Màn hình "Verify Your Email"
            ├─ Gọi API lấy OTP từ hòm thư
            ├─ Lọc 6 chữ số từ subject/text email
            ├─ Nhập OTP vào input[name='code']
            └─ Nhấn Enter để xác nhận
   │
   ▼
 [BƯỚC 5]  Trang Quiz: "How do you plan to use Higgsfield?"
            ├─ Click "For personal use"
            └─ Click Continue cho đến hết quiz (tối đa 15 bước)
   │
   ▼
 [DONE]   Chờ URL không còn /quiz
           Lưu email + password vào higgsfield_accounts.txt
           Xóa hòm thư tạm
```

---

## 5. Kiến trúc & Các module

### 5.1 `LocalProxyRelay` (class)
Local TCP relay chạy trên `127.0.0.1` với port ngẫu nhiên.  
Chrome kết nối vào relay (không cần popup auth), relay tự chèn header `Proxy-Authorization` và forward lên proxy thật.

```
Chrome → 127.0.0.1:XXXX (Relay) → proxy:port (Auth thật)
```

### 5.2 Email API

| Hàm | Mô tả |
|-----|-------|
| `create_random_email()` | `POST /api/emails/create` → trả về địa chỉ email tạm |
| `get_latest_email(email)` | `GET /api/emails/latest?email=...` → lấy email mới nhất |
| `wait_for_otp(email)` | Vòng lặp polling 4s/lần, tối đa 120s, lọc OTP 6 số từ email |
| `delete_mailbox(email)` | `DELETE /api/emails/address/{email}` → dọn hòm thư sau khi xong |

**Format OTP từ API:**
```json
{
  "success": true,
  "emails": [{
    "subject": "474451 is your verification code",
    "otp": "474451"
  }]
}
```

### 5.3 Proxy API
```
GET https://proxyquick.click/api/v3/users/rotatev2?token=...
```
Trả về proxy dạng `host:port:user:pass`. Script tự tạo LocalProxyRelay nếu có auth.

### 5.4 Các hàm Selenium

| Hàm | Mô tả |
|-----|-------|
| `setup_driver(index, ...)` | Khởi tạo Chrome với proxy, chia màn hình theo số tab |
| `set_input(driver, el, val)` | Nhập text vào input (gõ từng ký tự để tránh bị detect) |
| `try_click(driver, el, label)` | Click element, fallback JS click nếu thất bại |
| `wait_for_element(...)` | Chờ element xuất hiện trong DOM |
| `wait_clickable(...)` | Chờ element có thể click |

### 5.5 Các bước đăng ký

| Hàm | Selector chính | Mô tả |
|-----|---------------|-------|
| `step1_open_signup()` | `button.hfnav-auth-signup` | Mở trang + click Sign up |
| `step2_click_email()` | `button[contains(.,'Continue with Email')]` | Click Continue with Email |
| `step3_fill_form()` | `input[name='email']`, `input[type='password']`, `input[type='submit']` | Điền form |
| `step4_enter_otp()` | `input[name='code']` | Nhập OTP |
| `step5_complete_quiz()` | `button[contains(.,'personal')]` + nav buttons | Hoàn thành quiz |

---

## 6. Xử lý Proxy

Script có 3 chế độ proxy:

```
Người dùng chọn "Dùng proxy? y"
        │
        ▼
  Gọi API xoay proxy
        │
   ┌────┴────┐
   │ Có kết  │  Thành công → Tạo LocalProxyRelay → Chrome dùng relay
   │  quả    │
   └────┬────┘
        │ Thất bại
        ▼
  Không dùng proxy (chạy IP thật)
```

> **Lưu ý:** Higgsfield sử dụng Clerk để auth. Nếu bị chặn CAPTCHA, thử đổi proxy hoặc dùng IP sạch hơn.

---

## 7. Output

### File `higgsfield_accounts.txt`
Mỗi tài khoản đăng ký thành công được ghi 1 dòng:
```
email@catshopvip.site    Higgsfield123@@
email2@catshopvip.site   Higgsfield123@@
```

> Format: `{email}\t{password}` (tab-separated)

### Ảnh lỗi
Khi gặp exception, script tự chụp màn hình Chrome:
```
higgsfield_error_1.png
higgsfield_error_2.png
```

---

## 8. Xử lý lỗi

| Lỗi | Nguyên nhân | Xử lý |
|-----|------------|-------|
| Không tìm thấy `button.hfnav-auth-signup` | Trang chưa load xong | Script chờ 15s, thử nhiều selector |
| Không nhận được OTP | Email chưa đến | Polling mỗi 4s, tối đa 120s |
| Submit form thất bại | React input không kích hoạt | Gõ từng ký tự với delay 30ms |
| Proxy 407 | Sai auth proxy | LocalProxyRelay trả 502 → retry |
| Quiz loop vô tận | URL vẫn có `/quiz` | Giới hạn tối đa 15 bước quiz |

---

## 9. FAQ

**Q: Chạy nhiều tab cùng lúc có bị lỗi không?**  
A: Có thể. Khuyến nghị chạy 2–3 tab cùng lúc. Mỗi tab delay 2.5s để tránh quá tải proxy.

**Q: Password có thể đổi không?**  
A: Sửa biến `PASSWORD` ở đầu file:
```python
PASSWORD = "MyNewPass123@@"
```

**Q: Tài khoản lưu ở đâu?**  
A: File `higgsfield_accounts.txt` trong cùng thư mục với script.

**Q: OTP timeout thì tài khoản có được lưu không?**  
A: Không. Hàm trả về `False` → bỏ qua tài khoản đó, tiếp tục tài khoản sau.

**Q: Chạy không proxy có ổn không?**  
A: Được nếu IP sạch. Nhập `n` khi hỏi "Dung proxy?".

---

## 🔑 Tóm tắt nhanh

```bash
# Chạy script
python3 auto_register_higgsfield.py

# Xem kết quả
cat higgsfield_accounts.txt

# Xem lỗi
ls higgsfield_error_*.png
```

---

*Script tương tự CapCut auto-register tool trong cùng thư mục (`auto_register_capcut-new.py`)*
