#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check current balance and trading limits for debugging order issues
"""
import os
import sys
from pybit.unified_trading import HTTP
from config import API_KEY, API_SECRET, USE_TESTNET

def main():
    # Get API credentials from config
    api_key = API_KEY
    api_secret = API_SECRET
    
    if not api_key or not api_secret:
        print("Error: API keys not found in config.py")
        print("Please set API_KEY and API_SECRET in config.py")
        return

    # Initialize client
    client = HTTP(
        testnet=USE_TESTNET,
        api_key=api_key,
        api_secret=api_secret
    )

    print("Checking current balance and order limits...")

    try:
        # Get wallet balance (use UNIFIED for testnet)
        balance_result = client.get_wallet_balance(accountType='UNIFIED')
        if balance_result['retCode'] == 0:
            coins = balance_result['result']['list'][0]['coin']
            for coin in coins:
                if coin['coin'] in ['USDT', 'SOL', 'BTC', 'ETH']:
                    print(f"{coin['coin']}: Available = {coin['walletBalance']}, Locked = {coin['locked']}")
        
        # Get instrument info for key symbols
        symbols = ['SOLUSDT', 'BTCUSDT', 'ETHUSDT']
        for symbol in symbols:
            instrument_result = client.get_instruments_info(category='spot', symbol=symbol)
            if instrument_result['retCode'] == 0:
                info = instrument_result['result']['list'][0]
                print(f"\n{symbol} limits:")
                print(f"  minOrderQty: {info['lotSizeFilter']['minOrderQty']}")
                print(f"  maxOrderQty: {info['lotSizeFilter']['maxOrderQty']}")
                print(f"  minOrderAmt: {info['lotSizeFilter']['minOrderAmt']}")
                print(f"  maxOrderAmt: {info['lotSizeFilter']['maxOrderAmt']}")
                print(f"  basePrecision: {info['lotSizeFilter']['basePrecision']}")
                print(f"  quotePrecision: {info['lotSizeFilter']['quotePrecision']}")
        
        # Get current prices
        print("\nCurrent prices:")
        for symbol in symbols:
            ticker = client.get_tickers(category='spot', symbol=symbol)
            if ticker['retCode'] == 0:
                price = float(ticker['result']['list'][0]['lastPrice'])
                print(f"{symbol}: ${price}")
                
                # Calculate minimum order value
                instrument_result = client.get_instruments_info(category='spot', symbol=symbol)
                if instrument_result['retCode'] == 0:
                    info = instrument_result['result']['list'][0]
                    min_qty = float(info['lotSizeFilter']['minOrderQty'])
                    min_amt = float(info['lotSizeFilter']['minOrderAmt'])
                    min_value_by_qty = min_qty * price
                    print(f"  Min value by qty: ${min_value_by_qty:.2f}")
                    print(f"  Min value by amt: ${min_amt:.2f}")
                    print(f"  Effective min: ${max(min_value_by_qty, min_amt):.2f}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()