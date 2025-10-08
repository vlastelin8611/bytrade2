#!/usr/bin/env python3
"""
Analyze the actual historical data file from AppData to understand 
real 4-hour price movements and why thresholds produce only label 0
"""

import json
import os
from pathlib import Path

def analyze_appdata_historical():
    """Analyze the actual historical data file from AppData"""
    
    data_file = r"C:\Users\vlastelin8\AppData\Local\BybitTradingBot\data\tickers_data.json"
    
    if not os.path.exists(data_file):
        print(f"❌ File not found: {data_file}")
        return
    
    print(f"📊 Analyzing: {data_file}")
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📈 Data structure type: {type(data)}")
        print(f"📈 Top-level keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        if isinstance(data, dict) and 'historical_data' in data:
            historical_data = data['historical_data']
            print(f"📈 Historical data contains {len(historical_data)} symbols")
            
            # Analyze first few symbols
            symbols_analyzed = 0
            for symbol, klines in historical_data.items():
                if symbols_analyzed >= 5:  # Analyze only first 5 symbols
                    break
                
                print(f"\n🔍 Analyzing symbol: {symbol}")
                
                if not isinstance(klines, list) or len(klines) < 2:
                    print(f"  ⚠️ Insufficient data: {len(klines) if isinstance(klines, list) else 'Not a list'}")
                    continue
                
                print(f"  📊 Records: {len(klines)}")
                print(f"  📊 Sample record: {klines[0] if klines else 'None'}")
                
                # Calculate 4-hour price movements
                movements = []
                for i in range(1, min(100, len(klines))):  # Analyze first 100 records
                    try:
                        if isinstance(klines[i], list) and len(klines[i]) > 4:
                            # OHLCV format: [timestamp, open, high, low, close, volume]
                            current_close = float(klines[i][4])
                            prev_close = float(klines[i-1][4])
                            change = abs(current_close - prev_close) / prev_close
                            movements.append(change)
                        elif isinstance(klines[i], dict):
                            # Dictionary format
                            current_close = float(klines[i].get('close', klines[i].get('4', 0)))
                            prev_close = float(klines[i-1].get('close', klines[i-1].get('4', 0)))
                            if current_close > 0 and prev_close > 0:
                                change = abs(current_close - prev_close) / prev_close
                                movements.append(change)
                    except (ValueError, KeyError, IndexError, ZeroDivisionError) as e:
                        continue
                
                if movements:
                    movements.sort()
                    print(f"  📊 4-hour price movements analysis ({len(movements)} records):")
                    print(f"    Max change: {max(movements):.8f} ({max(movements)*100:.6f}%)")
                    print(f"    Mean change: {sum(movements)/len(movements):.8f} ({sum(movements)/len(movements)*100:.6f}%)")
                    print(f"    Median change: {movements[len(movements)//2]:.8f} ({movements[len(movements)//2]*100:.6f}%)")
                    print(f"    95th percentile: {movements[int(len(movements)*0.95)]:.8f} ({movements[int(len(movements)*0.95)]*100:.6f}%)")
                    print(f"    99th percentile: {movements[int(len(movements)*0.99)]:.8f} ({movements[int(len(movements)*0.99)]*100:.6f}%)")
                    
                    # Test current thresholds
                    thresholds = [
                        (0.00001, "0.001%"),  # Current threshold
                        (0.000005, "0.0005%"),  # Even lower
                        (0.000001, "0.0001%"),  # Extremely low
                        (0.00005, "0.005%"),   # Previous threshold
                        (0.0001, "0.01%"),     # Higher threshold
                    ]
                    
                    print(f"  🎯 Threshold analysis for {symbol}:")
                    for threshold, label in thresholds:
                        exceeding = sum(1 for m in movements if m > threshold)
                        percentage = (exceeding / len(movements)) * 100
                        status = "GOOD" if 10 <= percentage <= 70 else ("TOO LOW" if percentage > 70 else "TOO HIGH")
                        print(f"    {label:>8}: {exceeding:>3}/{len(movements)} ({percentage:>5.1f}%) exceed - {status}")
                    
                    # Count labels that would be generated
                    print(f"  🏷️ Label generation simulation:")
                    for threshold, label in thresholds:
                        labels = []
                        for i in range(1, len(movements)):
                            if i < len(klines) - 1:  # Ensure we have next candle
                                try:
                                    if isinstance(klines[i], list):
                                        current_close = float(klines[i][4])
                                        next_close = float(klines[i+1][4])
                                    else:
                                        current_close = float(klines[i].get('close', klines[i].get('4', 0)))
                                        next_close = float(klines[i+1].get('close', klines[i+1].get('4', 0)))
                                    
                                    if current_close > 0 and next_close > 0:
                                        change = (next_close - current_close) / current_close
                                        if change > threshold:
                                            labels.append(1)  # Up
                                        elif change < -threshold:
                                            labels.append(2)  # Down
                                        else:
                                            labels.append(0)  # Neutral
                                except:
                                    continue
                        
                        if labels:
                            unique_labels = set(labels)
                            label_counts = {l: labels.count(l) for l in unique_labels}
                            print(f"    {label:>8}: {len(unique_labels)} unique labels - {label_counts}")
                
                symbols_analyzed += 1
        
        else:
            print("❌ No 'historical_data' key found in the file")
            if isinstance(data, dict):
                for key in list(data.keys())[:5]:
                    print(f"  Available key: {key} (type: {type(data[key])})")
    
    except Exception as e:
        print(f"❌ Error analyzing {data_file}: {e}")

if __name__ == "__main__":
    analyze_appdata_historical()