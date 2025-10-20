#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Независимая программа-торговец для автоматической торговли
Интегрируется с существующими программами тикеров и нейросети
"""

import sys
import os
import json
import pickle
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

# Настройка логирования на DEBUG уровень
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trader_program.log', encoding='utf-8')
    ]
)

# Добавляем путь к модулям
sys.path.append(str(os.path.join(os.path.dirname(__file__), 'src')))

# GUI импорты
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
        QPushButton, QLabel, QTextEdit, QGroupBox, QGridLayout,
        QProgressBar, QStatusBar, QFrame, QSplitter, QTableWidget,
        QTableWidgetItem, QHeaderView, QSpacerItem, QSizePolicy,
        QTabWidget, QLineEdit, QCheckBox
    )
    from PySide6.QtCore import QTimer, QThread, Signal, Qt, QMutex
    from PySide6.QtGui import QFont, QColor, QPalette, QTextCursor
    GUI_AVAILABLE = True
except ImportError as e:
    print(f"❌ Ошибка импорта GUI: {e}")
    GUI_AVAILABLE = False
    sys.exit(1)

# Импорт API клиента
try:
    from api.bybit_client import BybitClient
    from config import get_api_credentials
    import config
except ImportError as e:
    print(f"❌ Ошибка импорта API: {e}")
    sys.exit(1)

# Импорт Telegram уведомлений
try:
    from telegram_notifier import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Telegram уведомления недоступны: {e}")
    TelegramNotifier = None
    TELEGRAM_AVAILABLE = False


class TradingSignal:
    """Класс для представления торгового сигнала"""
    def __init__(self, symbol: str, signal: str, confidence: float, price: float, reason: str = ""):
        self.symbol = symbol
        self.signal = signal  # 'BUY' или 'SELL'
        self.confidence = confidence
        self.price = price
        self.reason = reason
        self.timestamp = datetime.now()
        self.execution_attempts = 0  # Счетчик попыток исполнения
        self.max_attempts = 3  # Максимальное количество попыток
        self.last_attempt_time = None  # Время последней попытки
        self.status = "PENDING"  # PENDING, EXECUTING, EXECUTED, FAILED


class DataCollector(QThread):
    """Поток для сбора данных от программы тикеров и нейросети"""
    data_updated = Signal(dict)
    log_message = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        # Используем TickerDataLoader для получения правильного пути
        from src.tools.ticker_data_loader import TickerDataLoader
        ticker_loader = TickerDataLoader()
        self.ticker_data_path = ticker_loader.get_data_file_path()
        self.models_path = Path("C:/Users/vlastelin8/Desktop/trade/crypto/src/strategies/models")
        self.mutex = QMutex()
        
    def run(self):
        """Основной цикл сбора данных"""
        self.running = True
        self.log_message.emit("🔄 Запуск сбора данных...")
        
        while self.running:
            try:
                # Собираем данные тикеров
                ticker_data = self.load_ticker_data()
                
                # Собираем данные нейросети
                ml_data = self.load_ml_data()
                
                # Объединяем данные
                combined_data = {
                    'ticker_data': ticker_data,
                    'ml_data': ml_data,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.data_updated.emit(combined_data)
                
                # Пауза между обновлениями
                time.sleep(5)
                
            except Exception as e:
                self.log_message.emit(f"❌ Ошибка сбора данных: {e}")
                time.sleep(10)
    
    def load_ticker_data(self) -> Dict:
        """Загрузка данных тикеров только через API"""
        try:
            # Используем только TickerDataLoader для получения реальных данных через API
            from src.tools.ticker_data_loader import TickerDataLoader
            ticker_loader = TickerDataLoader()
            ticker_data = ticker_loader.load_tickers_data()
            
            if ticker_data and 'tickers' in ticker_data:
                # Возвращаем только данные тикеров
                tickers = ticker_data['tickers']
                self.log_message.emit(f"✅ Загружены реальные данные тикеров через API. Последнее обновление: {ticker_data['update_time']}")
                return tickers
            else:
                self.log_message.emit("❌ Не удалось получить данные тикеров через API")
                return {}
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка загрузки данных тикеров через API: {e}")
            return {}
    
    def load_ml_data(self) -> Dict:
        """Загрузка данных нейросети"""
        try:
            ml_data = {}
            
            # Загружаем производительность моделей
            performance_file = self.models_path / "adaptive_ml_performance.json"
            if performance_file.exists():
                try:
                    with open(performance_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:  # Проверяем, что файл не пустой
                            ml_data['performance'] = json.loads(content)
                        else:
                            self.log_message.emit(f"⚠️ Файл {performance_file.name} пустой")
                except json.JSONDecodeError as e:
                    self.log_message.emit(f"⚠️ Ошибка JSON в {performance_file.name}: {e}")
            
            # Загружаем состояние обучения
            training_file = self.models_path / "adaptive_ml_training_state.json"
            if training_file.exists():
                try:
                    with open(training_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:  # Проверяем, что файл не пустой
                            ml_data['training_state'] = json.loads(content)
                        else:
                            self.log_message.emit(f"⚠️ Файл {training_file.name} пустой")
                except json.JSONDecodeError as e:
                    self.log_message.emit(f"⚠️ Ошибка JSON в {training_file.name}: {e}")
            
            return ml_data
            
        except Exception as e:
            self.log_message.emit(f"⚠️ Ошибка загрузки данных ML: {e}")
            return {}
    
    def stop(self):
        """Остановка сбора данных"""
        self.running = False


class SignalGenerator:
    """Генератор торговых сигналов"""
    
    def __init__(self, logger, banned_symbols=None):
        self.logger = logger
        self.min_confidence = 0.1  # Минимальная уверенность для сигнала (снижено до 0.1 для максимальной активности)
        self.banned_symbols = banned_symbols or []
        
    def generate_signals(self, data: Dict, portfolio: Dict) -> List[TradingSignal]:
        """Генерация торговых сигналов на основе данных"""
        signals = []
        
        try:
            ticker_data = data.get('ticker_data', {})
            ml_data = data.get('ml_data', {})
            
            # Отладочная информация о структуре данных
            self.logger.info(f"🔍 Тип ticker_data: {type(ticker_data)}")
            if isinstance(ticker_data, dict):
                self.logger.info(f"🔍 Ключи ticker_data: {list(ticker_data.keys())[:5]}")  # Первые 5 ключей
            elif isinstance(ticker_data, list):
                self.logger.info(f"🔍 ticker_data - список из {len(ticker_data)} элементов")
                if ticker_data:
                    self.logger.info(f"🔍 Первый элемент: {type(ticker_data[0])}")
            
            self.logger.info(f"🔍 Генерация сигналов: ticker_data={len(ticker_data)} символов, ml_data={len(ml_data)} записей")
            
            # Получаем список USDT пар для анализа
            usdt_pairs = self.get_usdt_pairs(ticker_data)
            self.logger.info(f"📊 Анализируем {len(usdt_pairs)} USDT пар")
            
            # Анализируем каждую пару
            analyzed_count = 0
            for symbol in usdt_pairs[:200]:  # Увеличиваем лимит для полноценного анализа нейросети
                try:
                    signal = self.analyze_symbol(symbol, ticker_data, ml_data, portfolio)
                    analyzed_count += 1
                    if signal and signal.confidence >= self.min_confidence:
                        signals.append(signal)
                        self.logger.info(f"✅ Сигнал {signal.signal} для {signal.symbol}: уверенность {signal.confidence:.2f}")
                except Exception as e:
                    self.logger.error(f"Ошибка анализа {symbol}: {e}")
            
            self.logger.info(f"📈 Проанализировано {analyzed_count} символов, найдено {len(signals)} сигналов")
            
            # Сортируем сигналы по уверенности (наименее рискованные первыми)
            signals.sort(key=lambda x: x.confidence, reverse=True)
            
            return signals[:50]  # Увеличиваем с 30 до 50 сигналов для более активной торговли
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации сигналов: {e}")
            return []
    
    def get_usdt_pairs(self, ticker_data) -> List[str]:
        """Получение списка USDT торговых пар с активным движением цены"""
        pairs = []
        active_pairs = []
        
        # Если ticker_data - это список словарей (как из TickerDataLoader)
        if isinstance(ticker_data, list):
            for ticker in ticker_data:
                if isinstance(ticker, dict) and 'symbol' in ticker:
                    symbol = ticker['symbol']
                    if (symbol.endswith('USDT') and 
                        symbol != 'USDT' and 
                        symbol not in self.banned_symbols):
                        pairs.append(symbol)
                        # Проверяем активность символа (есть ли изменение цены)
                        price_change = float(ticker.get('price24hPcnt', 0))
                        volume = float(ticker.get('volume24h', 0))
                        if abs(price_change) > 0.0001 or volume > 1000:  # Активные символы
                            active_pairs.append(symbol)
        # Если ticker_data - это словарь
        elif isinstance(ticker_data, dict):
            # Получаем все USDT пары из тикеров
            tickers = ticker_data.get('tickers', ticker_data)
            for symbol, ticker_info in tickers.items():
                if (symbol.endswith('USDT') and 
                    symbol != 'USDT' and 
                    symbol not in self.banned_symbols):
                    pairs.append(symbol)
                    # Проверяем активность символа
                    price_change = float(ticker_info.get('price24hPcnt', 0))
                    volume = float(ticker_info.get('volume24h', 0))
                    if abs(price_change) > 0.0001 or volume > 1000:  # Активные символы
                        active_pairs.append(symbol)
        
        # Приоритет активным символам, но добавляем популярные как резерв
        popular_pairs = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT',
            'XRPUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'LINKUSDT',
            'MATICUSDT', 'LTCUSDT', 'UNIUSDT', 'ATOMUSDT', 'FILUSDT'
        ]
        
        # Фильтруем популярные символы от запрещенных
        popular_pairs = [pair for pair in popular_pairs if pair not in self.banned_symbols]
        
        # Используем активные символы, если есть, иначе популярные
        if active_pairs:
            # Добавляем популярные символы к активным для полноты анализа
            final_pairs = list(set(active_pairs + popular_pairs))
        else:
            final_pairs = popular_pairs
        
        # Фильтруем недоступные символы для testnet
        invalid_symbols = {'SHIB1000USDT', 'BANDUSDT', 'WIFUSDT', 'HBARUSDT'}
        final_pairs = [pair for pair in final_pairs if pair not in invalid_symbols]
        
        self.logger.info(f"🎯 Найдено {len(active_pairs)} активных и {len(final_pairs)} общих USDT пар для анализа")
        self.logger.info(f"🚫 Исключено {len(self.banned_symbols)} запрещенных символов: {self.banned_symbols}")
        return final_pairs
    
    def analyze_symbol(self, symbol: str, ticker_data, ml_data: Dict, portfolio: Dict) -> Optional[TradingSignal]:
        """Анализ конкретного символа для генерации сигнала"""
        try:
            # Получаем данные по символу
            symbol_ticker = {}
            
            # Если ticker_data - это список словарей
            if isinstance(ticker_data, list):
                for ticker in ticker_data:
                    if isinstance(ticker, dict) and ticker.get('symbol') == symbol:
                        symbol_ticker = ticker
                        break
            # Если ticker_data - это словарь
            elif isinstance(ticker_data, dict):
                symbol_ticker = ticker_data.get(symbol, {})
            if not symbol_ticker:
                return None
            
            # Получаем текущую цену
            current_price = float(symbol_ticker.get('lastPrice', 0))
            if current_price <= 0:
                return None
            
            # Получаем изменения цены (используем правильное поле от Bybit API)
            # Исправляем поле для получения изменения цены - используем priceChangePercent
            price_change_24h = float(symbol_ticker.get('priceChangePercent', 0))
            
            # Получаем данные ML для символа
            ml_performance = ml_data.get('performance', {}).get(symbol, {})
            ml_training = ml_data.get('training_state', {}).get(symbol, {})
            
            # Базовая логика генерации сигналов
            signal_type = None
            confidence = 0.0
            reason = ""
            
            # Логируем данные для отладки каждого символа
            # Исправляем извлечение ML точности - данные хранятся как {"SYMBOL": accuracy_value}
            ml_accuracy = ml_performance if isinstance(ml_performance, (int, float)) else 0
            self.logger.debug(f"🔍 Анализ {symbol}: цена=${current_price:.6f}, изменение 24ч={price_change_24h:.2%}, ML точность={ml_accuracy:.2f}")
            
            # Проверяем ML данные
            if ml_accuracy > 0.1:  # Снижаем порог с 0.3 до 0.1 для еще большего количества сигналов
                self.logger.debug(f"🤖 ML модель активна для {symbol}, точность: {ml_accuracy:.2f}")
                # Используем ML логику с более мягкими условиями
                if price_change_24h > 0.0001:  # Рост более 0.01% (было 0.05%)
                    signal_type = 'BUY'
                    confidence = min(0.8, ml_accuracy * 0.9)
                    reason = f"ML модель (точность: {ml_accuracy:.2f}), рост 24ч: {price_change_24h:.2%}"
                    self.logger.debug(f"🟢 ML BUY сигнал для {symbol}: изменение {price_change_24h:.4f} > 0.0001")
                elif price_change_24h < -0.0001:  # Падение более 0.01% (было 0.05%)
                    # Проверяем, есть ли актив в портфолио для продажи
                    base_asset = symbol.replace('USDT', '')
                    if base_asset in portfolio and float(portfolio[base_asset]) > 0:
                        signal_type = 'SELL'
                        confidence = min(0.8, ml_accuracy * 0.9)
                        reason = f"ML модель (точность: {ml_accuracy:.2f}), падение 24ч: {price_change_24h:.2%}"
                        self.logger.debug(f"🔴 ML SELL сигнал для {symbol}: изменение {price_change_24h:.4f} < -0.0001")
                    else:
                        self.logger.debug(f"⚠️ ML SELL условие выполнено для {symbol}, но актив {base_asset} не найден в портфолио")
                else:
                    self.logger.debug(f"⚪ ML условия не выполнены для {symbol}: изменение {price_change_24h:.4f} в диапазоне [-0.0005, 0.0005]")
            else:
                self.logger.debug(f"📊 Техническая логика для {symbol}, ML точность: {ml_accuracy:.2f} < 0.3")
                # Используем простую техническую логику с более мягкими условиями
                if price_change_24h > 0.0003:  # Рост 0.03% (было 0.1%)
                    signal_type = 'BUY'
                    confidence = min(0.7, abs(price_change_24h) * 100)  # Увеличиваем множитель для компенсации
                    reason = f"Технический анализ, рост: {price_change_24h:.2%}"
                    self.logger.debug(f"🟢 Технический BUY сигнал для {symbol}: изменение {price_change_24h:.4f} > 0.0003")
                elif price_change_24h < -0.0003:  # Падение 0.03% (было 0.1%)
                    base_asset = symbol.replace('USDT', '')
                    
                    # Отладочная информация о портфолио
                    self.logger.debug(f"🔍 Проверка портфолио для {base_asset}:")
                    self.logger.debug(f"🔍 Тип портфолио: {type(portfolio)}")
                    self.logger.debug(f"🔍 Ключи портфолио: {list(portfolio.keys()) if isinstance(portfolio, dict) else 'Не словарь'}")
                    
                    # Проверяем наличие актива в портфолио
                    asset_in_portfolio = base_asset in portfolio if isinstance(portfolio, dict) else False
                    asset_balance = 0
                    
                    if asset_in_portfolio:
                        try:
                            asset_balance = float(portfolio[base_asset])
                            self.logger.debug(f"🔍 Баланс {base_asset}: {asset_balance}")
                        except (ValueError, TypeError) as e:
                            self.logger.debug(f"⚠️ Ошибка преобразования баланса {base_asset}: {e}")
                            asset_balance = 0
                    
                    if asset_in_portfolio and asset_balance > 0:
                        signal_type = 'SELL'
                        confidence = min(0.7, abs(price_change_24h) * 100)  # Увеличиваем множитель для компенсации
                        reason = f"Технический анализ, падение: {price_change_24h:.2%}"
                        self.logger.debug(f"🔴 Технический SELL сигнал для {symbol}: изменение {price_change_24h:.4f} < -0.0003, баланс {base_asset}: {asset_balance}")
                    else:
                        if not asset_in_portfolio:
                            self.logger.debug(f"⚠️ Технический SELL условие выполнено для {symbol}, но актив {base_asset} не найден в портфолио (ключи: {list(portfolio.keys()) if isinstance(portfolio, dict) else 'Не словарь'})")
                        else:
                            self.logger.debug(f"⚠️ Технический SELL условие выполнено для {symbol}, но баланс {base_asset} = {asset_balance} <= 0")
                else:
                    self.logger.debug(f"⚪ Технические условия не выполнены для {symbol}: изменение {price_change_24h:.4f} в диапазоне [-0.0003, 0.0003]")
            
            if signal_type and confidence >= self.min_confidence:
                self.logger.info(f"🎯 Потенциальный сигнал {signal_type} для {symbol}: уверенность {confidence:.2f}")
                return TradingSignal(symbol, signal_type, confidence, current_price, reason)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа символа {symbol}: {e}")
            return None


class TradingEngine(QThread):
    """Торговый движок"""
    trade_executed = Signal(dict)
    log_message = Signal(str)
    status_changed = Signal(str)
    
    def __init__(self, bybit_client, trading_enabled=True, telegram_notifier=None):  # Добавлен параметр telegram_notifier
        super().__init__()
        self.bybit_client = bybit_client
        self.running = False
        self.trading_enabled = trading_enabled  # Флаг включения торговли
        self.signals_queue = []
        self.portfolio = {}
        self.logger = logging.getLogger(__name__)
        
        # Централизованный список проблемных символов для исключения из торговли
        self.banned_symbols = [
            'BBSOLUSDT',      # Проблемы с минимальными суммами и округлением
            'BABYDOGEUSDT',   # Ошибки API периода и превышение лимитов
            'BBDUSDT',        # Ошибки API периода
            'USDT',           # Не является торговой парой
            'USDTUSDT'        # Не является торговой парой
        ]
        
        self.signal_generator = SignalGenerator(self.logger, self.banned_symbols)
        self.mutex = QMutex()
        self.last_buy_times = {}  # Словарь для отслеживания времени последних покупок
        self.holding_start_times = {}  # Словарь для отслеживания времени начала удержания позиций
        self.position_values_usdt = {}  # Словарь для отслеживания общей стоимости позиций по монетам
        self.buy_cooldown = 24 * 60 * 60  # 24 часа кулдаун для повторной покупки той же монеты
        self.signals_file = Path("signals_queue.json")  # Файл для сохранения очереди сигналов
        
        # Новые параметры для контроля риска
        self.max_open_positions = 10  # Максимальное количество одновременно открытых позиций
        self.risk_per_trade = config.MAX_POSITION_PERCENT  # Используем значение из конфига (3%)
        
        # Используем переданный telegram_notifier или создаем новый
        self.telegram_notifier = telegram_notifier
        if self.telegram_notifier and hasattr(self.telegram_notifier, 'set_callback'):
            # Настройка callback функций
            self.telegram_notifier.set_callback('get_balance', self.get_balance_for_telegram)
            self.telegram_notifier.set_callback('stop_trading', self.stop_trading_for_telegram)
        
        self.load_signals_queue()  # Загружаем сохраненную очередь при инициализации
        
    def run(self):
        """Основной торговый цикл"""
        self.running = True
        self.status_changed.emit("🟢 Торговля активна")
        self.log_message.emit("🚀 Запуск автоматической торговли...")
        
        # Инициализируем генератор сигналов
        signal_generator = SignalGenerator(self.logger, self.banned_symbols)
        
        while self.running:
            try:
                # Обновляем портфолио
                self.update_portfolio()
                
                # Проверяем существующие позиции на предмет умного выхода
                self.check_smart_exit_conditions()
                
                # Генерируем торговые сигналы автоматически
                try:
                    # Загружаем данные для анализа
                    ticker_data = self.load_ticker_data()
                    ml_data = self.load_ml_data()
                    
                    if ticker_data:
                        # Генерируем сигналы на основе данных
                        new_signals = signal_generator.generate_signals(
                            {'ticker_data': ticker_data, 'ml_data': ml_data}, 
                            self.portfolio
                        )
                        
                        if new_signals:
                            self.add_signals(new_signals)
                            self.log_message.emit(f"🎯 Сгенерировано {len(new_signals)} новых торговых сигналов")
                    
                except Exception as e:
                    self.log_message.emit(f"⚠️ Ошибка генерации сигналов: {e}")
                
                # Обрабатываем сигналы из очереди (до 10 сигналов за итерацию)
                signals_processed = 0
                max_signals_per_iteration = 10
                
                while self.signals_queue and signals_processed < max_signals_per_iteration:
                    signal = self.signals_queue.pop(0)
                    self.process_signal(signal)
                    signals_processed += 1
                
                if signals_processed > 0:
                    self.log_message.emit(f"🔄 Обработано {signals_processed} сигналов, осталось в очереди: {len(self.signals_queue)}")
                
                # Очищаем провалившиеся сигналы из очереди
                self.cleanup_failed_signals()
                
                time.sleep(10)  # Увеличиваем паузу для более стабильной работы
                
            except Exception as e:
                self.log_message.emit(f"❌ Ошибка в торговом цикле: {e}")
                time.sleep(5)
        
        self.status_changed.emit("🔴 Торговля остановлена")
    
    def get_significant_positions(self) -> int:
        """
        Подсчет открытых позиций с игнорированием микроскопических остатков (< $5 USDT)
        """
        try:
            significant_positions = 0
            ignored_remnants = []
            
            # Загружаем данные тикеров для получения цен
            ticker_data = self.load_ticker_data()
            
            for coin, amount in self.portfolio.items():
                if coin == 'USDT' or amount <= 0:
                    continue
                
                # Получаем цену монеты
                symbol = f"{coin}USDT"
                price = 0
                
                if ticker_data and symbol in ticker_data:
                    price = float(ticker_data[symbol].get('lastPrice', 0))
                
                # Если цена не найдена в ticker_data, пытаемся получить через API
                if price <= 0:
                    try:
                        ticker_info = self.bybit_client.get_tickers(category='spot', symbol=symbol)
                        if ticker_info and 'result' in ticker_info and 'list' in ticker_info['result']:
                            ticker_list = ticker_info['result']['list']
                            if ticker_list:
                                price = float(ticker_list[0].get('lastPrice', 0))
                    except Exception as e:
                        self.log_message.emit(f"⚠️ Ошибка получения цены для {symbol}: {e}")
                        continue
                
                # Рассчитываем стоимость позиции в USDT
                position_value = amount * price
                
                # Проверяем, является ли позиция значимой (>= $5)
                if position_value >= 5.0:
                    significant_positions += 1
                    self.log_message.emit(f"💰 Значимая позиция: {coin} = {amount:.6f} × ${price:.6f} = ${position_value:.2f}")
                else:
                    ignored_remnants.append({
                        'coin': coin,
                        'amount': amount,
                        'price': price,
                        'value': position_value
                    })
            
            # Логируем игнорируемые остатки
            if ignored_remnants:
                self.log_message.emit(f"🔍 Игнорируем {len(ignored_remnants)} микроскопических остатков:")
                for remnant in ignored_remnants:
                    self.log_message.emit(f"   {remnant['coin']}: {remnant['amount']:.6f} × ${remnant['price']:.6f} = ${remnant['value']:.2f}")
            
            self.log_message.emit(f"📊 Значимых позиций: {significant_positions} (игнорировано {len(ignored_remnants)} остатков < $5)")
            return significant_positions
            
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка подсчета значимых позиций: {e}")
            # В случае ошибки возвращаем старый способ подсчета
            return len([coin for coin, amount in self.portfolio.items() if coin != 'USDT' and amount > 0])

    def update_position_values(self):
        """Обновление стоимости позиций в USDT"""
        try:
            # Получаем текущие цены
            ticker_data = self.bybit_client.get_tickers(category='spot')
            if not ticker_data or 'list' not in ticker_data:
                self.log_message.emit("⚠️ Не удалось получить данные тикеров для обновления стоимости позиций")
                return
            
            # Создаем словарь цен
            prices = {}
            for ticker in ticker_data['list']:
                symbol = ticker.get('symbol', '')
                price = float(ticker.get('lastPrice', 0))
                if symbol and price > 0:
                    prices[symbol] = price
            
            # Обновляем стоимость позиций
            self.position_values_usdt.clear()
            for coin, amount in self.portfolio.items():
                if coin == 'USDT' or amount <= 0:
                    continue
                
                symbol = f"{coin}USDT"
                if symbol in prices:
                    value_usdt = amount * prices[symbol]
                    self.position_values_usdt[symbol] = value_usdt
                    self.log_message.emit(f"💰 {symbol}: {amount:.6f} × ${prices[symbol]:.4f} = ${value_usdt:.2f}")
                else:
                    self.log_message.emit(f"⚠️ Не найдена цена для {symbol}")
            
            total_value = sum(self.position_values_usdt.values())
            self.log_message.emit(f"📊 Общая стоимость позиций: ${total_value:.2f}")
            
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка обновления стоимости позиций: {e}")

    def load_ticker_data(self) -> Dict:
        """Загрузка данных тикеров через API"""
        try:
            # Используем TickerDataLoader для получения реальных данных через API
            from src.tools.ticker_data_loader import TickerDataLoader
            ticker_loader = TickerDataLoader()
            ticker_data = ticker_loader.load_tickers_data()
            
            if ticker_data and 'tickers' in ticker_data:
                # Возвращаем только данные тикеров
                tickers = ticker_data['tickers']
                self.log_message.emit(f"✅ Загружены реальные данные тикеров через API. Последнее обновление: {ticker_data['update_time']}")
                return tickers
            else:
                self.log_message.emit("❌ Не удалось получить данные тикеров через API")
                return {}
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка загрузки данных тикеров через API: {e}")
            return {}
    
    def load_ml_data(self) -> Dict:
        """Загрузка ML данных"""
        try:
            models_path = Path("src/strategies/models")
            ml_data = {}
            
            # Загружаем данные производительности ML
            perf_file = models_path / "adaptive_ml_performance.json"
            if perf_file.exists():
                with open(perf_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        ml_data['performance'] = json.loads(content)
            
            # Загружаем состояние обучения ML
            state_file = models_path / "adaptive_ml_training_state.json"
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        ml_data['training_state'] = json.loads(content)
            
            return ml_data
        except Exception as e:
            self.log_message.emit(f"⚠️ Ошибка загрузки ML данных: {e}")
        return {}
    
    def get_instrument_info(self, symbol: str) -> Dict:
        """Получение информации об инструменте через API"""
        try:
            # Используем API endpoint /v5/market/instruments-info
            response = self.bybit_client.get_instruments_info(
                category='spot',
                symbol=symbol
            )
            
            self.log_message.emit(f"🔍 API ответ для {symbol}: {response}")
            
            # Проверяем, что response - это список инструментов
            if response and isinstance(response, list) and len(response) > 0:
                instrument = response[0]
                
                self.log_message.emit(f"🔍 Инструмент {symbol}: {instrument} (тип: {type(instrument)})")
                
                # Проверяем, что instrument - это словарь
                if isinstance(instrument, dict):
                    lot_size_filter = instrument.get('lotSizeFilter', {})
                    
                    # Извлекаем минимальные и максимальные значения
                    min_order_qty = float(lot_size_filter.get('minOrderQty', 0))
                    min_order_amt = float(lot_size_filter.get('minOrderAmt', 5))  # По умолчанию 5 USDT
                    max_order_qty = float(lot_size_filter.get('maxOrderQty', 0))  # Максимальное количество
                    max_market_order_qty = float(lot_size_filter.get('maxMarketOrderQty', 0))  # Максимальное количество для рыночных ордеров
                    qty_step = float(lot_size_filter.get('qtyStep', lot_size_filter.get('minOrderQty', 0.00001)))
                    
                    # Если qtyStep равен 0, используем minOrderQty как шаг
                    if qty_step == 0:
                        qty_step = min_order_qty if min_order_qty > 0 else 0.00001
                    
                    # Используем maxMarketOrderQty для рыночных ордеров, если оно меньше maxOrderQty
                    # Это решает проблему с нереалистично большими значениями maxOrderQty
                    effective_max_qty = max_order_qty
                    if max_market_order_qty > 0 and (max_order_qty == 0 or max_market_order_qty < max_order_qty):
                        effective_max_qty = max_market_order_qty
                        self.log_message.emit(f"📊 {symbol}: Используем maxMarketOrderQty={max_market_order_qty} вместо maxOrderQty={max_order_qty}")
                    
                    self.log_message.emit(f"📊 {symbol}: minOrderQty={min_order_qty}, minOrderAmt={min_order_amt}, maxOrderQty={max_order_qty}, maxMarketOrderQty={max_market_order_qty}, effectiveMaxQty={effective_max_qty}, qtyStep={qty_step}")
                    
                    return {
                        'symbol': symbol,
                        'minOrderQty': min_order_qty,
                        'minOrderAmt': min_order_amt,
                        'maxOrderQty': effective_max_qty,  # Используем эффективное максимальное количество
                        'qtyStep': qty_step,
                        'basePrecision': lot_size_filter.get('basePrecision', '0.00001'),
                        'quotePrecision': lot_size_filter.get('quotePrecision', '0.0000001')
                    }
                else:
                    self.log_message.emit(f"⚠️ Неожиданная структура данных инструмента {symbol}: {type(instrument)}")
            else:
                # Возможно, response имеет стандартную структуру API
                if response and isinstance(response, dict) and response.get('retCode') == 0:
                    result = response.get('result', {})
                    instruments_list = result.get('list', [])
                    
                    self.log_message.emit(f"🔍 Список инструментов для {symbol}: {instruments_list}")
                    
                    if instruments_list and len(instruments_list) > 0:
                        instrument = instruments_list[0]
                        
                        self.log_message.emit(f"🔍 Инструмент {symbol}: {instrument} (тип: {type(instrument)})")
                        
                        # Проверяем, что instrument - это словарь
                        if isinstance(instrument, dict):
                            lot_size_filter = instrument.get('lotSizeFilter', {})
                            
                            # Извлекаем минимальные и максимальные значения
                            min_order_qty = float(lot_size_filter.get('minOrderQty', 0))
                            min_order_amt = float(lot_size_filter.get('minOrderAmt', 5))  # По умолчанию 5 USDT
                            max_order_qty = float(lot_size_filter.get('maxOrderQty', 0))  # Максимальное количество
                            max_market_order_qty = float(lot_size_filter.get('maxMarketOrderQty', 0))  # Максимальное количество для рыночных ордеров
                            qty_step = float(lot_size_filter.get('qtyStep', 0.0))
                            
                            # Используем maxMarketOrderQty для рыночных ордеров, если оно меньше maxOrderQty
                            # Это решает проблему с нереалистично большими значениями maxOrderQty
                            effective_max_qty = max_order_qty
                            if max_market_order_qty > 0 and (max_order_qty == 0 or max_market_order_qty < max_order_qty):
                                effective_max_qty = max_market_order_qty
                                self.log_message.emit(f"📊 {symbol}: Используем maxMarketOrderQty={max_market_order_qty} вместо maxOrderQty={max_order_qty}")
                            
                            self.log_message.emit(f"📊 {symbol}: minOrderQty={min_order_qty}, minOrderAmt={min_order_amt}, maxOrderQty={max_order_qty}, maxMarketOrderQty={max_market_order_qty}, effectiveMaxQty={effective_max_qty}, qtyStep={qty_step}")
                            
                            return {
                                'symbol': symbol,
                                'minOrderQty': min_order_qty,
                                'minOrderAmt': min_order_amt,
                                'maxOrderQty': effective_max_qty,  # Используем эффективное максимальное количество
                                'qtyStep': qty_step,
                                'basePrecision': lot_size_filter.get('basePrecision', '0.00001'),
                                'quotePrecision': lot_size_filter.get('quotePrecision', '0.0000001')
                            }
                        else:
                            self.log_message.emit(f"⚠️ Неожиданная структура данных инструмента {symbol}: {type(instrument)}")
                    else:
                        self.log_message.emit(f"⚠️ Инструмент {symbol} не найден в ответе API")
                else:
                    error_msg = response.get('retMsg', 'Неизвестная ошибка') if isinstance(response, dict) else 'Неожиданный формат ответа'
                    self.log_message.emit(f"❌ Ошибка получения информации об инструменте {symbol}: {error_msg}")
                
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка запроса информации об инструменте {symbol}: {e}")
        
        # Возвращаем значения по умолчанию в случае ошибки
        return {
            'symbol': symbol,
            'minOrderQty': 0.00001,
            'minOrderAmt': 5.0,  # По умолчанию 5 USDT для большинства символов
            'qtyStep': 0.00001,  # По умолчанию
            'basePrecision': '0.00001',
            'quotePrecision': '0.0000001'
        }
    
    def add_signals(self, signals: List[TradingSignal]):
        """Добавление сигналов в очередь с проверкой кулдауна и фильтрацией по доступности баланса"""
        self.mutex.lock()
        try:
            filtered_signals = []
            current_time = time.time()
            usdt_balance = self.portfolio.get('USDT', 0)
            
            # Детальное логирование начального состояния
            self.log_message.emit(f"🔍 Обработка {len(signals)} сигналов. USDT баланс: ${usdt_balance:.2f}")
            
            # Проверяем количество открытых позиций (игнорируем микроскопические остатки < $5)
            open_positions = self.get_significant_positions()
            
            self.log_message.emit(f"📊 Открытых позиций: {open_positions}/{self.max_open_positions}")
            
            for signal in signals:
                self.log_message.emit(f"🔍 Обрабатываем сигнал {signal.symbol} ({signal.signal}), цена: ${signal.price:.6f}, уверенность: {signal.confidence:.2f}")
                
                # Проверяем кулдаун только для сигналов на покупку (24 часа)
                if signal.signal == 'BUY' and signal.symbol in self.last_buy_times:
                    time_since_last_buy = current_time - self.last_buy_times[signal.symbol]
                    if time_since_last_buy < self.buy_cooldown:
                        remaining_time = self.buy_cooldown - time_since_last_buy
                        remaining_hours = remaining_time / 3600
                        self.log_message.emit(f"⏳ 24-часовой кулдаун для {signal.symbol}: осталось {remaining_hours:.1f} часов (сигнал отклонен)")
                        continue
                
                # Фильтрация сигналов на покупку по доступности баланса
                if signal.signal == 'BUY':
                    # Проверяем максимальное количество позиций
                    if open_positions >= self.max_open_positions:
                        self.log_message.emit(f"⚠️ Достигнуто максимальное количество позиций ({self.max_open_positions}). Сигнал {signal.symbol} отклонен")
                        continue
                    
                    # Проверяем минимальную сумму для покупки
                    try:
                        instrument_info = self.get_instrument_info(signal.symbol)
                        min_trade_amount = max(float(instrument_info['minOrderAmt']), 5.0)  # API минимум $5
                        
                        # Детальное логирование параметров инструмента
                        self.log_message.emit(f"📋 {signal.symbol} - minOrderAmt: ${instrument_info['minOrderAmt']}, minOrderQty: {instrument_info['minOrderQty']}, qtyStep: {instrument_info['qtyStep']}")
                        
                        # Добавляем проверку максимальной аллокации на одну монету (50% баланса)
                        max_allocation_per_coin = usdt_balance * 0.5
                        
                        # Проверяем текущую стоимость позиции по данной монете
                        current_position_value = self.position_values_usdt.get(signal.symbol, 0)
                        
                        self.log_message.emit(f"💰 {signal.symbol} - минимальная сумма: ${min_trade_amount:.2f}, "
                                            f"макс. аллокация: ${max_allocation_per_coin:.2f}, "
                                            f"текущая позиция: ${current_position_value:.2f}")
                        
                        # Проверяем, что у нас достаточно баланса для минимальной торговли
                        if usdt_balance < min_trade_amount:
                            self.log_message.emit(f"⚠️ Недостаточно USDT для {signal.symbol}: ${usdt_balance:.2f} < ${min_trade_amount:.2f} (сигнал отклонен)")
                            continue
                        
                        # Проверяем, что минимальная сумма не превышает 50% баланса
                        if min_trade_amount > max_allocation_per_coin:
                            self.log_message.emit(f"⚠️ Минимальная сумма для {signal.symbol} (${min_trade_amount:.2f}) превышает 50% баланса (${max_allocation_per_coin:.2f}) (сигнал отклонен)")
                            continue
                        
                        # Проверяем, что новая покупка не превысит лимит 50% баланса на одну монету
                        if current_position_value + min_trade_amount > max_allocation_per_coin:
                            available_allocation = max_allocation_per_coin - current_position_value
                            self.log_message.emit(f"⚠️ {signal.symbol}: Превышен лимит 50% баланса на монету. "
                                                f"Текущая позиция: ${current_position_value:.2f}, "
                                                f"доступно: ${available_allocation:.2f}, "
                                                f"минимум для покупки: ${min_trade_amount:.2f} (сигнал отклонен)")
                            continue
                            
                    except Exception as e:
                        self.log_message.emit(f"⚠️ Ошибка проверки инструмента {signal.symbol}: {e} (сигнал отклонен)")
                        continue
                
                # Фильтрация сигналов на продажу по доступности активов
                elif signal.signal == 'SELL':
                    # Извлекаем базовый актив из символа (например, BTC из BTCUSDT)
                    base_asset = signal.symbol.replace('USDT', '')
                    asset_balance = self.portfolio.get(base_asset, 0)
                    
                    self.log_message.emit(f"💰 {signal.symbol} - баланс {base_asset}: {asset_balance}")
                    
                    # Проверяем, есть ли актив для продажи
                    if asset_balance <= 0:
                        self.log_message.emit(f"⚠️ Недостаточно {base_asset} для продажи {signal.symbol}: {asset_balance} (сигнал отклонен)")
                        continue
                    
                    # Проверяем минимальные требования для продажи
                    try:
                        instrument_info = self.get_instrument_info(signal.symbol)
                        min_order_qty = float(instrument_info['minOrderQty'])
                        min_order_amt = float(instrument_info['minOrderAmt'])
                        
                        # Проверяем, что количество актива больше минимального
                        if asset_balance < min_order_qty:
                            self.log_message.emit(f"⚠️ {signal.symbol}: количество {base_asset} ({asset_balance}) меньше минимального ({min_order_qty}) (сигнал отклонен)")
                            continue
                        
                        # Проверяем, что стоимость продажи больше минимальной суммы
                        # Временно снижаем минимум для тестирования с $5.00 до $2.00
                        temp_min_sell_amount = min(min_order_amt, 2.0)
                        estimated_value = asset_balance * signal.price
                        if estimated_value < temp_min_sell_amount:
                            self.log_message.emit(f"⚠️ {signal.symbol}: стоимость продажи (${estimated_value:.2f}) меньше минимальной (${temp_min_sell_amount:.2f}) (сигнал отклонен)")
                            continue
                            
                    except Exception as e:
                        self.log_message.emit(f"⚠️ Ошибка проверки инструмента для продажи {signal.symbol}: {e} (сигнал отклонен)")
                        continue
                
                self.log_message.emit(f"✅ Сигнал {signal.symbol} прошел все проверки и добавлен в очередь")
                filtered_signals.append(signal)
            
            self.signals_queue.extend(filtered_signals)
            if filtered_signals:
                self.log_message.emit(f"📊 Добавлено {len(filtered_signals)} сигналов в очередь (всего в очереди: {len(self.signals_queue)})")
                self.save_signals_queue()  # Сохраняем изменения в файл
            if len(filtered_signals) < len(signals):
                rejected_count = len(signals) - len(filtered_signals)
                self.log_message.emit(f"🚫 Отклонено {rejected_count} сигналов из-за ограничений")
        finally:
            self.mutex.unlock()
    
    def update_portfolio(self):
        """Обновление портфолио с улучшенной обработкой ошибок"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.log_message.emit(f"📊 Обновление портфолио (попытка {attempt + 1}/{max_retries})")
                
                # Получаем данные о балансе
                balance_data = self.bybit_client.get_unified_balance_flat()
                
                if not balance_data:
                    self.log_message.emit("⚠️ Получен пустой ответ при запросе баланса")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return
                
                # Проверяем структуру данных
                if not isinstance(balance_data, dict):
                    self.log_message.emit(f"⚠️ Неожиданная структура данных баланса: {type(balance_data)}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return
                
                # Проверяем, что balance_data содержит ключ 'coins'
                if 'coins' not in balance_data:
                    self.log_message.emit(f"⚠️ Отсутствует ключ 'coins' в данных баланса: {balance_data}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return
                
                # Обрабатываем данные о монетах
                coins_data = balance_data['coins']
                
                self.log_message.emit(f"🔍 Обработка данных монет: {coins_data}")
                
                # Проверяем, есть ли данные для обработки
                if not coins_data:
                    self.log_message.emit("⚠️ Получены пустые данные о монетах, сохраняем текущий портфолио")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return
                
                # Создаем временный портфолио для новых данных
                temp_portfolio = {}
                
                if isinstance(coins_data, dict):
                    # Если coins - это словарь с парами coin_name: balance
                    for coin_name, balance in coins_data.items():
                        try:
                            # Преобразуем Decimal в float
                            balance_float = float(balance) if balance else 0
                            if balance_float > 0:
                                temp_portfolio[coin_name] = balance_float
                                self.log_message.emit(f"💰 Обработана монета {coin_name}: {balance_float}")
                        except (ValueError, TypeError) as e:
                            self.log_message.emit(f"⚠️ Ошибка обработки монеты {coin_name}: {e}")
                elif isinstance(coins_data, list):
                    # Если coins - это список
                    for coin_info in coins_data:
                        if isinstance(coin_info, dict):
                            coin_name = coin_info.get('coin', '')
                            balance = coin_info.get('walletBalance', 0)
                            try:
                                balance_float = float(balance) if balance else 0
                                if balance_float > 0 and coin_name:
                                    temp_portfolio[coin_name] = balance_float
                                    self.log_message.emit(f"💰 Обработана монета {coin_name}: {balance_float}")
                            except (ValueError, TypeError) as e:
                                self.log_message.emit(f"⚠️ Ошибка обработки монеты {coin_name}: {e}")
                
                # Обновляем портфолио только если получили валидные данные
                if temp_portfolio:
                    # Сохраняем предыдущий баланс USDT для сравнения
                    old_usdt_balance = self.portfolio.get('USDT', 0)
                    
                    self.portfolio = temp_portfolio
                    self.log_message.emit(f"✅ Портфолио успешно обновлено новыми данными")
                    
                    # Обновляем стоимость позиций в USDT
                    self.update_position_values()
                    
                    # Отправляем Telegram уведомление об изменении баланса
                    new_usdt_balance = self.portfolio.get('USDT', 0)
                    if self.telegram_notifier and abs(new_usdt_balance - old_usdt_balance) > 0.01:
                        self.telegram_notifier.notify_balance_change(old_usdt_balance, new_usdt_balance)
                else:
                    self.log_message.emit("⚠️ Не получено валидных данных о балансе, сохраняем текущий портфолио")
                
                # Логируем успешное обновление
                total_coins = len(self.portfolio)
                total_usdt = self.portfolio.get('USDT', 0)
                self.log_message.emit(f"✅ Портфолио обновлено: {total_coins} монет, USDT: ${total_usdt:.2f}")
                return  # Успешно обновили, выходим
                
            except Exception as e:
                error_msg = f"❌ Ошибка обновления портфолио (попытка {attempt + 1}): {e}"
                self.log_message.emit(error_msg)
                
                if attempt < max_retries - 1:
                    self.log_message.emit(f"⏳ Повторная попытка через {retry_delay} секунд...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Увеличиваем задержку для следующей попытки
                else:
                    self.log_message.emit("❌ Все попытки обновления портфолио исчерпаны")
    
    def cleanup_failed_signals(self):
        """Удаление провалившихся сигналов из очереди"""
        try:
            self.mutex.lock()
            initial_count = len(self.signals_queue)
            
            # Фильтруем сигналы, оставляя только те, которые не провалились
            self.signals_queue = [signal for signal in self.signals_queue if signal.status != "FAILED"]
            
            removed_count = initial_count - len(self.signals_queue)
            if removed_count > 0:
                self.log_message.emit(f"🗑️ Удалено {removed_count} провалившихся сигналов из очереди")
                self.save_signals_queue()  # Сохраняем изменения в файл
        finally:
            self.mutex.unlock()

    def load_signals_queue(self):
        """Загрузка очереди сигналов из файла"""
        try:
            if self.signals_file.exists():
                with open(self.signals_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for signal_data in data:
                        signal = TradingSignal(
                            symbol=signal_data['symbol'],
                            signal=signal_data['signal'],
                            confidence=signal_data['confidence'],
                            price=signal_data.get('price', 0.0),
                            reason=signal_data['reason']
                        )
                        signal.status = signal_data.get('status', 'PENDING')
                        signal.execution_attempts = signal_data.get('execution_attempts', 0)
                        self.signals_queue.append(signal)
                    self.log_message.emit(f"📥 Загружено {len(self.signals_queue)} сигналов из файла")
        except Exception as e:
            self.log_message.emit(f"⚠️ Ошибка загрузки очереди сигналов: {e}")

    def save_signals_queue(self):
        """Сохранение очереди сигналов в файл"""
        try:
            data = []
            for signal in self.signals_queue:
                data.append({
                    'symbol': signal.symbol,
                    'signal_type': signal.signal,  # Исправляем на signal_type для консистентности
                    'signal': signal.signal,
                    'confidence': signal.confidence,
                    'price': signal.price,  # Добавляем цену для правильных расчетов
                    'reason': signal.reason,
                    'status': signal.status,
                    'execution_attempts': signal.execution_attempts
                })
            with open(self.signals_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log_message.emit(f"⚠️ Ошибка сохранения очереди сигналов: {e}")

    def clear_signals_queue(self):
        """Очистка всей очереди сигналов"""
        try:
            signals_count = len(self.signals_queue)
            self.signals_queue.clear()
            self.save_signals_queue()  # Сохраняем пустую очередь в файл
            self.log_message.emit(f"🗑️ Очищено {signals_count} сигналов из очереди")
        except Exception as e:
            self.log_message.emit(f"⚠️ Ошибка очистки очереди сигналов: {e}")

    def process_signal(self, signal: TradingSignal):
        """Обработка торгового сигнала с механизмом повторных попыток"""
        try:
            # Проверяем статус сигнала
            if signal.status == "EXECUTED":
                return  # Сигнал уже исполнен
            
            if signal.status == "FAILED":
                return  # Сигнал провален, не обрабатываем
            
            # Проверяем количество попыток
            if signal.execution_attempts >= signal.max_attempts:
                signal.status = "FAILED"
                self.log_message.emit(f"❌ Сигнал {signal.signal} для {signal.symbol} отклонен после {signal.max_attempts} попыток")
                return
            
            # Проверяем, включена ли торговля
            if not self.trading_enabled:
                self.log_message.emit(f"⏸️ Торговля отключена. Сигнал {signal.signal} для {signal.symbol} игнорируется.")
                return
            
            # Увеличиваем счетчик попыток
            signal.execution_attempts += 1
            signal.last_attempt_time = datetime.now()
            signal.status = "EXECUTING"
            
            self.log_message.emit(f"🔍 Обработка сигнала {signal.signal} для {signal.symbol} (попытка {signal.execution_attempts}/{signal.max_attempts}, уверенность: {signal.confidence:.2f})")
            
            success = False
            if signal.signal == 'BUY':
                success = self.execute_buy_order(signal)
            elif signal.signal == 'SELL':
                success = self.execute_sell_order(signal)
            
            # Обновляем статус на основе результата
            if success:
                signal.status = "EXECUTED"
                self.log_message.emit(f"✅ Сигнал {signal.signal} для {signal.symbol} успешно исполнен")
                self.save_signals_queue()  # Сохраняем изменения в файл
            else:
                signal.status = "PENDING"  # Возвращаем в ожидание для повторной попытки
                self.log_message.emit(f"⚠️ Сигнал {signal.signal} для {signal.symbol} не исполнен (попытка {signal.execution_attempts}/{signal.max_attempts})")
                self.save_signals_queue()  # Сохраняем изменения в файл
                
        except Exception as e:
            signal.status = "PENDING"  # Возвращаем в ожидание при ошибке
            self.log_message.emit(f"❌ Ошибка обработки сигнала {signal.symbol}: {e}")
            self.save_signals_queue()  # Сохраняем изменения в файл
    
    def format_quantity_for_api(self, qty: float, qty_step: float) -> str:
        """
        Форматирует количество для API без использования научной нотации
        
        Args:
            qty: Количество для форматирования
            qty_step: Шаг количества для определения точности
            
        Returns:
            str: Отформатированное количество как строка
        """
        if qty == 0:
            return "0"
        
        from decimal import Decimal, ROUND_DOWN, getcontext
        
        # Устанавливаем высокую точность для вычислений
        getcontext().prec = 28
        
        # Преобразуем в Decimal, используя округление для устранения проблем точности float
        # Сначала округляем до разумного количества знаков (15), чтобы избежать артефактов float
        qty_rounded = round(qty, 15)
        qty_step_rounded = round(qty_step, 15)
        
        decimal_qty = Decimal(str(qty_rounded))
        decimal_step = Decimal(str(qty_step_rounded))
        
        # Округляем количество до ближайшего кратного qty_step (вниз)
        rounded_qty = (decimal_qty // decimal_step) * decimal_step
        
        # Определяем количество десятичных знаков на основе qty_step
        if decimal_step >= 1:
            # Если шаг >= 1, используем целые числа
            return str(int(rounded_qty))
        else:
            # Определяем точность на основе qty_step
            step_str = f"{decimal_step:.15f}".rstrip('0').rstrip('.')
            
            if '.' in step_str:
                precision_decimals = len(step_str.split('.')[1])
            else:
                precision_decimals = 0
            
            # Ограничиваем максимальную точность разумным пределом
            precision_decimals = min(precision_decimals, 8)
            
            # Форматируем с нужной точностью
            formatted = f"{rounded_qty:.{precision_decimals}f}"
            
            # Убираем лишние нули справа
            if '.' in formatted:
                formatted = formatted.rstrip('0').rstrip('.')
                # Если убрали все знаки после точки, но precision_decimals > 0, 
                # оставляем хотя бы один знак
                if '.' not in formatted and precision_decimals > 0:
                    formatted += '.0'
            
            return formatted
    
    def execute_buy_order(self, signal: TradingSignal):
        """Выполнение ордера на покупку"""
        try:
            # Детальное логирование начального состояния
            self.log_message.emit(f"🔍 Начинаем покупку {signal.symbol}. Цена: ${signal.price:.6f}, Уверенность: {signal.confidence:.2f}")
            
            # Фильтрация проблемных символов через централизованный список
            if signal.symbol in self.banned_symbols:
                self.log_message.emit(f"⚠️ Символ {signal.symbol} в списке исключений, пропускаем торговлю")
                return False
            
            # Проверяем количество открытых позиций (игнорируем микроскопические остатки < $5)
            open_positions = self.get_significant_positions()
            
            self.log_message.emit(f"📊 Открытых позиций: {open_positions}/{self.max_open_positions}")
            
            if open_positions >= self.max_open_positions:
                self.log_message.emit(f"⚠️ Достигнуто максимальное количество открытых позиций ({self.max_open_positions}). Пропускаем покупку {signal.symbol}")
                return False
            
            # Проверяем 24-часовой кулдаун для данного символа
            current_time = time.time()
            if signal.symbol in self.last_buy_times:
                time_since_last_buy = current_time - self.last_buy_times[signal.symbol]
                hours_since_last_buy = time_since_last_buy / 3600
                self.log_message.emit(f"⏰ {signal.symbol}: Время с последней покупки: {hours_since_last_buy:.1f} часов (кулдаун: 24 часа)")
                
                if time_since_last_buy < self.buy_cooldown:
                    remaining_time = self.buy_cooldown - time_since_last_buy
                    remaining_hours = remaining_time / 3600
                    self.log_message.emit(f"⏳ 24-часовой кулдаун для {signal.symbol}: осталось {remaining_hours:.1f} часов")
                    return False
            else:
                self.log_message.emit(f"⏰ {signal.symbol}: Первая покупка для этого символа")
            
            # Проверяем баланс USDT
            usdt_balance = self.portfolio.get('USDT', 0)
            self.log_message.emit(f"💰 Баланс USDT: ${usdt_balance:.2f}")
            
            # Получаем актуальную информацию об инструменте через API
            instrument_info = self.get_instrument_info(signal.symbol)
            min_trade_amount = float(instrument_info['minOrderAmt'])
            min_order_qty = instrument_info['minOrderQty']
            qty_step = instrument_info['qtyStep']
            
            # Детальное логирование параметров инструмента
            self.log_message.emit(f"📋 {signal.symbol} - minOrderAmt: ${min_trade_amount:.2f}, minOrderQty: {min_order_qty}, qtyStep: {qty_step}")
            
            # ВАЖНО: Bybit API требует минимум $5 для API торговли (с января 2025)
            # Но для BTCUSDT minOrderAmt уже равен 5 USDT согласно API ответу
            api_min_order_value = 5.0  # $5 минимум для API торговли
            
            # Список проблемных символов, требующих больших буферов
            problematic_symbols = ['BBSOLUSDT', 'BABYDOGEUSDT']
            
            # Рассчитываем динамический буфер в зависимости от qtyStep и символа
            if signal.symbol in problematic_symbols:
                buffer_multiplier = 1.50  # 50% буфер для проблемных символов
                self.log_message.emit(f"🔍 {signal.symbol}: Применяется увеличенный буфер 50% для проблемного символа")
            elif qty_step < 1e-6:  # Очень маленький шаг количества
                buffer_multiplier = 1.25  # 25% буфер для монет с очень малым qtyStep
                self.log_message.emit(f"🔍 {signal.symbol}: qtyStep={qty_step} < 1e-6, применяется буфер 25%")
            elif qty_step < 1e-4:  # Маленький шаг количества
                buffer_multiplier = 1.15  # 15% буфер для монет с малым qtyStep
                self.log_message.emit(f"🔍 {signal.symbol}: qtyStep={qty_step} < 1e-4, применяется буфер 15%")
            else:
                buffer_multiplier = 1.05  # 5% буфер для обычных монет
                self.log_message.emit(f"🔍 {signal.symbol}: Стандартный буфер 5%")
            
            # Устанавливаем эффективную минимальную сумму на основе реальных данных API
            if signal.symbol == 'BTCUSDT':
                # Для BTCUSDT используем minOrderAmt из API (5 USDT) с буфером
                base_min_amount = max(min_trade_amount, api_min_order_value)
                effective_min_amount = base_min_amount * buffer_multiplier
                max_trade_amount = max(effective_min_amount * 20, 100.0)  # До $100 для BTCUSDT
                self.log_message.emit(f"💎 BTCUSDT: base_min=${base_min_amount:.2f}, effective_min=${effective_min_amount:.2f}, max=${max_trade_amount:.2f}")
            elif signal.symbol == 'BBSOLUSDT':
                # Специальная обработка для BBSOLUSDT - используем только API минимум
                self.log_message.emit(f"🔍 BBSOLUSDT: minOrderAmt={min_trade_amount}, API_min={api_min_order_value}")
                base_min_amount = max(min_trade_amount, api_min_order_value)  # Убираем принудительный минимум $10
                effective_min_amount = base_min_amount * buffer_multiplier  # Используем динамический буфер
                max_trade_amount = max(effective_min_amount * 4, 20.0)  # Максимум $20
                self.log_message.emit(f"🔍 BBSOLUSDT: base_min=${base_min_amount:.2f}, effective_min=${effective_min_amount:.2f}, max=${max_trade_amount:.2f}, buffer={buffer_multiplier:.2f}")
            elif signal.symbol in ['ETHUSDT', 'BNBUSDT', 'LINKUSDT']:
                # Для других дорогих активов используем более высокий минимум с буфером
                base_min_amount = max(min_trade_amount, api_min_order_value, 20.0)  # Уменьшено с $50 до $20
                effective_min_amount = base_min_amount * buffer_multiplier
                max_trade_amount = max(effective_min_amount * 4, 80.0)  # Уменьшено с $200 до $80
                self.log_message.emit(f"💎 {signal.symbol}: base_min=${base_min_amount:.2f}, effective_min=${effective_min_amount:.2f}, max=${max_trade_amount:.2f}")
            else:
                # Для всех остальных символов используем API минимум $5 с буфером
                base_min_amount = max(min_trade_amount, api_min_order_value)
                effective_min_amount = base_min_amount * buffer_multiplier
                max_trade_amount = max(effective_min_amount * 10, 20.0)  # Уменьшено с $50 до $20 для надежности
                self.log_message.emit(f"💰 {signal.symbol}: base_min=${base_min_amount:.2f}, effective_min=${effective_min_amount:.2f}, max=${max_trade_amount:.2f}")
            
            if usdt_balance < effective_min_amount:
                self.log_message.emit(f"⚠️ Недостаточно USDT для покупки {signal.symbol}: ${usdt_balance:.2f} (минимум ${effective_min_amount:.2f})")
                return False
            
            # Ограничиваем максимальную аллокацию на одну монету до 50% от баланса
            max_allocation_per_coin = usdt_balance * 0.5  # 50% от баланса
            
            # Проверяем текущую стоимость позиции по данной монете
            current_position_value = self.position_values_usdt.get(signal.symbol, 0)
            self.log_message.emit(f"📊 {signal.symbol}: Текущая позиция ${current_position_value:.2f}, макс. аллокация ${max_allocation_per_coin:.2f}")
            
            # Рассчитываем сумму для покупки (используем MAX_POSITION_PERCENT из конфига, но не менее минимума и не более максимума)
            base_trade_amount = usdt_balance * self.risk_per_trade
            trade_amount = max(min(base_trade_amount, max_trade_amount), effective_min_amount)
            
            # Проверяем, не превысит ли новая покупка лимит в 50% баланса на одну монету
            if current_position_value + trade_amount > max_allocation_per_coin:
                # Корректируем сумму покупки, чтобы не превысить лимит
                available_allocation = max_allocation_per_coin - current_position_value
                if available_allocation < effective_min_amount:
                    self.log_message.emit(f"⚠️ {signal.symbol}: Превышен лимит 50% баланса на монету. "
                                        f"Текущая позиция: ${current_position_value:.2f}, доступно: ${available_allocation:.2f}, "
                                        f"минимум для покупки: ${effective_min_amount:.2f}")
                    return False
                trade_amount = available_allocation
                self.log_message.emit(f"📉 {signal.symbol}: Сумма покупки скорректирована до ${trade_amount:.2f} "
                                    f"для соблюдения лимита 50% баланса")
            
            self.log_message.emit(f"💵 Расчет суммы торговли: базовая=${base_trade_amount:.2f} (баланс×{self.risk_per_trade:.3f})")
            
            # Дополнительная проверка: если trade_amount превышает половину баланса, ограничиваем его
            if trade_amount > max_allocation_per_coin:
                trade_amount = max_allocation_per_coin
                self.log_message.emit(f"⚠️ {signal.symbol}: Сумма торговли ограничена 50% баланса: ${trade_amount:.2f}")
            
            # Логируем расчеты для диагностики
            self.log_message.emit(f"🔍 {signal.symbol}: Расчет торговли - баланс=${usdt_balance:.2f}, риск={self.risk_per_trade:.3f}, "
                                f"базовая_сумма=${base_trade_amount:.2f}, макс_на_монету=${max_allocation_per_coin:.2f}, "
                                f"эффективный_мин=${effective_min_amount:.2f}, макс_торговля=${max_trade_amount:.2f}, "
                                f"итоговая_сумма=${trade_amount:.2f}")
            self.log_message.emit(f"💰 Расчет для {signal.symbol}: баланс=${usdt_balance:.2f}, риск={self.risk_per_trade*100:.1f}%, макс_аллокация=${max_allocation_per_coin:.2f}, итого=${trade_amount:.2f}")
            
            # Рассчитываем количество для покупки
            qty = trade_amount / signal.price
            
            # Получаем параметры из API
            min_order_qty = instrument_info['minOrderQty']
            max_order_qty = instrument_info['maxOrderQty']  # Эффективное максимальное количество (уже учитывает maxMarketOrderQty)
            qty_step = instrument_info['qtyStep']
            
            # Правильно округляем количество согласно qtyStep
            if qty_step > 0:
                import math
                from decimal import Decimal
                
                # Правильно определяем количество десятичных знаков в qty_step
                # включая научную нотацию (например, 1e-05)
                decimal_step = Decimal(str(qty_step))
                step_str = format(decimal_step, 'f')
                step_str = step_str.rstrip('0').rstrip('.')
                
                if '.' in step_str:
                    precision_decimals = len(step_str.split('.')[1])
                else:
                    precision_decimals = 0
                
                # Округляем с правильной точностью
                qty = math.floor(qty / qty_step) * qty_step
                qty = round(qty, precision_decimals)
            
            # Дополнительная проверка для токенов с очень низкой ценой
            # Ограничиваем количество разумным пределом для предотвращения чрезмерно больших ордеров
            # Специальная обработка для BABYDOGEUSDT - рассчитываем лимит исходя из минимальной суммы
            if signal.symbol == 'BABYDOGEUSDT':
                # Для BABYDOGEUSDT рассчитываем максимальное количество исходя из разумной суммы ($50)
                max_reasonable_amount = 50.0  # Максимум $50 для BABYDOGEUSDT
                reasonable_max_qty = max_reasonable_amount / signal.price
                self.log_message.emit(f"🔍 BABYDOGEUSDT: рассчитываем лимит исходя из ${max_reasonable_amount}: {reasonable_max_qty:.0f} токенов")
            else:
                reasonable_max_qty = 1e8  # 100 миллионов токенов - разумный предел для других мелких токенов
            
            if qty > reasonable_max_qty:
                self.log_message.emit(f"⚠️ Количество {qty:.0f} превышает разумный предел {reasonable_max_qty:.0f} для {signal.symbol}")
                qty = reasonable_max_qty
                self.log_message.emit(f"⚠️ Количество ограничено разумным пределом: {qty:.0f}")
                # Пересчитываем сумму после ограничения количества
                trade_usdt = qty * signal.price
                self.log_message.emit(f"💰 Итоговая сумма после ограничения: ${trade_usdt:.6f}")
            
            # Проверяем максимальное количество от API (после применения разумного предела)
            if max_order_qty > 0 and qty > max_order_qty:
                self.log_message.emit(f"⚠️ Количество превышает максимальное для {signal.symbol}: {qty:.8f} > {max_order_qty:.8f}")
                qty = max_order_qty
                self.log_message.emit(f"⚠️ Количество скорректировано до максимального: {qty:.8f}")
            
            # Проверяем, что количество не меньше минимального
            if qty < min_order_qty:
                # Увеличиваем количество до минимального, округленного по qtyStep
                if qty_step > 0:
                    import math
                    from decimal import Decimal
                    
                    # Правильно определяем количество десятичных знаков в qty_step
                    # включая научную нотацию (например, 1e-05)
                    decimal_step = Decimal(str(qty_step))
                    step_str = format(decimal_step, 'f')
                    step_str = step_str.rstrip('0').rstrip('.')
                    
                    if '.' in step_str:
                        precision_decimals = len(step_str.split('.')[1])
                    else:
                        precision_decimals = 0
                    
                    # Округляем с правильной точностью
                    qty = math.ceil(min_order_qty / qty_step) * qty_step
                    qty = round(qty, precision_decimals)
                else:
                    qty = min_order_qty
                self.log_message.emit(f"⚠️ Количество увеличено до минимального: {qty:.8f}")
                
                # Повторно проверяем максимальное количество после корректировки
                if max_order_qty > 0 and qty > max_order_qty:
                    self.log_message.emit(f"❌ Невозможно выполнить ордер для {signal.symbol}: минимальное количество {min_order_qty:.8f} превышает максимальное {max_order_qty:.8f}")
                    return False
            
            # Пересчитываем сумму сделки после корректировки количества
            trade_usdt = qty * signal.price
            
            # Проверяем эффективный минимум: max(minOrderQty * price, minOrderAmt)
            effective_min_check = max(min_order_qty * signal.price, effective_min_amount)
            
            # Если пересчитанная сумма меньше эффективного минимума, корректируем
            if trade_usdt < effective_min_check:
                # Увеличиваем количество для достижения минимальной стоимости
                qty_needed = effective_min_check / signal.price
                if qty_step > 0:
                    import math
                    import decimal
                    
                    # Определяем количество десятичных знаков в qty_step
                    qty_step_str = f"{qty_step:.10f}".rstrip('0').rstrip('.')
                    if '.' in qty_step_str:
                        precision_decimals = len(qty_step_str.split('.')[1])
                    else:
                        precision_decimals = 0
                    
                    # Округляем с правильной точностью
                    qty = math.ceil(qty_needed / qty_step) * qty_step
                    qty = round(qty, precision_decimals)
                else:
                    qty = qty_needed
                trade_usdt = qty * signal.price
                self.log_message.emit(f"⚠️ Количество скорректировано для эффективного минимума: {qty:.8f}")
                
                # Повторная проверка разумного предела после корректировки
                if qty > reasonable_max_qty:
                    self.log_message.emit(f"⚠️ После корректировки количество {qty:.0f} превышает разумный предел {reasonable_max_qty:.0f} для {signal.symbol}")
                    qty = reasonable_max_qty
                    trade_usdt = qty * signal.price
                    self.log_message.emit(f"⚠️ Количество ограничено разумным пределом: {qty:.0f}, итоговая сумма: ${trade_usdt:.2f}")
            
            # Финальная проверка баланса
            if trade_usdt > usdt_balance:
                # Корректируем количество под доступный баланс
                max_affordable_qty = usdt_balance / signal.price
                
                # Округляем вниз согласно qtyStep
                if qty_step > 0:
                    import math
                    import decimal
                    
                    # Определяем количество десятичных знаков в qty_step
                    qty_step_str = f"{qty_step:.10f}".rstrip('0').rstrip('.')
                    if '.' in qty_step_str:
                        precision_decimals = len(qty_step_str.split('.')[1])
                    else:
                        precision_decimals = 0
                    
                    # Округляем вниз с правильной точностью
                    max_affordable_qty = math.floor(max_affordable_qty / qty_step) * qty_step
                    max_affordable_qty = round(max_affordable_qty, precision_decimals)
                
                # Проверяем, что скорректированное количество не меньше минимального
                if max_affordable_qty < min_order_qty:
                    self.log_message.emit(f"⚠️ Недостаточно USDT: требуется ${trade_usdt:.2f}, доступно ${usdt_balance:.2f}. Даже минимальное количество {min_order_qty:.8f} требует ${min_order_qty * signal.price:.2f}")
                    return False
                
                # Обновляем количество и сумму
                qty = max_affordable_qty
                trade_usdt = qty * signal.price
                self.log_message.emit(f"⚠️ Количество скорректировано под доступный баланс: {qty:.8f} (${trade_usdt:.2f})")
                
                # Проверяем, что скорректированная сумма не меньше эффективного минимума
                if trade_usdt < effective_min_amount:
                    self.log_message.emit(f"⚠️ После корректировки под баланс сумма ${trade_usdt:.2f} меньше минимальной ${effective_min_amount:.2f}")
                    return False
            
            self.log_message.emit(f"💰 ПОКУПКА {signal.symbol}: ${trade_usdt:.2f} USDT ({qty:.6f} {signal.symbol.replace('USDT', '')})")
            self.log_message.emit(f"   Цена: ${signal.price:.6f}, Итоговая стоимость: ${trade_usdt:.2f}, Эффективный минимум: ${effective_min_amount:.2f}")
            self.log_message.emit(f"   Причина: {signal.reason}")
            
            # Выполняем реальный ордер
            formatted_qty = self.format_quantity_for_api(qty, qty_step)
            
            # Детальное логирование для диагностики (особенно для BBSOLUSDT)
            self.log_message.emit(f"🔢 Детали ордера {signal.symbol}:")
            self.log_message.emit(f"   minOrderQty: {min_order_qty}, maxOrderQty: {max_order_qty}")
            self.log_message.emit(f"   qtyStep: {qty_step}, minOrderAmt: {min_trade_amount}")
            self.log_message.emit(f"   Цена: ${signal.price:.8f}, Количество: {qty:.8f}")
            self.log_message.emit(f"   Форматированное количество: {formatted_qty}")
            self.log_message.emit(f"   Итоговая стоимость: ${trade_usdt:.2f}")
            
            order_result = self.bybit_client.place_order(
                category='spot',
                symbol=signal.symbol,
                side='Buy',
                order_type='Market',
                qty=formatted_qty
            )
            
            # Проверяем успешность ордера по retCode и наличию orderId
            if (order_result and 
                order_result.get('retCode') == 0 and 
                order_result.get('result', {}).get('orderId')):
                
                order_id = order_result.get('result', {}).get('orderId')
                self.log_message.emit(f"✅ Ордер на покупку {signal.symbol} успешно размещен (ID: {order_id})")
                
                # Обновляем время последней покупки для данного символа
                self.last_buy_times[signal.symbol] = current_time
                
                # Записываем время начала удержания позиции
                self.holding_start_times[signal.symbol] = current_time
                
                # Немедленно обновляем портфолио после успешной покупки
                self.update_portfolio()
                
                # Отправляем Telegram уведомление о покупке
                if self.telegram_notifier:
                    self.telegram_notifier.notify_trade_executed(
                        'BUY', signal.symbol, qty, signal.price, trade_usdt
                    )
                
                # Эмитируем событие выполненной сделки
                trade_info = {
                    'symbol': signal.symbol,
                    'side': 'BUY',
                    'amount': trade_usdt,
                    'qty': qty,
                    'price': signal.price,
                    'confidence': signal.confidence,
                    'reason': signal.reason,
                    'order_id': order_result.get('result', {}).get('orderId'),
                    'timestamp': datetime.now().isoformat()
                }
                self.trade_executed.emit(trade_info)
                return True
            else:
                error_msg = order_result.get('retMsg', 'Неизвестная ошибка') if order_result else 'Нет ответа от API'
                self.log_message.emit(f"❌ Ошибка размещения ордера на покупку {signal.symbol}: {error_msg}")
                # Telegram notification for buy order error
                if self.telegram_notifier:
                    self.telegram_notifier.notify_error(f"Ошибка покупки {signal.symbol}: {error_msg}")
                return False
            
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка выполнения покупки {signal.symbol}: {e}")
            # Telegram notification for buy order exception
            if self.telegram_notifier:
                self.telegram_notifier.notify_error(f"Ошибка выполнения покупки {signal.symbol}: {e}")
            return False
    
    def execute_sell_order(self, signal: TradingSignal):
        """Выполнение ордера на продажу"""
        try:
            base_asset = signal.symbol.replace('USDT', '')
            asset_balance = self.portfolio.get(base_asset, 0)
            
            # Детальное логирование начального состояния
            self.log_message.emit(f"🔍 Начинаем продажу {signal.symbol}. Баланс {base_asset}: {asset_balance:.8f}")
            
            if asset_balance <= 0:
                self.log_message.emit(f"⚠️ Недостаточно {base_asset} для продажи: {asset_balance}")
                return False
            
            # Получаем информацию об инструменте для правильного округления
            instrument_info = self.get_instrument_info(signal.symbol)
            min_order_qty = instrument_info['minOrderQty']
            qty_step = instrument_info['qtyStep']
            min_order_amt = instrument_info['minOrderAmt']
            
            # Детальное логирование параметров инструмента
            self.log_message.emit(f"📋 {signal.symbol} - minOrderQty: {min_order_qty}, qtyStep: {qty_step}, minOrderAmt: ${min_order_amt}")
            
            # Продаем 50% от имеющегося количества
            sell_amount = asset_balance * 0.5
            
            self.log_message.emit(f"💰 Планируем продать 50% от {asset_balance:.8f} = {sell_amount:.8f} {base_asset}")
            
            # Правильно округляем количество согласно qtyStep
            if qty_step > 0:
                import math
                from decimal import Decimal
                
                # Правильно определяем количество десятичных знаков в qty_step
                # включая научную нотацию (например, 1e-05)
                decimal_step = Decimal(str(qty_step))
                step_str = format(decimal_step, 'f')
                step_str = step_str.rstrip('0').rstrip('.')
                
                if '.' in step_str:
                    precision_decimals = len(step_str.split('.')[1])
                else:
                    precision_decimals = 0
                
                self.log_message.emit(f"🔢 Округление: qtyStep={qty_step}, precision_decimals={precision_decimals}")
                
                # Округляем с правильной точностью
                original_sell_amount = sell_amount
                sell_amount = math.floor(sell_amount / qty_step) * qty_step
                sell_amount = round(sell_amount, precision_decimals)
                
                self.log_message.emit(f"🔢 Округлено с {original_sell_amount:.8f} до {sell_amount:.8f}")
            
            # Проверяем, что количество не меньше минимального
            if sell_amount < min_order_qty:
                self.log_message.emit(f"⚠️ Количество для продажи 50% ({sell_amount:.8f}) меньше минимального {min_order_qty:.8f}")
                # Пробуем продать полный объем
                sell_amount = asset_balance
                
                self.log_message.emit(f"🔄 Пробуем продать полный объем: {sell_amount:.8f}")
                
                # Правильно округляем полный объем согласно qtyStep
                if qty_step > 0:
                    original_full_amount = sell_amount
                    sell_amount = math.floor(sell_amount / qty_step) * qty_step
                    sell_amount = round(sell_amount, precision_decimals)
                    
                    self.log_message.emit(f"🔢 Полный объем округлен с {original_full_amount:.8f} до {sell_amount:.8f}")
                
                if sell_amount >= min_order_qty:
                    self.log_message.emit(f"✅ Продаем полный объем: {sell_amount:.8f} {base_asset}")
                else:
                    self.log_message.emit(f"❌ Даже полный объем {sell_amount:.8f} меньше минимального {min_order_qty:.8f}")
                    return False
            
            # Проверяем минимальную стоимость ордера
            # Временно снижаем минимум для тестирования с $5.00 до $2.00
            temp_min_sell_amount = min(min_order_amt, 2.0)
            estimated_usdt = sell_amount * signal.price
            
            self.log_message.emit(f"💵 Расчетная стоимость продажи: {sell_amount:.8f} × ${signal.price:.6f} = ${estimated_usdt:.2f}")
            
            if estimated_usdt < temp_min_sell_amount:
                self.log_message.emit(f"⚠️ Стоимость продажи ${estimated_usdt:.2f} меньше минимальной ${temp_min_sell_amount:.2f}")
                return False
            
            self.log_message.emit(f"💸 ПРОДАЖА {signal.symbol}: {sell_amount:.8f} {base_asset} ≈ ${estimated_usdt:.2f}")
            self.log_message.emit(f"   Цена: ${signal.price:.6f}, Причина: {signal.reason}")
            
            # Выполняем реальный ордер
            formatted_qty = self.format_quantity_for_api(sell_amount, qty_step)
            self.log_message.emit(f"🔢 Отправляем количество в API: {formatted_qty} (исходное: {sell_amount})")
            
            order_result = self.bybit_client.place_order(
                category='spot',
                symbol=signal.symbol,
                side='Sell',
                order_type='Market',
                qty=formatted_qty
            )
            
            # Проверяем успешность ордера по retCode и наличию orderId
            if (order_result and 
                order_result.get('retCode') == 0 and 
                order_result.get('result', {}).get('orderId')):
                
                order_id = order_result.get('result', {}).get('orderId')
                self.log_message.emit(f"✅ Ордер на продажу {signal.symbol} успешно размещен (ID: {order_id})")
                
                # Очищаем время удержания позиции после успешной продажи
                if signal.symbol in self.holding_start_times:
                    del self.holding_start_times[signal.symbol]
                
                # Немедленно обновляем портфолио после успешной продажи
                self.update_portfolio()
                
                # Отправляем Telegram уведомление о продаже
                if self.telegram_notifier:
                    self.telegram_notifier.notify_trade_executed(
                        'SELL', signal.symbol, sell_amount, signal.price, estimated_usdt
                    )
                
                # Эмитируем событие выполненной сделки
                trade_info = {
                    'symbol': signal.symbol,
                    'side': 'SELL',
                    'amount': sell_amount,
                    'price': signal.price,
                    'confidence': signal.confidence,
                    'reason': signal.reason,
                    'estimated_usdt': estimated_usdt,
                    'order_id': order_result.get('result', {}).get('orderId'),
                    'timestamp': datetime.now().isoformat()
                }
                self.trade_executed.emit(trade_info)
                return True
            else:
                error_msg = order_result.get('retMsg', 'Неизвестная ошибка') if order_result else 'Нет ответа от API'
                self.log_message.emit(f"❌ Ошибка размещения ордера на продажу {signal.symbol}: {error_msg}")
                # Telegram notification for sell order error
                if self.telegram_notifier:
                    self.telegram_notifier.notify_error(f"Ошибка продажи {signal.symbol}: {error_msg}")
                return False
            
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка выполнения продажи {signal.symbol}: {e}")
            # Telegram notification for sell order exception
            if self.telegram_notifier:
                self.telegram_notifier.notify_error(f"Ошибка выполнения продажи {signal.symbol}: {e}")
            return False
    
    def stop(self):
        """Остановка торгового движка"""
        self.running = False
    
    def check_smart_exit_conditions(self):
        """Проверяет существующие позиции на предмет умного выхода"""
        try:
            if not hasattr(self, 'portfolio') or not self.portfolio:
                return
            
            # Загружаем ML стратегию для анализа
            try:
                from strategies.adaptive_ml import AdaptiveMLStrategy
                ml_strategy = AdaptiveMLStrategy()
                
                # Загружаем текущие данные рынка
                ticker_data = self.load_ticker_data()
                if not ticker_data:
                    return
                
                # Проверяем каждую позицию в портфолио
                for coin, amount in self.portfolio.items():
                    if coin == 'USDT' or amount <= 0:
                        continue
                    
                    symbol = f"{coin}USDT"
                    if symbol not in ticker_data:
                        continue
                    
                    current_price = float(ticker_data[symbol].get('price', 0))
                    if current_price <= 0:
                        continue
                    
                    # Анализируем позицию на предмет выгодного выхода
                    should_exit, confidence, reason = ml_strategy.analyze_position_profitability(
                        symbol, current_price, amount
                    )
                    
                    if should_exit and confidence > 0.7:  # Высокая уверенность в выходе
                        # Создаем сигнал на продажу
                        sell_signal = TradingSignal(
                            symbol=symbol,
                            signal='SELL',
                            confidence=confidence,
                            price=current_price,
                            reason=f"Умный выход: {reason}"
                        )
                        
                        self.log_message.emit(f"🧠 Умный выход из {symbol}: {reason} (уверенность: {confidence:.2f})")
                        
                        # Добавляем сигнал в очередь вместо прямого выполнения
                        self.add_signals([sell_signal])
                        
            except ImportError:
                # ML стратегия недоступна, используем простую логику
                self.log_message.emit("⚠️ ML стратегия недоступна для умного выхода")
            except Exception as e:
                self.log_message.emit(f"❌ Ошибка в умном выходе: {e}")
                
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка проверки умного выхода: {e}")
    
    def get_balance_for_telegram(self):
        """Получение баланса для Telegram уведомлений"""
        try:
            # Обновляем портфолио перед получением баланса
            self.update_portfolio()
            
            if hasattr(self, 'portfolio') and self.portfolio:
                balance_text = "💰 <b>Текущий баланс портфолио:</b>\n\n"
                
                # Получаем текущие цены для расчета стоимости
                ticker_data = self.load_ticker_data()
                total_value_usdt = 0
                has_assets = False
                
                for coin, amount in self.portfolio.items():
                    if amount > 0:
                        has_assets = True
                        if coin == 'USDT':
                            balance_text += f"• {coin}: {amount:.2f} USDT\n"
                            total_value_usdt += amount
                        else:
                            # Ищем цену монеты
                            symbol = f"{coin}USDT"
                            price = 0
                            if ticker_data and symbol in ticker_data:
                                price = float(ticker_data[symbol].get('price', 0))
                            
                            value_usdt = amount * price
                            total_value_usdt += value_usdt
                            
                            balance_text += f"• {coin}: {amount:.6f} (${value_usdt:.2f})\n"
                
                if has_assets:
                    balance_text += f"\n💵 <b>Общая стоимость: ${total_value_usdt:.2f} USDT</b>"
                    return balance_text
                else:
                    return "💰 <b>Портфолио пусто</b>\n\nНет активных позиций"
            else:
                return "❌ <b>Данные о балансе недоступны</b>\n\nПопробуйте позже"
        except Exception as e:
            error_msg = f"❌ <b>Ошибка получения баланса</b>\n\n{str(e)}"
            self.log_message.emit(f"❌ Ошибка получения баланса для Telegram: {e}")
            return error_msg
    
    def stop_trading_for_telegram(self):
        """Остановка торговли через Telegram"""
        try:
            if hasattr(self, 'trading_enabled'):
                self.trading_enabled = False
                self.log_message.emit("🛑 Торговля остановлена через Telegram")
                return "🛑 <b>Торговля остановлена</b>\n\nВсе новые сигналы будут игнорироваться"
            else:
                return "⚠️ <b>Торговля уже неактивна</b>\n\nСистема не торгует"
        except Exception as e:
            error_msg = f"❌ <b>Ошибка остановки торговли</b>\n\n{str(e)}"
            self.log_message.emit(f"❌ Ошибка остановки торговли через Telegram: {e}")
            return error_msg


class TraderMainWindow(QMainWindow):
    """Главное окно программы-торговца"""
    
    def __init__(self, enable_trading=True):  # Изменено с False на True для включения торговли по умолчанию
        super().__init__()
        self.setWindowTitle("🤖 Программа-торговец - Автоматическая торговля")
        self.setGeometry(100, 100, 1200, 800)
        
        # Инициализация переменных
        self.trading_active = False
        self.enable_trading_on_start = enable_trading  # Флаг для включения торговли при запуске
        self.current_data = {}
        self.trade_history = []
        self.bybit_client = None
        self.data_collector = None
        self.trading_engine = None
        self.telegram_notifier = None  # Инициализируем telegram_notifier
        
        # Настройка логирования
        self.setup_logging()
        
        # Настройка интерфейса (сначала создаем UI элементы)
        self.setup_ui()
        
        # Загружаем настройки Telegram перед инициализацией потоков
        self.load_telegram_settings_early()
        
        # Инициализация API клиента (после создания UI)
        self.init_api_client()
        
        # Инициализация потоков
        self.init_threads()
        
        # Подключение сигналов
        self.connect_signals()
        
        # Автоматический запуск торговли
        QTimer.singleShot(2000, self.auto_start_trading)  # Запуск через 2 секунды
        
    def setup_logging(self):
        """Настройка логирования"""
        self.logger = logging.getLogger(__name__)
    
    def init_api_client(self):
        """Инициализация API клиента"""
        try:
            credentials = get_api_credentials()
            self.bybit_client = BybitClient(
                api_key=credentials['api_key'],
                api_secret=credentials['api_secret'],
                testnet=credentials.get('testnet', True)
            )
            self.add_log("✅ API клиент инициализирован")
        except Exception as e:
            self.add_log(f"❌ Ошибка инициализации API: {e}")
            self.bybit_client = None
    
    def init_threads(self):
        """Инициализация потоков"""
        # Поток сбора данных
        self.data_collector = DataCollector()
        
        # Инициализируем Telegram уведомления если настройки загружены
        telegram_notifier = None
        if hasattr(self, 'telegram_settings') and self.telegram_settings:
            try:
                from telegram_notifier import TelegramNotifier
                telegram_notifier = TelegramNotifier(
                    self.telegram_settings['token'], 
                    self.telegram_settings['chat_id']
                )
                self.telegram_notifier = telegram_notifier
                self.add_log("✅ Telegram уведомления инициализированы")
            except Exception as e:
                self.add_log(f"❌ Ошибка инициализации Telegram: {e}")
                telegram_notifier = None
        
        # Торговый движок
        if self.bybit_client:
            self.trading_engine = TradingEngine(self.bybit_client, self.enable_trading_on_start, telegram_notifier)
        else:
            self.trading_engine = None
        
        # Таймер для периодического обновления таблицы активных сигналов
        self.signals_update_timer = QTimer()
        self.signals_update_timer.timeout.connect(self.update_active_signals_table)
        self.signals_update_timer.start(5000)  # Обновление каждые 5 секунд
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        
        # Верхняя панель управления
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # Создание системы вкладок
        self.tab_widget = QTabWidget()
        
        # Вкладка "Торговля"
        trading_tab = self.create_trading_tab()
        self.tab_widget.addTab(trading_tab, "📊 Торговля")
        
        # Вкладка "История сделок"
        history_tab = self.create_history_tab()
        self.tab_widget.addTab(history_tab, "📈 История сделок")
        
        # Вкладка "Telegram"
        telegram_tab = self.create_telegram_tab()
        self.tab_widget.addTab(telegram_tab, "📱 Telegram")
        
        main_layout.addWidget(self.tab_widget)
        
        # Статусная строка
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("🔴 Торговля остановлена")
    
    def create_trading_tab(self) -> QWidget:
        """Создание вкладки торговли"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Основная область с разделителем
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - статус и сигналы
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - логи
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([600, 600])
        layout.addWidget(splitter)
        
        return widget
    
    def create_history_tab(self) -> QWidget:
        """Создание вкладки истории сделок"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Заголовок
        title_label = QLabel("📈 История торговых операций")
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50; margin: 10px;")
        layout.addWidget(title_label)
        
        # Таблица истории сделок
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "Время", "Символ", "Операция", "Объем", "Цена", "Прибыль/Убыток", "Статус"
        ])
        
        # Настройка таблицы
        header = self.history_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.resizeSection(0, 150)  # Время
        header.resizeSection(1, 100)  # Символ
        header.resizeSection(2, 80)   # Операция
        header.resizeSection(3, 100)  # Объем
        header.resizeSection(4, 100)  # Цена
        header.resizeSection(5, 120)  # Прибыль/Убыток
        
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #bdc3c7;
                background-color: white;
                alternate-background-color: #f8f9fa;
                color: #2c3e50;
            }
            QTableWidget::item {
                padding: 8px;
                color: #2c3e50;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 8px;
                font-weight: bold;
            }
        """)
        
        layout.addWidget(self.history_table)
        
        # Панель статистики внизу
        stats_panel = QGroupBox("📊 Статистика торговли")
        stats_layout = QHBoxLayout(stats_panel)
        
        # Статистика сделок
        self.history_total_trades = QLabel("Всего сделок: 0")
        self.history_successful_trades = QLabel("Успешных: 0")
        self.history_total_profit = QLabel("Общая прибыль: $0.00")
        self.history_win_rate = QLabel("Процент успеха: 0%")
        
        for label in [self.history_total_trades, self.history_successful_trades, 
                     self.history_total_profit, self.history_win_rate]:
            label.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    font-weight: bold;
                    padding: 5px;
                    margin: 5px;
                    border: 1px solid #bdc3c7;
                    border-radius: 3px;
                    background-color: #ecf0f1;
                }
            """)
            stats_layout.addWidget(label)
        
        layout.addWidget(stats_panel)
        
        return widget
    
    def create_control_panel(self) -> QWidget:
        """Создание панели управления"""
        panel = QGroupBox("🎛️ Управление торговлей")
        layout = QHBoxLayout(panel)
        
        # Кнопка запуска торговли
        self.start_button = QPushButton("🚀 Запустить автоматическую торговлю")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.start_button.clicked.connect(self.start_trading)
        
        # Кнопка остановки торговли
        self.stop_button = QPushButton("⏹️ Остановить торговлю")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.stop_button.clicked.connect(self.stop_trading)
        self.stop_button.setEnabled(False)
        
        # Статус торговли
        self.trading_status_label = QLabel("🔴 Торговля остановлена")
        self.trading_status_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                border: 2px solid #e74c3c;
                border-radius: 5px;
                background-color: #fadbd8;
            }
        """)
        
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addStretch()
        layout.addWidget(self.trading_status_label)
        
        return panel
    
    def create_left_panel(self) -> QWidget:
        """Создание левой панели"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Панель статистики
        stats_panel = QGroupBox("📊 Статистика торговли")
        stats_layout = QGridLayout(stats_panel)
        
        self.total_trades_label = QLabel("0")
        self.successful_trades_label = QLabel("0")
        self.total_profit_label = QLabel("$0.00")
        
        stats_layout.addWidget(QLabel("Всего сделок:"), 0, 0)
        stats_layout.addWidget(self.total_trades_label, 0, 1)
        stats_layout.addWidget(QLabel("Успешных:"), 1, 0)
        stats_layout.addWidget(self.successful_trades_label, 1, 1)
        stats_layout.addWidget(QLabel("Общая прибыль:"), 2, 0)
        stats_layout.addWidget(self.total_profit_label, 2, 1)
        
        layout.addWidget(stats_panel)
        
        # Таблица активных сигналов
        signals_panel = QGroupBox("🎯 Активные сигналы")
        signals_layout = QVBoxLayout(signals_panel)
        
        # Кнопка очистки сигналов
        clear_signals_btn = QPushButton("🗑️ Очистить все сигналы")
        clear_signals_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
            QPushButton:pressed {
                background-color: #cc3333;
            }
        """)
        clear_signals_btn.clicked.connect(self.clear_all_signals)
        signals_layout.addWidget(clear_signals_btn)
        
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(5)
        self.signals_table.setHorizontalHeaderLabels([
            "Символ", "Сигнал", "Уверенность", "Цена", "Причина"
        ])
        self.signals_table.horizontalHeader().setStretchLastSection(True)
        
        signals_layout.addWidget(self.signals_table)
        layout.addWidget(signals_panel)
        
        return widget
    
    def create_right_panel(self) -> QWidget:
        """Создание правой панели"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Панель логов
        logs_panel = QGroupBox("📝 Подробные логи")
        logs_layout = QVBoxLayout(logs_panel)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
            }
        """)
        
        logs_layout.addWidget(self.log_text)
        layout.addWidget(logs_panel)
        
        return widget
    
    def connect_signals(self):
        """Подключение сигналов"""
        # Сигналы сбора данных
        self.data_collector.data_updated.connect(self.on_data_updated)
        self.data_collector.log_message.connect(self.add_log)
        
        # Сигналы торгового движка
        if self.trading_engine:
            self.trading_engine.trade_executed.connect(self.on_trade_executed)
            self.trading_engine.log_message.connect(self.add_log)
            self.trading_engine.status_changed.connect(self.on_trading_status_changed)
    
    def start_trading(self):
        """Запуск автоматической торговли"""
        if not self.bybit_client:
            self.add_log("❌ API клиент не инициализирован")
            return
        
        self.trading_active = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # Включаем торговлю в движке
        if self.trading_engine:
            self.trading_engine.trading_enabled = True
            self.add_log("✅ Торговля включена в движке")
            
            # Отправляем Telegram уведомление о запуске торговли
            if self.trading_engine.telegram_notifier:
                self.trading_engine.telegram_notifier.notify_trading_status(True)
        
        # Запускаем сбор данных
        if not self.data_collector.isRunning():
            self.data_collector.start()
        
        # Запускаем торговый движок
        if self.trading_engine and not self.trading_engine.isRunning():
            self.trading_engine.start()
        
        self.add_log("🚀 Автоматическая торговля запущена")
        self.update_trading_status("🟢 Торговля активна")
    
    def stop_trading(self):
        """Остановка автоматической торговли"""
        self.trading_active = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # Торговля остается включенной в движке для автоматической работы
        if self.trading_engine:
            # self.trading_engine.trading_enabled = False  # УБРАНО: не отключаем торговлю при остановке потока
            self.add_log("⏹️ Поток остановлен, торговля остается активной")
            
            # Отправляем Telegram уведомление об остановке торговли
            if self.trading_engine.telegram_notifier:
                self.trading_engine.telegram_notifier.notify_trading_status(False)
        
        # Останавливаем потоки
        if self.data_collector.isRunning():
            self.data_collector.stop()
            self.data_collector.wait(3000)
        
        if self.trading_engine and self.trading_engine.isRunning():
            self.trading_engine.stop()
            self.trading_engine.wait(3000)
        
        self.add_log("⏹️ Автоматическая торговля остановлена")
        self.update_trading_status("🔴 Торговля остановлена")
    
    def on_data_updated(self, data: Dict):
        """Обработка обновления данных"""
        self.current_data = data
        
        if self.trading_active and self.trading_engine:
            # Генерируем сигналы
            banned_symbols = getattr(self.trading_engine, 'banned_symbols', [])
            signal_generator = SignalGenerator(self.logger, banned_symbols)
            portfolio = getattr(self.trading_engine, 'portfolio', {})
            signals = signal_generator.generate_signals(data, portfolio)
            
            # Обновляем таблицу сигналов новыми сгенерированными сигналами
            self.update_signals_table(signals)
            
            # Отправляем сигналы в торговый движок
            if signals:
                self.trading_engine.add_signals(signals)
        
        # Всегда обновляем таблицу активных сигналов из очереди
        self.update_active_signals_table()
    
    def update_signals_table(self, signals: List[TradingSignal]):
        """Обновление таблицы сигналов"""
        self.signals_table.setRowCount(len(signals))
        
        for i, signal in enumerate(signals):
            self.signals_table.setItem(i, 0, QTableWidgetItem(signal.symbol))
            self.signals_table.setItem(i, 1, QTableWidgetItem(signal.signal))
            self.signals_table.setItem(i, 2, QTableWidgetItem(f"{signal.confidence:.2f}"))
            self.signals_table.setItem(i, 3, QTableWidgetItem(f"${signal.price:.6f}"))
            self.signals_table.setItem(i, 4, QTableWidgetItem(signal.reason))
    
    def update_active_signals_table(self):
        """Обновление таблицы активных сигналов из очереди торгового движка"""
        if not self.trading_engine:
            return
            
        # Получаем активные сигналы из очереди торгового движка
        active_signals = getattr(self.trading_engine, 'signals_queue', [])
        
        # Фильтруем только активные сигналы (не выполненные и не провалившиеся)
        pending_signals = [signal for signal in active_signals 
                          if signal.status not in ["EXECUTED", "FAILED"]]
        
        self.signals_table.setRowCount(len(pending_signals))
        
        for i, signal in enumerate(pending_signals):
            # Добавляем информацию о статусе и попытках
            status_info = f"{signal.status}"
            if hasattr(signal, 'execution_attempts') and signal.execution_attempts > 0:
                status_info += f" ({signal.execution_attempts} попыток)"
            
            self.signals_table.setItem(i, 0, QTableWidgetItem(signal.symbol))
            self.signals_table.setItem(i, 1, QTableWidgetItem(signal.signal))
            self.signals_table.setItem(i, 2, QTableWidgetItem(f"{signal.confidence:.2f}"))
            self.signals_table.setItem(i, 3, QTableWidgetItem(f"${signal.price:.6f}"))
            self.signals_table.setItem(i, 4, QTableWidgetItem(f"{signal.reason} | {status_info}"))
    
    def on_trade_executed(self, trade_info: Dict):
        """Обработка выполненной сделки"""
        self.trade_history.append(trade_info)
        self.update_statistics()
        self.add_trade_to_history_table(trade_info)
        
        # Логируем сделку
        symbol = trade_info['symbol']
        side = trade_info['side']
        amount = trade_info.get('amount', 0)
        price = trade_info['price']
        
        if side == 'BUY':
            self.add_log(f"✅ Выполнена покупка {symbol}: ${amount:.2f} по цене ${price:.6f}")
        else:
            estimated_usdt = trade_info.get('estimated_usdt', 0)
            self.add_log(f"✅ Выполнена продажа {symbol}: {amount:.6f} ≈ ${estimated_usdt:.2f}")
    
    def update_statistics(self):
        """Обновление статистики"""
        total_trades = len(self.trade_history)
        self.total_trades_label.setText(str(total_trades))
        
        # Подсчет успешных сделок (сделки с order_id считаются успешными)
        successful_trades = sum(1 for trade in self.trade_history if trade.get('order_id'))
        self.successful_trades_label.setText(str(successful_trades))
        
        # Расчет прибыли на основе покупок и продаж
        total_profit = self.calculate_total_profit()
        self.total_profit_label.setText(f"${total_profit:.2f}")
    
    def calculate_total_profit(self):
        """Расчет общей прибыли на основе истории сделок"""
        profit = 0.0
        symbol_positions = {}  # Отслеживаем позиции по символам
        
        for trade in self.trade_history:
            if not trade.get('order_id'):  # Пропускаем неуспешные сделки
                continue
                
            symbol = trade['symbol']
            side = trade['side']
            
            if symbol not in symbol_positions:
                symbol_positions[symbol] = {'qty': 0, 'total_cost': 0, 'total_sold': 0}
            
            if side == 'BUY':
                # При покупке увеличиваем количество и общую стоимость
                qty = trade['qty']
                cost = trade['amount']  # amount в USDT для покупки
                symbol_positions[symbol]['qty'] += qty
                symbol_positions[symbol]['total_cost'] += cost
                
            elif side == 'SELL':
                # При продаже рассчитываем прибыль
                qty_sold = trade['amount']  # amount в базовой валюте для продажи
                usdt_received = trade.get('estimated_usdt', 0)
                
                if symbol_positions[symbol]['qty'] > 0:
                    # Рассчитываем среднюю цену покупки
                    avg_buy_price = symbol_positions[symbol]['total_cost'] / symbol_positions[symbol]['qty']
                    cost_of_sold = qty_sold * avg_buy_price
                    
                    # Прибыль = полученные USDT - стоимость проданных монет
                    trade_profit = usdt_received - cost_of_sold
                    profit += trade_profit
                    
                    # Обновляем позицию
                    symbol_positions[symbol]['qty'] -= qty_sold
                    symbol_positions[symbol]['total_cost'] -= cost_of_sold
                    symbol_positions[symbol]['total_sold'] += usdt_received
        
        return profit
    
    def on_trading_status_changed(self, status: str):
        """Обработка изменения статуса торговли"""
        self.update_trading_status(status)
    
    def update_trading_status(self, status: str):
        """Обновление статуса торговли"""
        self.trading_status_label.setText(status)
        self.status_bar.showMessage(status)
        
        # Изменяем стиль в зависимости от статуса
        if "активна" in status:
            self.trading_status_label.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    padding: 10px;
                    border: 2px solid #27ae60;
                    border-radius: 5px;
                    background-color: #d5f4e6;
                    color: #27ae60;
                }
            """)
        else:
            self.trading_status_label.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    padding: 10px;
                    border: 2px solid #e74c3c;
                    border-radius: 5px;
                    background-color: #fadbd8;
                    color: #e74c3c;
                }
            """)
    
    def add_log(self, message: str):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_text.append(formatted_message)
        self.logger.info(message)
        
        # Автопрокрутка к концу
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
    
    def add_trade_to_history_table(self, trade_info: Dict):
        """Добавление сделки в таблицу истории"""
        try:
            # Получаем текущее количество строк
            row_count = self.history_table.rowCount()
            
            # Ограничиваем количество записей (например, 100)
            if row_count >= 100:
                self.history_table.removeRow(0)  # Удаляем самую старую запись
                row_count = self.history_table.rowCount()
            
            # Добавляем новую строку
            self.history_table.insertRow(row_count)
            
            # Заполняем данные
            timestamp = trade_info.get('timestamp', datetime.now().strftime("%H:%M:%S"))
            symbol = trade_info.get('symbol', 'N/A')
            side = trade_info.get('side', 'N/A')
            amount = trade_info.get('amount', 0)
            price = trade_info.get('price', 0)
            
            # Рассчитываем прибыль/убыток
            pnl = 0.0
            if side == 'SELL':
                estimated_usdt = trade_info.get('estimated_usdt', 0)
                # Для продажи показываем полученную сумму в USDT
                pnl = estimated_usdt
            elif side == 'BUY':
                # Для покупки показываем потраченную сумму со знаком минус
                pnl = -amount
            
            # Создаем элементы таблицы
            time_item = QTableWidgetItem(str(timestamp))
            symbol_item = QTableWidgetItem(symbol)
            side_item = QTableWidgetItem(side)
            amount_item = QTableWidgetItem(f"{amount:.6f}")
            price_item = QTableWidgetItem(f"${price:.6f}")
            pnl_item = QTableWidgetItem(f"${pnl:.2f}")
            
            # Цветовое кодирование для стороны сделки
            if side == 'BUY':
                side_item.setBackground(QColor(46, 204, 113, 50))  # Зеленый для покупки
                side_item.setForeground(QColor(39, 174, 96))
            elif side == 'SELL':
                side_item.setBackground(QColor(231, 76, 60, 50))   # Красный для продажи
                side_item.setForeground(QColor(192, 57, 43))
            
            # Цветовое кодирование для P&L
            if pnl > 0:
                pnl_item.setForeground(QColor(39, 174, 96))  # Зеленый для прибыли
            elif pnl < 0:
                pnl_item.setForeground(QColor(192, 57, 43))  # Красный для убытка
            
            # Устанавливаем элементы в таблицу
            self.history_table.setItem(row_count, 0, time_item)
            self.history_table.setItem(row_count, 1, symbol_item)
            self.history_table.setItem(row_count, 2, side_item)
            self.history_table.setItem(row_count, 3, amount_item)
            self.history_table.setItem(row_count, 4, price_item)
            self.history_table.setItem(row_count, 5, pnl_item)
            
            # Прокручиваем к последней записи
            self.history_table.scrollToBottom()
            
        except Exception as e:
            self.add_log(f"❌ Ошибка добавления сделки в таблицу: {e}")
    
    def create_telegram_tab(self) -> QWidget:
        """Создание вкладки Telegram уведомлений"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Заголовок
        title = QLabel("📱 Настройки Telegram уведомлений")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin: 10px;")
        layout.addWidget(title)
        
        # Группа настроек
        settings_group = QGroupBox("🔧 Конфигурация бота")
        settings_layout = QVBoxLayout(settings_group)
        
        # Bot Token
        token_layout = QHBoxLayout()
        token_layout.addWidget(QLabel("Bot Token:"))
        self.telegram_token_input = QLineEdit()
        self.telegram_token_input.setPlaceholderText("Введите токен Telegram бота")
        self.telegram_token_input.setEchoMode(QLineEdit.Password)
        token_layout.addWidget(self.telegram_token_input)
        settings_layout.addLayout(token_layout)
        
        # Chat ID
        chat_layout = QHBoxLayout()
        chat_layout.addWidget(QLabel("Chat ID:"))
        self.telegram_chat_input = QLineEdit()
        self.telegram_chat_input.setPlaceholderText("Введите Chat ID")
        chat_layout.addWidget(self.telegram_chat_input)
        settings_layout.addLayout(chat_layout)
        
        # Включение уведомлений
        self.telegram_enabled_checkbox = QCheckBox("Включить Telegram уведомления")
        settings_layout.addWidget(self.telegram_enabled_checkbox)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        test_button = QPushButton("🧪 Тест уведомления")
        test_button.clicked.connect(self.test_telegram_notification)
        buttons_layout.addWidget(test_button)
        
        save_button = QPushButton("💾 Сохранить настройки")
        save_button.clicked.connect(self.save_telegram_settings)
        buttons_layout.addWidget(save_button)
        
        settings_layout.addLayout(buttons_layout)
        layout.addWidget(settings_group)
        
        # Группа статистики
        stats_group = QGroupBox("📊 Статистика уведомлений")
        stats_layout = QVBoxLayout(stats_group)
        
        self.telegram_stats_label = QLabel("Отправлено уведомлений: 0\nОшибок: 0")
        stats_layout.addWidget(self.telegram_stats_label)
        
        layout.addWidget(stats_group)
        
        # Растягиваем пространство
        layout.addStretch()
        
        # Загружаем сохраненные настройки
        self.load_telegram_settings()
        
        return widget
    
    def test_telegram_notification(self):
        """Тестирование Telegram уведомления"""
        self.add_log("🔍 DEBUG: Кнопка тестирования нажата!")
        try:
            self.add_log(f"🔍 DEBUG: telegram_notifier = {self.telegram_notifier}")
            if not self.telegram_notifier:
                self.add_log("❌ Telegram уведомления не настроены")
                return
            
            self.add_log("🔍 DEBUG: Вызываем send_test_message()")
            self.telegram_notifier.send_test_message()
            self.add_log("✅ Тестовое уведомление отправлено")
        except Exception as e:
            self.add_log(f"❌ Ошибка отправки тестового уведомления: {e}")
            import traceback
            self.add_log(f"🔍 DEBUG: Полная ошибка: {traceback.format_exc()}")
    
    def save_telegram_settings(self):
        """Сохранение настроек Telegram"""
        try:
            settings = {
                'token': self.telegram_token_input.text(),
                'chat_id': self.telegram_chat_input.text(),
                'enabled': self.telegram_enabled_checkbox.isChecked()
            }
            
            # Сохраняем в файл
            import json
            with open('telegram_settings.json', 'w') as f:
                json.dump(settings, f)
            
            # Инициализируем уведомления если включены
            if settings['enabled'] and settings['token'] and settings['chat_id']:
                self.init_telegram_notifier(settings['token'], settings['chat_id'])
            
            self.add_log("✅ Настройки Telegram сохранены")
        except Exception as e:
            self.add_log(f"❌ Ошибка сохранения настроек Telegram: {e}")
    
    def load_telegram_settings_early(self):
        """Ранняя загрузка настроек Telegram перед созданием торгового движка"""
        try:
            import json
            with open('telegram_settings.json', 'r') as f:
                settings = json.load(f)
            
            # Сохраняем настройки для последующей инициализации
            if settings.get('enabled') and settings.get('token') and settings.get('chat_id'):
                self.telegram_settings = settings
                self.add_log("✅ Настройки Telegram загружены")
            else:
                self.telegram_settings = None
                
        except FileNotFoundError:
            # Файл настроек не найден - это нормально при первом запуске
            self.telegram_settings = None
        except Exception as e:
            self.add_log(f"❌ Ошибка ранней загрузки настроек Telegram: {e}")
            self.telegram_settings = None
    
    def load_telegram_settings(self):
        """Загрузка настроек Telegram"""
        try:
            import json
            with open('telegram_settings.json', 'r') as f:
                settings = json.load(f)
            
            self.telegram_token_input.setText(settings.get('token', ''))
            self.telegram_chat_input.setText(settings.get('chat_id', ''))
            self.telegram_enabled_checkbox.setChecked(settings.get('enabled', False))
            
            # Инициализируем уведомления если включены
            if settings.get('enabled') and settings.get('token') and settings.get('chat_id'):
                self.init_telegram_notifier(settings['token'], settings['chat_id'])
                
        except FileNotFoundError:
            # Файл настроек не найден - это нормально при первом запуске
            pass
        except Exception as e:
            self.add_log(f"❌ Ошибка загрузки настроек Telegram: {e}")
    
    def init_telegram_notifier(self, token: str, chat_id: str):
        """Инициализация Telegram уведомлений"""
        try:
            from telegram_notifier import TelegramNotifier
            self.telegram_notifier = TelegramNotifier(token, chat_id)
            
            # Обновляем ссылку на telegram_notifier в торговом движке
            if self.trading_engine:
                self.trading_engine.telegram_notifier = self.telegram_notifier
                # Настройка callback функций
                if hasattr(self.telegram_notifier, 'set_callback'):
                    self.telegram_notifier.set_callback('get_balance', self.trading_engine.get_balance_for_telegram)
                    self.telegram_notifier.set_callback('stop_trading', self.trading_engine.stop_trading_for_telegram)
            
            # Запускаем polling для обработки callback'ов
            if hasattr(self.telegram_notifier, 'start_polling'):
                self.telegram_notifier.start_polling()
                self.add_log("✅ Telegram уведомления обновлены и polling запущен")
            else:
                self.add_log("✅ Telegram уведомления обновлены")
        except Exception as e:
            self.add_log(f"❌ Ошибка инициализации Telegram уведомлений: {e}")
            self.telegram_notifier = None
    
    def auto_start_trading(self):
        """Автоматический запуск торговли при старте программы"""
        try:
            if self.enable_trading_on_start:
                self.add_log("🚀 Автоматический запуск торговли...")
                self.start_trading()
            else:
                self.add_log("ℹ️ Торговля не включена при запуске. Используйте кнопку 'Начать торговлю' или флаг --enable-trading")
        except Exception as e:
            self.add_log(f"❌ Ошибка автоматического запуска: {e}")
    
    def clear_all_signals(self):
        """Очистка всех активных сигналов"""
        try:
            if self.trading_engine:
                self.trading_engine.clear_signals_queue()
                self.update_active_signals_table()  # Обновляем таблицу после очистки
                self.add_log("🗑️ Все активные сигналы очищены")
            else:
                self.add_log("⚠️ Торговый движок не инициализирован")
        except Exception as e:
            self.add_log(f"❌ Ошибка очистки сигналов: {e}")
    
    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        if self.trading_active:
            self.stop_trading()
        
        event.accept()


def main():
    """Главная функция"""
    import argparse
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Программа-торговец')
    parser.add_argument('--enable-trading', action='store_true', 
                       help='Включить торговлю при запуске')
    args = parser.parse_args()
    
    if not GUI_AVAILABLE:
        print("❌ GUI компоненты недоступны")
        return
    
    app = QApplication(sys.argv)
    app.setApplicationName("Программа-торговец")
    app.setApplicationVersion("1.0")
    
    # Создаем и показываем главное окно
    window = TraderMainWindow(enable_trading=args.enable_trading)
    window.show()
    
    # Запускаем приложение
    sys.exit(app.exec())


if __name__ == "__main__":
    main()