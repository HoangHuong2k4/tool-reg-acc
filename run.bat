@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo =========================================
echo    Khoi dong Capcut/GPT Reg System (Windows)
echo =========================================

:: Kiểm tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Loi: Khong tim thay Python. Vui long cai dat Python va them vao PATH.
    pause
    exit /b 1
)

:: Tạo thư mục venv nếu chưa có
if not exist "venv\Scripts\activate.bat" (
    echo [*] Chua co virtual environment. Dang tao moi truong ao (venv)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo Loi: Khong the tao virtual environment.
        pause
        exit /b 1
    )
    echo [*] Khoi tao thanh cong.
)

:: Kích hoạt venv
echo [*] Kich hoat moi truong ao...
call venv\Scripts\activate.bat

:: Cập nhật pip và cài đặt thư viện
echo [*] Kiem tra va cai dat thu vien tu requirements.txt...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Loi: Cai dat thu vien that bai.
    pause
    exit /b 1
)

:: Đặt PYTHONPATH
set PYTHONPATH=%cd%

echo =========================================
echo        He thong dang khoi chay...
echo      Truy cap http://localhost:5050
echo =========================================

:: Chạy app Flask
python src\web\app.py

pause
