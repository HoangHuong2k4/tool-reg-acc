import sqlite3
import os
DB_PATH = "data/database.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
try:
    cursor.execute("INSERT INTO settings (`key`, `value`) VALUES (?, ?) ON CONFLICT(`key`) DO UPDATE SET `value`=excluded.`value`", ("TEST_KEY", "TEST_VALUE"))
    conn.commit()
    print("Upsert succeeded")
except Exception as e:
    print("Upsert failed:", e)
