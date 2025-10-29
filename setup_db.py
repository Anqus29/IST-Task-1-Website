import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "webstore.db")

CREATE_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_seller INTEGER NOT NULL DEFAULT 0,
    business_name TEXT,
    seller_description TEXT,
    rating REAL DEFAULT 0,
    total_sales INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL CHECK(price >= 0),
    stock INTEGER DEFAULT 0,
    image_url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(seller_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER,
    buyer_name TEXT,
    buyer_email TEXT,
    shipping_address TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    total REAL NOT NULL CHECK(total >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(buyer_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE RESTRICT
);
-- new addresses table to store saved shipping addresses per user
CREATE TABLE IF NOT EXISTS addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    label TEXT,
    address_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, address_text)
);
"""

SAMPLE_USERS = [
    # username, email, password_plain, is_admin, is_seller, business_name, desc, rating, total_sales
    ("angus", "angus@example.com", "password123", 1, 1, "Alice's Antiques", "Specialized in rare items", 4.5, 25),
    ("bob", "bob@example.com", "password123", 0, 0, None, None, 0, 0),
    ("charlie", "charlie@example.com", "password123", 0, 1, "Tech Haven", "Gadgets and electronics", 4.8, 150)
]

SAMPLE_PRODUCTS = [
    (1, "Vintage Clock", "An antique wall clock in good condition.", 49.99, 5),
    (1, "Crystal Vase", "Hand-cut crystal vase from 1920s.", 299.99, 2),
    (3, "Wireless Mouse", "Ergonomic wireless mouse, black.", 19.95, 25),
    (3, "Mechanical Keyboard", "RGB mechanical keyboard with blue switches.", 89.99, 10)
]

# optional sample addresses for seeded users
SAMPLE_ADDRESSES = [
    (1, "Home", "12 Example St, Springfield, SP 12345"),
    (3, "Office", "99 Tech Park, Suite 200, Metropolis, MT 54321")
]

def initialize_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()
    c.executescript(CREATE_SCHEMA)
    users_hashed = []
    for u in SAMPLE_USERS:
        pw_hash = generate_password_hash(u[2])
        users_hashed.append((u[0], u[1], pw_hash, u[3], u[4], u[5], u[6], u[7], u[8]))
    c.executemany('''
        INSERT INTO users (username, email, password_hash, is_admin, is_seller, business_name, seller_description, rating, total_sales)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', users_hashed)
    c.executemany('''
        INSERT INTO products (seller_id, title, description, price, stock)
        VALUES (?, ?, ?, ?, ?)
    ''', SAMPLE_PRODUCTS)
    # insert sample addresses (if any)
    c.executemany('''
        INSERT OR IGNORE INTO addresses (user_id, label, address_text) VALUES (?, ?, ?)
    ''', SAMPLE_ADDRESSES)
    conn.commit()
    conn.close()
    print("Database created at", DB_PATH)

if __name__ == "__main__":
    initialize_db()
