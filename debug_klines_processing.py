#!/usr/bin/env python3
"""
Отладка обработки данных klines от API до обучения
Проверяем, где теряются данные в процессе обработки
"""

import sys
import os
import json
from datetime import datetime

# Добавляем пути для импорта
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'api'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'strategies'))

#!/usr/bin/env python3
"""
Отладка обработки данных klines от API до обучения
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from config import get_api_credentials, get_ml_config
from src.api.bybit_client import BybitClient
from src.strategies.adaptive_ml import AdaptiveMLStrategy
import json
import pandas as pd

def debug_klines_processing():
    """Отладка обработки данных klines"""
    print("🔍 Отладка обработки данных klines")
    print("=" * 60)
    
    # Инициализация клиента
    try:
        api_creds = get_api_credentials()
        client = BybitClient(
            api_creds['api_key'],
            api_creds['api_secret'],
            api_creds['testnet']
        )
        print("✅ BybitClient инициализирован")
    except Exception as e:
        print(f"❌ Ошибка инициализации BybitClient: {e}")
        return
    
    # Инициализация ML стратегии
    try:
        ml_config = get_ml_config()
        ml_strategy = AdaptiveMLStrategy(
            name="adaptive_ml",
            config=ml_config,
            api_client=client,
            db_manager=None,
            config_manager=None
        )
        print("✅ AdaptiveMLStrategy инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации AdaptiveMLStrategy: {e}")
        return
    
    # Тестовые символы
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
    test_categories = ['spot', 'linear']
    test_intervals = ['4h', '240', '60', '1h']
    test_limits = [10, 50, 100, 200, 500, 1000]
    
    results = {
        'api_responses': {},
        'processed_data': {},
        'feature_extraction': {},
        'training_data': {}
    }
    
    for symbol in test_symbols:
        print(f"\n🔄 Тестирование {symbol}")
        print("-" * 40)
        
        for category in test_categories:
            print(f"\n📊 Категория: {category}")
            
            for interval in test_intervals:
                print(f"\n⏰ Интервал: {interval}")
                
                for limit in test_limits:
                    print(f"\n📈 Лимит: {limit}")
                    
                    try:
                        # 1. Прямой вызов API
                        print("1️⃣ Прямой вызов API...")
                        api_response = client._make_request('GET', '/v5/market/kline', {
                            'category': category,
                            'symbol': symbol,
                            'interval': interval,
                            'limit': limit
                        })
                        
                        api_count = 0
                        if api_response and 'result' in api_response and 'list' in api_response['result']:
                            api_count = len(api_response['result']['list'])
                        
                        print(f"   API ответ: {api_count} записей")
                        
                        # 2. Вызов через get_klines
                        print("2️⃣ Вызов через get_klines...")
                        klines_response = client.get_klines(
                            category=category,
                            symbol=symbol,
                            interval=interval,
                            limit=limit
                        )
                        
                        klines_count = 0
                        klines_data = None
                        if klines_response and 'result' in klines_response and 'list' in klines_response['result']:
                            klines_data = klines_response['result']['list']
                            klines_count = len(klines_data)
                        
                        print(f"   get_klines: {klines_count} записей")
                        
                        # 3. Обработка данных в формат для ML
                        print("3️⃣ Обработка для ML...")
                        processed_data = []
                        if klines_data:
                            for kline in klines_data:
                                try:
                                    processed_data.append({
                                        'open': float(kline[1]),
                                        'high': float(kline[2]),
                                        'low': float(kline[3]),
                                        'close': float(kline[4]),
                                        'volume': float(kline[5]),
                                        'timestamp': int(kline[0])
                                    })
                                except (ValueError, IndexError) as e:
                                    print(f"   ⚠️ Ошибка обработки kline: {e}")
                                    continue
                        
                        processed_count = len(processed_data)
                        print(f"   Обработано: {processed_count} записей")
                        
                        # 4. Извлечение признаков
                        print("4️⃣ Извлечение признаков...")
                        features_count = 0
                        if processed_data and len(processed_data) >= ml_strategy.feature_window:
                            for i in range(ml_strategy.feature_window, len(processed_data)):
                                window = processed_data[i - ml_strategy.feature_window : i]
                                features = ml_strategy.extract_features(window)
                                if features:
                                    features_count += 1
                        
                        print(f"   Признаки: {features_count} наборов")
                        
                        # Сохранение результатов
                        key = f"{symbol}_{category}_{interval}_{limit}"
                        results['api_responses'][key] = api_count
                        results['processed_data'][key] = processed_count
                        results['feature_extraction'][key] = features_count
                        
                        # Анализ потерь данных
                        if api_count != klines_count:
                            print(f"   ⚠️ ПОТЕРЯ ДАННЫХ: API {api_count} → get_klines {klines_count}")
                        
                        if klines_count != processed_count:
                            print(f"   ⚠️ ПОТЕРЯ ДАННЫХ: get_klines {klines_count} → обработка {processed_count}")
                        
                        if processed_count > 0 and features_count == 0:
                            print(f"   ⚠️ ПРОБЛЕМА ПРИЗНАКОВ: {processed_count} записей → 0 признаков")
                        
                        # Детальный анализ для первого случая
                        if symbol == test_symbols[0] and category == test_categories[0] and interval == test_intervals[0] and limit == test_limits[0]:
                            print("\n🔬 Детальный анализ первого случая:")
                            print(f"   API response keys: {list(api_response.keys()) if api_response else 'None'}")
                            if api_response and 'result' in api_response:
                                print(f"   Result keys: {list(api_response['result'].keys())}")
                                if 'list' in api_response['result'] and api_response['result']['list']:
                                    first_kline = api_response['result']['list'][0]
                                    print(f"   Первая kline: {first_kline}")
                                    print(f"   Длина kline: {len(first_kline)}")
                            
                            print(f"   get_klines response keys: {list(klines_response.keys()) if klines_response else 'None'}")
                            if processed_data:
                                print(f"   Первая обработанная запись: {processed_data[0]}")
                        
                    except Exception as e:
                        print(f"   ❌ Ошибка: {e}")
                        continue
    
    # Сохранение результатов
    with open('klines_processing_debug.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Результаты сохранены в klines_processing_debug.json")
    
    # Анализ общих проблем
    print("\n📊 АНАЛИЗ ПРОБЛЕМ:")
    print("=" * 40)
    
    api_counts = list(results['api_responses'].values())
    processed_counts = list(results['processed_data'].values())
    feature_counts = list(results['feature_extraction'].values())
    
    if api_counts:
        print(f"API ответы: мин={min(api_counts)}, макс={max(api_counts)}, среднее={sum(api_counts)/len(api_counts):.1f}")
    
    if processed_counts:
        print(f"Обработанные: мин={min(processed_counts)}, макс={max(processed_counts)}, среднее={sum(processed_counts)/len(processed_counts):.1f}")
    
    if feature_counts:
        print(f"Признаки: мин={min(feature_counts)}, макс={max(feature_counts)}, среднее={sum(feature_counts)/len(feature_counts):.1f}")
    
    # Поиск случаев с потерей данных
    data_loss_cases = []
    for key in results['api_responses']:
        api_count = results['api_responses'][key]
        processed_count = results['processed_data'][key]
        feature_count = results['feature_extraction'][key]
        
        if api_count != processed_count or (processed_count > 0 and feature_count == 0):
            data_loss_cases.append({
                'key': key,
                'api': api_count,
                'processed': processed_count,
                'features': feature_count
            })
    
    if data_loss_cases:
        print(f"\n⚠️ Найдено {len(data_loss_cases)} случаев потери данных:")
        for case in data_loss_cases[:10]:  # Показываем первые 10
            print(f"   {case['key']}: API {case['api']} → обработка {case['processed']} → признаки {case['features']}")

if __name__ == "__main__":
    debug_klines_processing()