"""
Test Discord alerts using alert_tasks
Usage: python test_discord_alert.py <discord_webhook_url>
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.product import Product
from app.models.product_snapshot import ProductSnapshot
from app.models.tracked_product import TrackedProduct
from app.models.discord_webhook import DiscordWebhook
from app.models.website import Website
from app.models.user import User
from celery_app.tasks.alert_tasks import send_discord_alert, evaluate_tracked_product_alerts
from datetime import datetime, timedelta
import random

def create_test_data(webhook_url):
    """Create test data for Discord alert testing."""
    app = create_app()
    
    with app.app_context():
        # Create or get test user
        user = User.query.filter_by(email='test@example.com').first()
        if not user:
            from app.services.auth_service import AuthService
            user = AuthService.register_user('test@example.com', 'testpassword123')
            print(f"Created test user: {user.email}")
        else:
            print(f"Using existing user: {user.email}")
        
        # Create or get test website
        website = Website.query.filter_by(url='https://test-example.com').first()
        if not website:
            website = Website(
                user_id=user.id,
                name='Test Website',
                url='https://test-example.com',
                sitemap_url='https://test-example.com/sitemap.xml',
                alert_cooldown_minutes=5
            )
            db.session.add(website)
            db.session.commit()
            print(f"Created test website: {website.name}")
        else:
            print(f"Using existing website: {website.name}")
        
        # Create or get test product
        product = Product.query.filter_by(sku='TEST-SHOE-001').first()
        if not product:
            product = Product(
                website_id=website.id,
                sku='TEST-SHOE-001',
                title='Nike Air Jordan 1 Retro High - Test Shoe',
                brand='Nike',
                url='https://test-example.com/products/nike-air-jordan-1',
                image='https://images.unsplash.com/photo-1549298916-b41d501d3772?w=800',
                price_current=150.00,
                price_previous=180.00,
                currency='USD',
                availability='In Stock',
                gender='men',
                categories=['Shoes', 'Sneakers', 'Basketball']
            )
            db.session.add(product)
            db.session.commit()
            print(f"Created test product: {product.title}")
        else:
            print(f"Using existing product: {product.title}")
        
        # Create product snapshots for price drop scenario
        # Previous snapshot (higher price)
        prev_snapshot = ProductSnapshot.query.filter_by(
            product_id=product.id
        ).order_by(ProductSnapshot.created_at.desc()).offset(1).first()
        
        if not prev_snapshot:
            prev_snapshot = ProductSnapshot(
                product_id=product.id,
                price=180.00,
                currency='USD',
                availability='In Stock',
                title=product.title,
                created_at=datetime.utcnow() - timedelta(hours=1)
            )
            db.session.add(prev_snapshot)
            db.session.commit()
            print(f"Created previous snapshot: ${prev_snapshot.price}")
        
        # Current snapshot (lower price - price drop)
        current_snapshot = ProductSnapshot(
            product_id=product.id,
            price=120.00,  # Price dropped!
            currency='USD',
            availability='In Stock',
            title=product.title
        )
        db.session.add(current_snapshot)
        db.session.commit()
        print(f"Created current snapshot: ${current_snapshot.price}")
        
        # Create tracked product with price direction = 'below'
        tracked = TrackedProduct.query.filter_by(
            user_id=user.id,
            product_id=product.id
        ).first()
        
        if not tracked:
            tracked = TrackedProduct(
                user_id=user.id,
                product_id=product.id,
                priority='high',
                price_direction='below',  # Alert when price goes below
                price_reference=150.00,   # Reference price
                size_filter=['10', '10.5', '11']
            )
            db.session.add(tracked)
            db.session.commit()
            print(f"Created tracked product with price_direction='below', reference=${tracked.price_reference}")
        else:
            print(f"Using existing tracked product")
        
        # Create Discord webhook
        webhook = DiscordWebhook.query.filter_by(
            website_id=website.id,
            webhook_url=webhook_url
        ).first()
        
        if not webhook:
            webhook = DiscordWebhook(
                website_id=website.id,
                webhook_url=webhook_url,
                is_active=True
            )
            db.session.add(webhook)
            db.session.commit()
            print(f"Created Discord webhook")
        else:
            print(f"Using existing webhook")
        
        return {
            'user_id': user.id,
            'website_id': website.id,
            'product_id': product.id,
            'snapshot_id': current_snapshot.id,
            'tracked_id': tracked.id,
            'webhook_id': webhook.id
        }

def test_send_discord_alert_directly(test_data):
    """Test sending Discord alert directly."""
    from app.models.alert import Alert
    
    app = create_app()
    with app.app_context():
        # Create a test alert
        alert = Alert(
            user_id=test_data['user_id'],
            product_id=test_data['product_id'],
            alert_type='price_drop',
            state_hash=f"test_{random.randint(1000, 9999)}"
        )
        db.session.add(alert)
        db.session.commit()
        
        print(f"\n{'='*50}")
        print("Test 1: Direct Discord Alert")
        print(f"{'='*50}")
        print(f"Alert ID: {alert.id}")
        print(f"Alert Type: {alert.alert_type}")
        print(f"Product ID: {alert.product_id}")
        print(f"Sending Discord alert...")
        
        # Send the alert
        result = send_discord_alert.apply_async(args=[alert.id], queue='alert_queue')
        print(f"Task queued: {result.id}")
        print("Check your Discord channel for the alert!")
        
        return alert.id

def test_tracked_product_alert_evaluation(test_data):
    """Test tracked product alert evaluation with price direction."""
    app = create_app()
    
    print(f"\n{'='*50}")
    print("Test 2: Tracked Product Alert Evaluation")
    print(f"{'='*50}")
    print(f"Product ID: {test_data['product_id']}")
    print(f"Snapshot ID: {test_data['snapshot_id']}")
    print(f"Expected: Price drop alert (current price < reference price)")
    print(f"Evaluating alerts...")
    
    # Evaluate alerts
    result = evaluate_tracked_product_alerts.apply_async(
        args=[test_data['product_id'], test_data['snapshot_id']],
        queue='alert_queue'
    )
    
    print(f"Task queued: {result.id}")
    print("Check your Discord channel for price drop alerts!")
    
    return result.id

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_discord_alert.py <discord_webhook_url>")
        print("\nTo get a Discord webhook URL:")
        print("1. In Discord, go to Server Settings > Integrations > Webhooks")
        print("2. Click 'New Webhook' and copy the URL")
        print("\nExample:")
        print("python test_discord_alert.py https://discord.com/api/webhooks/123456789/abcdef...")
        sys.exit(1)
    
    webhook_url = sys.argv[1]
    
    print(f"{'='*60}")
    print("Discord Alert Test Script")
    print(f"{'='*60}")
    print(f"Webhook URL: {webhook_url[:50]}...")
    
    # Create test data
    print(f"\n{'='*50}")
    print("Setting up test data...")
    print(f"{'='*50}")
    
    test_data = create_test_data(webhook_url)
    
    # Run tests
    test_send_discord_alert_directly(test_data)
    test_tracked_product_alert_evaluation(test_data)
    
    print(f"\n{'='*60}")
    print("Tests completed!")
    print(f"{'='*60}")
    print("\nNext steps:")
    print("1. Check your Discord channel for the test alerts")
    print("2. Verify the embed shows product details correctly")
    print("3. Check the Celery worker logs for any errors")

if __name__ == '__main__':
    main()
