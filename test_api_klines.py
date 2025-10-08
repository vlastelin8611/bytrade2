#!/usr/bin/env python3
"""
Test script to check API klines with different categories
"""

import sys
import os

# Add project modules to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.api.bybit_client import BybitClient
    from config import get_api_credentials
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

def test_klines_categories():
    """Test different categories for klines"""
    try:
        # Load API credentials
        api_creds = get_api_credentials()
        client = BybitClient(api_creds['api_key'], api_creds['api_secret'])
        
        # Test symbols and categories
        test_cases = [
            ('BTCUSDT', 'spot'),
            ('BTCUSDT', 'linear'),
            ('BTCUSDT', 'inverse'),
            ('ETHUSDT', 'spot'),
            ('ETHUSDT', 'linear'),
        ]
        
        for symbol, category in test_cases:
            print(f"\n=== Testing {symbol} with category '{category}' ===")
            
            try:
                response = client.get_klines(category, symbol, '4h', 10)
                
                if response and 'result' in response and 'list' in response['result']:
                    klines = response['result']['list']
                    print(f"✅ Success: Got {len(klines)} klines")
                    
                    if klines:
                        # Show first kline
                        first_kline = klines[0]
                        print(f"   First kline: {first_kline}")
                        
                        # Analyze price changes
                        if len(klines) >= 2:
                            changes = []
                            for i in range(1, min(5, len(klines))):
                                prev_close = float(klines[i]['4'])  # close price is at index 4
                                curr_close = float(klines[i-1]['4'])  # klines are in reverse order
                                change = (curr_close - prev_close) / prev_close
                                changes.append(change)
                                print(f"   Change {i}: {change:.6f} ({change*100:.4f}%)")
                            
                            if changes:
                                avg_abs_change = sum(abs(c) for c in changes) / len(changes)
                                print(f"   Average absolute change: {avg_abs_change:.6f} ({avg_abs_change*100:.4f}%)")
                else:
                    print(f"❌ No data in response: {response}")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
        
    except Exception as e:
        print(f"General error: {e}")

if __name__ == "__main__":
    test_klines_categories()