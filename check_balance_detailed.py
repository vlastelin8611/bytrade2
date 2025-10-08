#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Детальная проверка баланса с выводом всех данных
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from api.bybit_client import BybitClient
from config import get_api_credentials
import json

def check_detailed_balance():
    """Детальная проверка баланса"""
    print("=== Детальная проверка баланса ===")
    
    # Получение API ключей
    credentials = get_api_credentials()
    api_key = credentials['api_key']
    api_secret = credentials['api_secret']
    print(f"API Key: {api_key[:10]}...")
    print(f"Testnet: {credentials['testnet']}")
    
    # Инициализация клиента
    client = BybitClient(api_key, api_secret)
    
    try:
        # Проверка подключения
        print("\n🔍 Проверка подключения к API...")
        server_time = client.get_server_time()
        print(f"Время сервера: {server_time}")
        
        # Тест 1: UNIFIED баланс
        print("\n💰 1. Получение UNIFIED баланса:")
        unified_balance = client.get_wallet_balance("UNIFIED")
        print(f"Код ответа: {unified_balance.get('retCode', 'N/A')}")
        print(f"Сообщение: {unified_balance.get('retMsg', 'N/A')}")
        
        if unified_balance.get('retCode') == 0 and unified_balance.get('result'):
            result = unified_balance['result']
            if 'list' in result and result['list']:
                account = result['list'][0]
                print(f"   Тип аккаунта: {account.get('accountType', 'N/A')}")
                print(f"   Общий баланс: {account.get('totalEquity', '0')} USDT")
                print(f"   Доступно для торговли: {account.get('totalAvailableBalance', '0')} USDT")
                
                if 'coin' in account and account['coin']:
                    print("   Монеты:")
                    for coin_info in account['coin']:
                        balance = float(coin_info.get('walletBalance', '0'))
                        if balance > 0:
                            print(f"     {coin_info.get('coin', 'N/A')}: {balance}")
        else:
            print(f"   ❌ Ошибка: {unified_balance}")
        
        # Тест 2: SPOT баланс
        print("\n💰 2. Получение SPOT баланса:")
        spot_balance = client.get_wallet_balance("SPOT")
        print(f"Код ответа: {spot_balance.get('retCode', 'N/A')}")
        print(f"Сообщение: {spot_balance.get('retMsg', 'N/A')}")
        
        if spot_balance.get('retCode') == 0 and spot_balance.get('result'):
            result = spot_balance['result']
            if 'list' in result and result['list']:
                account = result['list'][0]
                print(f"   Тип аккаунта: {account.get('accountType', 'N/A')}")
                
                if 'coin' in account and account['coin']:
                    print("   Монеты:")
                    for coin_info in account['coin']:
                        balance = float(coin_info.get('walletBalance', '0'))
                        if balance > 0:
                            print(f"     {coin_info.get('coin', 'N/A')}: {balance}")
        else:
            print(f"   ❌ Ошибка: {spot_balance}")
        
        # Тест 3: Информация об аккаунте
        print("\n📊 3. Информация об аккаунте:")
        account_info = client.get_account_info()
        print(f"Код ответа: {account_info.get('retCode', 'N/A')}")
        print(f"Сообщение: {account_info.get('retMsg', 'N/A')}")
        
        if account_info.get('retCode') == 0 and account_info.get('result'):
            result = account_info['result']
            print(f"   Статус маржи: {result.get('marginMode', 'N/A')}")
            print(f"   Обновлено: {result.get('updatedTime', 'N/A')}")
        
        print("\n✅ Проверка баланса завершена")
        
    except Exception as e:
        print(f"\n❌ Ошибка при проверке баланса: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_detailed_balance()