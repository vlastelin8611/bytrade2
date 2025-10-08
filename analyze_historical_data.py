#!/usr/bin/env python3
"""
Analyze historical 4-hour data to understand actual price movements
and determine why even 0.001% threshold produces only label 0
"""

import json
import os
from pathlib import Path

def analyze_historical_data():
    """Analyze actual historical data files to understand price movements"""
    
    # Look for data files in common locations
    data_paths = [
        "data",
        "src/data", 
        "bytrade2/src/data",
        "."
    ]
    
    found_files = []
    for data_path in data_paths:
        if os.path.exists(data_path):
            for file in os.listdir(data_path):
                if file.endswith('.json') and ('klines' in file.lower() or 'historical' in file.lower() or 'data' in file.lower()):
                    found_files.append(os.path.join(data_path, file))
    
    print(f"🔍 Found {len(found_files)} potential data files:")
    for file in found_files[:10]:  # Show first 10
        print(f"  - {file}")
    
    if not found_files:
        print("❌ No historical data files found")
        return
    
    # Analyze the first available file
    data_file = found_files[0]
    print(f"\n📊 Analyzing: {data_file}")
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📈 Data structure type: {type(data)}")
        
        if isinstance(data, dict):
            print(f"📈 Dictionary keys: {list(data.keys())[:10]}")
            
            # Try to find symbol data
            for key, value in list(data.items())[:3]:
                print(f"\n🔍 Analyzing symbol: {key}")
                if isinstance(value, list) and len(value) > 0:
                    print(f"  Records: {len(value)}")
                    print(f"  Sample record: {value[0] if value else 'None'}")
                    
                    # Calculate price movements
                    if len(value) > 10:
                        movements = []
                        for i in range(1, min(100, len(value))):  # Analyze first 100 records
                            try:
                                if isinstance(value[i], list) and len(value[i]) > 4:
                                    # Assuming OHLCV format: [timestamp, open, high, low, close, volume]
                                    current_close = float(value[i][4])
                                    prev_close = float(value[i-1][4])
                                    change = abs(current_close - prev_close) / prev_close
                                    movements.append(change)
                                elif isinstance(value[i], dict) and 'close' in value[i]:
                                    current_close = float(value[i]['close'])
                                    prev_close = float(value[i-1]['close'])
                                    change = abs(current_close - prev_close) / prev_close
                                    movements.append(change)
                            except (ValueError, KeyError, IndexError) as e:
                                continue
                        
                        if movements:
                            movements.sort()
                            print(f"  📊 Price movements analysis (first 100 records):")
                            print(f"    Max change: {max(movements):.6f} ({max(movements)*100:.4f}%)")
                            print(f"    Mean change: {sum(movements)/len(movements):.6f} ({sum(movements)/len(movements)*100:.4f}%)")
                            print(f"    Median change: {movements[len(movements)//2]:.6f} ({movements[len(movements)//2]*100:.4f}%)")
                            print(f"    95th percentile: {movements[int(len(movements)*0.95)]:.6f} ({movements[int(len(movements)*0.95)]*100:.4f}%)")
                            
                            # Test thresholds
                            thresholds = [0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01]
                            print(f"  🎯 Threshold analysis:")
                            for threshold in thresholds:
                                exceeding = sum(1 for m in movements if m > threshold)
                                percentage = (exceeding / len(movements)) * 100
                                print(f"    {threshold:.5f} ({threshold*100:.3f}%): {exceeding}/{len(movements)} ({percentage:.1f}%) exceed")
                        
                        break  # Only analyze first symbol with data
                
        elif isinstance(data, list):
            print(f"📈 List with {len(data)} items")
            if data:
                print(f"📈 Sample item: {data[0]}")
        
    except Exception as e:
        print(f"❌ Error analyzing {data_file}: {e}")

if __name__ == "__main__":
    analyze_historical_data()