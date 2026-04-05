#!/usr/bin/env python3
"""Test script to trigger crawl and monitor execution"""
import sys
import time
from app import create_app
from app.models.website import Website
from celery_app.tasks.crawl_tasks import crawl_website

def test_crawl(website_id):
    app = create_app()
    
    with app.app_context():
        website = Website.query.get(website_id)
        if not website:
            print(f"Website {website_id} not found")
            return
        
        print(f"Testing crawl for: {website.name} ({website.base_url})")
        print(f"Website ID: {website_id}")
        print("-" * 60)
        
        # Trigger crawl task
        print("Triggering crawl task...")
        result = crawl_website.apply_async(args=[website_id, False], queue='crawl_queue')
        
        print(f"Task ID: {result.id}")
        print(f"Task state: {result.state}")
        print("-" * 60)
        
        # Wait for result
        print("Waiting for task to complete (max 30 seconds)...")
        try:
            task_result = result.get(timeout=30)
            print(f"Task completed successfully!")
            print(f"Result: {task_result}")
        except Exception as e:
            print(f"Task failed or timed out: {e}")
            print(f"Final state: {result.state}")

if __name__ == '__main__':
    website_id = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    test_crawl(website_id)
