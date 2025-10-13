#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import math

# Добавляем путь к модулям
sys.path.append('src')

from api.bybit_client import BybitClient
from config import get_api_credentials

def test_quantity_calculation(symbol: str = 'ETHUSDT', order_value: float = 50.0):
    """Тестирует расчет количества для одного символа"""
    print(f"\n=== Тестирование {symbol} ===")
    
    try:
        # Инициализируем клиент
        api_key, api_secret, use_testnet = get_api_credentials()
        client = BybitClient(api_key, api_secret, testnet=use_testnet)
        
        # Получаем информацию об инструменте (возвращает список)
        instruments_list = client.get_instruments_info(category='spot', symbol=symbol)
        
        if not instruments_list or len(instruments_list) == 0:
            print(f"❌ Не удалось получить информацию об инструменте {symbol}")
            return
        
        # Берем первый инструмент из списка
        instrument_info = instruments_list[0]
        print(f"Информация об инструменте: {instrument_info}")
        
        # Получаем текущую цену
        tickers = client.get_tickers(category='spot', symbol=symbol)
        if not tickers:
            print(f"❌ Не удалось получить цену для {symbol}")
            return
        
        current_price = float(tickers[0]['lastPrice'])
        print(f"Текущая цена: {current_price}")
        
        # Извлекаем параметры из lotSizeFilter
        lot_size_filter = instrument_info.get('lotSizeFilter', {})
        
        min_order_qty = float(lot_size_filter.get('minOrderQty', 0))
        qty_step = float(lot_size_filter.get('qtyStep', 0.00001))
        min_order_amt = float(lot_size_filter.get('minOrderAmt', 5))
        
        print(f"minOrderQty: {min_order_qty}")
        print(f"qtyStep: {qty_step}")
        print(f"minOrderAmt: {min_order_amt}")
        
        # Рассчитываем количество
        qty = order_value / current_price
        print(f"Исходное qty: {qty}")
        
        # Определяем количество знаков после запятой для qtyStep
        qty_step_str = str(qty_step)
        if '.' in qty_step_str:
            precision_decimals = len(qty_step_str.split('.')[1])
        else:
            precision_decimals = 0
        
        print(f"Точность (знаков после запятой): {precision_decimals}")
        
        # Округляем qty
        qty_rounded = round(qty, precision_decimals)
        print(f"Округленное qty: {qty_rounded}")
        
        # Проверяем минимальные требования
        if qty_rounded < min_order_qty:
            print(f"⚠️ qty ({qty_rounded}) меньше minOrderQty ({min_order_qty})")
            qty_rounded = min_order_qty
            print(f"Скорректированное qty: {qty_rounded}")
        
        estimated_value = qty_rounded * current_price
        if estimated_value < min_order_amt:
            print(f"⚠️ Стоимость ордера ({estimated_value}) меньше minOrderAmt ({min_order_amt})")
        
        qty_str = str(qty_rounded)
        print(f"qty как строка: '{qty_str}'")
        
        return {
            'symbol': symbol,
            'qty': qty_rounded,
            'qty_str': qty_str,
            'current_price': current_price,
            'estimated_value': estimated_value,
            'min_order_qty': min_order_qty,
            'min_order_amt': min_order_amt,
            'qty_step': qty_step
        }
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании {symbol}: {e}")
        return None

def test_multiple_symbols():
    """Тестирует расчет для нескольких символов"""
    symbols = ['ETHUSDT', 'BTCUSDT', 'XRPUSDT']
    results = []
    
    for symbol in symbols:
        result = test_quantity_calculation(symbol)
        if result:
            results.append(result)
    
    print("\n=== СВОДКА РЕЗУЛЬТАТОВ ===")
    for result in results:
        print(f"{result['symbol']}: qty={result['qty_str']}, цена={result['current_price']}, стоимость={result['estimated_value']:.2f}")
    
    return results

if __name__ == "__main__":
    print("Тестирование расчета количества для ордеров")
    print("=" * 50)
    
    # Тестируем один символ
    result = test_quantity_calculation('ETHUSDT')
    
    print("\n" + "=" * 50)
    
    # Тестируем несколько символов
    test_multiple_symbols()