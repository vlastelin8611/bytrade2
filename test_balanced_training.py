#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify balanced class distribution with new thresholds
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.bybit_client import BybitClient
from src.strategies.adaptive_ml import AdaptiveMLStrategy
from config import get_api_credentials, get_ml_config
import numpy as np
from collections import Counter

def test_balanced_training():
    """Test that new thresholds create balanced classes and allow training"""
    
    print("🧪 Testing balanced class distribution with new thresholds")
    print("="*60)
    
    # Initialize components
    api_creds = get_api_credentials()
    bybit_client = BybitClient(
        api_creds['api_key'],
        api_creds['api_secret'],
        api_creds['testnet']
    )
    
    config = get_ml_config()
    
    # Create ML strategy instance
    ml_strategy = AdaptiveMLStrategy(
        name="test_strategy",
        config=config,
        api_client=bybit_client,
        db_manager=None,
        config_manager=None
    )
    
    # Test symbols
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ATOMUSDT', 'GASUSDT', 'APEXUSDT']
    
    for symbol in test_symbols:
        print(f"\n📊 Testing {symbol}")
        print("-" * 40)
        
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
            
            print(f"   Loaded {len(klines)} klines")
            
            # Test training with new thresholds
            training_result = ml_strategy.train_on_historical_data(symbol, klines)
            
            if training_result:
                print(f"   ✅ Training SUCCESSFUL for {symbol}")
            else:
                print(f"   ❌ Training FAILED for {symbol}")
            
            # Manually check label distribution with new thresholds
            features = []
            labels = []
            
            feature_window = config.get('feature_window', 20)
            
            for i in range(feature_window, len(klines) - 1):
                # Extract features for this window
                window_klines = klines[i-feature_window:i]
                feature_vector = ml_strategy.extract_features(window_klines)
                
                if feature_vector is not None:
                    features.append(feature_vector)
                    
                    # Calculate label with new thresholds
                    current_price = float(klines[i]['close'])
                    future_price = float(klines[i + 1]['close'])
                    change = (future_price - current_price) / current_price
                    
                    # New balanced thresholds
                    if change > 0.004467:  # UP threshold
                        label = 1
                    elif change < -0.004172:  # DOWN threshold
                        label = -1
                    else:
                        label = 0
                    
                    labels.append(label)
            
            # Analyze label distribution
            label_counts = Counter(labels)
            total_samples = len(labels)
            
            print(f"   📈 Label Distribution:")
            for label in [-1, 0, 1]:
                count = label_counts.get(label, 0)
                percentage = (count / total_samples) * 100 if total_samples > 0 else 0
                label_name = {-1: "SELL", 0: "HOLD", 1: "BUY"}[label]
                print(f"      {label_name:4s} ({label:2d}): {count:4d} samples ({percentage:5.1f}%)")
            
            # Check training requirements
            print(f"   🔍 Training Requirements Check:")
            print(f"      Total features: {len(features)} (need >= 50)")
            print(f"      Unique labels: {len(set(labels))} (need >= 2)")
            
            min_class_size = min(label_counts.values()) if label_counts else 0
            print(f"      Min class size: {min_class_size} (need >= 2)")
            
            # Overall assessment
            requirements_met = (
                len(features) >= 50 and
                len(set(labels)) >= 2 and
                min_class_size >= 2
            )
            
            if requirements_met:
                print(f"   ✅ All training requirements MET")
            else:
                print(f"   ❌ Training requirements NOT met")
                
        except Exception as e:
            print(f"   ❌ Error processing {symbol}: {e}")
    
    print(f"\n{'='*60}")
    print("🎯 Test completed!")

if __name__ == "__main__":
    test_balanced_training()