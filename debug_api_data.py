#!/usr/bin/env python3
"""
Скрипт для диагностики проблем с загрузкой исторических данных через Bybit API
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import config
from src.api.bybit_client import BybitClient
import json
import time

def test_api_data_loading():
    """Тестирование загрузки данных через API"""
    print("🔍 Диагностика загрузки данных через Bybit API")
    print("=" * 60)
    
    # Загружаем конфигурацию
    try:
        api_key = config.API_KEY
        api_secret = config.API_SECRET
        testnet = config.USE_TESTNET
        
        if not api_key or not api_secret:
            print("❌ API ключи не найдены в конфигурации")
            return
            
        print(f"✅ API ключи загружены (testnet: {testnet})")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        return
    
    # Создаем клиент API
    try:
        client = BybitClient(api_key, api_secret, testnet=testnet)
        print("✅ Клиент API создан")
    except Exception as e:
        print(f"❌ Ошибка создания клиента API: {e}")
        return
    
    # Тестовые символы
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
    
    # Тестовые интервалы
    test_intervals = ['1', '5', '15', '60', '240', 'D']
    
    # Тестовые лимиты
    test_limits = [10, 50, 100, 200, 500, 1000]
    
    print("\n📊 Тестирование различных параметров запроса:")
    print("-" * 60)
    
    results = {}
    
    # Тест 1: Разные символы с базовыми параметрами
    print("\n🔸 Тест 1: Разные символы (интервал=60, лимит=200)")
    for symbol in test_symbols:
        try:
            result = client.get_klines(
                category='spot',
                symbol=symbol,
                interval='60',
                limit=200
            )
            
            if result and 'list' in result:
                count = len(result['list'])
                print(f"  {symbol}: {count} записей")
                results[f"{symbol}_basic"] = count
            else:
                print(f"  {symbol}: Нет данных")
                results[f"{symbol}_basic"] = 0
                
        except Exception as e:
            print(f"  {symbol}: Ошибка - {e}")
            results[f"{symbol}_basic"] = -1
        
        time.sleep(0.1)  # Небольшая задержка между запросами
    
    # Тест 2: Разные интервалы для BTCUSDT
    print("\n🔸 Тест 2: Разные интервалы для BTCUSDT (лимит=200)")
    for interval in test_intervals:
        try:
            result = client.get_klines(
                category='spot',
                symbol='BTCUSDT',
                interval=interval,
                limit=200
            )
            
            if result and 'list' in result:
                count = len(result['list'])
                print(f"  Интервал {interval}: {count} записей")
                results[f"BTCUSDT_interval_{interval}"] = count
            else:
                print(f"  Интервал {interval}: Нет данных")
                results[f"BTCUSDT_interval_{interval}"] = 0
                
        except Exception as e:
            print(f"  Интервал {interval}: Ошибка - {e}")
            results[f"BTCUSDT_interval_{interval}"] = -1
        
        time.sleep(0.1)
    
    # Тест 3: Разные лимиты для BTCUSDT
    print("\n🔸 Тест 3: Разные лимиты для BTCUSDT (интервал=60)")
    for limit in test_limits:
        try:
            result = client.get_klines(
                category='spot',
                symbol='BTCUSDT',
                interval='60',
                limit=limit
            )
            
            if result and 'list' in result:
                count = len(result['list'])
                print(f"  Лимит {limit}: {count} записей")
                results[f"BTCUSDT_limit_{limit}"] = count
            else:
                print(f"  Лимит {limit}: Нет данных")
                results[f"BTCUSDT_limit_{limit}"] = 0
                
        except Exception as e:
            print(f"  Лимит {limit}: Ошибка - {e}")
            results[f"BTCUSDT_limit_{limit}"] = -1
        
        time.sleep(0.1)
    
    # Тест 4: Проверка формата ответа
    print("\n🔸 Тест 4: Детальный анализ ответа API")
    try:
        result = client.get_klines(
            category='spot',
            symbol='BTCUSDT',
            interval='60',
            limit=10
        )
        
        print(f"  Тип результата: {type(result)}")
        print(f"  Ключи в результате: {list(result.keys()) if isinstance(result, dict) else 'Не словарь'}")
        
        if result and 'list' in result:
            klines = result['list']
            print(f"  Количество записей: {len(klines)}")
            
            if klines:
                print(f"  Формат первой записи: {klines[0]}")
                print(f"  Длина первой записи: {len(klines[0]) if isinstance(klines[0], (list, tuple)) else 'Не список'}")
        
        # Сохраняем полный ответ для анализа
        with open('api_response_sample.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("  ✅ Образец ответа сохранен в api_response_sample.json")
        
    except Exception as e:
        print(f"  ❌ Ошибка детального анализа: {e}")
    
    # Тест 5: Проверка с временными параметрами
    print("\n🔸 Тест 5: Запрос с временными параметрами")
    try:
        # Запрос данных за последние 24 часа
        end_time = int(time.time() * 1000)
        start_time = end_time - (24 * 60 * 60 * 1000)  # 24 часа назад
        
        result = client.get_klines(
            category='spot',
            symbol='BTCUSDT',
            interval='60',
            limit=200,
            start=start_time,
            end=end_time
        )
        
        if result and 'list' in result:
            count = len(result['list'])
            print(f"  С временными параметрами: {count} записей")
            results['BTCUSDT_with_time'] = count
        else:
            print(f"  С временными параметрами: Нет данных")
            results['BTCUSDT_with_time'] = 0
            
    except Exception as e:
        print(f"  С временными параметрами: Ошибка - {e}")
        results['BTCUSDT_with_time'] = -1
    
    # Сводка результатов
    print("\n📋 Сводка результатов:")
    print("=" * 60)
    
    successful_requests = sum(1 for v in results.values() if v > 0)
    failed_requests = sum(1 for v in results.values() if v == -1)
    empty_requests = sum(1 for v in results.values() if v == 0)
    
    print(f"✅ Успешных запросов: {successful_requests}")
    print(f"❌ Неудачных запросов: {failed_requests}")
    print(f"⚠️ Пустых ответов: {empty_requests}")
    
    # Анализ количества записей
    successful_counts = [v for v in results.values() if v > 0]
    if successful_counts:
        print(f"\n📊 Статистика по количеству записей:")
        print(f"  Минимум: {min(successful_counts)}")
        print(f"  Максимум: {max(successful_counts)}")
        print(f"  Среднее: {sum(successful_counts) / len(successful_counts):.1f}")
    
    # Сохраняем результаты
    with open('api_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Результаты сохранены в api_test_results.json")
    
    # Рекомендации
    print("\n💡 Рекомендации:")
    print("-" * 60)
    
    if all(v <= 3 for v in successful_counts if v > 0):
        print("⚠️ Все запросы возвращают очень мало данных (≤3 записи)")
        print("   Возможные причины:")
        print("   - Ограничения testnet API")
        print("   - Неправильные параметры запроса")
        print("   - Проблемы с аутентификацией")
        print("   - Ограничения для новых символов")
    
    if failed_requests > successful_requests:
        print("⚠️ Много неудачных запросов")
        print("   Проверьте:")
        print("   - Правильность API ключей")
        print("   - Доступность API")
        print("   - Лимиты запросов")

if __name__ == "__main__":
    test_api_data_loading()