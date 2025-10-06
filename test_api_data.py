#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки данных от Bybit API
"""

import sys
import os
import json
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from src.tools.ticker_data_loader import TickerDataLoader

def test_api_data():
    """Тестирование данных от API"""
    print("🔍 Тестирование данных от Bybit API...")
    
    try:
        # Создаем загрузчик данных
        loader = TickerDataLoader()
        
        # Загружаем данные
        data = loader.load_tickers_data()
        
        if not data:
            print("❌ Не удалось получить данные от API")
            return
        
        tickers = data.get('tickers', {})
        print(f"✅ Получено {len(tickers)} тикеров")
        
        # Анализируем price24hPcnt для разных символов
        symbols_with_change = []
        symbols_without_change = []
        
        for symbol, ticker in tickers.items():
            price_change = float(ticker.get('price24hPcnt', 0))
            if price_change != 0:
                symbols_with_change.append((symbol, price_change))
            else:
                symbols_without_change.append(symbol)
        
        print(f"\n📊 Символы с изменением цены: {len(symbols_with_change)}")
        print(f"📊 Символы без изменения цены: {len(symbols_without_change)}")
        
        # Показываем топ-10 символов с изменением цены
        if symbols_with_change:
            symbols_with_change.sort(key=lambda x: abs(x[1]), reverse=True)
            print("\n🔥 Топ-10 символов с наибольшим изменением цены:")
            for i, (symbol, change) in enumerate(symbols_with_change[:10]):
                print(f"  {i+1}. {symbol}: {change}%")
        
        # Показываем несколько символов без изменения
        if symbols_without_change:
            print(f"\n⚪ Первые 10 символов без изменения цены:")
            for i, symbol in enumerate(symbols_without_change[:10]):
                ticker = tickers[symbol]
                print(f"  {i+1}. {symbol}: lastPrice={ticker.get('lastPrice')}, prevPrice24h={ticker.get('prevPrice24h')}")
        
        # Проверяем популярные символы
        popular_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
        print(f"\n🎯 Популярные символы:")
        for symbol in popular_symbols:
            if symbol in tickers:
                ticker = tickers[symbol]
                price_change = float(ticker.get('price24hPcnt', 0))
                print(f"  {symbol}: цена={ticker.get('lastPrice')}, изменение={price_change}%")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_data()