#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.bybit_client import BybitClient
from config import API_KEY, API_SECRET, USE_TESTNET

def test_different_order_sizes():
    """Test different order sizes to find the actual minimum"""
    print("=== Testing Different Order Sizes for SOLUSDT ===")
    
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
        
        # Test different order values
        test_values = [1, 5, 10, 20, 50, 100, 200]
        
        for order_value in test_values:
            print(f"\n--- Testing ${order_value} order ---")
            
            # Calculate quantity
            qty = order_value / current_price
            qty = round(qty, precision_decimals)
            final_order_value = qty * current_price
            
            print(f"Qty: {qty}")
            print(f"Final order value: ${final_order_value:.2f}")
            
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
    test_different_order_sizes()