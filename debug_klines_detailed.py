#!/usr/bin/env python3
"""
Детальная отладка обработки klines данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from config import get_api_credentials
from src.api.bybit_client import BybitClient
import json

def debug_klines_detailed():
    """Детальная отладка klines"""
    print("🔍 Детальная отладка klines данных")
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
    
    # Тестируем разные способы получения данных
    symbol = "BTCUSDT"
    category = "spot"
    interval = "240"
    limit = 10
    
    print(f"\n📊 Тестируем {symbol} ({category}, {interval}, limit={limit})")
    print("-" * 50)
    
    # 1. Прямой вызов _make_request
    print("1️⃣ Прямой вызов _make_request:")
    try:
        raw_response = client._make_request('GET', '/v5/market/kline', {
            'category': category,
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        })
        print(f"   Тип ответа: {type(raw_response)}")
        print(f"   Ключи ответа: {list(raw_response.keys()) if isinstance(raw_response, dict) else 'Не словарь'}")
        
        if isinstance(raw_response, dict) and 'result' in raw_response:
            result = raw_response['result']
            print(f"   Тип result: {type(result)}")
            print(f"   Ключи result: {list(result.keys()) if isinstance(result, dict) else 'Не словарь'}")
            
            if isinstance(result, dict) and 'list' in result:
                klines_list = result['list']
                print(f"   Количество klines: {len(klines_list)}")
                if klines_list:
                    print(f"   Первая запись: {klines_list[0]}")
                    print(f"   Последняя запись: {klines_list[-1]}")
            else:
                print(f"   Нет 'list' в result: {result}")
        else:
            print(f"   Нет 'result' в ответе: {raw_response}")
            
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 2. Вызов через get_klines
    print("\n2️⃣ Вызов через get_klines:")
    try:
        klines_response = client.get_klines(
            category=category,
            symbol=symbol,
            interval=interval,
            limit=limit
        )
        print(f"   Тип ответа: {type(klines_response)}")
        print(f"   Содержимое: {klines_response}")
        
        # Проверяем, что возвращает get_klines
        if isinstance(klines_response, dict):
            print(f"   Ключи: {list(klines_response.keys())}")
            
            # Пытаемся извлечь данные как в trainer_console.py
            if 'result' in klines_response and 'list' in klines_response['result']:
                actual_klines = klines_response['result']['list']
                print(f"   Извлеченные klines: {len(actual_klines)} записей")
            else:
                print(f"   Не удалось извлечь klines из ответа")
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 3. Проверяем, как trainer_console.py обрабатывает ответ
    print("\n3️⃣ Симуляция обработки в trainer_console.py:")
    try:
        klines = client.get_klines(
            symbol=symbol,
            interval='4h',
            limit=1000,
            category=category
        )
        
        print(f"   Исходный ответ get_klines: тип={type(klines)}")
        
        # Проверяем условие из trainer_console.py: if klines and len(klines) > 0
        if klines and len(klines) > 0:
            print(f"   ✅ Условие 'klines and len(klines) > 0' выполнено: {len(klines)}")
        else:
            print(f"   ❌ Условие 'klines and len(klines) > 0' НЕ выполнено")
            print(f"       klines = {klines}")
            print(f"       len(klines) = {len(klines) if klines else 'klines is None/False'}")
        
        # Проверяем, что trainer_console.py ожидает список klines
        # Но get_klines возвращает словарь с результатом API
        if isinstance(klines, dict) and 'result' in klines and 'list' in klines['result']:
            actual_data = klines['result']['list']
            print(f"   📊 Фактические данные: {len(actual_data)} записей")
            print(f"   🔧 ПРОБЛЕМА: trainer_console.py ожидает список, но получает словарь!")
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print("\n🎯 ВЫВОДЫ:")
    print("=" * 60)
    print("1. API возвращает корректные данные в формате словаря")
    print("2. get_klines возвращает полный ответ API (словарь)")
    print("3. trainer_console.py ожидает список klines, но получает словарь")
    print("4. Нужно исправить обработку ответа в trainer_console.py")

if __name__ == "__main__":
    debug_klines_detailed()