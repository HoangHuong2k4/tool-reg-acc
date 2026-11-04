#!/usr/bin/env bash
# =========================================================================
# Khởi động Grok Relay Server trên macOS / Linux
# =========================================================================
cd "$(dirname "$0")"

# Tìm binary Python 3 phù hợp
PYTHON_BIN=""
if [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
elif [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Lỗi: Không tìm thấy Python 3 trên máy Mac."
    echo "👉 Vui lòng cài đặt Python (ví dụ: brew install python3) để chạy relay."
    echo ""
    read -p "Nhấn phím bất kỳ để thoát..."
    exit 1
fi

echo "=================================================="
echo "   🚀 GROK MULTI-PROFILE RELAY SERVER (MACOS)    "
echo "=================================================="
echo "Dùng Python: $($PYTHON_BIN --version) ($PYTHON_BIN)"
echo "Đang khởi động relay chuyển tiếp mã Grok..."
echo "Giữ cửa sổ Terminal này mở trong khi săn mã."
echo "=================================================="
echo ""

exec "$PYTHON_BIN" -u "relay/server.py"

