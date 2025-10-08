#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug script to analyze feature extraction process
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.strategies.adaptive_ml import AdaptiveMLStrategy
from src.api.bybit_client import BybitClient
from config import get_api_credentials, get_ml_config

def debug_feature_extraction():
    """Debug the feature extraction process for specific symbols"""
    
    # Initialize components
    api_creds = get_api_credentials()
    bybit_client = BybitClient(
        api_creds['api_key'],
        api_creds['api_secret'],
        api_creds['testnet']
    )
    
    ml_config = get_ml_config()
    ml_strategy = AdaptiveMLStrategy(
        name="debug_ml",
        config=ml_config,
        api_client=bybit_client,
        db_manager=None,
        config_manager=None
    )
    
    # Test symbols that are failing
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ATOMUSDT', 'GASUSDT', 'APEXUSDT']
    
    for symbol in test_symbols:
        print(f"\n{'='*60}")
        print(f"🔍 Debugging feature extraction for {symbol}")
        print(f"{'='*60}")
        
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
            
            if not klines:
                print(f"❌ No klines data for {symbol}")
                continue
                
            print(f"📊 Total klines: {len(klines)}")
            print(f"🪟 Feature window: {ml_strategy.feature_window}")
            
            # Simulate the training process
            features = []
            labels = []
            failed_extractions = 0
            
            for i in range(ml_strategy.feature_window, len(klines) - 1):
                window = klines[i - ml_strategy.feature_window : i]
                feat = ml_strategy.extract_features(window)
                
                if feat:
                    features.append(feat)
                    
                    # Create label
                    current_price = float(klines[i]['close'])
                    future_price = float(klines[i + 1]['close'])
                    change = (future_price - current_price) / current_price
                    
                    if change > 0.00001:
                        label = 1
                    elif change < -0.00001:
                        label = -1
                    else:
                        label = 0
                    labels.append(label)
                else:
                    failed_extractions += 1
            
            print(f"📈 Potential samples: {len(klines) - ml_strategy.feature_window - 1}")
            print(f"✅ Valid features extracted: {len(features)}")
            print(f"❌ Failed extractions: {failed_extractions}")
            print(f"📊 Feature vector length: {len(features[0]) if features else 'N/A'}")
            
            # Analyze labels
            if labels:
                label_counts = {label: labels.count(label) for label in set(labels)}
                print(f"🏷️ Label distribution: {label_counts}")
                
                # Check if meets training requirements
                min_features_trainer = 20  # from trainer_console.py
                min_features_ml = 50       # from adaptive_ml.py
                min_class_size = min(label_counts.values()) if label_counts else 0
                
                print(f"\n📋 Training Requirements Check:")
                print(f"   Features >= {min_features_trainer} (trainer): {'✅' if len(features) >= min_features_trainer else '❌'}")
                print(f"   Features >= {min_features_ml} (ML strategy): {'✅' if len(features) >= min_features_ml else '❌'}")
                print(f"   Label diversity >= 2: {'✅' if len(label_counts) >= 2 else '❌'}")
                print(f"   Min class size >= 2: {'✅' if min_class_size >= 2 else '❌'}")
                
                # Show first few features for inspection
                if features:
                    print(f"\n🔍 First 3 feature vectors:")
                    for j, feat in enumerate(features[:3]):
                        print(f"   [{j}] {feat[:5]}... (length: {len(feat)})")
                        
                # Show price data sample
                print(f"\n💰 Price data sample (last 5 klines):")
                for j, kline in enumerate(klines[-5:]):
                    print(f"   [{j}] Close: {kline['close']}, Volume: {kline['volume']}")
            
        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_feature_extraction()