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
        QTableWidgetItem, QHeaderView, QSpacerItem, QSizePolicy
    )
    from PySide6.QtCore import QTimer, QThread, Signal, Qt, QMutex
    from PySide6.QtGui import QFont, QColor, QPalette
    GUI_AVAILABLE = True
except ImportError as e:
    print(f"❌ Ошибка импорта GUI: {e}")
    GUI_AVAILABLE = False
    sys.exit(1)

# Импорт API клиента
try:
    from api.bybit_client import BybitClient
    from config import get_api_credentials
except ImportError as e:
    print(f"❌ Ошибка импорта API: {e}")
    sys.exit(1)


class TradingSignal:
    """Класс для представления торгового сигнала"""
    def __init__(self, symbol: str, signal: str, confidence: float, price: float, reason: str = ""):
        self.symbol = symbol
        self.signal = signal  # 'BUY' или 'SELL'
        self.confidence = confidence
        self.price = price
        self.reason = reason
        self.timestamp = datetime.now()


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
    
    def __init__(self, logger):
        self.logger = logger
        self.min_confidence = 0.3  # Минимальная уверенность для сигнала (снижено для тестирования)
        
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
            
            return signals[:30]  # Возвращаем топ-30 сигналов для полноценного использования нейросети
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации сигналов: {e}")
            return []
    
    def get_usdt_pairs(self, ticker_data) -> List[str]:
        """Получение списка USDT торговых пар с активным движением цены"""
        pairs = []
        
        # Если ticker_data - это список словарей (как из TickerDataLoader)
        if isinstance(ticker_data, list):
            for ticker in ticker_data:
                if isinstance(ticker, dict) and 'symbol' in ticker:
                    symbol = ticker['symbol']
                    if symbol.endswith('USDT') and symbol != 'USDT':
                        pairs.append(symbol)
        # Если ticker_data - это словарь
        elif isinstance(ticker_data, dict):
            # Получаем все USDT пары из тикеров
            tickers = ticker_data.get('tickers', ticker_data)
            for symbol, ticker_info in tickers.items():
                if symbol.endswith('USDT') and symbol != 'USDT':
                    # Добавляем все USDT символы для полноценного анализа нейросети
                    pairs.append(symbol)
        
        # Если нет данных тикеров, используем стандартный список (только проверенные символы)
        if not pairs:
            pairs = [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT',
                'XRPUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'LINKUSDT',
                'MATICUSDT', 'LTCUSDT', 'UNIUSDT', 'ATOMUSDT', 'FILUSDT'
            ]
        
        # Фильтруем недоступные символы для testnet
        invalid_symbols = {'SHIB1000USDT', 'BANDUSDT', 'WIFUSDT', 'HBARUSDT'}
        pairs = [pair for pair in pairs if pair not in invalid_symbols]
        
        self.logger.info(f"🎯 Найдено {len(pairs)} активных USDT пар для анализа")
        return pairs
    
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
            price_change_24h = float(symbol_ticker.get('price24hPcnt', 0))
            
            # Получаем данные ML для символа
            ml_performance = ml_data.get('performance', {}).get(symbol, {})
            ml_training = ml_data.get('training_state', {}).get(symbol, {})
            
            # Базовая логика генерации сигналов
            signal_type = None
            confidence = 0.0
            reason = ""
            
            # Логируем данные для отладки каждого символа
            ml_accuracy = ml_performance.get('accuracy', 0) if isinstance(ml_performance, dict) else 0
            self.logger.debug(f"🔍 Анализ {symbol}: цена=${current_price:.6f}, изменение 24ч={price_change_24h:.2%}, ML точность={ml_accuracy:.2f}")
            
            # Проверяем ML данные
            if ml_accuracy > 0.5:  # Снижаем порог с 0.7 до 0.5
                self.logger.debug(f"🤖 ML модель активна для {symbol}, точность: {ml_accuracy:.2f}")
                # Используем ML логику с более мягкими условиями
                if price_change_24h > 0.002:  # Рост более 0.2% (было 0.5%)
                    signal_type = 'BUY'
                    confidence = min(0.8, ml_accuracy * 0.9)
                    reason = f"ML модель (точность: {ml_accuracy:.2f}), рост 24ч: {price_change_24h:.2%}"
                    self.logger.debug(f"🟢 ML BUY сигнал для {symbol}: изменение {price_change_24h:.4f} > 0.002")
                elif price_change_24h < -0.002:  # Падение более 0.2% (было 0.5%)
                    # Проверяем, есть ли актив в портфолио для продажи
                    base_asset = symbol.replace('USDT', '')
                    if base_asset in portfolio and float(portfolio[base_asset]) > 0:
                        signal_type = 'SELL'
                        confidence = min(0.8, ml_accuracy * 0.9)
                        reason = f"ML модель (точность: {ml_accuracy:.2f}), падение 24ч: {price_change_24h:.2%}"
                        self.logger.debug(f"🔴 ML SELL сигнал для {symbol}: изменение {price_change_24h:.4f} < -0.002")
                    else:
                        self.logger.debug(f"⚠️ ML SELL условие выполнено для {symbol}, но актив {base_asset} не найден в портфолио")
                else:
                    self.logger.debug(f"⚪ ML условия не выполнены для {symbol}: изменение {price_change_24h:.4f} в диапазоне [-0.002, 0.002]")
            else:
                self.logger.debug(f"📊 Техническая логика для {symbol}, ML точность: {ml_accuracy:.2f} < 0.5")
                # Используем простую техническую логику с более мягкими условиями
                if price_change_24h > 0.001:  # Сильный рост 0.1% (было 0.5%)
                    signal_type = 'BUY'
                    confidence = min(0.7, abs(price_change_24h) * 50)  # Увеличиваем множитель для компенсации
                    reason = f"Технический анализ, рост: {price_change_24h:.2%}"
                    self.logger.debug(f"🟢 Технический BUY сигнал для {symbol}: изменение {price_change_24h:.4f} > 0.001")
                elif price_change_24h < -0.001:  # Сильное падение 0.1% (было 0.5%)
                    base_asset = symbol.replace('USDT', '')
                    if base_asset in portfolio and float(portfolio[base_asset]) > 0:
                        signal_type = 'SELL'
                        confidence = min(0.7, abs(price_change_24h) * 50)  # Увеличиваем множитель для компенсации
                        reason = f"Технический анализ, падение: {price_change_24h:.2%}"
                        self.logger.debug(f"🔴 Технический SELL сигнал для {symbol}: изменение {price_change_24h:.4f} < -0.001")
                    else:
                        self.logger.debug(f"⚠️ Технический SELL условие выполнено для {symbol}, но актив {base_asset} не найден в портфолио")
                else:
                    self.logger.debug(f"⚪ Технические условия не выполнены для {symbol}: изменение {price_change_24h:.4f} в диапазоне [-0.001, 0.001]")
            
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
    
    def __init__(self, bybit_client, trading_enabled=False):
        super().__init__()
        self.bybit_client = bybit_client
        self.running = False
        self.trading_enabled = trading_enabled  # Флаг включения торговли
        self.signals_queue = []
        self.portfolio = {}
        self.logger = logging.getLogger(__name__)
        self.signal_generator = SignalGenerator(self.logger)
        self.mutex = QMutex()
        self.last_buy_times = {}  # Словарь для отслеживания времени последних покупок
        self.buy_cooldown = 300  # Кулдаун между покупками одного актива (5 минут)
        
    def run(self):
        """Основной торговый цикл"""
        self.running = True
        self.status_changed.emit("🟢 Торговля активна")
        self.log_message.emit("🚀 Запуск автоматической торговли...")
        
        # Инициализируем генератор сигналов
        signal_generator = SignalGenerator(self.logger)
        
        while self.running:
            try:
                # Обновляем портфолио
                self.update_portfolio()
                
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
                
                # Обрабатываем сигналы из очереди
                if self.signals_queue:
                    signal = self.signals_queue.pop(0)
                    self.process_signal(signal)
                
                time.sleep(10)  # Увеличиваем паузу для более стабильной работы
                
            except Exception as e:
                self.log_message.emit(f"❌ Ошибка в торговом цикле: {e}")
                time.sleep(5)
        
        self.status_changed.emit("🔴 Торговля остановлена")
    
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
                    
                    # Извлекаем минимальные значения
                    min_order_qty = float(lot_size_filter.get('minOrderQty', 0))
                    min_order_amt = float(lot_size_filter.get('minOrderAmt', 5))  # По умолчанию 5 USDT
                    
                    self.log_message.emit(f"📊 {symbol}: minOrderQty={min_order_qty}, minOrderAmt={min_order_amt}")
                    
                    return {
                        'symbol': symbol,
                        'minOrderQty': min_order_qty,
                        'minOrderAmt': min_order_amt,
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
                            
                            # Извлекаем минимальные значения
                            min_order_qty = float(lot_size_filter.get('minOrderQty', 0))
                            min_order_amt = float(lot_size_filter.get('minOrderAmt', 5))  # По умолчанию 5 USDT
                            
                            self.log_message.emit(f"📊 {symbol}: minOrderQty={min_order_qty}, minOrderAmt={min_order_amt}")
                            
                            return {
                                'symbol': symbol,
                                'minOrderQty': min_order_qty,
                                'minOrderAmt': min_order_amt,
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
            'basePrecision': '0.00001',
            'quotePrecision': '0.0000001'
        }
    
    def add_signals(self, signals: List[TradingSignal]):
        """Добавление сигналов в очередь с проверкой кулдауна"""
        self.mutex.lock()
        try:
            filtered_signals = []
            current_time = time.time()
            
            for signal in signals:
                # Проверяем кулдаун только для сигналов на покупку
                if signal.signal == 'BUY' and signal.symbol in self.last_buy_times:
                    time_since_last_buy = current_time - self.last_buy_times[signal.symbol]
                    if time_since_last_buy < self.buy_cooldown:
                        remaining_time = self.buy_cooldown - time_since_last_buy
                        self.log_message.emit(f"⏳ Кулдаун для {signal.symbol}: осталось {remaining_time:.0f} сек (сигнал отклонен)")
                        continue
                
                filtered_signals.append(signal)
            
            self.signals_queue.extend(filtered_signals)
            if filtered_signals:
                self.log_message.emit(f"📊 Добавлено {len(filtered_signals)} сигналов в очередь")
            if len(filtered_signals) < len(signals):
                rejected_count = len(signals) - len(filtered_signals)
                self.log_message.emit(f"🚫 Отклонено {rejected_count} сигналов из-за кулдауна")
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
                
                # Обрабатываем данные о монетах
                coins_data = balance_data.get('coins', {})
                
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
                    self.portfolio = temp_portfolio
                    self.log_message.emit(f"✅ Портфолио успешно обновлено новыми данными")
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
    
    def process_signal(self, signal: TradingSignal):
        """Обработка торгового сигнала"""
        try:
            # Проверяем, включена ли торговля
            if not self.trading_enabled:
                self.log_message.emit(f"⏸️ Торговля отключена. Сигнал {signal.signal} для {signal.symbol} игнорируется.")
                return
            
            self.log_message.emit(f"🔍 Обработка сигнала {signal.signal} для {signal.symbol} (уверенность: {signal.confidence:.2f})")
            
            if signal.signal == 'BUY':
                self.execute_buy_order(signal)
            elif signal.signal == 'SELL':
                self.execute_sell_order(signal)
                
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка обработки сигнала {signal.symbol}: {e}")
    
    def execute_buy_order(self, signal: TradingSignal):
        """Выполнение ордера на покупку"""
        try:
            # Проверяем кулдаун для данного символа
            current_time = time.time()
            if signal.symbol in self.last_buy_times:
                time_since_last_buy = current_time - self.last_buy_times[signal.symbol]
                if time_since_last_buy < self.buy_cooldown:
                    remaining_time = self.buy_cooldown - time_since_last_buy
                    self.log_message.emit(f"⏳ Кулдаун для {signal.symbol}: осталось {remaining_time:.0f} сек")
                    return
            
            # Проверяем баланс USDT
            usdt_balance = self.portfolio.get('USDT', 0)
            
            # Получаем актуальную информацию об инструменте через API
            instrument_info = self.get_instrument_info(signal.symbol)
            min_trade_amount = float(instrument_info['minOrderAmt'])
            
            # ВАЖНО: Bybit API требует минимум $5 для API торговли (с января 2025)
            # Но для BTCUSDT minOrderAmt уже равен 5 USDT согласно API ответу
            api_min_order_value = 5.0  # $5 минимум для API торговли
            
            # Устанавливаем эффективную минимальную сумму на основе реальных данных API
            if signal.symbol == 'BTCUSDT':
                # Для BTCUSDT используем minOrderAmt из API (5 USDT)
                effective_min_amount = max(min_trade_amount, api_min_order_value)
                max_trade_amount = max(effective_min_amount * 20, 100.0)  # До $100 для BTCUSDT
            elif signal.symbol in ['ETHUSDT', 'BNBUSDT', 'LINKUSDT']:
                # Для других дорогих активов используем более высокий минимум
                effective_min_amount = max(min_trade_amount, api_min_order_value, 50.0)
                max_trade_amount = max(effective_min_amount * 4, 200.0)
            else:
                # Для всех остальных символов используем API минимум $5
                effective_min_amount = max(min_trade_amount, api_min_order_value)
                max_trade_amount = max(effective_min_amount * 10, 50.0)  # Минимум $50 для надежности
            
            if usdt_balance < effective_min_amount:
                self.log_message.emit(f"⚠️ Недостаточно USDT для покупки {signal.symbol}: ${usdt_balance:.2f} (минимум ${effective_min_amount})")
                return
            
            # Рассчитываем сумму для покупки (1% от USDT, но не менее минимума и не более максимума)
            trade_amount = max(min(usdt_balance * 0.01, max_trade_amount), effective_min_amount)
            
            # Рассчитываем количество для покупки
            qty = trade_amount / signal.price
            
            # Получаем минимальное количество из API
            min_order_qty = instrument_info['minOrderQty']
            
            # Проверяем, что количество не меньше минимального
            if qty < min_order_qty:
                # Увеличиваем количество до минимального
                qty = min_order_qty
                # Пересчитываем сумму сделки
                trade_amount = qty * signal.price
                self.log_message.emit(f"⚠️ Количество увеличено до минимального: {qty:.8f}")
            
            # Округляем количество согласно точности инструмента
            base_precision = instrument_info.get('basePrecision', '0.00001')
            decimal_places = len(base_precision.split('.')[-1]) if '.' in base_precision else 0
            qty = round(qty, decimal_places)
            
            # ВАЖНО: Пересчитываем итоговую стоимость после округления
            final_order_value = qty * signal.price
            
            # Проверяем, что итоговая стоимость не меньше эффективной минимальной
            if final_order_value < effective_min_amount:
                # Увеличиваем количество, чтобы достичь минимальной стоимости
                qty = effective_min_amount / signal.price
                # Снова округляем
                qty = round(qty, decimal_places)
                # Пересчитываем итоговую стоимость
                final_order_value = qty * signal.price
                trade_amount = final_order_value
                self.log_message.emit(f"⚠️ Количество скорректировано для достижения эффективной минимальной стоимости: {qty:.8f}")
            
            self.log_message.emit(f"💰 ПОКУПКА {signal.symbol}: ${trade_amount:.2f} USDT ({qty:.6f} {signal.symbol.replace('USDT', '')})")
            self.log_message.emit(f"   Цена: ${signal.price:.6f}, Итоговая стоимость: ${final_order_value:.2f}, Эффективный минимум: ${effective_min_amount:.2f}")
            self.log_message.emit(f"   Причина: {signal.reason}")
            
            # Выполняем реальный ордер
            order_result = self.bybit_client.place_order(
                category='spot',
                symbol=signal.symbol,
                side='Buy',
                order_type='Market',
                qty=str(qty)
            )
            
            if order_result and order_result.get('retCode') == 0:
                self.log_message.emit(f"✅ Ордер на покупку {signal.symbol} успешно размещен")
                
                # Обновляем время последней покупки для данного символа
                self.last_buy_times[signal.symbol] = current_time
                
                # Эмитируем событие выполненной сделки
                trade_info = {
                    'symbol': signal.symbol,
                    'side': 'BUY',
                    'amount': trade_amount,
                    'qty': qty,
                    'price': signal.price,
                    'confidence': signal.confidence,
                    'reason': signal.reason,
                    'order_id': order_result.get('result', {}).get('orderId'),
                    'timestamp': datetime.now().isoformat()
                }
                self.trade_executed.emit(trade_info)
            else:
                error_msg = order_result.get('retMsg', 'Неизвестная ошибка') if order_result else 'Нет ответа от API'
                self.log_message.emit(f"❌ Ошибка размещения ордера на покупку {signal.symbol}: {error_msg}")
            
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка выполнения покупки {signal.symbol}: {e}")
    
    def execute_sell_order(self, signal: TradingSignal):
        """Выполнение ордера на продажу"""
        try:
            base_asset = signal.symbol.replace('USDT', '')
            asset_balance = self.portfolio.get(base_asset, 0)
            
            if asset_balance <= 0:
                self.log_message.emit(f"⚠️ Недостаточно {base_asset} для продажи: {asset_balance}")
                return
            
            # Продаем 50% от имеющегося количества
            sell_amount = asset_balance * 0.5
            
            # Округляем количество для продажи с учетом цены монеты
            if signal.price > 1000:  # BTC, ETH и другие дорогие монеты
                sell_amount = round(sell_amount, 6)
            elif signal.price > 1:   # Большинство альткоинов
                sell_amount = round(sell_amount, 4)
            else:                    # Дешевые монеты
                sell_amount = round(sell_amount, 2)
            
            estimated_usdt = sell_amount * signal.price
            
            self.log_message.emit(f"💸 ПРОДАЖА {signal.symbol}: {sell_amount:.6f} {base_asset} ≈ ${estimated_usdt:.2f}")
            self.log_message.emit(f"   Цена: ${signal.price:.6f}, Причина: {signal.reason}")
            
            # Выполняем реальный ордер
            order_result = self.bybit_client.place_order(
                category='spot',
                symbol=signal.symbol,
                side='Sell',
                order_type='Market',
                qty=str(sell_amount)
            )
            
            if order_result and order_result.get('retCode') == 0:
                self.log_message.emit(f"✅ Ордер на продажу {signal.symbol} успешно размещен")
                
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
            else:
                error_msg = order_result.get('retMsg', 'Неизвестная ошибка') if order_result else 'Нет ответа от API'
                self.log_message.emit(f"❌ Ошибка размещения ордера на продажу {signal.symbol}: {error_msg}")
            
        except Exception as e:
            self.log_message.emit(f"❌ Ошибка выполнения продажи {signal.symbol}: {e}")
    
    def stop(self):
        """Остановка торгового движка"""
        self.running = False


class TraderMainWindow(QMainWindow):
    """Главное окно программы-торговца"""
    
    def __init__(self, enable_trading=False):
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
        
        # Настройка логирования
        self.setup_logging()
        
        # Настройка интерфейса (сначала создаем UI элементы)
        self.setup_ui()
        
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
        
        # Торговый движок
        if self.bybit_client:
            self.trading_engine = TradingEngine(self.bybit_client, self.enable_trading_on_start)
        else:
            self.trading_engine = None
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        
        # Верхняя панель управления
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # Основная область с разделителем
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - статус и сигналы
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Правая панель - логи
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([600, 600])
        main_layout.addWidget(splitter)
        
        # Статусная строка
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("🔴 Торговля остановлена")
    
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
        
        # Отключаем торговлю в движке
        if self.trading_engine:
            self.trading_engine.trading_enabled = False
            self.add_log("⏹️ Торговля отключена в движке")
        
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
            signal_generator = SignalGenerator(self.logger)
            portfolio = getattr(self.trading_engine, 'portfolio', {})
            signals = signal_generator.generate_signals(data, portfolio)
            
            # Обновляем таблицу сигналов
            self.update_signals_table(signals)
            
            # Отправляем сигналы в торговый движок
            if signals:
                self.trading_engine.add_signals(signals)
    
    def update_signals_table(self, signals: List[TradingSignal]):
        """Обновление таблицы сигналов"""
        self.signals_table.setRowCount(len(signals))
        
        for i, signal in enumerate(signals):
            self.signals_table.setItem(i, 0, QTableWidgetItem(signal.symbol))
            self.signals_table.setItem(i, 1, QTableWidgetItem(signal.signal))
            self.signals_table.setItem(i, 2, QTableWidgetItem(f"{signal.confidence:.2f}"))
            self.signals_table.setItem(i, 3, QTableWidgetItem(f"${signal.price:.6f}"))
            self.signals_table.setItem(i, 4, QTableWidgetItem(signal.reason))
    
    def on_trade_executed(self, trade_info: Dict):
        """Обработка выполненной сделки"""
        self.trade_history.append(trade_info)
        self.update_statistics()
        
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
        
        # Пока что считаем все сделки успешными (симуляция)
        self.successful_trades_label.setText(str(total_trades))
        
        # Расчет прибыли (упрощенный)
        total_profit = 0.0  # Пока что $0
        self.total_profit_label.setText(f"${total_profit:.2f}")
    
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
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
    
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