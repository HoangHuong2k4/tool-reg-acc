# 📬 API mới cho RegMail + Get-OTP (bản bảo mật, cập nhật 03/10/2026)

Tài liệu dùng khi viết hoặc cập nhật **extension / tool** có dùng mail domain của hệ thống.

| Hệ thống | URL gốc | Xác thực | Dùng cho |
|---|---|---|---|
| **RegMail API** | `https://regmail.phh.info.vn` | API key (header `X-API-Key`) | Tool riêng của bạn: tạo email, lấy OTP, lấy domain... |
| **Get-OTP API** | `https://get-opt.phh.info.vn/api.php` | Không cần key | Tra OTP công khai theo **đúng 1 địa chỉ email** |

---

## ⚠️ Những gì đã thay đổi (phải sửa ext/tool cũ)

| Cũ | Mới |
|---|---|
| `GET /api/public-key` để lấy key | ❌ **Đã xóa**. Lấy key trong web admin (xem mục 1) |
| Key cũ `1dec9d51...` | ❌ **Đã thu hồi** (trả 403). Dùng key mới bắt đầu bằng `rm_` |
| Gửi key qua URL `?api_key=...` | ❌ **Không còn nhận** (401). Chỉ nhận header `X-API-Key` |
| Session token qua URL `?token=...` | ❌ Không còn nhận. Dùng header `Authorization: Bearer <token>` |
| `get-opt .../api.php?action=domains` | ❌ **Đã xóa**. Cần list domain thì dùng `GET /api/domains` (có key) |
| Thêm/xóa/bật tắt domain, cleanup bằng API key | ❌ Chỉ admin đăng nhập web mới làm được |
| Gọi thẳng `http://IP:3003` | ❌ Cổng đã đóng. Luôn dùng `https://regmail.phh.info.vn` |
| Mật khẩu admin `12345678` | ❌ Đã đổi |

---

## 1. Lấy API key

1. Đăng nhập `https://regmail.phh.info.vn`.
2. Bấm **Admin / API Key** trên header.
3. Bấm **Show** hoặc **Copy**.
4. Key bị lộ thì bấm **Create new key (revoke old)**: key cũ chết ngay, và key của Get-OTP cũng tự cập nhật theo.

> 🔒 **Quy tắc giữ key**
> - **KHÔNG** nhúng key vào extension hay tool **phát cho người khác**: ai giải nén ext là đọc được key. Ext công khai nên dùng **Get-OTP API** (mục 3), vì API này không cần key.
> - Tool chạy trên máy hoặc server của bạn: để key trong biến môi trường hoặc file config, không commit lên git.
> - Không đặt key trong URL, không log key ra console.

---

## 2. RegMail API (cần key)

**Header bắt buộc cho mọi request:**
```
X-API-Key: rm_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 2.1 Danh sách endpoint dùng được bằng API key

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/domains` | Danh sách domain **đang active** |
| POST | `/api/emails/create` | Tạo 1 email ngẫu nhiên trên domain active |
| GET | `/api/emails/latest?email=<email>` | Email mới nhất của 1 địa chỉ (kèm `otp`) ⭐ dùng nhiều nhất |
| GET | `/api/emails?email=<email>` | Tất cả email gửi tới địa chỉ đó (có phân trang) |
| GET | `/api/emails?username=<user>` | Email của `user@<mọi domain active>` |
| GET | `/api/emails?search=<từ khóa>` | Tìm trong from / to / subject / nội dung |
| GET | `/api/emails/:id` | Chi tiết 1 email (gọi xong sẽ đánh dấu đã đọc) |
| POST | `/api/emails/:id/read` | Đánh dấu đã đọc |
| DELETE | `/api/emails/:id` | Xóa 1 email |
| DELETE | `/api/emails/address/<email>` | Xóa toàn bộ email của 1 địa chỉ |
| DELETE | `/api/emails/addresses` | Xóa nhiều địa chỉ. Body: `{"addresses":["a@x.com","b@y.com"]}` |
| GET | `/api/email-addresses?page=&limit=&search=` | Danh sách địa chỉ đã nhận mail |
| GET | `/api/emails/all` | Toàn bộ email (nặng, hạn chế dùng) |
| GET | `/api/stats` | Thống kê |
| GET | `/health` | Kiểm tra server (không cần key) |

**Tham số phân trang** cho `/api/emails`: `page` (mặc định 1), `limit` (mặc định 50).

### 2.2 Định dạng response

**`GET /api/domains`**
```json
{
  "success": true,
  "domains": [
    { "id": 1, "domain": "phh.info.vn", "ip_address": "116.118.45.223", "status": "active", "created_at": "..." }
  ]
}
```

**`POST /api/emails/create`**
```json
{ "success": true, "email": "k3j9x0abcd@phh.info.vn", "domain": "phh.info.vn" }
```

**`GET /api/emails/latest?email=...`**
```json
{
  "success": true,
  "email": {
    "id": 112462,
    "to_email": "k3j9x0abcd@phh.info.vn",
    "subject": "Your verification code",
    "html": "<div>...</div>",
    "text": "Your verification code is 928800",
    "otp": "928800",
    "received_at": "2026-10-03T07:45:12.000Z"
  }
}
```
Chưa có mail thì trả: `{ "success": true, "email": null, "message": "No email found" }`

**`GET /api/emails?email=...`**
```json
{
  "success": true,
  "emails": [
    {
      "id": 112462, "from_email": "no-reply@x.com", "from_name": "X",
      "to_email": "k3j9x0abcd@phh.info.vn", "subject": "...",
      "text": "...", "html": "...", "is_read": 0,
      "otp": "928800", "received_at": "2026-10-03T07:45:12.000Z"
    }
  ],
  "pagination": { "page": 1, "limit": 50, "total": 1, "pages": 1 }
}
```

- `received_at` luôn là **UTC ISO**. Hiển thị giờ VN thì tự convert sang `Asia/Ho_Chi_Minh`.
- `otp` do server tự trích từ nội dung (4–8 chữ số), có thể là `null`.
- Email gửi tới domain **không active** sẽ không trả về.

### 2.3 Mã lỗi

| HTTP | Ý nghĩa | Ext/tool nên làm gì |
|---|---|---|
| 400 | Thiếu hoặc sai tham số | Kiểm tra input |
| 401 | Thiếu `X-API-Key` (hoặc gửi key qua URL) | Thêm header |
| 403 | **Key sai hoặc đã bị thu hồi** | Báo người dùng cập nhật key, **không retry liên tục** |
| 429 | Quá giới hạn, hoặc IP bị khóa | Đợi rồi thử lại (xem 2.4) |
| 500 | Lỗi server | Retry sau vài giây |

Body lỗi luôn có dạng: `{ "success": false, "error": "..." }`

### 2.4 Giới hạn (rate limit)

- **600 request/phút/IP** cho toàn bộ `/api/*`.
- **Sai key hoặc sai mật khẩu 10 lần trong 15 phút thì IP bị khóa 15 phút** (trả 429 cho mọi request).
  → Nhận 403 thì **dừng ngay**, đừng vòng lặp gọi tiếp, nếu không IP sẽ bị khóa.
- Poll OTP: nên gọi **3–5 giây/lần**, tối đa khoảng 2–3 phút rồi dừng.

### 2.5 CORS (cho extension / web)

Chỉ cho phép gọi từ trình duyệt với các origin sau:
- `https://regmail.phh.info.vn`
- `chrome-extension://*`, `moz-extension://*`

Tool chạy server-side (Node, Python, PHP, cURL...) không bị ảnh hưởng bởi CORS.
Userscript (Tampermonkey) thì dùng `GM_xmlhttpRequest` + `@connect regmail.phh.info.vn`.

---

## 3. Get-OTP API (công khai, không cần key)

Dành cho **extension phát cho người khác** hoặc trang tra OTP công khai.

```
GET https://get-opt.phh.info.vn/api.php?email=<địa chỉ email đầy đủ>
```

- **Bắt buộc** nhập đủ email (`abc@domain.com`). Chỉ có username thì bị từ chối.
- Chỉ đọc được hộp thư của **đúng địa chỉ đó**. Không lấy được danh sách domain, không tạo hay xóa được gì.
- Response giống `GET /api/emails?email=...` ở mục 2.2 (tối đa 50 mail, có field `otp`).
- **Giới hạn: 30 request/phút/IP** → poll **≥ 3 giây/lần** (khuyên 5–10 giây).
- Đã bỏ CORS `*` → extension gọi được (cần `host_permissions`), web của site khác thì **không** gọi trực tiếp được.

| HTTP | Ý nghĩa |
|---|---|
| 400 | Thiếu email / sai định dạng |
| 405 | Không phải GET |
| 429 | Quá 30 req/phút (có header `Retry-After`) |
| 500 / 502 | Lỗi server, thử lại sau |

---

## 4. Code mẫu

### 4.1 Extension Chrome (Manifest V3)

`manifest.json`
```json
{
  "manifest_version": 3,
  "name": "My OTP Ext",
  "version": "2.0.0",
  "permissions": ["storage"],
  "host_permissions": [
    "https://regmail.phh.info.vn/*",
    "https://get-opt.phh.info.vn/*"
  ],
  "background": { "service_worker": "background.js" }
}
```

**Cách A – Ext dùng riêng, có key** (key do người dùng nhập vào trang Options rồi lưu `chrome.storage.local`, **không hardcode**):
```js
const BASE = 'https://regmail.phh.info.vn';

async function getKey() {
  const { regmailKey } = await chrome.storage.local.get('regmailKey');
  if (!regmailKey) throw new Error('Chưa nhập API key trong Options');
  return regmailKey;
}

async function api(path, options = {}) {
  const res = await fetch(BASE + path, {
    ...options,
    headers: { ...(options.headers || {}), 'X-API-Key': await getKey() }
  });
  if (res.status === 403) throw new Error('API key sai hoặc đã bị thu hồi – cập nhật key mới');
  if (res.status === 429) throw new Error('Quá giới hạn, thử lại sau');
  const data = await res.json();
  if (!data.success) throw new Error(data.error || 'API error');
  return data;
}

// Tạo email mới
async function createEmail() {
  const { email } = await api('/api/emails/create', { method: 'POST' });
  return email;
}

// Chờ OTP (poll 4s, tối đa 3 phút), chỉ nhận mail đến SAU thời điểm bắt đầu
async function waitForOtp(email, { timeoutMs = 180000, intervalMs = 4000 } = {}) {
  const startedAt = Date.now() - 5000;
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    const { email: mail } = await api(`/api/emails/latest?email=${encodeURIComponent(email)}`);
    if (mail && mail.otp && new Date(mail.received_at).getTime() >= startedAt) {
      return mail.otp;
    }
    await new Promise(r => setTimeout(r, intervalMs));
  }
  throw new Error('Hết thời gian chờ OTP');
}

// Lấy domain active
async function getDomains() {
  const { domains } = await api('/api/domains');
  return domains.map(d => d.domain);
}
```

**Cách B – Ext phát công khai, không key** (dùng Get-OTP):
```js
async function getOtpPublic(email) {
  const res = await fetch(`https://get-opt.phh.info.vn/api.php?email=${encodeURIComponent(email)}`);
  if (res.status === 429) throw new Error('Quá nhanh, đợi chút');
  const data = await res.json();
  if (!data.success) throw new Error(data.error);
  const latest = data.emails[0];       // mới nhất nằm đầu
  return latest ? latest.otp : null;
}
```

### 4.2 Node.js tool
```js
// REGMAIL_API_KEY=rm_xxx node tool.js
const KEY = process.env.REGMAIL_API_KEY;
const BASE = 'https://regmail.phh.info.vn';

const res = await fetch(`${BASE}/api/emails/latest?email=${encodeURIComponent('abc@phh.info.vn')}`, {
  headers: { 'X-API-Key': KEY }
});
console.log((await res.json()).email?.otp);
```

### 4.3 Python
```python
import os, time, requests

BASE = "https://regmail.phh.info.vn"
S = requests.Session()
S.headers["X-API-Key"] = os.environ["REGMAIL_API_KEY"]

email = S.post(f"{BASE}/api/emails/create").json()["email"]
print("Email:", email)

for _ in range(45):                      # ~3 phút
    r = S.get(f"{BASE}/api/emails/latest", params={"email": email})
    if r.status_code == 403:
        raise SystemExit("API key sai / bị thu hồi")
    mail = r.json().get("email")
    if mail and mail.get("otp"):
        print("OTP:", mail["otp"]); break
    time.sleep(4)
```

### 4.4 PHP
```php
$key = trim(file_get_contents('/path/ngoai/webroot/regmail-api-key')); // KHÔNG hardcode
$ctx = stream_context_create(['http' => [
    'header' => "X-API-Key: $key\r\nAccept: application/json\r\n",
    'timeout' => 10, 'ignore_errors' => true,
]]);
$data = json_decode(file_get_contents(
    'https://regmail.phh.info.vn/api/emails/latest?email=' . urlencode('abc@phh.info.vn'), false, $ctx
), true);
echo $data['email']['otp'] ?? 'chưa có';
```

### 4.5 cURL
```bash
curl -H "X-API-Key: $REGMAIL_API_KEY" https://regmail.phh.info.vn/api/domains
curl -X POST -H "X-API-Key: $REGMAIL_API_KEY" https://regmail.phh.info.vn/api/emails/create
curl -H "X-API-Key: $REGMAIL_API_KEY" "https://regmail.phh.info.vn/api/emails/latest?email=abc@phh.info.vn"
curl "https://get-opt.phh.info.vn/api.php?email=abc@phh.info.vn"
```

---

## 5. Checklist cập nhật ext/tool cũ

- [ ] Xóa mọi chỗ gọi `/api/public-key`
- [ ] Xóa key cũ hardcode (`1dec9d51...`), không hardcode key mới
- [ ] Đổi `?api_key=` → header `X-API-Key`
- [ ] Đổi `get-opt ...?action=domains` → `GET /api/domains` (có key), hoặc bỏ nếu ext công khai
- [ ] Ext công khai → chuyển sang Get-OTP API (không key), luôn gửi email đầy đủ
- [ ] URL dùng `https://regmail.phh.info.vn`, không dùng `http://IP:3003`
- [ ] Xử lý 403 (dừng, báo cập nhật key) và 429 (đợi rồi thử lại)
- [ ] Poll ≥ 3 giây/lần, có timeout
- [ ] `host_permissions` trong manifest có 2 domain trên

---

## 6. Dành cho admin (chỉ qua web, cần đăng nhập)

| Việc | Ở đâu |
|---|---|
| Xem / copy / đổi API key | Web → **Admin / API Key** |
| Đổi mật khẩu admin | Web → **Admin / API Key** → Change Admin Password |
| Thêm / bật tắt / xóa domain | Web → **Admin / API Key** |
| Quên mật khẩu | SSH: `cd /home/huong/web/regmail.phh.info.vn/public_html && node set-admin-password.js admin` rồi `pm2 restart email-inbox-phhuong` |
| Build lại giao diện | `cd client && ./node_modules/.bin/vite build` (**không** dùng `pnpm run build`) |
