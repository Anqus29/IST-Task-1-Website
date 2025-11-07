from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import CheckConstraint

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Integer, default=0)
    is_seller = db.Column(db.Integer, default=0)
    is_verified = db.Column(db.Integer, default=0)
    business_name = db.Column(db.String(200))
    seller_description = db.Column(db.Text)
    rating = db.Column(db.Float, default=0.0)
    total_sales = db.Column(db.Integer, default=0)
    profile_picture = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', back_populates='seller', lazy=True, cascade='all, delete-orphan')
    orders_as_buyer = db.relationship('Order', back_populates='buyer', lazy=True, foreign_keys='Order.buyer_id')
    reviews = db.relationship('Review', back_populates='user', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('Favorite', back_populates='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', back_populates='user', lazy=True, cascade='all, delete-orphan')
    addresses = db.relationship('Address', back_populates='user', lazy=True, cascade='all, delete-orphan')
    reset_tokens = db.relationship('PasswordResetToken', back_populates='user', lazy=True, cascade='all, delete-orphan')
    product_reports = db.relationship('ProductReport', back_populates='reporter', lazy=True, foreign_keys='ProductReport.reporter_id')
    product_views = db.relationship('ProductView', back_populates='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'


class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer)
    image_url = db.Column(db.String(500))
    category = db.Column(db.String(100), default='Other')
    condition = db.Column(db.String(50), default='used')
    location = db.Column(db.String(200))
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Auction fields
    is_auction = db.Column(db.Integer, default=0)  # 0 = regular, 1 = auction
    starting_bid = db.Column(db.Float)  # Starting bid price for auctions
    current_bid = db.Column(db.Float)  # Current highest bid
    auction_end = db.Column(db.DateTime)  # When auction ends
    reserve_price = db.Column(db.Float)  # Minimum price seller will accept (optional)
    buy_now_price = db.Column(db.Float)  # Optional "Buy It Now" price
    
    # Relationships
    seller = db.relationship('User', back_populates='products')
    order_items = db.relationship('OrderItem', back_populates='product', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', back_populates='product', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('Favorite', back_populates='product', lazy=True, cascade='all, delete-orphan')
    reports = db.relationship('ProductReport', back_populates='product', lazy=True, cascade='all, delete-orphan')
    views = db.relationship('ProductView', back_populates='product', lazy=True, cascade='all, delete-orphan')
    bids = db.relationship('Bid', back_populates='product', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Product {self.title}>'


class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    buyer_name = db.Column(db.String(200), nullable=False)
    buyer_email = db.Column(db.String(200), nullable=False)
    shipping_address = db.Column(db.Text, nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')
    refund_status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    buyer = db.relationship('User', back_populates='orders_as_buyer', foreign_keys=[buyer_id])
    items = db.relationship('OrderItem', back_populates='order', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Order {self.id}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    
    # Relationships
    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product', back_populates='order_items')
    
    def __repr__(self):
        return f'<OrderItem {self.id}>'


class Review(db.Model):
    __tablename__ = 'reviews'
    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
        db.UniqueConstraint('product_id', 'user_id', name='unique_product_user_review'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200))
    body = db.Column(db.Text)
    seller_response = db.Column(db.Text)
    is_approved = db.Column(db.Integer, default=0, nullable=False)
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', back_populates='reviews')
    user = db.relationship('User', back_populates='reviews')
    
    def __repr__(self):
        return f'<Review {self.id}>'


class Favorite(db.Model):
    __tablename__ = 'favorites'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_id', name='unique_user_product_favorite'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='favorites')
    product = db.relationship('Product', back_populates='favorites')
    
    def __repr__(self):
        return f'<Favorite {self.id}>'


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(500))
    is_read = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='notifications')
    
    def __repr__(self):
        return f'<Notification {self.id}>'


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='reset_tokens')
    
    def __repr__(self):
        return f'<PasswordResetToken {self.id}>'


class ProductReport(db.Model):
    __tablename__ = 'product_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', back_populates='reports')
    reporter = db.relationship('User', back_populates='product_reports', foreign_keys=[reporter_id])
    
    def __repr__(self):
        return f'<ProductReport {self.id}>'


class ProductView(db.Model):
    __tablename__ = 'product_views'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='product_views')
    product = db.relationship('Product', back_populates='views')
    
    def __repr__(self):
        return f'<ProductView {self.id}>'


class Address(db.Model):
    __tablename__ = 'addresses'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'address_text', name='unique_user_address'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    label = db.Column(db.String(100))
    address_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='addresses')
    
    def __repr__(self):
        return f'<Address {self.id}>'


class Bid(db.Model):
    __tablename__ = 'bids'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    bid_amount = db.Column(db.Float, nullable=False)
    is_winning = db.Column(db.Integer, default=0)  # 1 if currently winning bid
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', back_populates='bids')
    bidder = db.relationship('User', foreign_keys=[user_id])
    
    def __repr__(self):
        return f'<Bid {self.id} - ${self.bid_amount}>'
