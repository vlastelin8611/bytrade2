#!/usr/bin/env python3
"""
Тест API учетных данных и соединения с Bybit
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from config import get_api_credentials
from src.api.bybit_client import BybitClient
import json

def test_api_credentials():
    """Тестирование API учетных данных"""
    print("🔑 Тестирование API учетных данных")
    print("=" * 60)
    
    # Получаем учетные данные
    try:
        api_creds = get_api_credentials()
        print(f"✅ API ключи загружены:")
        print(f"   API Key: {api_creds['api_key'][:10]}...{api_creds['api_key'][-5:] if len(api_creds['api_key']) > 15 else api_creds['api_key']}")
        print(f"   API Secret: {api_creds['api_secret'][:10]}...{api_creds['api_secret'][-5:] if len(api_creds['api_secret']) > 15 else api_creds['api_secret']}")
        print(f"   Testnet: {api_creds['testnet']}")
        print()
    except Exception as e:
        print(f"❌ Ошибка загрузки API ключей: {e}")
        return
    
    # Проверяем длину ключей
    if len(api_creds['api_key']) < 20:
        print("⚠️ ВНИМАНИЕ: API ключ слишком короткий!")
    if len(api_creds['api_secret']) < 30:
        print("⚠️ ВНИМАНИЕ: API секрет слишком короткий!")
    
    # Инициализируем клиент
    try:
        client = BybitClient(
            api_creds['api_key'],
            api_creds['api_secret'],
            api_creds['testnet']
        )
        print("✅ BybitClient инициализирован")
    except Exception as e:
        print(f"❌ Ошибка инициализации BybitClient: {e}")
        return
    
    # Тестируем соединение
    print("\n🌐 Тестирование соединения...")
    
    # Тест 1: Получение времени сервера
    try:
        server_time = client._make_request('GET', '/v5/market/time')
        print(f"✅ Время сервера получено: {server_time}")
    except Exception as e:
        print(f"❌ Ошибка получения времени сервера: {e}")
    
    # Тест 2: Получение информации об аккаунте
    try:
        account_info = client._make_request('GET', '/v5/account/info')
        print(f"✅ Информация об аккаунте получена")
    except Exception as e:
        print(f"❌ Ошибка получения информации об аккаунте: {e}")
        print(f"   Это может указывать на неверные API ключи")
    
    # Тест 3: Получение списка символов
    try:
        symbols = client._make_request('GET', '/v5/market/instruments-info', {'category': 'spot'})
        if symbols and 'result' in symbols and 'list' in symbols['result']:
            symbol_count = len(symbols['result']['list'])
            print(f"✅ Получено {symbol_count} символов spot")
        else:
            print(f"⚠️ Неожиданный формат ответа символов: {symbols}")
    except Exception as e:
        print(f"❌ Ошибка получения символов: {e}")
    
    # Тест 4: Получение klines данных
    try:
        klines = client._make_request('GET', '/v5/market/kline', {
            'category': 'spot',
            'symbol': 'BTCUSDT',
            'interval': '240',
            'limit': 10
        })
        if klines and 'result' in klines and 'list' in klines['result']:
            klines_count = len(klines['result']['list'])
            print(f"✅ Получено {klines_count} klines для BTCUSDT")
            
            # Проверяем первую запись
            if klines_count > 0:
                first_kline = klines['result']['list'][0]
                print(f"   Первая запись: {first_kline}")
        else:
            print(f"⚠️ Неожиданный формат ответа klines: {klines}")
    except Exception as e:
        print(f"❌ Ошибка получения klines: {e}")
    
    print("\n📊 Тестирование завершено")

if __name__ == "__main__":
    test_api_credentials()