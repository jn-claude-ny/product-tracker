#!/usr/bin/env python3
"""Test script to check why certain products fail"""
import requests
import json

def test_product(product_id):
    """Test fetching a specific product from Bazaarvoice API"""
    
    url = "https://apps.bazaarvoice.com/bfd/v1/clients/wss/api-products/cv2/resources/data/products.json"
    
    params = {
        'locale': 'en_US',
        'allowMissing': 'true',
        'apiVersion': '5.4',
        'filter': f'id:{product_id}'
    }
    
    headers = {
        'Accept': 'application/json',
        'bv-bfd-token': '18656,main_site,en_US',
        'Origin': 'https://www.shopwss.com'
    }
    
    print(f"Testing product: {product_id}")
    print("-" * 60)
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        
        print(f"Status: {response.status_code}")
        print(f"Content-Length: {len(response.text)}")
        print(f"Response text: '{response.text[:200]}'")
        print("-" * 60)
        
        if response.text and response.text.strip():
            data = response.json()
            print(f"✅ JSON parsed")
            print(f"Keys: {list(data.keys())}")
            
            if 'response' in data:
                resp = data['response']
                if resp is None:
                    print("⚠️  'response' is None")
                else:
                    results = resp.get('Results', [])
                    print(f"Results: {len(results)}")
        else:
            print("❌ Empty response")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    print()

if __name__ == '__main__':
    # Test the failing products from the logs
    failing_products = [
        '7132459401271',
        '8903944044674',
        '8904064172162',
        '8904017674370'
    ]
    
    for pid in failing_products:
        test_product(pid)
