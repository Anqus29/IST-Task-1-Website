import sqlite3

conn = sqlite3.connect('webstore.db')
cur = conn.cursor()

print("=" * 60)
print("DATABASE VERIFICATION")
print("=" * 60)

print("\n📊 TABLE COUNTS:")
for table in ['users', 'products', 'bids', 'reviews', 'favorites', 'orders']:
    cur.execute(f'SELECT COUNT(*) FROM {table}')
    count = cur.fetchone()[0]
    print(f"   {table:20s}: {count}")

print("\n📁 PRODUCT CATEGORIES:")
cur.execute("SELECT category, COUNT(*) as count FROM products GROUP BY category ORDER BY count DESC")
for row in cur.fetchall():
    print(f"   {row[0]:30s}: {row[1]:2d} items")

print("\n⚓ SAILING PRODUCTS (sample):")
cur.execute("SELECT id, title, category, price FROM products WHERE category IN ('Sailboats', 'Sails', 'Rigging', 'Safety', 'Gear', 'Accessories') LIMIT 10")
for row in cur.fetchall():
    print(f"   #{row[0]:2d} {row[1]:40s} [{row[2]:15s}] ${row[3]:.2f}")

print("\n🔨 AUCTION ITEMS:")
cur.execute("SELECT id, title, category, starting_bid, current_bid, buy_now_price, auction_end FROM products WHERE is_auction=1")
for row in cur.fetchall():
    print(f"   #{row[0]:2d} {row[1]}")
    print(f"       Category: {row[2]}")
    print(f"       Starting: ${row[3]:.2f} | Current: ${row[4]:.2f} | Buy Now: ${row[5]:.2f}")
    print(f"       Ends: {row[6]}")
    print()

print("💰 SAMPLE BIDS:")
cur.execute("""
    SELECT b.id, b.bid_amount, p.title, u.username 
    FROM bids b 
    JOIN products p ON b.product_id = p.id 
    JOIN users u ON b.user_id = u.id
    LIMIT 5
""")
for row in cur.fetchall():
    print(f"   Bid #{row[0]}: ${row[1]:.2f} on '{row[2]}' by {row[3]}")

print("\n👥 USERS:")
cur.execute("SELECT id, username, is_admin, is_seller, business_name FROM users")
for row in cur.fetchall():
    role = []
    if row[2]: role.append("ADMIN")
    if row[3]: role.append("SELLER")
    if not role: role.append("BUYER")
    business = f" ({row[4]})" if row[4] else ""
    print(f"   User #{row[0]}: {row[1]:15s} [{', '.join(role)}]{business}")

print("\n" + "=" * 60)
print("✅ Database verification complete!")
print("=" * 60)

conn.close()
