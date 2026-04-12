#!/usr/bin/env python3
"""
Direct database setup script - no Alembic needed
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/product_tracker')

def setup_database():
    """Create all tables directly without Alembic"""
    engine = create_engine(DATABASE_URL)
    
    print("Setting up database...")
    
    # Create schema and tables
    with engine.connect() as conn:
        # Users table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                role VARCHAR(50) DEFAULT 'user'
            );
        """))
        
        # Websites table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS websites (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                base_url VARCHAR(500) NOT NULL,
                allowed_domains TEXT,
                sitemap_url VARCHAR(500),
                use_playwright BOOLEAN DEFAULT FALSE,
                scrape_delay_seconds DECIMAL(5,2) DEFAULT 2.0,
                randomize_delay BOOLEAN DEFAULT TRUE,
                alert_cooldown_minutes INTEGER DEFAULT 60,
                cron_schedule VARCHAR(100) DEFAULT '0 */6 * * * *',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                discord_webhook_url VARCHAR(500),
                crawl_progress INTEGER DEFAULT 0
            );
        """))
        
        # Categories table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                url VARCHAR(500),
                selector VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # Products table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                website_id INTEGER REFERENCES websites(id) ON DELETE CASCADE,
                category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                sku VARCHAR(255),
                name VARCHAR(500) NOT NULL,
                url VARCHAR(1000),
                image_url VARCHAR(1000),
                price DECIMAL(10,2),
                original_price DECIMAL(10,2),
                description TEXT,
                gender VARCHAR(20),
                color VARCHAR(100),
                size_range VARCHAR(100),
                price_current DECIMAL(10,2),
                sale_price DECIMAL(10,2),
                is_new BOOLEAN DEFAULT FALSE,
                is_on_sale BOOLEAN DEFAULT FALSE,
                availability VARCHAR(50),
                variants_data JSON,
                available BOOLEAN,
                inventory_level INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # Product variants table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS product_variants (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                sku VARCHAR(255),
                size VARCHAR(50),
                color VARCHAR(100),
                price DECIMAL(10,2),
                availability VARCHAR(50),
                available BOOLEAN,
                inventory_level INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # Other required tables
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS selectors (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                css_selector VARCHAR(1000) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tracking_rules (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                website_id INTEGER REFERENCES websites(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                conditions JSON,
                actions JSON,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS discord_webhooks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                url VARCHAR(500) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS product_snapshots (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                price DECIMAL(10,2),
                availability VARCHAR(50),
                available BOOLEAN,
                inventory_level INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                alert_type VARCHAR(50) NOT NULL,
                message TEXT,
                is_sent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # Create indexes
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_websites_user_id ON websites(user_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_website_id ON products(website_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_product_variants_product_id ON product_variants(product_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_product_variants_sku ON product_variants(sku);"))
        
        # Create alembic version table to mark migration as complete
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            );
        """))
        
        # Mark migration as complete
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('009') ON CONFLICT (version_num) DO NOTHING;"))
        
        conn.commit()
    
    print("✅ Database setup complete!")
    print("📊 Tables created: users, websites, categories, products, product_variants, selectors, tracking_rules, discord_webhooks, product_snapshots, alerts")
    print("🔗 Indexes created for performance")
    print("🚀 Ready for user creation!")


if __name__ == "__main__":
    setup_database()
    
    # Create Flask app and seed user/websites
    print("\nCreating Flask app and seeding user...")
    
    # Add app directory to path
    sys.path.insert(0, '/app')
    
    from app import create_app
    from app.extensions import db
    from app.services.auth_service import AuthService
    from app.services.website_service import WebsiteService
    
    app = create_app()
    
    with app.app_context():
        # Create user
        email = "resell951@thatdev.com"
        password = "Resell@951"
        
        print(f"Creating user: {email}")
        try:
            user = AuthService.register_user(email, password)
            print(f"✅ User created with ID: {user.id}")
            
            # Seed default websites
            print("Seeding default websites...")
            websites = WebsiteService.seed_default_websites(user.id)
            print(f"✅ Seeded {len(websites)} websites:")
            for website in websites:
                print(f"  - {website.name}: {website.base_url}")
            
            print(f"\n🎉 Setup complete!")
            print(f"🔐 Login credentials: {email} / {password}")
            print(f"🌐 Ready to test ASOS scraping!")
            
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            db.session.rollback()
