#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тест исправленной функции format_quantity_for_api
"""

from decimal import Decimal, getcontext

def fixed_format_quantity_for_api(qty: float, qty_step: float) -> str:
    """
    Исправленная функция форматирования количества для API
    """
    if qty == 0:
        return "0"
    
    # Устанавливаем высокую точность для вычислений
    getcontext().prec = 28
    
    # Преобразуем в Decimal, используя округление для устранения проблем точности float
    # Сначала округляем до разумного количества знаков (15), чтобы избежать артефактов float
    qty_rounded = round(qty, 15)
    qty_step_rounded = round(qty_step, 15)
    
    decimal_qty = Decimal(str(qty_rounded))
    decimal_step = Decimal(str(qty_step_rounded))
    
    # Округляем количество до ближайшего кратного qty_step (вниз)
    rounded_qty = (decimal_qty // decimal_step) * decimal_step
    
    # Определяем количество десятичных знаков на основе qty_step
    if decimal_step >= 1:
        # Если шаг >= 1, используем целые числа
        return str(int(rounded_qty))
    else:
        # Определяем точность на основе qty_step
        step_str = f"{decimal_step:.15f}".rstrip('0').rstrip('.')
        
        if '.' in step_str:
            precision_decimals = len(step_str.split('.')[1])
        else:
            precision_decimals = 0
        
        # Ограничиваем максимальную точность разумным пределом
        precision_decimals = min(precision_decimals, 8)
        
        # Форматируем с нужной точностью
        formatted = f"{rounded_qty:.{precision_decimals}f}"
        
        # Убираем лишние нули справа
        if '.' in formatted:
            formatted = formatted.rstrip('0').rstrip('.')
            # Если убрали все знаки после точки, но precision_decimals > 0, 
            # оставляем хотя бы один знак
            if '.' not in formatted and precision_decimals > 0:
                formatted += '.0'
        
        return formatted

def old_format_quantity_for_api(qty: float, qty_step: float) -> str:
    """
    Старая функция для сравнения
    """
    if qty == 0:
        return "0"
    
    from decimal import Decimal, ROUND_DOWN
    
    # Преобразуем в Decimal для точных вычислений
    decimal_qty = Decimal(str(qty))
    decimal_step = Decimal(str(qty_step))
    
    # Округляем количество до ближайшего кратного qty_step (вниз)
    rounded_qty = (decimal_qty // decimal_step) * decimal_step
    
    # Определяем количество десятичных знаков на основе qty_step
    if decimal_step >= 1:
        # Если шаг >= 1, используем целые числа
        return str(int(rounded_qty))
    else:
        # Получаем строковое представление step без экспоненциальной записи
        step_str = format(decimal_step, 'f')
        
        # Убираем лишние нули справа
        step_str = step_str.rstrip('0').rstrip('.')
        
        # Определяем количество знаков после запятой
        if '.' in step_str:
            precision_decimals = len(step_str.split('.')[1])
        else:
            precision_decimals = 0
        
        # Ограничиваем максимальную точность разумным пределом
        precision_decimals = min(precision_decimals, 8)
        
        # Форматируем с нужной точностью, избегая научной нотации
        formatted = f"{rounded_qty:.{precision_decimals}f}"
        
        # Убираем лишние нули справа, но оставляем минимум нужных знаков
        if '.' in formatted:
            formatted = formatted.rstrip('0').rstrip('.')
            # Если убрали все знаки после точки, добавляем минимум нужных
            if '.' not in formatted and precision_decimals > 0:
                formatted += '.' + '0' * min(precision_decimals, 1)
        
        return formatted

def test_problematic_cases():
    """
    Тестируем проблемные случаи из логов
    """
    print("=== Тест проблемных случаев из логов ===\n")
    
    # Случаи из логов, которые вызывали ошибки
    test_cases = [
        # (qty, qty_step, symbol, description)
        (373468.8, 1e-05, "ETHUSDT", "Случай из лога: 373468.79999999998835846782"),
        (2451461070.8, 1e-05, "ETHUSDT", "Случай из лога: 2451461070.80000019073486328125"),
        (15.05, 1e-05, "ETHUSDT", "Случай из лога: 15.05000000000000071054"),
        (0.03, 1e-05, "ETHUSDT", "Случай из лога: 0.02999999999999999889"),
        (0.1, 0.01, "BTCUSDT", "Простой случай с 0.01 шагом"),
        (1.23456789, 0.001, "GENERIC", "Много знаков после запятой"),
        (999999.999999, 1e-06, "GENERIC", "Большое число с микро-шагом"),
    ]
    
    for qty, qty_step, symbol, description in test_cases:
        print(f"Тест: {description}")
        print(f"Символ: {symbol}")
        print(f"Исходное количество: {qty}")
        print(f"Шаг количества: {qty_step}")
        
        old_result = old_format_quantity_for_api(qty, qty_step)
        new_result = fixed_format_quantity_for_api(qty, qty_step)
        
        print(f"Старая функция: '{old_result}' (длина: {len(old_result)})")
        print(f"Новая функция:  '{new_result}' (длина: {len(new_result)})")
        
        # Проверяем количество знаков после запятой
        old_decimals = len(old_result.split('.')[1]) if '.' in old_result else 0
        new_decimals = len(new_result.split('.')[1]) if '.' in new_result else 0
        
        print(f"Знаков после запятой - старая: {old_decimals}, новая: {new_decimals}")
        
        # Проверяем, что результат корректный
        try:
            old_float = float(old_result)
            new_float = float(new_result)
            print(f"Проверка float - старая: {old_float}, новая: {new_float}")
        except ValueError as e:
            print(f"❌ Ошибка преобразования в float: {e}")
        
        print("-" * 60)

if __name__ == "__main__":
    test_problematic_cases()