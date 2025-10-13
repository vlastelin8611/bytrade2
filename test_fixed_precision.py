#!/usr/bin/env python3
"""
Тест исправленной логики расчета количества для ордеров
Проверяем, что новая логика правильно обрабатывает научную нотацию в qtyStep
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.bybit_client import BybitClient
from decimal import Decimal
import math

def get_precision_decimals(qty_step):
    """Правильно определяем количество десятичных знаков в qty_step"""
    decimal_step = Decimal(str(qty_step))
    step_str = format(decimal_step, 'f')
    step_str = step_str.rstrip('0').rstrip('.')
    
    if '.' in step_str:
        precision_decimals = len(step_str.split('.')[1])
    else:
        precision_decimals = 0
    
    return precision_decimals

def round_quantity_properly(qty, qty_step):
    """Правильно округляем количество согласно qtyStep"""
    if qty_step > 0:
        precision_decimals = get_precision_decimals(qty_step)
        qty_rounded = math.floor(qty / qty_step) * qty_step
        qty_final = round(qty_rounded, precision_decimals)
        return qty_final, precision_decimals
    return qty, 0

def test_fixed_precision():
    """Тестируем исправленную логику расчета количества"""
    print("=== Тест исправленной логики расчета количества ===")
    
    # Инициализируем клиент с API ключами из config
    from config import API_KEY, API_SECRET
    client = BybitClient(API_KEY, API_SECRET)
    
    # Тестовые символы
    symbols = ['ETHUSDT', 'BTCUSDT', 'XRPUSDT']
    order_value = 50.0  # $50 для тестирования
    
    for symbol in symbols:
        print(f"\n--- Тестирование {symbol} ---")
        
        try:
            # Получаем информацию об инструменте
            instruments = client.get_instruments_info(category='spot', symbol=symbol)
            if not instruments:
                print(f"❌ Не удалось получить информацию об инструменте {symbol}")
                continue
                
            instrument_info = instruments[0]
            lot_size_filter = instrument_info.get('lotSizeFilter', {})
            
            min_order_qty = float(lot_size_filter.get('minOrderQty', 0))
            qty_step = float(lot_size_filter.get('qtyStep', 0))
            min_order_amt = float(lot_size_filter.get('minOrderAmt', 0))
            
            # Получаем текущую цену
            ticker = client.get_tickers(category='spot', symbol=symbol)
            if not ticker or 'list' not in ticker or not ticker['list']:
                print(f"❌ Не удалось получить цену для {symbol}")
                continue
                
            current_price = float(ticker['list'][0]['lastPrice'])
            
            # Рассчитываем количество
            qty = order_value / current_price
            
            print(f"Исходные данные:")
            print(f"  minOrderQty: {min_order_qty}")
            print(f"  qtyStep: {qty_step}")
            print(f"  minOrderAmt: {min_order_amt}")
            print(f"  Цена: ${current_price}")
            print(f"  Исходное qty: {qty}")
            
            # Применяем исправленную логику
            qty_fixed, precision = round_quantity_properly(qty, qty_step)
            
            print(f"Исправленная логика:")
            print(f"  Точность (десятичных знаков): {precision}")
            print(f"  Округленное qty: {qty_fixed}")
            print(f"  qty как строка: '{qty_fixed}'")
            print(f"  Стоимость: ${qty_fixed * current_price:.2f}")
            
            # Проверяем соответствие минимальным требованиям
            if qty_fixed < min_order_qty:
                print(f"  ⚠️ qty меньше minOrderQty")
            else:
                print(f"  ✅ qty соответствует minOrderQty")
                
            if qty_fixed * current_price < min_order_amt:
                print(f"  ⚠️ Стоимость меньше minOrderAmt")
            else:
                print(f"  ✅ Стоимость соответствует minOrderAmt")
                
        except Exception as e:
            print(f"❌ Ошибка при тестировании {symbol}: {e}")
    
    print("\n=== Тест завершен ===")

if __name__ == "__main__":
    test_fixed_precision()