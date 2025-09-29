#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def check_eth_limits():
    try:
        # Получаем информацию об инструменте ETHUSDT
        response = requests.get('https://api-testnet.bybit.com/v5/market/instruments-info?category=spot&symbol=ETHUSDT')
        data = response.json()
        
        if 'result' in data and 'list' in data['result'] and len(data['result']['list']) > 0:
            instrument = data['result']['list'][0]
            print('=== Информация об ETHUSDT ===')
            print(f'Символ: {instrument.get("symbol", "N/A")}')
            
            lot_filter = instrument.get("lotSizeFilter", {})
            print(f'Минимальный размер ордера: {lot_filter.get("minOrderQty", "N/A")}')
            print(f'Максимальный размер ордера: {lot_filter.get("maxOrderQty", "N/A")}')
            print(f'Шаг размера: {lot_filter.get("qtyStep", "N/A")}')
            print(f'Минимальная стоимость ордера: {lot_filter.get("minOrderAmt", "N/A")}')
            print(f'Максимальная стоимость ордера: {lot_filter.get("maxOrderAmt", "N/A")}')
            print(f'Статус торговли: {instrument.get("status", "N/A")}')
            
            # Получаем текущую цену
            price_response = requests.get('https://api-testnet.bybit.com/v5/market/tickers?category=spot&symbol=ETHUSDT')
            price_data = price_response.json()
            
            if 'result' in price_data and 'list' in price_data['result'] and len(price_data['result']['list']) > 0:
                current_price = float(price_data['result']['list'][0]['lastPrice'])
                print(f'\nТекущая цена ETH: ${current_price:.2f}')
                
                min_qty = float(lot_filter.get("minOrderQty", "0"))
                min_amt = float(lot_filter.get("minOrderAmt", "0"))
                
                print(f'\nРасчеты:')
                print(f'0.1 ETH = ${0.1 * current_price:.2f}')
                print(f'1.0 ETH = ${1.0 * current_price:.2f}')
                print(f'Минимальное количество: {min_qty} ETH = ${min_qty * current_price:.2f}')
                print(f'Минимальная сумма ордера: ${min_amt}')
                
                if min_amt > 0:
                    min_eth_for_amt = min_amt / current_price
                    print(f'Минимальное количество ETH для суммы: {min_eth_for_amt:.6f}')
                
        else:
            print('Не удалось получить информацию об инструменте')
            print(f'Ответ API: {data}')
            
    except Exception as e:
        print(f'Ошибка: {e}')

if __name__ == "__main__":
    check_eth_limits()