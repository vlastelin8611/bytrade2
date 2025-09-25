#!/usr/bin/env python3
"""
Отладочный скрипт для проверки получения klines данных
"""

from config import get_api_credentials
from src.api.bybit_client import BybitClient
import json

def debug_klines():
    """Отладка получения klines данных"""
    
    # Получаем API credentials
    api_creds = get_api_credentials()
    print(f'API ключи загружены: testnet={api_creds["testnet"]}')

    # Инициализируем клиент
    client = BybitClient(api_creds['api_key'], api_creds['api_secret'], api_creds['testnet'])

    # Тестируем несколько популярных символов
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT']
    
    for symbol in test_symbols:
        print(f'\n=== Тестируем {symbol} ===')
        
        # Пробуем spot категорию
        print(f'Пробуем spot категорию для {symbol}...')
        try:
            response = client.get_klines(category='spot', symbol=symbol, interval='60', limit=10)
            print(f'Ответ API (spot): {json.dumps(response, indent=2)[:500]}...')
            
            if response and 'list' in response and response['list']:
                klines_data = response['list']
                print(f'✅ Получено {len(klines_data)} свечей (spot)')
                
                # Проверяем формат данных
                if klines_data:
                    first_kline = klines_data[0]
                    print(f'Формат первой свечи: {first_kline}')
                    
                    # Пробуем преобразовать в нужный формат
                    try:
                        converted = {
                            'open': float(first_kline[1]),
                            'high': float(first_kline[2]), 
                            'low': float(first_kline[3]),
                            'close': float(first_kline[4]),
                            'volume': float(first_kline[5])
                        }
                        print(f'✅ Преобразование успешно: {converted}')
                    except Exception as conv_e:
                        print(f'❌ Ошибка преобразования: {conv_e}')
            else:
                print('❌ Данные не получены (spot)')
                
        except Exception as e:
            print(f'❌ Ошибка spot: {e}')
        
        # Пробуем linear категорию
        print(f'Пробуем linear категорию для {symbol}...')
        try:
            response = client.get_klines(category='linear', symbol=symbol, interval='60', limit=10)
            print(f'Ответ API (linear): {json.dumps(response, indent=2)[:500]}...')
            
            if response and 'list' in response and response['list']:
                klines_data = response['list']
                print(f'✅ Получено {len(klines_data)} свечей (linear)')
            else:
                print('❌ Данные не получены (linear)')
                
        except Exception as e:
            print(f'❌ Ошибка linear: {e}')

if __name__ == "__main__":
    debug_klines()