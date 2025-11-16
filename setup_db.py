# All migration and error image creation logic is now handled in this file. No need for separate scripts.
import sqlite3
import os
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "webstore.db")

# Local images available
LOCAL_IMAGES = [
    '/static/img/sailing-yacht-20ft.jpg',
    '/static/img/racing-dinghy-14ft.jpg',
    '/static/img/luxury-cruiser-28ft.jpg',
    '/static/img/catamaran-16ft.jpg',
    '/static/img/wooden-sloop-vintage.jpg',
    '/static/img/racing-yacht-performance.jpg',
    '/static/img/foul-weather-jacket-red.jpg',
    '/static/img/custom-rowboat.jpg',
    '/static/img/sailing-gloves-premium.jpg',
    '/static/img/teak-deck-panels.jpg',
    '/static/img/sailing-boots-waterproof.jpg',
    '/static/img/logo.png'
]

# Categories for sailing/boating products
CATEGORIES = ['Sailboats', 'Powerboats', 'Dinghies', 'Sails', 'Rigging', 'Safety Equipment', 
              'Navigation', 'Anchoring', 'Deck Hardware', 'Electronics', 'Maintenance', 'Apparel']

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
    # username, email, password_plain, is_admin, is_seller, business_name, desc, rating, total_sales, profile_picture
    ("angus", "angus@example.com", "password123", 1, 1, "Coastal Marine Supply", "Premium sailing equipment and boat sales", 4.9, 45, "/static/img/product1.jpg"),
    ("bob", "bob@example.com", "password123", 0, 0, None, None, 0, 0, "/static/img/product2.jpg"),
    ("charlie", "charlie@example.com", "password123", 0, 1, "Ocean Breeze Yachts", "Quality sailboats and rigging specialists", 4.7, 82, "/static/img/product3.jpg"),
    ("diana", "diana@example.com", "password123", 0, 1, "Harbor Outfitters", "Marine apparel and accessories", 4.5, 33, "/static/img/product4.jpg"),
    ("eva", "eva@example.com", "password123", 0, 0, None, None, 0, 0, "/static/img/product5.jpg"),
    ("frank", "frank@example.com", "password123", 0, 1, "Bay Boatworks", "Custom boat building and repairs", 4.8, 21, "/static/img/product6.jpg"),
    ("george", "george@example.com", "password123", 0, 0, None, None, 0, 0, "/static/img/product1.jpg"),
    ("hannah", "hannah@example.com", "password123", 0, 0, None, None, 0, 0, "/static/img/product2.jpg")
]

SAMPLE_PRODUCTS = [
    # seller_id, title, description, price, stock, category, image_url
    (1, "Classic 20ft Sailing Yacht", "Beautiful classic yacht with mahogany trim. Perfect for weekend coastal cruising. Recently serviced, ready to sail.", 15500.00, 1, "Sailboats", "/static/img/sailing-yacht-20ft.jpg"),
    (3, "14ft Racing Dinghy", "Competition-ready racing dinghy. Fast and responsive, ideal for club racing or training.", 3200.00, 2, "Sailboats", "/static/img/racing-dinghy-14ft.jpg"),
    (1, "Luxury 100ft Cruiser", "Spacious cruiser with full cabin amenities. Sleeps 4, galley, head, and navigation station.", 28900.00, 1, "Yachts", "/static/img/luxury-cruiser-28ft.jpg"),
    (3, "16ft Catamaran", "Stable and fast catamaran perfect for beach sailing. Easy to trailer and launch.", 5800.00, 1, "Sailboats", "/static/img/catamaran-16ft.jpg"),
    (1, "Vintage Wooden Sloop", "Restored 1960s wooden sloop. Beautiful lines, excellent condition. A real head-turner.", 12000.00, 1, "Sailboats", "/static/img/wooden-sloop-vintage.jpg"),
    (3, "Performance Racing Yacht", "High-performance racing yacht with carbon fiber mast. Competitive and well-maintained.", 35000.00, 1, "Yachts", "/static/img/racing-yacht-performance.jpg"),
    # New products for new sellers
    (4, "Marine Rain Jacket", "Waterproof jacket for sailing in rough weather. Breathable and lightweight.", 120.00, 15, "Clothing", "/static/img/foul-weather-jacket-red.jpg"),
    (6, "Custom Rowboat", "Hand-built rowboat, perfect for lakes and rivers. Durable and easy to row.", 2100.00, 2, "Dinghies", "/static/img/custom-rowboat.jpg"),
    (4, "Sailing Sunglasses", "Polarized sunglasses for glare reduction on the water.", 60.00, 20, "Accessories", "/static/img/sailing-gloves-premium.jpg"),
    (6, "Boat Repair Kit", "Complete kit for emergency boat repairs. Includes epoxy, tape, and tools.", 75.00, 10, "Maintenance", "/static/img/teak-deck-panels.jpg"),
    (4, "Deck Shoes", "Non-slip deck shoes for safe movement on wet surfaces.", 80.00, 18, "Apparel", "/static/img/sailing-boots-waterproof.jpg"),
    (6, "Bay Boatworks Hoodie", "Warm hoodie with Bay Boatworks logo. Perfect for chilly mornings.", 45.00, 25, "Apparel", "/static/img/logo.png"),
]

# Auction products with special fields - basic ones
# (seller_id, title, description, price, stock, category, image_url, is_auction, starting_bid, current_bid, auction_end, reserve_price, buy_now_price)
SAMPLE_AUCTIONS = [
    (1, "Laser Racing Dinghy - COMPETITIVE READY", 
     "Competition-ready Laser dinghy in excellent condition with new sail and rigging. Great for racing or learning high-performance sailing. Hull in very good shape with minimal wear. Includes boat cover and launching dolly.",
     0, 1, "Sailboats", "/static/img/product3.jpg",
     1, 1200.00, 1200.00, None, 2000.00, 2800.00),  # auction_end will be set to 3 days from now
    
    (3, "VHF Marine Radio with DSC - SAFETY ESSENTIAL",
     "Waterproof VHF marine radio with Digital Selective Calling (DSC) and GPS integration. Essential safety equipment for any boat. Like new condition, barely used.",
     0, 1, "Electronics", "/static/img/product4.jpg",
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
        'image_url': '/static/img/product5.jpg',
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
        'image_url': '/static/img/product6.jpg',
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
        users_hashed.append((u[0], u[1], pw_hash, u[3], u[4], u[5], u[6], u[7], u[8], u[9]))
    c.executemany('''
        INSERT INTO users (username, email, password_hash, is_admin, is_seller, business_name, seller_description, rating, total_sales, profile_picture)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    
    # Insert example reviews
    SAMPLE_REVIEWS = [
        (1, 1, 5, 'Amazing quality!', 'This product exceeded my expectations. Highly recommended!', 1),
        (1, 2, 4, 'Good value', 'Works well, but shipping was slow.', 1),
        (2, 1, 3, 'Average', 'It does the job, but nothing special.', 1),
        (2, 3, 5, 'Perfect!', 'Exactly what I needed for my boat.', 1),
        (3, 2, 2, 'Not great', 'Had some issues with durability.', 1),
        (4, 4, 5, 'Great jacket!', 'Kept me dry during a storm. Would buy again.', 1),
        (5, 5, 4, 'Nice sunglasses', 'Reduces glare well, stylish too.', 1),
        (6, 6, 5, 'Excellent repair kit', 'Saved my trip when my boat needed a quick fix.', 1),
        (7, 4, 5, 'Comfortable shoes', 'Perfect for deck work, no slips.', 1),
        (8, 6, 4, 'Warm hoodie', 'Very cozy and well made.', 1),
    ]
    c.executemany('''
        INSERT INTO reviews (product_id, user_id, rating, title, body, is_approved)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', SAMPLE_REVIEWS)

    # Insert sample orders
    SAMPLE_ORDERS = [
        # (buyer_id, buyer_name, buyer_email, shipping_address, status, refund_status, total)
        (2, 'Bob', 'bob@example.com', '12 Example St, Springfield, SP 12345', 'completed', None, 15500.00),
        (5, 'Eva', 'eva@example.com', '99 Tech Park, Suite 200, Metropolis, MT 54321', 'pending', None, 3200.00)
    ]
    c.executemany('''
        INSERT INTO orders (buyer_id, buyer_name, buyer_email, shipping_address, status, refund_status, total)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', SAMPLE_ORDERS)

    # Insert sample order items
    SAMPLE_ORDER_ITEMS = [
        # (order_id, product_id, quantity, unit_price)
        (1, 1, 1, 15500.00),
        (2, 2, 1, 3200.00)
    ]
    c.executemany('''
        INSERT INTO order_items (order_id, product_id, quantity, unit_price)
        VALUES (?, ?, ?, ?)
    ''', SAMPLE_ORDER_ITEMS)

    # Insert sample favorites
    SAMPLE_FAVORITES = [
        # (user_id, product_id)
        (2, 1),
        (5, 2),
        (1, 3)
    ]
    c.executemany('''
        INSERT INTO favorites (user_id, product_id)
        VALUES (?, ?)
    ''', SAMPLE_FAVORITES)

    # Insert sample notifications
    SAMPLE_NOTIFICATIONS = [
        # (user_id, message, link, is_read)
        (1, 'Welcome to Sailor\'s Bay!', None, 1),
        (2, 'Your order has shipped.', '/order/1', 0)
    ]
    c.executemany('''
        INSERT INTO notifications (user_id, message, link, is_read)
        VALUES (?, ?, ?, ?)
    ''', SAMPLE_NOTIFICATIONS)

    # Insert sample product reports
    SAMPLE_REPORTS = [
        # (product_id, reporter_id, reason, status)
        (2, 5, 'Suspected counterfeit', 'pending'),
        (3, 2, 'Incorrect description', 'resolved')
    ]
    c.executemany('''
        INSERT INTO product_reports (product_id, reporter_id, reason, status)
        VALUES (?, ?, ?, ?)
    ''', SAMPLE_REPORTS)

    # Insert sample product views
    SAMPLE_VIEWS = [
        # (user_id, product_id)
        (1, 1),
        (2, 2),
        (3, 3)
    ]
    for v in SAMPLE_VIEWS:
        c.execute('''
            INSERT INTO product_views (user_id, product_id, viewed_at)
            VALUES (?, ?, ?)
        ''', (v[0], v[1], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Insert sample bids
    SAMPLE_BIDS = [
        # (product_id, user_id, bid_amount, is_winning)
        (1, 2, 1600.00, 1),
        (2, 5, 3500.00, 0)
    ]
    for bid in SAMPLE_BIDS:
        product_id, user_id, bid_amount, is_winning = bid
        c.execute('''
            INSERT INTO bids (product_id, user_id, bid_amount, is_winning, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (product_id, user_id, bid_amount, is_winning, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Insert sample password reset tokens
    SAMPLE_RESET_TOKENS = [
        # (user_id, token, expires_at)
        (1, 'sampletoken1', (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')),
        (2, 'sampletoken2', (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'))
    ]
    for t in SAMPLE_RESET_TOKENS:
        c.execute('''
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES (?, ?, ?)
        ''', t)

    # Insert sample addresses (if any)
    c.executemany('''
        INSERT OR IGNORE INTO addresses (user_id, label, address_text) VALUES (?, ?, ?)
    ''', SAMPLE_ADDRESSES)

    conn.commit()
    conn.close()
    print(f"✅ Database created at {DB_PATH}")
    print("✅ Added sample users, products, auctions, reviews, orders, bids, favorites, notifications, reports, views, and reset tokens.")
    print("🎯 Ready to test! Run: python app.py")

def update_product_images():
    """Update ALL products with local image URLs from static/img folder"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Local images available
    LOCAL_IMAGES = [
        '/static/img/product1.jpg',
        '/static/img/product2.jpg',
        '/static/img/product3.jpg',
        '/static/img/product4.jpg',
        '/static/img/product5.jpg',
        '/static/img/product6.jpg'
    ]
    
    # Get all products
    cursor.execute("SELECT id, title, category, image_url FROM products")
    products = cursor.fetchall()
    
    updated_count = 0
    
    for i, product in enumerate(products):
        product_id = product['id']
        current_image = product['image_url']
        
        # If image doesn't start with /static/img/, update it
        # Rotate through the 6 available images
        if not current_image or not current_image.startswith('/static/img/'):
            image_url = LOCAL_IMAGES[i % len(LOCAL_IMAGES)]
            cursor.execute("UPDATE products SET image_url = ? WHERE id = ?", (image_url, product_id))
            updated_count += 1
    
    conn.commit()
    
    # Print summary
    cursor.execute("SELECT COUNT(*) as total FROM products")
    total = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as with_images FROM products WHERE image_url IS NOT NULL AND image_url != ''")
    with_images = cursor.fetchone()['with_images']
    
    print(f"✅ Verified {total} products with local image URLs ({with_images}/{total} have images)")
    
    conn.close()

if __name__ == "__main__":
    # Create database schema and populate with sample data
    initialize_db()
