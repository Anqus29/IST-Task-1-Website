"""
Test script to verify the webstore application is working properly
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = "webstore.db"

def test_database_schema():
    """Test that all required tables and columns exist"""
    print("🔍 Testing Database Schema...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check all required tables exist
    required_tables = [
        'users', 'products', 'orders', 'order_items', 'addresses',
        'reviews', 'favorites', 'notifications', 'password_reset_tokens',
        'product_reports', 'product_views', 'bids'
    ]
    
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in c.fetchall()]
    
    for table in required_tables:
        if table in existing_tables:
            print(f"  ✅ Table '{table}' exists")
        else:
            print(f"  ❌ Table '{table}' MISSING")
            return False
    
    # Check products table has auction columns
    c.execute("PRAGMA table_info(products)")
    product_columns = [row[1] for row in c.fetchall()]
    auction_columns = ['is_auction', 'starting_bid', 'current_bid', 'auction_end', 'reserve_price', 'buy_now_price']
    
    for col in auction_columns:
        if col in product_columns:
            print(f"  ✅ Products.{col} exists")
        else:
            print(f"  ❌ Products.{col} MISSING")
            return False
    
    # Check reviews table has approval columns
    c.execute("PRAGMA table_info(reviews)")
    review_columns = [row[1] for row in c.fetchall()]
    
    if 'is_approved' in review_columns and 'approved_at' in review_columns:
        print(f"  ✅ Review approval columns exist")
    else:
        print(f"  ❌ Review approval columns MISSING")
        return False
    
    conn.close()
    print("✅ Database schema is correct!\n")
    return True

def test_sample_data():
    """Test that sample data exists"""
    print("🔍 Testing Sample Data...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check users
    c.execute("SELECT COUNT(*) FROM users")
    user_count = c.fetchone()[0]
    print(f"  Users: {user_count} (expected: 3+)")
    
    # Check products
    c.execute("SELECT COUNT(*) FROM products WHERE is_auction = 0")
    regular_products = c.fetchone()[0]
    print(f"  Regular Products: {regular_products} (expected: 6+)")
    
    # Check auctions
    c.execute("SELECT COUNT(*) FROM products WHERE is_auction = 1")
    auctions = c.fetchone()[0]
    print(f"  Auction Products: {auctions} (expected: 2+)")
    
    # Check in-stock products
    c.execute("SELECT COUNT(*) FROM products WHERE stock > 0")
    in_stock = c.fetchone()[0]
    print(f"  In-Stock Products: {in_stock} (expected: 7+)")
    
    # Check bids
    c.execute("SELECT COUNT(*) FROM bids")
    bids = c.fetchone()[0]
    print(f"  Bids: {bids} (expected: 1+)")
    
    conn.close()
    
    if user_count >= 3 and regular_products >= 6 and auctions >= 2 and in_stock >= 7 and bids >= 1:
        print("✅ Sample data looks good!\n")
        return True
    else:
        print("⚠️ Sample data might be incomplete\n")
        return False

def test_auction_data():
    """Test auction data specifically"""
    print("🔍 Testing Auction Data...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        SELECT id, title, starting_bid, current_bid, auction_end, reserve_price, buy_now_price
        FROM products WHERE is_auction = 1
    """)
    
    auctions = c.fetchall()
    for auction in auctions:
        id, title, start, current, end, reserve, buy_now = auction
        print(f"  Auction #{id}: {title[:40]}")
        print(f"    Starting: ${start:.2f}, Current: ${current:.2f}")
        print(f"    Reserve: ${reserve:.2f}, Buy Now: ${buy_now:.2f}")
        print(f"    Ends: {end}")
        
        # Check if auction end date is in the future
        try:
            end_date = datetime.strptime(end, '%Y-%m-%d %H:%M:%S')
            if end_date > datetime.now():
                print(f"    ✅ Auction is active (ends in future)")
            else:
                print(f"    ⚠️ Auction has ended")
        except:
            print(f"    ⚠️ Invalid end date format")
    
    conn.close()
    print()
    return True

def test_relationships():
    """Test database relationships"""
    print("🔍 Testing Database Relationships...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Test products have sellers
    c.execute("""
        SELECT COUNT(*) FROM products p
        LEFT JOIN users u ON p.seller_id = u.id
        WHERE u.id IS NULL AND p.seller_id IS NOT NULL
    """)
    orphaned_products = c.fetchone()[0]
    
    if orphaned_products == 0:
        print(f"  ✅ All products have valid sellers")
    else:
        print(f"  ❌ {orphaned_products} products have invalid seller_id")
    
    # Test bids have valid products and users
    c.execute("""
        SELECT COUNT(*) FROM bids b
        LEFT JOIN products p ON b.product_id = p.id
        LEFT JOIN users u ON b.user_id = u.id
        WHERE p.id IS NULL OR u.id IS NULL
    """)
    invalid_bids = c.fetchone()[0]
    
    if invalid_bids == 0:
        print(f"  ✅ All bids have valid products and users")
    else:
        print(f"  ❌ {invalid_bids} bids have invalid references")
    
    conn.close()
    print()
    return orphaned_products == 0 and invalid_bids == 0

def test_data_integrity():
    """Test data integrity constraints"""
    print("🔍 Testing Data Integrity...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check for negative prices
    c.execute("SELECT COUNT(*) FROM products WHERE price < 0")
    negative_prices = c.fetchone()[0]
    
    if negative_prices == 0:
        print(f"  ✅ No negative prices")
    else:
        print(f"  ⚠️ {negative_prices} products with negative prices")
    
    # Check for negative stock
    c.execute("SELECT COUNT(*) FROM products WHERE stock < 0")
    negative_stock = c.fetchone()[0]
    
    if negative_stock == 0:
        print(f"  ✅ No negative stock")
    else:
        print(f"  ⚠️ {negative_stock} products with negative stock")
    
    # Check auction bids are >= starting bid
    c.execute("""
        SELECT COUNT(*) FROM bids b
        JOIN products p ON b.product_id = p.id
        WHERE b.bid_amount < p.starting_bid
    """)
    invalid_bids = c.fetchone()[0]
    
    if invalid_bids == 0:
        print(f"  ✅ All bids meet minimum requirements")
    else:
        print(f"  ⚠️ {invalid_bids} bids below starting bid")
    
    conn.close()
    print()
    return negative_prices == 0 and negative_stock == 0 and invalid_bids == 0

def main():
    """Run all tests"""
    print("="*60)
    print("  SECRET BAY WEBSTORE - SYSTEM TEST")
    print("="*60)
    print()
    
    if not os.path.exists(DB_PATH):
        print("❌ Database not found! Run 'python setup_db.py' first.")
        return
    
    results = []
    
    results.append(("Database Schema", test_database_schema()))
    results.append(("Sample Data", test_sample_data()))
    results.append(("Auction Data", test_auction_data()))
    results.append(("Relationships", test_relationships()))
    results.append(("Data Integrity", test_data_integrity()))
    
    print("="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 All tests passed! The system is ready to use.")
    else:
        print("⚠️ Some tests failed. Please review the issues above.")
    print()

if __name__ == "__main__":
    main()
