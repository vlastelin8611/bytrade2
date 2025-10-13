#!/usr/bin/env python3
"""
Тест с реальными случаями из логов для выявления проблемы с форматированием количества
"""

from decimal import Decimal, ROUND_DOWN

def current_format_quantity_for_api(qty: float, qty_step: float) -> str:
    """
    Текущая функция форматирования количества для API
    """
    if qty == 0:
        return "0"
    
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

def improved_format_quantity_for_api(qty: float, qty_step: float) -> str:
    """
    Улучшенная функция форматирования количества для API
    """
    if qty == 0:
        return "0"
    
    # Преобразуем в Decimal для точных вычислений
    decimal_qty = Decimal(str(qty))
    decimal_step = Decimal(str(qty_step))
    
    # Округляем количество до ближайшего кратного qty_step (вниз)
    rounded_qty = (decimal_qty // decimal_step) * decimal_step
    
    # Определяем количество десятичных знаков на основе qty_step
    if decimal_step >= 1:
        return str(int(rounded_qty))
    
    # Более точное определение количества десятичных знаков
    step_str = f"{decimal_step:.20f}".rstrip('0')
    if '.' in step_str:
        precision_decimals = len(step_str.split('.')[1])
    else:
        precision_decimals = 0
    
    # Строгое ограничение на 8 десятичных знаков для API
    precision_decimals = min(precision_decimals, 8)
    
    # Форматируем результат
    if precision_decimals == 0:
        return str(int(rounded_qty))
    else:
        formatted = f"{rounded_qty:.{precision_decimals}f}"
        # Убираем лишние нули справа
        formatted = formatted.rstrip('0').rstrip('.')
        return formatted

# Реальные случаи из логов
real_test_cases = [
    # Случаи с ETHUSDT
    (0.00123456789, 1e-05, "ETHUSDT", "Реальный случай ETHUSDT с qtyStep=1e-05"),
    (0.123456789, 1e-05, "ETHUSDT", "Средний случай ETHUSDT"),
    (1.23456789, 1e-05, "ETHUSDT", "Большой случай ETHUSDT"),
    
    # Случаи с очень маленькими шагами (потенциальная проблема)
    (123.456789123456789, 1e-08, "TESTCOIN", "Очень маленький шаг 1e-08"),
    (0.000123456789123456789, 1e-10, "TESTCOIN", "Нано-шаг 1e-10"),
    (999.999999999999999, 1e-12, "TESTCOIN", "Пико-шаг 1e-12"),
    
    # Случаи с проблемными числами с плавающей точкой
    (0.1 + 0.2, 0.01, "TESTCOIN", "Проблема точности 0.1 + 0.2"),
    (1.0000000000000002, 0.0001, "TESTCOIN", "Проблема точности float"),
]

def analyze_step_precision():
    """Анализ точности шагов"""
    print("=== Анализ точности шагов ===\n")
    
    steps_to_test = [1e-05, 1e-06, 1e-07, 1e-08, 1e-09, 1e-10, 1e-11, 1e-12]
    
    for step in steps_to_test:
        decimal_step = Decimal(str(step))
        step_str = format(decimal_step, 'f')
        step_str_clean = step_str.rstrip('0').rstrip('.')
        
        if '.' in step_str_clean:
            precision = len(step_str_clean.split('.')[1])
        else:
            precision = 0
            
        print(f"Шаг: {step} -> Decimal: {decimal_step} -> Точность: {precision}")
        
        # Проверяем форматирование
        step_str_20f = f"{decimal_step:.20f}".rstrip('0')
        if '.' in step_str_20f:
            precision_20f = len(step_str_20f.split('.')[1])
        else:
            precision_20f = 0
            
        print(f"  С .20f: {step_str_20f} -> Точность: {precision_20f}")
        print()

def run_real_tests():
    print("=== Тестирование реальных случаев ===\n")
    
    for qty, qty_step, symbol, description in real_test_cases:
        print(f"Тест: {description}")
        print(f"Символ: {symbol}")
        print(f"Исходное количество: {qty}")
        print(f"Шаг количества: {qty_step}")
        
        current_result = current_format_quantity_for_api(qty, qty_step)
        improved_result = improved_format_quantity_for_api(qty, qty_step)
        
        print(f"Текущий результат: '{current_result}' (длина: {len(current_result)})")
        print(f"Улучшенный результат: '{improved_result}' (длина: {len(improved_result)})")
        
        # Проверяем количество десятичных знаков
        current_decimals = len(current_result.split('.')[1]) if '.' in current_result else 0
        improved_decimals = len(improved_result.split('.')[1]) if '.' in improved_result else 0
        
        print(f"Десятичных знаков - текущий: {current_decimals}, улучшенный: {improved_decimals}")
        
        # Проверяем на проблемы
        if current_decimals > 8:
            print("⚠️ ПРОБЛЕМА: Текущий результат имеет слишком много десятичных знаков!")
        
        if len(current_result) > 20:
            print("⚠️ ПРОБЛЕМА: Текущий результат слишком длинный!")
            
        if improved_decimals <= 8 and len(improved_result) <= 20:
            print("✅ Улучшенный результат соответствует ограничениям API")
        else:
            print("❌ Улучшенный результат все еще имеет проблемы")
        
        print("-" * 60)

if __name__ == "__main__":
    analyze_step_precision()
    print("\n" + "="*60 + "\n")
    run_real_tests()