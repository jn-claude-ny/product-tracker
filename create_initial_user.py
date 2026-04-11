#!/usr/bin/env python3
"""
Script to create initial user and seed default websites
"""
import os
import sys
from app import create_app
from app.extensions import db
from app.services.auth_service import AuthService
from app.services.website_service import WebsiteService


def main():
    """Create initial user and seed websites"""
    app = create_app()
    
    with app.app_context():
        # Create user
        email = "resell951@thatdev.com"
        password = "Resell@951"
        
        print(f"Creating user: {email}")
        user = AuthService.register_user(email, password)
        print(f"✅ User created with ID: {user.id}")
        
        # Seed default websites
        print("Seeding default websites...")
        websites = WebsiteService.seed_default_websites(user.id)
        print(f"✅ Seeded {len(websites)} websites:")
        for website in websites:
            print(f"  - {website.name}: {website.base_url}")
        
        print("\n🎉 Initial setup complete!")
        print(f"Login credentials: {email} / {password}")


if __name__ == "__main__":
    main()
