#!/usr/bin/env python3
"""
Debug script to understand what data the trainer is actually using
"""
import json
import sys
from pathlib import Path

def debug_trainer_data():
    """Debug the data sources used by trainer_console.py"""
    
    # Check AppData file
    appdata_path = Path.home() / "AppData" / "Local" / "BybitTradingBot" / "data" / "tickers_data.json"
    print(f"Checking AppData file: {appdata_path}")
    print(f"File exists: {appdata_path.exists()}")
    
    if appdata_path.exists():
        try:
            with open(appdata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"\nAppData file structure:")
            print(f"Keys: {list(data.keys())}")
            
            if 'historical_data' in data:
                hist_data = data['historical_data']
                print(f"Historical data type: {type(hist_data)}")
                print(f"Historical data keys: {list(hist_data.keys()) if isinstance(hist_data, dict) else 'Not a dict'}")
                
                if isinstance(hist_data, dict) and hist_data:
                    first_symbol = list(hist_data.keys())[0]
                    first_data = hist_data[first_symbol]
                    print(f"\nFirst symbol: {first_symbol}")
                    print(f"First symbol data type: {type(first_data)}")
                    if isinstance(first_data, list) and first_data:
                        print(f"First kline structure: {first_data[0].keys() if isinstance(first_data[0], dict) else first_data[0]}")
                        print(f"Number of klines: {len(first_data)}")
                        
                        # Check if this is real or synthetic data by looking at price changes
                        if len(first_data) > 1:
                            changes = []
                            for i in range(1, min(10, len(first_data))):
                                try:
                                    prev_close = float(first_data[i-1]['close'])
                                    curr_close = float(first_data[i]['close'])
                                    change = abs((curr_close - prev_close) / prev_close)
                                    changes.append(change)
                                except:
                                    continue
                            
                            if changes:
                                avg_change = sum(changes) / len(changes)
                                max_change = max(changes)
                                print(f"\nPrice change analysis:")
                                print(f"Average absolute change: {avg_change:.6f} ({avg_change*100:.4f}%)")
                                print(f"Max absolute change: {max_change:.6f} ({max_change*100:.4f}%)")
                                
                                if avg_change > 0.01:  # > 1%
                                    print("⚠️ This looks like SYNTHETIC data (very high volatility)")
                                else:
                                    print("✅ This looks like REAL market data (normal volatility)")
            
            if 'tickers' in data:
                tickers = data['tickers']
                print(f"\nTickers data type: {type(tickers)}")
                if isinstance(tickers, dict):
                    print(f"Number of tickers: {len(tickers)}")
                elif isinstance(tickers, list):
                    print(f"Number of tickers: {len(tickers)}")
                    if tickers:
                        print(f"First ticker structure: {tickers[0].keys() if isinstance(tickers[0], dict) else tickers[0]}")
                        
        except Exception as e:
            print(f"Error reading AppData file: {e}")
    
    # Check local files
    local_files = [
        "tickers_data.json",
        "tickers_data_copy.json", 
        "klines_processing_debug.json"
    ]
    
    print(f"\nChecking local files:")
    for filename in local_files:
        filepath = Path(filename)
        print(f"{filename}: exists={filepath.exists()}")
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"  Keys: {list(data.keys()) if isinstance(data, dict) else f'List with {len(data)} items'}")
            except Exception as e:
                print(f"  Error reading: {e}")

if __name__ == "__main__":
    debug_trainer_data()