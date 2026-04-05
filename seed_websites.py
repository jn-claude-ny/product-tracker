#!/usr/bin/env python3
"""
Seed script to create the 3 predefined websites
"""

import sys
import os
from app import create_app, db
from app.models.website import Website

def seed_websites():
    app = create_app()
    
    with app.app_context():
        # Define the 3 websites
        websites_data = [
            {
                'name': 'Champs Sports',
                'base_url': 'https://www.champssports.com/',
                'sitemap_url': 'https://www.champssports.com/sitemap.xml',
                'allowed_domains': ['champssports.com'],
                'use_playwright': False,
                'scrape_delay_seconds': 3.0,
                'randomize_delay': True,
                'alert_cooldown_minutes': 60
            },
            {
                'name': 'WSS',
                'base_url': 'https://www.shopwss.com/',
                'sitemap_url': 'https://www.shopwss.com/sitemap.xml',
                'allowed_domains': ['shopwss.com'],
                'use_playwright': False,
                'scrape_delay_seconds': 3.0,
                'randomize_delay': True,
                'alert_cooldown_minutes': 60
            },
            {
                'name': 'ASOS',
                'base_url': 'https://www.asos.com/',
                'sitemap_url': 'https://www.asos.com/sitemap.xml',
                'allowed_domains': ['asos.com'],
                'use_playwright': False,
                'scrape_delay_seconds': 3.0,
                'randomize_delay': True,
                'alert_cooldown_minutes': 60
            }
        ]
        
        # Get first user (assuming user_id = 1 for now)
        user_id = 1
        
        for website_data in websites_data:
            # Check if website already exists
            existing = Website.query.filter_by(
                user_id=user_id,
                base_url=website_data['base_url']
            ).first()
            
            if existing:
                print(f"Website {website_data['name']} already exists, skipping...")
                continue
            
            # Create new website
            website = Website(user_id=user_id, **website_data)
            db.session.add(website)
            print(f"Created website: {website_data['name']}")
        
        try:
            db.session.commit()
            print("✅ Websites seeded successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding websites: {e}")
            sys.exit(1)

if __name__ == '__main__':
    seed_websites()
