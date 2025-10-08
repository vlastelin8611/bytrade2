#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug script to trace exactly where training is failing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.bybit_client import BybitClient
from src.strategies.adaptive_ml import AdaptiveMLStrategy
from config import get_api_credentials, get_ml_config
import numpy as np
from collections import Counter
import logging

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def debug_training_failure():
    """Debug exactly where training is failing"""
    
    print("🔍 Debugging training failure")
    print("="*60)
    
    # Initialize components
    api_creds = get_api_credentials()
    bybit_client = BybitClient(
        api_creds['api_key'],
        api_creds['api_secret'],
        api_creds['testnet']
    )
    
    config = get_ml_config()
    
    # Create ML strategy instance with debug logging
    ml_strategy = AdaptiveMLStrategy(
        name="debug_strategy",
        config=config,
        api_client=bybit_client,
        db_manager=None,
        config_manager=None
    )
    
    # Test with BTCUSDT first
    symbol = 'BTCUSDT'
    print(f"\n🔍 Debugging {symbol}")
    print("-" * 40)
    
    try:
        # Get klines data
        print("1. Getting klines data...")
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
        
        print(f"   ✅ Loaded {len(klines)} klines")
        
        # Check initial conditions
        print("2. Checking initial conditions...")
        feature_window = config.get('feature_window', 20)
        print(f"   Feature window: {feature_window}")
        print(f"   Klines length: {len(klines)}")
        print(f"   Required minimum: {feature_window + 10}")
        
        if len(klines) < feature_window + 10:
            print(f"   ❌ FAIL: Not enough klines ({len(klines)} < {feature_window + 10})")
            return
        else:
            print(f"   ✅ PASS: Enough klines")
        
        # Test feature extraction
        print("3. Testing feature extraction...")
        features = []
        labels = []
        failed_extractions = 0
        
        for i in range(feature_window, len(klines) - 1):
            window = klines[i - feature_window : i]
            feat = ml_strategy.extract_features(window)
            if feat:
                features.append(feat)
                
                # Calculate label
                current_price = float(klines[i]['close'])
                future_price = float(klines[i + 1]['close'])
                change = (future_price - current_price) / current_price
                
                if change > 0.004467:
                    label = 1
                elif change < -0.004172:
                    label = -1
                else:
                    label = 0
                labels.append(label)
            else:
                failed_extractions += 1
        
        print(f"   Valid features extracted: {len(features)}")
        print(f"   Failed extractions: {failed_extractions}")
        print(f"   Label distribution: {Counter(labels)}")
        
        # Check feature count requirement
        print("4. Checking feature count requirement...")
        if len(features) < 50:
            print(f"   ❌ FAIL: Not enough features ({len(features)} < 50)")
            return
        else:
            print(f"   ✅ PASS: Enough features")
        
        # Test train_model directly
        print("5. Testing train_model directly...")
        try:
            result = ml_strategy.train_model(symbol, features, labels)
            print(f"   train_model result: {result}")
            
            if result:
                print(f"   ✅ train_model SUCCESS")
            else:
                print(f"   ❌ train_model FAILED")
                
        except Exception as e:
            print(f"   ❌ train_model EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
        
        # Test full train_on_historical_data
        print("6. Testing full train_on_historical_data...")
        try:
            result = ml_strategy.train_on_historical_data(symbol, klines)
            print(f"   train_on_historical_data result: {result}")
            
            if result:
                print(f"   ✅ train_on_historical_data SUCCESS")
            else:
                print(f"   ❌ train_on_historical_data FAILED")
                
        except Exception as e:
            print(f"   ❌ train_on_historical_data EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ Error in debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_training_failure()