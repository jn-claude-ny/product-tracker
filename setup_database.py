#!/usr/bin/env python3
"""
Direct database setup script using SQLAlchemy db.create_all()
"""
import os
import sys

# Add app directory to path
sys.path.insert(0, '/app')

def setup_database():
    """Create all tables using SQLAlchemy's db.create_all()"""
    from app import create_app
    from app.extensions import db
    
    print("Setting up database with SQLAlchemy...")
    
    app = create_app()
    
    with app.app_context():
        # Create all tables from models
        db.create_all()
        
        # Mark alembic as complete
        from sqlalchemy import text
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            );
        """))
        db.session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('009') ON CONFLICT (version_num) DO NOTHING;"))
        db.session.commit()
    
    print("✅ Database setup complete!")
    print("📊 All tables created from SQLAlchemy models")
    print("🔗 Indexes created automatically")
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
