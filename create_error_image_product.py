from app import app, db
from models import Product

with app.app_context():
    error_product = Product(
        title='Error Image',
        description='This product is used as a placeholder for missing or unassigned images.',
        image_url='/static/img/error.jpg',
        price=0.0
    )
    db.session.add(error_product)
    db.session.commit()
    print(f'Created Error Image product with ID: {error_product.id}')
