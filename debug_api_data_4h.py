#!/usr/bin/env python3
"""
Диагностика загрузки данных с API Bybit с интервалом 4h
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.api.bybit_client import BybitClient
    import config
except ImportError as e:
    print(f"Ошибка импорта модулей: {e}")
    sys.exit(1)

def test_api_data_loading():
    """Тестирование загрузки данных с API"""
    
    print("🔍 Диагностика загрузки данных с API Bybit (интервал 4h)")
    print("=" * 60)
    
    # Инициализация клиента
    try:
        bybit_client = BybitClient(
            api_key=config.API_KEY,
            api_secret=config.API_SECRET,
            testnet=config.USE_TESTNET
        )
        print("✅ BybitClient инициализирован")
    except Exception as e:
        print(f"❌ Ошибка инициализации BybitClient: {e}")
        return
    
    # Тестовые символы
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
    
    # Тестирование различных интервалов
    test_intervals = ['4h', '240', '1d', 'D']
    
    results = []
    
    print("\n📊 Тестирование различных символов с интервалом 4h:")
    print("-" * 50)
    
    for symbol in test_symbols:
        try:
            print(f"\n🔄 Тестирование {symbol}...")
            
            # Тест с интервалом 4h
            klines = bybit_client.get_klines(
                symbol=symbol,
                interval='4h',
                limit=500,
                category='spot'
            )
            
            if klines and 'list' in klines:
                count = len(klines['list'])
                print(f"  ✅ Получено {count} записей")
                results.append({
                    'symbol': symbol,
                    'interval': '4h',
                    'count': count,
                    'status': 'success'
                })
            else:
                print(f"  ❌ Пустой ответ")
                results.append({
                    'symbol': symbol,
                    'interval': '4h',
                    'count': 0,
                    'status': 'empty'
                })
                
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            results.append({
                'symbol': symbol,
                'interval': '4h',
                'count': -1,
                'status': 'error',
                'error': str(e)
            })
    
    print("\n📊 Тестирование различных интервалов для BTCUSDT:")
    print("-" * 50)
    
    for interval in test_intervals:
        try:
            print(f"\n🔄 Тестирование интервала {interval}...")
            
            klines = bybit_client.get_klines(
                symbol='BTCUSDT',
                interval=interval,
                limit=500,
                category='spot'
            )
            
            if klines and 'list' in klines:
                count = len(klines['list'])
                print(f"  ✅ Получено {count} записей")
                results.append({
                    'symbol': 'BTCUSDT',
                    'interval': interval,
                    'count': count,
                    'status': 'success'
                })
            else:
                print(f"  ❌ Пустой ответ")
                results.append({
                    'symbol': 'BTCUSDT',
                    'interval': interval,
                    'count': 0,
                    'status': 'empty'
                })
                
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            results.append({
                'symbol': 'BTCUSDT',
                'interval': interval,
                'count': -1,
                'status': 'error',
                'error': str(e)
            })
    
    print("\n📊 Тестирование различных лимитов для BTCUSDT (4h):")
    print("-" * 50)
    
    test_limits = [10, 50, 100, 200, 500, 1000]
    
    for limit in test_limits:
        try:
            print(f"\n🔄 Тестирование лимита {limit}...")
            
            klines = bybit_client.get_klines(
                symbol='BTCUSDT',
                interval='4h',
                limit=limit,
                category='spot'
            )
            
            if klines and 'list' in klines:
                count = len(klines['list'])
                print(f"  ✅ Получено {count} записей")
                results.append({
                    'symbol': 'BTCUSDT',
                    'interval': '4h',
                    'limit': limit,
                    'count': count,
                    'status': 'success'
                })
            else:
                print(f"  ❌ Пустой ответ")
                results.append({
                    'symbol': 'BTCUSDT',
                    'interval': '4h',
                    'limit': limit,
                    'count': 0,
                    'status': 'empty'
                })
                
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            results.append({
                'symbol': 'BTCUSDT',
                'interval': '4h',
                'limit': limit,
                'count': -1,
                'status': 'error',
                'error': str(e)
            })
    
    # Сохранение результатов
    with open('api_test_results_4h.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Статистика
    successful = len([r for r in results if r['status'] == 'success'])
    failed = len([r for r in results if r['status'] == 'error'])
    empty = len([r for r in results if r['status'] == 'empty'])
    
    print("\n" + "=" * 60)
    print("📈 ИТОГОВАЯ СТАТИСТИКА:")
    print(f"✅ Успешных запросов: {successful}")
    print(f"❌ Неудачных запросов: {failed}")
    print(f"⚪ Пустых ответов: {empty}")
    
    if successful > 0:
        successful_counts = [r['count'] for r in results if r['status'] == 'success']
        avg_count = sum(successful_counts) / len(successful_counts)
        print(f"📊 Среднее количество записей: {avg_count:.1f}")
        print(f"📊 Диапазон записей: {min(successful_counts)} - {max(successful_counts)}")
    
    print(f"💾 Результаты сохранены в api_test_results_4h.json")
    print("=" * 60)

if __name__ == "__main__":
    test_api_data_loading()