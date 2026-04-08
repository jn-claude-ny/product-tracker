import asyncio
import zendriver as zd
import json
import base64
from zendriver.cdp.network import get_response_body

proxies = {
    "server": "http://brd.superproxy.io:33335",
    "username": "brd-customer-hl_752541f5-zone-champs_residential_proxy1",
    "password": "zk7h5o7vxvt3",
}

async def extract_api_data():
    browser = await zd.start(headless=True,proxy=proxies, user_data_dir=r"D:\AI\product-tracker\app\scraping\champ_data")
    tab = await browser.get("about:blank")
    
    try:
        # Establish session
        print("Establishing session...")
        await tab.get("https://www.champssports.com")
        await asyncio.sleep(3)
        
        # # Load the category page
        print("Loading category page...")
        await tab.get("https://www.champssports.com/category/mens/shoes.html")
        await asyncio.sleep(5)  # Let initial API call complete

        all_products = []
        
        # Loop through pages
        for page_num in range(5):  # First 5 pages
            print(f"\n{'='*50}")
            print(f"Processing page {page_num + 1}")
            
            # Click Next to trigger the API call (even for first page, we need to get current data)
            # But for page 1, the data is already there, so we need to extract it first
            if page_num == 0:
                # For first page, we need to capture the already-loaded data
                print("Extracting first page data from network logs...")
                # Alternative approach: Use CDP to get all network responses
                # But for now, let's click something that triggers a refresh? Or we can intercept the initial load
                
                # Better: Click page 1 button to trigger the API call
                print("Clicking page 1 to trigger API...")
                page1_button = await tab.find("a[aria-label='Go to next page']")
                if not page1_button:
                    page1_button = await tab.find("a:has-text('1')")
                
                if page1_button:
                    async with tab.expect_response(".*zgw/search-core/products/v3/search.*") as response_expectation:
                        await page1_button.click()
                        print("Waiting for API response...")
                        await asyncio.sleep(5)
                        response = await response_expectation.value
                else:
                    print("No page 1 button found, trying to refresh...")
                    await tab.reload()
                    await asyncio.sleep(5)
                    continue
            else:
                # For subsequent pages, click Next
                print("Looking for Next link...")
                next_link = await tab.find("a[aria-label='Go to next page']")
                if not next_link:
                    print("No Next link found - breaking")
                    break
                
                async with tab.expect_response(".*zgw/search-core/products/v3/search.*") as response_expectation:
                    print("Clicking Next link...")
                    await next_link.click()
                    print("Waiting for API response...")
                    await asyncio.sleep(5)
                    response = await response_expectation.value
            
            # Get the response body
            try:
                print(f"Getting response body...")
                body, is_base64 = await tab.send(get_response_body(request_id=response.request_id))

                
                if is_base64:
                    body = base64.b64decode(body).decode('utf-8')
                
                data = json.loads(body)
                
                if data.get('products'):
                    products_count = len(data['products'])
                    all_products.extend(data['products'])
                    print(f"✓ Found {products_count} products")
                    print(f"  Total products available: {data.get('totalResults', 'N/A')}")
                    print(f"  Current page: {data.get('currentPage', 'N/A')}")
                else:
                    print(f"✗ No products in response")
                    print(f"  Response keys: {list(data.keys())}")
                    break
                    
            except json.JSONDecodeError as e:
                print(f"✗ JSON decode error: {e}")
                print(f"  Response preview: {body[:200] if body else 'Empty'}")
                break
            except Exception as e:
                print(f"✗ Error getting response: {e}")
                break
            
            # Small delay between pages
            await asyncio.sleep(2)
        
        print(f"\n{'='*50}")
        print(f"Total products extracted: {len(all_products)}")
        
        if all_products:
            # Save to file
            output = {
                "products": all_products,
                "total": len(all_products),
                "timestamp": asyncio.get_event_loop().time()
            }
            
            filename = "champs_data.json"
            with open(filename, "w") as f:
                json.dump(output, f, indent=2)
            
            print(f"\n✓ Data saved to {filename}")
            
            # Show sample
            if all_products:
                print(f"\nSample product (first):")
                sample = all_products[0]
                for key in list(sample.keys())[:10]:
                    value = str(sample[key])[:100]
                    print(f"  {key}: {value}")
        else:
            print("\n✗ No products captured.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await browser.stop()

if __name__ == "__main__":
    asyncio.run(extract_api_data())