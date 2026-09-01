# CapCut & ChatGPT Auto Register Suite

Dự án này là phiên bản hợp nhất các tính năng tự động tạo tài khoản của CapCut, Higgsfield, và ChatGPT vào trong một Giao diện Web (Web UI) duy nhất.
Tất cả đã được modular hóa theo kiến trúc sạch và hỗ trợ chạy hoàn toàn thông qua Docker.

## Tính năng

1. **CapCut Auto Register**:
   - Tạo bằng Hotmail (File).
   - Tạo bằng Domain riêng (Mail ảo tự sinh).
   - Tham gia Team tự động (Join Team Link).
2. **Higgsfield Auto**:
   - Tự động tạo và verify tài khoản Higgsfield qua Temp Mail.
3. **ChatGPT Signup**:
   - Tự động tạo tài khoản OpenAI.
   - Hỗ trợ mail iCloud HME (cần cấu hình iCloud HME trước), Outlook, Gmail Advanced.
4. **iCloud HME Manager**:
   - Quản lý Apple ID.
   - Tự động sinh email ẩn danh (Hide My Email) để đăng ký dịch vụ.
5. **Proxy Hỗ trợ**:
   - Proxy xoay vòng (TMProxy) tích hợp sẵn trong cấu hình Web UI.

---

## 🚀 Hướng dẫn Cài đặt & Chạy (Dành cho Người Dùng Cuối)

### Cách 1: Sử dụng Docker (Khuyên dùng - Nhanh nhất)

Bạn chỉ cần có `Docker` trên máy.

1. **Khởi chạy hệ thống**:
   ```bash
   docker compose up -d --build
   ```

2. **Truy cập Web UI**:
   - Mở trình duyệt và truy cập: [http://localhost:5050](http://localhost:5050)

3. **Cấu hình dữ liệu**:
   - Thêm danh sách mail (nếu dùng Hotmail) vào file `data/hotmails.txt`.
   - Các tài khoản đã tạo sẽ tự động được lưu vào cơ sở dữ liệu và hiển thị trên giao diện, hoặc bạn có thể xem trực tiếp nội dung trong tab **Tài khoản gần đây**.

*(Ghi chú: Toàn bộ dữ liệu tài khoản và cài đặt được lưu giữ an toàn trong thư mục `data/` nhờ Docker Volumes, bạn không lo mất data khi khởi động lại container).*

### Cách 2: Chạy Trực Tiếp (Local)

**Dành cho Windows:**
1. Cài đặt **Python 3.11** hoặc **Python 3.12** *(Lưu ý: Khuyến cáo KHÔNG dùng Python 3.13/3.14 vì các bản mới này yêu cầu cài thêm Microsoft C++ Build Tools nặng nề để biên dịch các thư viện như `greenlet`, `anyio`)*. Nhớ tích chọn **"Add python.exe to PATH"** khi cài đặt.
2. Chạy file khởi động tự động:
   - Cách dễ nhất: Nhấp đúp chuột vào file `run.bat` trong thư mục dự án.
   - Nếu dùng Terminal/VS Code: Mở Command Prompt hoặc PowerShell và gõ lệnh `.\run.bat` (hoặc `./run.bat` nếu dùng Git Bash).
3. File sẽ tự động cài đặt `requirements.txt` và khởi chạy Web Server.
4. Truy cập: [http://localhost:5050](http://localhost:5050)

**Dành cho Mac/Linux:**
1. Cài đặt Python 3.10+
2. Mở Terminal tại thư mục dự án và chạy file khởi động tự động:
   ```bash
   chmod +x run.sh
   ./run.sh
   ```
3. Truy cập: [http://localhost:5050](http://localhost:5050)

*(Nếu bạn muốn chạy thủ công không qua file run, hãy dùng: `pip install -r requirements.txt` -> `playwright install chromium firefox` -> `python src/web/app.py`)*

---

## 📂 Cấu trúc Thư mục

- `src/web/`: Server Flask và các API Routes.
- `src/bots/`: Mã nguồn của Bot CapCut, Higgsfield, ChatGPT, và iCloud HME.
- `src/auth/`: Module xử lý xác thực đăng nhập (sẵn sàng mở rộng tương lai).
- `ui/`: File Giao diện Web (HTML, CSS, JS).
- `data/`: Nơi lưu trữ Database SQLite (`database.db`).
- `data/accounts/`: Nơi xuất file tài khoản đã tạo.
- `docs/`: Chứa các file hướng dẫn chi tiết cho từng loại bot.

---
**Tận hưởng quá trình tạo tài khoản tự động hoàn toàn! 🚀**
