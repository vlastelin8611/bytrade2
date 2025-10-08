#!/usr/bin/env python3
"""
Debug script to check what data the trainer is actually using
"""
import json
import sys
import os
from pathlib import Path

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.api.bybit_client import BybitClient
    from src.tools.ticker_data_loader import TickerDataLoader
    from config import get_api_credentials
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def debug_trainer_data():
    """Debug what data the trainer is actually using"""
    
    # Initialize components like trainer does
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
    
    client = BybitClient(api_key, api_secret, testnet)
    ticker_loader = TickerDataLoader()
    
    # Test with a few symbols that are failing
    test_symbols = ['ETHUSDT', 'BTCUSDT', 'BNBUSDT', 'USTCUSDT', 'ARBUSDT']
    
    for symbol in test_symbols:
        print(f"\n🔍 Debugging {symbol}:")
        
        # Try to get data like trainer does
        try:
            # First try API
            print(f"  📡 Trying API for {symbol}...")
            api_response = client.get_klines(
                symbol=symbol,
                interval='4h',
                limit=1000,
                category='spot'
            )
            
            klines = []
            if api_response and isinstance(api_response, dict) and 'list' in api_response:
                raw_klines = api_response['list']
                print(f"  ✅ API returned {len(raw_klines)} klines")
                
                for kline in raw_klines:
                    klines.append({
                        'timestamp': int(kline[0]),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    })
            else:
                print(f"  ❌ API failed, trying cached data...")
                # Fallback to cached data
                cached_data = ticker_loader.get_historical_data(symbol)
                print(f"  📁 Cached data type: {type(cached_data)}, content: {cached_data}")
                
                if cached_data and symbol in cached_data:
                    klines = cached_data[symbol]
                    print(f"  ✅ Cached data has {len(klines)} klines")
                else:
                    print(f"  ❌ No cached data for {symbol}")
                    continue
            
            if not klines or len(klines) < 2:
                print(f"  ❌ Insufficient klines: {len(klines) if klines else 0}")
                continue
            
            # Analyze the data like trainer does
            print(f"  📊 Analyzing {len(klines)} klines...")
            
            # Check first few klines
            print(f"  📈 First 3 klines:")
            for i, kline in enumerate(klines[:3]):
                print(f"    [{i}] {kline}")
            
            # Calculate price changes and labels
            labels = []
            changes = []
            
            for i in range(1, min(20, len(klines))):  # Check first 20 changes
                try:
                    prev_close = float(klines[i-1]['close'])
                    curr_close = float(klines[i]['close'])
                    change = (curr_close - prev_close) / prev_close
                    changes.append(change)
                    
                    abs_change = abs(change)
                    
                    # Use same threshold as trainer
                    if abs_change > 0.0005:  # 0.05%
                        if change > 0:
                            labels.append(1)  # рост
                        else:
                            labels.append(-1)  # падение
                    else:
                        labels.append(0)  # боковик
                        
                except Exception as e:
                    print(f"    ❌ Error calculating change at index {i}: {e}")
                    continue
            
            if changes:
                print(f"  📊 Price changes analysis (first 20):")
                print(f"    Changes: {[f'{c:.6f}' for c in changes[:10]]}")
                print(f"    Abs changes: {[f'{abs(c):.6f}' for c in changes[:10]]}")
                print(f"    Labels: {labels[:10]}")
                print(f"    Unique labels: {set(labels)}")
                print(f"    Label counts: {dict((l, labels.count(l)) for l in set(labels))}")
                
                # Check if any changes exceed threshold
                threshold = 0.0005
                above_threshold = [abs(c) for c in changes if abs(c) > threshold]
                print(f"    Changes above {threshold}: {len(above_threshold)}/{len(changes)}")
                if above_threshold:
                    print(f"    Above threshold values: {above_threshold[:5]}")
            else:
                print(f"  ❌ No valid price changes calculated")
                
        except Exception as e:
            print(f"  ❌ Error processing {symbol}: {e}")

if __name__ == "__main__":
    print("🐛 Debugging trainer data sources...")
    debug_trainer_data()