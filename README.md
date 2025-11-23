# Sailor's Bay Marketplace

A modern, mobile-friendly marketplace web app for buying, selling, and bidding on products and auctions.

## Features
- Flask backend with Jinja2 templates for dynamic rendering
- Bootstrap 5 and custom CSS for responsive, modern UI
- Light and dark mode support with seamless switching
- Product browsing with advanced filters (price, rating, availability, auction-only)
- Currency selector for international users
- User features: favorites, cart, bidding, seller dashboard, profile management
- Auction system integrated into product listings
- Admin dashboard for managing users, products, and orders
- Robust error handling and flexible template logic

## Structure
```
app.py                # Main Flask app and routes
models.py             # Database models
setup_db.py           # Database setup script
requirements.txt      # Python dependencies
static/               # CSS, JS, images, and uploads
  js/theme.js         # Theme and dark mode logic
  ...
templates/            # Jinja2 HTML templates
  products.html       # Product browse page
  navbar.html         # Navigation bar
  ...
```

## Setup
1. Install Python 3.10+
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Set up the database:
   ```
   python setup_db.py
   ```
5. Run the app:
   ```
   python app.py
   ```

## Usage
- Register or log in to access user features
- Browse products, filter listings, and switch currency
- Add products to favorites or cart
- Place bids on auction items
- Sellers can manage listings and profile
- Admins can manage users, products, and orders

## Code Highlights
- Modular structure: separate files for models, routes, templates, and static assets
- Clean separation of backend logic, UI, and interactivity
- Robust template logic for handling both dicts and model objects
- Responsive design and theme support for all major pages

## License
MIT
