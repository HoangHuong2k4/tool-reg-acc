# Phân Tích Luồng Auto Đăng Ký & Bật 2FA — Auto GPT Premium Extension

---

## Kiến Trúc Tổng Quan

```
popup.html / popup.js          <- UI người dùng (Extension Popup)
      |  chrome.storage.local   <- Chia se state giua cac file
      v
background.js (Service Worker) <- Goi API doc email, sinh TOTP offline
      |  chrome.runtime.sendMessage
      v
content.js (Content Script)    <- Inject vao auth.openai.com / chatgpt.com
           + Floating UI widget (hien thi tren trang web)
```

**Co che dong bo state**: `chrome.storage.local` — cac key quan trong:

| Key | Y nghia |
|-----|---------|
| `auto_gpt_running` | `true` khi dang chay dang ky |
| `auto_gpt_2fa_setup` | `true` khi dang trong giai doan bat 2FA |
| `account_email` | Email Hotmail/Outlook |
| `account_pass` | Mat khau email (Hotmail) |
| `account_refresh` | OAuth2 refresh token cua email |
| `account_client` | OAuth2 client_id |
| `chatgpt_password` | Mat khau ChatGPT moi (random sinh ra) |
| `account_2fa_secret` | Secret TOTP Base32 (sau khi doc tu QR) |

---

## LUONG 1: AUTO DANG KY TAI KHOAN

### Buoc 0: Nguoi dung nhan Start (popup.js / content.js floating UI)

**Dieu kien dau vao (validate):**
- Token phai dung format: `email|hotmail_pass|refresh_token|client_id`
- Neu sai → bao loi, dung lai

**Khoi tao:**
```
chatgptPassword = random 20 ky tu (a-z A-Z 0-9 !@#$%^&*) + "aA1!"
```
> Luon ket thuc bang `aA1!` de dam bao du dieu kien: chu thuong, HOA, so, ky tu dac biet

**Ghi vao storage:**
```js
auto_gpt_running: true
auto_gpt_2fa_setup: false
account_email, account_pass, account_refresh, account_client
chatgpt_password: <mat khau GPT moi>
```

**Mo tab:** `https://auth.openai.com/create-account`

---

### Buoc 1: Dien Email (content.js — auth.openai.com/create-account)

**URL trigger:** `url.includes("/create-account") && !url.includes("/password")`

**Logic:**
1. Tim `input[type="email"]` hoac `input[name="email"]`
2. Neu chua dien va chua co `data-focusing` → danh dau `data-focusing = true`
3. **Cho 3 giay** (de Sentinel/Cloudflare Turnstile captcha khoi tao xong)
4. Fill email bang `setNativeValue()` (trigger React synthetic events)
5. **Cho them 3 giay** roi click nut Continue:
   - `button[name="intent"][value="email"]`
   - `button[data-dd-action-name="Continue"]`
   - `button[type="submit"]`

**Xu ly loi:**
- Neu bi redirect ve `/log-in` → phat hien, doi 2.5s roi tim link "Sign-up" hoac redirect thang ve `/create-account`

---

### Buoc 2: Click "Continue with password" (content.js)

**URL trigger:** Tu dong khi phat hien `a[href="/create-account/password"]` tren trang

**Logic:**
1. Tim link `a[href="/create-account/password"]`
2. **Cho 2.5 giay** (Sentinel load xong)
3. Navigate sang trang dat mat khau

---

### Buoc 3: Dien mat khau (content.js — auth.openai.com/*/password)

**URL trigger:** `url.includes("/password")`

**Logic:**
1. Tim `input[name="new-password"]`, `input[name="current-password"]`, hoac `input[type="password"]`
2. **Phan biet login vs register**: neu `url.includes("/log-in")` hoac `name="current-password"` → dung mat khau Hotmail cu; nguoc lai → dung `chatgpt_password` moi
3. **Cho 3 giay** (Sentinel load)
4. Fill password bang `setNativeValue()`
5. **Cho 2.5 giay** roi click `button[type="submit"]` trong form

---

### Buoc 4: Lay ma xac nhan email (content.js — /email-verification)

**URL trigger:** `url.includes("/email-verification") && !pwdLink`

**Logic:**
1. Tim `input[name="code"]` hoac `input[autocomplete="one-time-code"]`
2. **Cho 6 giay** (cho email ve hop thu)
3. Gui message toi background.js: `action: "getVerificationCode"`

**Background.js xu ly lay OTP theo 3 cach (uu tien):**

```
Uu tien 1 (neu co refresh_token + client_id):
  → POST https://tools.dongvanfb.net/api/get_messages_oauth2
     { email, pass, refresh_token, client_id }

Uu tien 2 (neu OAuth2 that bai):
  → POST https://tools.dongvanfb.net/api/graph_messages
     { email, pass, refresh_token, client_id }

Uu tien 3 (fallback — chi can email + pass):
  → POST https://tools.dongvanfb.net/api/get_messages_2
     { email, pass }
```

**Parsing response:**
- Neu response co field `code` → tim 6 chu so
- Neu response co array `messages/data/results` → sap xep theo ngay moi nhat truoc
  - Loc email co subject/from chua: `chatgpt`, `openai`, `verification`, `verify`, `login code`, `one-time`...
  - Trich 6 chu so tu HTML email bang 4 pattern:
    1. `<p>123456</p>` (6 so trong the HTML rieng)
    2. `code: 123456` / `OTP: 123456` (keyword + so)
    3. Dong chi chua 6 so
    4. Bat ky 6 so nao (fallback)
- Loai bo false positive: `000000`, nam kieu `202401...`

**Sau khi co code:**
1. Fill vao input
2. **Cho 2 giay** roi click nut validate (khong phai nut resend)

**Xu ly loi khi chua co ma:**
- Retry dem tu dong
- Den lan retry thu 3: tu dong click nut **Resend** va doi 10 giay
- Cac lan sau: doi 8 giay moi retry

---

### Buoc 5: Dien thong tin "About You" (content.js — /about-you)

**URL trigger:** `url.includes("/about-you")` hoac `/registration`

**Profile tu sinh (Indian Name Bot Bypass) — khoi tao mot lan luc load:**
```js
FIRST = random tu danh sach 20 ten An Do (nam/nu)
SUR   = random tu danh sach 24 ho An Do
YEAR  = 2025 - random(20→30)  // Tuoi 20-30
MON   = random 1-12 (padded 2 chu so)
DAYN  = random 1-28 (padded 2 chu so)
AGE   = 2025 - YEAR
```

**Logic fill:**
- `firstName/firstname/given-name` → FIRST
- `lastName/lastname/family-name` → SUR
- `fullName/name` → `FIRST + ' ' + SUR`
- `birth/dob` → `MM/DD/YYYY` (hoac `YYYY-MM-DD` neu input type=date)
- `age` → AGE

**Sau khi fill:**
1. **Cho 2 giay** roi click `button[type="submit"]`
2. Ghi vao storage: `auto_gpt_running: false`, `auto_gpt_2fa_setup: true`
3. Log: `"Account registered successfully!"`

---

### Buoc 6: Skip Onboarding (content.js — chatgpt.com)

**Trigger:** Loop 800ms kiem tra noi dung body khi `!S.done2FA`

**Cac case skip:**
- `"What brings you to ChatGPT?"` → Click "Skip" / hoac chon option → Click "Next"
- `"You're all set"` / `"ChatGPT can make mistakes"` → Click "Continue" → **1.5s sau redirect settings**

**Sau khi skip xong:**
```js
chrome.storage.local.set({ auto_gpt_2fa_setup: true })
window.location.href = "https://chatgpt.com/#settings/Security"
```

---

## LUONG 2: BAT 2FA (Two-Factor Authentication)

### Trigger bat dau

**Cach 1 (Auto sau dang ky):** `auto_gpt_2fa_setup: true` duoc set sau buoc onboarding

**Cach 2 (Thu cong - popup):** Nhan nut "Bat 2FA" trong popup → set `auto_gpt_2fa_setup: true` → mo `chatgpt.com/#settings/Security`

**Truoc khi mo Settings:** Gui message `manualStart2FA` toi cac tab dang mo de reset state `S`:
```js
S = { cantScanClicked: false, filling: false, secret: null,
      done2FA: false, navToSettings: false, enableClicked: false }
window._agSec = null
```

---

### Step 1: Mo tab Security Settings

**URL:** `https://chatgpt.com/#settings/Security`

**Loop 800ms phat hien** `url.includes("/settings")` hoac `#settings` → goi `handleSettingsPage()`

---

### Step 2: Click sang tab "Bao mat/Security" (neu can)

**Logic:**
- Kiem tra body co text `Xac thuc hai buoc`, `Two-factor`, `Authenticator`, `MFA` khong
- Neu chua thay → tim nut `Bao mat` / `Security` hoac `a[href*="security"]` → click

---

### Step 3: Bat toggle MFA Authenticator

**Cach uu tien (Radix UI toggle):**
```
Tim: button[data-testid="mfa-authenticator-toggle"]
```

**Xu ly Radix scroll-lock bug:**
- Radix UI dat `body { pointer-events: none }` khi mo dialog
- Extension phai **restore** `pointer-events: auto` cho body va tat ca ancestor element truoc khi click
- Dispatch du 5 events: `pointerdown`, `mousedown`, `pointerup`, `mouseup`, `click` voi toa do clientX/clientY thuc
- **Sau 1 giay:** kiem tra toggle da bat chua (`aria-checked="true"` hoac `data-state="checked"`)
- Neu chua bat → reset `window._agMfaToggleClicked = false` de thu lai

**Cach fallback (khi khong co data-testid):**
- Tim `[role="switch"][aria-checked="false"]` visible
- Hoac duyet tat ca button/a → tim element nam trong row co text `two-factor`/`xac thuc`/`2fa`/`authenticat` + button co text `bat`/`enable`/`set`/`add`

---

### Step 4: Click "Trouble scanning?" / "Can't scan"

**Trigger:** `modalOpened = S.enableClicked || window._agMfaToggleClicked`

**Logic:**
- Tim button/a co text: `Trouble scanning?`, `gap van de khi quet`, `setup key`, `Can't scan`
- Click mot lan (guard bang `S.cantScanClicked`)

> **Tai sao can buoc nay?** OpenAI hien thi ma secret duoi dang QR code. Extension khong doc duoc anh QR nen phai click "Can't scan" de lo ra chuoi text Base32.

---

### Step 5: Doc Secret Base32 tu trang

**Ham `getTotpSecretFromPage()`:**

**Uu tien 1:** Tim element co aria-label "Copy code":
```
div[aria-label="Copy code"][title="Copy code"]
[aria-label="Copy code"][role="button"]
[title="Copy code"][role="button"]
```

**Uu tien 2:** Tim trong modal/dialog:
```
[aria-labelledby="enroll-totp-modal-title"]
[role="dialog"][data-state="open"]
div[role="dialog"]
```
→ Trong dialog: tim `[role="button"], code, pre, div[title], div[aria-label]`

**Uu tien 3:** Fallback — scan toan bo `document.body.innerText` tim pattern `[A-Z2-7]{16,}`

**Validate secret:** Phai match regex `^[A-Z2-7\s]{16,}$` (Base32 toi thieu 16 ky tu)

---

### Step 6: Hien thi Secret Widget + Copy Clipboard

**Ham `showSecretWidget(raw)`:**
1. Luu vao `chrome.storage.local: account_2fa_secret`
2. Update input field `#auto-gpt-2fa-secret`
3. **Tu dong copy vao clipboard** (navigator.clipboard → fallback execCommand)
4. Hien thi floating widget goc phai man hinh (mau xanh #10b981)

---

### Step 7: Sinh ma TOTP va dien vao o xac nhan

**Ham `fillAndVerifyCodeLocal(secret)` → goi `background.js: get2FACode`**

**Background.js sinh TOTP:**

**Cach 1 — Sinh offline (RFC 6238, hoan toan local):**
```
Dung crypto.subtle (HMAC-SHA1) trong Service Worker
  1. Decode Base32 → Uint8Array (key)
     - Normalize: uppercase, bo space, so 0→O, so 1→L
     - Alphabet: A-Z (=0-25), 2-7 (=26-31)
  2. counter = floor(Date.now() / 1000 / 30)   <- window 30s
  3. Counter → 8 byte big-endian ArrayBuffer
  4. HMAC-SHA1(key, counter) → 20 byte hash
  5. Dynamic truncation: offset = hash[19] & 0x0F
     code = (hash[offset..+3] & 0x7FFFFFFF) % 10^6
  6. Pad 0 trai → 6 chu so
```

**Cach 2 — API online (fallback):**
```
GET https://lay2fa.phh.info.vn/api/totp.php?secret=<SECRET>
```

**Parse response tu API:**
Tim field `code`, `otp`, `totp`, hoac `token` trong response (ho tro nested `data.*` va `results[0].*`)

**Dien TOTP:**
1. Tim input: `input#totp_otp`, `input[name="totp_otp"]`, `input[placeholder*="6-digit"]`, `input[autocomplete="one-time-code"]`
2. `setNativeValue(input, code)` — trigger React events
3. **Cho 400ms** roi click nut Verify

---

### Step 8: Click nut Verify

**Ham `clickTotpVerifyButton()`:**

**Cach tim button:**
1. Tat ca `button` visible → filter text = `"Verify"` hoac `"Xac minh"`, khong disabled
2. Fallback: `button.btn-primary`, `button._primary_2sicu_111` → filter text
3. Neu chi co 1 nut primary trong dialog → dung luon

**Click:**
- `scrollIntoView({ block: "center" })`
- `.click()` thong thuong
- Dispatch day du: `mousedown`, `mouseup`, `click`
- Retry: click lai sau 600ms va 1500ms

**Guard race condition:** Dat lock `S.filling = true` truoc khi fetch TOTP, chi reset khi click Verify that bai

---

### Step 9: Hoan thanh 2FA

**Khi Verify thanh cong:**
```js
S.done2FA = true
chrome.storage.local.set({ auto_gpt_2fa_setup: false })
```
- Dong dialog Settings (click `[data-testid="close-button"]` hoac `button[aria-label="Close"]`)
- **1.5 giay sau:** Goi `executePaymentFlow("IN", "INR", true)` de lay link checkout
- Copy link vao clipboard + hien thi widget goc phai man hinh

---

## VONG LAP CHINH (content.js)

**`setInterval` moi 800ms** — chi hoat dong khi:
- Extension con valid (`chrome.runtime?.id` ton tai)
- URL la `chatgpt.com`, `auth.openai.com`, `pay.openai.com`, hoac checkout pages
- `auto_gpt_running = true` HOAC `auto_gpt_2fa_setup = true` (hoac dang o checkout page)

**Routing theo URL:**

```
URL                          → Ham xu ly
──────────────────────────── → ─────────────────────────────
chatgpt.com/#settings/*      → handleSettingsPage()
chatgpt.com (khong settings) → skipOnboarding() + scheduleNavToSettings()
chatgpt.com/checkout/*       → handleCheckoutPage()
checkout.stripe.com/*        → handleCheckoutPage()
auth.openai.com/*            → Dang ky step 1-5
```

---

## XU LY LOI CHI TIET

### Giai doan dang ky

| Loi | Xu ly |
|-----|-------|
| Token sai format | Bao loi, khong chay |
| Bi redirect ve /log-in | Phat hien, cho 2.5s, click link sign-up hoac redirect |
| Sentinel/Captcha chua load | Cho cung 3s truoc moi action |
| Email chua co ma | Retry moi 8s, lan 3 click Resend, tiep tuc retry |
| Extension context invalidated | clearInterval dung loop |

### Giai doan 2FA

| Loi | Xu ly |
|-----|-------|
| Radix pointer-events: none | Restore body + ancestor elements truoc click |
| Toggle chua bat sau 1s | Reset flag, thu lai o tick tiep theo |
| Khong tim thay secret | Scan fallback toan body, thu 3 selector khac nhau |
| API TOTP loi | Log warning, unlock S.filling, retry o tick sau |
| Verify button khong tim thay | Retry them 2 lan (600ms, 1500ms) |
| Dialog da dong truoc khi doc secret | S.cantScanClicked guard ngan click lai |

---

## CAC API SU DUNG

| API | Muc dich | Method |
|-----|----------|--------|
| `https://tools.dongvanfb.net/api/get_messages_oauth2` | Doc email OTP qua OAuth2 token | POST |
| `https://tools.dongvanfb.net/api/graph_messages` | Doc email OTP qua Graph API | POST |
| `https://tools.dongvanfb.net/api/get_messages_2` | Doc email OTP qua email+pass | POST |
| `https://lay2fa.phh.info.vn/api/totp.php?secret=...` | Lay TOTP OTP online (fallback) | GET |
| `https://chatgpt.com/api/auth/session` | Lay accessToken ChatGPT | GET |
| `https://chatgpt.com/backend-api/payments/checkout` | Tao link thanh toan Stripe | POST |

---

## DIEM DAC BIET KY THUAT

### 1. Tai sao dung setNativeValue() thay vi gan el.value truc tiep?

ChatGPT dung React. React theo doi state qua `_valueTracker` internal. Gan truc tiep se khong trigger React re-render → nut Submit van disabled.

`setNativeValue()` hack `Object.getOwnPropertyDescriptor` de goi setter goc, reset tracker, dispatch `input` + `change` events.

### 2. Tai sao TOTP duoc sinh offline?

Service Worker co `crypto.subtle` (HMAC-SHA1) — du de implement RFC 6238 hoan toan cuc bo. Tranh phu thuoc server, nhanh hon, bao mat hon (secret khong roi may).

### 3. Tai sao phai cho 3-6 giay o moi buoc?

Cloudflare Sentinel / Turnstile captcha can thoi gian khoi tao. Neu dien qua nhanh, request se bi chan. Email delivery cung can 5-6 giay sau khi submit form.

### 4. Indian Profile la gi?

Tai khoan OpenAI tu An Do co gia INR thap hon nhieu → dung profile ten An Do + dia chi Mumbai. DOB ngau nhien tuoi 20-30 de tranh bot detection pattern co dinh.

---

## SEQUENCE DIAGRAM — LUONG DANG KY

```
User    popup.js   storage   content.js         background.js   dongvanfb API
 |         |          |           |                   |               |
 |--Start-->          |           |                   |               |
 |         |--set run->           |                   |               |
 |         |--open tab------------>                   |               |
 |         |          |           |--fill email------->               |
 |         |          |           |--click Continue--->               |
 |         |          |           |--fill password---->               |
 |         |          |           |--click Submit----->               |
 |         |          |           |                   |               |
 |         |          |           |--getVerificationCode message------>
 |         |          |           |                   |               |
 |         |          |           |                   |--POST get_messages_oauth2-->
 |         |          |           |                   |<--{code: "123456"}---------
 |         |          |           |<--{success, code}--|               |
 |         |          |           |--fill code-------->               |
 |         |          |           |--submit----------->               |
 |         |          |           |--fill about-you--->               |
 |         |          |           |--submit----------->               |
 |         |          |--set 2fa-->                   |               |
 |         |          |           |--skip onboarding-->               |
 |         |          |           |--navigate #settings/Security------>
```

---

## SEQUENCE DIAGRAM — LUONG BAT 2FA

```
User    popup.js   storage   content.js(settings)   background.js   lay2fa API
 |         |          |            |                      |               |
 |-Bat 2FA->          |            |                      |               |
 |         |--set 2fa->            |                      |               |
 |         |--send manualStart2FA-->                      |               |
 |         |--open #settings/Security-->                  |               |
 |         |          |            |--click Security tab-->               |
 |         |          |            |--click MFA toggle---->               |
 |         |          |            |  (restore pointer-events)            |
 |         |          |            |--click Trouble scanning?------------>|
 |         |          |            |--read Base32 secret-->               |
 |         |          |            |--showSecretWidget()-->               |
 |         |          |--set secret->                     |               |
 |         |          |            |--get2FACode message-->               |
 |         |          |            |                      |--GET totp.php->
 |         |          |            |                      |<-{code:"6543"}|
 |         |          |            |<--{code:"654321"}-----|               |
 |         |          |            |--fill TOTP input----->               |
 |         |          |            |--click Verify------->               |
 |         |          |--set 2fa=F->                      |               |
 |         |          |            |--close dialog------->               |
 |         |          |            |--get checkout link--->               |
 |         |          |            |--copy to clipboard--->               |
```
