# Main application entry point for e-commerce/PWA webstore
# Imports core libraries, models, and initializes Flask app
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, make_response
from functools import wraps
from math import ceil
import os
import json
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import timedelta, datetime
from sqlalchemy import func, desc, distinct, or_
from sqlalchemy.exc import IntegrityError
import uuid

# Import models and db
from models import db, User, Product, Order, OrderItem, Review, Favorite, Notification, \
    PasswordResetToken, ProductReport, ProductView, Address, Bid


# --- Flask app configuration: session, upload, and security settings ---
app = Flask(__name__)
app.secret_key = "yes_sir_i_did_change_the_secret_key1234"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Auto-logout after 30 min
# Prefer HTTPS when building absolute URLs (can override via env)
app.config['PREFERRED_URL_SCHEME'] = os.environ.get('PREFERRED_URL_SCHEME', 'http')
# Optionally pin a canonical server name for absolute URL generation (off by default)
if os.environ.get('SERVER_NAME'):
    app.config['SERVER_NAME'] = os.environ['SERVER_NAME']

# --- File upload configuration: sets allowed image types and max file size ---
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Return True if the uploaded file has an allowed image extension (png, jpg, jpeg, gif, webp)."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- SQLAlchemy database configuration: sets up SQLite URI and options ---
DB_PATH = os.path.join(os.path.dirname(__file__), "webstore.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False  # Set to True for SQL debugging

# --- Initialize SQLAlchemy ORM ---
db.init_app(app)

# --- Create database tables if not present (first run) ---
with app.app_context():
    db.create_all()

def is_strong_password(pw: str) -> bool:
    """Check if password meets strong policy: 8+ chars, lower/upper/digit/special."""
    if not pw or len(pw) < 8:
        return False
    has_lower = any(c.islower() for c in pw)
    has_upper = any(c.isupper() for c in pw)
    has_digit = any(c.isdigit() for c in pw)
    has_special = any(not c.isalnum() for c in pw)
    return has_lower and has_upper and has_digit and has_special

def ensure_cart():
    """Retrieve cart from session, or load from cookie if session cart is missing/empty."""
    if 'cart' not in session or not session['cart']:
        # Try to load from cookie
        cart_cookie = request.cookies.get('cart')
        if cart_cookie:
            try:
                session['cart'] = json.loads(cart_cookie)
            except (json.JSONDecodeError, ValueError):
                session['cart'] = {}
        else:
            session['cart'] = {}
    return session['cart']

def save_cart_to_cookie(response, cart):
    """Serialize cart as JSON and store in cookie for 30-day persistence."""
    cart_json = json.dumps(cart)
    response.set_cookie('cart', cart_json, max_age=30*24*60*60, httponly=True, samesite='Lax')
    return response

def cart_total_items_and_amount(cart):
    """Calculate total items and total amount in the cart."""
    total_items = 0
    total_amount = Decimal("0.00")
    if not cart:
        return total_items, total_amount
    ids = list(cart.keys())
    products = Product.query.filter(Product.id.in_(ids)).all()
    product_prices = {str(p.id): Decimal(str(p.price)) for p in products}
    for pid, qty in cart.items():
        total_items += qty
        price = product_prices.get(str(pid), Decimal("0.00"))
        total_amount += price * qty
    return total_items, total_amount

def login_required(f):
    """Decorator to require user login for protected routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_user_permissions():
    """Inject user role flags (admin/seller) and cart item count into Jinja2 templates for navbar and permissions."""
    uid = session.get('user_id')
    is_admin_flag = False
    is_seller_flag = False
    if uid:
        user = User.query.get(uid)
        if user:
            allowed_admin_username = 'Bean'
            if (user.username and user.username.strip().lower() == allowed_admin_username.strip().lower()) or user.is_admin:
                is_admin_flag = True
            if user.is_seller:
                is_seller_flag = True
    # Get cart item count from session/cookie
    cart = ensure_cart()
    cart_item_count = sum(cart.values()) if cart else 0
    return {
        'current_user_is_admin': is_admin_flag, 
        'current_user_is_seller': is_seller_flag,
        'cart_item_count': cart_item_count
    }

def admin_required(f):
    """Decorator to restrict admin routes to a specific username or users with is_admin flag."""
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = session.get('user_id')
        if not uid:
            return redirect(url_for('login', next=request.path))
        user = User.query.get(uid)
        allowed_admin_username = 'Briscoe'
        has_name_match = bool(user and user.username and user.username.strip().lower() == allowed_admin_username.strip().lower())
        has_admin_flag = bool(user and user.is_admin)
        if not (has_name_match or has_admin_flag):
            flash("Admin access required.")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


# --- Home page route: fetches featured, popular, recently viewed products, and auction info for main landing page ---
@app.route('/')
def index():
    # Fetch featured products with seller info (exclude out of stock, limit to 9 for carousel)
    featured_raw = db.session.query(
        Product.id, Product.title, Product.description, Product.price, Product.stock, 
        Product.created_at, Product.seller_id, Product.image_url, Product.category,
        User.business_name, User.rating, User.username.label('seller_username')
    ).outerjoin(User, Product.seller_id == User.id)\
     .filter(Product.stock > 0)\
     .order_by(desc(Product.created_at))\
     .limit(9)\
     .all()
    
    # Convert to dictionaries for template compatibility
    featured = [dict(row._mapping) for row in featured_raw]
    
    # Fetch stats
    stats = {
        'active_listings': Product.query.filter(Product.stock > 0).count(),
        'total_sellers': db.session.query(func.count(distinct(User.id))).filter(User.is_seller == 1).scalar() or 0,
        'total_buyers': db.session.query(func.count(distinct(User.id))).filter(User.is_seller == 0).scalar() or 0,
        'total_users': User.query.count(),
        'total_products': Product.query.count()
    }

    # Fetch most popular products (by view_count, in stock) for ocean animation
    popular_raw = db.session.query(
        Product.id, Product.title, Product.price, Product.stock,
        Product.image_url, Product.category, Product.view_count
    ).filter(Product.stock > 0)
    # Basic heuristic: require at least 1 view, order by view_count desc then newest
    popular_raw = popular_raw.filter((Product.view_count.isnot(None)) & (Product.view_count > 0))\
        .order_by(desc(Product.view_count), desc(Product.created_at))\
        .limit(30)\
        .all()
    popular_products = [dict(row._mapping) for row in popular_raw]
    
    # Fetch recently viewed products (exclude out of stock)
    recently_viewed = []
    user_id = session.get('user_id')
    if user_id:
        recently_viewed_raw = db.session.query(
            Product.id, Product.title, Product.description, Product.price, Product.stock,
            Product.image_url, Product.category, Product.seller_id,
            User.business_name, User.username.label('seller_username')
        ).join(ProductView, ProductView.product_id == Product.id)\
         .outerjoin(User, Product.seller_id == User.id)\
         .filter(ProductView.user_id == user_id)\
         .filter(Product.stock > 0)\
         .distinct(Product.id)\
         .order_by(desc(ProductView.viewed_at))\
         .limit(8)\
         .all()
        recently_viewed = [dict(row._mapping) for row in recently_viewed_raw]
    
    # Ending soon auctions (next 24h)
    ending_soon_auctions = Product.query.filter(
        Product.is_auction == 1,
        Product.auction_end.isnot(None),
        Product.auction_end > datetime.utcnow(),
        Product.auction_end <= datetime.utcnow() + timedelta(hours=24)
    ).order_by(Product.auction_end.asc()).limit(6).all()

    return render_template(
        'index.html',
        featured_products=featured,
        recently_viewed=recently_viewed,
        stats=stats,
        popular_products=popular_products,
        ending_soon_auctions=ending_soon_auctions
    )

# --- About page route ---
@app.route('/about')
def about():
    return render_template('about.html')

# --- Contact page route: handles contact form submission ---
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

# --- Live Search Autocomplete API endpoint ---
@app.route('/api/search/autocomplete')
def search_autocomplete():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])
    
    # Search products by title, description, or category
    products = db.session.query(
        Product.id, Product.title, Product.price, Product.image_url, 
        Product.category, Product.stock
    ).filter(
        or_(
            Product.title.like(f'%{query}%'),
            Product.description.like(f'%{query}%'),
            Product.category.like(f'%{query}%')
        )
    ).filter(Product.stock > 0)\
     .order_by(desc(Product.view_count))\
     .limit(10)\
     .all()
    
    results = [{
        'id': p.id,
        'title': p.title,
        'price': float(p.price),
        'image_url': p.image_url or '/static/img/placeholder.png',
        'category': p.category,
        'url': url_for('product_detail', product_id=p.id)
    } for p in products]
    
    return jsonify(results)

# --- Help, Privacy, and Terms static page routes ---
@app.route('/help')
def help():
    return render_template('help.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

# --- Products listing route: supports filtering, sorting, and pagination ---
@app.route('/products')
def products():
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'newest')
    category = request.args.get('category', '')
    condition = request.args.get('condition', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    page = int(request.args.get('page', 1))
    per_page_raw = request.args.get('per_page', 12)
    try:
        per_page = int(per_page_raw) if per_page_raw else 12
    except ValueError:
        per_page = 12
    
    # Build query with explicit column selection
    query = db.session.query(
        Product.id, Product.title, Product.description, Product.price, Product.stock,
        Product.image_url, Product.category, Product.condition, Product.location,
        Product.view_count, Product.created_at, Product.seller_id,
        User.business_name, User.username.label('seller_name')
    ).outerjoin(User, Product.seller_id == User.id)
    
    # Apply filters
    if search:
        query = query.filter(or_(
            Product.title.like(f'%{search}%'),
            Product.description.like(f'%{search}%')
        ))
    if category:
        query = query.filter(Product.category == category)
    if condition:
        query = query.filter(Product.condition == condition)
    if min_price:
        try:
            query = query.filter(Product.price >= float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            query = query.filter(Product.price <= float(max_price))
        except ValueError:
            pass
    
    # Apply sorting (in-stock items first, then out-of-stock)
    if sort == 'price_low':
        query = query.order_by(desc(Product.stock > 0), Product.price.asc())
    elif sort == 'price_high':
        query = query.order_by(desc(Product.stock > 0), Product.price.desc())
    elif sort == 'popular':
        query = query.order_by(desc(Product.stock > 0), desc(Product.view_count), desc(Product.created_at))
    else:
        query = query.order_by(desc(Product.stock > 0), desc(Product.created_at))
    
    # Pagination
    total_products = query.count()
    products_raw = query.offset((page-1)*per_page).limit(per_page).all()
    products_list = [dict(row._mapping) for row in products_raw]
    total_pages = ceil(total_products / per_page)
    
    # Get distinct categories and conditions for filters
    categories = db.session.query(Product.category).distinct().filter(Product.category.isnot(None)).order_by(Product.category).all()
    categories = [c[0] for c in categories]
    
    conditions_list = ['new', 'used', 'refurbished']
    
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
                         per_page=per_page,
                         total_pages=total_pages,
                         total=total_products)

# --- Product detail route: shows product info, reviews, auction data, and related products ---
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    # Track product view
    track_product_view(product_id)
    
    # Fetch product with seller info - select specific columns to create dictionary
    product_raw = db.session.query(
        Product.id, Product.title, Product.description, Product.price, Product.stock,
        Product.image_url, Product.category, Product.condition, Product.location,
        Product.seller_id, Product.view_count, Product.created_at,
        Product.is_auction, Product.starting_bid, Product.current_bid,
        Product.auction_end, Product.reserve_price, Product.buy_now_price,
        User.business_name, User.username.label('seller_username'), User.rating.label('seller_rating'),
        User.seller_description, User.total_sales
    ).outerjoin(User, Product.seller_id == User.id)\
     .filter(Product.id == product_id)\
     .first()
    
    if product_raw is None:
        flash("Product not found.")
        return redirect(url_for('products'))
    
    # Convert to dictionary
    product = dict(product_raw._mapping)
    
    # Also need the actual Product object for auction checks
    product_obj = Product.query.get(product_id)

    # Auction-specific data
    bid_history = []
    winning_bid = None
    user_highest_bid = None
    is_auction_ended = False
    time_remaining = None
    time_remaining_str = None
    
    if product.get('is_auction'):
        # Get bid history
        bid_history = db.session.query(Bid, User.username)\
            .join(User, Bid.user_id == User.id)\
            .filter(Bid.product_id == product_id)\
            .order_by(desc(Bid.bid_amount))\
            .limit(10)\
            .all()
        
        # Get winning bid
        winning_bid = Bid.query.filter_by(product_id=product_id, is_winning=1).first()
        
        # Check if auction ended and calculate time remaining
        if product.get('auction_end'):
            # Parse the auction end time string to datetime
            from datetime import datetime as dt
            try:
                auction_end_dt = dt.strptime(product['auction_end'], '%Y-%m-%d %H:%M:%S')
                now = dt.utcnow()
                
                if auction_end_dt <= now:
                    is_auction_ended = True
                else:
                    # Calculate time remaining
                    time_remaining = auction_end_dt - now
                    
                    # Format time remaining as human-readable string
                    days = time_remaining.days
                    hours, remainder = divmod(time_remaining.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    if days > 0:
                        time_remaining_str = f"{days}d {hours}h {minutes}m"
                    elif hours > 0:
                        time_remaining_str = f"{hours}h {minutes}m"
                    else:
                        time_remaining_str = f"{minutes}m {seconds}s"
            except (ValueError, TypeError):
                # Invalid date format
                time_remaining_str = "Unknown"
        
        # Get user's highest bid if logged in
        uid = session.get('user_id')
        if uid:
            user_highest_bid = Bid.query.filter_by(product_id=product_id, user_id=uid)\
                .order_by(desc(Bid.bid_amount))\
                .first()

    # Fetch reviews with seller responses
    reviews = db.session.query(Review, User.username)\
        .join(User, Review.user_id == User.id)\
        .filter(Review.product_id == product_id, Review.is_approved == 1)\
        .order_by(desc(Review.created_at))\
        .all()

    # Get review stats
    stats = db.session.query(
        func.count(Review.id).label('c'),
        func.avg(Review.rating).label('avg_rating')
    ).filter(Review.product_id == product_id, Review.is_approved == 1).first()
    
    # Related products (same category)
    related_products_raw = db.session.query(
        Product.id, Product.title, Product.price, Product.stock, Product.image_url,
        Product.category, User.business_name
    ).outerjoin(User, Product.seller_id == User.id)\
     .filter(Product.category == product.get('category'), Product.id != product_id, Product.stock > 0)\
     .order_by(func.random())\
     .limit(4)\
     .all()
    related_products = [dict(row._mapping) for row in related_products_raw]
    
    # Check if user favorited this
    is_favorited = False
    uid = session.get('user_id')
    if uid:
        is_favorited = Favorite.query.filter_by(user_id=uid, product_id=product_id).first() is not None
    
    # Determine if current user purchased this product (to allow reviewing)
    can_review = False
    if uid:
        can_review = db.session.query(Order)\
            .join(OrderItem)\
            .filter(Order.buyer_id == uid, OrderItem.product_id == product_id)\
            .first() is not None
    
    review_count = stats.c if stats else 0
    avg_rating = float(stats.avg_rating) if stats and stats.avg_rating is not None else None

    return render_template('product_detail.html', 
                         product=product, 
                         reviews=reviews, 
                         review_count=review_count, 
                         avg_rating=avg_rating, 
                         can_review=can_review, 
                         related_products=related_products, 
                         is_favorited=is_favorited,
                         bid_history=bid_history,
                         winning_bid=winning_bid,
                         user_highest_bid=user_highest_bid,
                         is_auction_ended=is_auction_ended,
                         time_remaining=time_remaining_str)

# --- Product review submission route: allows buyers to submit or update reviews ---
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
    
    # Ensure product exists
    product = Product.query.get(product_id)
    if not product:
        flash('Product not found.')
        return redirect(url_for('products'))

    # Ensure the user has purchased this product
    has_purchased = db.session.query(Order)\
        .join(OrderItem)\
        .filter(Order.buyer_id == user_id, OrderItem.product_id == product_id)\
        .first() is not None
    
    if not has_purchased:
        flash('Only customers who purchased this item can leave a review.')
        return redirect(url_for('product_detail', product_id=product_id))

    # Check if review already exists
    existing_review = Review.query.filter_by(product_id=product_id, user_id=user_id).first()
    if existing_review:
        # Update existing review
        existing_review.rating = rating
        existing_review.title = title or None
        existing_review.body = body
        existing_review.created_at = datetime.utcnow()
        existing_review.is_approved = 0  # Reset approval when edited
    else:
        # Create new review
        new_review = Review(
            product_id=product_id,
            user_id=user_id,
            rating=rating,
            title=title or None,
            body=body
        )
        db.session.add(new_review)
    
    db.session.commit()
    flash('Thanks for your review!')
    return redirect(url_for('product_detail', product_id=product_id))

# --- Cart view route: displays cart items and recently viewed products ---
@app.route('/cart')
def cart_view():
    cart = ensure_cart()
    items = []
    if cart:
        for pid, qty in cart.items():
            product = Product.query.get(pid)
            if product:
                items.append({
                    'product': product,
                    'quantity': qty,
                    'line_total': float(product.price) * qty
                })
    total_items, total_amount = cart_total_items_and_amount(cart)
    
    # Fetch recently viewed products (exclude out of stock)
    recently_viewed = []
    user_id = session.get('user_id')
    if user_id:
        recently_viewed = db.session.query(Product)\
            .join(ProductView)\
            .filter(ProductView.user_id == user_id)\
            .filter(Product.stock > 0)\
            .distinct(Product.id)\
            .order_by(desc(ProductView.viewed_at))\
            .limit(8)\
            .all()
    
    response = make_response(render_template('cart.html', items=items, total_items=total_items, total_amount=total_amount, recently_viewed=recently_viewed))
    response = save_cart_to_cookie(response, cart)
    return response

# --- Cart add route: adds products to cart, respects stock limits ---
@app.route('/cart/add', methods=['POST'])
def cart_add():
    product_id = request.form.get('product_id')
    qty = int(request.form.get('quantity', 1))
    
    # Ensure product exists and respect stock limits
    prod = Product.query.get(product_id)
    if not prod:
        flash("Product not found.")
        return redirect(request.form.get('next') or url_for('products'))

    # stock == None/NULL means unlimited
    stock = prod.stock
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
        response = make_response(jsonify({
            "ok": True,
            "total_items": total_items,
            "total_amount": float(total_amount),
            "added": add_amount,
            "requested": add_requested,
            "message": msg
        }))
        response = save_cart_to_cookie(response, cart)
        return response
    # notify if we could not add full requested amount
    if add_amount < add_requested:
        flash(f"Only {add_amount} items were added due to limited stock.")
    else:
        flash("Added to cart.")
    response = make_response(redirect(request.form.get('next') or url_for('cart_view')))
    response = save_cart_to_cookie(response, cart)
    return response

# --- Cart summary API: returns total items and amount in cart ---
@app.route('/cart/summary')
def cart_summary():
    cart = ensure_cart()
    total_items, total_amount = cart_total_items_and_amount(cart)
    return jsonify({"total_items": total_items, "total_amount": float(total_amount)})

# --- Cart update route: updates quantities, checks stock ---
@app.route('/cart/update', methods=['POST'])
def cart_update():
    cart = ensure_cart()
    cart = dict(cart)
    # For each qty_<id> field, ensure quantity does not exceed stock
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
        product = Product.query.get(prod_id)
        if product and product.stock is not None:
            if q > product.stock:
                q = product.stock
                flash(f"Quantity for product {prod_id} reduced to available stock ({product.stock}).")

        cart[prod_id] = q
    session['cart'] = cart
    flash("Cart updated.")
    response = make_response(redirect(url_for('cart_view')))
    response = save_cart_to_cookie(response, cart)
    return response

# --- Cart remove route: removes product from cart ---
@app.route('/cart/remove/<int:product_id>', methods=['POST'])
def cart_remove(product_id):
    cart = ensure_cart()
    cart = dict(cart)
    cart.pop(str(product_id), None)
    session['cart'] = cart
    flash("Removed item.")
    response = make_response(redirect(url_for('cart_view')))
    response = save_cart_to_cookie(response, cart)
    return response

# --- User registration route: handles new user sign-up ---
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
        
        # Check if user already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash("Username or email already taken.")
            return redirect(url_for('register'))
        
        pw_hash = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=pw_hash, is_seller=0)
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        session['username'] = username
        session.permanent = True
        flash("Registered and logged in.")
        next_url = request.args.get('next') or url_for('index')
        return redirect(next_url)
    return render_template('register.html')

# --- User login route: handles authentication and cart merging ---
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        
        user = User.query.filter((User.username == username) | (User.email == username)).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid credentials.")
            return redirect(url_for('login', next=request.args.get('next')))
        
        session['user_id'] = user.id
        session['username'] = user.username
        session.permanent = True
        
        # Merge cart from cookie if exists
        cart_cookie = request.cookies.get('cart')
        if cart_cookie:
            try:
                cookie_cart = json.loads(cart_cookie)
                session_cart = session.get('cart', {})
                # Merge: add cookie cart items to session cart
                for pid, qty in cookie_cart.items():
                    if pid in session_cart:
                        session_cart[pid] = max(session_cart[pid], qty)
                    else:
                        session_cart[pid] = qty
                session['cart'] = session_cart
            except (json.JSONDecodeError, ValueError):
                pass
        
        flash("Logged in.")
        response = make_response(redirect(request.args.get('next') or url_for('index')))
        # Update cookie with merged cart
        if 'cart' in session:
            response = save_cart_to_cookie(response, session['cart'])
        return response
    return render_template('login.html')

# --- User logout route: clears session ---
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash("Logged out.")
    return redirect(url_for('index'))

# --- Checkout route: processes orders and payment ---
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart = ensure_cart()
    if not cart:
        flash("Your cart is empty.")
        return redirect(url_for('products'))

    # build items list for display and compute total (include stock for checks)
    ids = list(cart.keys())
    products = Product.query.filter(Product.id.in_(ids)).all()
    product_dict = {str(p.id): p for p in products}
    
    items = []
    total = 0.0
    for pid, qty in cart.items():
        p = product_dict.get(str(pid))
        if not p:
            continue
        line_total = float(p.price) * qty
        items.append({"product": p, "quantity": qty, "line_total": line_total})
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
            prod = product_dict.get(str(pid))
            if not prod:
                insufficient.append((pid, 0, qty))
                continue
            stock = prod.stock
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
            return redirect(url_for('cart_view'))

        # create order
        buyer_id = session.get('user_id')
        new_order = Order(
            buyer_id=buyer_id,
            buyer_name=name,
            buyer_email=email,
            shipping_address=address,
            total=total
        )
        db.session.add(new_order)
        db.session.flush()  # Get the order ID

        # save address for user (avoid duplicates due to UNIQUE constraint)
        try:
            if buyer_id:
                existing_address = Address.query.filter_by(user_id=buyer_id, address_text=address).first()
                if not existing_address:
                    new_address = Address(user_id=buyer_id, label=None, address_text=address)
                    db.session.add(new_address)
        except Exception:
            pass

        # insert order items and reduce stock
        for pid, qty in cart.items():
            prod = product_dict.get(str(pid))
            if not prod:
                continue
            unit_price = float(prod.price)
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=int(pid),
                quantity=qty,
                unit_price=unit_price
            )
            db.session.add(order_item)
            
            # decrement stock if not NULL
            if prod.stock is not None:
                prod.stock = prod.stock - qty
            
            # increment seller's total_sales if seller_id present
            if prod.seller_id:
                seller = User.query.get(prod.seller_id)
                if seller:
                    seller.total_sales = (seller.total_sales or 0) + qty
        
        db.session.commit()
        session.pop('cart', None)

        # redirect to order confirmation page
        flash("Order placed successfully!")
        response = make_response(redirect(url_for('order_confirmation', order_id=new_order.id)))
        # Clear cart cookie after successful purchase
        response.set_cookie('cart', '', max_age=0)
        return response

    # GET: prefill name/email if available
    user = User.query.get(session.get('user_id'))
    pre_name = user.username if user else ''
    pre_email = user.email if user else ''
    return render_template('checkout.html', items=items, total_amount=total, pre_name=pre_name, pre_email=pre_email)

# --- Order confirmation route: displays order details after purchase ---
@app.route('/order/<int:order_id>')
def order_confirmation(order_id):
    order = Order.query.get(order_id)
    if not order:
        flash("Order not found.")
        return redirect(url_for('index'))

    items_raw = db.session.query(OrderItem.quantity, OrderItem.unit_price, Product.title, Product.image_url)\
        .join(Product, OrderItem.product_id == Product.id)\
        .filter(OrderItem.order_id == order_id)\
        .all()
    items = [dict(row._mapping) for row in items_raw]
    
    return render_template('order_confirmation.html', order=order, items=items)

# --- Address suggestions API: returns saved addresses for user ---
@app.route('/addresses')
def address_suggestions():
    """Return saved addresses for the logged-in user that match ?query=..."""
    if 'user_id' not in session:
        return jsonify([])

    q = request.args.get('query', '').strip()
    query = Address.query.filter_by(user_id=session['user_id'])
    
    if q:
        query = query.filter(Address.address_text.like(f'%{q}%'))
    
    addresses = query.order_by(desc(Address.created_at)).limit(8).all()
    return jsonify([{"id": a.id, "label": a.label, "address": a.address_text} for a in addresses])

# --- Seller profile route: shows seller info and their products ---
@app.route('/seller/<int:seller_id>')
def seller_profile(seller_id):
    seller = User.query.get(seller_id)
    products = []
    if seller:
        products = Product.query.filter_by(seller_id=seller_id).order_by(desc(Product.created_at)).all()

    return render_template('seller_profile.html', seller=seller, products=products)

# --- Favicon route: serves favicon from available static assets ---
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

# --- Post ad route: allows sellers to create new product or auction listings ---
@app.route('/post-ad', methods=['GET', 'POST'])
@login_required
def post_ad():
    # Check if user is a seller
    user = User.query.get(session.get('user_id'))
    
    if not user or not user.is_seller:
        flash("You must be a seller to post ads. Please contact support to become a seller.", "warning")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '0').strip()
        stock = request.form.get('stock', '0').strip()
        category = request.form.get('category', 'Other').strip()
        image_url = request.form.get('image_url', '').strip() or None
        
        # Auction fields (force boats into auction mode)
        boat_categories = {"Sailboats", "Powerboats", "Dinghies"}
        requested_is_auction = request.form.get('is_auction') == 'on'
        is_boat_category = category in boat_categories
        # Force auction for boat categories regardless of checkbox
        is_auction = requested_is_auction or is_boat_category
        starting_bid = request.form.get('starting_bid', '').strip()
        auction_duration = request.form.get('auction_duration', '').strip()
        reserve_price = request.form.get('reserve_price', '').strip()
        buy_now_price = request.form.get('buy_now_price', '').strip()
        
        # Handle image URL formatting
        if image_url and not (image_url.startswith('http://') or image_url.startswith('https://') or image_url.startswith('/')):
            # Treat bare filenames as files placed under /static/img/
            image_url = f"/static/img/{image_url}"
        
        # Validation
        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for('post_ad'))
        
        try:
            if is_auction:
                # For auctions: stock must be 1 (one-of-a-kind)
                stock_val = 1
                starting_bid_val = float(starting_bid) if starting_bid else 0
                # If boat category and no starting bid supplied, use listed price as starting bid
                if is_boat_category and starting_bid_val <= 0:
                    starting_bid_val = float(price) if price else 0
                if starting_bid_val <= 0:
                    raise ValueError("Starting bid must be greater than 0")
                
                # Calculate auction end time
                duration_days = int(auction_duration) if auction_duration else 7
                if duration_days < 1 or duration_days > 30:
                    raise ValueError("Auction duration must be between 1 and 30 days")
                auction_end_time = datetime.utcnow() + timedelta(days=duration_days)
                
                # Optional fields
                reserve_price_val = float(reserve_price) if reserve_price else None
                buy_now_price_val = float(buy_now_price) if buy_now_price else None
                
                price_val = starting_bid_val  # Set price to starting bid for display
            else:
                # Regular product
                price_val = float(price)
                stock_val = int(stock)
                if price_val < 0 or stock_val < 0:
                    raise ValueError("Price and stock must be non-negative")
                starting_bid_val = None
                auction_end_time = None
                reserve_price_val = None
                buy_now_price_val = None
                
        except ValueError as e:
            flash(f"Invalid input: {e}", "danger")
            return redirect(url_for('post_ad'))
        
        # Insert the product
        seller_id = session.get('user_id')
        new_product = Product(
            seller_id=seller_id,
            title=title,
            description=description,
            price=price_val,
            stock=stock_val,
            image_url=image_url,
            category=category,
            is_auction=1 if is_auction else 0,
            starting_bid=starting_bid_val,
            current_bid=starting_bid_val if is_auction else None,
            auction_end=auction_end_time,
            reserve_price=reserve_price_val,
            buy_now_price=buy_now_price_val
        )
        db.session.add(new_product)
        db.session.commit()
        
        if is_boat_category:
            flash("Boat listing posted as an auction (boats are auction-only).", "success")
        elif is_auction:
            flash("Your auction has been posted successfully!", "success")
        else:
            flash("Your ad has been posted successfully!", "success")
        return redirect(url_for('product_detail', product_id=new_product.id))
    
    return render_template('post_ad.html')

# --- Admin utility: convert boat listings to auctions ---
@app.route('/admin/convert-boats', methods=['POST'])
@login_required
def admin_convert_boats():
    # Simple admin utility to convert existing boat listings into auctions
    user = User.query.get(session.get('user_id'))
    if not user or not user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('index'))
    boat_categories = ["Sailboats", "Powerboats", "Dinghies"]
    now = datetime.utcnow()
    changes = 0
    products = Product.query.filter(Product.category.in_(boat_categories), Product.is_auction == 0).all()
    for p in products:
        p.is_auction = 1
        # Use existing price as starting bid if no starting bid
        if not p.starting_bid:
            p.starting_bid = p.price if p.price else 1.0
        if not p.current_bid:
            p.current_bid = p.starting_bid
        # If auction_end not set or in past, set 7 days from now
        if not p.auction_end or p.auction_end < now:
            p.auction_end = now + timedelta(days=7)
        changes += 1
    if changes:
        db.session.commit()
        flash(f'Converted {changes} boat listings to auctions.', 'success')
    else:
        flash('No boat listings required conversion.', 'info')
    return redirect(url_for('auctions'))

# --- My listings route: shows products posted by current seller ---
@app.route('/my-listings')
@login_required
def my_listings():
    # Show products posted by the current user (if they're a seller)
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user or not user.is_seller:
        flash("You must be a seller to view listings.", "warning")
        return redirect(url_for('index'))
    
    products = Product.query.filter_by(seller_id=user_id).order_by(desc(Product.created_at)).all()
    
    return render_template('my_listings.html', products=products)

# --- User settings route: displays and updates profile and password ---
@app.route('/settings')
@login_required
def settings():
    """User settings page with password change"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    return render_template('edit_profile.html', user=user)

@app.route('/settings/update', methods=['POST'])
@login_required
def update_settings():
    """Handle settings updates"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    # Handle password change
    current_password = request.form.get('current_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    
    if current_password or new_password or confirm_password:
        # Password change requested
        if not current_password:
            flash("Please enter your current password.", "danger")
            return redirect(url_for('settings'))
        
        if not check_password_hash(user.password_hash, current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for('settings'))
        
        if not new_password:
            flash("Please enter a new password.", "danger")
            return redirect(url_for('settings'))
        
        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return redirect(url_for('settings'))
        
        if not is_strong_password(new_password):
            flash("Password is too weak. Use at least 8 characters including uppercase, lowercase, a number, and a symbol.", "danger")
            return redirect(url_for('settings'))
        
        # Update password
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Password updated successfully!", "success")
        return redirect(url_for('settings'))
    
    # Handle profile updates
    business_name = request.form.get('business_name', '').strip() or None
    seller_description = request.form.get('seller_description', '').strip() or None
    profile_picture = request.form.get('profile_picture', '').strip() or None
    
    user.business_name = business_name
    user.seller_description = seller_description
    user.profile_picture = profile_picture
    
    db.session.commit()
    flash("Profile updated successfully!", "success")
    return redirect(url_for('settings'))

# --- User profile route: shows own profile and seller stats ---
@app.route('/profile')
@login_required
def profile():
    """View user's own profile"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    # Get user's stats if seller
    stats = None
    if user.is_seller:
        products = Product.query.filter_by(seller_id=user_id).all()
        total_products = len(products)
        active_products = len([p for p in products if hasattr(p, 'status') and p.status == 'available'])
        
        stats = {
            'total_products': total_products,
            'active_products': active_products,
            'rating': user.rating or 0,
            'total_sales': user.total_sales or 0
        }
    
    return render_template('profile.html', user=user, stats=stats)

# --- Admin dashboard route: shows site stats ---
@app.route('/admin')
@admin_required
def admin_index():
    stats = {
        'products_count': Product.query.count(),
        'users_count': User.query.count(),
        'orders_count': Order.query.count(),
        'pending_reviews': Review.query.filter_by(is_approved=0).count(),
        'approved_reviews': Review.query.filter_by(is_approved=1).count(),
        'total_reviews': Review.query.count()
    }
    return render_template('admin/dashboard.html', stats=stats)

# --- Admin reviews management routes ---
@app.route('/admin/reviews')
@admin_required
def admin_reviews():
    filter_status = request.args.get('status', 'pending')  # pending, approved, all
    
    query = db.session.query(
        Review,
        User.username.label('reviewer_name'),
        Product.id.label('product_id'),
        Product.title.label('product_name')
    ).join(User, Review.user_id == User.id)\
     .join(Product, Review.product_id == Product.id)
    
    if filter_status == 'pending':
        query = query.filter(Review.is_approved == 0).order_by(desc(Review.created_at))
    elif filter_status == 'approved':
        query = query.filter(Review.is_approved == 1).order_by(desc(Review.approved_at))
    else:  # all
        query = query.order_by(desc(Review.created_at))
    
    reviews_raw = query.all()
    # Convert to list of tuples/dicts for easier template access
    reviews = []
    for row in reviews_raw:
        review_obj = row[0]  # The Review object
        reviews.append({
            'review': review_obj,
            'reviewer_name': row.reviewer_name,
            'product_id': row.product_id,
            'product_name': row.product_name
        })
    return render_template('admin/reviews.html', reviews=reviews, filter_status=filter_status)

@app.route('/admin/reviews/<int:review_id>/approve', methods=['POST'])
@admin_required
def admin_review_approve(review_id):
    review = Review.query.get(review_id)
    if review:
        review.is_approved = 1
        review.approved_at = datetime.utcnow()
        db.session.commit()
        flash('Review approved successfully.')
    return redirect(url_for('admin_reviews'))

@app.route('/admin/reviews/<int:review_id>/reject', methods=['POST'])
@admin_required
def admin_review_reject(review_id):
    review = Review.query.get(review_id)
    if review:
        db.session.delete(review)
        db.session.commit()
        flash('Review rejected and deleted.')
    return redirect(url_for('admin_reviews'))

# --- Admin orders management routes ---
@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)


@app.route('/admin/orders/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    order = Order.query.get(order_id)
    if not order:
        flash("Order not found.")
        return redirect(url_for('admin_orders'))

    items_raw = db.session.query(OrderItem.quantity, OrderItem.unit_price, Product.title, Product.image_url)\
        .join(Product, OrderItem.product_id == Product.id)\
        .filter(OrderItem.order_id == order_id)\
        .all()
    items = [dict(row._mapping) for row in items_raw]
    return render_template('admin/order_detail.html', order=order, items=items)

# --- Admin product management routes ---
@app.route('/admin/products')
@admin_required
def admin_products():
    products_raw = db.session.query(Product.id, Product.title, Product.price, Product.stock, User.username.label('seller'))\
        .outerjoin(User, Product.seller_id == User.id)\
        .order_by(Product.created_at.desc())\
        .all()
    products = [dict(row._mapping) for row in products_raw]
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
        
        crop_x = request.form.get('crop_x')
        crop_y = request.form.get('crop_y')
        crop_width = request.form.get('crop_width')
        crop_height = request.form.get('crop_height')
        new_product = Product(
            seller_id=seller_id,
            title=title,
            description=description,
            price=price_val,
            stock=stock_val,
            image_url=image_url,
            category=category,
            crop_x=float(crop_x) if crop_x else None,
            crop_y=float(crop_y) if crop_y else None,
            crop_width=float(crop_width) if crop_width else None,
            crop_height=float(crop_height) if crop_height else None
        )
        db.session.add(new_product)
        db.session.commit()
        flash("Product created.")
        return redirect(url_for('admin_products'))
    # GET
    sellers = User.query.order_by(User.username).all()
    return render_template('admin/product_form.html', sellers=sellers, product=None)

@app.route('/admin/products/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_product_edit(product_id):
    product = Product.query.get(product_id)
    if not product:
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

        product.seller_id = seller_id
        product.title = title
        product.description = description
        product.price = price_val
        product.stock = stock_val
        product.category = category
        crop_x = request.form.get('crop_x')
        crop_y = request.form.get('crop_y')
        crop_width = request.form.get('crop_width')
        crop_height = request.form.get('crop_height')
        if image_url is not None:
            product.image_url = image_url
        product.crop_x = float(crop_x) if crop_x else None
        product.crop_y = float(crop_y) if crop_y else None
        product.crop_width = float(crop_width) if crop_width else None
        product.crop_height = float(crop_height) if crop_height else None
        db.session.commit()
        flash("Product updated.")
        return redirect(url_for('admin_products'))
    # GET form
    sellers = User.query.order_by(User.username).all()
    return render_template('admin/product_form.html', product=product, sellers=sellers)

@app.route('/admin/products/<int:product_id>/delete', methods=['POST'])
@admin_required
def admin_product_delete(product_id):
    product = Product.query.get(product_id)
    if product:
        db.session.delete(product)
        db.session.commit()
    flash("Product deleted.")
    return redirect(url_for('admin_products'))

# --- Admin user management routes ---
@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/<int:user_id>/toggle_admin', methods=['POST'])
@admin_required
def admin_user_toggle_admin(user_id):
    user = User.query.get(user_id)
    if not user:
        flash("User not found.")
        return redirect(url_for('admin_users'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    flash("User admin status updated.")
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/toggle_seller', methods=['POST'])
@admin_required
def admin_user_toggle_seller(user_id):
    user = User.query.get(user_id)
    if not user:
        flash("User not found.")
        return redirect(url_for('admin_users'))
    
    user.is_seller = not user.is_seller
    db.session.commit()
    flash("User seller status updated.")
    # if we just promoted them to seller, send admin to the seller details form to fill info
    if user.is_seller:
        return redirect(url_for('admin_edit_seller', user_id=user_id))
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/seller', methods=['GET', 'POST'])
@admin_required
def admin_edit_seller(user_id):
    user = User.query.get(user_id)
    if not user:
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
        user.business_name = business_name
        user.seller_description = seller_description
        user.rating = rating
        user.total_sales = total_sales
        user.is_seller = True
        db.session.commit()
        flash("Seller details updated.")
        return redirect(url_for('admin_users'))

    return render_template('admin/seller_form.html', user=user)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_user_delete(user_id):
    # protect deleting self
    if session.get('user_id') == user_id:
        flash("Cannot delete your own account.")
        return redirect(url_for('admin_users'))
    
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
    flash("User deleted.")
    return redirect(url_for('admin_users'))

# --- Wishlist/Favorites routes ---
@app.route('/favorites')
@login_required
def favorites():
    user_id = session.get('user_id')
    products_raw = db.session.query(Product.id, Product.title, Product.description, Product.price, 
                                Product.stock, Product.image_url, Product.category,
                                User.business_name, User.rating, Product.seller_id)\
        .join(Favorite, Favorite.product_id == Product.id)\
        .outerjoin(User, Product.seller_id == User.id)\
        .filter(Favorite.user_id == user_id)\
        .order_by(Favorite.created_at.desc())\
        .all()
    products = [dict(row._mapping) for row in products_raw]
    return render_template('favorites.html', products=products)

@app.route('/favorites/add/<int:product_id>', methods=['POST'])
@login_required
def add_favorite(product_id):
    user_id = session.get('user_id')
    try:
        new_fav = Favorite(user_id=user_id, product_id=product_id)
        db.session.add(new_fav)
        db.session.commit()
        flash("Added to favorites!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Already in favorites.", "info")
    return redirect(request.referrer or url_for('products'))

@app.route('/favorites/remove/<int:product_id>', methods=['POST'])
@login_required
def remove_favorite(product_id):
    user_id = session.get('user_id')
    Favorite.query.filter_by(user_id=user_id, product_id=product_id).delete()
    db.session.commit()
    flash("Removed from favorites.")
    return redirect(request.referrer or url_for('favorites'))

# --- Password Reset routes ---
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash("Please enter your email.", "danger")
            return redirect(url_for('forgot_password'))
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            import secrets
            from datetime import datetime, timedelta
            token = secrets.token_urlsafe(32)
            expires = datetime.utcnow() + timedelta(hours=1)
            
            reset_token = PasswordResetToken(user_id=user.id, token=token, expires_at=expires)
            db.session.add(reset_token)
            db.session.commit()
            # In production, send email with reset link
            reset_link = url_for('reset_password', token=token, _external=True)
            flash(f"Password reset link (in production this would be emailed): {reset_link}", "info")
        else:
            flash("If that email exists, a reset link has been sent.", "info")
        
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    from datetime import datetime
    
    reset = PasswordResetToken.query.filter(
        PasswordResetToken.token == token,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()
    
    if not reset:
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        if not is_strong_password(password):
            flash("Password is too weak. Use at least 8 characters including uppercase, lowercase, a number, and a symbol.", "danger")
            return redirect(url_for('reset_password', token=token))
        
        pw_hash = generate_password_hash(password)
        user = User.query.get(reset.user_id)
        user.password_hash = pw_hash
        
        db.session.delete(reset)
        db.session.commit()
        flash("Password reset successfully. Please log in.", "success")
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)

# --- Notification routes ---
@app.route('/notifications')
@login_required
def notifications():
    user_id = session.get('user_id')
    notifs = Notification.query.filter_by(user_id=user_id)\
        .order_by(Notification.created_at.desc())\
        .limit(50)\
        .all()
    
    # If AJAX request, return JSON without marking as read
    if request.headers.get('Accept') == 'application/json' or request.args.get('json') == '1':
        return jsonify({'notifications': [{'id': n.id, 'message': n.message, 'link': n.link, 
                                          'is_read': n.is_read, 'created_at': n.created_at.isoformat()} 
                                         for n in notifs]})
    
    # Mark as read for full page view
    Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('notifications.html', notifications=notifs)

def create_notification(user_id, message, link=None):
    """Helper to create a notification for a user."""
    notif = Notification(user_id=user_id, message=message, link=link)
    db.session.add(notif)
    db.session.commit()

# --- Product reporting route ---
@app.route('/product/<int:product_id>/report', methods=['POST'])
@login_required
def report_product(product_id):
    reason = request.form.get('reason', '').strip()
    if not reason:
        flash("Please provide a reason for reporting.", "danger")
        return redirect(url_for('product_detail', product_id=product_id))
    
    user_id = session.get('user_id')
    report = ProductReport(product_id=product_id, reporter_id=user_id, reason=reason)
    db.session.add(report)
    db.session.commit()
    flash("Thank you for your report. We'll review it shortly.", "success")
    return redirect(url_for('product_detail', product_id=product_id))

# --- Seller reply to product review route ---
@app.route('/review/<int:review_id>/reply', methods=['POST'])
@login_required
def reply_to_review(review_id):
    response = request.form.get('response', '').strip()
    if not response:
        flash("Please enter a response.", "danger")
        return redirect(request.referrer or url_for('index'))
    
    user_id = session.get('user_id')
    
    # Verify this user is the seller of the reviewed product
    review = db.session.query(Review, Product.seller_id)\
        .join(Product, Review.product_id == Product.id)\
        .filter(Review.id == review_id)\
        .first()
    
    if not review or review[1] != user_id:
        flash("You can only reply to reviews on your own products.", "danger")
        return redirect(request.referrer or url_for('index'))
    
    review[0].seller_response = response
    db.session.commit()
    flash("Response added to review.", "success")
    return redirect(request.referrer or url_for('index'))

# --- Seller dashboard with analytics and stats ---
@app.route('/seller/dashboard')
@login_required
def seller_dashboard():
    user_id = session.get('user_id')
    
    # Check if user is a seller
    user = User.query.get(user_id)
    if not user or not user.is_seller:
        flash("Seller access required.", "warning")
        return redirect(url_for('index'))
    
    # Get stats
    product_count = Product.query.filter_by(seller_id=user_id).count()
    
    order_stats = db.session.query(
        func.count(func.distinct(Order.id)).label('count'),
        func.coalesce(func.sum(Order.total), 0).label('revenue')
    ).join(OrderItem, OrderItem.order_id == Order.id)\
     .join(Product, OrderItem.product_id == Product.id)\
     .filter(Product.seller_id == user_id)\
     .first()
    
    # Top products
    top_products_raw = db.session.query(
        Product.id, Product.title,
        func.sum(OrderItem.quantity).label('sold'),
        func.sum(OrderItem.quantity * OrderItem.unit_price).label('revenue')
    ).join(OrderItem, OrderItem.product_id == Product.id)\
     .filter(Product.seller_id == user_id)\
     .group_by(Product.id)\
     .order_by(desc('sold'))\
     .limit(5)\
     .all()
    top_products = [dict(row._mapping) for row in top_products_raw]
    
    # Recent orders
    recent_orders_raw = db.session.query(Order.id, Order.buyer_name, Order.total, Order.status, Order.created_at)\
        .join(OrderItem, OrderItem.order_id == Order.id)\
        .join(Product, OrderItem.product_id == Product.id)\
        .filter(Product.seller_id == user_id)\
        .group_by(Order.id)\
        .order_by(Order.created_at.desc())\
        .limit(10)\
        .all()
    recent_orders = [dict(row._mapping) for row in recent_orders_raw]
    
    # Top product per category (simplified version)
    top_by_category_raw = db.session.query(
        Product.category, Product.id, Product.title, Product.price, Product.image_url, Product.view_count,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('total_sold'),
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label('category_revenue')
    ).outerjoin(OrderItem, OrderItem.product_id == Product.id)\
     .filter(Product.seller_id == user_id, Product.category.isnot(None))\
     .group_by(Product.category, Product.id)\
     .order_by(desc('category_revenue'))\
     .all()
    top_by_category = [dict(row._mapping) for row in top_by_category_raw]
    
    return render_template('seller_dashboard.html', 
                         product_count=product_count,
                         order_count=order_stats.count,
                         revenue=order_stats.revenue,
                         top_products=top_products,
                         recent_orders=recent_orders,
                         top_by_category=top_by_category)

# --- Recently viewed products tracking and route ---
def track_product_view(product_id):
    """Helper to track when a product is viewed."""
    user_id = session.get('user_id')
    
    # Delete any existing view records for this user and product to avoid duplicates
    if user_id:
        ProductView.query.filter_by(user_id=user_id, product_id=product_id).delete()
    
    # Insert new view record (this will be the most recent)
    new_view = ProductView(user_id=user_id, product_id=product_id)
    db.session.add(new_view)
    
    # Increment view count
    product = Product.query.get(product_id)
    if product:
        product.view_count = (product.view_count or 0) + 1
    
    # Clean up old views (keep last 50 per user)
    if user_id:
        # Get IDs of old views to delete
        old_views = db.session.query(ProductView.id)\
            .filter(ProductView.user_id == user_id)\
            .order_by(desc(ProductView.viewed_at))\
            .offset(50)\
            .all()
        old_view_ids = [v.id for v in old_views]
        if old_view_ids:
            ProductView.query.filter(ProductView.id.in_(old_view_ids)).delete(synchronize_session=False)
    
    db.session.commit()

@app.route('/recently-viewed')
def recently_viewed():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to see your recently viewed products.", "info")
        return redirect(url_for('login'))
    
    # Show in-stock items first, then out-of-stock
    products = db.session.query(Product, ProductView.viewed_at)\
        .join(ProductView, ProductView.product_id == Product.id)\
        .filter(ProductView.user_id == user_id)\
        .distinct(Product.id)\
        .order_by(desc(Product.stock > 0), desc(ProductView.viewed_at))\
        .limit(20)\
        .all()
    
    return render_template('recently_viewed.html', products=products)

# ===== AUCTION ROUTES =====

@app.route('/auctions')
def auctions():
    """Unified auctions view with optional filters: category=<name>, boat=1, ending=soon"""
    now = datetime.utcnow()
    boat_categories = ['Sailboats', 'Powerboats', 'Dinghies']
    category = request.args.get('category', '').strip() or None
    boat_only = request.args.get('boat') == '1'
    ending_filter = request.args.get('ending') == 'soon'

    base_query = Product.query.filter(
        Product.is_auction == 1,
        Product.auction_end.isnot(None),
        Product.auction_end > now
    )
    if boat_only:
        base_query = base_query.filter(Product.category.in_(boat_categories))
    elif category:
        base_query = base_query.filter(Product.category == category)

    active_auctions = base_query.order_by(Product.auction_end.asc()).all()
    # Ending soon subset (within next 24h)
    soon_threshold = now + timedelta(hours=24)
    ending_soon = [a for a in active_auctions if a.auction_end <= soon_threshold]

    if ending_filter:
        # Narrow to only ending soon if requested
        active_auctions = ending_soon

    # Distinct auction categories for filter dropdown
    categories_rows = db.session.query(Product.category).filter(
        Product.is_auction == 1,
        Product.auction_end > now,
        Product.auction_end.isnot(None)
    ).distinct().all()
    auction_categories = sorted([r[0] for r in categories_rows if r[0]])

    return render_template('auctions.html',
                           active_auctions=active_auctions,
                           ending_soon=ending_soon,
                           boat_categories=boat_categories,
                           selected_category=category,
                           boat_only=boat_only,
                           ending_filter=ending_filter,
                           auction_categories=auction_categories)

# Filtered boat auctions (only sailing/boat categories)
@app.route('/boat-auctions')
def boat_auctions():
    # Redirect legacy boat auctions route to unified auctions view with boat filter
    return redirect(url_for('auctions', boat='1'))

@app.route('/product/<int:product_id>/bid', methods=['POST'])
@login_required
def place_bid(product_id):
    """Place a bid on an auction item"""
    product = Product.query.get(product_id)
    user_id = session.get('user_id')
    
    if not product or not product.is_auction:
        flash("This is not an auction item.", "danger")
        return redirect(url_for('products'))
    
    # Check if auction has ended
    if product.auction_end and product.auction_end <= datetime.utcnow():
        flash("This auction has ended.", "warning")
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Prevent seller from bidding on their own item
    if product.seller_id == user_id:
        flash("You cannot bid on your own auction.", "danger")
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Get bid amount
    bid_amount_str = request.form.get('bid_amount', '').strip()
    try:
        bid_amount = float(bid_amount_str)
    except ValueError:
        flash("Invalid bid amount.", "danger")
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Validate bid amount with $5 minimum increment
    min_bid = (product.current_bid + 5) if product.current_bid else product.starting_bid
    if bid_amount < min_bid:
        flash(f"Bid must be at least ${min_bid:.2f} (minimum $5 increment)", "danger")
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Check if there's a buy now price and user wants to buy now
    if product.buy_now_price and bid_amount >= product.buy_now_price:
        # Instant win - end auction
        product.current_bid = product.buy_now_price
        product.auction_end = datetime.utcnow()
        
        # Mark all previous bids as not winning
        Bid.query.filter_by(product_id=product_id).update({'is_winning': 0})
        
        # Create winning bid
        winning_bid = Bid(
            product_id=product_id,
            user_id=user_id,
            bid_amount=product.buy_now_price,
            is_winning=1
        )
        db.session.add(winning_bid)
        db.session.commit()
        
        flash(f"Congratulations! You won the auction with Buy Now at ${product.buy_now_price:.2f}!", "success")
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Mark all previous bids for this product as not winning
    Bid.query.filter_by(product_id=product_id).update({'is_winning': 0})
    
    # Create new bid
    new_bid = Bid(
        product_id=product_id,
        user_id=user_id,
        bid_amount=bid_amount,
        is_winning=1
    )
    db.session.add(new_bid)
    
    # Update product's current bid
    product.current_bid = bid_amount
    db.session.commit()
    
    # Notify seller
    create_notification(
        product.seller_id,
        f"New bid of ${bid_amount:.2f} placed on your auction: {product.title}",
        url_for('product_detail', product_id=product_id)
    )
    
    # Notify previous highest bidder (if any)
    previous_high_bidder = Bid.query.filter(
        Bid.product_id == product_id,
        Bid.user_id != user_id,
        Bid.is_winning == 0
    ).order_by(desc(Bid.bid_amount)).first()
    
    if previous_high_bidder:
        create_notification(
            previous_high_bidder.user_id,
            f"You've been outbid on {product.title}. Current bid: ${bid_amount:.2f}",
            url_for('product_detail', product_id=product_id)
        )
    
    flash(f"Bid placed successfully! You are currently the highest bidder at ${bid_amount:.2f}", "success")
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/my-bids')
@login_required
def my_bids():
    """View user's bid history"""
    user_id = session.get('user_id')
    
    # Get all bids by this user with product info
    bids = db.session.query(Bid, Product)\
        .join(Product, Bid.product_id == Product.id)\
        .filter(Bid.user_id == user_id)\
        .order_by(desc(Bid.created_at))\
        .all()
    
    # Get auctions the user is winning
    winning_bids = db.session.query(Bid, Product)\
        .join(Product, Bid.product_id == Product.id)\
        .filter(Bid.user_id == user_id, Bid.is_winning == 1)\
        .all()
    
    return render_template('my_bids.html', bids=bids, winning_bids=winning_bids)

@app.route('/auction/<int:product_id>/end', methods=['POST'])
@login_required
def end_auction(product_id):
    """Manually end an auction (seller only)"""
    product = Product.query.get(product_id)
    user_id = session.get('user_id')
    
    if not product or not product.is_auction:
        flash("Invalid auction.", "danger")
        return redirect(url_for('my_listings'))
    
    if product.seller_id != user_id:
        flash("You can only end your own auctions.", "danger")
        return redirect(url_for('product_detail', product_id=product_id))
    
    if product.auction_end <= datetime.utcnow():
        flash("This auction has already ended.", "info")
        return redirect(url_for('product_detail', product_id=product_id))
    
    # End the auction
    product.auction_end = datetime.utcnow()
    db.session.commit()
    
    # Notify winning bidder
    winning_bid = Bid.query.filter_by(product_id=product_id, is_winning=1).first()
    if winning_bid:
        create_notification(
            winning_bid.user_id,
            f"Congratulations! You won the auction for {product.title} at ${winning_bid.bid_amount:.2f}",
            url_for('product_detail', product_id=product_id)
        )
    
    flash("Auction ended successfully.", "success")
    return redirect(url_for('product_detail', product_id=product_id))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# --- Delete product route: allows seller or admin to delete a product ---
@app.route('/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    # Only allow seller or admin to delete
    if not user or (product.seller_id != user_id and not user.is_admin):
        flash('You do not have permission to delete this product.')
        return redirect(url_for('my_listings'))
    try:
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully.')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting product.')
    return redirect(url_for('my_listings'))

if __name__ == '__main__':
    app.run(debug=True)

