#!/usr/bin/env python3
"""
Script to replace synthetic historical data with real Bybit API data
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime
import time

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.api.bybit_client import BybitClient
    from config import get_api_credentials
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def replace_synthetic_data():
    """Replace synthetic historical data with real Bybit API data"""
    
    # Get API credentials
    try:
        api_creds = get_api_credentials()
        api_key = api_creds.get('api_key', 'test_key')
        api_secret = api_creds.get('api_secret', 'test_secret')
        testnet = api_creds.get('testnet', True)
    except:
        print("Using default test credentials")
        api_key = 'test_key'
        api_secret = 'test_secret'
        testnet = True
    
    # Initialize Bybit client
    client = BybitClient(api_key, api_secret, testnet)
    
    # Path to the AppData file
    appdata_path = Path.home() / "AppData" / "Local" / "BybitTradingBot" / "data" / "tickers_data.json"
    
    print(f"Loading existing data from: {appdata_path}")
    
    # Load existing data
    try:
        with open(appdata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading existing data: {e}")
        return False
    
    print(f"Found {len(data.get('historical_data', {}))} symbols with synthetic data")
    
    # Get list of symbols to update
    symbols = list(data.get('historical_data', {}).keys())[:10]  # Start with first 10 symbols
    print(f"Updating data for symbols: {symbols}")
    
    new_historical_data = {}
    
    for i, symbol in enumerate(symbols):
        print(f"\n[{i+1}/{len(symbols)}] Fetching real data for {symbol}...")
        
        try:
            # Determine category for the symbol
            category = "spot"  # Default to spot
            if symbol.endswith("USDT") or symbol.endswith("USDC"):
                category = "spot"
            elif "BTC" in symbol or "ETH" in symbol:
                category = "spot"
            
            # Fetch real historical data from Bybit API
            api_response = client.get_klines(
                symbol=symbol,
                interval='4h',
                limit=100,  # Get 100 4-hour candles
                category=category
            )
            
            if api_response and isinstance(api_response, dict) and 'list' in api_response:
                raw_klines = api_response['list']
                
                # Convert to expected format
                klines = []
                for kline in raw_klines:
                    klines.append({
                        'timestamp': int(kline[0]),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    })
                
                new_historical_data[symbol] = klines
                print(f"✅ Fetched {len(klines)} real klines for {symbol}")
                
                # Analyze volatility of real data
                if len(klines) > 1:
                    changes = []
                    for j in range(1, min(10, len(klines))):
                        try:
                            prev_close = float(klines[j-1]['close'])
                            curr_close = float(klines[j]['close'])
                            change = abs((curr_close - prev_close) / prev_close)
                            changes.append(change)
                        except:
                            continue
                    
                    if changes:
                        avg_change = sum(changes) / len(changes)
                        print(f"   Real data avg volatility: {avg_change:.6f} ({avg_change*100:.4f}%)")
                
            else:
                print(f"⚠️ No data returned for {symbol}")
                
        except Exception as e:
            print(f"❌ Error fetching data for {symbol}: {e}")
            
        # Add small delay to avoid rate limiting
        time.sleep(0.1)
    
    if new_historical_data:
        # Update the data structure
        data['historical_data'] = new_historical_data
        data['timestamp'] = datetime.now().timestamp()
        
        # Create backup of original file
        backup_path = appdata_path.with_suffix('.json.backup')
        try:
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"\n📁 Backup created: {backup_path}")
        except Exception as e:
            print(f"⚠️ Could not create backup: {e}")
        
        # Save updated data
        try:
            with open(appdata_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"✅ Updated {len(new_historical_data)} symbols with real market data")
            print(f"📁 Saved to: {appdata_path}")
            return True
        except Exception as e:
            print(f"❌ Error saving updated data: {e}")
            return False
    else:
        print("❌ No real data was fetched")
        return False

if __name__ == "__main__":
    print("🔄 Replacing synthetic data with real Bybit API data...")
    success = replace_synthetic_data()
    if success:
        print("\n🎉 Successfully replaced synthetic data with real market data!")
        print("Now restart trainer_console.py to use the real data.")
    else:
        print("\n❌ Failed to replace synthetic data")