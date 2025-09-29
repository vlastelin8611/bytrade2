#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка реальных ордеров в Bybit API
"""

import sys
import json
from src.api.bybit_client import BybitClient
from config import API_KEY, API_SECRET

def check_orders():
    """Проверка ордеров и исполнений"""
    try:
        client = BybitClient(API_KEY, API_SECRET, testnet=True)
        print('✅ API клиент создан успешно')
        
        # Тест соединения
        if client.test_connection():
            print('✅ Соединение с API работает')
        else:
            print('❌ Проблемы с соединением')
            return
            
        print('\n=== ПРОВЕРКА БАЛАНСА ===')
        balance = client.get_wallet_balance('UNIFIED')
        print(f'Баланс получен: {len(balance.get("list", []))} аккаунтов')
        
        # Показываем баланс USDT и других монет
        for account in balance.get('list', []):
            for coin in account.get('coin', []):
                if float(coin.get('walletBalance', 0)) > 0:
                    print(f"  {coin['coin']}: {coin['walletBalance']} (USD: {coin.get('usdValue', 'N/A')})")
        
        print('\n=== ПРОВЕРКА ИСТОРИИ ОРДЕРОВ ===')
        orders = client.get_order_history(category='spot', limit=20)
        print(f'История ордеров: {len(orders)} записей')
        
        if orders:
            print('Последние ордера:')
            for i, order in enumerate(orders[:5]):
                print(f"  {i+1}. {order.get('symbol', 'N/A')} - {order.get('side', 'N/A')} - {order.get('orderStatus', 'N/A')} - {order.get('qty', 'N/A')} - {order.get('createdTime', 'N/A')}")
        else:
            print('❌ Нет ордеров в истории')
        
        print('\n=== ПРОВЕРКА АКТИВНЫХ ОРДЕРОВ ===')
        active_orders = client.get_open_orders(category='spot')
        print(f'Активные ордера: {len(active_orders)} записей')
        
        if active_orders:
            for order in active_orders:
                print(f"  Активный: {order.get('symbol', 'N/A')} - {order.get('side', 'N/A')} - {order.get('qty', 'N/A')}")
        
        print('\n=== ПРОВЕРКА ИСПОЛНЕНИЙ ===')
        executions = client.get_execution_list(category='spot', limit=20)
        print(f'Исполнения: {len(executions)} записей')
        
        if executions:
            print('Последние исполнения:')
            for i, exec in enumerate(executions[:5]):
                print(f"  {i+1}. {exec.get('symbol', 'N/A')} - {exec.get('side', 'N/A')} - {exec.get('execQty', 'N/A')} - {exec.get('execPrice', 'N/A')} - {exec.get('execTime', 'N/A')}")
        else:
            print('❌ Нет исполнений')
            
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_orders()