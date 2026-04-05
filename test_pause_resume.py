#!/usr/bin/env python3
"""Test script to verify pause/resume API endpoints"""
import requests
import json

BASE_URL = "http://localhost:8081"

# Login to get token
print("1. Logging in...")
login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": "admin",
    "password": "admin123"
})

if login_response.status_code != 200:
    print(f"❌ Login failed: {login_response.status_code}")
    print(login_response.text)
    exit(1)

token = login_response.json()['access_token']
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}
print("✅ Login successful")

# Get current website state
print("\n2. Getting current website states...")
websites_response = requests.get(f"{BASE_URL}/api/websites", headers=headers)
websites = websites_response.json()

print(f"Found {len(websites)} websites:")
for ws in websites:
    print(f"  - ID {ws['id']}: {ws['name']} | State: {ws.get('crawl_state', 'N/A')} | Crawling: {ws.get('is_crawling', False)}")

# Test with website ID 4 (ASOS - currently crawling)
test_website_id = 4
print(f"\n3. Testing PAUSE on website ID {test_website_id}...")
pause_response = requests.post(
    f"{BASE_URL}/api/websites/{test_website_id}/crawl/pause",
    headers=headers
)

print(f"Status: {pause_response.status_code}")
print(f"Response: {json.dumps(pause_response.json(), indent=2)}")

# Verify state changed
print("\n4. Verifying state after PAUSE...")
website_response = requests.get(f"{BASE_URL}/api/websites/{test_website_id}", headers=headers)
website = website_response.json()
print(f"  State: {website.get('crawl_state')} (expected: paused)")
print(f"  Is Crawling: {website.get('is_crawling')} (expected: False)")

if website.get('crawl_state') == 'paused' and website.get('is_crawling') == False:
    print("✅ PAUSE works correctly!")
else:
    print("❌ PAUSE did not update state correctly")

# Test RESUME
print(f"\n5. Testing RESUME on website ID {test_website_id}...")
resume_response = requests.post(
    f"{BASE_URL}/api/websites/{test_website_id}/crawl/resume",
    headers=headers
)

print(f"Status: {resume_response.status_code}")
print(f"Response: {json.dumps(resume_response.json(), indent=2)}")

# Verify state changed
print("\n6. Verifying state after RESUME...")
website_response = requests.get(f"{BASE_URL}/api/websites/{test_website_id}", headers=headers)
website = website_response.json()
print(f"  State: {website.get('crawl_state')} (expected: crawling)")
print(f"  Is Crawling: {website.get('is_crawling')} (expected: True)")

if website.get('crawl_state') == 'crawling' and website.get('is_crawling') == True:
    print("✅ RESUME works correctly!")
else:
    print("❌ RESUME did not update state correctly")

# Test with website ID 2 (Champs Sports - currently paused)
test_website_id_2 = 2
print(f"\n7. Testing RESUME on already paused website ID {test_website_id_2}...")
resume_response = requests.post(
    f"{BASE_URL}/api/websites/{test_website_id_2}/crawl/resume",
    headers=headers
)

print(f"Status: {resume_response.status_code}")
print(f"Response: {json.dumps(resume_response.json(), indent=2)}")

# Verify
website_response = requests.get(f"{BASE_URL}/api/websites/{test_website_id_2}", headers=headers)
website = website_response.json()
print(f"  State: {website.get('crawl_state')} (expected: crawling)")
print(f"  Is Crawling: {website.get('is_crawling')} (expected: True)")

print("\n8. Final state of all websites:")
websites_response = requests.get(f"{BASE_URL}/api/websites", headers=headers)
websites = websites_response.json()
for ws in websites:
    print(f"  - ID {ws['id']}: {ws['name']} | State: {ws.get('crawl_state', 'N/A')} | Crawling: {ws.get('is_crawling', False)}")

print("\n✅ All tests completed!")
