import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "webstore.db")

# Mapping of categories to example image URLs
CATEGORY_IMAGES = {
    'Sailboats': 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=400',
    'Motorboats': 'https://images.unsplash.com/photo-1567899378494-47b22a2ae96a?w=400',
    'Yachts': 'https://images.unsplash.com/photo-1605281317010-fe5ffe798166?w=400',
    'Kayaks': 'https://images.unsplash.com/photo-1617469767053-d3b523a0d982?w=400',
    'Jet Skis': 'https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=400',
    'Fishing Boats': 'https://images.unsplash.com/photo-1544551763-77ef2d0cfc6c?w=400',
    'Pontoon Boats': 'https://images.unsplash.com/photo-1605281317010-fe5ffe798166?w=400',
    'Canoes': 'https://images.unsplash.com/photo-1618170101020-acccaaba0000?w=400',
    'Dinghies': 'https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=400',
    'Parts': 'https://images.unsplash.com/photo-1621847468516-59f7c82e1d4b?w=400',
    'Accessories': 'https://images.unsplash.com/photo-1580674285054-bed31e145f59?w=400',
    'Safety Equipment': 'https://images.unsplash.com/photo-1621847468516-59f7c82e1d4b?w=400',
    'Navigation': 'https://images.unsplash.com/photo-1543722530-d2c3201371e7?w=400',
    'Electronics': 'https://images.unsplash.com/photo-1517420704952-d9f39e95b43e?w=400',
    'Sails': 'https://images.unsplash.com/photo-1473496169904-658ba7c44d8a?w=400',
    'Anchors': 'https://images.unsplash.com/photo-1621847468516-59f7c82e1d4b?w=400',
    'Ropes & Lines': 'https://images.unsplash.com/photo-1580674285054-bed31e145f59?w=400',
    'Maintenance': 'https://images.unsplash.com/photo-1581092160562-40aa08e78837?w=400',
    'Clothing': 'https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=400',
    'Other': 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=400',
}

# Alternative boat images for variety
BOAT_IMAGES = [
    'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=400',  # sailboat
    'https://images.unsplash.com/photo-1567899378494-47b22a2ae96a?w=400',  # yacht
    'https://images.unsplash.com/photo-1605281317010-fe5ffe798166?w=400',  # luxury yacht
    'https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=400',  # speedboat
    'https://images.unsplash.com/photo-1544551763-77ef2d0cfc6c?w=400',  # fishing boat
    'https://images.unsplash.com/photo-1473496169904-658ba7c44d8a?w=400',  # sailing
    'https://images.unsplash.com/photo-1617469767053-d3b523a0d982?w=400',  # kayak
    'https://images.unsplash.com/photo-1618170101020-acccaaba0000?w=400',  # canoe
]

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
    # Sailboats & Boats (rotating through 6 images)
    (1, "Classic 20ft Sailing Yacht", "Beautiful classic yacht with mahogany trim. Perfect for weekend coastal cruising. Recently serviced, ready to sail.", 15500.00, 1, "Sailboats", "/static/img/product1.jpg"),
    (3, "14ft Racing Dinghy", "Competition-ready racing dinghy. Fast and responsive, ideal for club racing or training.", 3200.00, 2, "Sailboats", "/static/img/product2.jpg"),
    (1, "Luxury 28ft Cruiser", "Spacious cruiser with full cabin amenities. Sleeps 4, galley, head, and navigation station.", 28900.00, 1, "Yachts", "/static/img/product3.jpg"),
    (3, "16ft Catamaran", "Stable and fast catamaran perfect for beach sailing. Easy to trailer and launch.", 5800.00, 1, "Sailboats", "/static/img/product4.jpg"),
    (1, "Vintage Wooden Sloop", "Restored 1960s wooden sloop. Beautiful lines, excellent condition. A real head-turner.", 12000.00, 1, "Sailboats", "/static/img/product5.jpg"),
    (3, "Performance Racing Yacht", "High-performance racing yacht with carbon fiber mast. Competitive and well-maintained.", 35000.00, 1, "Yachts", "/static/img/product6.jpg"),
    
    # Sails & Rigging (cycling through images)
    (1, "Competition Spinnaker 35ft", "Lightweight racing spinnaker in excellent condition. Perfect for downwind sailing.", 850.00, 2, "Sails", "/static/img/product1.jpg"),
    (3, "Cruising Mainsail 30ft", "Dacron cruising mainsail with three reef points. UV protected, like new.", 1450.00, 3, "Sails", "/static/img/product2.jpg"),
    (1, "Storm Jib Heavy Duty", "High-quality storm jib for heavy weather. Essential offshore safety equipment.", 520.00, 4, "Sails", "/static/img/product3.jpg"),
    (3, "Genoa Sail 120%", "Large overlapping genoa for light wind performance. Excellent shape retention.", 1280.00, 2, "Sails", "/static/img/product4.jpg"),
    
    # Safety Equipment (cycling images)
    (1, "Automatic Inflatable Life Jacket", "Auto-inflate PFD with harness. Coast Guard approved. Essential safety gear.", 145.00, 12, "Safety", "/static/img/product5.jpg"),
    (3, "Complete Flare Kit", "Offshore flare kit with hand-held and parachute flares. Current certification.", 185.00, 8, "Safety", "/static/img/product6.jpg"),
    (1, "EPIRB 406 MHz", "Emergency position beacon with GPS. Registered and tested. Can save your life.", 450.00, 5, "Safety", "/static/img/product1.jpg"),
    (3, "Life Raft 4-Person", "Self-inflating life raft for 4 people. Recently serviced and certified.", 2800.00, 2, "Safety", "/static/img/product2.jpg"),
    
    # Navigation & Electronics (cycling images)
    (1, "Marine GPS Chartplotter", "Color GPS chartplotter with coastal charts. Easy to use, waterproof.", 895.00, 6, "Electronics", "/static/img/product3.jpg"),
    (3, "VHF Marine Radio", "Waterproof VHF radio with DSC. Essential communication equipment.", 245.00, 10, "Electronics", "/static/img/product4.jpg"),
    (1, "Depth Sounder", "Digital depth finder with alarm. Easy installation, accurate readings.", 180.00, 8, "Electronics", "/static/img/product5.jpg"),
    (3, "Wind Instrument Set", "Complete wind speed and direction display. Essential for racing.", 560.00, 4, "Electronics", "/static/img/product6.jpg"),
    
    # Anchors & Ground Tackle (cycling images)
    (1, "Plow Anchor 15kg", "High holding power anchor suitable for 30-40ft boats. Galvanized steel.", 185.00, 10, "Anchors", "/static/img/product1.jpg"),
    (3, "Anchor Chain 50ft", "Heavy-duty galvanized chain. 8mm links, perfect for larger boats.", 220.00, 8, "Anchors", "/static/img/product2.jpg"),
    (1, "Danforth Anchor 12kg", "Lightweight folding anchor ideal for cruising boats. Easy to stow.", 125.00, 12, "Anchors", "/static/img/product3.jpg"),
    
    # Accessories & Parts (cycling images)
    (3, "Sailing Gloves Premium", "Kevlar reinforced sailing gloves. Excellent grip and protection.", 65.00, 25, "Accessories", "/static/img/product4.jpg"),
    (1, "Electric Windlass", "Powerful 12V windlass for easy anchor handling. Foot switches included.", 680.00, 3, "Accessories", "/static/img/product5.jpg"),
    (3, "Teak Deck Panels", "Marine-grade teak panels for cockpit flooring. Beautiful and durable.", 240.00, 8, "Accessories", "/static/img/product6.jpg"),
    (1, "Stainless Steel Cleats", "Pair of heavy-duty cleats. Perfect for mooring or docking.", 45.00, 20, "Parts", "/static/img/product1.jpg"),
    (3, "Fender Set Marine", "Set of 4 inflatable fenders with rope. Protect your boat during docking.", 95.00, 15, "Accessories", "/static/img/product2.jpg"),
    
    # Rope & Lines (cycling images)
    (1, "Braided Dock Line 50ft", "Premium dock line with spliced eye. UV resistant and strong.", 68.00, 18, "Ropes & Lines", "/static/img/product3.jpg"),
    (3, "Halyard Rope 100ft", "Low-stretch halyard line. Perfect for raising and lowering sails.", 125.00, 12, "Ropes & Lines", "/static/img/product4.jpg"),
    (1, "Anchor Rode 200ft", "Complete anchor rode with chain and rope. Ready to deploy.", 285.00, 6, "Ropes & Lines", "/static/img/product5.jpg"),
    
    # Clothing & Gear (cycling images)
    (3, "Offshore Foul Weather Jacket", "Heavy-duty waterproof jacket with hood. Breathable and durable.", 195.00, 10, "Clothing", "/static/img/product6.jpg"),
    (1, "Sailing Boots Waterproof", "Non-slip sailing boots. Comfortable for long days on deck.", 85.00, 14, "Clothing", "/static/img/product1.jpg"),
    (3, "Sailing Cap UV Protection", "Wide-brim sailing cap with UV 50+ protection. Adjustable and floatable.", 32.00, 30, "Clothing", "/static/img/product2.jpg")
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
    
    # Update product images
    update_product_images()
    
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
    initialize_db()
