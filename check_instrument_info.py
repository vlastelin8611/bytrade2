#!/usr/bin/env python3
"""
Скрипт для проверки минимальных требований к ордерам на Bybit testnet
"""

import os
import sys
from pybit.unified_trading import HTTP
import json

# Добавляем путь к модулям проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import API_KEY, API_SECRET, USE_TESTNET

def check_instrument_info():
    """Проверяет минимальные требования к ордерам для различных символов"""
    
    # Инициализируем клиент API
    session = HTTP(
        testnet=USE_TESTNET,
        api_key=API_KEY,
        api_secret=API_SECRET,
    )
    
    # Список символов для проверки
    symbols = ['BTCUSDT', 'ETHUSDT', 'USDCUSDT', 'BNBUSDT', 'SOLUSDT', 'LINKUSDT']
    
    print(f"Проверяем минимальные требования к ордерам на {'testnet' if USE_TESTNET else 'mainnet'}:")
    print("=" * 80)
    
    for symbol in symbols:
        try:
            # Получаем информацию об инструменте
            response = session.get_instruments_info(
                category="spot",
                symbol=symbol
            )
            
            if response['retCode'] == 0 and response['result']['list']:
                instrument = response['result']['list'][0]
                
                # Извлекаем информацию о минимальных требованиях
                lot_size_filter = instrument.get('lotSizeFilter', {})
                min_order_qty = lot_size_filter.get('minOrderQty', 'N/A')
                min_order_amt = lot_size_filter.get('minOrderAmt', 'N/A')
                qty_step = lot_size_filter.get('qtyStep', 'N/A')
                
                print(f"\n{symbol}:")
                print(f"  Минимальное количество (minOrderQty): {min_order_qty}")
                print(f"  Минимальная стоимость (minOrderAmt): {min_order_amt}")
                print(f"  Шаг количества (qtyStep): {qty_step}")
                
                # Дополнительная информация
                price_filter = instrument.get('priceFilter', {})
                tick_size = price_filter.get('tickSize', 'N/A')
                print(f"  Шаг цены (tickSize): {tick_size}")
                
            else:
                print(f"\n{symbol}: Ошибка получения данных - {response.get('retMsg', 'Unknown error')}")
                
        except Exception as e:
            print(f"\n{symbol}: Исключение - {str(e)}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    check_instrument_info()