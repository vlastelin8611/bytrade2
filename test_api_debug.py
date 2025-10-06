#!/usr/bin/env python3
"""
Тест API подключения для отладки проблем с балансом
"""

import sys
import os
sys.path.append('src')

from api.bybit_client import BybitClient
from config import get_api_credentials

def test_api_connection():
    """Тестирование API подключения"""
    print("=== Тест API подключения ===")
    
    try:
        # Загружаем API ключи
        credentials = get_api_credentials()
        api_key = credentials['api_key']
        api_secret = credentials['api_secret']
        testnet = credentials['testnet']
        print(f"✅ API ключи загружены")
        print(f"API Key: {api_key[:10]}...")
        print(f"🔗 Режим: {'Testnet' if testnet else 'Mainnet'}")
        
        # Создаем клиент
        client = BybitClient(api_key, api_secret, testnet=testnet)
        print(f"✅ API клиент создан")
        
        # Тестируем время сервера
        print("\n=== Тест времени сервера ===")
        server_time = client._get_server_time_raw()
        print(f"Время сервера: {server_time}")
        
        # Тестируем прямой запрос баланса
        print("\n=== Тест прямого запроса баланса ===")
        raw_balance = client._make_request('GET', '/v5/account/wallet-balance', {'accountType': 'UNIFIED'})
        print(f"Сырой ответ API:")
        print(f"  Тип: {type(raw_balance)}")
        print(f"  Содержимое: {raw_balance}")
        
        if raw_balance and isinstance(raw_balance, dict):
            print(f"\n=== Анализ ответа ===")
            print(f"Код ответа: {raw_balance.get('retCode', 'не указан')}")
            print(f"Сообщение: {raw_balance.get('retMsg', 'не указано')}")
            
            if 'result' in raw_balance:
                result = raw_balance['result']
                print(f"Результат: {result}")
                
                if 'list' in result:
                    accounts = result['list']
                    print(f"Количество аккаунтов: {len(accounts)}")
                    
                    if accounts:
                        acc = accounts[0]
                        print(f"Первый аккаунт:")
                        print(f"  Общий баланс: {acc.get('totalWalletBalance', '0')} USD")
                        print(f"  Доступный баланс: {acc.get('totalAvailableBalance', '0')} USD")
                        
                        coins = acc.get('coin', [])
                        print(f"  Количество монет: {len(coins)}")
                        
                        for i, coin in enumerate(coins[:5]):  # Показываем первые 5 монет
                            coin_name = coin.get('coin', '?')
                            wallet_balance = coin.get('walletBalance', '0')
                            usd_value = coin.get('usdValue', '0')
                            print(f"    {i+1}. {coin_name}: {wallet_balance} (${usd_value})")
                    else:
                        print("  Список аккаунтов пуст")
                else:
                    print("  Нет поля 'list' в результате")
            else:
                print("  Нет поля 'result' в ответе")
        else:
            print("❌ Получен некорректный ответ API")
            
        # Тестируем метод get_unified_balance_flat
        print("\n=== Тест get_unified_balance_flat ===")
        flat_balance = client.get_unified_balance_flat()
        print(f"Плоский баланс: {flat_balance}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_connection()