#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.bybit_client import BybitClient
from config import API_KEY, API_SECRET, USE_TESTNET

def test_5usd_minimum():
    """Test if $5 minimum order value for API trading is the issue"""
    print("=== Testing $5+ Order Values for SOLUSDT (API Minimum) ===")
    
    try:
        # Initialize client
        client = BybitClient(API_KEY, API_SECRET, USE_TESTNET)
        symbol = 'SOLUSDT'
        
        # Get current price
        tickers = client.get_tickers(category='spot', symbol=symbol)
        if not tickers:
            print(f"No ticker data found for {symbol}")
            return
        
        current_price = float(tickers[0]['lastPrice'])
        print(f"Current price: {current_price}")
        
        # Get instrument info
        instruments_list = client.get_instruments_info(category='spot', symbol=symbol)
        if not instruments_list:
            print(f"No instrument info found for {symbol}")
            return
        
        instrument = instruments_list[0]
        lot_size_filter = instrument.get('lotSizeFilter', {})
        base_precision = lot_size_filter.get('basePrecision', '0.001')
        precision_decimals = len(base_precision.split('.')[-1]) if '.' in base_precision else 0
        
        # Test order values starting from $5 (new API minimum)
        test_values = [5.01, 6, 7, 8, 9, 10, 15, 20]
        
        for order_value in test_values:
            print(f"\n--- Testing ${order_value} order ---")
            
            # Calculate quantity
            qty = order_value / current_price
            qty = round(qty, precision_decimals)
            final_order_value = qty * current_price
            
            print(f"Qty: {qty}")
            print(f"Final order value: ${final_order_value:.2f}")
            
            # Check if order value is >= $5
            if final_order_value < 5.0:
                print(f"⚠️  Order value ${final_order_value:.2f} is below $5 API minimum")
                continue
            
            try:
                order_result = client.place_order(
                    category='spot',
                    symbol=symbol,
                    side='Buy',
                    order_type='Market',
                    qty=str(qty)
                )
                
                if order_result.get('retCode') == 0:
                    print(f"✅ ${order_value} order SUCCESS!")
                    print(f"Order ID: {order_result.get('result', {}).get('orderId', 'N/A')}")
                    print("🎉 Found working order size! API minimum is indeed $5 for testnet.")
                    break  # Stop at first successful order
                else:
                    print(f"❌ ${order_value} order FAILED: {order_result.get('retMsg', 'Unknown error')}")
                    
            except Exception as e:
                print(f"❌ ${order_value} order EXCEPTION: {e}")
        
        print(f"\n=== Test completed ===")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_5usd_minimum()