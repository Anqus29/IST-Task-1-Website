import sqlite3
import os
from datetime import datetime, timedelta
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
    is_verified INTEGER NOT NULL DEFAULT 0,
    business_name TEXT,
    seller_description TEXT,
    profile_picture TEXT,
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
    category TEXT DEFAULT 'Other',
    condition TEXT DEFAULT 'used',
    location TEXT,
    view_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_auction INTEGER NOT NULL DEFAULT 0,
    starting_bid REAL,
    current_bid REAL,
    auction_end TEXT,
    reserve_price REAL,
    buy_now_price REAL,
    FOREIGN KEY(seller_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER,
    buyer_name TEXT,
    buyer_email TEXT,
    shipping_address TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    refund_status TEXT,
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
-- product reviews table
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    title TEXT,
    body TEXT,
    seller_response TEXT,
    is_approved INTEGER NOT NULL DEFAULT 1,
    approved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(product_id, user_id)
);
-- favorites/wishlist
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE(user_id, product_id)
);
-- notifications
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    link TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
-- password reset tokens
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
-- product reports
CREATE TABLE IF NOT EXISTS product_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    reporter_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY(reporter_id) REFERENCES users(id) ON DELETE CASCADE
);
-- recently viewed products
CREATE TABLE IF NOT EXISTS product_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER NOT NULL,
    viewed_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
);
-- auction bids
CREATE TABLE IF NOT EXISTS bids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    bid_amount REAL NOT NULL CHECK(bid_amount > 0),
    is_winning INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

SAMPLE_USERS = [
    # username, email, password_plain, is_admin, is_seller, business_name, desc, rating, total_sales
    ("angus", "angus@example.com", "password123", 1, 1, "Coastal Marine Supply", "Premium sailing equipment and boat sales", 4.9, 45),
    ("bob", "bob@example.com", "password123", 0, 0, None, None, 0, 0),
    ("charlie", "charlie@example.com", "password123", 0, 1, "Ocean Breeze Yachts", "Quality sailboats and rigging specialists", 4.7, 82)
]

SAMPLE_PRODUCTS = [
    # seller_id, title, description, price, stock, category, image_url
    # Sailboats
    (1, "14ft Fiberglass Daysailer", "Stable daysailer ideal for learning and weekend fun. Easy to handle single-handed.", 2500.00, 1, "Sailboats", "boat1.jpg"),
    (3, "22ft Cruising Sloop", "Comfortable cruiser with cabin, perfect for coastal adventures.", 12500.00, 1, "Sailboats", "boat2.jpg"),
    # Sails
    (1, "Spinnaker Sail 30ft", "Lightweight nylon spinnaker in good, serviceable condition.", 450.00, 2, "Sails", "sail1.jpg"),
    (3, "Main Sail 25ft", "Dacron mainsail with two reef points, excellent shape.", 890.00, 3, "Sails", "sail2.jpg"),
    (1, "Storm Jib 20ft", "Heavy-duty storm jib for rough weather sailing.", 320.00, 4, "Sails", "sail3.jpg"),
    # Rigging
    (1, "Stainless Steel Anchor 10kg", "High holding-power plow anchor suitable for 25-30ft boats.", 120.00, 10, "Rigging", "anchor1.jpg"),
    (3, "Rope Halyard Set", "Complete halyard set with shackles for 30ft sailboat.", 215.00, 8, "Rigging", "rigging1.jpg"),
    (1, "Turnbuckle Kit", "Stainless steel turnbuckles for shroud adjustment.", 85.00, 15, "Rigging", "turnbuckle1.jpg"),
    # Safety
    (1, "Automatic Inflatable Life Jacket", "CO2 automatic/manual inflation PFD (Type V).", 89.99, 15, "Safety", "pfd1.jpg"),
    (3, "Flare Kit", "Complete offshore flare kit with SOLAS-approved flares.", 125.00, 7, "Safety", "flare1.jpg"),
    (1, "EPIRB Emergency Beacon", "406 MHz EPIRB with GPS for emergency situations.", 350.00, 5, "Safety", "epirb1.jpg"),
    # Gear & Accessories
    (1, "Marine GPS Chartplotter", "Compact GPS with coastal charts and waypoint tracking.", 699.00, 5, "Gear", "gps1.jpg"),
    (3, "Sailing Gloves - Kevlar", "Professional racing gloves with grip and finger protection.", 45.00, 20, "Accessories", "gloves1.jpg"),
    (1, "Anchor Windlass Electric", "12V electric windlass for easy anchor deployment.", 550.00, 3, "Accessories", "windlass1.jpg"),
    (3, "Teak Deck Grating", "Marine-grade teak grating panels for cockpit.", 180.00, 6, "Accessories", "teak1.jpg")
]

# Auction products with special fields - basic ones
# (seller_id, title, description, price, stock, category, image_url, is_auction, starting_bid, current_bid, auction_end, reserve_price, buy_now_price)
SAMPLE_AUCTIONS = [
    (1, "Laser Racing Dinghy - COMPETITIVE READY", 
     "Competition-ready Laser dinghy in excellent condition with new sail and rigging. Great for racing or learning high-performance sailing. Hull in very good shape with minimal wear. Includes boat cover and launching dolly.",
     0, 1, "Sailboats", "https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=400",
     1, 1200.00, 1200.00, None, 2000.00, 2800.00),  # auction_end will be set to 3 days from now
    
    (3, "VHF Marine Radio with DSC - SAFETY ESSENTIAL",
     "Waterproof VHF marine radio with Digital Selective Calling (DSC) and GPS integration. Essential safety equipment for any boat. Like new condition, barely used.",
     0, 1, "Gear", "https://images.unsplash.com/photo-1606041011872-596597976b25?w=400",
     1, 189.00, 189.00, None, 250.00, 350.00)
]

# Additional detailed auction products (with condition and location)
DETAILED_AUCTIONS = [
    {
        'seller_id': 1,
        'title': 'Classic Wooden Daysailer - ONE OF A KIND',
        'description': 'Beautiful 1970s 16ft wooden daysailer in excellent sailing condition. Recently revarnished, includes main and jib. A rare find and a head-turner at the marina.',
        'price': 0,
        'stock': 1,
        'image_url': 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=400',
        'category': 'Sailboats',
        'condition': 'used',
        'location': 'Springfield, SP',
        'is_auction': 1,
        'starting_bid': 1500.00,
        'current_bid': 1500.00,
        'auction_end': None,  # Will be set to 3 days from now
        'reserve_price': 3500.00,
        'buy_now_price': 5500.00
    },
    {
        'seller_id': 3,
        'title': 'Offshore Cruising Sail - AUCTION',
        'description': 'Dacron cruising mainsail for 32-34ft boats. Two reef points, excellent condition. Reserve not met yet - bid now!',
        'price': 0,
        'stock': 1,
        'image_url': 'https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=400',
        'category': 'Sails',
        'condition': 'new',
        'location': 'Metropolis, MT',
        'is_auction': 1,
        'starting_bid': 300.00,
        'current_bid': 300.00,
        'auction_end': None,  # Will be set to 12 hours from now
        'reserve_price': 600.00,
        'buy_now_price': 900.00
    }
]

# Sample bids for auctions - will be created after products are inserted
SAMPLE_BIDS = []  # Bids will be added dynamically for the detailed auctions

# optional sample addresses for seeded users
SAMPLE_ADDRESSES = [
    (1, "Home", "12 Example St, Springfield, SP 12345"),
    (3, "Office", "99 Tech Park, Suite 200, Metropolis, MT 54321")
]

def initialize_db():
    # Force close any existing connections and remove database
    if os.path.exists(DB_PATH):
        try:
            # Try to remove directly first
            os.remove(DB_PATH)
            print(f"Removed existing database: {DB_PATH}")
        except PermissionError:
            # If locked, drop all tables instead
            print(f"⚠️  Database is locked by another process")
            print(f"🔄 Dropping all existing tables and recreating...")
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                
                # Get all table names
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = [row[0] for row in c.fetchall()]
                
                # Drop all tables
                c.execute("PRAGMA foreign_keys = OFF")
                for table in tables:
                    c.execute(f"DROP TABLE IF EXISTS {table}")
                    print(f"   Dropped table: {table}")
                c.execute("PRAGMA foreign_keys = ON")
                conn.commit()
                conn.close()
                print(f"✅ All tables dropped successfully")
            except Exception as e:
                print(f"⚠️  Error during table drop: {e}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()
    c.executescript(CREATE_SCHEMA)
    
    # Insert users
    users_hashed = []
    for u in SAMPLE_USERS:
        pw_hash = generate_password_hash(u[2])
        users_hashed.append((u[0], u[1], pw_hash, u[3], u[4], u[5], u[6], u[7], u[8]))
    c.executemany('''
        INSERT INTO users (username, email, password_hash, is_admin, is_seller, business_name, seller_description, rating, total_sales)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', users_hashed)
    
    # Insert regular products
    c.executemany('''
        INSERT INTO products (seller_id, title, description, price, stock, category, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', SAMPLE_PRODUCTS)
    
    # Insert auction products with calculated end times
    for auction in SAMPLE_AUCTIONS:
        seller_id, title, desc, price, stock, cat, img, is_auction, start_bid, cur_bid, _, reserve, buy_now = auction
        
        # Set auction end times
        if "Record Player" in title:
            auction_end = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        else:  # Racing sail
            auction_end = (datetime.now() + timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S')
        
        c.execute('''
            INSERT INTO products (
                seller_id, title, description, price, stock, category, image_url,
                is_auction, starting_bid, current_bid, auction_end, reserve_price, buy_now_price
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (seller_id, title, desc, price, stock, cat, img, is_auction, start_bid, cur_bid, auction_end, reserve, buy_now))
    
    # Insert detailed auction products with condition and location
    for auction_data in DETAILED_AUCTIONS:
        # Set auction end time based on title
        if "Daysailer" in auction_data['title']:
            auction_data['auction_end'] = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
        else:  # Cruising sail
            auction_data['auction_end'] = (datetime.now() + timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S')
        
        c.execute('''
            INSERT INTO products (
                seller_id, title, description, price, stock, image_url, 
                category, condition, location, is_auction, starting_bid, 
                current_bid, auction_end, reserve_price, buy_now_price
            ) VALUES (
                :seller_id, :title, :description, :price, :stock, :image_url,
                :category, :condition, :location, :is_auction, :starting_bid,
                :current_bid, :auction_end, :reserve_price, :buy_now_price
            )
        ''', auction_data)
    
    # Insert sample bids
    for bid in SAMPLE_BIDS:
        product_id, user_id, bid_amount, is_winning = bid
        c.execute('''
            INSERT INTO bids (product_id, user_id, bid_amount, is_winning, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (product_id, user_id, bid_amount, is_winning, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    # Insert sample addresses (if any)
    c.executemany('''
        INSERT OR IGNORE INTO addresses (user_id, label, address_text) VALUES (?, ?, ?)
    ''', SAMPLE_ADDRESSES)
    
    conn.commit()
    conn.close()
    print(f"✅ Database created at {DB_PATH}")
    print("✅ Added 3 users (angus/admin, bob/buyer, charlie/seller)")
    print(f"✅ Added {len(SAMPLE_PRODUCTS)} sailing products (boats, sails, rigging, safety gear, accessories)")
    print(f"✅ Added {len(SAMPLE_AUCTIONS) + len(DETAILED_AUCTIONS)} auction products (sailing equipment)")
    print(f"✅ Added {len(SAMPLE_BIDS)} sample bid(s)")
    print("🎯 Ready to test! Run: python app.py")

if __name__ == "__main__":
    initialize_db()
