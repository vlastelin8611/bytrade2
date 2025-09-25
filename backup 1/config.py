#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация торгового бота
Настройки API ключей и параметров торговли
"""

import os
from pathlib import Path

# =============================================================================
# НАСТРОЙКИ API BYBIT
# =============================================================================

# ВАЖНО: Замените эти значения на ваши реальные API ключи от Bybit
# Получить API ключи можно в личном кабинете Bybit:
# https://www.bybit.com/app/user/api-management

# API ключи (ОБЯЗАТЕЛЬНО ЗАПОЛНИТЕ!)
API_KEY = "9HlqDp2h1HwSP8Ydnk"  # Ваш API ключ
API_SECRET = "hXpgFc1Wd97IzRuqBV96wCcScH2s7LDLSKij"  # Ваш API секрет

# Режим работы
USE_TESTNET = True  # True - тестовая сеть, False - реальная торговля

# ВНИМАНИЕ: 
# - Для тестирования используйте testnet ключи (USE_TESTNET = True)
# - Для реальной торговли используйте mainnet ключи (USE_TESTNET = False)
# - НИКОГДА не публикуйте ваши API ключи в открытом доступе!

# =============================================================================
# НАСТРОЙКИ ТОРГОВЛИ
# =============================================================================

# Лимиты торговли
MAX_DAILY_VOLUME_PERCENT = 0.20  # Максимум 20% от баланса в день
MIN_CONFIDENCE_THRESHOLD = 0.65  # Минимальная уверенность для торговли (65%)
MAX_POSITION_PERCENT = 0.03  # Максимум 3% от баланса на одну позицию
MIN_POSITION_SIZE = 10.0  # Минимальный размер позиции в USD

# Символы для торговли
# ВАЖНО: Символы теперь получаются динамически через Bybit API
# Программа автоматически загружает ВСЕ доступные USDT торговые пары
# и анализирует их все, а не только популярные криптовалюты.
# Это позволяет боту видеть все торговые активы, предлагаемые Bybit.

# Резервный список символов (используется только в случае ошибки API)
FALLBACK_TRADING_SYMBOLS = [
    'BTCUSDT',   # Bitcoin
    'ETHUSDT',   # Ethereum
    'ADAUSDT',   # Cardano
    'SOLUSDT',   # Solana
    'DOTUSDT'    # Polkadot
]

# Таймфреймы для анализа
ANALYSIS_TIMEFRAMES = {
    'primary': '1h',    # Основной таймфрейм
    'secondary': '4h',  # Дополнительный таймфрейм
    'trend': '1d'       # Для определения тренда
}

# Количество свечей для анализа
KLINE_LIMIT = 200

# =============================================================================
# НАСТРОЙКИ ML СТРАТЕГИИ
# =============================================================================

# Параметры машинного обучения
ML_CONFIG = {
    'retrain_interval_hours': 24,  # Переобучение каждые 24 часа
    'min_samples_for_training': 100,  # Минимум образцов для обучения
    'feature_window': 50,  # Окно для расчета признаков
    'prediction_horizon': 1,  # Горизонт прогнозирования (свечей)
    'model_type': 'random_forest',  # Тип модели: 'random_forest', 'gradient_boosting'
    'cross_validation_folds': 5,  # Количество фолдов для кросс-валидации
}

# Технические индикаторы
INDICATORS_CONFIG = {
    'sma_periods': [10, 20, 50],  # Периоды простой скользящей средней
    'ema_periods': [12, 26],      # Периоды экспоненциальной скользящей средней
    'rsi_period': 14,             # Период RSI
    'macd_fast': 12,              # Быстрая EMA для MACD
    'macd_slow': 26,              # Медленная EMA для MACD
    'macd_signal': 9,             # Сигнальная линия MACD
    'bb_period': 20,              # Период для полос Боллинджера
    'bb_std': 2,                  # Стандартное отклонение для полос Боллинджера
}

# =============================================================================
# НАСТРОЙКИ БАЗЫ ДАННЫХ
# =============================================================================

# Путь к базе данных
DB_PATH = str(Path(__file__).parent / 'data' / 'trading_bot.db')

# Настройки очистки логов
LOG_RETENTION_DAYS = 30  # Хранить логи 30 дней
CLEANUP_INTERVAL_HOURS = 24  # Очистка каждые 24 часа

# =============================================================================
# НАСТРОЙКИ ИНТЕРФЕЙСА
# =============================================================================

# Интервалы обновления (в миллисекундах)
UPDATE_INTERVALS = {
    'balance': 5000,      # Обновление баланса каждые 5 секунд
    'positions': 5000,    # Обновление позиций каждые 5 секунд
    'trading_cycle': 5000, # Торговый цикл каждые 5 секунд
    'ui_refresh': 1000,   # Обновление UI каждую секунду
}

# Максимальное количество записей в таблицах UI
UI_LIMITS = {
    'max_history_rows': 100,  # Максимум строк в истории торговли
    'max_log_lines': 1000,    # Максимум строк в логах
    'max_positions_display': 50,  # Максимум позиций для отображения
}

# =============================================================================
# НАСТРОЙКИ БЕЗОПАСНОСТИ
# =============================================================================

# Лимиты безопасности
SAFETY_LIMITS = {
    'max_daily_trades': 50,        # Максимум сделок в день
    'max_consecutive_losses': 5,   # Максимум убыточных сделок подряд
    'emergency_stop_loss': 0.10,   # Экстренная остановка при потере 10%
    'max_drawdown_percent': 0.15,  # Максимальная просадка 15%
}

# Настройки уведомлений
NOTIFICATIONS = {
    'enable_error_alerts': True,     # Уведомления об ошибках
    'enable_trade_alerts': True,     # Уведомления о сделках
    'enable_balance_alerts': True,   # Уведомления о балансе
    'critical_balance_threshold': 100,  # Критический уровень баланса
}

# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def validate_config():
    """
    Проверка корректности конфигурации
    """
    errors = []
    
    # Проверка API ключей
    if API_KEY == "YOUR_API_KEY_HERE" or not API_KEY:
        errors.append("API_KEY не настроен! Укажите ваш API ключ от Bybit.")
    
    if API_SECRET == "YOUR_API_SECRET_HERE" or not API_SECRET:
        errors.append("API_SECRET не настроен! Укажите ваш API секрет от Bybit.")
    
    # Проверка лимитов
    if not (0 < MAX_DAILY_VOLUME_PERCENT <= 1):
        errors.append("MAX_DAILY_VOLUME_PERCENT должен быть между 0 и 1")
    
    if not (0 < MIN_CONFIDENCE_THRESHOLD <= 1):
        errors.append("MIN_CONFIDENCE_THRESHOLD должен быть между 0 и 1")
    
    if not (0 < MAX_POSITION_PERCENT <= 1):
        errors.append("MAX_POSITION_PERCENT должен быть между 0 и 1")
    
    # Проверка резервных символов
    if not FALLBACK_TRADING_SYMBOLS:
        errors.append("FALLBACK_TRADING_SYMBOLS не может быть пустым")
    
    return errors

def get_api_credentials():
    """
    Получение API учетных данных
    """
    return {
        'api_key': API_KEY,
        'api_secret': API_SECRET,
        'testnet': USE_TESTNET
    }

def get_trading_config():
    """
    Получение конфигурации торговли
    """
    return {
        'max_daily_volume_percent': MAX_DAILY_VOLUME_PERCENT,
        'min_confidence_threshold': MIN_CONFIDENCE_THRESHOLD,
        'max_position_percent': MAX_POSITION_PERCENT,
        'min_position_size': MIN_POSITION_SIZE,
        'fallback_trading_symbols': FALLBACK_TRADING_SYMBOLS,
        'analysis_timeframes': ANALYSIS_TIMEFRAMES,
        'kline_limit': KLINE_LIMIT
    }

def get_ml_config():
    """
    Получение конфигурации ML
    """
    return {
        **ML_CONFIG,
        'indicators': INDICATORS_CONFIG
    }

def create_data_directory():
    """
    Создание директории для данных
    """
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)
    return data_dir

# Автоматическое создание директории данных при импорте
create_data_directory()

# =============================================================================
# ИНСТРУКЦИИ ПО НАСТРОЙКЕ
# =============================================================================

"""
ИНСТРУКЦИИ ПО НАСТРОЙКЕ API КЛЮЧЕЙ:

1. Зарегистрируйтесь на Bybit (если еще не зарегистрированы):
   https://www.bybit.com/

2. Войдите в личный кабинет и перейдите в раздел API Management:
   https://www.bybit.com/app/user/api-management

3. Создайте новый API ключ:
   - Для тестирования: выберите "Testnet" 
   - Для реальной торговли: выберите "Mainnet"
   
4. Настройте разрешения для API ключа:
   - ✅ Read (чтение данных)
   - ✅ Trade (торговые операции)
   - ❌ Withdraw (вывод средств) - НЕ ВКЛЮЧАЙТЕ для безопасности!

5. Скопируйте API Key и Secret Key

6. Замените значения в этом файле:
   API_KEY = "ваш_api_ключ"
   API_SECRET = "ваш_api_секрет"

7. Для начала установите USE_TESTNET = True для безопасного тестирования

8. После успешного тестирования можете переключиться на реальную торговлю:
   USE_TESTNET = False

ВНИМАНИЕ: 
- Никогда не публикуйте ваши API ключи!
- Используйте только необходимые разрешения
- Регулярно обновляйте API ключи
- Начинайте с testnet для изучения работы бота
"""

if __name__ == "__main__":
    # Проверка конфигурации при запуске файла
    print("🔧 Проверка конфигурации торгового бота...")
    
    errors = validate_config()
    
    if errors:
        print("❌ Найдены ошибки в конфигурации:")
        for error in errors:
            print(f"   • {error}")
        print("\n📝 Пожалуйста, исправьте ошибки перед запуском бота.")
    else:
        print("✅ Конфигурация корректна!")
        print(f"🔗 Режим: {'Testnet' if USE_TESTNET else 'Mainnet'}")
        print(f"📊 Резервных символов: {len(FALLBACK_TRADING_SYMBOLS)} (символы загружаются динамически через API)")
        print(f"💰 Максимальный дневной объем: {MAX_DAILY_VOLUME_PERCENT*100}%")
        print(f"🎯 Минимальная уверенность: {MIN_CONFIDENCE_THRESHOLD*100}%")