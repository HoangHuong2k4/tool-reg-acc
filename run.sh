#!/bin/bash

# run.sh - Dành cho Mac/Linux

# Chuyển tới thư mục chứa script
cd "$(dirname "$0")"

echo "========================================="
echo "   Khởi động Capcut/GPT Reg System (Mac/Linux)"
echo "========================================="

# Kiểm tra Python3
if ! command -v python3 &> /dev/null
then
    echo "Lỗi: Không tìm thấy Python3. Vui lòng cài đặt Python3 trước khi chạy."
    exit 1
fi

# Tạo thư mục venv nếu chưa có
if [ ! -d "venv" ]; then
    echo "[*] Chưa có virtual environment. Đang tạo môi trường ảo (venv)..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Lỗi: Không thể tạo virtual environment."
        exit 1
    fi
    echo "[*] Khởi tạo thành công."
fi

# Kích hoạt venv
echo "[*] Kích hoạt môi trường ảo..."
source venv/bin/activate

# Cập nhật pip và cài đặt thư viện
echo "[*] Kiểm tra và cài đặt thư viện từ requirements.txt..."
python -m pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Lỗi: Cài đặt thư viện thất bại."
    exit 1
fi

# Export PYTHONPATH để nhận module src
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "========================================="
echo "        Hệ thống đang khởi chạy..."
echo "     Truy cập http://localhost:5050"
echo "========================================="

# Chạy app Flask
python src/web/app.py
