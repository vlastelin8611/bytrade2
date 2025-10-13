#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Исправление функции для правильного определения точности qtyStep
"""

import math
from decimal import Decimal

def get_precision_decimals(qty_step):
    """
    Правильно определяет количество знаков после запятой для qtyStep,
    включая научную нотацию (например, 1e-05)
    """
    if qty_step <= 0:
        return 0
    
    # Используем Decimal для точного представления
    decimal_step = Decimal(str(qty_step))
    
    # Получаем строковое представление без экспоненты
    step_str = format(decimal_step, 'f')
    
    # Убираем лишние нули справа
    step_str = step_str.rstrip('0').rstrip('.')
    
    # Считаем знаки после запятой
    if '.' in step_str:
        precision_decimals = len(step_str.split('.')[1])
    else:
        precision_decimals = 0
    
    return precision_decimals

def round_quantity_properly(qty, qty_step):
    """
    Правильно округляет количество согласно qtyStep
    """
    if qty_step <= 0:
        return qty
    
    # Определяем точность
    precision_decimals = get_precision_decimals(qty_step)
    
    # Округляем вниз до ближайшего кратного qty_step
    qty_rounded = math.floor(qty / qty_step) * qty_step
    
    # Округляем до нужного количества знаков после запятой
    qty_final = round(qty_rounded, precision_decimals)
    
    return qty_final

def test_precision_fix():
    """Тестирует исправленную функцию"""
    test_cases = [
        (1e-05, "1e-05 (ETHUSDT)"),
        (1e-06, "1e-06 (BTCUSDT)"),
        (0.0001, "0.0001 (XRPUSDT)"),
        (0.01, "0.01"),
        (0.001, "0.001"),
        (1.0, "1.0"),
    ]
    
    print("=== Тестирование исправленной функции ===")
    for qty_step, description in test_cases:
        precision = get_precision_decimals(qty_step)
        print(f"{description}: точность = {precision} знаков")
        
        # Тестируем округление
        test_qty = 0.123456789
        rounded = round_quantity_properly(test_qty, qty_step)
        print(f"  {test_qty} -> {rounded} (строка: '{str(rounded)}')")
        print()

if __name__ == "__main__":
    test_precision_fix()