#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки подключения к Bybit API
и получения реального баланса с подробным логированием
"""

import sys
import os
import logging
import json
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent / 'src'))

# Настройка подробного логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('api_test.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def test_api_connection():
    """Тестирование подключения к API с подробным логированием"""
    
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ТЕСТИРОВАНИЯ API ПОДКЛЮЧЕНИЯ")
    logger.info("=" * 60)
    
    try:
        # Импорт конфигурации
        logger.info("📋 Загрузка конфигурации...")
        import config
        
        credentials = config.get_api_credentials()
        logger.info(f"🔑 API Key: {credentials['api_key'][:10]}...")
        logger.info(f"🔐 API Secret: {'*' * len(credentials['api_secret'])}")
        logger.info(f"🌐 Testnet: {credentials['testnet']}")
        
        # Импорт клиента API
        logger.info("📡 Инициализация Bybit клиента...")
        from api.bybit_client import BybitClient
        
        client = BybitClient(
            api_key=credentials['api_key'],
            api_secret=credentials['api_secret'],
            testnet=credentials['testnet']
        )
        
        logger.info("✅ Клиент успешно создан")
        
        # Тест подключения
        logger.info("🔗 Тестирование подключения...")
        connection_test = client.test_connection()
        logger.info(f"📊 Результат теста подключения: {connection_test}")
        
        if not connection_test:
            logger.error("❌ Тест подключения не прошел!")
            return False
            
        # Получение времени сервера
        logger.info("⏰ Получение времени сервера...")
        server_time = client.get_server_time()
        logger.info(f"🕐 Время сервера: {server_time}")
        
        # Получение баланса кошелька
        logger.info("💰 Получение баланса кошелька...")
        balance_info = client.get_wallet_balance(account_type="UNIFIED")
        
        logger.info("📈 РЕЗУЛЬТАТ ЗАПРОСА БАЛАНСА:")
        logger.info(f"Raw response: {json.dumps(balance_info, indent=2, ensure_ascii=False)}")
        
        if balance_info:
            # Парсинг данных баланса
            total_balance = balance_info.get('totalWalletBalance', 0)
            available_balance = balance_info.get('availableBalance', 0)
            unrealized_pnl = balance_info.get('totalUnrealizedPnl', 0)
            
            logger.info("💵 ДЕТАЛИ БАЛАНСА:")
            logger.info(f"   💰 Общий баланс: ${float(total_balance):.6f}")
            logger.info(f"   💳 Доступный баланс: ${float(available_balance):.6f}")
            logger.info(f"   📊 Нереализованный P&L: ${float(unrealized_pnl):.6f}")
            
            # Проверка наличия активов
            coin_list = balance_info.get('coin', [])
            if coin_list:
                logger.info(f"🪙 АКТИВЫ В КОШЕЛЬКЕ ({len(coin_list)} шт.):")
                for coin in coin_list:
                    coin_name = coin.get('coin', 'Unknown')
                    wallet_balance = float(coin.get('walletBalance', 0))
                    available = float(coin.get('availableToWithdraw', 0))
                    
                    if wallet_balance > 0:
                        logger.info(f"   💎 {coin_name}: {wallet_balance:.6f} (доступно: {available:.6f})")
            else:
                logger.warning("⚠️ Список активов пуст или не найден")
                
        else:
            logger.error("❌ Не удалось получить данные баланса")
            return False
            
        # Получение позиций
        logger.info("📍 Получение позиций...")
        positions = client.get_positions(category="linear")
        
        logger.info(f"📋 ПОЗИЦИИ: найдено {len(positions) if positions else 0} позиций")
        if positions:
            for pos in positions:
                symbol = pos.get('symbol', 'Unknown')
                size = float(pos.get('size', 0))
                side = pos.get('side', 'None')
                unrealized_pnl = float(pos.get('unrealisedPnl', 0))
                
                if size > 0:
                    logger.info(f"   📈 {symbol}: {side} {size} (P&L: ${unrealized_pnl:.6f})")
        
        # Получение информации об инструментах
        logger.info("🔧 Получение информации об инструментах...")
        instruments = client.get_instruments_info(category="linear")
        
        if instruments:
            logger.info(f"🛠️ Доступно инструментов: {len(instruments)}")
            # Показываем первые 5 инструментов
            for i, instrument in enumerate(instruments[:5]):
                symbol = instrument.get('symbol', 'Unknown')
                status = instrument.get('status', 'Unknown')
                logger.info(f"   🔹 {symbol}: {status}")
        
        logger.info("=" * 60)
        logger.info("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО")
        logger.info("=" * 60)
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта: {e}")
        logger.error("💡 Убедитесь, что все модули находятся в правильных директориях")
        return False
        
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        logger.error(f"📋 Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"📄 Трассировка:\n{traceback.format_exc()}")
        return False

def main():
    """Главная функция"""
    print("🔍 Тестирование подключения к Bybit API...")
    print("📝 Подробные логи сохраняются в файл api_test.log")
    print()
    
    success = test_api_connection()
    
    if success:
        print("\n✅ Тестирование прошло успешно!")
        print("📊 Проверьте логи выше для подробной информации о балансе")
    else:
        print("\n❌ Тестирование не удалось!")
        print("📋 Проверьте файл api_test.log для подробностей")
        
    print("\n📁 Логи сохранены в файл: api_test.log")

if __name__ == "__main__":
    main()