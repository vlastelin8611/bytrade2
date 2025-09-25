#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки функциональности получения баланса
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from api.bybit_client import BybitClient
from config import API_KEY, API_SECRET

def test_balance_functionality():
    """Тестирование функциональности получения баланса"""
    print("=== Тестирование получения баланса ===")
    
    # Инициализация клиента
    client = BybitClient(API_KEY, API_SECRET)
    
    try:
        # Тест 1: Получение UNIFIED баланса
        print("\n1. Тестирование get_wallet_balance (UNIFIED):")
        unified_balance = client.get_wallet_balance("UNIFIED")
        print(f"Статус: {unified_balance.get('retCode', 'N/A')}")
        print(f"Сообщение: {unified_balance.get('retMsg', 'N/A')}")
        
        if unified_balance.get('result'):
            result = unified_balance['result']
            if 'list' in result and result['list']:
                account = result['list'][0]
                print(f"Тип аккаунта: {account.get('accountType', 'N/A')}")
                if 'coin' in account and account['coin']:
                    for coin_info in account['coin'][:3]:  # Показать первые 3 монеты
                        print(f"  {coin_info.get('coin', 'N/A')}: {coin_info.get('walletBalance', '0')}")
        
        # Тест 2: Получение FUND баланса
        print("\n2. Тестирование get_fund_balance:")
        fund_balance = client.get_fund_balance()
        print(f"Статус: {fund_balance.get('retCode', 'N/A')}")
        print(f"Сообщение: {fund_balance.get('retMsg', 'N/A')}")
        
        if fund_balance.get('result'):
            result = fund_balance['result']
            if 'balance' in result and result['balance']:
                for coin_info in result['balance'][:3]:  # Показать первые 3 монеты
                    print(f"  {coin_info.get('coin', 'N/A')}: {coin_info.get('transferBalance', '0')}")
        
        # Тест 3: Получение списка монет для перевода
        print("\n3. Тестирование get_transfer_coin_list:")
        transfer_coins = client.get_transfer_coin_list()
        print(f"Статус: {transfer_coins.get('retCode', 'N/A')}")
        print(f"Сообщение: {transfer_coins.get('retMsg', 'N/A')}")
        
        if transfer_coins.get('result'):
            result = transfer_coins['result']
            if 'list' in result and result['list']:
                print(f"Доступно монет для перевода: {len(result['list'])}")
                for coin_info in result['list'][:5]:  # Показать первые 5 монет
                    print(f"  {coin_info.get('coin', 'N/A')}")
        
        print("\n=== Тестирование завершено успешно ===")
        
    except Exception as e:
        print(f"\nОшибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_balance_functionality()