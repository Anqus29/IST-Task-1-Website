import sqlite3

conn = sqlite3.connect("webstore.db")
c = conn.cursor()
for col in ["crop_x", "crop_y", "crop_width", "crop_height"]:
    try:
        c.execute(f"ALTER TABLE products ADD COLUMN {col} REAL;")
    except sqlite3.OperationalError:
        pass  # Column already exists
conn.commit()
conn.close()
print("Migration complete.")
