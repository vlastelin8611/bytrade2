#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for real SOLUSDT order placement
"""
import os
import sys
from pybit.unified_trading import HTTP

# Загружаем API ключи
keys_file = os.path.join(os.path.dirname(__file__), 'keys')
if os.path.exists(keys_file):
    with open(keys_file, 'r') as f:
        lines = f.read().strip().split('\n')
        api_key = lines[0].strip()
        api_secret = lines[1].strip()
else:
    print("❌ Файл с ключами не найден")
    sys.exit(1)

# Инициализируем клиент
client = HTTP(
    testnet=True,
    api_key=api_key,
    api_secret=api_secret,
)

print("Testing real SOLUSDT order placement...")

try:
    # Get current price
    ticker = client.get_tickers(category='spot', symbol='SOLUSDT')
    if ticker['retCode'] == 0:
        price = float(ticker['result']['list'][0]['lastPrice'])
        print(f"Current SOLUSDT price: ${price}")
        
        # Test minimal order for $2
        test_amount = 2.0
        qty = test_amount / price
        qty_rounded = round(qty, 3)  # basePrecision = 0.001
        final_value = qty_rounded * price
        
        print(f"\nTest order:")
        print(f"   Amount: ${test_amount}")
        print(f"   Quantity: {qty_rounded}")
        print(f"   Final value: ${final_value:.2f}")
        
        # Place test order
        print(f"\nPlacing order...")
        order_result = client.place_order(
            category='spot',
            symbol='SOLUSDT',
            side='Buy',
            order_type='Market',
            qty=str(qty_rounded)
        )
        
        print(f"Order result:")
        print(f"   retCode: {order_result.get('retCode')}")
        print(f"   retMsg: {order_result.get('retMsg')}")
        
        if order_result.get('retCode') == 0:
            print(f"   Order placed successfully!")
            order_id = order_result.get('result', {}).get('orderId')
            print(f"   Order ID: {order_id}")
        else:
            print(f"   Order placement failed")
            
except Exception as e:
    print(f"Error: {e}")