#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка спотовых позиций на Bybit
==================================

Скрипт для диагностики проблем с отображением спотовых позиций
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from api.bybit_client import BybitClient
import config

def check_spot_positions():
    """Проверка спотовых позиций и баланса"""
    try:
        # Инициализация клиента
        client = BybitClient(
            api_key=config.API_KEY,
            api_secret=config.API_SECRET,
            testnet=config.USE_TESTNET
        )
        
        print("=== ПРОВЕРКА СПОТОВЫХ ПОЗИЦИЙ ===\n")
        
        # 1. Проверяем баланс кошелька
        print("1. Баланс кошелька (UNIFIED):")
        balance = client.get_wallet_balance()
        print(f"Общий баланс: ${balance.get('total_wallet_usd', 0)}")
        print(f"Доступный баланс: ${balance.get('total_available_usd', 0)}")
        
        coins = balance.get('coins', [])
        print(f"\nМонеты в балансе ({len(coins)}):")
        for coin in coins:
            if float(coin.get('walletBalance', 0)) > 0:
                print(f"  {coin.get('coin')}: {coin.get('walletBalance')} (USD: {coin.get('usdValue', 0)})")
        
        # 2. Проверяем спотовые ордера
        print("\n2. Активные спотовые ордера:")
        try:
            orders = client.get_open_orders(category='spot')
            print(f"Найдено активных ордеров: {len(orders)}")
            for order in orders[:5]:  # Показываем первые 5
                print(f"  {order.get('symbol')}: {order.get('side')} {order.get('qty')} @ {order.get('price', 'Market')}")
        except Exception as e:
            print(f"Ошибка получения ордеров: {e}")
        
        # 3. Проверяем историю ордеров (недавние)
        print("\n3. История ордеров (последние 10):")
        try:
            history = client.get_order_history(category='spot', limit=10)
            print(f"Найдено ордеров в истории: {len(history)}")
            for order in history:
                status = order.get('orderStatus', 'Unknown')
                symbol = order.get('symbol', 'Unknown')
                side = order.get('side', 'Unknown')
                qty = order.get('qty', '0')
                filled_qty = order.get('cumExecQty', '0')
                print(f"  {symbol}: {side} {qty} - {status} (исполнено: {filled_qty})")
        except Exception as e:
            print(f"Ошибка получения истории: {e}")
        
        # 4. Проверяем исполненные сделки
        print("\n4. Исполненные сделки (последние 10):")
        try:
            executions = client.get_execution_list(category='spot', limit=10)
            print(f"Найдено исполненных сделок: {len(executions)}")
            for execution in executions:
                symbol = execution.get('symbol', 'Unknown')
                side = execution.get('side', 'Unknown')
                qty = execution.get('execQty', '0')
                price = execution.get('execPrice', '0')
                time = execution.get('execTime', '0')
                print(f"  {symbol}: {side} {qty} @ {price} (время: {time})")
        except Exception as e:
            print(f"Ошибка получения сделок: {e}")
        
        # 5. Анализируем спотовые позиции из баланса
        print("\n5. Анализ спотовых позиций:")
        spot_positions = []
        for coin in coins:
            balance_amount = float(coin.get('walletBalance', 0))
            if balance_amount > 0 and coin.get('coin') != 'USDT':
                usd_value = float(coin.get('usdValue', 0))
                spot_positions.append({
                    'coin': coin.get('coin'),
                    'balance': balance_amount,
                    'usd_value': usd_value,
                    'price': usd_value / balance_amount if balance_amount > 0 else 0
                })
        
        print(f"Найдено спотовых позиций: {len(spot_positions)}")
        for pos in spot_positions:
            print(f"  {pos['coin']}: {pos['balance']:.6f} (${pos['usd_value']:.2f}) @ ${pos['price']:.2f}")
        
        # 6. Находим самую дешевую позицию
        if spot_positions:
            cheapest = min(spot_positions, key=lambda x: x['usd_value'])
            print(f"\n6. Самая дешевая позиция:")
            print(f"  {cheapest['coin']}: ${cheapest['usd_value']:.2f}")
            
            # Проверяем минимальные лимиты для продажи
            symbol = f"{cheapest['coin']}USDT"
            print(f"\n7. Проверка лимитов для {symbol}:")
            try:
                import requests
                response = requests.get(f'https://api-testnet.bybit.com/v5/market/instruments-info?category=spot&symbol={symbol}')
                data = response.json()
                if 'result' in data and 'list' in data['result'] and len(data['result']['list']) > 0:
                    instrument = data['result']['list'][0]
                    lot_filter = instrument.get('lotSizeFilter', {})
                    print(f"  Минимальное количество: {lot_filter.get('minOrderQty', 'N/A')}")
                    print(f"  Минимальная сумма: {lot_filter.get('minOrderAmt', 'N/A')}")
                    print(f"  Шаг количества: {lot_filter.get('qtyStep', 'N/A')}")
                else:
                    print(f"  Информация о лимитах недоступна")
            except Exception as e:
                print(f"  Ошибка получения лимитов: {e}")
        else:
            print("\n6. Спотовых позиций не найдено (кроме USDT)")
        
        return spot_positions
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    positions = check_spot_positions()
    print(f"\n=== ИТОГО: Найдено {len(positions)} спотовых позиций ===")