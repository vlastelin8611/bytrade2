#!/usr/bin/env python3
"""
Test script to verify mainnet data quality vs testnet
"""
import json
import sys
import os
from datetime import datetime, timedelta
import time

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.api.bybit_client import BybitClient
    from config import get_api_credentials
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def test_data_quality():
    """Test data quality from mainnet vs testnet"""
    
    # Get API credentials
    try:
        api_creds = get_api_credentials()
        api_key = api_creds.get('api_key', 'test_key')
        api_secret = api_creds.get('api_secret', 'test_secret')
    except:
        print("Using default test credentials")
        api_key = 'test_key'
        api_secret = 'test_secret'
    
    test_symbols = ["BTCUSDT", "ETHUSDT", "SUSHIUSDT", "TONUSDT"]
    
    # Test mainnet (current config)
    print(f"🔍 Testing MAINNET data quality...")
    print(f"{'='*60}")
    
    try:
        client = BybitClient(api_key, api_secret, testnet=False)
        
        for symbol in test_symbols:
            print(f"\n📊 Testing {symbol}...")
            
            try:
                # Get recent klines
                response = client.get_klines(
                    category='spot',
                    symbol=symbol,
                    interval='4h',
                    limit=100
                )
                
                if response and 'list' in response:
                    klines = response['list']
                    print(f"   ✅ Got {len(klines)} klines")
                    
                    if len(klines) >= 10:
                        # Analyze price changes
                        prices = [float(kline[4]) for kline in klines[:10]]  # Close prices
                        changes = []
                        
                        for i in range(1, len(prices)):
                            change = abs(prices[i] - prices[i-1]) / prices[i-1]
                            changes.append(change)
                        
                        if changes:
                            avg_change = sum(changes) / len(changes)
                            max_change = max(changes)
                            zero_changes = sum(1 for c in changes if c == 0.0)
                            
                            print(f"   📈 Average change: {avg_change:.6f} ({avg_change*100:.4f}%)")
                            print(f"   📈 Max change: {max_change:.6f} ({max_change*100:.4f}%)")
                            print(f"   📈 Zero changes: {zero_changes}/{len(changes)} ({zero_changes/len(changes)*100:.1f}%)")
                            
                            # Check timestamps
                            first_ts = int(klines[0][0])
                            last_ts = int(klines[-1][0])
                            first_dt = datetime.fromtimestamp(first_ts / 1000)
                            last_dt = datetime.fromtimestamp(last_ts / 1000)
                            
                            print(f"   🕐 Time range: {last_dt} to {first_dt}")
                            
                            # Check if data is realistic
                            if zero_changes / len(changes) < 0.5 and avg_change > 0.001:
                                print(f"   ✅ Data looks realistic")
                            else:
                                print(f"   ⚠️ Data may be problematic")
                        else:
                            print(f"   ❌ No price changes calculated")
                    else:
                        print(f"   ⚠️ Not enough klines for analysis")
                else:
                    print(f"   ❌ No data returned")
                    
            except Exception as e:
                print(f"   ❌ Error getting data for {symbol}: {e}")
    
    except Exception as e:
        print(f"❌ Failed to test mainnet: {e}")
    
    print(f"\n💡 Analysis:")
    print("- If zero changes > 50%, the data has too many duplicate prices")
    print("- If average change < 0.001 (0.1%), the data may be static")
    print("- Real market data should have some price variation")

if __name__ == "__main__":
    print("🔍 Testing mainnet data quality...")
    test_data_quality()