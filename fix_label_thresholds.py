#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to analyze and fix label generation thresholds for better class balance
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.bybit_client import BybitClient
from config import get_api_credentials
import numpy as np

def analyze_price_changes():
    """Analyze price changes to determine optimal thresholds"""
    
    # Initialize API client
    api_creds = get_api_credentials()
    bybit_client = BybitClient(
        api_creds['api_key'],
        api_creds['api_secret'],
        api_creds['testnet']
    )
    
    # Test symbols
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ATOMUSDT', 'GASUSDT', 'APEXUSDT']
    
    all_changes = []
    
    for symbol in test_symbols:
        print(f"\n📊 Analyzing price changes for {symbol}")
        
        try:
            # Get klines data
            klines_response = bybit_client.get_klines('spot', symbol, '4h', 1000)
            klines = klines_response.get('list', []) if isinstance(klines_response, dict) else klines_response
            
            # Convert to expected format if needed
            if klines and isinstance(klines[0], list):
                formatted_klines = []
                for kline in klines:
                    formatted_klines.append({
                        'timestamp': int(kline[0]),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    })
                klines = formatted_klines
            
            if not klines or len(klines) < 2:
                print(f"❌ Insufficient data for {symbol}")
                continue
            
            # Calculate price changes
            changes = []
            for i in range(len(klines) - 1):
                current_price = float(klines[i]['close'])
                future_price = float(klines[i + 1]['close'])
                change = (future_price - current_price) / current_price
                changes.append(change)
            
            all_changes.extend(changes)
            
            # Analyze changes for this symbol
            changes_array = np.array(changes)
            print(f"   Total changes: {len(changes)}")
            print(f"   Mean change: {np.mean(changes_array):.6f}")
            print(f"   Std deviation: {np.std(changes_array):.6f}")
            print(f"   Min change: {np.min(changes_array):.6f}")
            print(f"   Max change: {np.max(changes_array):.6f}")
            
            # Percentiles
            percentiles = [5, 10, 25, 50, 75, 90, 95]
            for p in percentiles:
                print(f"   {p}th percentile: {np.percentile(changes_array, p):.6f}")
            
        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")
    
    if all_changes:
        print(f"\n{'='*60}")
        print(f"📈 OVERALL ANALYSIS ({len(all_changes)} samples)")
        print(f"{'='*60}")
        
        all_changes_array = np.array(all_changes)
        print(f"Mean change: {np.mean(all_changes_array):.6f}")
        print(f"Std deviation: {np.std(all_changes_array):.6f}")
        print(f"Min change: {np.min(all_changes_array):.6f}")
        print(f"Max change: {np.max(all_changes_array):.6f}")
        
        # Percentiles for threshold determination
        percentiles = [5, 10, 15, 20, 25, 30, 33, 50, 67, 70, 75, 80, 85, 90, 95]
        print(f"\n📊 Percentiles for threshold selection:")
        for p in percentiles:
            value = np.percentile(all_changes_array, p)
            print(f"   {p:2d}th percentile: {value:8.6f}")
        
        # Test different thresholds
        print(f"\n🎯 Testing different threshold combinations:")
        
        threshold_pairs = [
            (0.00001, -0.00001),   # Current (very tight)
            (0.0001, -0.0001),     # 0.01%
            (0.0005, -0.0005),     # 0.05%
            (0.001, -0.001),       # 0.1%
            (0.002, -0.002),       # 0.2%
            (0.003, -0.003),       # 0.3%
            (0.005, -0.005),       # 0.5%
            (0.01, -0.01),         # 1%
        ]
        
        for up_thresh, down_thresh in threshold_pairs:
            up_count = np.sum(all_changes_array > up_thresh)
            down_count = np.sum(all_changes_array < down_thresh)
            neutral_count = np.sum((all_changes_array >= down_thresh) & (all_changes_array <= up_thresh))
            
            total = len(all_changes_array)
            up_pct = (up_count / total) * 100
            down_pct = (down_count / total) * 100
            neutral_pct = (neutral_count / total) * 100
            
            print(f"   Threshold ±{up_thresh:.4f}: UP={up_count:4d}({up_pct:5.1f}%) | DOWN={down_count:4d}({down_pct:5.1f}%) | NEUTRAL={neutral_count:4d}({neutral_pct:5.1f}%)")
        
        # Recommend optimal thresholds
        print(f"\n💡 RECOMMENDATIONS:")
        
        # For balanced classes (33% each)
        up_33 = np.percentile(all_changes_array, 67)
        down_33 = np.percentile(all_changes_array, 33)
        print(f"   For 33% balanced classes: UP > {up_33:.6f}, DOWN < {down_33:.6f}")
        
        # For 25% each (50% neutral)
        up_25 = np.percentile(all_changes_array, 75)
        down_25 = np.percentile(all_changes_array, 25)
        print(f"   For 25% balanced classes: UP > {up_25:.6f}, DOWN < {down_25:.6f}")
        
        # For 20% each (60% neutral)
        up_20 = np.percentile(all_changes_array, 80)
        down_20 = np.percentile(all_changes_array, 20)
        print(f"   For 20% balanced classes: UP > {up_20:.6f}, DOWN < {down_20:.6f}")

if __name__ == "__main__":
    analyze_price_changes()