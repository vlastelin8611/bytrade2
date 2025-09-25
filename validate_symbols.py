#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для валидации символов и определения поддерживаемых категорий
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.bybit_client import BybitClient
from src.tools.ticker_data_loader import TickerDataLoader
from config import get_api_credentials
import json

def validate_symbols():
    """Валидация символов из TickerDataLoader против API Bybit"""
    
    # Получаем API ключи
    api_key, api_secret, testnet = get_api_credentials()
    
    # Создаем клиент
    client = BybitClient(api_key, api_secret, testnet)
    
    # Загружаем символы из TickerDataLoader
    loader = TickerDataLoader()
    ticker_data = loader.load_tickers_data()
    
    if not ticker_data or 'tickers' not in ticker_data:
        print("❌ Не удалось загрузить данные из TickerDataLoader")
        return
    
    # Получаем все символы
    if isinstance(ticker_data['tickers'], dict):
        all_symbols = list(ticker_data['tickers'].keys())
    else:
        all_symbols = [ticker.get('symbol') for ticker in ticker_data['tickers'] if ticker.get('symbol')]
    
    # Фильтруем только USDT пары
    usdt_symbols = [s for s in all_symbols if s.endswith('USDT')]
    
    print(f"📊 Всего символов из TickerDataLoader: {len(all_symbols)}")
    print(f"📊 USDT символов для проверки: {len(usdt_symbols)}")
    
    # Получаем поддерживаемые инструменты для разных категорий
    categories = ['spot', 'linear']
    supported_symbols = {}
    
    for category in categories:
        print(f"\n🔍 Проверяем категорию '{category}'...")
        try:
            instruments = client.get_instruments_info(category=category)
            if instruments:
                category_symbols = []
                for instrument in instruments:
                    symbol = instrument.get('symbol', '')
                    status = instrument.get('status', '')
                    
                    # Проверяем что это USDT пара и инструмент активен
                    if (symbol.endswith('USDT') and 
                        status == 'Trading'):
                        category_symbols.append(symbol)
                
                supported_symbols[category] = set(category_symbols)
                print(f"✅ Найдено {len(category_symbols)} активных USDT инструментов в категории '{category}'")
            else:
                supported_symbols[category] = set()
                print(f"❌ Не удалось получить инструменты для категории '{category}'")
        except Exception as e:
            supported_symbols[category] = set()
            print(f"❌ Ошибка при получении инструментов для категории '{category}': {e}")
    
    # Анализируем символы из TickerDataLoader
    valid_symbols = {}
    invalid_symbols = []
    
    print(f"\n🔍 Анализируем символы из TickerDataLoader...")
    
    for symbol in usdt_symbols[:50]:  # Проверяем первые 50 для примера
        found_categories = []
        
        for category, category_symbols in supported_symbols.items():
            if symbol in category_symbols:
                found_categories.append(category)
        
        if found_categories:
            valid_symbols[symbol] = found_categories
        else:
            invalid_symbols.append(symbol)
    
    # Выводим результаты
    print(f"\n📈 Результаты валидации (первые 50 символов):")
    print(f"✅ Поддерживаемые символы: {len(valid_symbols)}")
    print(f"❌ Неподдерживаемые символы: {len(invalid_symbols)}")
    
    if valid_symbols:
        print(f"\n✅ Примеры поддерживаемых символов:")
        for symbol, categories in list(valid_symbols.items())[:10]:
            print(f"  {symbol}: {', '.join(categories)}")
    
    if invalid_symbols:
        print(f"\n❌ Примеры неподдерживаемых символов:")
        for symbol in invalid_symbols[:10]:
            print(f"  {symbol}")
    
    # Сохраняем результаты в файл
    results = {
        'timestamp': ticker_data.get('timestamp'),
        'total_symbols': len(all_symbols),
        'usdt_symbols': len(usdt_symbols),
        'supported_symbols': {k: list(v) for k, v in valid_symbols.items()},
        'invalid_symbols': invalid_symbols,
        'categories_info': {k: len(v) for k, v in supported_symbols.items()}
    }
    
    with open('symbol_validation_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты сохранены в 'symbol_validation_results.json'")
    
    return valid_symbols, invalid_symbols

if __name__ == "__main__":
    validate_symbols()