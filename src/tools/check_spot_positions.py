#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Программа для проверки спотовых позиций через API Bybit
"""

import logging
import json
from decimal import Decimal
from pathlib import Path
import sys

# Добавляем корневую директорию проекта в sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Импортируем BybitClient из модуля api
from src.api.bybit_client import BybitClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('spot_positions_checker')

def main():
    # Загрузка API ключей из файла keys
    keys_path = Path(__file__).parent.parent.parent / 'keys'
    if not keys_path.exists():
        logger.error(f"Файл с API ключами не найден: {keys_path}")
        return
    
    # Загружаем API ключи из файла keys
    try:
        api_key = None
        api_secret = None
        
        with open(keys_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('BYBIT_API_KEY='):
                    api_key = line.split('=', 1)[1]
                elif line.startswith('BYBIT_API_SECRET='):
                    api_secret = line.split('=', 1)[1]
        
        # Если ключи не найдены, проверяем тестовые ключи
        if not api_key or not api_secret:
            with open(keys_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('BYBIT_TESTNET_API_KEY='):
                        api_key = line.split('=', 1)[1]
                    elif line.startswith('BYBIT_TESTNET_API_SECRET='):
                        api_secret = line.split('=', 1)[1]
    except Exception as e:
        logger.error(f"Ошибка загрузки API ключей: {e}")
        return
    
    if not api_key or not api_secret:
        logger.error("API ключи не найдены в конфигурации")
        return
    
    # Инициализация клиента Bybit
    client = BybitClient(api_key, api_secret)
    
    # Проверка спотовых позиций через баланс кошелька
    try:
        logger.info("Проверка спотовых позиций через баланс кошелька...")
        balance = client.get_unified_balance_flat()
        
        if not balance or not balance.get('coins'):
            logger.warning("Спотовые позиции не найдены в балансе кошелька")
            logger.info("Это может означать, что у вас нет спотовых позиций или проблема с API ключами")
        else:
            logger.info("Найдены спотовые позиции в балансе кошелька:")
            logger.info(f"Общий баланс кошелька: {balance['total_wallet_usd']} USD")
            logger.info(f"Доступный баланс: {balance['total_available_usd']} USD")
            
            # Выводим информацию о монетах (спотовых позициях)
            for coin, amount in balance.get('coins', {}).items():
                if isinstance(amount, dict):
                    total = amount.get('total', Decimal('0'))
                    free = amount.get('free', Decimal('0'))
                    if total > Decimal('0'):
                        logger.info(f"  {coin}: всего {total} (доступно: {free})")
                elif amount > Decimal('0'):
                    logger.info(f"  {coin}: {amount}")
    except Exception as e:
        logger.error(f"Ошибка при получении баланса кошелька: {e}")
    
    # Примечание: API позиций не поддерживает категорию 'spot'
    logger.info("\nПримечание: API позиций Bybit не поддерживает категорию 'spot'")
    logger.info("Спотовые позиции - это фактически баланс кошелька UNIFIED или SPOT")
    logger.info("Для проверки спотовых позиций используйте только метод get_unified_balance_flat()")
    
    # Проверка через API тикеров для получения текущих цен
    try:
        logger.info("\nПолучение текущих цен через API тикеров...")
        tickers = client.get_tickers(category="spot")
        
        if not tickers:
            logger.info("Не удалось получить информацию о текущих ценах")
        else:
            logger.info(f"Получена информация о {len(tickers)} тикерах")
            # Выводим несколько примеров
            for i, ticker in enumerate(tickers[:3]):
                logger.info(f"  {ticker.get('symbol')}: {ticker.get('lastPrice')}")
            if len(tickers) > 3:
                logger.info(f"  ... и еще {len(tickers) - 3} тикеров")
    except Exception as e:
        logger.error(f"Ошибка при получении тикеров: {e}")

if __name__ == "__main__":
    main()