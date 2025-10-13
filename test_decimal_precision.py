#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Детальный тест точности десятичных знаков в format_quantity_for_api
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

# Импортируем класс TradingEngine для тестирования
from trader_program import TradingEngine

def test_decimal_precision():
    """
    Тестируем точность десятичных знаков
    """
    print("=== Тест точности десятичных знаков ===\n")
    
    # Создаем экземпляр TradingEngine для доступа к методу
    engine = TradingEngine(None, False)
    
    # Проблемные случаи из логов
    test_cases = [
        # Случаи, которые ранее вызывали ошибки "too many decimals"
        (373468.8, 1e-05, "ETHUSDT"),
        (2451461070.8, 1e-05, "ETHUSDT"), 
        (15.05, 1e-05, "ETHUSDT"),
        (0.03, 1e-05, "ETHUSDT"),
        
        # Дополнительные проблемные случаи
        (0.1, 1e-08, "TEST"),  # Очень маленький шаг
        (123.456789, 1e-06, "TEST"),  # Много знаков
        (0.00000001, 1e-08, "TEST"),  # Очень маленькое число
        (999999999.999999, 1e-06, "TEST"),  # Большое число
        
        # Случаи с float артефактами
        (0.1 + 0.2, 0.01, "TEST"),  # 0.30000000000000004
        (1.1 * 3, 0.01, "TEST"),    # 3.3000000000000003
        (0.1 * 3, 0.001, "TEST"),   # 0.30000000000000004
    ]
    
    for qty, qty_step, symbol in test_cases:
        print(f"Тест: {symbol}")
        print(f"Исходное количество: {qty}")
        print(f"Точное представление: {repr(qty)}")
        print(f"Шаг количества: {qty_step}")
        
        # Тестируем исправленную функцию
        result = engine.format_quantity_for_api(qty, qty_step)
        
        print(f"Результат: '{result}'")
        print(f"Длина результата: {len(result)}")
        
        # Проверяем количество знаков после запятой
        if '.' in result:
            decimal_places = len(result.split('.')[1])
            print(f"Знаков после запятой: {decimal_places}")
            
            # Проверяем, что не слишком много знаков
            if decimal_places > 8:
                print(f"❌ ОШИБКА: Слишком много знаков после запятой ({decimal_places})")
            else:
                print(f"✅ OK: Приемлемое количество знаков после запятой")
        else:
            print("✅ OK: Целое число")
        
        # Проверяем, что результат можно преобразовать в float
        try:
            result_float = float(result)
            print(f"Float значение: {result_float}")
            print(f"✅ OK: Корректное преобразование в float")
        except ValueError as e:
            print(f"❌ ОШИБКА: Не удается преобразовать в float: {e}")
        
        # Проверяем, что результат не содержит научную нотацию
        if 'e' in result.lower():
            print(f"❌ ОШИБКА: Результат содержит научную нотацию")
        else:
            print(f"✅ OK: Без научной нотации")
        
        print("-" * 60)

def test_edge_cases():
    """
    Тестируем граничные случаи
    """
    print("\n=== Тест граничных случаев ===\n")
    
    engine = TradingEngine(None, False)
    
    edge_cases = [
        (0, 0.01, "ZERO"),
        (0.0, 1e-08, "ZERO_FLOAT"),
        (1e-10, 1e-08, "VERY_SMALL"),
        (1e10, 1, "VERY_LARGE"),
        (float('inf'), 0.01, "INFINITY"),
        (float('nan'), 0.01, "NAN"),
    ]
    
    for qty, qty_step, description in edge_cases:
        print(f"Тест: {description}")
        print(f"Количество: {qty}")
        print(f"Шаг: {qty_step}")
        
        try:
            result = engine.format_quantity_for_api(qty, qty_step)
            print(f"Результат: '{result}'")
            print(f"✅ OK: Обработано без ошибок")
        except Exception as e:
            print(f"❌ ОШИБКА: {e}")
        
        print("-" * 40)

if __name__ == "__main__":
    test_decimal_precision()
    test_edge_cases()