#!/usr/bin/env python3
"""
Консольная версия тренера ML моделей
Автоматически запускает обучение без GUI интерфейса
"""

import sys
import os
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Добавляем путь к модулям проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.strategies.adaptive_ml import AdaptiveMLStrategy
    from src.api.bybit_client import BybitClient
    from src.tools.ticker_data_loader import TickerDataLoader
    from config import get_api_credentials, get_ml_config
except ImportError as e:
    print(f"Ошибка импорта модулей: {e}")
    print("Убедитесь, что все необходимые модули доступны")
    sys.exit(1)


class TickerDataWatcher(FileSystemEventHandler):
    """Класс для мониторинга изменений в файле tickers_data.json"""
    
    def __init__(self, trainer):
        self.trainer = trainer
        self.last_modified = 0
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        if event.src_path.endswith('tickers_data.json'):
            # Проверяем, чтобы не обрабатывать одно и то же изменение несколько раз
            current_time = time.time()
            if current_time - self.last_modified < 5:  # Игнорируем изменения чаще чем раз в 5 секунд
                return
                
            self.last_modified = current_time
            print(f"🔄 Обнаружено обновление данных тикеров: {datetime.now().strftime('%H:%M:%S')}")
            
            # Запускаем автоматическое обучение в отдельном потоке
            threading.Thread(target=self.trainer.auto_retrain, daemon=True).start()


class ConsoleTrainer:
    """Консольный тренер ML моделей"""
    
    def __init__(self):
        self.symbols = []
        self.symbol_categories = {}
        self.file_watcher = None
        self.observer = None
        self.auto_training_enabled = True
        self.init_components()
        self.setup_file_monitoring()
    
    def init_components(self):
        """Инициализация компонентов"""
        try:
            print("✅ API ключи загружены из файла C:\\Users\\vlastelin8\\Desktop\\trade\\crypto\\keys")
            
            # Получаем API credentials
            api_creds = get_api_credentials()
            
            # Инициализируем API клиент
            self.bybit_client = BybitClient(
                api_creds['api_key'],
                api_creds['api_secret'],
                api_creds['testnet']
            )
            
            # Инициализируем TickerDataLoader
            try:
                self.ticker_loader = TickerDataLoader()
            except Exception as e:
                print(f"Ошибка инициализации TickerDataLoader: {e}")
                self.ticker_loader = None
            
            # Инициализируем ML стратегию
            ml_config = get_ml_config()
            self.ml_strategy = AdaptiveMLStrategy(
                name="adaptive_ml",
                config=ml_config,
                api_client=self.bybit_client,
                db_manager=None,
                config_manager=None
            )
            
            # Подключаем TickerDataLoader к ML стратегии
            if self.ticker_loader:
                self.ml_strategy.ticker_loader = self.ticker_loader
            
            # Загружаем существующие модели
            self.ml_strategy.load_models()
            
        except Exception as e:
            print(f"❌ Ошибка инициализации компонентов: {e}")
            sys.exit(1)
    
    def validate_symbols_with_api(self, symbols: List[str]) -> List[str]:
        """Валидация символов через API"""
        print("🔍 Валидация символов через API...")
        
        validated_symbols = []
        symbol_categories = {}
        
        try:
            # Получаем информацию о доступных инструментах для разных категорий
            categories_to_check = ['spot', 'linear']
            all_valid_symbols = {}
            
            for category in categories_to_check:
                try:
                    instruments = self.ml_strategy.api_client.get_instruments_info(category=category)
                    if instruments:
                        active_usdt_count = 0
                        for instrument in instruments:
                            symbol = instrument.get('symbol', '')
                            status = instrument.get('status', '')
                            
                            if symbol.endswith('USDT') and status == 'Trading':
                                active_usdt_count += 1
                                if symbol not in all_valid_symbols:
                                    all_valid_symbols[symbol] = []
                                all_valid_symbols[symbol].append(category)
                        
                        print(f"✅ Категория '{category}': {active_usdt_count} активных USDT инструментов")
                
                except Exception as e:
                    print(f"⚠️ Ошибка получения инструментов для категории {category}: {e}")
            
            # Валидируем переданные символы
            for symbol in symbols:
                if symbol in all_valid_symbols:
                    validated_symbols.append(symbol)
                    symbol_categories[symbol] = all_valid_symbols[symbol]
            
            self.symbol_categories = symbol_categories
            print(f"✅ Валидировано {len(validated_symbols)} из {len(symbols)} символов")
            
            return validated_symbols
            
        except Exception as e:
            print(f"❌ Ошибка валидации символов: {e}")
            return []
    
    def load_symbols(self):
        """Загрузка списка символов"""
        try:
            # Сначала пытаемся загрузить из TickerDataLoader
            if self.ticker_loader:
                # Загружаем полные данные тикеров
                full_ticker_data = self.ticker_loader.load_tickers_data()
                if full_ticker_data and 'tickers' in full_ticker_data:
                    tickers = full_ticker_data['tickers']
                    
                    # Извлекаем USDT символы из списка тикеров
                    if isinstance(tickers, list):
                        usdt_symbols = [ticker['symbol'] for ticker in tickers 
                                      if ticker.get('symbol', '').endswith('USDT')]
                    else:
                        # Если это словарь (старый формат)
                        usdt_symbols = [symbol for symbol in tickers.keys() if symbol.endswith('USDT')]
                    
                    print(f"📊 Загружено символов из TickerDataLoader: {len(usdt_symbols)}")
                    
                    if usdt_symbols:
                        # Валидируем все символы через API
                        validated_symbols = self.validate_symbols_with_api(usdt_symbols)
                        
                        if validated_symbols:
                            self.symbols = validated_symbols
                            print(f"✅ Валидировано символов для обучения: {len(validated_symbols)}")
                            return
                        else:
                            print("⚠️ Не найдено валидных символов из TickerDataLoader")
                    else:
                        print("⚠️ Не найдено USDT символов в TickerDataLoader")
                else:
                    print(f"📊 Загружено символов из TickerDataLoader: 0")
            
            # Fallback: загружаем напрямую из API
            print("🔄 Загружаем символы напрямую из API...")
            try:
                instruments = self.ml_strategy.api_client.get_instruments_info(category='spot')
                if instruments:
                    api_symbols = []
                    for instrument in instruments:
                        symbol = instrument.get('symbol', '')
                        status = instrument.get('status', '')
                        
                        if symbol.endswith('USDT') and status == 'Trading':
                            api_symbols.append(symbol)
                    
                    if api_symbols:
                        # Убираем ограничение на 100 символов
                        self.symbols = api_symbols
                        print(f"✅ Загружено символов из API: {len(self.symbols)}")
                        
                        # Создаем информацию о категориях для API символов
                        self.symbol_categories = {symbol: ['spot'] for symbol in self.symbols}
                        return
                    
            except Exception as e:
                print(f"❌ Ошибка загрузки из API: {e}")
            
            # Последний fallback
            self.symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'DOTUSDT', 'LINKUSDT']
            self.symbol_categories = {symbol: ['spot'] for symbol in self.symbols}
            print(f"⚠️ Используем резервный список символов: {len(self.symbols)}")
            
        except Exception as e:
            print(f"❌ Критическая ошибка загрузки символов: {e}")
            self.symbols = ['BTCUSDT', 'ETHUSDT']
            self.symbol_categories = {symbol: ['spot'] for symbol in self.symbols}
    
    def choose_category(self, symbol: str) -> str:
        """Определение категории для символа"""
        if symbol in self.symbol_categories:
            categories = self.symbol_categories[symbol]
            if categories:
                # Предпочитаем spot, если доступен
                if 'spot' in categories:
                    return 'spot'
                else:
                    return categories[0]
        
        # Fallback: простая эвристика
        if symbol.endswith('USDT') and not symbol.endswith('PERP'):
            return 'spot'
        elif symbol.endswith('PERP') or symbol.endswith('USD'):
            return 'linear'
        else:
            return 'spot'
    
    def train_models(self):
        """Обучение моделей"""
        if not self.symbols:
            print("❌ Нет символов для обучения")
            return
        
        print(f"🚀 Начинаем обучение для {len(self.symbols)} символов...")
        
        successful_trainings = 0
        failed_trainings = 0
        total_symbols = len(self.symbols)
        
        for i, symbol in enumerate(self.symbols):
            try:
                print(f"\n[{i+1}/{total_symbols}] 🔄 Обучение модели для {symbol}...")
                
                # Определяем категорию
                category = self.choose_category(symbol)
                
                # Получаем исторические данные
                klines = []
                try:
                    api_response = self.ml_strategy.api_client.get_klines(
                        symbol=symbol,
                        interval='4h',
                        limit=1000,
                        category=category
                    )
                    
                    # Извлекаем данные из ответа API
                    if api_response and isinstance(api_response, dict) and 'list' in api_response:
                        raw_klines = api_response['list']
                        # Преобразуем формат API в ожидаемый формат
                        klines = []
                        for kline in raw_klines:
                            klines.append({
                                'timestamp': int(kline[0]),
                                'open': float(kline[1]),
                                'high': float(kline[2]),
                                'low': float(kline[3]),
                                'close': float(kline[4]),
                                'volume': float(kline[5])
                            })
                        print(f"📈 Загружены данные для {symbol}: {len(klines)} записей")
                    elif api_response and isinstance(api_response, list):
                        klines = api_response
                        print(f"📈 Загружены данные для {symbol}: {len(klines)} записей")
                    else:
                        print(f"⚠️ API не вернул данные для {symbol}")
                        
                except Exception as e:
                    error_msg = str(e)
                    if "Category is invalid" in error_msg:
                        print(f"⚠️ Неверная категория для {symbol}: {error_msg}")
                    elif "Not supported symbols" in error_msg:
                        print(f"⚠️ Символ {symbol} не поддерживается: {error_msg}")
                    else:
                        print(f"⚠️ Ошибка API для {symbol}: {error_msg}")
                
                # Если API не дал данных, пытаемся загрузить из кэша
                if not klines or len(klines) < 100:
                    try:
                        if self.ticker_loader:
                            historical_data = self.ticker_loader.get_historical_data(symbol)
                            if historical_data and len(historical_data) > len(klines):
                                klines = historical_data
                                print(f"📁 Загружены данные из кэша для {symbol}: {len(klines)} записей")
                    except Exception as e:
                        print(f"⚠️ Ошибка загрузки из кэша для {symbol}: {e}")
                
                # Проверяем достаточность данных
                min_required = 30
                if not klines or len(klines) < min_required:
                    print(f"⚠️ Недостаточно данных для {symbol}: {len(klines) if klines else 0} < {min_required}")
                    failed_trainings += 1
                    continue
                
                # Извлекаем признаки и метки
                features, labels = [], []
                window = self.ml_strategy.feature_window
                
                for j in range(window, len(klines) - 1):
                    try:
                        f = self.ml_strategy.extract_features(klines[j-window:j])
                        if f and len(f) > 0:
                            features.append(f)
                            # Создаем метку на основе изменения цены
                            current_price = float(klines[j]['close'])
                            future_price = float(klines[j + 1]['close'])
                            change = (future_price - current_price) / current_price
                            
                            # Улучшенный алгоритм генерации меток
                            # Используем процентили для более сбалансированного распределения
                            abs_change = abs(change)
                            
                            # Фиксированные пороги для лучшего баланса классов
                            if abs_change > 0.005:  # 0.5% - значимое движение
                                if change > 0:
                                    labels.append(1)  # рост
                                else:
                                    labels.append(-1)  # падение
                            else:
                                labels.append(0)  # боковик
                    except Exception as e:
                        continue
                
                # Проверяем качество данных
                min_features = 20
                if len(features) < min_features:
                    print(f"⚠️ Недостаточно признаков для {symbol}: {len(features)} < {min_features}")
                    failed_trainings += 1
                    continue
                
                # Проверяем баланс классов с более мягкими требованиями
                unique_labels = set(labels)
                if len(unique_labels) < 2:
                    print(f"⚠️ Недостаточное разнообразие меток для {symbol}: {unique_labels}")
                    failed_trainings += 1
                    continue
                
                # Проверяем минимальное количество каждого класса
                label_counts = {label: labels.count(label) for label in unique_labels}
                min_class_size = min(label_counts.values())
                if min_class_size < 5:  # минимум 5 примеров каждого класса
                    print(f"⚠️ Слишком мало примеров класса для {symbol}: {label_counts}")
                    failed_trainings += 1
                    continue
                
                # Обучаем модель
                success = self.ml_strategy.train_model(symbol, features, labels)
                
                if success:
                    # Сохраняем модель
                    try:
                        self.ml_strategy.save_models()
                        
                        # Получаем метрики точности
                        accuracy = self.ml_strategy.performance.get(symbol, {}).get('accuracy', 0.0)
                        samples = self.ml_strategy.performance.get(symbol, {}).get('samples', len(features))
                        
                        print(f"✅ Модель для {symbol} обучена (точность: {accuracy:.2%}, образцов: {samples})")
                        successful_trainings += 1
                        
                    except Exception as e:
                        print(f"⚠️ Ошибка сохранения модели для {symbol}: {e}")
                        failed_trainings += 1
                else:
                    print(f"❌ Ошибка обучения модели для {symbol}")
                    failed_trainings += 1
                
            except Exception as e:
                print(f"❌ Критическая ошибка при обучении {symbol}: {e}")
                failed_trainings += 1
        
        # Итоговая статистика
        print(f"\n🎉 Обучение завершено!")
        print(f"📊 Статистика: успешно {successful_trainings}, ошибок {failed_trainings} из {total_symbols}")
        if successful_trainings > 0:
            success_rate = (successful_trainings / total_symbols) * 100
            print(f"📈 Процент успеха: {success_rate:.1f}%")
    
    def run(self):
        """Запуск консольного тренера"""
        print("🤖 Консольный тренер ML моделей")
        print("=" * 50)
        
        # Загружаем символы
        self.load_symbols()
        
        if not self.symbols:
            print("❌ Не удалось загрузить символы для обучения")
            return
        
        # Запускаем обучение
        self.train_models()
        
        print("\n✅ Работа завершена!")
    
    def setup_file_monitoring(self):
        """Настройка мониторинга файла tickers_data.json"""
        try:
            # Путь к файлу с данными тикеров
            data_path = Path.home() / "AppData" / "Local" / "BybitTradingBot" / "data"
            
            if not data_path.exists():
                print(f"⚠️ Директория с данными не найдена: {data_path}")
                return
            
            # Создаем наблюдатель за файлами
            self.file_watcher = TickerDataWatcher(self)
            self.observer = Observer()
            self.observer.schedule(self.file_watcher, str(data_path), recursive=False)
            self.observer.start()
            
            print(f"👁️ Мониторинг файла tickers_data.json активирован")
            print(f"📁 Отслеживаемая директория: {data_path}")
            
        except Exception as e:
            print(f"❌ Ошибка настройки мониторинга файлов: {e}")
    
    def auto_retrain(self):
        """Автоматическое переобучение при обновлении данных"""
        if not self.auto_training_enabled:
            print("⏸️ Автоматическое обучение отключено")
            return
            
        try:
            print("🔄 Начинаем автоматическое переобучение...")
            
            # Перезагружаем символы
            old_count = len(self.symbols)
            self.load_symbols()
            new_count = len(self.symbols)
            
            print(f"📊 Символов: было {old_count}, стало {new_count}")
            
            if new_count == 0:
                print("❌ Нет символов для обучения")
                return
            
            # Запускаем обучение
            self.train_models()
            
            print("✅ Автоматическое переобучение завершено!")
            
        except Exception as e:
            print(f"❌ Ошибка автоматического переобучения: {e}")
    
    def stop_monitoring(self):
        """Остановка мониторинга файлов"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("🛑 Мониторинг файлов остановлен")
    
    def run_with_monitoring(self):
        """Запуск тренера с мониторингом файлов"""
        try:
            print("🤖 Консольный тренер ML моделей с автоматическим обучением")
            print("=" * 60)
            
            # Загружаем символы и обучаем модели
            self.load_symbols()
            
            if not self.symbols:
                print("❌ Не удалось загрузить символы для обучения")
                return
            
            # Запускаем первоначальное обучение
            self.train_models()
            
            print("\n🔄 Ожидание обновлений данных тикеров...")
            print("💡 Нажмите Ctrl+C для выхода")
            
            # Ожидаем обновления файлов
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n👋 Получен сигнал выхода...")
                
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
        finally:
            self.stop_monitoring()
            print("✅ Работа завершена!")

    def run(self):
        """Запуск консольного тренера"""
        print("🤖 Консольный тренер ML моделей")
        print("=" * 50)
        
        # Загружаем символы
        self.load_symbols()
        
        if not self.symbols:
            print("❌ Не удалось загрузить символы для обучения")
            return
        
        # Запускаем обучение
        self.train_models()
        
        print("\n✅ Работа завершена!")


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ML Trainer для криптовалютного бота')
    parser.add_argument('--auto', action='store_true', 
                       help='Запуск с автоматическим переобучением при обновлении данных')
    
    args = parser.parse_args()
    
    trainer = ConsoleTrainer()
    
    if args.auto:
        trainer.run_with_monitoring()
    else:
        trainer.run()


if __name__ == "__main__":
    main()