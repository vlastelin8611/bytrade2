#!/usr/bin/env python3
"""
Тестовый скрипт для проверки минимальных требований к ордеру SOLUSDT
"""
import os
import sys
from pybit.unified_trading import HTTP

# Загружаем API ключи
keys_file = os.path.join(os.path.dirname(__file__), 'keys')
if os.path.exists(keys_file):
    with open(keys_file, 'r') as f:
        lines = f.read().strip().split('\n')
        api_key = lines[0].strip()
        api_secret = lines[1].strip()
else:
    print("❌ Файл с ключами не найден")
    sys.exit(1)

# Инициализируем клиент
client = HTTP(
    testnet=True,
    api_key=api_key,
    api_secret=api_secret,
)

print("🔍 Тестируем минимальные требования к ордеру SOLUSDT...")

# Получаем информацию об инструменте
try:
    instrument_info = client.get_instruments_info(category='spot', symbol='SOLUSDT')
    if instrument_info['retCode'] == 0:
        info = instrument_info['result']['list'][0]
        lot_size = info['lotSizeFilter']
        
        print(f"📊 Информация об инструменте SOLUSDT:")
        print(f"   minOrderQty: {lot_size['minOrderQty']}")
        print(f"   minOrderAmt: {lot_size['minOrderAmt']}")
        print(f"   basePrecision: {lot_size['basePrecision']}")
        print(f"   quotePrecision: {lot_size['quotePrecision']}")
        
        # Получаем текущую цену
        ticker = client.get_tickers(category='spot', symbol='SOLUSDT')
        if ticker['retCode'] == 0:
            price = float(ticker['result']['list'][0]['lastPrice'])
            print(f"💰 Текущая цена SOLUSDT: ${price}")
            
            # Тестируем разные суммы
            test_amounts = [1.0, 5.0, 10.0, 15.0, 20.0]
            
            for amount in test_amounts:
                qty = amount / price
                # Округляем согласно basePrecision
                precision = len(lot_size['basePrecision'].split('.')[-1]) if '.' in lot_size['basePrecision'] else 0
                qty_rounded = round(qty, precision)
                final_value = qty_rounded * price
                
                print(f"\n🧮 Тест для суммы ${amount}:")
                print(f"   Количество: {qty_rounded}")
                print(f"   Итоговая стоимость: ${final_value:.2f}")
                
                # Проверяем минимальные требования
                min_qty_ok = qty_rounded >= float(lot_size['minOrderQty'])
                min_amt_ok = final_value >= float(lot_size['minOrderAmt'])
                
                print(f"   Минимальное количество OK: {min_qty_ok}")
                print(f"   Минимальная сумма OK: {min_amt_ok}")
                
                if min_qty_ok and min_amt_ok:
                    print(f"   ✅ Ордер должен пройти")
                else:
                    print(f"   ❌ Ордер не пройдет")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")