import asyncio
import zendriver as zd

from zendriver.cdp.network import get_response_body

proxies = {
    "server": "http://brd.superproxy.io:33335",
    "username": "brd-customer-hl_752541f5-zone-champs_residential_proxy1",
    "password": "zk7h5o7vxvt3",
}

async def main():
    browser = await zd.start(
        headless=True, 
        proxy = proxies,
        user_data_dir= r"D:\AI\Freelance\champssports\phase_2\zendriver\champ_data"
        )
    tab = await browser.get("about:blank")
    
    async with tab.expect_response(".*zgw/product-core/v1/pdp/sku.*") as response_expectation:

        await tab.get("https://www.champssports.com/product/new-balance-574-mens/ML574EVE.html")
        print("Waiting for API response...")

        await asyncio.sleep(0.5)

        response = await response_expectation.value

    # Get the response body
    try:
        print(f"Getting response body...")
        body, is_base64 = await tab.send(get_response_body(request_id=response.request_id))
        print(body)
        # TO DO
        # figure out the way to transform the body in a json/object you can use to extract the data      
            
    except Exception as e:
        print(f"✗ Error getting response: {e}")
        

    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())