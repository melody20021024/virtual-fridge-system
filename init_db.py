import sqlite3

conn = sqlite3.connect('fridge.db')
cursor = conn.cursor()

# ⚠️ 開發階段：先刪除原資料表
cursor.execute('DROP TABLE IF EXISTS fridge')

# ✅ 重建資料表，將 quantity 改為 REAL（浮點數類型）
cursor.execute('''
    CREATE TABLE fridge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        quantity REAL,
        expiry_date DATE
    )
''')

conn.commit()
conn.close()
print("✅ 資料庫建立完成 fridge.db，含分類欄位與正確數量格式")
