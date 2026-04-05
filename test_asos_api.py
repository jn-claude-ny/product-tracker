#!/usr/bin/env python3
"""Test script to debug ASOS API access"""
import requests
import json

def test_asos_api():
    """Test ASOS search API with different header configurations"""
    
    url = "https://www.asos.com/api/product/search/v2/categories/4209"
    params = {
        'offset': 0,
        'limit': 72,
        'store': 'US',
        'country': 'US',
        'currency': 'USD',
        'lang': 'en-US'
    }
    
    # Test 1: Minimal headers
    print("=" * 60)
    print("Test 1: Minimal headers")
    print("=" * 60)
    headers1 = {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers1, timeout=60)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            products = data.get('products', [])
            print(f"✅ Success! Found {len(products)} products")
            if products:
                print(f"First product: {products[0].get('name', 'N/A')}")
        else:
            print(f"❌ Failed: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()
    
    # Test 2: Full browser headers
    print("=" * 60)
    print("Test 2: Full browser headers")
    print("=" * 60)
    headers2 = {
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.asos.com/men/',
        'Origin': 'https://www.asos.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'Connection': 'keep-alive'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers2, timeout=60)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            products = data.get('products', [])
            print(f"✅ Success! Found {len(products)} products")
            if products:
                print(f"First product: {products[0].get('name', 'N/A')}")
                print(f"Product ID: {products[0].get('id', 'N/A')}")
                print(f"Brand: {products[0].get('brandName', 'N/A')}")
        else:
            print(f"❌ Failed: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()
    
    # Test 3: With session
    print("=" * 60)
    print("Test 3: Using session with cookies")
    print("=" * 60)
    session = requests.Session()
    
    # First visit the homepage to get cookies
    try:
        print("Visiting homepage first...")
        homepage = session.get('https://www.asos.com/', timeout=30)
        print(f"Homepage status: {homepage.status_code}")
        print(f"Cookies received: {len(session.cookies)}")
        
        # Now try the API
        session.headers.update(headers2)
        response = session.get(url, params=params, timeout=60)
        print(f"API Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            products = data.get('products', [])
            print(f"✅ Success! Found {len(products)} products")
            if products:
                print(f"First product: {products[0].get('name', 'N/A')}")
        else:
            print(f"❌ Failed: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    test_asos_api()
