#!/usr/bin/env python3
"""
Test script to check API historical data with different configurations
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

def test_api_configurations():
    """Test different API configurations to get real historical data"""
    
    # Get API credentials
    try:
        api_creds = get_api_credentials()
        api_key = api_creds.get('api_key', 'test_key')
        api_secret = api_creds.get('api_secret', 'test_secret')
        testnet = api_creds.get('testnet', True)
    except:
        print("Using default test credentials")
        api_key = 'test_key'
        api_secret = 'test_secret'
        testnet = True
    
    print(f"🔧 Current configuration: testnet={testnet}")
    
    # Test both testnet and mainnet
    configs = [
        {"testnet": True, "name": "Testnet"},
        {"testnet": False, "name": "Mainnet"}
    ]
    
    test_symbol = "BTCUSDT"
    
    for config in configs:
        print(f"\n{'='*50}")
        print(f"🧪 Testing {config['name']} (testnet={config['testnet']})")
        print(f"{'='*50}")
        
        try:
            client = BybitClient(api_key, api_secret, config['testnet'])
            
            # Test 1: Get current server time
            print(f"📅 Testing server time...")
            try:
                server_time = client._get_server_time_raw()
                server_dt = datetime.fromtimestamp(server_time / 1000)
                current_dt = datetime.now()
                print(f"   Server time: {server_dt}")
                print(f"   Local time:  {current_dt}")
                print(f"   Difference:  {abs((server_dt - current_dt).total_seconds())} seconds")
            except Exception as e:
                print(f"   ❌ Server time error: {e}")
            
            # Test 2: Get klines without time parameters (should get recent data)
            print(f"\n📊 Testing recent klines for {test_symbol}...")
            try:
                response = client.get_klines(
                    category='spot',
                    symbol=test_symbol,
                    interval='4h',
                    limit=10
                )
                
                if response and 'list' in response:
                    klines = response['list']
                    print(f"   ✅ Got {len(klines)} klines")
                    
                    # Analyze first few klines
                    for i, kline in enumerate(klines[:3]):
                        timestamp = int(kline[0])
                        dt = datetime.fromtimestamp(timestamp / 1000)
                        open_price = float(kline[1])
                        close_price = float(kline[4])
                        
                        print(f"   [{i}] {dt} | Open: {open_price} | Close: {close_price}")
                        
                        # Check if timestamp is in the future
                        if dt > datetime.now():
                            print(f"       ⚠️ FUTURE TIMESTAMP DETECTED!")
                        elif dt < datetime.now() - timedelta(days=30):
                            print(f"       ✅ Historical data (older than 30 days)")
                        else:
                            print(f"       ✅ Recent data")
                else:
                    print(f"   ❌ No data returned: {response}")
                    
            except Exception as e:
                print(f"   ❌ Klines error: {e}")
            
            # Test 3: Get historical data with specific time range
            print(f"\n📈 Testing historical klines with time range...")
            try:
                # Get data from 7 days ago to 1 day ago
                end_time = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)
                start_time = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
                
                print(f"   Requesting data from {datetime.fromtimestamp(start_time/1000)} to {datetime.fromtimestamp(end_time/1000)}")
                
                response = client.get_klines(
                    category='spot',
                    symbol=test_symbol,
                    interval='4h',
                    limit=20,
                    start=start_time,
                    end=end_time
                )
                
                if response and 'list' in response:
                    klines = response['list']
                    print(f"   ✅ Got {len(klines)} historical klines")
                    
                    # Check if we got real historical data
                    if klines:
                        first_kline = klines[0]
                        last_kline = klines[-1]
                        
                        first_dt = datetime.fromtimestamp(int(first_kline[0]) / 1000)
                        last_dt = datetime.fromtimestamp(int(last_kline[0]) / 1000)
                        
                        print(f"   First kline: {first_dt}")
                        print(f"   Last kline:  {last_dt}")
                        
                        # Check for price variation
                        prices = [float(kline[4]) for kline in klines]
                        min_price = min(prices)
                        max_price = max(prices)
                        price_variation = (max_price - min_price) / min_price
                        
                        print(f"   Price range: {min_price} - {max_price}")
                        print(f"   Variation: {price_variation:.4f} ({price_variation*100:.2f}%)")
                        
                        if price_variation > 0.001:  # More than 0.1% variation
                            print(f"   ✅ Real market data detected (has price variation)")
                        else:
                            print(f"   ⚠️ Suspicious data (no price variation)")
                else:
                    print(f"   ❌ No historical data returned: {response}")
                    
            except Exception as e:
                print(f"   ❌ Historical klines error: {e}")
                
        except Exception as e:
            print(f"❌ Failed to test {config['name']}: {e}")
    
    # Recommendation
    print(f"\n💡 Recommendations:")
    print("1. If testnet shows future timestamps or static prices, switch to mainnet")
    print("2. Use specific time ranges (start/end parameters) for historical data")
    print("3. Verify API credentials are valid for the chosen environment")

if __name__ == "__main__":
    print("🔍 Testing API configurations for historical data...")
    test_api_configurations()