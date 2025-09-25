#!/usr/bin/env python3
"""
Тест интеграции ticker_loader со стратегиями
"""

import sys
import os
import logging
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию проекта в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.strategies.adaptive_ml import AdaptiveMLStrategy
from src.tools.ticker_data_loader import TickerDataLoader
from src.database.db_manager import DatabaseManager
from src.api.bybit_client import BybitClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_ticker_data(ticker_data, limit=10):
    """
    Вывод данных тикеров в консоль для проверки
    
    Args:
        ticker_data: Данные тикеров
        limit: Количество записей для вывода
    """
    if not ticker_data or len(ticker_data) == 0:
        logger.error("Нет данных для отображения")
        return
    
    logger.info(f"Первые {min(limit, len(ticker_data))} записей из {len(ticker_data)}:")
    
    for i, data in enumerate(ticker_data[:limit]):
        timestamp = datetime.fromtimestamp(data['timestamp'] / 1000) if 'timestamp' in data else 'Н/Д'
        open_price = data.get('open', 'Н/Д')
        high_price = data.get('high', 'Н/Д')
        low_price = data.get('low', 'Н/Д')
        close_price = data.get('close', 'Н/Д')
        volume = data.get('volume', 'Н/Д')
        
        logger.info(f"{i+1}. Время: {timestamp}, Открытие: {open_price}, Макс: {high_price}, Мин: {low_price}, Закрытие: {close_price}, Объем: {volume}")

def visualize_ticker_data(ticker_data, symbol, timeframe):
    """
    Визуализация данных тикеров для проверки
    
    Args:
        ticker_data: Данные тикеров
        symbol: Символ тикера
        timeframe: Временной интервал
    """
    if not ticker_data or len(ticker_data) == 0:
        logger.error("Нет данных для визуализации")
        return
    
    # Преобразуем данные в DataFrame для удобства визуализации
    df = pd.DataFrame(ticker_data)
    
    # Преобразуем timestamp в datetime
    if 'timestamp' in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)
    
    # Создаем график
    plt.figure(figsize=(12, 8))
    
    # График цены закрытия
    plt.subplot(2, 1, 1)
    plt.plot(df['close'], label='Цена закрытия')
    plt.title(f'Данные тикера {symbol} ({timeframe})')
    plt.ylabel('Цена')
    plt.grid(True)
    plt.legend()
    
    # График объема
    plt.subplot(2, 1, 2)
    plt.bar(df.index, df['volume'], label='Объем')
    plt.ylabel('Объем')
    plt.grid(True)
    plt.legend()
    
    plt.tight_layout()
    
    # Сохраняем график в файл
    output_dir = Path('data/charts')
    output_dir.mkdir(exist_ok=True, parents=True)
    output_path = output_dir / f"{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(output_path)
    
    logger.info(f"График сохранен в {output_path}")
    
    # Закрываем график
    plt.close()

def verify_strategy_data_buffers(strategy):
    """
    Проверка буферов данных в стратегии
    
    Args:
        strategy: Экземпляр стратегии
    
    Returns:
        bool: True если буферы заполнены, иначе False
    """
    # Проверяем наличие буферов данных
    if not hasattr(strategy, '_price_buffer') or not strategy._price_buffer:
        logger.error("Буфер цен пуст")
        return False
    
    if not hasattr(strategy, '_volume_buffer') or not strategy._volume_buffer:
        logger.error("Буфер объемов пуст")
        return False
    
    if not hasattr(strategy, '_timestamp_buffer') or not strategy._timestamp_buffer:
        logger.error("Буфер временных меток пуст")
        return False
    
    # Выводим информацию о буферах
    logger.info(f"Буфер цен: {len(strategy._price_buffer)} записей")
    logger.info(f"Буфер объемов: {len(strategy._volume_buffer)} записей")
    logger.info(f"Буфер временных меток: {len(strategy._timestamp_buffer)} записей")
    
    # Выводим первые и последние элементы буферов
    if len(strategy._price_buffer) > 0:
        logger.info(f"Первая цена: {strategy._price_buffer[0]}, Последняя цена: {strategy._price_buffer[-1]}")
    
    if len(strategy._timestamp_buffer) > 0:
        first_time = datetime.fromtimestamp(strategy._timestamp_buffer[0] / 1000)
        last_time = datetime.fromtimestamp(strategy._timestamp_buffer[-1] / 1000)
        logger.info(f"Первая метка времени: {first_time}, Последняя метка времени: {last_time}")
    
    return True

def test_ticker_strategy_integration():
    """
    Тестирование интеграции ticker_loader со стратегиями
    """
    logger.info("=== Тест интеграции ticker_loader со стратегиями ===")
    
    try:
        # Инициализация компонентов
        ticker_loader = TickerDataLoader()
        db_manager = DatabaseManager()
        api_client = BybitClient(test_mode=True)
        
        # Параметры для теста
        symbol = "BTCUSDT"
        timeframe = "4h"
        limit = 100
        
        # Загрузка данных через ticker_loader
        logger.info(f"Загрузка данных для {symbol} с таймфреймом {timeframe}")
        ticker_data = ticker_loader.load_ticker_data(symbol, timeframe, limit)
        
        if not ticker_data or len(ticker_data) == 0:
            logger.error("Не удалось загрузить данные через ticker_loader")
            return False
        
        logger.info(f"Успешно загружено {len(ticker_data)} записей")
        
        # Выводим данные для проверки
        print_ticker_data(ticker_data)
        
        # Визуализируем данные
        visualize_ticker_data(ticker_data, symbol, timeframe)
        
        # Тестирование AdaptiveMLStrategy
        logger.info("Тестирование интеграции с AdaptiveMLStrategy")
        
        # Используем напрямую класс стратегии
        strategy_class = AdaptiveMLStrategy
        logger.info("Используем класс стратегии AdaptiveMLStrategy")
        
        # Создаем конфигурацию для тестирования
        test_config = {
            'asset': symbol,
            'position_size': 0.01,
            'stop_loss': 2.0,
            'take_profit': 4.0,
            'timeframe': timeframe,
            'max_daily_loss_pct': 20.0,
            'max_consecutive_losses': 3,
            'max_position_size_pct': 10.0
        }
        
        # Инициализируем стратегию
        strategy = strategy_class(
            name="adaptive_ml_test",
            config=test_config,
            api_client=api_client,
            db_manager=db_manager,
            config_manager=None
        )
        
        # Устанавливаем ticker_loader в стратегию
        strategy.ticker_loader = ticker_loader
        
        # Проверяем метод загрузки исторических данных
        logger.info("Тестирование метода prepare_historical_data")
        result = strategy.prepare_historical_data(symbol, timeframe, limit)
        
        if not result:
            logger.error("✗ Метод prepare_historical_data вернул False")
            return False
        
        # Проверяем буферы данных в стратегии
        logger.info("Проверка буферов данных в стратегии")
        if not verify_strategy_data_buffers(strategy):
            logger.error("✗ Буферы данных в стратегии не заполнены")
            return False
        
        logger.info("✓ Тест интеграции успешно пройден")
        logger.info("✓ Стратегия корректно загружает данные тикеров")
        return True
            
    except Exception as e:
        logger.error(f"Ошибка при тестировании интеграции: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_ticker_strategy_integration()
    sys.exit(0 if success else 1)