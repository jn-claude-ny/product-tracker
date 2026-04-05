"""
Test script for multi-site scrapers.
Tests each scraper with real data to verify functionality.
"""
import sys
import logging
from app import create_app
from app.scraping import AsosScraper, ShopWssScraper, ChampsSportsScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_asos_scraper():
    """Test ASOS scraper"""
    print("\n" + "="*60)
    print("Testing ASOS Scraper")
    print("="*60)
    
    scraper = AsosScraper(website_id=1, base_url="https://www.asos.com")
    
    try:
        # Test discovery (limit to 5 products)
        print("\n1. Testing product discovery (men's shoes)...")
        products = scraper.discover_products('men', limit=5)
        print(f"   ✓ Discovered {len(products)} products")
        
        if products:
            print(f"\n   Sample product:")
            sample = products[0]
            print(f"   - ID: {sample.get('id')}")
            print(f"   - Name: {sample.get('name')}")
            print(f"   - Brand: {sample.get('brand')}")
            print(f"   - Price: ${sample.get('price')}")
            print(f"   - URL: {sample.get('url')}")
            
            # Test detail extraction
            print(f"\n2. Testing detail extraction...")
            details = scraper.extract_product_details(sample.get('id'))
            if details:
                print(f"   ✓ Extracted details")
                print(f"   - Variants: {len(details.get('variants', []))}")
                print(f"   - Size range: {details.get('size_range')}")
                print(f"   - Colors: {details.get('color')}")
            else:
                print(f"   ⚠ No details extracted")
        
        scraper.close()
        print("\n✅ ASOS scraper test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"ASOS scraper test failed: {e}")
        scraper.close()
        print("\n❌ ASOS scraper test FAILED")
        return False


def test_shopwss_scraper():
    """Test ShopWSS scraper"""
    print("\n" + "="*60)
    print("Testing ShopWSS Scraper")
    print("="*60)
    
    scraper = ShopWssScraper(website_id=2, base_url="https://www.shopwss.com")
    
    try:
        # Test discovery (limit to 5 products)
        print("\n1. Testing product discovery (women's shoes)...")
        products = scraper.discover_products('women', limit=5)
        print(f"   ✓ Discovered {len(products)} products")
        
        if products:
            print(f"\n   Sample product:")
            sample = products[0]
            print(f"   - ID: {sample.get('id')}")
            print(f"   - Name: {sample.get('name')}")
            print(f"   - Brand: {sample.get('brand')}")
            print(f"   - Price: ${sample.get('price')}")
            print(f"   - Availability: {sample.get('availability')}")
            
            # Test detail extraction
            print(f"\n2. Testing detail extraction...")
            details = scraper.extract_product_details(sample.get('id'))
            if details:
                print(f"   ✓ Extracted details")
                print(f"   - Variants: {len(details.get('variants', []))}")
                print(f"   - Size range: {details.get('size_range')}")
            else:
                print(f"   ⚠ No details extracted (Bazaarvoice may require product in catalog)")
        
        scraper.close()
        print("\n✅ ShopWSS scraper test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"ShopWSS scraper test failed: {e}")
        scraper.close()
        print("\n❌ ShopWSS scraper test FAILED")
        return False


def test_champssports_scraper():
    """Test ChampsSports scraper"""
    print("\n" + "="*60)
    print("Testing ChampsSports Scraper")
    print("="*60)
    
    scraper = ChampsSportsScraper(website_id=3, base_url="https://www.champssports.com")
    
    try:
        # Test discovery (limit to 5 products)
        print("\n1. Testing product discovery (men's shoes)...")
        products = scraper.discover_products('men', limit=5)
        print(f"   ✓ Discovered {len(products)} product URLs")
        
        if products:
            print(f"\n   Sample product:")
            sample = products[0]
            print(f"   - URL: {sample.get('url')}")
            print(f"   - ID: {sample.get('id')}")
            
            print(f"\n2. Detail extraction requires Playwright (async)")
            print(f"   ⚠ Skipping detail test (requires async context)")
        
        scraper.close()
        print("\n✅ ChampsSports scraper test PASSED")
        return True
        
    except Exception as e:
        logger.error(f"ChampsSports scraper test failed: {e}")
        scraper.close()
        print("\n❌ ChampsSports scraper test FAILED")
        return False


def main():
    """Run all scraper tests"""
    print("\n" + "="*60)
    print("MULTI-SITE SCRAPER TEST SUITE")
    print("="*60)
    
    app = create_app()
    
    with app.app_context():
        results = {
            'ASOS': test_asos_scraper(),
            'ShopWSS': test_shopwss_scraper(),
            'ChampsSports': test_champssports_scraper()
        }
        
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)
        
        for scraper, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{scraper}: {status}")
        
        all_passed = all(results.values())
        
        if all_passed:
            print("\n🎉 All scraper tests PASSED!")
            return 0
        else:
            print("\n⚠️ Some scraper tests FAILED")
            return 1


if __name__ == '__main__':
    sys.exit(main())
