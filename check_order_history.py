#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка истории ордеров на Bybit testnet
Для проверки правильности исправления точности количества
"""

from src.api.bybit_client import BybitClient
from config import API_KEY, API_SECRET
from datetime import datetime, timedelta
import json

def check_order_history():
    """Проверяем историю ордеров на testnet"""
    print("=== Проверка истории ордеров Bybit testnet ===")
    
    try:
        # Инициализируем клиент
        client = BybitClient(API_KEY, API_SECRET)
        
        # Получаем историю ордеров за последние 7 дней
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
        
        print(f"Запрашиваем ордера с {datetime.fromtimestamp(start_time/1000)} по {datetime.fromtimestamp(end_time/1000)}")
        
        # Получаем историю ордеров
        response = client.get_order_history(
            category="spot",
            limit=50
        )
        
        if response:
            orders = response
            print(f"\nНайдено ордеров: {len(orders)}")
            
            if orders:
                print("\n--- Последние ордера ---")
                for i, order in enumerate(orders[:10]):  # Показываем первые 10
                    print(f"\n{i+1}. Ордер ID: {order.get('orderId', 'N/A')}")
                    print(f"   Символ: {order.get('symbol', 'N/A')}")
                    print(f"   Сторона: {order.get('side', 'N/A')}")
                    print(f"   Количество: {order.get('qty', 'N/A')}")
                    print(f"   Цена: {order.get('price', 'N/A')}")
                    print(f"   Статус: {order.get('orderStatus', 'N/A')}")
                    print(f"   Время: {datetime.fromtimestamp(int(order.get('createdTime', 0))/1000)}")
                    
                    # Проверяем точность количества
                    qty = order.get('qty', '0')
                    if '.' in qty:
                        decimal_places = len(qty.split('.')[1].rstrip('0'))
                        print(f"   Десятичных знаков в количестве: {decimal_places}")
            else:
                print("Ордеров не найдено")
        else:
            print("Ошибка получения истории ордеров")
            print(f"Ответ: {response}")
            
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

def check_wallet_balance():
    """Проверяем баланс кошелька"""
    print("\n=== Проверка баланса кошелька ===")
    
    try:
        client = BybitClient(API_KEY, API_SECRET)
        
        # Получаем баланс spot кошелька
        response = client.get_wallet_balance(account_type="SPOT")
        
        if response and 'result' in response:
            balances = response['result']['list']
            print(f"Найдено аккаунтов: {len(balances)}")
            
            for account in balances:
                coins = account.get('coin', [])
                print(f"\nАккаунт: {account.get('accountType', 'N/A')}")
                
                for coin in coins:
                    balance = float(coin.get('walletBalance', '0'))
                    if balance > 0:
                        print(f"  {coin.get('coin', 'N/A')}: {balance}")
        else:
            print("Ошибка получения баланса")
            print(f"Ответ: {response}")
            
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_order_history()
    check_wallet_balance()