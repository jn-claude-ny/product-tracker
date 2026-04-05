#!/usr/bin/env python3
"""Test script to verify Bazaarvoice API integration"""
import requests
import json

def test_bazaarvoice_api():
    """Test fetching product details from Bazaarvoice API"""
    
    # Test product ID from the error log
    product_id = "7064569577527"
    
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
    
    print(f"Testing Bazaarvoice API for product: {product_id}")
    print(f"URL: {url}")
    print(f"Params: {params}")
    print(f"Headers: {headers}")
    print("-" * 60)
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Length: {len(response.text)} bytes")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print("-" * 60)
        
        if response.status_code == 200:
            if response.text and response.text.strip():
                data = response.json()
                print("✅ JSON parsed successfully!")
                print(f"Response structure: {list(data.keys())}")
                
                # Check for 'response' wrapper
                if 'response' in data:
                    print("Found 'response' wrapper")
                    response_data = data.get('response', {})
                    results = response_data.get('Results', [])
                    print(f"Results count: {len(results)}")
                    
                    if results:
                        product = results[0]
                        print(f"Product Name: {product.get('Name')}")
                        print(f"Product ID: {product.get('Id')}")
                        print(f"Brand: {product.get('Brand', {}).get('Name')}")
                        print(f"Description length: {len(product.get('Description', ''))}")
                else:
                    print("No 'response' wrapper found")
                    results = data.get('Results', [])
                    print(f"Direct Results count: {len(results)}")
            else:
                print("❌ Empty response body")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode failed: {e}")
        print(f"Response text: {response.text[:500]}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == '__main__':
    test_bazaarvoice_api()
