#!/usr/bin/env python3
import pymysql
import sys

def setup_database():
    try:
        # Kết nối MySQL (không chọn DB để tạo DB trước)
        conn = pymysql.connect(host='localhost', user='root', password='')
        cursor = conn.cursor()
        
        # 1. Tạo Database
        cursor.execute("CREATE DATABASE IF NOT EXISTS auto_register CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print("Database 'auto_register' checked/created.")
        
        # Chọn DB vừa tạo
        cursor.execute("USE auto_register")
        
        # 2. Tạo bảng settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                `key` VARCHAR(50) PRIMARY KEY,
                `value` VARCHAR(255)
            )
        """)
        
        # 3. Tạo bảng accounts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                app VARCHAR(20) NOT NULL,
                uid VARCHAR(100),
                email VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        default_settings = {
            "PROXY_TYPE": "proxyquick",
            "PROXY_API_TOKEN": "proxyquick6_9df2f4385910e1a5d4bf45498a783abf845ba8776cb2642cb31839a1740b29ef",
            "PROXY_MERCHANT": "a20f20d6-9512-40fd-9a12-eeff809fdaeb",
            "PROXY_ID": "953319",
            "PROXYXOAY_KEY": ""
        }
        
        for k, v in default_settings.items():
            cursor.execute("INSERT IGNORE INTO settings (`key`, `value`) VALUES (%s, %s)", (k, v))
            
        conn.commit()
        print("Bảng 'settings' và 'accounts' đã được thiết lập thành công.")
        print("Dữ liệu mặc định đã được thêm vào.")
        
    except pymysql.MySQLError as e:
        print(f"Lỗi MySQL: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals() and conn.open:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    setup_database()
