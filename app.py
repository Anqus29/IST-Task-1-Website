from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from functools import wraps
import sqlite3
import os
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta


app = Flask(__name__)
app.secret_key = "change_this_to_a_random_secret"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Auto-logout after 30 min

DB_PATH = os.path.join(os.path.dirname(__file__), "webstore.db")

def get_db_connection(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def is_strong_password(pw: str) -> bool:
    """Basic strong password policy: at least 8 chars, with lower, upper, digit, and special."""
    if not pw or len(pw) < 8:
        return False
    has_lower = any(c.islower() for c in pw)
    has_upper = any(c.isupper() for c in pw)
    has_digit = any(c.isdigit() for c in pw)
    has_special = any(not c.isalnum() for c in pw)
    return has_lower and has_upper and has_digit and has_special

def ensure_reviews_table():
    """Create reviews table if it does not exist (safe to call at startup)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            title TEXT,
            body TEXT,
            seller_response TEXT,
            is_approved INTEGER NOT NULL DEFAULT 0,
            approved_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(product_id, user_id)
        )
        """
    )
    conn.commit()
    conn.close()

def ensure_additional_tables():
    """Create additional feature tables if they don't exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Favorites/wishlist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
            UNIQUE(user_id, product_id)
        )
    """)
    
    # Notifications
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            link TEXT,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # Password reset tokens
    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # Product reports
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            reporter_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY(reporter_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    # Recently viewed
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER NOT NULL,
            viewed_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    """)
    
    # Add new columns to existing tables if they don't exist
    try:
        cur.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0")
    except:
        pass
    try:
        cur.execute("ALTER TABLE users ADD COLUMN profile_picture TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE products ADD COLUMN condition TEXT DEFAULT 'used'")
    except:
        pass
    try:
        cur.execute("ALTER TABLE products ADD COLUMN location TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE products ADD COLUMN view_count INTEGER DEFAULT 0")
    except:
        pass
    try:
        cur.execute("ALTER TABLE orders ADD COLUMN refund_status TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN seller_response TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 0")
    except:
        pass
    try:
        cur.execute("ALTER TABLE reviews ADD COLUMN approved_at TEXT")
    except:
        pass
    
    conn.commit()
    conn.close()

# Ensure DB has reviews table
ensure_reviews_table()
ensure_additional_tables()

def ensure_cart():
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']

def cart_total_items_and_amount(cart):
    total_items = 0
    total_amount = Decimal("0.00")
    if not cart:
        return total_items, total_amount
    conn = get_db_connection()
    cur = conn.cursor()
    ids = list(cart.keys())
    placeholders = ",".join("?" for _ in ids)
    cur.execute(f"SELECT id, price FROM products WHERE id IN ({placeholders})", ids)
    rows = {str(r["id"]): Decimal(str(r["price"])) for r in cur.fetchall()}
    conn.close()
    for pid, qty in cart.items():
        total_items += qty
        price = rows.get(str(pid), Decimal("0.00"))
        total_amount += price * qty
    return total_items, total_amount

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_user_permissions():
    """Inject helpers into templates: current_user_is_admin and current_user_is_seller
    """
    uid = session.get('user_id')
    is_admin_flag = False
    is_seller_flag = False
    if uid:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, is_admin, is_seller FROM users WHERE id = ?", (uid,))
        u = cur.fetchone()
        conn.close()
        if u:
            allowed_admin_username = 'Bean'
            if (u['username'] and u['username'].strip().lower() == allowed_admin_username.strip().lower()) or u['is_admin']:
                is_admin_flag = True
            if u['is_seller']:
                is_seller_flag = True
    return {'current_user_is_admin': is_admin_flag, 'current_user_is_seller': is_seller_flag}


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # restrict admin area to a single user account (by username)
        uid = session.get('user_id')
        if not uid:
            return redirect(url_for('login', next=request.path))
        conn = get_db_connection()
        cur = conn.cursor()
        # fetch both username and is_admin flag so toggling is_admin grants access
        cur.execute("SELECT username, is_admin FROM users WHERE id = ?", (uid,))
        u = cur.fetchone()
        conn.close()
        # allow either the special username or any user with is_admin truthy
        allowed_admin_username = 'Bean'
        has_name_match = bool(u and u['username'] and u['username'].strip().lower() == allowed_admin_username.strip().lower())
        has_admin_flag = bool(u and u['is_admin'])
        if not (has_name_match or has_admin_flag):
            flash("Admin access required.")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.description, p.price, p.stock, p.created_at, p.seller_id, p.image_url, u.business_name, u.rating, u.username AS seller_username
        FROM products p 
        LEFT JOIN users u ON p.seller_id = u.id 
        ORDER BY p.created_at DESC LIMIT 12
    """)
    featured = cur.fetchall()
    
    # Fetch stats
    cur.execute("""
        SELECT 
            (SELECT COUNT(*) FROM products WHERE stock > 0) as active_listings,
            (SELECT COUNT(DISTINCT seller_id) FROM products) as total_sellers,
            (SELECT COUNT(*) FROM users) as total_users
    """)
    stats = cur.fetchone()
    
    # Fetch recently viewed products
    recently_viewed = []
    user_id = session.get('user_id')
    if user_id:
        cur.execute("""
            SELECT DISTINCT p.id, p.title, p.price, p.image_url, p.stock
            FROM product_views pv
            JOIN products p ON pv.product_id = p.id
            WHERE pv.user_id = ?
            ORDER BY pv.viewed_at DESC
            LIMIT 8
        """, (user_id,))
        recently_viewed = cur.fetchall()
    
    conn.close()
    return render_template('index.html', featured_products=featured, recently_viewed=recently_viewed, stats=stats)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # In a real app, you would send an email or save to database
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        flash('Thank you for contacting us! We will respond to your message soon.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/help')
def help():
    return render_template('help.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/products')
def products():
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'newest')
    category = request.args.get('category', '')
    condition = request.args.get('condition', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    page = int(request.args.get('page', 1))
    per_page = 20
    
    conn = get_db_connection()
    cur = conn.cursor()
    base = """
     SELECT p.id, p.title, p.description, p.price, p.created_at, 
         p.stock, p.image_url, p.category, p.condition, u.business_name, u.rating, p.seller_id, u.is_verified
        FROM products p 
        LEFT JOIN users u ON p.seller_id = u.id
    """
    params = []
    conditions = []
    if search:
        conditions.append("(p.title LIKE ? OR p.description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if category:
        conditions.append("p.category = ?")
        params.append(category)
    if condition:
        conditions.append("p.condition = ?")
        params.append(condition)
    if min_price:
        try:
            conditions.append("p.price >= ?")
            params.append(float(min_price))
        except:
            pass
    if max_price:
        try:
            conditions.append("p.price <= ?")
            params.append(float(max_price))
        except:
            pass
    
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    
    if sort == 'price_low':
        order = " ORDER BY p.price ASC"
    elif sort == 'price_high':
        order = " ORDER BY p.price DESC"
    elif sort == 'popular':
        order = " ORDER BY p.view_count DESC, p.created_at DESC"
    else:
        order = " ORDER BY p.created_at DESC"
    
    # Get total count for pagination
    cur.execute(f"SELECT COUNT(*) as total FROM products p {where}", params)
    total = cur.fetchone()['total']
    total_pages = (total + per_page - 1) // per_page
    
    # Get paginated results
    offset = (page - 1) * per_page
    cur.execute(base + where + order + " LIMIT ? OFFSET ?", params + [per_page, offset])
    products_list = cur.fetchall()
    
    # Get distinct categories and conditions for filters
    cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category")
    categories = [row['category'] for row in cur.fetchall()]
    
    conditions_list = ['new', 'used', 'refurbished']
    
    conn.close()
    return render_template('products.html', 
                         products=products_list, 
                         search=search, 
                         sort=sort, 
                         category=category, 
                         categories=categories,
                         condition=condition,
                         conditions=conditions_list,
                         min_price=min_price,
                         max_price=max_price,
                         page=page,
                         total_pages=total_pages,
                         total=total)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    # Track product view
    track_product_view(product_id)
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.description, p.price, p.stock, p.image_url, p.category,
               u.id AS seller_id, u.business_name, u.seller_description, u.rating, u.is_verified
        FROM products p
        LEFT JOIN users u ON p.seller_id = u.id
        WHERE p.id = ?
    """, (product_id,))
    product = cur.fetchone()
    if product is None:
        conn.close()
        flash("Product not found.")
        return redirect(url_for('products'))

    # Fetch reviews with seller responses
    cur.execute(
        """
        SELECT r.id, r.rating, r.title, r.body, r.seller_response, r.created_at, u.username
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.product_id = ? AND r.is_approved = 1
        ORDER BY r.created_at DESC
        """,
        (product_id,)
    )
    reviews = cur.fetchall()

    cur.execute("SELECT COUNT(*) AS c, AVG(rating) AS avg_rating FROM reviews WHERE product_id = ? AND is_approved = 1", (product_id,))
    stats = cur.fetchone()
    
    # Related products (same category)
    cur.execute("""
        SELECT id, title, price, image_url, stock
        FROM products
        WHERE category = ? AND id != ? AND stock > 0
        ORDER BY RANDOM()
        LIMIT 4
    """, (product['category'], product_id))
    related_products = cur.fetchall()
    
    # Check if user favorited this
    is_favorited = False
    uid = session.get('user_id')
    if uid:
        cur.execute("SELECT 1 FROM favorites WHERE user_id = ? AND product_id = ?", (uid, product_id))
        is_favorited = cur.fetchone() is not None
    
    # Determine if current user purchased this product (to allow reviewing)
    can_review = False
    if uid:
        cur.execute(
            """
            SELECT 1
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            WHERE o.buyer_id = ? AND oi.product_id = ?
            LIMIT 1
            """,
            (uid, product_id)
        )
        can_review = cur.fetchone() is not None
    conn.close()
    review_count = stats["c"] if stats else 0
    avg_rating = float(stats["avg_rating"]) if stats and stats["avg_rating"] is not None else None

    return render_template('product_detail.html', product=product, reviews=reviews, review_count=review_count, avg_rating=avg_rating, can_review=can_review, related_products=related_products, is_favorited=is_favorited)

@app.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def submit_review(product_id):
    rating_raw = request.form.get('rating')
    title = (request.form.get('title') or '').strip()
    body = (request.form.get('body') or '').strip()
    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError()
    except Exception:
        flash('Please provide a valid rating between 1 and 5.')
        return redirect(url_for('product_detail', product_id=product_id))

    if not body:
        flash('Please add a short review comment.')
        return redirect(url_for('product_detail', product_id=product_id))

    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    # Ensure product exists
    cur.execute("SELECT id FROM products WHERE id = ?", (product_id,))
    if not cur.fetchone():
        conn.close()
        flash('Product not found.')
        return redirect(url_for('products'))

    # Ensure the user has purchased this product
    cur.execute(
        """
        SELECT 1
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        WHERE o.buyer_id = ? AND oi.product_id = ?
        LIMIT 1
        """,
        (user_id, product_id)
    )
    if cur.fetchone() is None:
        conn.close()
        flash('Only customers who purchased this item can leave a review.')
        return redirect(url_for('product_detail', product_id=product_id))

    # Insert or update the user's review for this product
    cur.execute(
        """
        INSERT INTO reviews (product_id, user_id, rating, title, body)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(product_id, user_id) DO UPDATE SET
            rating=excluded.rating,
            title=excluded.title,
            body=excluded.body,
            created_at=datetime('now')
        """,
        (product_id, user_id, rating, title or None, body)
    )
    conn.commit()
    conn.close()
    flash('Thanks for your review!')
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/cart')
def cart_view():
    cart = ensure_cart()
    items = []
    if cart:
        conn = get_db_connection()
        cur = conn.cursor()
        for pid, qty in cart.items():
            cur.execute("SELECT id, title, price FROM products WHERE id = ?", (pid,))
            product = cur.fetchone()
            if product:
                items.append({
                    'product': product,
                    'quantity': qty,
                    'line_total': float(product['price']) * qty
                })
        conn.close()
    total_items, total_amount = cart_total_items_and_amount(cart)
    
    # Fetch recently viewed products
    recently_viewed = []
    user_id = session.get('user_id')
    if user_id:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT p.id, p.title, p.price, p.image_url, p.stock
            FROM product_views pv
            JOIN products p ON pv.product_id = p.id
            WHERE pv.user_id = ?
            ORDER BY pv.viewed_at DESC
            LIMIT 8
        """, (user_id,))
        recently_viewed = cur.fetchall()
        conn.close()
    
    return render_template('cart.html', items=items, total_items=total_items, total_amount=total_amount, recently_viewed=recently_viewed)

@app.route('/cart/add', methods=['POST'])
def cart_add():
    product_id = request.form.get('product_id')
    qty = int(request.form.get('quantity', 1))
    # ensure product exists and respect stock limits
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, stock FROM products WHERE id = ?", (product_id,))
        prod = cur.fetchone()
    finally:
        conn.close()

    if not prod:
        flash("Product not found.")
        return redirect(request.form.get('next') or url_for('products'))

    # stock == None/NULL means unlimited
    stock = prod['stock']
    cart = ensure_cart()
    cart = dict(cart)
    current = cart.get(product_id, 0)
    add_requested = max(1, qty)
    if stock is not None:
        available = stock - current
        if available <= 0:
            wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
            if wants_json:
                return jsonify({"ok": False, "error": "Out of stock", "total_items": sum(cart.values())})
            flash("Item is out of stock.")
            return redirect(request.form.get('next') or url_for('cart_view'))
        add_amount = min(add_requested, available)
    else:
        add_amount = add_requested

    cart[product_id] = current + add_amount
    session['cart'] = cart
    total_items, total_amount = cart_total_items_and_amount(cart)
    wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
    if wants_json:
        # include how many were actually added and a helpful message
        msg = None
        if add_amount < add_requested:
            msg = f"Only {add_amount} items were added due to limited stock."
        else:
            msg = "Added to cart."
        return jsonify({
            "ok": True,
            "total_items": total_items,
            "total_amount": float(total_amount),
            "added": add_amount,
            "requested": add_requested,
            "message": msg
        })
    # notify if we could not add full requested amount
    if add_amount < add_requested:
        flash(f"Only {add_amount} items were added due to limited stock.")
    else:
        flash("Added to cart.")
    return redirect(request.form.get('next') or url_for('cart_view'))

@app.route('/cart/summary')
def cart_summary():
    cart = ensure_cart()
    total_items, total_amount = cart_total_items_and_amount(cart)
    return jsonify({"total_items": total_items, "total_amount": float(total_amount)})

@app.route('/cart/update', methods=['POST'])
def cart_update():
    cart = ensure_cart()
    cart = dict(cart)
    # For each qty_<id> field, ensure quantity does not exceed stock
    conn = get_db_connection()
    cur = conn.cursor()
    for pid, qty in request.form.items():
        if not pid.startswith("qty_"):
            continue
        prod_id = pid[4:]
        try:
            q = int(qty)
        except ValueError:
            q = 0
        if q <= 0:
            cart.pop(prod_id, None)
            continue

        # check stock for this product
        cur.execute("SELECT stock FROM products WHERE id = ?", (prod_id,))
        r = cur.fetchone()
        if r and r['stock'] is not None:
            stock = r['stock']
            if q > stock:
                q = stock
                flash(f"Quantity for product {prod_id} reduced to available stock ({stock}).")

        cart[prod_id] = q
    conn.close()
    session['cart'] = cart
    flash("Cart updated.")
    return redirect(url_for('cart_view'))

@app.route('/cart/remove/<int:product_id>', methods=['POST'])
def cart_remove(product_id):
    cart = ensure_cart()
    cart = dict(cart)
    cart.pop(str(product_id), None)
    session['cart'] = cart
    flash("Removed item.")
    return redirect(url_for('cart_view'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        email = request.form.get('email','').strip()
        password = request.form.get('password','')
        if not username or not email or not password:
            flash("Fill all fields.")
            return redirect(url_for('register'))
        # Enforce strong password policy
        if not is_strong_password(password):
            flash("Password is too weak. Use at least 8 characters including uppercase, lowercase, a number, and a symbol.", "danger")
            return redirect(url_for('register'))
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cur.fetchone():
            conn.close()
            flash("Username or email already taken.")
            return redirect(url_for('register'))
        pw_hash = generate_password_hash(password)
        cur.execute("INSERT INTO users (username, email, password_hash, is_seller) VALUES (?, ?, ?, 0)",
                    (username, email, pw_hash))
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        session['user_id'] = user_id
        session['username'] = username
        session.permanent = True
        flash("Registered and logged in.")
        next_url = request.args.get('next') or url_for('index')
        return redirect(next_url)
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password_hash FROM users WHERE username = ? OR email = ?", (username, username))
        user = cur.fetchone()
        conn.close()
        if not user or not check_password_hash(user['password_hash'], password):
            flash("Invalid credentials.")
            return redirect(url_for('login', next=request.args.get('next')))
        session['user_id'] = user['id']
        session['username'] = user['username']
        session.permanent = True
        flash("Logged in.")
        return redirect(request.args.get('next') or url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash("Logged out.")
    return redirect(url_for('index'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart = ensure_cart()
    if not cart:
        flash("Your cart is empty.")
        return redirect(url_for('products'))

    conn = get_db_connection()
    cur = conn.cursor()

    # build items list for display and compute total (include stock for checks)
    ids = list(cart.keys())
    placeholders = ",".join("?" for _ in ids)
    cur.execute(f"SELECT id, title, price, stock, seller_id FROM products WHERE id IN ({placeholders})", ids)
    rows = {str(r["id"]): r for r in cur.fetchall()}
    items = []
    total = 0.0
    for pid, qty in cart.items():
        r = rows.get(str(pid))
        if not r:
            continue
        line_total = float(r["price"]) * qty
        items.append({"product": r, "quantity": qty, "line_total": line_total})
        total += line_total

    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip()
        address = request.form.get('address','').strip()
        if not name or not email or not address:
            flash("Please fill all fields.")
            return redirect(url_for('checkout'))

        # re-validate stock for all items before creating order
        insufficient = []
        for pid, qty in cart.items():
            prod = rows.get(str(pid))
            if not prod:
                insufficient.append((pid, 0, qty))
                continue
            stock = prod['stock']
            if stock is not None and stock < qty:
                insufficient.append((pid, stock, qty))
        if insufficient:
            # inform user and redirect back to cart so they can adjust
            msgs = []
            for pid, avail, wanted in insufficient:
                if avail == 0:
                    msgs.append(f"Product {pid} is no longer available.")
                else:
                    msgs.append(f"Product {pid} only has {avail} left (you wanted {wanted}).")
            for m in msgs:
                flash(m)
            conn.close()
            return redirect(url_for('cart_view'))

        # create order
        buyer_id = session.get('user_id')
        cur.execute(
            "INSERT INTO orders (buyer_id, buyer_name, buyer_email, shipping_address, total) VALUES (?, ?, ?, ?, ?)",
            (buyer_id, name, email, address, total)
        )
        order_id = cur.lastrowid

        # save address for user (avoid duplicates due to UNIQUE constraint)
        try:
            if buyer_id:
                cur.execute("INSERT OR IGNORE INTO addresses (user_id, label, address_text) VALUES (?, ?, ?)",
                            (buyer_id, None, address))
        except Exception:
            pass

        # insert order items and reduce stock
        for pid, qty in cart.items():
            prod = rows.get(str(pid))
            if not prod:
                continue
            unit_price = float(prod['price'])
            cur.execute("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                        (order_id, int(pid), qty, unit_price))
            # decrement stock if not NULL
            cur.execute("UPDATE products SET stock = stock - ? WHERE id = ? AND stock IS NOT NULL", (qty, int(pid)))
            # increment seller's total_sales if seller_id present
            seller_id = prod.get('seller_id') if isinstance(prod, dict) else prod['seller_id']
            if seller_id:
                cur.execute("UPDATE users SET total_sales = COALESCE(total_sales, 0) + ? WHERE id = ?", (qty, seller_id))
        conn.commit()
        conn.close()
        session.pop('cart', None)

        # redirect to order confirmation page (new)
        flash("Order placed successfully!")
        return redirect(url_for('order_confirmation', order_id=order_id))

    # GET: prefill name/email if available
    cur.execute("SELECT username, email FROM users WHERE id = ?", (session.get('user_id'),))
    u = cur.fetchone()
    conn.close()
    pre_name = u['username'] if u else ''
    pre_email = u['email'] if u else ''
    return render_template('checkout.html', items=items, total_amount=total, pre_name=pre_name, pre_email=pre_email)

# new route: order confirmation
@app.route('/order/<int:order_id>')
def order_confirmation(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()
    if not order:
        conn.close()
        flash("Order not found.")
        return redirect(url_for('index'))

    cur.execute("""
        SELECT oi.quantity, oi.unit_price, p.title
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    """, (order_id,))
    items = cur.fetchall()
    conn.close()
    return render_template('order_confirmation.html', order=order, items=items)

@app.route('/addresses')
def address_suggestions():
    """Return saved addresses for the logged-in user that match ?query=..."""
    if 'user_id' not in session:
        return jsonify([])

    q = request.args.get('query', '').strip()
    conn = get_db_connection()
    cur = conn.cursor()
    if q:
        like = f"%{q}%"
        cur.execute("SELECT id, label, address_text FROM addresses WHERE user_id = ? AND address_text LIKE ? ORDER BY created_at DESC LIMIT 8",
                    (session['user_id'], like))
    else:
        cur.execute("SELECT id, label, address_text FROM addresses WHERE user_id = ? ORDER BY created_at DESC LIMIT 8",
                    (session['user_id'],))
    rows = cur.fetchall()
    conn.close()
    return jsonify([{"id": r["id"], "label": r["label"], "address": r["address_text"]} for r in rows])

@app.route('/seller/<int:seller_id>')
def seller_profile(seller_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, business_name, seller_description, rating, total_sales FROM users WHERE id = ?",
        (seller_id,)
    )
    seller = cur.fetchone()

    products = []
    if seller:
        cur.execute(
            "SELECT id, title, description, price, created_at FROM products WHERE seller_id = ? ORDER BY created_at DESC",
            (seller_id,)
        )
        products = cur.fetchall()

    conn.close()
    return render_template('seller_profile.html', seller=seller, products=products)

# Serve favicon automatically from available assets
@app.route('/favicon.ico')
def favicon():
    """Serve a favicon even if favicon.ico isn't present.
    Priority:
      1) static/img/logo.png (PNG)
      2) static/favicon.png (PNG)
      3) static/favicon.ico (ICO)
    """
    # Paths
    logo_png = os.path.join(app.root_path, 'static', 'img', 'logo.png')
    png_path = os.path.join(app.root_path, 'static', 'favicon.png')
    ico_path = os.path.join(app.root_path, 'static', 'favicon.ico')

    if os.path.exists(logo_png):
        return send_file(logo_png, mimetype='image/png')
    if os.path.exists(png_path):
        return send_file(png_path, mimetype='image/png')
    if os.path.exists(ico_path):
        return send_file(ico_path, mimetype='image/x-icon')
    # If nothing exists, return 204 No Content to avoid 404 noise
    return ('', 204)

@app.route('/post-ad', methods=['GET', 'POST'])
@login_required
def post_ad():
    # Check if user is a seller
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_seller FROM users WHERE id = ?", (session.get('user_id'),))
    user = cur.fetchone()
    
    if not user or not user['is_seller']:
        conn.close()
        flash("You must be a seller to post ads. Please contact support to become a seller.", "warning")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '0').strip()
        stock = request.form.get('stock', '0').strip()
        category = request.form.get('category', 'Other').strip()
        image_url = request.form.get('image_url', '').strip() or None
        
        # Handle image URL formatting
        if image_url and not (image_url.startswith('http://') or image_url.startswith('https://') or image_url.startswith('/')):
            # Treat bare filenames as files placed under /static/img/
            image_url = f"/static/img/{image_url}"
        
        # Validation
        if not title:
            flash("Title is required.", "danger")
            conn.close()
            return redirect(url_for('post_ad'))
        
        try:
            price_val = float(price)
            stock_val = int(stock)
            if price_val < 0 or stock_val < 0:
                raise ValueError("Price and stock must be non-negative")
        except ValueError as e:
            flash(f"Invalid price or stock: {e}", "danger")
            conn.close()
            return redirect(url_for('post_ad'))
        
        # Insert the product
        seller_id = session.get('user_id')
        cur.execute(
            "INSERT INTO products (seller_id, title, description, price, stock, image_url, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (seller_id, title, description, price_val, stock_val, image_url, category)
        )
        conn.commit()
        product_id = cur.lastrowid
        conn.close()
        
        flash("Your ad has been posted successfully!", "success")
        return redirect(url_for('product_detail', product_id=product_id))
    
    conn.close()
    return render_template('post_ad.html')

@app.route('/my-listings')
@login_required
def my_listings():
    # Show products posted by the current user (if they're a seller)
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT is_seller FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    
    if not user or not user['is_seller']:
        conn.close()
        flash("You must be a seller to view listings.", "warning")
        return redirect(url_for('index'))
    
    cur.execute("""
        SELECT id, title, description, price, stock, category, image_url, created_at 
        FROM products 
        WHERE seller_id = ? 
        ORDER BY created_at DESC
    """, (user_id,))
    products = cur.fetchall()
    conn.close()
    
    return render_template('my_listings.html', products=products)

@app.route('/settings')
@login_required
def settings():
    """User settings page - redirects to edit profile for now"""
    return redirect(url_for('edit_profile'))

# Admin dashboard
@app.route('/admin')
@admin_required
def admin_index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
          (SELECT COUNT(*) FROM products) AS products_count,
          (SELECT COUNT(*) FROM users) AS users_count,
          (SELECT COUNT(*) FROM orders) AS orders_count,
          (SELECT COUNT(*) FROM reviews WHERE is_approved = 0) AS pending_reviews,
          (SELECT COUNT(*) FROM reviews WHERE is_approved = 1) AS approved_reviews,
          (SELECT COUNT(*) FROM reviews) AS total_reviews
    """)
    stats = cur.fetchone()
    conn.close()
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/reviews')
@admin_required
def admin_reviews():
    filter_status = request.args.get('status', 'pending')  # pending, approved, all
    conn = get_db_connection()
    cur = conn.cursor()
    
    if filter_status == 'pending':
        query = """
            SELECT r.id, r.rating, r.title, r.body, r.created_at,
                   u.username as reviewer_name,
                   p.id as product_id, p.name as product_name
            FROM reviews r
            JOIN users u ON r.user_id = u.id
            JOIN products p ON r.product_id = p.id
            WHERE r.is_approved = 0
            ORDER BY r.created_at DESC
        """
    elif filter_status == 'approved':
        query = """
            SELECT r.id, r.rating, r.title, r.body, r.created_at, r.approved_at,
                   u.username as reviewer_name,
                   p.id as product_id, p.name as product_name
            FROM reviews r
            JOIN users u ON r.user_id = u.id
            JOIN products p ON r.product_id = p.id
            WHERE r.is_approved = 1
            ORDER BY r.approved_at DESC
        """
    else:  # all
        query = """
            SELECT r.id, r.rating, r.title, r.body, r.created_at, r.approved_at, r.is_approved,
                   u.username as reviewer_name,
                   p.id as product_id, p.name as product_name
            FROM reviews r
            JOIN users u ON r.user_id = u.id
            JOIN products p ON r.product_id = p.id
            ORDER BY r.created_at DESC
        """
    
    cur.execute(query)
    reviews = cur.fetchall()
    conn.close()
    return render_template('admin/reviews.html', reviews=reviews, filter_status=filter_status)

@app.route('/admin/reviews/<int:review_id>/approve', methods=['POST'])
@admin_required
def admin_review_approve(review_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE reviews SET is_approved = 1, approved_at = datetime('now') WHERE id = ?", (review_id,))
    conn.commit()
    conn.close()
    flash('Review approved successfully.')
    return redirect(url_for('admin_reviews'))

@app.route('/admin/reviews/<int:review_id>/reject', methods=['POST'])
@admin_required
def admin_review_reject(review_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    conn.commit()
    conn.close()
    flash('Review rejected and deleted.')
    return redirect(url_for('admin_reviews'))


@app.route('/admin/orders')
@admin_required
def admin_orders():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, buyer_id, buyer_name, total, created_at FROM orders ORDER BY created_at DESC")
    orders = cur.fetchall()
    conn.close()
    return render_template('admin/orders.html', orders=orders)


@app.route('/admin/orders/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()
    if not order:
        conn.close()
        flash("Order not found.")
        return redirect(url_for('admin_orders'))

    cur.execute("SELECT oi.quantity, oi.unit_price, p.title FROM order_items oi JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?", (order_id,))
    items = cur.fetchall()
    conn.close()
    return render_template('admin/order_detail.html', order=order, items=items)

# Product management
@app.route('/admin/products')
@admin_required
def admin_products():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT p.id, p.title, p.price, p.stock, u.username AS seller FROM products p LEFT JOIN users u ON p.seller_id = u.id ORDER BY p.created_at DESC")
    products = cur.fetchall()
    conn.close()
    return render_template('admin/products.html', products=products)

@app.route('/admin/products/new', methods=['GET', 'POST'])
@admin_required
def admin_product_new():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        description = request.form.get('description','').strip()
        price = request.form.get('price','0').strip()
        stock = request.form.get('stock','0').strip()
        seller_id = request.form.get('seller_id') or None
        category = request.form.get('category','Other').strip()
        # optional image filename/URL provided by admin
        image_url = request.form.get('image_url','').strip() or None
        if image_url and not (image_url.startswith('http://') or image_url.startswith('https://') or image_url.startswith('/')):
            # treat bare filenames as files placed under /static/img/
            image_url = f"/static/img/{image_url}"
        try:
            price_val = float(price)
            stock_val = int(stock)
        except ValueError:
            flash("Invalid price or stock.")
            return redirect(url_for('admin_product_new'))
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO products (seller_id, title, description, price, stock, image_url, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (seller_id, title, description, price_val, stock_val, image_url, category))
        conn.commit()
        conn.close()
        flash("Product created.")
        return redirect(url_for('admin_products'))
    # GET
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users ORDER BY username")
    sellers = cur.fetchall()
    conn.close()
    return render_template('admin/product_form.html', sellers=sellers, product=None)

@app.route('/admin/products/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_product_edit(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cur.fetchone()
    if not product:
        conn.close()
        flash("Product not found.")
        return redirect(url_for('admin_products'))
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        description = request.form.get('description','').strip()
        price = request.form.get('price','0').strip()
        stock = request.form.get('stock','0').strip()
        seller_id = request.form.get('seller_id') or None
        category = request.form.get('category','Other').strip()
        try:
            price_val = float(price)
            stock_val = int(stock)
        except ValueError:
            flash("Invalid price or stock.")
            return redirect(url_for('admin_product_edit', product_id=product_id))
        # optional image filename/URL provided by admin
        image_url = request.form.get('image_url','').strip() or None
        if image_url and not (image_url.startswith('http://') or image_url.startswith('https://') or image_url.startswith('/')):
            image_url = f"/static/img/{image_url}"

        if image_url is not None:
            cur.execute("UPDATE products SET seller_id = ?, title = ?, description = ?, price = ?, stock = ?, image_url = ?, category = ? WHERE id = ?",
                (seller_id, title, description, price_val, stock_val, image_url, category, product_id))
        else:
            cur.execute("UPDATE products SET seller_id = ?, title = ?, description = ?, price = ?, stock = ?, category = ? WHERE id = ?",
                (seller_id, title, description, price_val, stock_val, category, product_id))
        conn.commit()
        conn.close()
        flash("Product updated.")
        return redirect(url_for('admin_products'))
    # GET form
    cur.execute("SELECT id, username FROM users ORDER BY username")
    sellers = cur.fetchall()
    conn.close()
    return render_template('admin/product_form.html', product=product, sellers=sellers)

@app.route('/admin/products/<int:product_id>/delete', methods=['POST'])
@admin_required
def admin_product_delete(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    flash("Product deleted.")
    return redirect(url_for('admin_products'))

# User management
@app.route('/admin/users')
@admin_required
def admin_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, is_admin, is_seller, created_at FROM users ORDER BY created_at DESC")
    users = cur.fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/<int:user_id>/toggle_admin', methods=['POST'])
@admin_required
def admin_user_toggle_admin(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    u = cur.fetchone()
    if not u:
        conn.close()
        flash("User not found.")
        return redirect(url_for('admin_users'))
    new = 0 if u['is_admin'] else 1
    cur.execute("UPDATE users SET is_admin = ? WHERE id = ?", (new, user_id))
    conn.commit()
    conn.close()
    flash("User admin status updated.")
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/toggle_seller', methods=['POST'])
@admin_required
def admin_user_toggle_seller(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_seller FROM users WHERE id = ?", (user_id,))
    u = cur.fetchone()
    if not u:
        conn.close()
        flash("User not found.")
        return redirect(url_for('admin_users'))
    new = 0 if u['is_seller'] else 1
    cur.execute("UPDATE users SET is_seller = ? WHERE id = ?", (new, user_id))
    conn.commit()
    conn.close()
    flash("User seller status updated.")
    # if we just promoted them to seller, send admin to the seller details form to fill info
    if new == 1:
        return redirect(url_for('admin_edit_seller', user_id=user_id))
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/seller', methods=['GET', 'POST'])
@admin_required
def admin_edit_seller(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, business_name, seller_description, rating, total_sales, is_seller FROM users WHERE id = ?", (user_id,))
    u = cur.fetchone()
    if not u:
        conn.close()
        flash("User not found.")
        return redirect(url_for('admin_users'))

    if request.method == 'POST':
        business_name = request.form.get('business_name','').strip() or None
        seller_description = request.form.get('seller_description','').strip() or None
        try:
            rating = float(request.form.get('rating','0') or 0)
        except ValueError:
            rating = 0.0
        try:
            total_sales = int(request.form.get('total_sales','0') or 0)
        except ValueError:
            total_sales = 0

        # ensure user is marked as seller
        cur.execute("UPDATE users SET business_name = ?, seller_description = ?, rating = ?, total_sales = ?, is_seller = 1 WHERE id = ?",
                    (business_name, seller_description, rating, total_sales, user_id))
        conn.commit()
        conn.close()
        flash("Seller details updated.")
        return redirect(url_for('admin_users'))

    conn.close()
    return render_template('admin/seller_form.html', user=u)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_user_delete(user_id):
    # protect deleting self
    if session.get('user_id') == user_id:
        flash("Cannot delete your own account.")
        return redirect(url_for('admin_users'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted.")
    return redirect(url_for('admin_users'))

# ===== NEW FEATURES =====

# Wishlist/Favorites
@app.route('/favorites')
@login_required
def favorites():
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.description, p.price, p.stock, p.image_url, p.category,
               u.business_name, u.rating, p.seller_id
        FROM favorites f
        JOIN products p ON f.product_id = p.id
        LEFT JOIN users u ON p.seller_id = u.id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC
    """, (user_id,))
    products = cur.fetchall()
    conn.close()
    return render_template('favorites.html', products=products)

@app.route('/favorites/add/<int:product_id>', methods=['POST'])
@login_required
def add_favorite(product_id):
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO favorites (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
        conn.commit()
        flash("Added to favorites!", "success")
    except:
        flash("Already in favorites.", "info")
    conn.close()
    return redirect(request.referrer or url_for('products'))

@app.route('/favorites/remove/<int:product_id>', methods=['POST'])
@login_required
def remove_favorite(product_id):
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM favorites WHERE user_id = ? AND product_id = ?", (user_id, product_id))
    conn.commit()
    conn.close()
    flash("Removed from favorites.")
    return redirect(request.referrer or url_for('favorites'))

# Password Reset
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash("Please enter your email.", "danger")
            return redirect(url_for('forgot_password'))
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        
        if user:
            import secrets
            from datetime import datetime, timedelta
            token = secrets.token_urlsafe(32)
            expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
            cur.execute("INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
                       (user['id'], token, expires))
            conn.commit()
            # In production, send email with reset link
            reset_link = url_for('reset_password', token=token, _external=True)
            flash(f"Password reset link (in production this would be emailed): {reset_link}", "info")
        else:
            flash("If that email exists, a reset link has been sent.", "info")
        
        conn.close()
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    from datetime import datetime
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, expires_at FROM password_reset_tokens 
        WHERE token = ? AND datetime(expires_at) > datetime('now')
    """, (token,))
    reset = cur.fetchone()
    
    if not reset:
        conn.close()
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        if not is_strong_password(password):
            flash("Password is too weak. Use at least 8 characters including uppercase, lowercase, a number, and a symbol.", "danger")
            return redirect(url_for('reset_password', token=token))
        
        pw_hash = generate_password_hash(password)
        cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, reset['user_id']))
        cur.execute("DELETE FROM password_reset_tokens WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        flash("Password reset successfully. Please log in.", "success")
        return redirect(url_for('login'))
    
    conn.close()
    return render_template('reset_password.html', token=token)

# Notifications
@app.route('/notifications')
@login_required
def notifications():
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, message, link, is_read, created_at 
        FROM notifications 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 50
    """, (user_id,))
    notifs = cur.fetchall()
    
    # If AJAX request, return JSON without marking as read
    if request.headers.get('Accept') == 'application/json' or request.args.get('json') == '1':
        conn.close()
        return jsonify({'notifications': [dict(n) for n in notifs]})
    
    # Mark as read for full page view
    cur.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
    conn.commit()
    conn.close()
    return render_template('notifications.html', notifications=notifs)

def create_notification(user_id, message, link=None):
    """Helper to create a notification for a user."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO notifications (user_id, message, link) VALUES (?, ?, ?)", (user_id, message, link))
    conn.commit()
    conn.close()

# Report Product
@app.route('/product/<int:product_id>/report', methods=['POST'])
@login_required
def report_product(product_id):
    reason = request.form.get('reason', '').strip()
    if not reason:
        flash("Please provide a reason for reporting.", "danger")
        return redirect(url_for('product_detail', product_id=product_id))
    
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO product_reports (product_id, reporter_id, reason) VALUES (?, ?, ?)",
               (product_id, user_id, reason))
    conn.commit()
    conn.close()
    flash("Thank you for your report. We'll review it shortly.", "success")
    return redirect(url_for('product_detail', product_id=product_id))

# Seller Reply to Review
@app.route('/review/<int:review_id>/reply', methods=['POST'])
@login_required
def reply_to_review(review_id):
    response = request.form.get('response', '').strip()
    if not response:
        flash("Please enter a response.", "danger")
        return redirect(request.referrer or url_for('index'))
    
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Verify this user is the seller of the reviewed product
    cur.execute("""
        SELECT r.id, p.seller_id 
        FROM reviews r
        JOIN products p ON r.product_id = p.id
        WHERE r.id = ?
    """, (review_id,))
    review = cur.fetchone()
    
    if not review or review['seller_id'] != user_id:
        conn.close()
        flash("You can only reply to reviews on your own products.", "danger")
        return redirect(request.referrer or url_for('index'))
    
    cur.execute("UPDATE reviews SET seller_response = ? WHERE id = ?", (response, review_id))
    conn.commit()
    conn.close()
    flash("Response added to review.", "success")
    return redirect(request.referrer or url_for('index'))

# User Profile Editor
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip() or None
        seller_description = request.form.get('seller_description', '').strip() or None
        profile_picture = request.form.get('profile_picture', '').strip() or None
        
        cur.execute("""
            UPDATE users 
            SET business_name = ?, seller_description = ?, profile_picture = ?
            WHERE id = ?
        """, (business_name, seller_description, profile_picture, user_id))
        conn.commit()
        conn.close()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('edit_profile'))
    
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return render_template('edit_profile.html', user=user)

# Seller Dashboard with Analytics
@app.route('/seller/dashboard')
@login_required
def seller_dashboard():
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if user is a seller
    cur.execute("SELECT is_seller FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    if not user or not user['is_seller']:
        conn.close()
        flash("Seller access required.", "warning")
        return redirect(url_for('index'))
    
    # Get stats
    cur.execute("SELECT COUNT(*) as count FROM products WHERE seller_id = ?", (user_id,))
    product_count = cur.fetchone()['count']
    
    cur.execute("""
        SELECT COUNT(DISTINCT o.id) as count, COALESCE(SUM(o.total), 0) as revenue
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        JOIN products p ON oi.product_id = p.id
        WHERE p.seller_id = ?
    """, (user_id,))
    order_stats = cur.fetchone()
    
    # Top products
    cur.execute("""
        SELECT p.id, p.title, SUM(oi.quantity) as sold, SUM(oi.quantity * oi.unit_price) as revenue
        FROM products p
        JOIN order_items oi ON oi.product_id = p.id
        WHERE p.seller_id = ?
        GROUP BY p.id
        ORDER BY sold DESC
        LIMIT 5
    """, (user_id,))
    top_products = cur.fetchall()
    
    # Recent orders
    cur.execute("""
        SELECT o.id, o.buyer_name, o.total, o.status, o.created_at
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        JOIN products p ON oi.product_id = p.id
        WHERE p.seller_id = ?
        GROUP BY o.id
        ORDER BY o.created_at DESC
        LIMIT 10
    """, (user_id,))
    recent_orders = cur.fetchall()
    
    # Highest in each category (top performing product per category)
    cur.execute("""
        SELECT p.category, p.id, p.title, p.price, p.image_url, p.view_count,
               COALESCE(SUM(oi.quantity), 0) as total_sold,
               COALESCE(SUM(oi.quantity * oi.unit_price), 0) as category_revenue
        FROM products p
        LEFT JOIN order_items oi ON oi.product_id = p.id
        WHERE p.seller_id = ? AND p.category IS NOT NULL
        GROUP BY p.category, p.id
        HAVING total_sold = (
            SELECT MAX(sales)
            FROM (
                SELECT COALESCE(SUM(oi2.quantity), 0) as sales
                FROM products p2
                LEFT JOIN order_items oi2 ON oi2.product_id = p2.id
                WHERE p2.seller_id = ? AND p2.category = p.category
                GROUP BY p2.id
            )
        )
        ORDER BY category_revenue DESC
    """, (user_id, user_id))
    top_by_category = cur.fetchall()
    
    conn.close()
    return render_template('seller_dashboard.html', 
                         product_count=product_count,
                         order_count=order_stats['count'],
                         revenue=order_stats['revenue'],
                         top_products=top_products,
                         recent_orders=recent_orders,
                         top_by_category=top_by_category)

# Recently Viewed Products
def track_product_view(product_id):
    """Helper to track when a product is viewed."""
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Delete any existing view records for this user and product to avoid duplicates
    if user_id:
        cur.execute("DELETE FROM product_views WHERE user_id = ? AND product_id = ?", (user_id, product_id))
    
    # Insert new view record (this will be the most recent)
    cur.execute("INSERT INTO product_views (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
    
    # Increment view count
    cur.execute("UPDATE products SET view_count = view_count + 1 WHERE id = ?", (product_id,))
    
    # Clean up old views (keep last 50 per user)
    if user_id:
        cur.execute("""
            DELETE FROM product_views 
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM product_views WHERE user_id = ? ORDER BY viewed_at DESC LIMIT 50
            )
        """, (user_id, user_id))
    conn.commit()
    conn.close()

@app.route('/recently-viewed')
def recently_viewed():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to see your recently viewed products.", "info")
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT p.id, p.title, p.price, p.image_url, p.stock, pv.viewed_at
        FROM product_views pv
        JOIN products p ON pv.product_id = p.id
        WHERE pv.user_id = ?
        ORDER BY pv.viewed_at DESC
        LIMIT 20
    """, (user_id,))
    products = cur.fetchall()
    conn.close()
    return render_template('recently_viewed.html', products=products)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

