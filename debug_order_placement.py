#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.bybit_client import BybitClient
from config import API_KEY, API_SECRET, USE_TESTNET

def debug_order_placement():
    """Debug order placement with exact parameters from the program"""
    
    # Initialize client
    client = BybitClient(API_KEY, API_SECRET, testnet=USE_TESTNET)
    
    # Test SOLUSDT order with parameters from logs
    symbol = "SOLUSDT"
    price = 259.59  # From recent logs
    
    print(f"=== Debugging {symbol} Order Placement ===")
    
    # Get instrument info
    try:
        instruments_list = client.get_instruments_info(category='spot', symbol=symbol)
        if not instruments_list:
            print(f"No instrument info found for {symbol}")
            return
        
        instrument = instruments_list[0]
        print(f"Instrument info: {instrument}")
        
        # Calculate quantity like the program does
        order_value = 50.0  # Same as max_trade_amount in config
        
        # Get current price first
        tickers = client.get_tickers(category='spot', symbol=symbol)
        if not tickers:
            print(f"No ticker data found for {symbol}")
            return
        
        current_price = float(tickers[0]['lastPrice'])
        print(f"Current price: {current_price}")
        
        # Extract precision and limits from nested structure
        lot_size_filter = instrument.get('lotSizeFilter', {})
        price_filter = instrument.get('priceFilter', {})
        
        min_order_qty = float(lot_size_filter.get('minOrderQty', '0'))
        max_order_qty = float(lot_size_filter.get('maxOrderQty', '0'))
        base_precision = lot_size_filter.get('basePrecision', '0.001')
        
        min_order_amt = float(lot_size_filter.get('minOrderAmt', '0'))
        max_order_amt = float(lot_size_filter.get('maxOrderAmt', '0'))
        
        tick_size = float(price_filter.get('tickSize', '0.01'))
        
        print(f"Min order qty: {min_order_qty}")
        print(f"Max order qty: {max_order_qty}")
        print(f"Base precision: {base_precision}")
        print(f"Min order amount: ${min_order_amt}")
        print(f"Max order amount: ${max_order_amt}")
        print(f"Tick size: {tick_size}")
        
        # Calculate quantity
        qty = order_value / current_price
        
        # Round quantity to proper precision (using base_precision)
        precision_decimals = len(base_precision.split('.')[-1]) if '.' in base_precision else 0
        qty = round(qty, precision_decimals)
        
        final_order_value = qty * current_price
        
        print(f"\nCalculated qty: {qty}")
        print(f"Final order value: ${final_order_value:.2f}")
        
        # Check if values meet requirements
        print(f"Qty >= min_order_qty: {qty >= min_order_qty} ({qty} >= {min_order_qty})")
        print(f"Final value >= min_order_amt: {final_order_value >= min_order_amt} (${final_order_value:.2f} >= ${min_order_amt})")
        
        # Try to place the order
        print(f"\n=== Attempting to place market buy order ===")
        print(f"Symbol: {symbol}")
        print(f"Qty: {qty}")
        print(f"Order value: ${final_order_value:.2f}")
        
        try:
            order_result = client.place_order(
                category='spot',
                symbol=symbol,
                side='Buy',
                order_type='Market',
                qty=str(qty)
            )
            print(f"Order result: {order_result}")
            
            if order_result.get('retCode') == 0:
                print("✅ Order placed successfully!")
            else:
                print(f"❌ Order failed: {order_result.get('retMsg', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Exception during order placement: {e}")
            
            # Try with slightly larger quantity
            print(f"\n=== Trying with slightly larger quantity ===")
            qty_larger = qty * 1.05  # 5% larger
            qty_larger = round(qty_larger, precision_decimals)
            
            final_order_value_larger = qty_larger * current_price
            print(f"Larger qty: {qty_larger}")
            print(f"Larger order value: ${final_order_value_larger:.2f}")
            
            try:
                order_result = client.place_order(
                    category='spot',
                    symbol=symbol,
                    side='Buy',
                    order_type='Market',
                    qty=str(qty_larger)
                )
                print(f"Order result with larger qty: {order_result}")
                
                if order_result.get('retCode') == 0:
                    print("✅ Order with larger quantity placed successfully!")
                else:
                    print(f"❌ Order with larger quantity also failed: {order_result.get('retMsg', 'Unknown error')}")
                    
            except Exception as e2:
                print(f"❌ Exception with larger quantity: {e2}")
        
    except Exception as e:
        print(f"Error during debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_order_placement()