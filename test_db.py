import sqlite3
def get_db_setting(key, default=""):
    try:
        conn = sqlite3.connect("data/database.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row["value"]
    except Exception as e:
        print("Error:", e)
    return default
print(repr(get_db_setting("MASA_TOKEN")))
