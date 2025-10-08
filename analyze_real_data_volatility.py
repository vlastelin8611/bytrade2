#!/usr/bin/env python3
"""
Analyze the volatility of real market data to determine appropriate thresholds
"""
import json
import sys
import os
from pathlib import Path
import numpy as np

def analyze_real_data_volatility():
    """Analyze volatility of real market data"""
    
    # Path to the AppData file with real data
    appdata_path = Path.home() / "AppData" / "Local" / "BybitTradingBot" / "data" / "tickers_data.json"
    
    print(f"Loading real market data from: {appdata_path}")
    
    try:
        with open(appdata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return
    
    historical_data = data.get('historical_data', {})
    print(f"Found {len(historical_data)} symbols with real data")
    
    all_changes = []
    symbol_stats = {}
    
    for symbol, klines in historical_data.items():
        if not klines or len(klines) < 2:
            continue
            
        changes = []
        for i in range(1, len(klines)):
            try:
                prev_close = float(klines[i-1]['close'])
                curr_close = float(klines[i]['close'])
                change = abs((curr_close - prev_close) / prev_close)
                changes.append(change)
            except:
                continue
        
        if changes:
            symbol_stats[symbol] = {
                'count': len(changes),
                'mean': np.mean(changes),
                'median': np.median(changes),
                'std': np.std(changes),
                'min': np.min(changes),
                'max': np.max(changes),
                'p25': np.percentile(changes, 25),
                'p75': np.percentile(changes, 75),
                'p90': np.percentile(changes, 90),
                'p95': np.percentile(changes, 95),
                'p99': np.percentile(changes, 99)
            }
            all_changes.extend(changes)
    
    if not all_changes:
        print("No price changes found in the data")
        return
    
    print(f"\n📊 Overall Statistics from {len(all_changes)} price changes:")
    print(f"Mean change: {np.mean(all_changes):.6f} ({np.mean(all_changes)*100:.4f}%)")
    print(f"Median change: {np.median(all_changes):.6f} ({np.median(all_changes)*100:.4f}%)")
    print(f"Std deviation: {np.std(all_changes):.6f} ({np.std(all_changes)*100:.4f}%)")
    print(f"Min change: {np.min(all_changes):.6f} ({np.min(all_changes)*100:.4f}%)")
    print(f"Max change: {np.max(all_changes):.6f} ({np.max(all_changes)*100:.4f}%)")
    
    print(f"\n📈 Percentiles:")
    print(f"25th percentile: {np.percentile(all_changes, 25):.6f} ({np.percentile(all_changes, 25)*100:.4f}%)")
    print(f"50th percentile: {np.percentile(all_changes, 50):.6f} ({np.percentile(all_changes, 50)*100:.4f}%)")
    print(f"75th percentile: {np.percentile(all_changes, 75):.6f} ({np.percentile(all_changes, 75)*100:.4f}%)")
    print(f"90th percentile: {np.percentile(all_changes, 90):.6f} ({np.percentile(all_changes, 90)*100:.4f}%)")
    print(f"95th percentile: {np.percentile(all_changes, 95):.6f} ({np.percentile(all_changes, 95)*100:.4f}%)")
    print(f"99th percentile: {np.percentile(all_changes, 99):.6f} ({np.percentile(all_changes, 99)*100:.4f}%)")
    
    # Test different thresholds
    thresholds = [0.00001, 0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02]
    
    print(f"\n🎯 Threshold Analysis:")
    print("Threshold | % Above | % Below | Label Distribution")
    print("-" * 55)
    
    for threshold in thresholds:
        above_count = sum(1 for change in all_changes if change > threshold)
        below_count = len(all_changes) - above_count
        above_pct = (above_count / len(all_changes)) * 100
        below_pct = (below_count / len(all_changes)) * 100
        
        # Simulate label generation
        labels = []
        for change in all_changes:
            if change > threshold:
                labels.append(1)  # Significant movement
            else:
                labels.append(0)  # No significant movement
        
        unique_labels = set(labels)
        label_counts = {label: labels.count(label) for label in unique_labels}
        
        print(f"{threshold:8.5f} | {above_pct:6.2f}% | {below_pct:6.2f}% | {label_counts}")
    
    # Recommend optimal threshold
    print(f"\n💡 Recommendations:")
    
    # Find threshold where ~30-70% of changes are above it (balanced labels)
    optimal_thresholds = []
    for threshold in thresholds:
        above_pct = (sum(1 for change in all_changes if change > threshold) / len(all_changes)) * 100
        if 30 <= above_pct <= 70:
            optimal_thresholds.append((threshold, above_pct))
    
    if optimal_thresholds:
        print("Balanced thresholds (30-70% above):")
        for threshold, pct in optimal_thresholds:
            print(f"  {threshold:.5f} ({threshold*100:.3f}%) - {pct:.1f}% above threshold")
    
    # Show per-symbol stats for top symbols
    print(f"\n📋 Per-Symbol Statistics (top 10):")
    sorted_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['mean'], reverse=True)[:10]
    
    print("Symbol      | Mean    | Median  | Max     | P90     | P95")
    print("-" * 60)
    for symbol, stats in sorted_symbols:
        print(f"{symbol:11} | {stats['mean']*100:6.3f}% | {stats['median']*100:6.3f}% | {stats['max']*100:6.3f}% | {stats['p90']*100:6.3f}% | {stats['p95']*100:6.3f}%")

if __name__ == "__main__":
    print("🔍 Analyzing real market data volatility...")
    analyze_real_data_volatility()