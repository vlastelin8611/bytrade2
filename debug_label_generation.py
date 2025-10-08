#!/usr/bin/env python3
"""
Debug script to examine actual price changes and label generation
"""

import json
import os
from pathlib import Path

def analyze_cached_data():
    """Analyze cached kline data to understand price movements"""
    
    # Look for cached data files
    cache_dir = Path(os.path.expanduser("~")) / "AppData" / "Local" / "BybitTradingBot" / "data"
    
    print(f"Looking for cached data in: {cache_dir}")
    
    if not cache_dir.exists():
        print("Cache directory doesn't exist")
        return
    
    # Find JSON files
    json_files = list(cache_dir.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")
    
    for json_file in json_files[:3]:  # Analyze first 3 files
        print(f"\n=== Analyzing {json_file.name} ===")
        
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            if 'klines' in data and data['klines']:
                klines = data['klines']
                print(f"Found {len(klines)} klines")
                
                # Analyze price changes
                changes = []
                for i in range(1, min(50, len(klines))):  # First 50 candles
                    prev_close = float(klines[i-1]['close'])
                    curr_close = float(klines[i]['close'])
                    change = (curr_close - prev_close) / prev_close
                    changes.append(change)
                
                if changes:
                    print(f"Price changes analysis (first {len(changes)} candles):")
                    print(f"  Min change: {min(changes):.6f} ({min(changes)*100:.4f}%)")
                    print(f"  Max change: {max(changes):.6f} ({max(changes)*100:.4f}%)")
                    print(f"  Avg absolute change: {sum(abs(c) for c in changes)/len(changes):.6f} ({sum(abs(c) for c in changes)/len(changes)*100:.4f}%)")
                    
                    # Count labels with different thresholds
                    thresholds = [0.001, 0.0005, 0.0001, 0.00005, 0.00001]  # 0.1%, 0.05%, 0.01%, 0.005%, 0.001%
                    
                    for threshold in thresholds:
                        labels = []
                        for change in changes:
                            if abs(change) > threshold:
                                labels.append(1 if change > 0 else -1)
                            else:
                                labels.append(0)
                        
                        label_counts = {-1: labels.count(-1), 0: labels.count(0), 1: labels.count(1)}
                        unique_labels = len(set(labels))
                        
                        print(f"  Threshold {threshold:.5f} ({threshold*100:.3f}%): {label_counts}, unique: {unique_labels}")
                
                # Show some actual price data
                print(f"\nFirst 10 candles:")
                for i in range(min(10, len(klines))):
                    kline = klines[i]
                    print(f"  {i}: O:{kline['open']} H:{kline['high']} L:{kline['low']} C:{kline['close']}")
                    
        except Exception as e:
            print(f"Error analyzing {json_file.name}: {e}")

def analyze_real_api_data():
    """Analyze real API data to understand price movements"""
    try:
        # Load API credentials
        api_creds = get_api_credentials()
        client = BybitClient(api_creds['api_key'], api_creds['api_secret'])
        
        # Test with real API data
        print("\n=== Analyzing real API data ===")
        try:
            # Try to get historical data for a few symbols
            for symbol in ['BTCUSDT', 'ETHUSDT']:
                print(f"\n--- Analyzing {symbol} ---")
                try:
                    # Get klines data using 'linear' category
                    response = client.get_klines('linear', symbol, '4h', 100)
                    if response and 'result' in response and 'list' in response['result']:
                        klines = response['result']['list']
                        print(f"Got {len(klines)} klines for {symbol}")
                        
                        # Extract close prices (index 4 in kline data)
                        # Note: klines are in reverse chronological order
                        prices = [float(kline[4]) for kline in reversed(klines)]
                        analyze_price_changes(prices, symbol)
                    else:
                        print(f"No klines data for {symbol}: {response}")
                except Exception as e:
                    print(f"Error getting klines for {symbol}: {e}")
        except Exception as e:
            print(f"Error analyzing API data: {e}")
    except Exception as e:
        print(f"Error initializing API client: {e}")

def analyze_price_changes(prices, symbol):
    """Analyze price changes for a given price series"""
    if len(prices) < 2:
        print(f"Not enough price data for {symbol}")
        return
    
    # Calculate price changes
    changes = []
    for i in range(1, len(prices)):
        prev_price = prices[i-1]
        curr_price = prices[i]
        change = (curr_price - prev_price) / prev_price
        changes.append(change)
    
    if changes:
        print(f"Price changes analysis for {symbol} ({len(changes)} changes):")
        print(f"  Min change: {min(changes):.6f} ({min(changes)*100:.4f}%)")
        print(f"  Max change: {max(changes):.6f} ({max(changes)*100:.4f}%)")
        print(f"  Avg absolute change: {sum(abs(c) for c in changes)/len(changes):.6f} ({sum(abs(c) for c in changes)/len(changes)*100:.4f}%)")
        
        # Count labels with different thresholds
        thresholds = [0.001, 0.0005, 0.0001, 0.00005, 0.00001]  # 0.1%, 0.05%, 0.01%, 0.005%, 0.001%
        
        for threshold in thresholds:
            labels = []
            for change in changes:
                if abs(change) > threshold:
                    labels.append(1 if change > 0 else -1)
                else:
                    labels.append(0)
            
            label_counts = {-1: labels.count(-1), 0: labels.count(0), 1: labels.count(1)}
            unique_labels = len(set(labels))
            min_class_size = min(label_counts.values()) if label_counts.values() else 0
            
            print(f"  Threshold {threshold:.5f} ({threshold*100:.3f}%): {label_counts}, unique: {unique_labels}, min_class: {min_class_size}")

def create_synthetic_test():
    """Create synthetic data with known price movements to test label generation"""
    
    print("\n=== Testing with synthetic data ===")
    
    # Create test data with various price movements
    base_price = 50000.0
    test_klines = []
    
    # Generate test candles with different price movements
    price_changes = [0.0002, -0.0001, 0.0015, -0.0008, 0.0003, -0.0012, 0.0006, -0.0004, 0.0020, -0.0025]
    
    current_price = base_price
    for i, change in enumerate(price_changes):
        new_price = current_price * (1 + change)
        
        kline = {
            'timestamp': str(1700000000 + i * 14400),  # 4h intervals
            'open': str(current_price),
            'high': str(max(current_price, new_price) * 1.001),
            'low': str(min(current_price, new_price) * 0.999),
            'close': str(new_price),
            'volume': '1000'
        }
        test_klines.append(kline)
        current_price = new_price
    
    print(f"Created {len(test_klines)} synthetic candles")
    
    # Analyze synthetic data
    changes = []
    for i in range(1, len(test_klines)):
        prev_close = float(test_klines[i-1]['close'])
        curr_close = float(test_klines[i]['close'])
        change = (curr_close - prev_close) / prev_close
        changes.append(change)
        print(f"Candle {i}: {prev_close:.2f} -> {curr_close:.2f}, change: {change:.6f} ({change*100:.4f}%)")
    
    # Test label generation
    thresholds = [0.001, 0.0005, 0.0001]
    
    for threshold in thresholds:
        labels = []
        for change in changes:
            if abs(change) > threshold:
                labels.append(1 if change > 0 else -1)
            else:
                labels.append(0)
        
        label_counts = {-1: labels.count(-1), 0: labels.count(0), 1: labels.count(1)}
        unique_labels = len(set(labels))
        min_class_size = min(label_counts.values()) if label_counts.values() else 0
        
        print(f"Threshold {threshold:.4f} ({threshold*100:.2f}%): {label_counts}")
        print(f"  Unique labels: {unique_labels}, Min class size: {min_class_size}")
        print(f"  Passes diversity check: {unique_labels >= 2}")
        print(f"  Passes min class check (>=2): {min_class_size >= 2}")

if __name__ == "__main__":
    print("🔍 Debugging label generation issues")
    print("=" * 50)
    
    analyze_cached_data()
    analyze_real_api_data()
    create_synthetic_test()