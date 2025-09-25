#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест динамического получения торговых символов
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.bybit_client import BybitClient
from config import API_KEY, API_SECRET, USE_TESTNET
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_dynamic_symbols():
    """Тестирование получения динамических символов"""
    try:
        logger.info("=== ТЕСТ ДИНАМИЧЕСКОГО ПОЛУЧЕНИЯ СИМВОЛОВ ===")
        
        # Создаем клиент Bybit
        client = BybitClient(API_KEY, API_SECRET, USE_TESTNET)
        logger.info(f"Клиент создан. Testnet: {USE_TESTNET}")
        
        # Получаем информацию об инструментах
        logger.info("Получение списка всех spot инструментов...")
        instruments = client.get_instruments_info(category="spot")
        
        if not instruments:
            logger.error("Не удалось получить список инструментов!")
            return False
            
        logger.info(f"Получено {len(instruments)} инструментов")
        
        # Фильтруем USDT пары
        usdt_symbols = []
        active_count = 0
        inactive_count = 0
        
        for instrument in instruments:
            symbol = instrument.get('symbol', '')
            status = instrument.get('status', '')
            
            if symbol.endswith('USDT'):
                if status == 'Trading' and len(symbol) <= 12:
                    usdt_symbols.append(symbol)
                    active_count += 1
                else:
                    inactive_count += 1
        
        logger.info(f"Найдено USDT пар: {len(usdt_symbols)} активных, {inactive_count} неактивных")
        
        # Показываем первые 20 символов
        logger.info("Первые 20 активных USDT символов:")
        for i, symbol in enumerate(sorted(usdt_symbols)[:20]):
            logger.info(f"  {i+1:2d}. {symbol}")
            
        if len(usdt_symbols) > 20:
            logger.info(f"  ... и еще {len(usdt_symbols) - 20} символов")
        
        # Проверяем популярные символы
        popular_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOGEUSDT']
        found_popular = []
        missing_popular = []
        
        for symbol in popular_symbols:
            if symbol in usdt_symbols:
                found_popular.append(symbol)
            else:
                missing_popular.append(symbol)
        
        logger.info(f"Популярные символы найдены: {found_popular}")
        if missing_popular:
            logger.warning(f"Популярные символы НЕ найдены: {missing_popular}")
        
        # Тест успешен если найдено больше 50 символов и есть популярные
        success = len(usdt_symbols) >= 50 and len(found_popular) >= 3
        
        if success:
            logger.info("✅ ТЕСТ ПРОЙДЕН: Динамическое получение символов работает корректно!")
        else:
            logger.error("❌ ТЕСТ НЕ ПРОЙДЕН: Недостаточно символов или отсутствуют популярные")
            
        return success
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании: {e}")
        return False

if __name__ == "__main__":
    success = test_dynamic_symbols()
    sys.exit(0 if success else 1)