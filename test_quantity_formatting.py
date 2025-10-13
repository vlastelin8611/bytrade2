#!/usr/bin/env python3
"""
Тест для проверки и исправления проблемы с форматированием количества для API
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
    Исправляет проблему с избыточными десятичными знаками
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
        # Определяем точность на основе qty_step более надежным способом
        step_str = f"{decimal_step:.20f}".rstrip('0')
        
        if '.' in step_str:
            precision_decimals = len(step_str.split('.')[1])
        else:
            precision_decimals = 0
        
        # Ограничиваем максимальную точность для предотвращения избыточных знаков
        # Большинство бирж поддерживают максимум 8 десятичных знаков
        precision_decimals = min(precision_decimals, 8)
        
        # Дополнительная проверка: если qty_step очень маленький, ограничиваем точность
        if decimal_step < Decimal('0.00000001'):  # 1e-8
            precision_decimals = min(precision_decimals, 8)
        elif decimal_step < Decimal('0.0001'):  # 1e-4
            precision_decimals = min(precision_decimals, 6)
        elif decimal_step < Decimal('0.01'):  # 1e-2
            precision_decimals = min(precision_decimals, 4)
        
        # Форматируем с определенной точностью
        formatted = f"{rounded_qty:.{precision_decimals}f}"
        
        # Убираем лишние нули справа
        if '.' in formatted:
            formatted = formatted.rstrip('0').rstrip('.')
        
        return formatted

# Тестовые случаи на основе реальных данных
test_cases = [
    # (qty, qty_step, symbol, description)
    (0.001234567890, 0.000001, "ETHUSDT", "Малое количество ETH с микро-шагом"),
    (0.123456789, 0.00001, "ETHUSDT", "Среднее количество ETH"),
    (1.23456789, 0.0001, "ETHUSDT", "Большое количество ETH"),
    (1000000.123456789, 0.000001, "TRXUSDT", "Большое количество TRX с микро-шагом"),
    (123.456789, 0.1, "BTCUSDT", "BTC с шагом 0.1"),
    (0.00000123456789, 0.00000001, "SMALLCOIN", "Очень малое количество с нано-шагом"),
    (999999999.123456789, 0.000000001, "BIGCOIN", "Очень большое количество с нано-шагом"),
]

def run_tests():
    print("=== Тестирование форматирования количества для API ===\n")
    
    for qty, qty_step, symbol, description in test_cases:
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
        
        if current_decimals > 8:
            print("⚠️ ПРОБЛЕМА: Текущий результат имеет слишком много десятичных знаков!")
        
        if improved_decimals <= 8:
            print("✅ Улучшенный результат соответствует ограничениям API")
        else:
            print("❌ Улучшенный результат все еще имеет проблемы")
        
        print("-" * 60)

if __name__ == "__main__":
    run_tests()