#!/usr/bin/env python3
"""Test script to manually insert a product and verify database schema"""
from app import create_app
from app.models.product import Product
from app.extensions import db
from datetime import datetime

def test_product_insert():
    app = create_app()
    
    with app.app_context():
        print("Testing product insertion...")
        print("-" * 60)
        
        # Create a minimal product with only required fields
        test_product = Product(
            website_id=3,  # WSS
            url='https://test.com/product',
            sku='TEST123',
            title='Test Product',
            brand='Test Brand',
            image='https://test.com/image.jpg',
            gender='men',
            category='shoes',
            color='black',
            price_current=99.99,
            currency='USD',
            is_on_sale=False,
            is_new=True,
            categories=['shoes', 'sneakers'],
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        try:
            print(f"Adding product: {test_product.title}")
            db.session.add(test_product)
            db.session.commit()
            print(f"✅ SUCCESS! Product saved with ID: {test_product.id}")
            
            # Verify it's in the database
            saved = Product.query.filter_by(sku='TEST123').first()
            if saved:
                print(f"✅ VERIFIED! Product found in database: {saved.title}")
            else:
                print("❌ ERROR! Product not found after save")
                
        except Exception as e:
            print(f"❌ ERROR! Failed to save product: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    test_product_insert()
