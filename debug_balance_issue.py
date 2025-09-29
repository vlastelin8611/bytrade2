#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отладка проблемы с получением баланса
====================================
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from api.bybit_client import BybitClient
import config
import json

def debug_balance_issue():
    """Детальная отладка проблемы с балансом"""
    try:
        # Инициализация клиента
        client = BybitClient(
            api_key=config.API_KEY,
            api_secret=config.API_SECRET,
            testnet=config.USE_TESTNET
        )
        
        print("=== ОТЛАДКА ПРОБЛЕМЫ С БАЛАНСОМ ===\n")
        
        # 1. Прямой запрос к API
        print("1. Прямой запрос к API wallet-balance:")
        try:
            raw_response = client._make_request('GET', '/v5/account/wallet-balance', {'accountType': 'UNIFIED'})
            print(f"Сырой ответ API:")
            print(json.dumps(raw_response, indent=2, ensure_ascii=False))
            
            # Проверяем структуру ответа
            if 'result' in raw_response and 'list' in raw_response['result']:
                accounts = raw_response['result']['list']
                print(f"\nНайдено аккаунтов: {len(accounts)}")
                
                for i, account in enumerate(accounts):
                    print(f"\nАккаунт {i+1}:")
                    print(f"  Тип: {account.get('accountType', 'Unknown')}")
                    print(f"  Общий баланс: {account.get('totalWalletBalance', '0')}")
                    print(f"  Доступный баланс: {account.get('totalAvailableBalance', '0')}")
                    print(f"  Общий капитал: {account.get('totalEquity', '0')}")
                    
                    coins = account.get('coin', [])
                    print(f"  Монет: {len(coins)}")
                    
                    for coin in coins:
                        balance = float(coin.get('walletBalance', 0))
                        if balance > 0:
                            print(f"    {coin.get('coin')}: {balance} (USD: {coin.get('usdValue', '0')})")
            else:
                print("❌ Некорректная структура ответа API")
                
        except Exception as e:
            print(f"❌ Ошибка прямого запроса: {e}")
        
        # 2. Через метод get_wallet_balance
        print("\n2. Через метод get_wallet_balance:")
        try:
            balance = client.get_wallet_balance()
            print(f"Результат get_wallet_balance:")
            print(json.dumps(balance, indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            print(f"❌ Ошибка get_wallet_balance: {e}")
        
        # 3. Через метод get_unified_balance_flat
        print("\n3. Через метод get_unified_balance_flat:")
        try:
            flat_balance = client.get_unified_balance_flat()
            print(f"Результат get_unified_balance_flat:")
            print(json.dumps(flat_balance, indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            print(f"❌ Ошибка get_unified_balance_flat: {e}")
        
        # 4. Проверяем подключение к API
        print("\n4. Проверка подключения к API:")
        try:
            server_time = client._make_request('GET', '/v5/market/time', {})
            print(f"Время сервера: {server_time}")
            print("✅ Подключение к API работает")
        except Exception as e:
            print(f"❌ Ошибка подключения к API: {e}")
        
        # 5. Проверяем права API ключа
        print("\n5. Проверка прав API ключа:")
        try:
            # Пробуем получить информацию об аккаунте
            account_info = client._make_request('GET', '/v5/account/info', {})
            print(f"Информация об аккаунте:")
            print(json.dumps(account_info, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"❌ Ошибка получения информации об аккаунте: {e}")
            print("Возможно, у API ключа недостаточно прав")
        
        return True
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_balance_issue()