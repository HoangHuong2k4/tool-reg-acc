# HƯỚNG DẪN CHẠY VÀ XỬ LÝ LỖI (NOTE)

Dưới đây là các câu lệnh quan trọng bạn cần dùng khi sử dụng tool Auto Register. Bạn có thể mở Terminal / iTerm (trên Mac) và copy dán các lệnh này.

---

## 1. Lệnh Khởi động Tool (Chạy Web Server)

Di chuyển vào thư mục dự án và chạy file `web_app.py`:

```bash
cd /Users/huong/TaiNguyen/capcut-regaccc
python3 web_app.py
```

> Sau khi chạy lệnh này, bạn mở trình duyệt web (Chrome/Safari) và truy cập vào địa chỉ: **http://localhost:5050**

---

## 2. Lệnh Xử lý lỗi "Port 5050 đã được sử dụng" (Address already in use)

Nếu bạn chạy tool mà bị báo lỗi không thể khởi động vì port 5050 đang bận (do lần trước tắt chưa hết), hãy dùng 2 lệnh sau để diệt process cũ:

**Cách 1 (Dùng lsof - Khuyên dùng):**
```bash
kill -9 $(lsof -t -i:5050)
```
Lệnh trên sẽ tìm chính xác tiến trình nào đang giữ port 5050 và ép nó tắt ngay lập tức.

**Cách 2 (Dùng pkill):**
```bash
pkill -f "python3 web_app.py"
```
Lệnh này sẽ tắt tất cả các tiến trình python đang chạy file `web_app.py`.

---

## 3. Lệnh Đóng toàn bộ Chrome (Nếu máy bị lag do kẹt quá nhiều tab)

Nếu chức năng "💥 ĐÓNG TRÌNH DUYỆT" trên web bị lỗi hoặc bạn muốn chủ động tắt sạch các cửa sổ Chrome ẩn:

```bash
pkill -f "Google Chrome"
```
*(Lưu ý: Lệnh này sẽ đóng toàn bộ Chrome trên máy Mac của bạn, bao gồm cả các tab bạn đang lướt web bình thường).*

---

## 4. Lệnh Khởi tạo lại Database (MySQL)
Nếu bạn lỡ tay xóa mất bảng hoặc muốn reset lại toàn bộ hệ thống Database `auto_register`:

```bash
cd /Users/huong/TaiNguyen/capcut-regaccc
python3 setup_db.py
```
*(Script này tự động kiểm tra và tạo lại các bảng Cài đặt và Tài khoản, đồng thời không làm mất dữ liệu hiện có).*
