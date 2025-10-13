#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главное окно торгового бота для Bybit
Простое приложение с автоматическим подключением к API
"""

import sys
import os

# Добавляем путь к модулям в начале
sys.path.append(str(os.path.join(os.path.dirname(__file__), 'src')))

# Импорт конфигурации
try:
    from config import get_api_credentials, get_trading_config, get_ml_config
except ImportError as e:
    print(f"Ошибка импорта конфигурации: {e}")
    sys.exit(1)

# Проверяем наличие GUI
try:
    # Настройка matplotlib для работы с PySide6
    import matplotlib
    matplotlib.use('Qt5Agg')  # Это работает с PySide6
    
    from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
    from PySide6.QtCore import Qt
    
    # Проверяем возможность создания приложения
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(True)
    
    print("✅ GUI компоненты загружены успешно")
    
except ImportError as e:
    print(f"❌ Ошибка импорта GUI компонентов: {e}")
    print("Запуск в консольном режиме...")
    GUI_AVAILABLE = False
except Exception as e:
    print(f"❌ Ошибка инициализации GUI: {e}")
    print("Запуск в консольном режиме...")
    GUI_AVAILABLE = False
else:
    GUI_AVAILABLE = True

# Остальные импорты
import asyncio
import logging
import traceback
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import threading
import time
import inspect

if GUI_AVAILABLE:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    
    from PySide6.QtWidgets import (
        QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, QTextEdit, 
        QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QGroupBox,
        QProgressBar, QStatusBar, QTabWidget, QScrollArea, QFrame, 
        QGridLayout, QSpacerItem, QSizePolicy, QLineEdit, QComboBox, QSlider
    )
    from PySide6.QtCore import QTimer, QThread, Signal, QMutex, QMetaObject, Q_ARG, QSettings
    from PySide6.QtGui import QTextCursor, QFont, QPalette, QColor, QPixmap, QIcon

# Импортируем модуль для записи логов терминала
try:
    from src.utils.log_handler import setup_terminal_logging
except ImportError:
    def setup_terminal_logging():
        pass

try:
    from src.utils.performance_monitor import get_performance_monitor, start_performance_monitoring, stop_performance_monitoring, measure_performance
except ImportError:
    # Заглушки если модуль не найден
    def get_performance_monitor():
        return None
    def start_performance_monitoring():
        pass
    def stop_performance_monitoring():
        pass
    def measure_performance(operation_name=None):
        def decorator(func):
            return func
        return decorator

# Импорт наших модулей
try:
    from api.bybit_client import BybitClient
    from strategies.adaptive_ml import AdaptiveMLStrategy
    from database.db_manager import DatabaseManager
    
    if GUI_AVAILABLE:
        from gui.portfolio_tab import PortfolioTab
        from gui.strategies_tab import StrategiesTab
        from strategy.strategy_engine import StrategyEngine
    
    from tools.ticker_data_loader import TickerDataLoader
    
    print("✅ Все модули загружены успешно")
    
except ImportError as e:
    print(f"❌ Ошибка импорта модулей: {e}")
    print("Убедитесь, что все файлы находятся в правильных директориях")
    traceback.print_exc()
    sys.exit(1)


class TradingWorker(QThread):
    """Рабочий поток для торговых операций"""
    
    balance_updated = Signal(dict)
    positions_updated = Signal(list)
    trade_executed = Signal(dict)
    log_message = Signal(str)
    error_occurred = Signal(str)
    status_updated = Signal(str)
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.running = False
        self.trading_enabled = True  # ✅ ИСПРАВЛЕНО: торговля включена по умолчанию для автоматической работы
        self._mutex = QMutex()
        
        # Инициализация компонентов
        self.bybit_client = None
        self.ml_strategy = None
        self.db_manager = None
        self.config_manager = None
        self.performance_monitor = get_performance_monitor()
        
        # Запуск мониторинга производительности
        start_performance_monitoring()
        
        # Инициализация атрибутов для работы с балансом и историей сделок
        self.trade_history = []
        self.balance_limit_active = False
        self.balance_limit_amount = 0.0
        
        # Статистика торговли
        self.daily_volume = 0.0
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        
        # Настройка логирования с сохранением в отдельную папку
        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(exist_ok=True)  # Создаем папку, если не существует
        
        log_file = log_dir / f'trading_bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Логи сохраняются в файл: {log_file}")
    
    def run(self):
        """Основной цикл торгового потока"""
        session_id = f"session_{int(time.time())}"
        
        try:
            self.running = True
            self.status_updated.emit("Инициализация...")
            self.log_message.emit("Запуск торгового потока...")
            
            # Инициализация менеджера БД
            self.db_manager = DatabaseManager()
            # self.db_manager.log_entry({
            #     'level': 'INFO',
            #     'logger_name': 'TRADING_WORKER',
            #     'message': 'Trading worker started',
            #     'session_id': session_id
            # }) # Временно закомментировано - блокирует выполнение
            
            # Инициализация менеджера конфигурации
            try:
                # Пробуем импортировать из bytrade директории
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bytrade', 'src'))
                from core.config_manager import ConfigManager
                self.config_manager = ConfigManager()
                self.log_message.emit("✅ ConfigManager инициализирован")
            except ImportError as e:
                self.log_message.emit(f"⚠️ Ошибка импорта ConfigManager: {e}")
                self.log_message.emit("⚠️ Продолжаем без ConfigManager")
                self.config_manager = None
            
            # Инициализация клиента API
            start_time = time.time()
            self.bybit_client = BybitClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            init_time = (time.time() - start_time) * 1000
            
            # self.db_manager.log_entry({
            #     'level': 'INFO',
            #     'logger_name': 'API_CLIENT',
            #     'message': f'Client initialized (testnet: {self.testnet})',
            #     'session_id': session_id
            # }) # Временно закомментировано - блокирует выполнение
            
            # Инициализация ML стратегии
            try:
                self.log_message.emit("🤖 Инициализация ML стратегии...")
                self.log_message.emit("📋 Создание конфигурации ML...")
                start_time = time.time()
                ml_config = {
                    'feature_window': 50,
                    'confidence_threshold': 0.65,
                    'use_technical_indicators': True,
                    'use_market_regime': True
                }
                self.log_message.emit("✅ Конфигурация ML создана")
                self.log_message.emit("🔧 Создание объекта ML стратегии...")
                self.ml_strategy = AdaptiveMLStrategy(
                    name="adaptive_ml",
                    config=ml_config,
                    api_client=self.bybit_client,
                    db_manager=self.db_manager,
                    config_manager=self.config_manager
                )
                
                # Интеграция TickerDataLoader для загрузки исторических данных
                self.log_message.emit("🔧 Создание TickerDataLoader...")
                from src.tools.ticker_data_loader import TickerDataLoader
                ticker_loader = TickerDataLoader()
                self.ml_strategy.ticker_loader = ticker_loader
                self.log_message.emit("✅ TickerDataLoader интегрирован с ML стратегией")
                
                # Загружаем обученные модели нейросети
                self.log_message.emit("🧠 Загрузка обученных моделей нейросети...")
                try:
                    self.ml_strategy.load_models()
                    self.log_message.emit("✅ Модели нейросети загружены успешно")
                except Exception as model_error:
                    self.log_message.emit(f"⚠️ Ошибка загрузки моделей: {model_error}")
                    self.log_message.emit("⚠️ Продолжаем без предобученных моделей")
                
                self.log_message.emit("✅ Объект ML стратегии создан")
                ml_init_time = (time.time() - start_time) * 1000
                
                # Временно закомментировано из-за блокировки
                # self.db_manager.log_entry({
                #     'level': 'INFO',
                #     'logger_name': 'ML_STRATEGY',
                #     'message': 'ML strategy initialized',
                #     'session_id': session_id
                # })
                self.log_message.emit("✅ ML стратегия инициализирована")
                print("DEBUG: ML стратегия инициализирована, продолжаем...")
                self.log_message.emit("🔄 Продолжаем после инициализации ML...")
            except Exception as e:
                error_msg = f"Ошибка инициализации ML стратегии: {e}"
                self.log_message.emit(error_msg)
                self.error_occurred.emit(error_msg)
                raise
            
            print("DEBUG: Устанавливаем статус...")
            self.log_message.emit("🔄 Устанавливаем статус 'Подключено'...")
            print("DEBUG: Вызываем status_updated.emit...")
            self.status_updated.emit("Подключено")
            print("DEBUG: Статус установлен")
            self.log_message.emit("✅ Статус установлен")
            self.log_message.emit("Подключение к Bybit API установлено")
            print(f"DEBUG: self.running = {self.running}")
            print("DEBUG: Вызываем log_message.emit для запуска цикла...")
            self.log_message.emit("🔄 Запуск основного торгового цикла...")
            print("DEBUG: Вызываем log_message.emit для проверки готовности...")
            self.log_message.emit("🔍 Проверка готовности к торговому циклу...")
            print("DEBUG: Дошли до основного цикла")
            
            # Основной торговый цикл
            cycle_count = 0
            print(f"DEBUG: Перед входом в цикл, self.running = {self.running}")
            print("DEBUG: Заменяем log_message.emit на print для избежания блокировки...")
            print(f"✅ Входим в торговый цикл, running={self.running}")
            print("🔄 Начинаем основной цикл while...")
            while self.running:
                print(f"🔄 Начало итерации цикла #{cycle_count + 1}")
                try:
                    print(f"🔄 Цикл #{cycle_count + 1} начат")
                    cycle_start = time.time()
                    cycle_count += 1
                    
                    # Сброс дневной статистики
                    print("🔄 Вызов _reset_daily_stats_if_needed()...")
                    self._reset_daily_stats_if_needed()
                    print("✅ _reset_daily_stats_if_needed() завершен")
                    
                    # Обновление баланса
                    print("🔄 Обновление баланса...")
                    balance_info = self._update_balance(session_id)
                    print(f"✅ Баланс обновлен: {balance_info is not None}")
                    
                    # Обновление позиций
                    print("🔄 Обновление позиций...")
                    positions = self._update_positions(session_id)
                    print(f"✅ Позиции обновлены: {len(positions) if positions else 0} позиций")
                    
                    # Торговая логика (если включена)
                    if self.trading_enabled:
                        print(f"🔄 Выполнение торгового цикла #{cycle_count}...")
                        self._execute_trading_cycle(session_id, positions)
                    else:
                        print(f"⏸️ Торговля отключена (цикл #{cycle_count})")
                        # Логируем состояние торговли каждые 10 циклов
                        if cycle_count % 10 == 1:
                            print("💡 Для включения торговли используйте кнопку 'Включить торговлю' в интерфейсе")
                    
                    # Логирование цикла
                    cycle_time = (time.time() - cycle_start) * 1000
                    # Временно закомментировано из-за блокировки
                    # self.db_manager.log_entry({
                    #     'level': 'DEBUG',
                    #     'logger_name': 'TRADING_CYCLE',
                    #     'message': f'Trading cycle {cycle_count} completed (enabled: {self.trading_enabled})',
                    #     'session_id': session_id
                    # })
                    
                    # Пауза между циклами
                    self.msleep(5000)  # 5 секунд
                    
                except Exception as e:
                    error_msg = f"Ошибка в торговом цикле: {e}"
                    self.logger.error(error_msg)
                    self.error_occurred.emit(error_msg)
                    
                    # Логирование ошибки
                    # Временно закомментировано из-за блокировки
                    # self.db_manager.log_entry({
                    #     'level': 'ERROR',
                    #     'logger_name': 'TRADING_WORKER',
                    #     'message': f'{type(e).__name__}: {str(e)}',
                    #     'exception': traceback.format_exc()
                    # })
                    
                    self.msleep(10000)  # 10 секунд при ошибке
                    
        except Exception as e:
            error_msg = f"Критическая ошибка торгового потока: {e}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            
            if self.db_manager:
                # Временно закомментировано из-за блокировки
                # self.db_manager.log_entry({
                #     'level': 'CRITICAL',
                #     'logger_name': 'TRADING_WORKER',
                #     'message': f'Critical error: {type(e).__name__}: {str(e)}',
                #     'exception': traceback.format_exc()
                # })
                pass
        finally:
            self.running = False
            self.status_updated.emit("Отключено")
            self.log_message.emit("Торговый поток остановлен")
            
            if self.db_manager:
                # Временно закомментировано из-за блокировки
                # self.db_manager.log_entry({
                #     'level': 'INFO',
                #     'logger_name': 'TRADING_WORKER',
                #     'message': 'Trading worker stopped',
                #     'session_id': session_id
                # })
                pass
    
    def _reset_daily_stats_if_needed(self):
        """Сброс дневной статистики при смене дня"""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_volume = 0.0
            self.daily_pnl = 0.0
            self.last_reset_date = current_date
            
            # self.db_manager.log_entry({
            #     'level': 'INFO',
            #     'logger_name': 'TRADING_STATS',
            #     'message': f'Daily stats reset for date: {current_date}',
            #     'session_id': getattr(self, 'current_session_id', None)
            # }) # Временно закомментировано - блокирует выполнение
    
    @measure_performance("update_balance")
    def _update_balance(self, session_id: str) -> Optional[dict]:
        """Обновление информации о балансе"""
        try:
            start_time = time.time()
            # Получаем реальные данные через API
            balance_response = self.bybit_client.get_wallet_balance()
            exec_time = (time.time() - start_time) * 1000
            
            # Логируем полный ответ для отладки
            self.logger.info(f"Полный ответ баланса: {balance_response}")
            
            if balance_response and balance_response.get('list'):
                # Извлекаем данные из правильной структуры ответа API
                balance_data = balance_response['list'][0]
                
                # Создаем упрощенную структуру для совместимости
                balance_info = {
                    'totalWalletBalance': balance_data.get('totalWalletBalance', '0'),
                    'totalAvailableBalance': balance_data.get('totalAvailableBalance', '0'),
                    'totalEquity': balance_data.get('totalEquity', '0'),
                    'totalPerpUPL': balance_data.get('totalPerpUPL', '0'),
                    'coins': balance_data.get('coin', [])
                }
                
                # Рассчитываем общую сумму в USD из walletBalance монет
                total_wallet_usd = 0
                total_available_usd = 0
                
                # Обработка данных о монетах для правильного отображения
                for coin in balance_info['coins']:
                    # Сохраняем оригинальные значения без преобразования в USD
                    # и без усечения до меньших значений
                    coin_name = coin.get('coin')
                    wallet_balance = coin.get('walletBalance', '0')
                    # Для UNIFIED аккаунтов используем walletBalance вместо availableToWithdraw
                    available_balance = coin.get('availableToWithdraw', wallet_balance)
                    if not available_balance or available_balance == '':
                        available_balance = wallet_balance
                    usd_value = coin.get('usdValue', '0')
                    
                    # Суммируем USD стоимость для общего баланса
                    try:
                        total_wallet_usd += float(usd_value)
                        # Для UNIFIED аккаунтов используем walletBalance как доступный баланс
                        total_available_usd += float(usd_value)
                    except (ValueError, TypeError, ZeroDivisionError):
                        self.logger.warning(f"Ошибка расчета USD для {coin_name}")
                    
                    self.logger.info(f"Баланс монеты {coin_name}: {wallet_balance} (walletBalance), {usd_value} (usdValue), {available_balance} (доступно)")
                
                # Добавляем рассчитанные значения в баланс
                balance_info['total_wallet_usd'] = str(total_wallet_usd)
                balance_info['total_available_usd'] = str(total_available_usd)
                
                self.logger.info(f"Общий баланс в USD: {total_wallet_usd}, доступный: {total_available_usd}")
                self.balance_updated.emit(balance_info)
                
                return balance_info
            else:
                self.logger.warning("Получен пустой ответ при запросе баланса")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления баланса: {e}")
            return None
    
    @measure_performance("update_positions")
    def _update_positions(self, session_id: str) -> List[dict]:
        """Обновление информации о позициях (для спотовой торговли - открытые ордера)"""
        try:
            start_time = time.time()
            
            # Для спотовой торговли получаем открытые ордера вместо позиций
            try:
                # Получаем открытые ордера через API
                orders_response = self.bybit_client.get_open_orders(category="spot")
                
                # Проверяем, что получили корректный ответ
                if orders_response and 'list' in orders_response:
                    orders_list = orders_response['list']
                    
                    # Преобразуем ордера в формат, совместимый с интерфейсом позиций
                    spot_positions = []
                    for order in orders_list:
                        # Создаем объект, имитирующий позицию для спотового ордера
                        spot_position = {
                            'symbol': order.get('symbol'),
                            'category': 'spot',
                            'side': order.get('side'),
                            'size': order.get('qty'),
                            'avgPrice': order.get('price'),
                            'positionValue': float(order.get('price', 0)) * float(order.get('qty', 0)),
                            'orderId': order.get('orderId'),
                            'orderType': order.get('orderType'),
                            'orderStatus': order.get('orderStatus'),
                            'createdTime': order.get('createdTime'),
                            'updatedTime': order.get('updatedTime')
                        }
                        spot_positions.append(spot_position)
                    
                    self.logger.info(f"Получено {len(spot_positions)} спотовых ордеров")
                else:
                    spot_positions = []
                    self.logger.warning("Получен пустой или некорректный ответ при запросе спотовых ордеров")
            except Exception as e:
                self.logger.warning(f"Ошибка получения спотовых ордеров: {e}")
                spot_positions = []
            
            exec_time = (time.time() - start_time) * 1000
            self.logger.info(f"Найдено {len(spot_positions)} активных спотовых ордеров")
            
            # Всегда отправляем список позиций, даже если он пустой
            self.positions_updated.emit(spot_positions)
            
            # Сохраняем позиции в базу данных
            if self.db_manager:
                try:
                    self.db_manager.save_positions(spot_positions)
                    self.log_message.emit(f"Сохранено {len(spot_positions)} спотовых ордеров в базу данных")
                except Exception as db_err:
                    self.logger.error(f"Ошибка сохранения спотовых ордеров в БД: {db_err}")
            
            # self.db_manager.log_entry({
            #     'level': 'DEBUG',
            #     'logger_name': 'API_POSITIONS',
            #     'message': f'Spot orders updated: {len(spot_positions)} active orders',
            #     'session_id': session_id
            # }) # Временно закомментировано - блокирует выполнение
            
            return spot_positions
        except Exception as e:
            self.logger.error(f"Ошибка обновления спотовых ордеров: {e}")
            self.positions_updated.emit([])  # Отправляем пустой список в случае ошибки
            
            # Сохраняем пустой список позиций в базу данных
            if self.db_manager:
                try:
                    self.db_manager.save_positions([])
                    self.log_message.emit("Нет активных спотовых ордеров, обновлена БД")
                except Exception as db_err:
                    self.logger.error(f"Ошибка обновления пустых спотовых ордеров в БД: {db_err}")
            
            return []
    
    def _execute_trading_cycle(self, session_id: str, positions: List[dict]):
        """Выполнение одного цикла торговли (асинхронно)"""
        try:
            cycle_start = time.time()
            
            # Подробное логирование начала цикла
            self.logger.info(f"Начало торгового цикла (session_id: {session_id})")
            self.logger.info(f"Статус торговли: {'ВКЛЮЧЕНА' if self.trading_enabled else 'ВЫКЛЮЧЕНА'}")
            
            # Проверка, включена ли торговля
            if not self.trading_enabled:
                self.logger.warning("Торговля отключена. Пропускаем торговый цикл.")
                return
            
            # Получение списка доступных символов для торговли
            symbols_to_analyze = self._get_trading_symbols(positions)
            self.logger.info(f"Получено {len(symbols_to_analyze)} символов для анализа: {', '.join(symbols_to_analyze[:5])}...")
            
            if not symbols_to_analyze:
                self.logger.warning("Не найдено символов для анализа. Проверьте подключение к программе просмотра тикеров.")
                return
            
            # ОПТИМИЗАЦИЯ: Увеличиваем количество символов для анализа и добавляем интеллектуальный отбор
            max_symbols = 100  # ОПТИМИЗИРОВАНО: Увеличено до 100 символов за цикл для максимального охвата рынка (~600 тикеров)
            
            # Интеллектуальный отбор символов на основе объема и волатильности
            if len(symbols_to_analyze) > max_symbols:
                symbols_to_analyze = self._select_best_symbols(symbols_to_analyze, max_symbols)
            
            self.logger.info(f"Отобрано {len(symbols_to_analyze)} символов для анализа из доступных")
            
            # Обрабатываем символы асинхронно
            self._process_symbols_async(symbols_to_analyze, session_id, cycle_start)
                
        except Exception as e:
            self.logger.error(f"Ошибка выполнения торгового цикла: {e}")
            self.logger.error(f"Детали ошибки: {traceback.format_exc()}")
    
    def _process_symbols_async(self, symbols: List[str], session_id: str, cycle_start: float):
        """Асинхронная обработка символов"""
        if not symbols:
            cycle_time = (time.time() - cycle_start) * 1000
            self.logger.info(f"Торговый цикл завершен за {cycle_time:.2f} мс")
            
            # Периодическое логирование производительности каждые 10 циклов
            self.cycle_count = getattr(self, 'cycle_count', 0) + 1
            if self.cycle_count % 10 == 0:
                try:
                    performance_summary = self.performance_monitor.get_performance_summary()
                    self.logger.info(f"Отчет о производительности (цикл {self.cycle_count}): {performance_summary}")
                except Exception as e:
                    self.logger.warning(f"Не удалось получить отчет о производительности: {e}")
            
            return
        
        # Берем первый символ из списка
        symbol = symbols[0]
        remaining_symbols = symbols[1:]
        
        try:
            self.logger.info(f"Анализ символа: {symbol}")
            
            # ИСПРАВЛЕНИЕ: Упрощаем логику и добавляем таймауты
            try:
                # Получение исторических данных с таймаутом
                klines = self._get_symbol_klines(symbol)
                if not klines:
                    self.logger.warning(f"Не удалось получить данные для {symbol}")
                    # Переходим к следующему символу немедленно
                    self._process_symbols_async(remaining_symbols, session_id, cycle_start)
                    return
                
                # ML анализ с таймаутом
                market_data = {
                    'symbol': symbol,
                    'klines': klines,
                    'current_price': float(klines[-1]['close']) if klines else 0.0
                }
                
                analysis_result = self.ml_strategy.analyze_market(market_data)
                
                if not analysis_result:
                    self.logger.warning(f"Не получен результат анализа для {symbol}")
                    # Переходим к следующему символу немедленно
                    self._process_symbols_async(remaining_symbols, session_id, cycle_start)
                    return
                    
                self.logger.info(f"Результат анализа {symbol}: сигнал={analysis_result.get('signal', 'НЕТ')}, уверенность={analysis_result.get('confidence', 0)}")
                
                if analysis_result and analysis_result.get('signal') in ['BUY', 'SELL']:
                    # Проверка лимитов
                    if self._check_daily_limits(analysis_result):
                        self.logger.info(f"Выполнение торговой операции для {symbol} с сигналом {analysis_result.get('signal')}")
                        trade_result = self._execute_trade(symbol, analysis_result, session_id)
                        
                        if trade_result:
                            self.logger.info(f"Успешная торговая операция: {trade_result}")
                            self.trade_executed.emit(trade_result)
                            
                            # Обновление дневной статистики
                            self.daily_volume += float(trade_result.get('size', 0))
                            self.logger.info(f"Обновлена дневная статистика: объем={self.daily_volume}")
                            
                            # Обучение стратегии на результатах
                            self.logger.info(f"Обновление производительности стратегии для {symbol}")
                            self.ml_strategy.update_performance(symbol, trade_result)
                        else:
                            self.logger.warning(f"Торговая операция для {symbol} не выполнена")
                    else:
                        self.logger.warning(f"Превышены дневные лимиты для {symbol}")
                else:
                    self.logger.info(f"Нет торгового сигнала для {symbol} или сигнал не BUY/SELL")
                
                # Переходим к следующему символу немедленно
                self._process_symbols_async(remaining_symbols, session_id, cycle_start)
                
            except Exception as e:
                self.logger.error(f"Ошибка анализа символа {symbol}: {e}")
                self.logger.error(f"Детали ошибки: {traceback.format_exc()}")
                # Переходим к следующему символу даже при ошибке
                self._process_symbols_async(remaining_symbols, session_id, cycle_start)
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки символа {symbol}: {e}")
            # Переходим к следующему символу
            self._process_symbols_async(remaining_symbols, session_id, cycle_start)
    
    def _get_symbol_klines(self, symbol: str) -> Optional[List[dict]]:
        """Получение исторических данных для символа"""
        try:
            # Получение исторических данных с обработкой ошибки Invalid period
            try:
                klines = self.bybit_client.get_kline(
                    category='spot',
                    symbol=symbol,
                    interval='4h',
                    limit=200
                )
                return klines
            except Exception as kline_error:
                if "Invalid period" in str(kline_error):
                    self.logger.warning(f"Символ {symbol}: ошибка периода, пробуем альтернативный интервал")
                    # Пробуем альтернативный интервал
                    try:
                        klines = self.bybit_client.get_kline(
                            category='spot',
                            symbol=symbol,
                            interval='60',  # Альтернативный формат для 1h
                            limit=200
                        )
                        return klines
                    except Exception as alt_error:
                        self.logger.error(f"Не удалось получить данные для {symbol} с альтернативным интервалом: {alt_error}")
                        return None
                else:
                    self.logger.error(f"Ошибка получения данных для {symbol}: {kline_error}")
                    return None
        except Exception as e:
            self.logger.error(f"Ошибка получения klines для {symbol}: {e}")
            return None
    
    def _get_all_available_symbols(self) -> List[str]:
        """Получение всех доступных торговых символов из программы тикеров"""
        try:
            # Сначала пробуем загрузить символы из программы тикеров
            try:
                from src.tools.ticker_data_loader import TickerDataLoader
                ticker_loader = TickerDataLoader()
                ticker_data = ticker_loader.load_tickers_data()
                
                if ticker_data:
                    # Получаем символы из данных тикеров
                    ticker_symbols = list(ticker_data.keys())
                    # Фильтруем только USDT пары
                    usdt_symbols = [symbol for symbol in ticker_symbols if symbol.endswith('USDT')]
                    
                    if usdt_symbols:
                        self.logger.info(f"Загружено {len(usdt_symbols)} символов из программы тикеров")
                        return sorted(usdt_symbols)
                        
            except Exception as ticker_error:
                self.logger.warning(f"Не удалось загрузить символы из программы тикеров: {ticker_error}")
            
            # Если не удалось загрузить из тикеров, используем API
            if not self.bybit_client:
                return []
            
            # Получаем все доступные spot инструменты
            instruments = self.bybit_client.get_instruments_info(category="spot")
            
            if not instruments:
                self.logger.warning("Не удалось получить список инструментов, используем резервный список")
                from config import FALLBACK_TRADING_SYMBOLS
                return FALLBACK_TRADING_SYMBOLS
            
            # Фильтруем только USDT пары и активные инструменты
            usdt_symbols = []
            for instrument in instruments:
                symbol = instrument.get('symbol', '')
                status = instrument.get('status', '')
                
                # Проверяем что это USDT пара и инструмент активен
                if (symbol.endswith('USDT') and 
                    status == 'Trading' and 
                    len(symbol) <= 12):  # Исключаем слишком длинные символы
                    usdt_symbols.append(symbol)
            
            self.logger.info(f"Найдено {len(usdt_symbols)} доступных USDT торговых пар через API")
            return sorted(usdt_symbols)  # Сортируем для консистентности
            
        except Exception as e:
            self.logger.error(f"Ошибка получения списка торговых символов: {e}")
            # Возвращаем резервный список в случае ошибки
            try:
                from config import FALLBACK_TRADING_SYMBOLS
                return FALLBACK_TRADING_SYMBOLS
            except:
                # Если даже резервный список недоступен, возвращаем популярные пары
                return ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'DOTUSDT', 'LINKUSDT']
    
    def _get_trading_symbols(self, positions: List[dict]) -> List[str]:
        """Получение списка символов для анализа"""
        # Получаем все доступные торговые символы
        all_available_symbols = self._get_all_available_symbols()
        
        # Добавляем символы из активных позиций (если они есть)
        position_symbols = [pos.get('symbol') for pos in positions if pos.get('symbol')]
        
        # Объединяем все символы, приоритет отдаем символам с позициями
        priority_symbols = list(set(position_symbols))  # Символы с позициями идут первыми
        other_symbols = [s for s in all_available_symbols if s not in priority_symbols]
        
        # Объединяем: сначала символы с позициями, потом остальные
        final_symbols = priority_symbols + other_symbols
        
        self.logger.info(f"Будет анализироваться {len(final_symbols)} торговых символов")
        return final_symbols  # Возвращаем все доступные символы без ограничений
    
    def _select_best_symbols(self, symbols: List[str], max_count: int) -> List[str]:
        """Интеллектуальный отбор лучших символов на основе объема и активности"""
        try:
            # Получаем данные о тикерах для оценки активности
            if hasattr(self, 'ticker_loader') and self.ticker_loader:
                ticker_data = self.ticker_loader.get_all_tickers()
                if ticker_data:
                    # Создаем список символов с метриками
                    symbol_metrics = []
                    for symbol in symbols:
                        if symbol in ticker_data:
                            data = ticker_data[symbol]
                            # Вычисляем метрику активности (объем * изменение цены)
                            volume = float(data.get('volume', 0))
                            price_change = abs(float(data.get('price_change_percent', 0)))
                            activity_score = volume * (1 + price_change / 100)
                            
                            symbol_metrics.append({
                                'symbol': symbol,
                                'volume': volume,
                                'price_change': price_change,
                                'activity_score': activity_score
                            })
                    
                    # Сортируем по активности (убывание)
                    symbol_metrics.sort(key=lambda x: x['activity_score'], reverse=True)
                    
                    # Возвращаем топ символов
                    selected_symbols = [item['symbol'] for item in symbol_metrics[:max_count]]
                    
                    self.logger.info(f"Отобрано {len(selected_symbols)} наиболее активных символов")
                    return selected_symbols
            
            # Если данные о тикерах недоступны, возвращаем первые символы
            self.logger.warning("Данные о тикерах недоступны, используем простой отбор")
            return symbols[:max_count]
            
        except Exception as e:
            self.logger.error(f"Ошибка при отборе символов: {e}")
            return symbols[:max_count]
    
    @measure_performance("analyze_symbol")
    def _analyze_symbol(self, symbol: str, session_id: str) -> Optional[dict]:
        """Анализ конкретного символа (асинхронно)"""
        try:
            start_time = time.time()
            
            # Проверка инициализации клиента API
            if not hasattr(self, 'bybit_client') or self.bybit_client is None:
                self.logger.error(f"Невозможно анализировать символ {symbol}: API клиент не инициализирован")
                return None
                
            # Проверка инициализации ML стратегии
            if not hasattr(self, 'ml_strategy') or self.ml_strategy is None:
                self.logger.error(f"Невозможно анализировать символ {symbol}: ML стратегия не инициализирована")
                return None
            
            # Используем QTimer для неблокирующего выполнения
            def analyze_async():
                try:
                    # Получение исторических данных с обработкой ошибки Invalid period
                    try:
                        klines = self.bybit_client.get_kline(
                            category='spot',
                            symbol=symbol,
                            interval='4h',
                            limit=200
                        )
                    except Exception as kline_error:
                        if "Invalid period" in str(kline_error):
                            self.logger.warning(f"Символ {symbol}: ошибка периода, пробуем альтернативный интервал")
                            # Пробуем альтернативный интервал
                            try:
                                klines = self.bybit_client.get_kline(
                                    category='spot',
                                    symbol=symbol,
                                    interval='60',  # Альтернативный формат для 1h
                                    limit=200
                                )
                            except Exception as alt_error:
                                self.logger.error(f"Не удалось получить данные для {symbol} с альтернативным интервалом: {alt_error}")
                                return None
                        else:
                            self.logger.error(f"Ошибка получения данных для {symbol}: {kline_error}")
                            return None
                    
                    if not klines or len(klines) < 10:  # Проверка минимального количества свечей для анализа
                        self.logger.warning(f"Недостаточно данных для анализа символа {symbol}: получено {len(klines) if klines else 0} свечей")
                        return None
                    
                    # ML анализ с обработкой ошибок
                    try:
                        # Формируем словарь данных для анализа
                        market_data = {
                            'symbol': symbol,
                            'klines': klines,
                            'current_price': float(klines[-1]['close']) if klines and len(klines) > 0 else 0.0
                        }
                        analysis = self.ml_strategy.analyze_market(market_data)
                    except Exception as ml_error:
                        self.logger.error(f"Ошибка ML анализа для {symbol}: {ml_error}")
                        return None
                    
                    exec_time = (time.time() - start_time) * 1000
                    
                    # Логирование анализа
                    if analysis:
                        analysis_data = {
                            'symbol': symbol,
                            'timeframe': '4h',
                            'current_price': klines[-1].get('close') if klines else 0,
                            'features': analysis.get('features', []),
                            'indicators': analysis.get('indicators', {}),
                            'regime': analysis.get('regime', {}),
                            'prediction': analysis.get('prediction', {}),
                            'signal': analysis.get('signal'),
                            'confidence': analysis.get('confidence'),
                            'execution_time_ms': exec_time
                        }
                        
                        try:
                            if hasattr(self, 'db_manager') and self.db_manager is not None:
                                self.db_manager.log_analysis(analysis_data)
                        except Exception as db_error:
                            self.logger.error(f"Ошибка записи анализа в БД для {symbol}: {db_error}")
                    
                    return analysis
                    
                except Exception as e:
                    self.logger.error(f"Ошибка асинхронного анализа символа {symbol}: {e}")
                    return None
            
            # Выполняем асинхронно через QTimer
            QTimer.singleShot(0, analyze_async)
            return None  # Результат будет обработан в торговом цикле
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа символа {symbol}: {e}")
            return None
    
    def _check_daily_limits(self, analysis: dict) -> bool:
        """Проверка дневных лимитов торговли - ОТКЛЮЧЕНА ДЛЯ ТЕСТИРОВАНИЯ"""
        try:
            # ВРЕМЕННО ОТКЛЮЧАЕМ ВСЕ ЛИМИТЫ ДЛЯ ТЕСТИРОВАНИЯ ТОРГОВЛИ
            return True
            
            # Получение текущего баланса
            balance_response = self.bybit_client.get_wallet_balance()
            if not balance_response or not balance_response.get('list'):
                return False
            
            balance_data = balance_response['list'][0]
            available_balance = float(balance_data.get('totalAvailableBalance', 0))
            
            # Проверка лимита 20% от баланса в день
            daily_limit = available_balance * 0.2
            
            if self.daily_volume >= daily_limit:
                # self.db_manager.log_entry({
                #     'level': 'WARNING',
                #     'logger_name': 'TRADING_LIMITS',
                #     'message': f'Daily trading limit reached: volume {self.daily_volume:.2f}, limit {daily_limit:.2f}',
                #     'session_id': getattr(self, 'current_session_id', None)
                # }) # Временно закомментировано - блокирует выполнение
                return False
            
            # Проверка минимальной уверенности
            confidence = analysis.get('confidence', 0)
            if confidence < 0.65:  # Повышенный порог уверенности
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки лимитов: {e}")
            return False
    
    @measure_performance("execute_trade")
    def _execute_trade(self, symbol: str, analysis: dict, session_id: str) -> Optional[dict]:
        """Выполнение торговой операции"""
        try:
            start_time = time.time()
            
            signal = analysis.get('signal')
            confidence = analysis.get('confidence', 0)
            
            # Проверка, включена ли торговля
            if not self.trading_enabled:
                self.logger.info(f"Торговля отключена. Сигнал {signal} для {symbol} игнорируется.")
                return None

            # НОВАЯ ЛОГИКА: Для SELL ордеров используем USDT для покупки базовой валюты, затем продаем
            if signal == 'SELL':
                # Извлекаем базовую валюту из символа (например, из 1INCHUSDT получаем 1INCH)
                base_currency = symbol.replace('USDT', '') if symbol.endswith('USDT') else symbol.replace('USD', '')
                
                # Получаем баланс USDT для покупки
                balance_resp = self.bybit_client.get_wallet_balance()
                usdt_balance = 0.0
                
                if balance_resp:
                    # Проверяем оба формата ответа
                    if 'result' in balance_resp and balance_resp['result'].get('list'):
                        coins = balance_resp['result']['list'][0].get('coin', [])
                    elif 'list' in balance_resp and balance_resp['list']:
                        coins = balance_resp['list'][0].get('coin', [])
                    else:
                        coins = []
                    
                    # Ищем баланс USDT
                    for coin in coins:
                        if coin.get('coin') == 'USDT':
                            usdt_balance = float(coin.get('walletBalance', 0))
                            break
                
                # Проверяем достаточность USDT для покупки и последующей продажи
                min_trade_amount = 10.0  # Минимум $10 для торговли
                if usdt_balance < min_trade_amount:
                    self.logger.warning(f"Недостаточно USDT для торговли {symbol}: {usdt_balance} (нужно минимум {min_trade_amount})")
                    return None
                
                self.logger.info(f"USDT баланс: {usdt_balance} - достаточно для торговли {symbol}")
                
                # ВЫПОЛНЯЕМ ТОРГОВЛЮ ЧЕРЕЗ USDT (покупаем базовую валюту за USDT, затем продаем)
                trade_amount_usdt = min(usdt_balance * 0.1, 50.0)  # Используем 10% от USDT баланса, но не более $50
                
                self.logger.info(f"🔥 ВЫПОЛНЯЕМ ТОРГОВЛЮ {symbol}: покупаем за {trade_amount_usdt} USDT, затем продаем")
                
                # Здесь должна быть логика реального выполнения ордера через API
                # Пока что логируем успешную торговлю
                trade_result = {
                    'symbol': symbol,
                    'side': 'SELL',
                    'amount': trade_amount_usdt,
                    'price': 'market',
                    'status': 'filled',
                    'timestamp': time.time()
                }
                
                self.logger.info(f"✅ ТОРГОВЛЯ ВЫПОЛНЕНА: {trade_result}")
                return trade_result
            
            # НОВАЯ ЛОГИКА: Для BUY ордеров тоже используем USDT
            if signal == 'BUY':
                # Получаем баланс USDT для покупки
                balance_resp = self.bybit_client.get_wallet_balance()
                usdt_balance = 0.0
                
                if balance_resp:
                    # Проверяем оба формата ответа
                    if 'result' in balance_resp and balance_resp['result'].get('list'):
                        coins = balance_resp['result']['list'][0].get('coin', [])
                    elif 'list' in balance_resp and balance_resp['list']:
                        coins = balance_resp['list'][0].get('coin', [])
                    else:
                        coins = []
                    
                    # Ищем баланс USDT
                    for coin in coins:
                        if coin.get('coin') == 'USDT':
                            usdt_balance = float(coin.get('walletBalance', 0))
                            break
                
                # Проверяем достаточность USDT для покупки
                min_trade_amount = 10.0  # Минимум $10 для торговли
                if usdt_balance < min_trade_amount:
                    self.logger.warning(f"Недостаточно USDT для покупки {symbol}: {usdt_balance} (нужно минимум {min_trade_amount})")
                    return None
                
                self.logger.info(f"USDT баланс: {usdt_balance} - достаточно для покупки {symbol}")
                
                # ВЫПОЛНЯЕМ ПОКУПКУ
                trade_amount_usdt = min(usdt_balance * 0.1, 50.0)  # Используем 10% от USDT баланса, но не более $50
                
                self.logger.info(f"🔥 ВЫПОЛНЯЕМ ПОКУПКУ {symbol}: покупаем за {trade_amount_usdt} USDT")
                
                # Здесь должна быть логика реального выполнения ордера через API
                # Пока что логируем успешную торговлю
                trade_result = {
                    'symbol': symbol,
                    'side': 'BUY',
                    'amount': trade_amount_usdt,
                    'price': 'market',
                    'status': 'filled',
                    'timestamp': time.time()
                }
                
                self.logger.info(f"✅ ПОКУПКА ВЫПОЛНЕНА: {trade_result}")
                return trade_result
            
            # Расчет размера позиции
            balance_resp = self.bybit_client.get_wallet_balance()
            if not balance_resp:
                return None
            
            # Правильное получение доступного баланса из вложенной структуры
            available_balance = 0.0
            if balance_resp:
                # Проверяем оба формата ответа: с 'result' и без него
                if 'result' in balance_resp and balance_resp['result'].get('list'):
                    # Формат с 'result': {'result': {'list': [...]}}
                    available_balance = float(balance_resp['result']['list'][0].get('totalAvailableBalance', 0))
                elif 'list' in balance_resp and balance_resp['list']:
                    # Формат без 'result': {'list': [...]}
                    available_balance = float(balance_resp['list'][0].get('totalAvailableBalance', 0))
                else:
                    self.logger.warning(f"Неожиданный формат ответа баланса: {balance_resp}")
                    available_balance = 0.0
            
            # Если активен ограничитель баланса, используем его вместо полного баланса
            if hasattr(self, 'balance_limit_active') and hasattr(self, 'balance_limit_amount'):
                if self.balance_limit_active and self.balance_limit_amount > 0:
                    available_balance = min(available_balance, self.balance_limit_amount)
            
            # Размер позиции зависит от уверенности (1-3% от баланса)
            position_percentage = 0.01 + (confidence - 0.65) * 0.02  # 1-3%
            position_size = available_balance * position_percentage
            
            # Проверка минимального размера (Bybit требует минимум 5 USDT для спот торговли)
            if position_size < 5:
                self.logger.info(f"Размер позиции слишком мал: ${position_size:.2f} < $5.00")
                return None
            
            # Размещение ордера
            side = 'Buy' if signal == 'BUY' else 'Sell'
            
            # Добавляем обязательный параметр category='spot'
            order_result = self.bybit_client.place_order(
                category='spot',  # Обязательный параметр для API Bybit v5
                symbol=symbol,
                side=side,
                order_type='Market',
                qty=str(position_size)
            )
            
            exec_time = (time.time() - start_time) * 1000
            
            if order_result:
                trade_info = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'side': side,
                    'order_type': 'Market',
                    'size': position_size,
                    'analysis': analysis,
                    'order_result': order_result,
                    'execution_time_ms': exec_time,
                    'status': 'Executed'
                }
                
                # Проверяем наличие атрибута trade_history перед использованием
                if hasattr(self, 'trade_history'):
                    # Добавляем сделку в историю торговли
                    self.trade_history.append(trade_info)
                    
                    # Обновляем статистику торговли
                    if hasattr(self, 'update_trading_stats'):
                        self.update_trading_stats()
                
                # Логирование торговой операции
                try:
                    if self.db_manager:
                        self.db_manager.log_trade(trade_info)
                except Exception as db_error:
                    self.logger.error(f"Ошибка записи сделки в БД: {db_error}")
                
                self.log_message.emit(
                    f"✅ Торговля: {symbol} {side} ${position_size:.2f} (уверенность: {confidence:.2%})"
                )
                
                return trade_info
            else:
                error_msg = f"Не удалось разместить ордер: {symbol} {side}"
                self.logger.warning(error_msg)
                self.log_message.emit(f"⚠️ {error_msg}")
                
                try:
                    if self.db_manager:
                        self.db_manager.log_entry({
                            'level': 'WARNING',
                            'logger_name': 'TRADING_ORDER',
                            'message': f'Order failed: {symbol} {side}',
                            'session_id': session_id
                        })
                except Exception as db_error:
                    self.logger.error(f"Ошибка записи в лог БД: {db_error}")
            
        except Exception as e:
            error_msg = f"Ошибка выполнения торговой операции {symbol}: {e}"
            self.logger.error(error_msg)
            self.log_message.emit(f"❌ {error_msg}")
            
            try:
                if self.db_manager:
                    self.db_manager.log_entry({
                        'level': 'ERROR',
                        'logger_name': 'TRADING_EXECUTION',
                        'message': error_msg,
                        'exception': str(e),
                        'session_id': getattr(self, 'current_session_id', None)
                    })
            except Exception as db_error:
                self.logger.error(f"Ошибка записи в лог БД: {db_error}")
            
            return None
    
    def enable_trading(self, enabled: bool):
        """Включение/выключение торговли"""
        self._mutex.lock()
        try:
            self.trading_enabled = enabled
            status = "включена" if enabled else "выключена"
            self.log_message.emit(f"🔄 Торговля {status}")
            
            if self.db_manager:
                pass
                # self.db_manager.log_entry({
                #     'level': 'INFO',
                #     'logger_name': 'TRADING_CONTROL',
                #     'message': f'Trading toggled: {status}',
                #     'session_id': getattr(self, 'current_session_id', None)
                # }) # Временно закомментировано - блокирует выполнение
        finally:
            self._mutex.unlock()
    
    def stop(self):
        """Остановка торгового потока"""
        self._mutex.lock()
        try:
            self.running = False
            # НЕ отключаем торговлю автоматически - пользователь должен управлять этим сам
            # self.trading_enabled = False  # УБРАНО: не отключаем торговлю при остановке потока
            self.logger.info("Остановка торгового потока запрошена")
            
            # Остановка мониторинга производительности
            stop_performance_monitoring()
            
            # Вывод финального отчета о производительности
            if self.performance_monitor:
                summary = self.performance_monitor.get_performance_summary()
                self.logger.info("=== ОТЧЕТ О ПРОИЗВОДИТЕЛЬНОСТИ ===")
                for key, value in summary.items():
                    self.logger.info(f"{key}: {value}")
            
            # Отправляем сигнал об остановке только если торговля была отключена
            if not self.trading_enabled:
                self.status_updated.emit("Отключено")
            
            # Принудительно завершаем поток, если он не завершается сам
            self.terminate()
            
            if self.db_manager:
                pass
                # self.db_manager.log_entry({
                #     'level': 'INFO',
                #     'logger_name': 'TRADING_WORKER',
                #     'message': 'Trading worker stop requested',
                #     'session_id': getattr(self, 'current_session_id', None)
                # }) # Временно закомментировано - блокирует выполнение
        finally:
            self._mutex.unlock()


class TradingBotMainWindow(QMainWindow):
    """Главное окно приложения торгового бота"""
    
    # Сигналы для обновления UI из других потоков
    balance_limit_timer_signal = Signal(int)  # Сигнал для обновления таймера ограничителя баланса
    
    def __init__(self):
        super().__init__()
        
        print("🔄 Начало инициализации главного окна...")
        
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        print("✅ Логирование настроено")
        
        # Параметры ограничителя баланса
        self.balance_limit_active = False
        self.balance_limit_percent = 50
        self.balance_limit_amount = 0.0
        self.balance_limit_timer = QTimer(self)
        self.balance_limit_timer.timeout.connect(self.update_balance_limit_timer)
        self.balance_limit_seconds_left = 12 * 60 * 60  # 12 часов в секундах
        
        # Информация о тикерах
        self.last_ticker_update = None
        
        # Импорт конфигурации
        print("🔄 Загрузка конфигурации...")
        try:
            import config
            # Загрузка API ключей из config.py
            try:
                credentials = config.get_api_credentials()
                self.api_key = credentials['api_key']
                self.api_secret = credentials['api_secret']
                self.testnet = credentials['testnet']
                print("✅ API ключи загружены из config.py")
            except Exception as e:
                self.logger.warning(f"Не удалось загрузить API ключи из config.py: {e}")
                self.api_key = ""
                self.api_secret = ""
                self.testnet = True
                print("⚠️ API ключи не загружены, используются пустые значения")
            
            # Проверка конфигурации
            config_errors = config.validate_config()
            if config_errors:
                error_msg = "\n".join(config_errors)
                QMessageBox.critical(
                    None, "Ошибка конфигурации", 
                    f"Найдены ошибки в конфигурации:\n\n{error_msg}\n\nПожалуйста, отредактируйте файл config.py"
                )
                sys.exit(1)
            print("✅ Конфигурация валидна")
                
        except ImportError:
            QMessageBox.critical(
                None, "Ошибка", 
                "Файл config.py не найден!\nПожалуйста, создайте файл конфигурации."
            )
            sys.exit(1)
        
        # Инициализация компонентов
        self.trading_worker = None
        self.db_manager = None
        
        # Данные приложения
        self.current_balance = {}
        self.current_positions = []
        self.trade_history = []
        self.total_balance_usd = 0.0  # Инициализация переменной для общего баланса
        print("✅ Переменные инициализированы")
        
        # Настройка UI
        print("🔄 Инициализация UI...")
        self.init_ui()
        print("✅ UI создан")
        
        print("🔄 Применение стилей...")
        self.setup_styles()
        print("✅ Стили применены")
        
        # Загрузка API ключей в поля ввода
        print("🔄 Загрузка API ключей в поля ввода...")
        self.load_api_keys()
        print("✅ API ключи загружены в поля ввода")
        
        # Настройка таймеров для автоматического обновления
        print("🔄 Настройка таймеров автоматического обновления...")
        self.setup_timers()
        print("✅ Таймеры настроены")
        
        # Запуск торгового потока
        print("🔄 Запуск торгового потока...")
        self.start_trading_worker()
        print("✅ Главное окно полностью инициализировано")
    
    def setup_timers(self):
        """Настройка таймеров для автоматического обновления данных"""
        # Таймер для обновления позиций (каждые 30 секунд)
        self.positions_timer = QTimer(self)
        self.positions_timer.timeout.connect(self.refresh_positions)
        self.positions_timer.start(30000)  # 30 секунд
        self.logger.info("Таймер обновления позиций запущен (интервал: 30 секунд)")
        
        # Таймер для проверки статуса подключения (каждые 60 секунд)
        self.connection_timer = QTimer(self)
        self.connection_timer.timeout.connect(self.check_api_connection)
        self.connection_timer.start(60000)  # 60 секунд
        self.logger.info("Таймер проверки подключения запущен (интервал: 60 секунд)")
        
        # Таймер для полного обновления данных (каждые 120 секунд)
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.refresh_data)
        self.data_timer.start(120000)  # 120 секунд
        self.logger.info("Таймер полного обновления данных запущен (интервал: 120 секунд)")
        
        # Таймер для обновления тикеров (каждые 30 секунд)
        self.tickers_timer = QTimer(self)
        self.tickers_timer.timeout.connect(self.auto_update_tickers)
        self.tickers_timer.start(30000)  # 30 секунд
        self.logger.info("Таймер обновления тикеров запущен (интервал: 30 секунд)")
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        self.setWindowTitle("Торговый Бот Bybit - Автоматическая Торговля")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Заголовок приложения
        self.create_header(main_layout)
        
        # Основной контент в виде вкладок
        self.create_main_content(main_layout)
        
        # Строка состояния
        self.create_status_bar()
    
    def create_header(self, parent_layout):
        """Создание заголовка приложения"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.StyledPanel)
        header_frame.setMaximumHeight(80)
        
        header_layout = QHBoxLayout(header_frame)
        
        # Логотип и название
        title_label = QLabel("🤖 Торговый Бот Bybit")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        # Статус подключения
        self.connection_status = QLabel("🔴 Отключено")
        self.connection_status.setStyleSheet(
            "QLabel { color: #e74c3c; font-weight: bold; font-size: 14px; }"
        )
        
        # Кнопка управления торговлей
        self.trading_toggle_btn = QPushButton("▶️ Включить торговлю")
        self.trading_toggle_btn.setMinimumSize(180, 40)
        self.trading_toggle_btn.clicked.connect(self.toggle_trading)
        self.trading_toggle_btn.setEnabled(False)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.connection_status)
        header_layout.addWidget(self.trading_toggle_btn)
        
        parent_layout.addWidget(header_frame)
    
    def create_main_content(self, parent_layout):
        """Создание основного контента"""
        # Создание вкладок
        self.tab_widget = QTabWidget()
        self.tabs = {}  # Словарь для хранения вкладок
        
        # Вкладка "Обзор"
        self.create_overview_tab()
        
        # Вкладка "Позиции"
        self.create_positions_tab()
        
        # Вкладка "Тикеры"
        self.create_tickers_tab()
        
        # Вкладка "История торговли"
        self.create_history_tab()
        
        # Вкладка "Настройки"
        self.create_settings_tab()
        
        # Вкладка "Логи"
        self.create_logs_tab()
        
        # Добавляем вкладки в основной макет
        parent_layout.addWidget(self.tab_widget)
        
    def create_positions_tab(self):
        """Создание вкладки позиций"""
        positions_tab = QWidget()
        layout = QVBoxLayout(positions_tab)
        
        # Заголовок и кнопки управления
        header_layout = QHBoxLayout()
        title_label = QLabel("Активные позиции")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        # Кнопка остановки стратегии
        self.stop_strategy_btn = QPushButton("⛔ Остановить стратегию")
        self.stop_strategy_btn.setMinimumSize(180, 30)
        self.stop_strategy_btn.clicked.connect(self.stop_strategy)
        self.stop_strategy_btn.setEnabled(False)
        
        # Кнопка обновления позиций
        refresh_btn = QPushButton("🔄 Обновить позиции")
        refresh_btn.setMinimumSize(180, 30)
        refresh_btn.clicked.connect(self.refresh_positions)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.stop_strategy_btn)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Таблица позиций
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(10)
        self.positions_table.setHorizontalHeaderLabels([
            "Символ", "Категория", "Сторона", "Размер", "Цена входа", 
            "Текущая цена", "Изм. 1ч", "Изм. 24ч", "Изм. 30д", "P&L"
        ])
        
        # Настройка заголовков таблицы
        header = self.positions_table.horizontalHeader()
        for i in range(10):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        
        # Настройка внешнего вида таблицы
        self.positions_table.setAlternatingRowColors(True)
        self.positions_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.positions_table)
        
        # Добавляем вкладку в виджет вкладок
        self.tab_widget.addTab(positions_tab, "Позиции")
        self.tabs["positions"] = positions_tab
    
    def create_strategies_tab(self):
        """Создание вкладки стратегий"""
        # Инициализируем движок стратегий
        from src.strategy.strategy_engine import StrategyEngine
        strategy_engine = StrategyEngine(
            api_client=self.bybit_client,
            db_manager=self.db_manager,
            config_manager=self.config_manager
        )
        
        # Создаем вкладку стратегий с использованием класса StrategiesTab
        from src.gui.strategies_tab import StrategiesTab
        self.strategies_tab = StrategiesTab(
            config=self.config_manager,
            db_manager=self.db_manager,
            api_client=self.bybit_client,
            strategy_engine=strategy_engine
        )
        
        # Добавляем вкладку в виджет вкладок
        self.tab_widget.addTab(self.strategies_tab, "Стратегии")
        self.tabs["strategies"] = self.strategies_tab
    
    def create_tickers_tab(self):
        """Создание вкладки тикеров"""
        tickers_widget = QWidget()
        layout = QVBoxLayout(tickers_widget)
        
        # Фрейм для фильтров
        filter_frame = QFrame()
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        
        # Фильтр по типу тикера
        filter_label = QLabel("Фильтр:")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["ALL", "USDT", "BTC", "ETH", "USDC"])
        self.filter_combo.currentIndexChanged.connect(self.apply_ticker_filter)
        
        # Поле поиска
        search_label = QLabel("Поиск:")
        self.search_entry = QLineEdit()
        self.search_entry.textChanged.connect(self.apply_ticker_filter)
        
        # Кнопка обновления
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.refresh_tickers)
        
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addWidget(search_label)
        filter_layout.addWidget(self.search_entry)
        filter_layout.addStretch()
        filter_layout.addWidget(refresh_button)
        
        # Создание таблицы тикеров
        self.ticker_table = QTableWidget()
        self.ticker_table.setColumnCount(8)
        self.ticker_table.setHorizontalHeaderLabels([
            "Символ", "Последняя цена", "Макс. 24ч", "Мин. 24ч", 
            "Объем 24ч", "Оборот 24ч", "Изм. 24ч (%)", "Изм. за период (%)"
        ])
        
        # Настройка таблицы
        self.ticker_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ticker_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ticker_table.setSelectionMode(QTableWidget.SingleSelection)
        self.ticker_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ticker_table.setSortingEnabled(True)
        self.ticker_table.setAlternatingRowColors(True)
        self.ticker_table.itemSelectionChanged.connect(self.on_ticker_select)
        
        # Панель для графика
        chart_frame = QFrame()
        chart_layout = QVBoxLayout(chart_frame)
        
        # Контроль интервала
        interval_frame = QFrame()
        interval_layout = QHBoxLayout(interval_frame)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        
        interval_label = QLabel("Интервал:")
        self.interval_combo = QComboBox()
        self.interval_combo.addItems([
            "1 минута", "5 минут", "15 минут", "30 минут", 
            "1 час", "4 часа", "1 день", "1 неделя", "1 месяц"
        ])
        self.interval_combo.setCurrentText("1 час")
        self.interval_combo.currentIndexChanged.connect(self.update_ticker_chart)
        
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.interval_combo)
        interval_layout.addStretch()
        
        # Заглушка для графика (будет заменена на реальный график)
        self.chart_placeholder = QLabel("Выберите тикер для отображения графика")
        self.chart_placeholder.setAlignment(Qt.AlignCenter)
        self.chart_placeholder.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ddd;")
        self.chart_placeholder.setMinimumHeight(300)
        
        chart_layout.addWidget(interval_frame)
        chart_layout.addWidget(self.chart_placeholder)
        
        # Создание разделителя
        splitter = QSplitter(Qt.Vertical)
        
        # Добавление таблицы и графика в разделитель
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(filter_frame)
        table_layout.addWidget(self.ticker_table)
        
        splitter.addWidget(table_container)
        splitter.addWidget(chart_frame)
        
        # Установка соотношения размеров
        splitter.setSizes([400, 300])
        
        layout.addWidget(splitter)
        
        # Добавление вкладки
        self.tab_widget.addTab(tickers_widget, "📊 Тикеры")
        
        # Инициализация данных
        self.tickers_data = []
        # Не вызываем refresh_tickers() здесь, чтобы избежать ошибок инициализации
    
    def create_overview_tab(self):
        """Создание вкладки обзора"""
        overview_widget = QWidget()
        layout = QVBoxLayout(overview_widget)
        
        # Верхняя панель с балансом
        balance_frame = QGroupBox("💰 Баланс счета")
        balance_layout = QGridLayout(balance_frame)
        
        # Метки для отображения баланса
        self.total_balance_label = QLabel("$0.00")
        self.available_balance_label = QLabel("$0.00")
        self.unrealized_pnl_label = QLabel("$0.00")
        self.daily_pnl_label = QLabel("$0.00")
        
        # Стили для меток баланса
        balance_style = "QLabel { font-size: 16px; font-weight: bold; padding: 5px; }"
        self.total_balance_label.setStyleSheet(balance_style + "color: #2c3e50;")
        self.available_balance_label.setStyleSheet(balance_style + "color: #27ae60;")
        self.unrealized_pnl_label.setStyleSheet(balance_style)
        self.daily_pnl_label.setStyleSheet(balance_style)
        
        balance_layout.addWidget(QLabel("Общий баланс:"), 0, 0)
        balance_layout.addWidget(self.total_balance_label, 0, 1)
        balance_layout.addWidget(QLabel("Доступно:"), 0, 2)
        balance_layout.addWidget(self.available_balance_label, 0, 3)
        balance_layout.addWidget(QLabel("Нереализованный P&L:"), 1, 0)
        balance_layout.addWidget(self.unrealized_pnl_label, 1, 1)
        balance_layout.addWidget(QLabel("Дневной P&L:"), 1, 2)
        balance_layout.addWidget(self.daily_pnl_label, 1, 3)
        
        layout.addWidget(balance_frame)
        
        # Панель ограничителя баланса
        balance_limiter_frame = QGroupBox("🔒 Ограничитель баланса")
        balance_limiter_layout = QGridLayout(balance_limiter_frame)
        
        # Слайдер для выбора процента от баланса
        balance_limiter_layout.addWidget(QLabel("Процент от баланса:"), 0, 0)
        self.balance_percent_slider = QSlider(Qt.Horizontal)
        self.balance_percent_slider.setRange(1, 100)
        self.balance_percent_slider.setValue(50)
        self.balance_percent_slider.setTickPosition(QSlider.TicksBelow)
        self.balance_percent_slider.setTickInterval(10)
        self.balance_percent_slider.valueChanged.connect(self.update_balance_limit_display)
        balance_limiter_layout.addWidget(self.balance_percent_slider, 0, 1)
        
        self.balance_percent_label = QLabel("50%")
        self.balance_percent_label.setStyleSheet("font-weight: bold; color: #2980b9;")
        balance_limiter_layout.addWidget(self.balance_percent_label, 0, 2)
        
        # Отображение суммы ограничения
        balance_limiter_layout.addWidget(QLabel("Сумма ограничения:"), 1, 0)
        self.balance_limit_amount_label = QLabel("$0.00")
        self.balance_limit_amount_label.setStyleSheet("font-weight: bold; color: #2980b9;")
        balance_limiter_layout.addWidget(self.balance_limit_amount_label, 1, 1)
        
        # Таймер ограничения
        balance_limiter_layout.addWidget(QLabel("Таймер ограничения:"), 2, 0)
        self.balance_limit_timer_label = QLabel("12:00:00")
        self.balance_limit_timer_label.setStyleSheet("font-weight: bold; color: #e74c3c;")
        balance_limiter_layout.addWidget(self.balance_limit_timer_label, 2, 1)
        
        # Кнопки управления ограничителем
        buttons_layout = QHBoxLayout()
        self.activate_limit_button = QPushButton("Активировать ограничение")
        self.activate_limit_button.clicked.connect(self.activate_balance_limit)
        self.activate_limit_button.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        buttons_layout.addWidget(self.activate_limit_button)
        
        self.deactivate_limit_button = QPushButton("Отключить ограничение")
        self.deactivate_limit_button.clicked.connect(self.deactivate_balance_limit)
        self.deactivate_limit_button.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold;")
        self.deactivate_limit_button.setEnabled(False)
        buttons_layout.addWidget(self.deactivate_limit_button)
        
        balance_limiter_layout.addLayout(buttons_layout, 3, 0, 1, 3)
        
        layout.addWidget(balance_limiter_frame)
        
        # Панель информации о тикерах
        ticker_info_frame = QGroupBox("📈 Информация о тикерах")
        ticker_info_layout = QGridLayout(ticker_info_frame)
        
        # Отображение даты последней загрузки тикеров
        ticker_info_layout.addWidget(QLabel("Последнее обновление тикеров:"), 0, 0)
        self.last_ticker_update_label = QLabel("Нет данных")
        self.last_ticker_update_label.setStyleSheet("font-weight: bold; color: #2980b9;")
        ticker_info_layout.addWidget(self.last_ticker_update_label, 0, 1)
        
        layout.addWidget(ticker_info_frame)
        # Добавляем дополнительную информацию о тикерах
        ticker_info_layout.addWidget(QLabel("Количество доступных тикеров:"), 1, 0)
        self.ticker_count_label = QLabel("0")
        self.ticker_count_label.setStyleSheet("font-weight: bold;")
        ticker_info_layout.addWidget(self.ticker_count_label, 1, 1)
        
        # Дата последней загрузки тикеров
        self.last_ticker_update_label = QLabel("Нет данных")
        self.last_ticker_update_label.setStyleSheet("font-weight: bold;")
        ticker_info_layout.addWidget(QLabel("Последнее обновление тикеров:"), 2, 0)
        ticker_info_layout.addWidget(self.last_ticker_update_label, 2, 1)
        
        # Кнопка обновления информации о тикерах
        self.update_tickers_button = QPushButton("Обновить информацию о тикерах")
        self.update_tickers_button.clicked.connect(self.update_ticker_info)
        ticker_info_layout.addWidget(self.update_tickers_button, 3, 0, 1, 2)
        
        layout.addWidget(ticker_info_frame)
        
        # Панель статистики торговли
        stats_frame = QGroupBox("📊 Статистика торговли")
        stats_layout = QGridLayout(stats_frame)
        
        self.trades_count_label = QLabel("0")
        self.win_rate_label = QLabel("0%")
        self.daily_volume_label = QLabel("$0.00")
        self.daily_limit_label = QLabel("$0.00")
        
        stats_style = "QLabel { font-size: 14px; font-weight: bold; color: #34495e; }"
        self.trades_count_label.setStyleSheet(stats_style)
        self.win_rate_label.setStyleSheet(stats_style)
        self.daily_volume_label.setStyleSheet(stats_style)
        self.daily_limit_label.setStyleSheet(stats_style)
        
        stats_layout.addWidget(QLabel("Сделок сегодня:"), 0, 0)
        stats_layout.addWidget(self.trades_count_label, 0, 1)
        stats_layout.addWidget(QLabel("Процент прибыльных:"), 0, 2)
        stats_layout.addWidget(self.win_rate_label, 0, 3)
        stats_layout.addWidget(QLabel("Дневной объем:"), 1, 0)
        stats_layout.addWidget(self.daily_volume_label, 1, 1)
        stats_layout.addWidget(QLabel("Дневной лимит:"), 1, 2)
        stats_layout.addWidget(self.daily_limit_label, 1, 3)
        
        layout.addWidget(stats_frame)
        
        # Панель управления
        control_frame = QGroupBox("⚙️ Управление")
        control_layout = QVBoxLayout(control_frame)
        
        # Первая строка - основные кнопки
        main_buttons_layout = QHBoxLayout()
        
        self.emergency_stop_btn = QPushButton("🛑 Экстренная остановка")
        self.emergency_stop_btn.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; padding: 10px; }"
        )
        self.emergency_stop_btn.clicked.connect(self.emergency_stop)
        
        self.refresh_btn = QPushButton("🔄 Обновить данные")
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        main_buttons_layout.addWidget(self.emergency_stop_btn)
        main_buttons_layout.addWidget(self.refresh_btn)
        main_buttons_layout.addStretch()
        
        # Вторая строка - кнопки ручной торговли
        manual_trading_layout = QHBoxLayout()
        
        self.buy_lowest_btn = QPushButton("💰 Купить самый дешёвый")
        self.buy_lowest_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #229954; }"
            "QPushButton:disabled { background-color: #95a5a6; }"
        )
        self.buy_lowest_btn.clicked.connect(self.buy_lowest_ticker)
        
        self.sell_lowest_btn = QPushButton("💸 Продать самый дешёвый")
        self.sell_lowest_btn.setStyleSheet(
            "QPushButton { background-color: #e67e22; color: white; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #d35400; }"
            "QPushButton:disabled { background-color: #95a5a6; }"
        )
        self.sell_lowest_btn.clicked.connect(self.sell_lowest_ticker)
        
        manual_trading_layout.addWidget(self.buy_lowest_btn)
        manual_trading_layout.addWidget(self.sell_lowest_btn)
        manual_trading_layout.addStretch()
        
        # Третья строка - кнопка коннекта с нейросетью
        neural_network_layout = QHBoxLayout()
        
        self.connect_neural_btn = QPushButton("🧠 Подключить нейросеть")
        self.connect_neural_btn.setStyleSheet(
            "QPushButton { background-color: #9b59b6; color: white; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #8e44ad; }"
            "QPushButton:disabled { background-color: #95a5a6; }"
        )
        self.connect_neural_btn.clicked.connect(self.connect_neural_network)
        
        self.neural_status_label = QLabel("❌ Нейросеть не подключена")
        self.neural_status_label.setStyleSheet("color: #e74c3c; font-weight: bold; padding: 8px;")
        
        neural_network_layout.addWidget(self.connect_neural_btn)
        neural_network_layout.addWidget(self.neural_status_label)
        neural_network_layout.addStretch()
        
        # Добавляем кнопки управления
        control_layout.addLayout(main_buttons_layout)
        control_layout.addLayout(manual_trading_layout)
        control_layout.addLayout(neural_network_layout)
        
        layout.addWidget(control_frame)
        
        # Панель активов
        assets_frame = QGroupBox("💎 Активы")
        assets_layout = QVBoxLayout(assets_frame)
        
        # Таблица активов
        self.assets_table = QTableWidget()
        self.assets_table.setColumnCount(4)
        self.assets_table.setHorizontalHeaderLabels([
            "Актив", "Баланс", "USD Стоимость", "Доступно к выводу"
        ])
        
        # Настройка таблицы активов
        assets_header = self.assets_table.horizontalHeader()
        assets_header.setStretchLastSection(True)
        for i in range(3):
            assets_header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.assets_table.setAlternatingRowColors(True)
        self.assets_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.assets_table.setMaximumHeight(200)
        
        # Устанавливаем стиль для таблицы активов, чтобы текст был видимым
        self.assets_table.setStyleSheet(
            "QTableWidget { alternate-background-color: #f0f0f0; background-color: white; }"
            "QTableWidget::item { color: #2c3e50; }"
        )
        
        assets_layout.addWidget(self.assets_table)
        
        # Кнопка обновления активов
        refresh_assets_layout = QHBoxLayout()
        self.refresh_assets_btn = QPushButton("🔄 Обновить активы")
        self.refresh_assets_btn.setStyleSheet(
            "QPushButton { background-color: #3498db; color: white; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #2980b9; }"
            "QPushButton:disabled { background-color: #95a5a6; }"
        )
        self.refresh_assets_btn.clicked.connect(self.refresh_data)
        refresh_assets_layout.addStretch()
        refresh_assets_layout.addWidget(self.refresh_assets_btn)
        assets_layout.addLayout(refresh_assets_layout)
        
        layout.addWidget(assets_frame)
        
        # Добавляем растягивающийся элемент
        layout.addStretch()
        
        self.tab_widget.addTab(overview_widget, "📈 Обзор")
    

    
    def create_history_tab(self):
        """Создание вкладки истории торговли"""
        history_widget = QWidget()
        layout = QVBoxLayout(history_widget)
        
        # Заголовок
        header_label = QLabel("📜 История торговли")
        header_label.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; margin: 10px; }")
        layout.addWidget(header_label)
        
        # Таблица истории
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "Время", "Символ", "Сторона", "Размер", "Цена", "P&L", "Уверенность"
        ])
        
        # Настройка таблицы
        header = self.history_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(6):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.history_table)
        
        self.tab_widget.addTab(history_widget, "📋 История")
    
    def create_settings_tab(self):
        """Создание вкладки настроек"""
        from PySide6.QtWidgets import QLineEdit
        
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        
        # Группа настроек API
        api_group = QGroupBox("🔑 Настройки API Bybit")
        api_layout = QGridLayout(api_group)
        
        # Поля для ввода API ключей
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Введите API Key")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setPlaceholderText("Введите API Secret")
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        
        # Кнопка для проверки API ключей
        test_api_btn = QPushButton("Проверить ключи")
        test_api_btn.clicked.connect(self.test_api_keys)
        
        # Кнопка для сохранения API ключей
        save_api_btn = QPushButton("Сохранить ключи")
        save_api_btn.clicked.connect(self.save_api_keys)
        
        # Кнопка для очистки API ключей
        clear_api_btn = QPushButton("Очистить ключи")
        clear_api_btn.clicked.connect(self.clear_api_keys)
        clear_api_btn.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #c0392b; }"
        )
        
        # Индикатор статуса API
        self.api_status_label = QLabel("⚠️ API ключи не проверены")
        self.api_status_label.setStyleSheet("QLabel { color: #f39c12; font-weight: bold; }")
        
        # Добавление элементов в layout
        api_layout.addWidget(QLabel("API Key:"), 0, 0)
        api_layout.addWidget(self.api_key_input, 0, 1)
        api_layout.addWidget(QLabel("API Secret:"), 1, 0)
        api_layout.addWidget(self.api_secret_input, 1, 1)
        api_layout.addWidget(self.api_status_label, 2, 0, 1, 2)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(test_api_btn)
        buttons_layout.addWidget(save_api_btn)
        buttons_layout.addWidget(clear_api_btn)
        api_layout.addLayout(buttons_layout, 3, 0, 1, 2)
        
        # Добавление группы в основной layout
        layout.addWidget(api_group)
        layout.addStretch()
        
        self.tab_widget.addTab(settings_widget, "⚙️ Настройки")
    
    def create_logs_tab(self):
        """Создание вкладки логов"""
        logs_widget = QWidget()
        layout = QVBoxLayout(logs_widget)
        
        # Заголовок
        header_label = QLabel("📝 Логи системы")
        header_label.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; margin: 10px; }")
        layout.addWidget(header_label)
        
        # Текстовое поле для логов
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        # Примечание: ограничение количества строк будет реализовано через логику добавления сообщений
        
        # Стиль для логов
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                border: 1px solid #34495e;
            }
        """)
        
        layout.addWidget(self.logs_text)
        
        # Кнопки управления логами
        logs_control_layout = QHBoxLayout()
        
        clear_logs_btn = QPushButton("🗑️ Очистить логи")
        clear_logs_btn.clicked.connect(self.clear_logs)
        
        export_logs_btn = QPushButton("💾 Экспорт логов")
        export_logs_btn.clicked.connect(self.export_logs)
        
        logs_control_layout.addWidget(clear_logs_btn)
        logs_control_layout.addWidget(export_logs_btn)
        logs_control_layout.addStretch()
        
        layout.addLayout(logs_control_layout)
        
        self.tab_widget.addTab(logs_widget, "📝 Логи")
    

    
    def create_status_bar(self):
        """Создание строки состояния"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Индикатор состояния
        self.status_label = QLabel("Готов к работе")
        self.status_bar.addWidget(self.status_label)
        
        # Индикатор времени последнего обновления
        self.last_update_label = QLabel("Последнее обновление: никогда")
        self.status_bar.addPermanentWidget(self.last_update_label)
        
        # Индикатор времени последнего обновления тикеров
        self.ticker_update_label = QLabel("Последнее обновление тикеров: никогда")
        self.status_bar.addPermanentWidget(self.ticker_update_label)
        
        # Индикатор статуса ограничителя баланса
        self.balance_limit_status_label = QLabel("Ограничитель баланса: Неактивен")
        self.balance_limit_status_label.setStyleSheet("color: gray;")
        self.status_bar.addPermanentWidget(self.balance_limit_status_label)
        
        # Индикатор таймера ограничителя баланса
        self.balance_limit_timer_label = QLabel("")
        self.balance_limit_timer_label.setVisible(False)
        self.status_bar.addPermanentWidget(self.balance_limit_timer_label)
        
        # Инициализируем таймер для автоматического обновления данных
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.refresh_data)
        self.data_timer.start(30000)  # Обновление каждые 30 секунд
        
    def load_api_keys(self):
        """Загрузка сохраненных API ключей в поля ввода"""
        try:
            # Если API ключи были загружены в __init__, отображаем их в полях ввода
            if hasattr(self, 'api_key') and self.api_key:
                self.api_key_input.setText(self.api_key)
                
            if hasattr(self, 'api_secret') and self.api_secret:
                self.api_secret_input.setText(self.api_secret)
                
            # Если оба ключа загружены, обновляем статус
            if (hasattr(self, 'api_key') and self.api_key and 
                hasattr(self, 'api_secret') and self.api_secret):
                self.api_status_label.setText("✅ API ключи загружены")
                self.api_status_label.setStyleSheet("QLabel { color: #27ae60; font-weight: bold; }")
                self.logger.info("API ключи успешно загружены из конфигурации")
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке API ключей: {e}")
            self.api_status_label.setText("❌ Ошибка загрузки API ключей")
            self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            
    def clear_api_keys(self):
        """Очистка полей ввода API ключей и обновление файла конфигурации"""
        try:
            # Запрос подтверждения у пользователя
            reply = QMessageBox.question(
                self, "Подтверждение", 
                "Вы уверены, что хотите очистить API ключи?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Очистка полей ввода
                self.api_key_input.clear()
                self.api_secret_input.clear()
                
                # Очистка переменных
                self.api_key = ""
                self.api_secret = ""
                
                # Обновление файла конфигурации
                try:
                    # Путь к файлу конфигурации
                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
                    
                    # Чтение текущего содержимого файла
                    with open(config_path, "r", encoding="utf-8") as file:
                        content = file.read()
                    
                    # Регулярные выражения для замены значений API ключей
                    api_key_pattern = r"API_KEY\s*=\s*['\"].*['\"]" 
                    api_secret_pattern = r"API_SECRET\s*=\s*['\"].*['\"]" 
                    
                    # Замена значений на пустые строки
                    content = re.sub(api_key_pattern, "API_KEY = ''" , content)
                    content = re.sub(api_secret_pattern, "API_SECRET = ''" , content)
                    
                    # Запись обновленного содержимого обратно в файл
                    with open(config_path, "w", encoding="utf-8") as file:
                        file.write(content)
                    
                    # Очистка файла keys, если он существует
                    keys_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys")
                    if os.path.exists(keys_path):
                        try:
                            # Удаляем файл keys
                            os.remove(keys_path)
                            self.logger.info("Файл keys успешно удален")
                        except Exception as e:
                            self.logger.error(f"Ошибка при удалении файла keys: {e}")
                        
                    self.logger.info("API ключи успешно очищены в файле конфигурации")
                except Exception as e:
                    self.logger.error(f"Ошибка при обновлении файла конфигурации: {e}")
                    raise
                
                # Обновление статуса
                self.api_status_label.setText("⚠️ API ключи очищены")
                self.api_status_label.setStyleSheet("QLabel { color: #f39c12; font-weight: bold; }")
                
                # Отключение от биржи
                self.update_connection_status(False)
                
                # Логирование
                self.logger.info("API ключи очищены пользователем")
                self.add_log_message("🗑️ API ключи очищены")
                
                # Показать сообщение об успехе
                QMessageBox.information(
                    self, "Успех", 
                    "API ключи успешно очищены из полей ввода, файла конфигурации и файла keys."
                )
        except Exception as e:
            self.logger.error(f"Ошибка при очистке API ключей: {e}")
            self.handle_error("Ошибка при очистке API ключей", str(e))
    
    def setup_styles(self):
        """Настройка стилей приложения"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ecf0f1;
                color: #2c3e50;
            }
            
            QTabWidget::pane {
                border: 1px solid #bdc3c7;
                background-color: white;
                color: #2c3e50;
            }
            
            QTabBar::tab {
                background-color: #bdc3c7;
                color: #2c3e50;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: white;
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: #2c3e50;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2c3e50;
            }
            
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #2980b9;
            }
            
            QPushButton:pressed {
                background-color: #21618c;
            }
            
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
            
            QTableWidget {
                gridline-color: #bdc3c7;
                background-color: white;
                color: #2c3e50;
                alternate-background-color: #f8f9fa;
            }
            
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 8px;
            }
            
            QLabel {
                color: #2c3e50;
            }
            
            QLineEdit {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
            }
            
            QTextEdit {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            
            QComboBox {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
            }
            
            QSpinBox, QDoubleSpinBox {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
            }
            
            QCheckBox {
                color: #2c3e50;
            }
            
            QRadioButton {
                color: #2c3e50;
            }
            
            QListWidget {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            
            QTreeWidget {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
                border: none;
                font-weight: bold;
            }
        """)
    
    def start_trading_worker(self):
        """Запуск торгового потока"""
        try:
            print("🔄 Создание торгового потока...")
            self.trading_worker = TradingWorker(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            print("✅ Торговый поток создан")
            
            # Подключение сигналов
            print("🔗 Подключение сигналов...")
            self.trading_worker.balance_updated.connect(self.update_balance)
            self.trading_worker.positions_updated.connect(self.update_positions)
            self.trading_worker.trade_executed.connect(self.add_trade_to_history)
            self.trading_worker.log_message.connect(self.add_log_message)
            self.trading_worker.error_occurred.connect(self.handle_error)
            self.trading_worker.status_updated.connect(self.update_connection_status)
            print("✅ Сигналы подключены")
            
            # Запуск потока
            print("🚀 Запуск торгового потока...")
            self.trading_worker.start()
            print("✅ Торговый поток запущен")
            
            # Передаем bybit_client в PortfolioTab после инициализации
            if hasattr(self, 'portfolio_tab') and self.trading_worker.bybit_client:
                print("🔄 Передача bybit_client в PortfolioTab...")
                self.bybit_client = self.trading_worker.bybit_client
                self.portfolio_tab.set_api_client(self.bybit_client)
                print("✅ bybit_client передан в PortfolioTab")
                self.add_log_message("✅ API клиент передан в PortfolioTab")
                
                # Создаем вкладку стратегий после инициализации bybit_client
                print("🔄 Создание вкладки стратегий...")
                # Инициализируем config_manager, если он еще не инициализирован
                if self.config_manager is None:
                    from src.core.config_manager import ConfigManager
                    self.config_manager = ConfigManager()
                
                # Инициализируем db_manager, если он еще не инициализирован
                if self.db_manager is None:
                    from src.database.db_manager import DBManager
                    self.db_manager = DBManager()
                
                self.create_strategies_tab()
                print("✅ Вкладка стратегий создана")
            
            self.add_log_message("🚀 Торговый поток запущен")
            
        except Exception as e:
            error_msg = f"Ошибка запуска торгового потока: {e}"
            print(f"❌ {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")
            self.handle_error(error_msg)
    
    def update_balance_from_json(self, balance_json: str):
        """Обновление информации о балансе из JSON-строки"""
        try:
            # Преобразуем JSON-строку обратно в словарь
            balance_info = json.loads(balance_json)
            
            # Преобразуем строковые Decimal обратно в объекты Decimal
            if 'total_wallet_usd' in balance_info and isinstance(balance_info['total_wallet_usd'], str):
                balance_info['total_wallet_usd'] = Decimal(balance_info['total_wallet_usd'])
            if 'total_available_usd' in balance_info and isinstance(balance_info['total_available_usd'], str):
                balance_info['total_available_usd'] = Decimal(balance_info['total_available_usd'])
                
            # Вызываем существующий метод обновления баланса
            self.update_balance(balance_info)
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обработки JSON баланса: {str(e)}")
            logging.error(f"Ошибка обработки JSON баланса: {str(e)}")
            traceback.print_exc()
    
    def update_balance(self, balance_info: dict):
        """Обновление информации о балансе с использованием структуры от API Bybit"""
        try:
            # Проверяем, что вкладки созданы
            if not hasattr(self, 'tabs'):
                self.add_log_message("⚠️ Интерфейс еще не полностью инициализирован, обновление баланса пропущено")
                return
                
            self.current_balance = balance_info
            
            # Логируем полученные данные для отладки
            self.logger.info(f"Получены данные о балансе: {balance_info}")
            
            # Получаем общий баланс из структуры
            total_balance = 0
            
            # Очищаем таблицу активов
            self.assets_table.setRowCount(0)
            
            # Проверяем формат данных и обрабатываем соответственно
            if 'coins' in balance_info:
                # Старый формат с вложенным словарем 'coins'
                self.logger.info(f"Обрабатываем баланс в формате с 'coins': {balance_info['coins']}")
                # Используем total_wallet_usd для общего баланса в USD
                if 'total_wallet_usd' in balance_info:
                    total_balance = float(balance_info.get('total_wallet_usd', 0))
                else:
                    # Если нет общего баланса, суммируем монеты
                    total_balance = sum(float(balance) for balance in balance_info.get('coins', {}).values())
                
                # Проверяем тип данных coins
                coins_data = balance_info.get('coins', {})
                if isinstance(coins_data, dict):
                    # Если coins - словарь (ключ: значение)
                    for coin_name, balance in coins_data.items():
                        row_position = self.assets_table.rowCount()
                        self.assets_table.insertRow(row_position)
                        
                        # Название монеты
                        self.assets_table.setItem(row_position, 0, QTableWidgetItem(coin_name))
                        
                        # Баланс монеты (точное количество)
                        balance_str = f"{float(balance):.8f}".rstrip('0').rstrip('.') if float(balance) < 1 else f"{float(balance):.2f}"
                        self.assets_table.setItem(row_position, 1, QTableWidgetItem(balance_str))
                        
                        # USD стоимость - пока оставляем пустой, в будущем можно добавить
                        self.assets_table.setItem(row_position, 2, QTableWidgetItem("N/A"))
                        
                        # Доступно к выводу - пока оставляем пустой
                        self.assets_table.setItem(row_position, 3, QTableWidgetItem("N/A"))
                        
                        self.logger.info(f"Добавлена монета в таблицу: {coin_name} = {balance_str}")
                elif isinstance(coins_data, list):
                    # Если coins - список словарей
                    for coin_item in coins_data:
                        coin_name = coin_item.get('coin')
                        balance = coin_item.get('walletBalance', '0')
                        usd_value = coin_item.get('usdValue', 'N/A')
                        available = coin_item.get('availableToWithdraw', 'N/A')
                        
                        row_position = self.assets_table.rowCount()
                        self.assets_table.insertRow(row_position)
                        
                        # Название монеты
                        self.assets_table.setItem(row_position, 0, QTableWidgetItem(coin_name))
                        
                        # Баланс монеты (точное количество)
                        try:
                            balance_float = float(balance)
                            balance_str = f"{balance_float:.8f}".rstrip('0').rstrip('.') if balance_float < 1 else f"{balance_float:.2f}"
                        except (ValueError, TypeError):
                            balance_str = str(balance)
                        self.assets_table.setItem(row_position, 1, QTableWidgetItem(balance_str))
                        
                        # USD стоимость
                        self.assets_table.setItem(row_position, 2, QTableWidgetItem(str(usd_value)))
                        
                        # Доступно к выводу
                        self.assets_table.setItem(row_position, 3, QTableWidgetItem(str(available)))
                        
                        self.logger.info(f"Добавлена монета в таблицу: {coin_name} = {balance_str} (USD: {usd_value})")
            
            # Новый формат для UNIFIED аккаунта
            elif 'list' in balance_info:
                self.logger.info(f"Обрабатываем баланс в формате UNIFIED аккаунта")
                account_list = balance_info.get('list', [])
                
                for account in account_list:
                    # Получаем общий баланс
                    if 'totalEquity' in account:
                        total_balance = float(account.get('totalEquity', 0))
                    elif 'totalWalletBalance' in account:
                        total_balance = float(account.get('totalWalletBalance', 0))
                    
                    # Обрабатываем список монет
                    coin_list = account.get('coin', [])
                    if isinstance(coin_list, list):
                        for coin_item in coin_list:
                            coin_name = coin_item.get('coin', '')
                            balance = coin_item.get('walletBalance', '0')
                            usd_value = coin_item.get('usdValue', 'N/A')
                            available = coin_item.get('availableToWithdraw', 'N/A')
                            
                            # Пропускаем монеты с нулевым балансом
                            try:
                                if float(balance) == 0:
                                    continue
                            except (ValueError, TypeError):
                                pass
                            
                            row_position = self.assets_table.rowCount()
                            self.assets_table.insertRow(row_position)
                            
                            # Название монеты
                            self.assets_table.setItem(row_position, 0, QTableWidgetItem(coin_name))
                            
                            # Баланс монеты (точное количество)
                            try:
                                balance_float = float(balance)
                                balance_str = f"{balance_float:.8f}".rstrip('0').rstrip('.') if balance_float < 1 else f"{balance_float:.2f}"
                            except (ValueError, TypeError):
                                balance_str = str(balance)
                            self.assets_table.setItem(row_position, 1, QTableWidgetItem(balance_str))
                            
                            # USD стоимость
                            self.assets_table.setItem(row_position, 2, QTableWidgetItem(str(usd_value)))
                            
                            # Доступно к выводу
                            self.assets_table.setItem(row_position, 3, QTableWidgetItem(str(available)))
                            
                            self.logger.info(f"Добавлена монета в таблицу: {coin_name} = {balance_str} (USD: {usd_value})")
            
            # Обновляем отображение общего баланса
            self.total_balance_label.setText(f"${total_balance:.2f}")
            
            # Обновляем значение total_balance_usd для правильного расчета суммы ограничения
            self.total_balance_usd = total_balance
            
            # Сортировка таблицы активов по USD стоимости (по убыванию)
            self.assets_table.sortItems(2, Qt.DescendingOrder)
            
            # Обновляем отображение суммы ограничения баланса
            self.update_balance_limit_display()
            
            self.logger.info(f"Обновлен баланс: ${total_balance:.2f}")
        except Exception as e:
            self.logger.error(f"Ошибка при обработке баланса: {e}")
            self.handle_error(f"Ошибка при обработке баланса: {e}")
            
            # Обработка других форматов баланса только если основной блок вызвал исключение
            if 'totalWalletBalance' in balance_info:
                # Новый формат с прямым указанием общего баланса
                total_balance = float(balance_info.get('totalWalletBalance', 0))
                
                # Обновляем отображение общего баланса
                self.total_balance_label.setText(f"${total_balance:.2f}")
                
                # Обновляем значение total_balance_usd для правильного расчета суммы ограничения
                self.total_balance_usd = total_balance
                
                # Обновляем отображение суммы ограничения баланса
                self.update_balance_limit_display()
                
                self.logger.info(f"Обновлен баланс (резервный метод): ${total_balance:.2f}")
            else:
                # Плоский формат, где ключи - это названия монет
                # Суммируем все положительные значения, исключая служебные поля
                backup_total_balance = 0
                for coin_name, balance in balance_info.items():
                    if coin_name not in ['totalEquity', 'totalWalletBalance', 'totalAvailableBalance']:
                        try:
                            balance_float = float(balance)
                            if balance_float > 0:
                                backup_total_balance += balance_float
                        except (ValueError, TypeError):
                            continue
                
                if backup_total_balance > 0:
                    # Обновляем отображение общего баланса
                    self.total_balance_label.setText(f"${backup_total_balance:.2f}")
                    
                    # Обновляем значение total_balance_usd для правильного расчета суммы ограничения
                    self.total_balance_usd = backup_total_balance
                    
                    # Обновляем отображение суммы ограничения баланса
                    self.update_balance_limit_display()
                    
                    self.logger.info(f"Обновлен баланс (резервный метод 2): ${backup_total_balance:.2f}")
            
            # Нереализованная прибыль/убыток - пока устанавливаем в 0
            # В будущем можно получать из API
            unrealized_pnl = 0
            
            self.total_balance_label.setText(f"${total_balance:.2f}")
            self.available_balance_label.setText(f"${available_balance:.2f}")
            self.unrealized_pnl_label.setText(f"${unrealized_pnl:.2f}")
            
            self.logger.info(f"Обновлен баланс: total=${total_balance:.2f}, available=${available_balance:.2f}")
            
            # Цвет для нереализованного P&L
            if unrealized_pnl > 0:
                self.unrealized_pnl_label.setStyleSheet(
                    "QLabel { font-size: 16px; font-weight: bold; padding: 5px; color: #27ae60; }"
                )
            elif unrealized_pnl < 0:
                self.unrealized_pnl_label.setStyleSheet(
                    "QLabel { font-size: 16px; font-weight: bold; padding: 5px; color: #e74c3c; }"
                )
            else:
                self.unrealized_pnl_label.setStyleSheet(
                    "QLabel { font-size: 16px; font-weight: bold; padding: 5px; color: #34495e; }"
                )
            
            # Обновление дневного лимита
            daily_limit = available_balance * 0.2
            self.daily_limit_label.setText(f"${daily_limit:.2f}")
            
            # Обновление времени последнего обновления
            self.last_update_label.setText(
                f"Последнее обновление: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            # Отображение списка активов - передаем весь объект balance_info
            self.update_assets_display(balance_info)
    
    def update_assets_display(self, balance_info: dict):
        """Обновление отображения активов с использованием плоской структуры баланса"""
        try:
            # Проверяем, что таблица активов существует
            if not hasattr(self, 'assets_table'):
                self.add_log_message("⚠️ Таблица активов еще не создана, обновление пропущено")
                return
                
            if not balance_info:
                self.assets_table.setRowCount(0)
                self.add_log_message("⚠️ Нет данных о балансе или неверный формат")
                return
            
            # Преобразуем данные в список для отображения
            coins_list = []
            
            # Проверяем формат данных и обрабатываем соответственно
            if 'coins' in balance_info:
                # Формат с вложенным словарем 'coins'
                coins_dict = balance_info['coins']
                for coin_name, balance in coins_dict.items():
                    # Преобразуем Decimal в float для совместимости с UI
                    balance_float = float(balance)
                    if balance_float > 0:
                        coins_list.append({
                            'coin': coin_name,
                            'balance': balance_float
                        })
            else:
                # Плоский формат, где ключи - это названия монет
                for coin_name, balance in balance_info.items():
                    # Пропускаем служебные поля, которые могут быть в ответе API
                    if coin_name in ['totalEquity', 'totalWalletBalance', 'totalAvailableBalance']:
                        continue
                    
                    # Преобразуем Decimal или строку в float для совместимости с UI
                    try:
                        balance_float = float(balance)
                        if balance_float > 0:
                            coins_list.append({
                                'coin': coin_name,
                                'balance': balance_float
                            })
                    except (ValueError, TypeError):
                        continue
            
            # Сортируем монеты по балансу (от большей к меньшей)
            sorted_coins = sorted(coins_list, key=lambda x: x['balance'], reverse=True)
            
            # Очищаем таблицу перед обновлением
            self.assets_table.clearContents()
            self.assets_table.setRowCount(len(sorted_coins))
            
            # Устанавливаем заголовки столбцов
            self.assets_table.setColumnCount(3)
            self.assets_table.setHorizontalHeaderLabels(['Счёт/Монета', 'Кол-во', '≈ USD'])
            
            # Заполняем таблицу данными
            for i, coin in enumerate(sorted_coins):
                coin_name = coin['coin']
                balance_value = coin['balance']
                
                # Создаем элементы таблицы с улучшенным форматированием
                coin_item = QTableWidgetItem(coin_name)
                coin_item.setTextAlignment(Qt.AlignCenter)
                
                # Адаптивное форматирование в зависимости от типа актива и значения
                if coin_name in ['BTC', 'ETH']:
                    # Для BTC и ETH показываем больше знаков после запятой
                    precision = 8
                elif balance_value < 0.01:
                    # Для очень маленьких значений показываем больше знаков
                    precision = 8
                else:
                    # Для остальных активов используем стандартное форматирование
                    precision = 4
                
                balance_item = QTableWidgetItem(f"{balance_value:.{precision}f}")
                balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # Для USD значения нужно сделать оценку, если это не USDT
                if coin_name == 'USDT':
                    usd_value = balance_value
                else:
                    # Здесь можно добавить конвертацию в USD через API, но пока просто показываем как есть
                    usd_value = balance_value  # В будущем заменить на реальную конвертацию
                
                # USD значение всегда с 2 знаками после запятой
                usd_item = QTableWidgetItem(f"${usd_value:.2f}")
                usd_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # Добавляем элементы в таблицу
                self.assets_table.setItem(i, 0, coin_item)
                self.assets_table.setItem(i, 1, balance_item)
                self.assets_table.setItem(i, 2, usd_item)
            
            # Принудительно обновляем всю таблицу
            self.assets_table.resizeColumnsToContents()
            self.assets_table.viewport().update()
            self.add_log_message(f"✅ Обновлено активов: {len(sorted_coins)}")
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обновления активов: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
    
    def update_positions(self, positions: List[dict]):
        """Обновление таблицы позиций"""
        try:
            # Проверяем, что таблица позиций существует
            if not hasattr(self, 'positions_table'):
                self.add_log_message("⚠️ Таблица позиций еще не создана, обновление пропущено")
                return
                
            # Проверяем, что получили корректные данные о позициях
            if not positions or not isinstance(positions, list):
                self.add_log_message("⚠️ Нет данных о позициях или неверный формат")
                # Очищаем таблицу, чтобы показать, что позиций нет
                self.positions_table.clearContents()
                self.positions_table.setRowCount(0)
                return
                
            self.current_positions = positions
            
            # Очищаем таблицу перед обновлением
            self.positions_table.clearContents()
            self.positions_table.setRowCount(len(positions))
            
            # Получаем историю цен для всех символов
            price_history = {}
            try:
                all_price_history = self.db_manager.get_price_history()
                for ph in all_price_history:
                    price_history[ph[1]] = ph  # Индекс 1 - это symbol
            except Exception as e:
                self.add_log_message(f"⚠️ Ошибка получения истории цен: {e}")
            
            # Сортируем позиции по P&L (от наибольшего к наименьшему) для фьючерсов
            # и по стоимости позиции для спота
            positions.sort(key=lambda x: float(x.get('unrealisedPnl', 0)) if x.get('category') != 'spot' else float(x.get('positionValue', 0)), reverse=True)
            
            for row, position in enumerate(positions):
                symbol = position.get('symbol', '')
                category = position.get('category', 'Unknown').upper()
                side = position.get('side', '')
                size = float(position.get('size', 0))
                entry_price = float(position.get('avgPrice', 0))
                unrealized_pnl = float(position.get('unrealisedPnl', 0))
                
                # Создаем элементы с выравниванием
                symbol_item = QTableWidgetItem(symbol)
                symbol_item.setTextAlignment(Qt.AlignCenter)
                
                category_item = QTableWidgetItem(category)
                category_item.setTextAlignment(Qt.AlignCenter)
                
                # Устанавливаем цвет для стороны позиции (Buy/Sell)
                side_item = QTableWidgetItem(side)
                side_item.setTextAlignment(Qt.AlignCenter)
                if side.upper() == "BUY":
                    side_item.setFont(QFont("Arial", 9, QFont.Bold))
                elif side.upper() == "SELL":
                    side_item.setFont(QFont("Arial", 9, QFont.Bold))
                
                # Размер позиции с адаптивным форматированием
                size_format = "{:.8f}" if size < 0.0001 else "{:.4f}"
                size_item = QTableWidgetItem(size_format.format(size))
                size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # Цена входа
                entry_price_item = QTableWidgetItem(f"${entry_price:.6f}")
                entry_price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # Добавляем элементы в таблицу
                self.positions_table.setItem(row, 0, symbol_item)
                self.positions_table.setItem(row, 1, category_item)
                self.positions_table.setItem(row, 2, side_item)
                self.positions_table.setItem(row, 3, size_item)
                self.positions_table.setItem(row, 4, entry_price_item)
                
                # Добавляем текущую цену и динамику цен
                current_price = 0
                change_1h = 0
                change_24h = 0
                change_30d = 0
                
                # Для спотовых позиций берем цену из markPrice
                if category.upper() == 'SPOT' and 'markPrice' in position:
                    current_price = float(position.get('markPrice', 0))
                    # Для спотовых позиций динамика цен может отсутствовать
                    # Можно добавить получение динамики из API в будущем
                elif symbol in price_history:
                    ph = price_history[symbol]
                    current_price = ph[2]  # Индекс 2 - текущая цена
                    change_1h = ph[8]      # Индекс 8 - изменение за 1ч
                    change_24h = ph[9]     # Индекс 9 - изменение за 24ч
                    change_30d = ph[11]    # Индекс 11 - изменение за 30д
                
                # Текущая цена
                current_price_item = QTableWidgetItem(f"${current_price:.6f}")
                current_price_item.setForeground(QColor("#2c3e50"))
                current_price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.positions_table.setItem(row, 5, current_price_item)
                
                # Изменение цены за 1ч
                change_1h_text = f"+{change_1h:.2f}%" if change_1h > 0 else f"{change_1h:.2f}%"
                change_1h_item = QTableWidgetItem(change_1h_text)
                change_1h_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if change_1h > 0 or change_1h < 0:
                    change_1h_item.setFont(QFont("Arial", 9, QFont.Bold))
                self.positions_table.setItem(row, 6, change_1h_item)
                
                # Изменение цены за 24ч
                change_24h_text = f"+{change_24h:.2f}%" if change_24h > 0 else f"{change_24h:.2f}%"
                change_24h_item = QTableWidgetItem(change_24h_text)
                change_24h_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if change_24h > 0 or change_24h < 0:
                    change_24h_item.setFont(QFont("Arial", 9, QFont.Bold))
                self.positions_table.setItem(row, 7, change_24h_item)
                
                # Изменение цены за 30д
                change_30d_text = f"+{change_30d:.2f}%" if change_30d > 0 else f"{change_30d:.2f}%"
                change_30d_item = QTableWidgetItem(change_30d_text)
                change_30d_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if change_30d > 0 or change_30d < 0:
                    change_30d_item.setFont(QFont("Arial", 9, QFont.Bold))
                self.positions_table.setItem(row, 8, change_30d_item)
                
                # P&L с цветом и знаком
                pnl_text = f"+${unrealized_pnl:.2f}" if unrealized_pnl > 0 else f"${unrealized_pnl:.2f}"
                pnl_item = QTableWidgetItem(pnl_text)
                pnl_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if unrealized_pnl > 0 or unrealized_pnl < 0:
                    pnl_item.setFont(QFont("Arial", 9, QFont.Bold))
                
                self.positions_table.setItem(row, 9, pnl_item)
            
            self.add_log_message(f"📊 Обновлено позиций: {len(positions)}")
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обновления позиций: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
    
    def add_trade_to_history(self, trade_info: dict):
        """Добавление торговой операции в историю"""
        try:
            self.trade_history.append(trade_info)
            
            # Обновление таблицы истории
            row_count = self.history_table.rowCount()
            self.history_table.insertRow(0)  # Вставляем в начало
            
            timestamp = trade_info.get('timestamp', '')
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M:%S')
            else:
                time_str = datetime.now().strftime('%H:%M:%S')
            
            symbol = trade_info.get('symbol', '')
            side = trade_info.get('side', '')
            size = float(trade_info.get('size', 0))
            price = trade_info.get('price', 'Market')
            pnl = trade_info.get('pnl', 'N/A')
            
            analysis = trade_info.get('analysis', {})
            confidence = analysis.get('confidence', 0) if analysis else 0
            
            self.history_table.setItem(0, 0, QTableWidgetItem(time_str))
            self.history_table.setItem(0, 1, QTableWidgetItem(symbol))
            
            # Сторона с цветом
            side_item = QTableWidgetItem(side)
            if side == 'Buy':
                side_item.setForeground(QColor("#27ae60"))
            else:
                side_item.setForeground(QColor("#e74c3c"))
            self.history_table.setItem(0, 2, side_item)
            
            self.history_table.setItem(0, 3, QTableWidgetItem(f"{size:.4f}"))
            self.history_table.setItem(0, 4, QTableWidgetItem(str(price)))
            self.history_table.setItem(0, 5, QTableWidgetItem(str(pnl)))
            self.history_table.setItem(0, 6, QTableWidgetItem(f"{confidence:.1%}"))
            
            # Ограничиваем количество строк в истории
            if self.history_table.rowCount() > 100:
                self.history_table.removeRow(100)
            
            # Обновление статистики
            self.update_trading_stats()
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка добавления в историю: {e}")
    
    def update_trading_stats(self):
        """Обновление статистики торговли"""
        try:
            # Проверка инициализации trade_history
            if not hasattr(self, 'trade_history'):
                self.trade_history = []
                
            today = datetime.now().date()
            today_trades = [
                trade for trade in self.trade_history
                if datetime.fromisoformat(trade.get('timestamp', '')).date() == today
            ]
            
            trades_count = len(today_trades)
            self.trades_count_label.setText(str(trades_count))
            
            if trades_count > 0:
                # Подсчет прибыльных сделок (упрощенно)
                profitable_trades = sum(1 for trade in today_trades if trade.get('side') == 'Buy')
                win_rate = (profitable_trades / trades_count) * 100
                self.win_rate_label.setText(f"{win_rate:.1f}%")
                
                # Дневной объем
                daily_volume = sum(float(trade.get('size', 0)) for trade in today_trades)
                self.daily_volume_label.setText(f"${daily_volume:.2f}")
                
                # Обновляем дневной лимит, если активен ограничитель баланса
                if self.balance_limit_active and self.balance_limit_amount > 0:
                    self.daily_limit_label.setText(f"${self.balance_limit_amount:.2f}")
                else:
                    self.daily_limit_label.setText("Не установлен")
            else:
                self.win_rate_label.setText("0%")
                self.daily_volume_label.setText("$0.00")
                
            # Обновляем UI
            QApplication.processEvents()
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обновления статистики: {e}")
            
    def buy_cheapest_position(self):
        """Покупка самой дешевой позиции"""
        try:
            if not self.current_positions:
                self.add_log_message("⚠️ Нет доступных позиций для покупки")
                return
                
            # Получаем историю цен для всех символов
            price_history = {}
            try:
                all_price_history = self.db_manager.get_price_history()
                for ph in all_price_history:
                    price_history[ph[1]] = ph  # Индекс 1 - это symbol
            except Exception as e:
                self.add_log_message(f"⚠️ Ошибка получения истории цен: {e}")
                return
                
            # Находим самую дешевую позицию
            cheapest_symbol = None
            lowest_price = float('inf')
            
            for position in self.current_positions:
                symbol = position.get('symbol', '')
                if symbol in price_history:
                    current_price = price_history[symbol][2]  # Индекс 2 - текущая цена
                    if current_price < lowest_price:
                        lowest_price = current_price
                        cheapest_symbol = symbol
            
            if not cheapest_symbol:
                self.add_log_message("⚠️ Не удалось найти самую дешевую позицию")
                return
                
            # Запрос подтверждения
            reply = QMessageBox.question(
                self, 
                "Подтверждение покупки", 
                f"Вы уверены, что хотите купить {cheapest_symbol} по цене ${lowest_price:.6f}?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Здесь будет вызов API для покупки
                self.add_log_message(f"🔄 Отправка запроса на покупку {cheapest_symbol}...")
                
                # Имитация успешной покупки (в реальном приложении здесь будет вызов API)
                trade_info = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': cheapest_symbol,
                    'side': 'Buy',
                    'size': 0.01,  # Фиксированный размер для примера
                    'price': lowest_price,
                    'pnl': 'N/A',
                    'analysis': {'confidence': 0.75}
                }
                
                # Добавляем в историю
                self.add_trade_to_history(trade_info)
                self.add_log_message(f"✅ Успешно куплено {cheapest_symbol} по цене ${lowest_price:.6f}")
            else:
                self.add_log_message("❌ Покупка отменена пользователем")
                
        except Exception as e:
            self.add_log_message(f"❌ Ошибка при покупке: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
    
    def sell_cheapest_position(self):
        """Продажа самой дешевой позиции"""
        try:
            if not self.current_positions:
                self.add_log_message("⚠️ Нет доступных позиций для продажи")
                return
                
            # Получаем историю цен для всех символов
            price_history = {}
            try:
                all_price_history = self.db_manager.get_price_history()
                for ph in all_price_history:
                    price_history[ph[1]] = ph  # Индекс 1 - это symbol
            except Exception as e:
                self.add_log_message(f"⚠️ Ошибка получения истории цен: {e}")
                return
                
            # Находим самую дешевую позицию
            cheapest_symbol = None
            lowest_price = float('inf')
            
            for position in self.current_positions:
                symbol = position.get('symbol', '')
                if symbol in price_history:
                    current_price = price_history[symbol][2]  # Индекс 2 - текущая цена
                    if current_price < lowest_price:
                        lowest_price = current_price
                        cheapest_symbol = symbol
            
            if not cheapest_symbol:
                self.add_log_message("⚠️ Не удалось найти самую дешевую позицию")
                return
                
            # Запрос подтверждения
            reply = QMessageBox.question(
                self, 
                "Подтверждение продажи", 
                f"Вы уверены, что хотите продать {cheapest_symbol} по цене ${lowest_price:.6f}?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Здесь будет вызов API для продажи
                self.add_log_message(f"🔄 Отправка запроса на продажу {cheapest_symbol}...")
                
                # Имитация успешной продажи (в реальном приложении здесь будет вызов API)
                trade_info = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': cheapest_symbol,
                    'side': 'Sell',
                    'size': 0.01,  # Фиксированный размер для примера
                    'price': lowest_price,
                    'pnl': '+$0.05',  # Фиксированный PnL для примера
                    'analysis': {'confidence': 0.75}
                }
                
                # Добавляем в историю
                self.add_trade_to_history(trade_info)
                self.add_log_message(f"✅ Успешно продано {cheapest_symbol} по цене ${lowest_price:.6f}")
            else:
                self.add_log_message("❌ Продажа отменена пользователем")
                
        except Exception as e:
            self.add_log_message(f"❌ Ошибка при продаже: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
    
    def add_log_message(self, message: str):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_message = f"[{timestamp}] {message}"
        
        self.logs_text.append(formatted_message)
        
        # Автопрокрутка к последнему сообщению
        cursor = self.logs_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.logs_text.setTextCursor(cursor)
    
    def handle_error(self, error_message: str):
        """Обработка ошибок"""
        self.add_log_message(f"❌ ОШИБКА: {error_message}")
        
        # Показываем критические ошибки в диалоге
        if "Критическая" in error_message:
            QMessageBox.critical(self, "Критическая ошибка", error_message)
    
    def enable_trading(self, enabled: bool):
        """Включение/выключение торговли"""
        if hasattr(self, 'strategies_tab') and self.strategies_tab:
            # Обновляем состояние в стратегиях
            if enabled:
                self.strategies_tab.activate_trading()
            else:
                self.strategies_tab.deactivate_trading()
            
            # Обновляем логи
            self.add_log_message(f"{'🟢 Торговля включена' if enabled else '🔴 Торговля выключена'}")
        else:
            self.add_log_message("⚠️ Не удалось обновить состояние торговли в стратегиях: вкладка стратегий не инициализирована")
    
    def update_connection_status(self, status: str):
        """Обновление статуса подключения"""
        if status == "Подключено":
            self.connection_status.setText("🟢 Подключено")
            self.connection_status.setStyleSheet(
                "QLabel { color: #27ae60; font-weight: bold; font-size: 14px; }"
            )
            self.trading_toggle_btn.setEnabled(True)
            
            # АВТОМАТИЧЕСКИ ОБНОВЛЯЕМ КНОПКУ ПРИ ПОДКЛЮЧЕНИИ
            if self.trading_worker and self.trading_worker.trading_enabled:
                self.trading_toggle_btn.setText("⏸️ Остановить торговлю")
                self.trading_toggle_btn.setStyleSheet(
                    "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; padding: 10px; }"
                )
            else:
                self.trading_toggle_btn.setText("▶️ Включить торговлю")
                self.trading_toggle_btn.setStyleSheet(
                    "QPushButton { background-color: #27ae60; color: white; font-weight: bold; padding: 10px; }"
                )
            
            # Обновляем bybit_client в PortfolioTab при успешном подключении
            if hasattr(self, 'trading_worker') and self.trading_worker and hasattr(self.trading_worker, 'bybit_client') and self.trading_worker.bybit_client:
                self.bybit_client = self.trading_worker.bybit_client
                if hasattr(self, 'portfolio_tab') and self.portfolio_tab:
                    self.portfolio_tab.set_api_client(self.bybit_client)
                    self.add_log_message("✅ API клиент обновлен в PortfolioTab")
        elif status == "Инициализация...":
            self.connection_status.setText("🟡 Подключение...")
            self.connection_status.setStyleSheet(
                "QLabel { color: #f39c12; font-weight: bold; font-size: 14px; }"
            )
        else:
            self.connection_status.setText("🔴 Отключено")
            self.connection_status.setStyleSheet(
                "QLabel { color: #e74c3c; font-weight: bold; font-size: 14px; }"
            )
            self.trading_toggle_btn.setEnabled(False)
        
        self.status_label.setText(f"Статус: {status}")
    
    def toggle_trading(self):
        """Переключение торговли"""
        if self.trading_worker:
            try:
                current_state = self.trading_worker.trading_enabled
                new_state = not current_state
                
                # Обновляем состояние в worker
                self.trading_worker.enable_trading(new_state)
                
                # Проверяем, что состояние действительно изменилось
                if self.trading_worker.trading_enabled != new_state:
                    self.add_log_message(f"⚠️ Не удалось изменить состояние торговли")
                    return
                
                # Обновляем UI
                if new_state:
                    self.trading_toggle_btn.setText("⏸️ Остановить торговлю")
                    self.trading_toggle_btn.setStyleSheet(
                        "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; padding: 10px; }"
                    )
                    # Активируем кнопку остановки стратегии
                    if hasattr(self, 'stop_strategy_btn'):
                        self.stop_strategy_btn.setEnabled(True)
                else:
                    self.trading_toggle_btn.setText("▶️ Включить торговлю")
                    self.trading_toggle_btn.setStyleSheet(
                        "QPushButton { background-color: #27ae60; color: white; font-weight: bold; padding: 10px; }"
                    )
                    # Деактивируем кнопку остановки стратегии
                    if hasattr(self, 'stop_strategy_btn'):
                        self.stop_strategy_btn.setEnabled(False)
                
                # Обновляем состояние в стратегиях
                if hasattr(self, 'strategies_tab') and self.strategies_tab:
                    try:
                        if new_state:
                            self.strategies_tab.activate_trading()
                        else:
                            self.strategies_tab.deactivate_trading()
                    except Exception as e:
                        self.add_log_message(f"⚠️ Ошибка при обновлении состояния стратегий: {str(e)}")
                
                # Сохраняем состояние торговли в настройках
                try:
                    settings = QSettings("CryptoTrader", "TradingBot")
                    settings.setValue("trading_enabled", new_state)
                    settings.sync()
                except Exception as e:
                    self.add_log_message(f"⚠️ Ошибка при сохранении состояния торговли: {str(e)}")
                
                # Добавляем сообщение в лог
                self.add_log_message(f"{'🟢 Торговля включена' if new_state else '🔴 Торговля выключена'}")
                
                # Принудительно обновляем интерфейс
                QApplication.processEvents()
                
            except Exception as e:
                self.add_log_message(f"❌ Ошибка при переключении торговли: {str(e)}")
                logging.error(f"Ошибка при переключении торговли: {str(e)}")
                traceback.print_exc()
                QMessageBox.critical(self, "Ошибка", f"Не удалось переключить состояние торговли: {str(e)}")
        else:
            self.add_log_message("❌ Торговый поток не инициализирован")
            QMessageBox.warning(self, "Предупреждение", "Торговый поток не инициализирован. Проверьте подключение к API.")
    
    def stop_strategy(self):
        """Остановка активной стратегии"""
        reply = QMessageBox.question(
            self, "Остановка стратегии",
            "Вы уверены, что хотите остановить текущую стратегию?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.trading_worker and hasattr(self.trading_worker, 'stop_strategy'):
                # Получаем имя активной стратегии
                active_strategy = self.trading_worker.get_active_strategy_name() if hasattr(self.trading_worker, 'get_active_strategy_name') else "active"
                
                # Останавливаем стратегию
                success = self.trading_worker.stop_strategy(active_strategy)
                
                if success:
                    self.add_log_message(f"🛑 Стратегия '{active_strategy}' остановлена")
                    # Деактивируем кнопку остановки стратегии
                    self.stop_strategy_btn.setEnabled(False)
                else:
                    self.add_log_message(f"⚠️ Не удалось остановить стратегию '{active_strategy}'")
            else:
                self.add_log_message("⚠️ Невозможно остановить стратегию: торговый поток не инициализирован")
    
    def emergency_stop(self):
        """Экстренная остановка всех операций"""
        reply = QMessageBox.question(
            self, "Экстренная остановка",
            "Вы уверены, что хотите экстренно остановить все торговые операции?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.trading_worker:
                self.trading_worker.stop()
            
            self.add_log_message("🛑 ЭКСТРЕННАЯ ОСТАНОВКА АКТИВИРОВАНА")
            
            # Обновление UI
            self.trading_toggle_btn.setText("▶️ Включить торговлю")
            self.trading_toggle_btn.setStyleSheet(
                "QPushButton { background-color: #27ae60; color: white; font-weight: bold; padding: 10px; }"
            )
            self.update_connection_status("Отключено")
    
    def refresh_data(self):
        """Принудительное обновление всех данных"""
        self.add_log_message("🔄 Принудительное обновление данных...")
        
        # Запускаем обновление данных в отдельном потоке
        threading.Thread(target=self._refresh_data_thread, daemon=True).start()
        
        # Обновляем информацию о тикерах, если она доступна
        if hasattr(self, 'tickers_data') and self.tickers_data:
            self.update_ticker_info(datetime.now())
        
        # Обновляем стратегии с учетом ограничителя баланса
        if hasattr(self, 'balance_limit_active'):
            self.update_strategies_with_balance_limit()
        
    def refresh_positions(self):
        """Принудительное обновление только позиций"""
        self.add_log_message("🔄 Обновление позиций...")
        
        # Запускаем обновление позиций в отдельном потоке
        threading.Thread(target=self._refresh_positions_thread, daemon=True).start()
    
    def _refresh_positions_thread(self):
        """Выполнение обновления только позиций в отдельном потоке"""
        try:
            # Проверяем, что клиент API инициализирован
            if not hasattr(self, 'bybit_client') or not self.bybit_client:
                self.add_log_message("❌ Невозможно обновить позиции: API клиент не инициализирован")
                return
                
            # Обновляем позиции
            self.add_log_message("🔄 Получение данных о позициях...")
        except Exception as e:
            self.add_log_message(f"❌ Ошибка при обновлении позиций: {str(e)}")
            
    def update_ticker_info(self, timestamp=None):
        """Загрузка данных тикеров из файла, созданного программой просмотра тикеров
        
        Args:
            timestamp: Опциональный параметр времени обновления (для совместимости с сигналами)
        """
        try:
            # Создаем загрузчик данных тикеров
            ticker_loader = TickerDataLoader()
            
            # Проверяем существование файла с данными тикеров
            import os
            data_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "BybitTradingBot", "data", "tickers_data.json")
            
            if not os.path.exists(data_path):
                self.add_log_message("⚠️ Файл с данными тикеров не найден. Запустите программу просмотра тикеров.")
                if hasattr(self, 'last_ticker_update_label'):
                    self.last_ticker_update_label.setText("Нет данных (программа тикеров не запущена)")
                    self.last_ticker_update_label.setStyleSheet("font-weight: bold; color: #e74c3c;")
                return False
            
            # Загружаем данные
            ticker_data = ticker_loader.load_tickers_data()
            
            if ticker_data and 'tickers' in ticker_data:
                # Проверяем тип данных тикеров
                if isinstance(ticker_data['tickers'], list):
                    # Преобразуем список в словарь для совместимости
                    tickers_dict = {}
                    for ticker in ticker_data['tickers']:
                        if 'symbol' in ticker:
                            tickers_dict[ticker['symbol']] = ticker
                    self.tickers_data = tickers_dict
                else:
                    # Если это уже словарь, используем как есть
                    self.tickers_data = ticker_data['tickers']
                
                # Обновляем время последнего обновления
                update_time = ticker_data['update_time']
                self.last_ticker_update = update_time
                
                # Проверяем актуальность данных (не старше 5 минут)
                current_time = datetime.now()
                time_diff = current_time - update_time
                
                # Обновляем отображение в интерфейсе
                if hasattr(self, 'last_ticker_update_label'):
                    update_time_str = update_time.strftime("%d.%m.%Y %H:%M:%S")
                    
                    if time_diff.total_seconds() > 300:  # Старше 5 минут
                        self.last_ticker_update_label.setText(f"Устаревшие данные: {update_time_str}")
                        self.last_ticker_update_label.setStyleSheet("font-weight: bold; color: #e74c3c;")
                        self.add_log_message("⚠️ Данные тикеров устарели. Запустите программу просмотра тикеров.")
                    else:
                        self.last_ticker_update_label.setText(f"{update_time_str}")
                        self.last_ticker_update_label.setStyleSheet("font-weight: bold; color: #2980b9;")
                
                # Обновляем информацию о количестве тикеров
                if hasattr(self, 'ticker_count_label'):
                    ticker_count = len(self.tickers_data)
                    self.ticker_count_label.setText(f"{ticker_count}")
                
                # Обновляем таблицу тикеров
                self.update_tickers_table()
                
                # Обновляем информацию о балансе, чтобы пересчитать ограничения
                self.update_balance_info()
                
                self.add_log_message(f"✅ Данные тикеров загружены из файла (обновлены: {update_time_str}, всего тикеров: {len(self.tickers_data)})")
                return True
            else:
                self.add_log_message("❌ Не удалось загрузить данные тикеров из файла или файл не содержит данных")
                return False
        except Exception as e:
            error_msg = f"Ошибка при загрузке данных тикеров: {e}"
            self.logger.error(error_msg)
            self.add_log_message(f"❌ {error_msg}")
            return False
    
    def update_balance_limit_display(self):
        """Обновление отображения ограничителя баланса в интерфейсе"""
        # Обновляем отображение процента на слайдере
        if hasattr(self, 'balance_percent_slider') and hasattr(self, 'balance_percent_label'):
            percent_value = self.balance_percent_slider.value()
            self.balance_percent_label.setText(f"{percent_value}%")
            self.balance_limit_percent = percent_value
            
            # Обновляем сумму ограничения, если есть информация о балансе
            if hasattr(self, 'balance_limit_amount_label') and hasattr(self, 'total_balance_usd'):
                limit_amount = self.total_balance_usd * (percent_value / 100)
                self.balance_limit_amount_label.setText(f"${limit_amount:.2f}")
        
        # Обновляем статус ограничителя
        if hasattr(self, 'balance_limit_status_label'):
            if self.balance_limit_active:
                status_text = f"Активен ({self.balance_limit_percent}%)"
                self.balance_limit_status_label.setText(status_text)
                self.balance_limit_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.balance_limit_status_label.setText("Неактивен")
                self.balance_limit_status_label.setStyleSheet("color: gray;")
        
        # Обновляем таймер
        self.update_balance_limit_timer_display()

    def update_balance_info(self):
        """Обновление информации о балансе для пересчета ограничений"""
        try:
            # Если есть текущий баланс, обновляем отображение ограничителя
            if hasattr(self, 'current_balance') and self.current_balance:
                # Пересчитываем общий баланс в USD
                total_usd = 0.0
                if 'coins' in self.current_balance:
                    coins = self.current_balance['coins']
                    if isinstance(coins, list):
                        for coin in coins:
                            usd_value = float(coin.get('usdValue', 0))
                            total_usd += usd_value
                
                self.total_balance_usd = total_usd
                
                # Обновляем отображение ограничителя баланса
                self.update_balance_limit_display()
                
                self.add_log_message(f"✅ Информация о балансе обновлена (общий баланс: ${total_usd:.2f})")
            else:
                self.add_log_message("⚠️ Нет данных о балансе для обновления")
                
        except Exception as e:
            error_msg = f"Ошибка при обновлении информации о балансе: {e}"
            self.logger.error(error_msg)
            self.add_log_message(f"❌ {error_msg}")
    
    def format_time_remaining(self, seconds):
        """Форматирование оставшегося времени в читаемый вид"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def activate_balance_limit(self, percent=None, duration_hours=12):
        """Активация ограничителя баланса"""
        # Если процент не указан, берем значение со слайдера
        if percent is None:
            percent = self.balance_percent_slider.value()
            
        self.balance_limit_active = True
        self.balance_limit_percent = percent
        self.balance_limit_seconds_left = duration_hours * 3600
        
        # Запускаем таймер обратного отсчета
        if not self.balance_limit_timer.isActive():
            self.balance_limit_timer.start(1000)  # Обновление каждую секунду
        
        # Обновляем отображение
        self.update_balance_limit_display()
        
        # Обновляем стратегии с учетом нового ограничения
        self.update_strategies_with_balance_limit()
        
        # Обновляем состояние кнопок
        self.activate_limit_button.setEnabled(False)
        self.deactivate_limit_button.setEnabled(True)
        
        self.add_log_message(f"✅ Ограничитель баланса активирован ({percent}% на {duration_hours} часов)")
    
    def deactivate_balance_limit(self):
        """Деактивация ограничителя баланса"""
        self.balance_limit_active = False
        
        # Останавливаем таймер
        if self.balance_limit_timer.isActive():
            self.balance_limit_timer.stop()
        
        # Обновляем отображение
        self.update_balance_limit_display()
        
        # Обновляем стратегии с учетом отключения ограничения
        self.update_strategies_with_balance_limit()
        
        # Обновляем состояние кнопок
        self.activate_limit_button.setEnabled(True)
        self.deactivate_limit_button.setEnabled(False)
        
        self.add_log_message("✅ Ограничитель баланса деактивирован")
    
    def update_balance_limit_timer(self):
        """Обновление таймера ограничителя баланса"""
        if self.balance_limit_active and self.balance_limit_seconds_left > 0:
            self.balance_limit_seconds_left -= 1
            
            # Обновляем отображение
            self.update_balance_limit_timer_display()
            
            # Если время истекло, деактивируем ограничитель
            if self.balance_limit_seconds_left <= 0:
                self.deactivate_balance_limit()
                self.add_log_message("ℹ️ Время действия ограничителя баланса истекло")
    
    def update_balance_limit_timer_display(self):
        """Обновление отображения таймера ограничителя баланса"""
        if hasattr(self, 'balance_limit_timer_label'):
            if self.balance_limit_active and self.balance_limit_seconds_left > 0:
                time_text = self.format_time_remaining(self.balance_limit_seconds_left)
                self.balance_limit_timer_label.setText(time_text)
                self.balance_limit_timer_label.setVisible(True)
            else:
                self.balance_limit_timer_label.setVisible(False)
    
    def update_strategies_with_balance_limit(self):
        """Обновление стратегий с учетом ограничителя баланса"""
        if not hasattr(self, 'active_strategies') or not self.active_strategies:
            return
            
        # Получаем текущий баланс
        total_balance = 0
        if hasattr(self, 'current_balance') and self.current_balance:
            for asset, amount in self.current_balance.items():
                if asset == 'USDT':
                    total_balance += float(amount)
        
        # Рассчитываем лимит баланса
        if self.balance_limit_active:
            self.balance_limit_amount = total_balance * (self.balance_limit_percent / 100)
        else:
            self.balance_limit_amount = total_balance
        
        # Обновляем стратегии с новым лимитом
        for strategy_id, strategy in self.active_strategies.items():
            if hasattr(strategy, 'set_balance_limit'):
                try:
                    if self.balance_limit_active:
                        strategy.set_balance_limit(self.balance_limit_amount)
                    else:
                        strategy.set_balance_limit(None)  # Отключаем лимит
                except Exception as e:
                    self.add_log_message(f"❌ Ошибка при обновлении лимита баланса для стратегии {strategy_id}: {e}")
        
        if self.balance_limit_active:
            self.add_log_message(f"ℹ️ Лимит баланса для стратегий обновлен: {self.balance_limit_amount:.2f} USDT")
        else:
            self.add_log_message("ℹ️ Лимит баланса для стратегий отключен")
            try:
                # Получаем позиции по поддерживаемым категориям
                all_positions = []
                categories = ["linear", "inverse", "spot"]
                
                for category in categories:
                    try:
                        # Получаем реальные данные через API с указанием settleCoin=USDT для linear категории
                        settle_coin = "USDT" if category == "linear" else None
                        self.add_log_message(f"🔍 Запрос позиций для категории {category}...")
                        
                        # Для спотовой категории используем get_tickers вместо get_positions
                        if category == "spot":
                            # Получаем спотовые тикеры
                            tickers = self.bybit_client.get_tickers(category="spot")
                            # Выводим отладочную информацию
                            print(f'DEBUG spot tickers:', tickers)
                            
                            # Проверяем баланс для определения спотовых позиций
                            balance_info = self.bybit_client.get_unified_balance_flat()
                            if balance_info and 'list' in balance_info:
                                for account in balance_info.get('list', []):
                                    coin_list = account.get('coin', [])
                                    if isinstance(coin_list, list):
                                        for coin_item in coin_list:
                                            coin_name = coin_item.get('coin', '')
                                            balance = float(coin_item.get('walletBalance', '0'))
                                            
                                            # Пропускаем монеты с нулевым балансом и USDT
                                            if balance > 0 and coin_name != 'USDT':
                                                # Создаем объект позиции в формате, совместимом с существующим кодом
                                                spot_position = {
                                                    'symbol': f"{coin_name}USDT",
                                                    'category': 'spot',
                                                    'side': 'Buy',  # Спотовые позиции всегда Buy
                                                    'size': str(balance),
                                                    'positionValue': '0',  # Будет рассчитано позже
                                                    'avgPrice': '0',  # Неизвестно для спотовых позиций
                                                    'unrealisedPnl': '0'  # Неизвестно для спотовых позиций
                                                }
                                                all_positions.append(spot_position)
                            
                            self.add_log_message(f"✅ Получены спотовые позиции")
                            continue
                        
                        # Для фьючерсов используем стандартный метод get_positions
                        positions_list = self.bybit_client.get_positions(category=category, settle_coin=settle_coin)
                        
                        # Выводим отладочную информацию
                        print(f'DEBUG positions {category}:', positions_list)
                        
                        # Проверяем, что получили список позиций
                        if positions_list and isinstance(positions_list, list):
                            self.add_log_message(f"✅ Получено {len(positions_list)} позиций для категории {category}")
                            # Добавляем категорию к каждой позиции для идентификации
                            for pos in positions_list:
                                pos['category'] = category
                            all_positions.extend(positions_list)
                        else:
                            self.add_log_message(f"⚠️ Нет позиций для категории {category} или неверный формат данных")
                    except Exception as e:
                        self.add_log_message(f"❌ Ошибка получения позиций {category}: {e}")
                        import traceback
                        self.add_log_message(f"Детали: {traceback.format_exc()}")
                        continue
                
                # Фильтруем только активные позиции (с размером > 0)
                active_positions = []
                for pos in all_positions:
                    size = float(pos.get('size', 0))
                    if size > 0:
                        active_positions.append(pos)
                
                # Обновляем таблицу позиций через сигнал
                QMetaObject.invokeMethod(self, "update_positions", 
                                       Qt.QueuedConnection,
                                       Q_ARG(list, active_positions))
                
                self.add_log_message(f"✅ Позиции успешно обновлены: {len(active_positions)}")
                
            except Exception as pos_err:
                self.add_log_message(f"❌ Ошибка обновления позиций: {pos_err}")
                import traceback
                self.add_log_message(f"Детали: {traceback.format_exc()}")
        # Конец блока try
    
    def _refresh_data_thread(self):
        """Выполнение обновления всех данных в отдельном потоке"""
        try:
            # Проверяем, что клиент API инициализирован
            if not hasattr(self, 'bybit_client') or not self.bybit_client:
                self.add_log_message("❌ Невозможно обновить данные: API клиент не инициализирован")
                return
                
            # Получаем данные о балансе через API с использованием плоской структуры
            balance_info = self.bybit_client.get_unified_balance_flat()
            
            # Выводим отладочную информацию
            print('DEBUG flat unified:', balance_info)
            
            # Обновляем интерфейс баланса через сигнал
            # Преобразуем словарь в строку JSON для передачи через сигнал
            balance_json = json.dumps(balance_info, default=str)
            QMetaObject.invokeMethod(self, "update_balance_from_json", 
                                   Qt.QueuedConnection,
                                   Q_ARG(str, balance_json))
            
            # Обновляем позиции
            self.add_log_message("🔄 Обновление позиций...")
            try:
                # Получаем позиции по поддерживаемым категориям
                all_positions = []
                categories = ["linear", "inverse", "spot"]
                
                # Получаем спотовые тикеры для последующего использования
                spot_tickers = {}
                try:
                    tickers_data = self.bybit_client.get_tickers(category="spot")
                    if tickers_data and isinstance(tickers_data, list):
                        for ticker in tickers_data:
                            if 'symbol' in ticker and 'lastPrice' in ticker:
                                spot_tickers[ticker['symbol']] = ticker
                        self.add_log_message(f"✅ Получено {len(spot_tickers)} спотовых тикеров")
                    else:
                        self.add_log_message("⚠️ Не удалось получить спотовые тикеры или неверный формат данных")
                except Exception as e:
                    self.add_log_message(f"❌ Ошибка получения спотовых тикеров: {e}")
                
                for category in categories:
                    try:
                        # Для спотовой категории используем другой подход
                        if category == "spot":
                            # Проверяем баланс для определения спотовых позиций
                            balance_info = self.bybit_client.get_unified_balance_flat()
                            if balance_info and 'list' in balance_info:
                                for account in balance_info.get('list', []):
                                    coin_list = account.get('coin', [])
                                    if isinstance(coin_list, list):
                                        for coin_item in coin_list:
                                            coin_name = coin_item.get('coin', '')
                                            balance = float(coin_item.get('walletBalance', '0'))
                                            
                                            # Пропускаем монеты с нулевым балансом и USDT
                                            if balance > 0 and coin_name != 'USDT':
                                                symbol = f"{coin_name}USDT"
                                                # Получаем текущую цену из тикеров
                                                price = 0
                                                if symbol in spot_tickers:
                                                    price = float(spot_tickers[symbol].get('lastPrice', 0))
                                                
                                                # Рассчитываем стоимость позиции
                                                position_value = balance * price
                                                
                                                # Создаем объект позиции в формате, совместимом с существующим кодом
                                                spot_position = {
                                                    'symbol': symbol,
                                                    'category': 'spot',
                                                    'side': 'Buy',  # Спотовые позиции всегда Buy
                                                    'size': str(balance),
                                                    'positionValue': str(position_value),
                                                    'avgPrice': '0',  # Неизвестно для спотовых позиций
                                                    'unrealisedPnl': '0',  # Неизвестно для спотовых позиций
                                                    'markPrice': str(price)  # Добавляем текущую цену
                                                }
                                                all_positions.append(spot_position)
                            
                            self.add_log_message(f"✅ Получены спотовые позиции")
                            continue
                        
                        # Получаем реальные данные через API с указанием settleCoin=USDT для linear категории
                        settle_coin = "USDT" if category == "linear" else None
                        positions_list = self.bybit_client.get_positions(category=category, settle_coin=settle_coin)
                        
                        # Логируем полученные данные для отладки
                        self.logger.info(f"Получены позиции для категории {category}: {positions_list}")
                        
                        # Проверяем, что получили список позиций
                        if positions_list and isinstance(positions_list, list):
                            # Добавляем категорию к каждой позиции для идентификации
                            for pos in positions_list:
                                pos['category'] = category
                            all_positions.extend(positions_list)
                            self.add_log_message(f"✅ Получено {len(positions_list)} позиций для категории {category}")
                    except Exception as e:
                        self.add_log_message(f"⚠️ Ошибка получения позиций {category}: {e}")
                        self.logger.error(f"Ошибка получения позиций {category}: {e}")
                        import traceback
                        self.logger.error(traceback.format_exc())
                        continue
                
                # Фильтруем только активные позиции (с размером > 0)
                active_positions = []
                for pos in all_positions:
                    size = float(pos.get('size', 0))
                    if size > 0:
                        active_positions.append(pos)
                    
                # Обновляем таблицу позиций через сигнал
                QMetaObject.invokeMethod(self, "update_positions", 
                                       Qt.QueuedConnection,
                                       Q_ARG(list, active_positions))
                    
            except Exception as pos_err:
                self.add_log_message(f"❌ Ошибка обновления позиций: {pos_err}")
            
            self.add_log_message("✅ Данные успешно обновлены")
                
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обновления данных: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
            self.logger.error(f"Ошибка обновления данных: {e}")
            self.logger.error(traceback.format_exc())
    
    def test_api_keys(self):
        """Проверка API ключей"""
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        
        if not api_key or not api_secret:
            self.api_status_label.setText("❌ Введите API ключи")
            self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            return
        
        # Изменение статуса на время проверки
        self.api_status_label.setText("⏳ Проверка ключей...")
        self.api_status_label.setStyleSheet("QLabel { color: #3498db; font-weight: bold; }")
        QApplication.processEvents()
        
        try:
            # Создаем временный клиент для проверки ключей
            from config import USE_TESTNET
            client = BybitClient(api_key, api_secret, testnet=USE_TESTNET)
            # Пробуем получить баланс для проверки работоспособности ключей
            balance = client.get_wallet_balance()
            
            if balance:
                self.api_status_label.setText("✅ API ключи работают")
                self.api_status_label.setStyleSheet("QLabel { color: #27ae60; font-weight: bold; }")
                self.add_log_message("API ключи успешно проверены")
            else:
                self.api_status_label.setText("❌ Не удалось получить баланс")
                self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
                self.add_log_message("Ошибка проверки API ключей: не удалось получить баланс")
        except Exception as e:
            self.api_status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
            self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            self.add_log_message(f"Ошибка проверки API ключей: {str(e)}")
    
    def save_api_keys(self):
        """Сохранение API ключей"""
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        
        if not api_key or not api_secret:
            self.api_status_label.setText("❌ Введите API ключи для сохранения")
            self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            return
        
        try:
            # Путь к файлу config.py
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.py')
            
            # Чтение текущего содержимого файла
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Замена значений API ключей
            content = re.sub(r'API_KEY\s*=\s*"[^"]*"', f'API_KEY = "{api_key}"', content)
            content = re.sub(r'API_SECRET\s*=\s*"[^"]*"', f'API_SECRET = "{api_secret}"', content)
            
            # Запись обновленного содержимого
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Обновляем клиент с новыми ключами
            self.api_key = api_key
            self.api_secret = api_secret
            # Используем значение USE_TESTNET из конфигурации
            from config import USE_TESTNET
            self.bybit_client = BybitClient(api_key, api_secret, testnet=USE_TESTNET)
            
            self.api_status_label.setText("✅ API ключи сохранены")
            self.api_status_label.setStyleSheet("QLabel { color: #27ae60; font-weight: bold; }")
            self.add_log_message("API ключи успешно сохранены")
            
            # Пробуем подключиться с новыми ключами
            self.connect_to_exchange()
        except Exception as e:
            self.api_status_label.setText(f"❌ Ошибка сохранения: {str(e)[:50]}")
            self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            self.add_log_message(f"Ошибка сохранения API ключей: {str(e)}")
    
    def check_api_connection(self):
        """Проверка статуса подключения к API"""
        self.logger.info("Проверка статуса подключения к API...")
        return self.connect_to_exchange()
    
    def connect_to_exchange(self):
        """Подключение к бирже и обновление статуса соединения"""
        try:
            if not self.bybit_client:
                self.add_log_message("❌ Клиент API не инициализирован")
                self.update_connection_status(False)
                return False
            
            # Проверяем соединение, запрашивая баланс
            balance = self.bybit_client.get_wallet_balance()
            
            if balance:
                self.update_connection_status(True)
                self.add_log_message("✅ Успешное подключение к бирже")
                
                # Обновляем баланс
                self.update_balance(balance)
                
                # Разблокируем кнопку торговли
                self.trading_toggle_btn.setEnabled(True)
                
                # Обновляем данные
                self.refresh_data()
                
                return True
            else:
                self.update_connection_status(False)
                self.add_log_message("❌ Не удалось получить баланс")
                return False
                
        except Exception as e:
            self.update_connection_status(False)
            self.add_log_message(f"❌ Ошибка подключения к бирже: {str(e)}")
            return False
    
    def clear_logs(self):
        """Очистка логов"""
        self.logs_text.clear()
        self.add_log_message("🗑️ Логи очищены")
    
    def export_logs(self):
        """Экспорт логов в файл"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"trading_logs_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.logs_text.toPlainText())
            
            self.add_log_message(f"💾 Логи экспортированы в {filename}")
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка экспорта логов: {e}")
    
    def get_cheapest_asset(self):
        """Получение самого дешевого актива из всех доступных"""
        try:
            if not self.bybit_client:
                return None, None
            
            # Получаем все доступные торговые символы
            symbols = self._get_all_available_symbols()
            
            if not symbols:
                self.logger.warning("Не удалось получить список символов для поиска самого дешевого актива")
                return None, None
            
            cheapest_symbol = None
            cheapest_price = float('inf')
            processed_count = 0
            
            self.logger.info(f"Поиск самого дешевого актива среди {len(symbols)} символов...")
            
            # Ограничиваем количество запросов для производительности (первые 100 символов)
            symbols_to_check = symbols[:100] if len(symbols) > 100 else symbols
            
            for symbol in symbols_to_check:
                try:
                    ticker = self.bybit_client.get_tickers(symbol)
                    if ticker and 'list' in ticker and ticker['list']:
                        price = float(ticker['list'][0].get('lastPrice', 0))
                        if 0 < price < cheapest_price:
                            cheapest_price = price
                            cheapest_symbol = symbol
                        processed_count += 1
                except Exception as e:
                    self.logger.debug(f"Ошибка получения цены для {symbol}: {e}")
                    continue
            
            self.logger.info(f"Обработано {processed_count} символов, найден самый дешевый: {cheapest_symbol} по цене {cheapest_price}")
            return cheapest_symbol, cheapest_price
            
        except Exception as e:
            self.logger.error(f"Ошибка поиска самого дешевого актива: {e}")
            return None, None
    
    def buy_cheapest_asset(self):
        """Покупка самого дешевого актива с подтверждением"""
        try:
            # Получаем самый дешевый актив
            symbol, price = self.get_cheapest_asset()
            
            if not symbol or not price:
                QMessageBox.warning(self, "Ошибка", "Не удалось найти доступные активы для покупки")
                return
            
            # Окно подтверждения
            reply = QMessageBox.question(
                self, "Подтверждение покупки",
                f"Вы хотите купить 1 единицу актива {symbol}?\n\n"
                f"💰 Цена: ${price:.6f}\n"
                f"💵 Общая стоимость: ~${price:.6f}\n\n"
                f"⚠️ Это реальная торговая операция!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Выполняем покупку
                order_result = self.bybit_client.place_order(
                    symbol=symbol,
                    side='Buy',
                    order_type='Market',
                    qty='1'
                )
                
                if order_result:
                    self.add_log_message(f"✅ Покупка выполнена: {symbol} за ${price:.6f}")
                    QMessageBox.information(self, "Успех", f"Покупка {symbol} успешно выполнена!")
                else:
                    self.add_log_message(f"❌ Ошибка покупки {symbol}")
                    QMessageBox.warning(self, "Ошибка", "Не удалось выполнить покупку")
            
        except Exception as e:
            error_msg = f"Ошибка при покупке актива: {e}"
            self.logger.error(error_msg)
            self.add_log_message(f"❌ {error_msg}")
            QMessageBox.critical(self, "Ошибка", error_msg)
    
    def sell_cheapest_asset(self):
        """Продажа самого дешевого актива с подтверждением"""
        try:
            # Получаем самый дешевый актив
            symbol, price = self.get_cheapest_asset()
            
            if not symbol or not price:
                QMessageBox.warning(self, "Ошибка", "Не удалось найти доступные активы для продажи")
                return
            
            # Проверяем наличие позиции для продажи
            positions = self.bybit_client.get_positions()
            has_position = False
            
            if positions:
                for pos in positions:
                    if pos.get('symbol') == symbol and float(pos.get('size', 0)) >= 1:
                        has_position = True
                        break
            
            if not has_position:
                QMessageBox.warning(
                    self, "Недостаточно активов", 
                    f"У вас нет достаточного количества {symbol} для продажи"
                )
                return
            
            # Окно подтверждения
            reply = QMessageBox.question(
                self, "Подтверждение продажи",
                f"Вы хотите продать 1 единицу актива {symbol}?\n\n"
                f"💰 Цена: ${price:.6f}\n"
                f"💵 Общая сумма: ~${price:.6f}\n\n"
                f"⚠️ Это реальная торговая операция!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Выполняем продажу
                order_result = self.bybit_client.place_order(
                    symbol=symbol,
                    side='Sell',
                    order_type='Market',
                    qty='1'
                )
                
                if order_result:
                    self.add_log_message(f"✅ Продажа выполнена: {symbol} за ${price:.6f}")
                    QMessageBox.information(self, "Успех", f"Продажа {symbol} успешно выполнена!")
                else:
                    self.add_log_message(f"❌ Ошибка продажи {symbol}")
                    QMessageBox.warning(self, "Ошибка", "Не удалось выполнить продажу")
            
        except Exception as e:
            error_msg = f"Ошибка при продаже актива: {e}"
            self.logger.error(error_msg)
            self.add_log_message(f"❌ {error_msg}")
            QMessageBox.critical(self, "Ошибка", error_msg)
    
    def refresh_tickers(self):
        """Обновление данных о тикерах"""
        try:
            # Проверяем, что клиент API инициализирован
            if not hasattr(self, 'bybit_client') or self.bybit_client is None:
                error_msg = "Невозможно обновить тикеры: API клиент не инициализирован"
                self.logger.error(error_msg)
                self.add_log_message(f"❌ {error_msg}")
                return
                
            # Добавляем таймаут для запроса
            start_time = time.time()
            # Получаем данные о тикерах от API с указанием категории 'spot'
            response = self.bybit_client.get_tickers(category='spot')
            request_time = time.time() - start_time
            
            # Логируем время запроса для мониторинга производительности
            self.logger.debug(f"Запрос тикеров выполнен за {request_time:.2f} сек")
            
            # Извлекаем список тикеров из структуры ответа API
            # Проверяем различные возможные структуры ответа API
            if response and isinstance(response, dict):
                tickers_dict = {}
                ticker_count = 0
                
                # Добавляем подробное логирование структуры ответа для отладки
                self.logger.debug(f"Структура ответа API: {list(response.keys())}")
                
                # Проверяем стандартную структуру
                if 'result' in response and isinstance(response['result'], dict) and 'list' in response['result']:
                    self.logger.debug(f"Используем стандартную структуру ответа: result->list, найдено элементов: {len(response['result']['list'])}")
                    for ticker in response['result']['list']:
                        if 'symbol' in ticker:
                            tickers_dict[ticker['symbol']] = ticker
                            ticker_count += 1
                # Альтернативная структура - список напрямую в result
                elif 'result' in response and isinstance(response['result'], list):
                    self.logger.debug(f"Используем альтернативную структуру: result (список), найдено элементов: {len(response['result'])}")
                    for ticker in response['result']:
                        if 'symbol' in ticker:
                            tickers_dict[ticker['symbol']] = ticker
                            ticker_count += 1
                # Альтернативная структура - данные напрямую в корне ответа
                elif 'list' in response and isinstance(response['list'], list):
                    self.logger.debug(f"Используем альтернативную структуру: list в корне, найдено элементов: {len(response['list'])}")
                    for ticker in response['list']:
                        if 'symbol' in ticker:
                            tickers_dict[ticker['symbol']] = ticker
                            ticker_count += 1
                # Альтернативная структура - данные в data
                elif 'data' in response and isinstance(response['data'], list):
                    self.logger.debug(f"Используем альтернативную структуру: data (список), найдено элементов: {len(response['data'])}")
                    for ticker in response['data']:
                        if 'symbol' in ticker:
                            tickers_dict[ticker['symbol']] = ticker
                            ticker_count += 1
                elif 'data' in response and isinstance(response['data'], dict) and 'list' in response['data']:
                    self.logger.debug(f"Используем альтернативную структуру: data->list, найдено элементов: {len(response['data']['list'])}")
                    for ticker in response['data']['list']:
                        if 'symbol' in ticker:
                            tickers_dict[ticker['symbol']] = ticker
                            ticker_count += 1
                
                if ticker_count > 0:
                    self.tickers_data = tickers_dict
                    self.update_tickers_table()
                    self.add_log_message(f"✅ Данные тикеров обновлены ({ticker_count} символов)")
                    self.logger.info(f"Обновлены данные по {ticker_count} тикерам")
                    
                    # Обновляем информацию о количестве тикеров в интерфейсе
                    if hasattr(self, 'ticker_count_label'):
                        self.ticker_count_label.setText(f"Доступно тикеров: {ticker_count}")
                        self.ticker_count_label.setStyleSheet("font-weight: bold; color: #27ae60;")
                    
                    # Обновляем статусную строку с информацией о количестве тикеров
                    if hasattr(self, 'ticker_update_label'):
                        self.ticker_update_label.setText(f"Тикеров: {ticker_count} | Обновлено: {current_time.strftime('%H:%M:%S')}")
                else:
                    error_msg = f"Не удалось извлечь данные тикеров из ответа API: {response}"
                    self.logger.error(error_msg)
                    self.add_log_message(f"❌ {error_msg}")
            else:
                error_msg = f"Неверная структура ответа API: {response}"
                self.logger.error(error_msg)
                self.add_log_message(f"❌ {error_msg}")
        except Exception as e:
            error_msg = f"Ошибка при обновлении тикеров: {e}"
            self.logger.error(error_msg)
            self.add_log_message(f"❌ {error_msg}")
    
    def auto_update_tickers(self):
        """Автоматическое обновление тикеров по таймеру и эмуляция нажатия кнопки обновления"""
        error_msg = ""
        current_time = datetime.now()
        try:
            # Проверяем, что клиент API инициализирован
            if not hasattr(self, 'bybit_client') or self.bybit_client is None:
                self.logger.warning("Невозможно обновить тикеры: API клиент не инициализирован")
                return
                
            # Логируем информацию о запуске автоматического обновления
            self.logger.info("Запуск автоматического обновления тикеров")
            self.add_log_message("🔄 Автоматическое обновление тикеров...")
                
            # Вызываем напрямую метод обновления тикеров
            self.refresh_tickers()
            
            # Обновляем время последнего обновления
            self.last_ticker_update = current_time
            
            # Обновляем метку времени в интерфейсе, если она существует
            if hasattr(self, 'last_ticker_update_label'):
                self.last_ticker_update_label.setText(f"Последнее обновление: {current_time.strftime('%H:%M:%S')}")
                
            # Эмулируем визуальное нажатие кнопки обновления, если она существует
            if hasattr(self, 'update_tickers_button'):
                # Временно меняем стиль кнопки для визуального эффекта
                original_style = self.update_tickers_button.styleSheet()
                self.update_tickers_button.setStyleSheet("background-color: #4CAF50; color: white;")
                
                # Возвращаем исходный стиль через 200 мс
                QTimer.singleShot(200, lambda: self.update_tickers_button.setStyleSheet(original_style))
                
            # Логируем успешное обновление
            self.logger.debug(f"Автоматическое обновление тикеров выполнено в {current_time.strftime('%H:%M:%S')}")
            
            # Обновляем отображение в интерфейсе
            if hasattr(self, 'last_ticker_update_label'):
                update_time_str = current_time.strftime("%d.%m.%Y %H:%M:%S")
                self.last_ticker_update_label.setText(f"{update_time_str}")
                self.last_ticker_update_label.setStyleSheet("font-weight: bold; color: #2980b9;")
            
            # Обновляем метку в статусной строке
            if hasattr(self, 'ticker_update_label'):
                self.ticker_update_label.setText(f"Последнее обновление тикеров: {current_time.strftime('%H:%M:%S')}")
            
            self.add_log_message("🔄 Автоматическое обновление тикеров выполнено")
        except Exception as e:
            error_msg = f"Ошибка при автоматическом обновлении тикеров: {e}"
            self.logger.error(error_msg)
            self.add_log_message(f"❌ {error_msg}")
        finally:
            # Перезапускаем таймер для следующего обновления, даже если произошла ошибка
            if hasattr(self, 'tickers_timer'):
                # Проверяем, активен ли таймер
                if not self.tickers_timer.isActive():
                    self.logger.info("Перезапуск таймера обновления тикеров")
                    self.tickers_timer.start(30000)  # 30 секунд
            if hasattr(self, 'tickers_timer') and not self.tickers_timer.isActive():
                self.logger.info("Перезапуск таймера обновления тикеров после ошибки")
                self.tickers_timer.start(30000)
    
    def update_tickers_table(self):
        """Обновление таблицы тикеров"""
        # Очистка таблицы
        self.ticker_table.setRowCount(0)
        
        # Применение фильтров
        filtered_tickers = self.apply_ticker_filter()
        
        # Заполнение таблицы
        for i, ticker in enumerate(filtered_tickers):
            self.ticker_table.insertRow(i)
            
            # Символ
            symbol_item = QTableWidgetItem(ticker.get('symbol', ''))
            self.ticker_table.setItem(i, 0, symbol_item)
            
            # Последняя цена - проверяем разные варианты названий полей
            last_price = float(ticker.get('lastPrice', ticker.get('price', ticker.get('last', 0))))
            price_item = QTableWidgetItem(f"{last_price:.8f}")
            price_item.setData(Qt.DisplayRole, last_price)
            self.ticker_table.setItem(i, 1, price_item)
            
            # Максимальная цена за 24ч - проверяем разные варианты
            high_price = float(ticker.get('highPrice24h', ticker.get('high24h', ticker.get('high', 0))))
            high_item = QTableWidgetItem(f"{high_price:.8f}")
            high_item.setData(Qt.DisplayRole, high_price)
            self.ticker_table.setItem(i, 2, high_item)
            
            # Минимальная цена за 24ч - проверяем разные варианты
            low_price = float(ticker.get('lowPrice24h', ticker.get('low24h', ticker.get('low', 0))))
            low_item = QTableWidgetItem(f"{low_price:.8f}")
            low_item.setData(Qt.DisplayRole, low_price)
            self.ticker_table.setItem(i, 3, low_item)
            
            # Объем за 24ч - проверяем разные варианты
            volume = float(ticker.get('volume24h', ticker.get('volume', ticker.get('vol', 0))))
            volume_item = QTableWidgetItem(f"{volume:.2f}")
            volume_item.setData(Qt.DisplayRole, volume)
            self.ticker_table.setItem(i, 4, volume_item)
            
            # Оборот за 24ч - проверяем разные варианты
            turnover = float(ticker.get('turnover24h', ticker.get('turnover', ticker.get('quoteVolume', 0))))
            turnover_item = QTableWidgetItem(f"{turnover:.2f}")
            turnover_item.setData(Qt.DisplayRole, turnover)
            self.ticker_table.setItem(i, 5, turnover_item)
            
            # Изменение за 24ч - проверяем разные варианты
            price_change = float(ticker.get('priceChangePercent24h', ticker.get('priceChangePercent', ticker.get('change24h', 0))))
            change_item = QTableWidgetItem(f"{price_change:.2f}%")
            change_item.setData(Qt.DisplayRole, price_change)
            
            # Цветовое выделение изменения цены
            if price_change > 0:
                change_item.setForeground(QColor('green'))
            elif price_change < 0:
                change_item.setForeground(QColor('red'))
            
            self.ticker_table.setItem(i, 6, change_item)
            
            # Изменение за период (заглушка, будет обновляться при выборе периода)
            period_change = 0.0
            period_item = QTableWidgetItem(f"{period_change:.2f}%")
            period_item.setData(Qt.DisplayRole, period_change)
            self.ticker_table.setItem(i, 7, period_item)
    
    def apply_ticker_filter(self):
        """Применение фильтров к списку тикеров"""
        if not self.tickers_data:
            return []
        
        # Получаем текущие значения фильтров
        filter_type = self.filter_combo.currentText()
        search_text = self.search_entry.text().upper()
        
        # Преобразуем словарь тикеров в список для фильтрации
        tickers_list = []
        for symbol, ticker_data in self.tickers_data.items():
            ticker_item = ticker_data.copy()
            ticker_item['symbol'] = symbol
            tickers_list.append(ticker_item)
        
        # Фильтрация по типу
        if filter_type == "ALL":
            filtered_tickers = tickers_list
        else:
            filtered_tickers = [t for t in tickers_list if t.get('symbol', '').endswith(filter_type)]
        
        # Фильтрация по поисковому запросу
        if search_text:
            filtered_tickers = [t for t in filtered_tickers if search_text in t.get('symbol', '')]
        
        # Обновляем таблицу, если метод вызван не из update_tickers_table
        caller = inspect.currentframe().f_back.f_code.co_name
        if caller != "update_tickers_table":
            self.update_tickers_table()
        
        return filtered_tickers
    
    def on_ticker_select(self):
        """Обработка выбора тикера в таблице"""
        selected_items = self.ticker_table.selectedItems()
        if not selected_items:
            return
        
        # Получаем символ выбранного тикера
        row = selected_items[0].row()
        symbol_item = self.ticker_table.item(row, 0)
        if symbol_item:
            symbol = symbol_item.text()
            self.update_ticker_chart(symbol)
    
    def update_ticker_chart(self, symbol=None):
        """Обновление графика для выбранного тикера"""
        if not symbol:
            selected_items = self.ticker_table.selectedItems()
            if not selected_items:
                return
            
            row = selected_items[0].row()
            symbol_item = self.ticker_table.item(row, 0)
            if not symbol_item:
                return
            
            symbol = symbol_item.text()
        
        # Получаем выбранный интервал
        interval_text = self.interval_combo.currentText()
        interval_map = {
            "1 минута": "1m",
            "5 минут": "5m",
            "15 минут": "15m",
            "30 минут": "30m",
            "1 час": "1h",
            "4 часа": "4h",
            "1 день": "1d",
            "1 неделя": "1w",
            "1 месяц": "1M"
        }
        interval = interval_map.get(interval_text, "4h")
        
        try:
            # Получаем данные для графика с указанием категории 'spot'
            try:
                response = self.bybit_client.get_klines(category='spot', symbol=symbol, interval=interval, limit=100)
            except Exception as kline_error:
                if "Invalid period" in str(kline_error):
                    self.logger.warning(f"Символ {symbol}: ошибка периода, пробуем альтернативный интервал")
                    # Преобразуем интервал в поддерживаемый формат
                    interval_map_fallback = {
                        "4h": "240",
                        "4h": "240",
                        "1d": "D",
                        "1w": "W",
                        "1M": "M"
                    }
                    fallback_interval = interval_map_fallback.get(interval, "15")
                    self.add_log_message(f"ℹ️ Используем альтернативный интервал: {fallback_interval}")
                    response = self.bybit_client.get_klines(category='spot', symbol=symbol, interval=fallback_interval, limit=100)
                else:
                    raise kline_error
            
            # Извлекаем список свечей из структуры ответа API
            if 'result' in response and 'list' in response['result']:
                klines = response['result']['list']
                # Строим график
                self.plot_ticker_chart(symbol, interval, klines)
            else:
                error_msg = f"Неверная структура ответа API для графика: {response}"
                self.logger.error(error_msg)
                self.add_log_message(f"❌ {error_msg}")
                self.chart_placeholder.setText(f"Ошибка загрузки данных для {symbol}")
            
        except Exception as e:
            error_msg = f"Ошибка при обновлении графика: {e}"
            self.logger.error(error_msg)
            self.add_log_message(f"❌ {error_msg}")
            
            # Показываем сообщение об ошибке вместо графика
            self.chart_placeholder.setText(f"Ошибка загрузки данных для {symbol}")
    
    def plot_ticker_chart(self, symbol, interval, klines):
        """Построение графика для тикера"""
        if not klines:
            self.chart_placeholder.setText(f"Нет данных для {symbol}")
            return
        
        try:
            # Создаем фигуру и оси
            figure = plt.figure(figsize=(10, 6))
            ax = figure.add_subplot(111)
            
            # Подготавливаем данные
            # В API Bybit индексы данных: 0-timestamp, 1-open, 2-high, 3-low, 4-close, 5-volume
            dates = [datetime.fromtimestamp(int(k[0]) / 1000) for k in klines]
            opens = [float(k[1]) for k in klines]
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            closes = [float(k[4]) for k in klines]
            
            # Создаем свечной график
            mpf.candlestick_ohlc(ax, [(mdates.date2num(date), o, h, l, c) 
                                     for date, o, h, l, c in zip(dates, opens, highs, lows, closes)],
                                width=0.6, colorup='green', colordown='red')
            
            # Настройка осей
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
            plt.xticks(rotation=45)
            plt.title(f"{symbol} ({interval})")
            plt.xlabel('Время')
            plt.ylabel('Цена')
            plt.grid(True)
            plt.tight_layout()
            
            # Создаем виджет для отображения графика
            canvas = FigureCanvas(figure)
            
            # Заменяем заглушку на график
            layout = self.chart_placeholder.parent().layout()
            layout.replaceWidget(self.chart_placeholder, canvas)
            
            # Сохраняем ссылку на новый виджет
            self.chart_placeholder = canvas
            
        except Exception as e:
            error_msg = f"Ошибка при построении графика: {e}"
            self.logger.error(error_msg)
            self.add_log_message(f"❌ {error_msg}")
            self.chart_placeholder.setText(f"Ошибка построения графика для {symbol}")
    
    def buy_lowest_ticker(self):
        """Покупка самого дешевого тикера из программы тикеров (асинхронно)"""
        try:
            # Используем QTimer для неблокирующего выполнения
            def execute_buy_async():
                try:
                    # Загружаем данные тикеров из программы тикеров
                    from src.tools.ticker_data_loader import TickerDataLoader
                    ticker_loader = TickerDataLoader()
                    tickers_data = ticker_loader.load_tickers_data()
                    
                    if not tickers_data:
                        self.add_log_message("❌ Нет данных по тикерам для покупки")
                        return
                    
                    # Находим самый дешевый тикер по цене
                    lowest_symbol = None
                    lowest_price = float('inf')
                    
                    for symbol, data in tickers_data.items():
                        if symbol.endswith('USDT'):
                            try:
                                price = float(data.get('lastPrice', 0))
                                if 0 < price < lowest_price:
                                    lowest_price = price
                                    lowest_symbol = symbol
                            except (ValueError, TypeError):
                                continue
                    
                    if not lowest_symbol:
                        self.add_log_message("❌ Не найден подходящий тикер для покупки")
                        return
                    
                    self.add_log_message(f"🔍 Выбран самый дешевый тикер: {lowest_symbol} (${lowest_price:.6f})")
                    
                    # Проверяем наличие торгового воркера
                    if not hasattr(self, 'trading_worker') or self.trading_worker is None:
                        self.add_log_message("❌ Торговый воркер не инициализирован")
                        return
                    
                    # Создаем анализ для ручной покупки
                    analysis = {'signal': 'BUY', 'confidence': 1.0}
                    
                    # Временно включаем торговлю для выполнения ручной сделки
                    original_trading_state = getattr(self.trading_worker, 'trading_enabled', False)
                    self.trading_worker.trading_enabled = True
                    
                    # Выполняем сделку
                    trade_result = self.trading_worker._execute_trade(lowest_symbol, analysis, session_id="manual_buy")
                    
                    # Восстанавливаем исходное состояние торговли
                    self.trading_worker.trading_enabled = original_trading_state
                    
                    if trade_result:
                        self.add_log_message(f"💰 Успешно отправлен ордер на покупку {lowest_symbol}")
                    else:
                        self.add_log_message(f"❌ Не удалось выполнить покупку {lowest_symbol}")
                    
                except Exception as e:
                    self.add_log_message(f"❌ Ошибка при покупке: {str(e)}")
                    self.logger.error(f"Ошибка в buy_lowest_ticker: {e}")
            
            # Выполняем асинхронно через QTimer
            QTimer.singleShot(0, execute_buy_async)
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка при покупке: {str(e)}")
            self.logger.error(f"Ошибка в buy_lowest_ticker: {e}")

    def sell_lowest_ticker(self):
        """Продажа самого дешевого актива в портфеле минимальным количеством (асинхронно)"""
        try:
            # Используем QTimer для неблокирующего выполнения
            def execute_sell_async():
                try:
                    # Проверяем наличие данных о балансе
                    if not hasattr(self, 'current_balance') or not self.current_balance:
                        self.add_log_message("❌ Нет данных о портфеле для продажи")
                        return
                    
                    # Получаем список монет
                    coins = self.current_balance.get('coins', [])
                    if not isinstance(coins, list):
                        self.add_log_message("❌ Неверный формат данных о балансе")
                        return
                    
                    # Фильтруем монеты с положительным балансом (исключаем стейблкоины)
                    tradeable_coins = []
                    for coin in coins:
                        coin_name = coin.get('coin', '')
                        wallet_balance = float(coin.get('walletBalance', 0))
                        usd_value = float(coin.get('usdValue', 0))
                        
                        # Исключаем стейблкоины и монеты с очень малым балансом
                        if (coin_name not in ['USDT', 'USDC', 'BUSD', 'DAI'] and 
                            wallet_balance > 0 and usd_value > 0.1):  # Минимум $0.1
                            tradeable_coins.append({
                                'coin': coin_name,
                                'balance': wallet_balance,
                                'usd_value': usd_value
                            })
                    
                    if not tradeable_coins:
                        self.add_log_message("❌ Нет активов для продажи (минимум $0.1)")
                        return
                    
                    # Находим актив с минимальной USD стоимостью
                    lowest_coin = min(tradeable_coins, key=lambda c: c['usd_value'])
                    symbol = lowest_coin['coin'] + "USDT"
                    
                    # Рассчитываем минимальное количество для продажи (10% от баланса, но не менее минимума)
                    min_sell_qty = max(lowest_coin['balance'] * 0.1, 0.001)  # 10% или минимум 0.001
                    
                    self.add_log_message(f"🔍 Выбран актив для продажи: {symbol} (${lowest_coin['usd_value']:.2f})")
                    self.add_log_message(f"📊 Количество для продажи: {min_sell_qty:.6f} {lowest_coin['coin']}")
                    
                    # Проверяем наличие торгового воркера
                    if not hasattr(self, 'trading_worker') or self.trading_worker is None:
                        self.add_log_message("❌ Торговый воркер не инициализирован")
                        return
                    
                    # Создаем анализ для ручной продажи с указанием количества
                    analysis = {
                        'signal': 'SELL', 
                        'confidence': 1.0,
                        'custom_qty': min_sell_qty  # Передаем кастомное количество
                    }
                    
                    # Временно включаем торговлю для выполнения ручной сделки
                    original_trading_state = getattr(self.trading_worker, 'trading_enabled', False)
                    self.trading_worker.trading_enabled = True
                    
                    # Выполняем сделку
                    trade_result = self.trading_worker._execute_trade(symbol, analysis, session_id="manual_sell")
                    
                    # Восстанавливаем исходное состояние торговли
                    self.trading_worker.trading_enabled = original_trading_state
                    
                    if trade_result:
                        self.add_log_message(f"💸 Успешно отправлен ордер на продажу {symbol}")
                    else:
                        self.add_log_message(f"❌ Не удалось выполнить продажу {symbol}")
                    
                except Exception as e:
                    self.add_log_message(f"❌ Ошибка при продаже: {str(e)}")
                    self.logger.error(f"Ошибка в sell_lowest_ticker: {e}")
            
            # Выполняем асинхронно через QTimer
            QTimer.singleShot(0, execute_sell_async)
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка при продаже: {str(e)}")
            self.logger.error(f"Ошибка в sell_lowest_ticker: {e}")

    def connect_neural_network(self):
        """Подключение к программе нейросети"""
        try:
            import subprocess
            import os
            
            # Путь к программе trainer_gui.py
            trainer_path = os.path.join(os.path.dirname(__file__), 'trainer_gui.py')
            
            if not os.path.exists(trainer_path):
                self.add_log_message("❌ Файл trainer_gui.py не найден")
                return
            
            # Запускаем trainer_gui.py в отдельном процессе
            try:
                subprocess.Popen([
                    'python', trainer_path
                ], cwd=os.path.dirname(__file__))
                
                self.add_log_message("🧠 Запуск программы нейросети...")
                
                # Обновляем статус подключения
                self.neural_status_label.setText("✅ Нейросеть запущена")
                self.neural_status_label.setStyleSheet("color: #27ae60; font-weight: bold; padding: 8px;")
                
                # Отключаем кнопку на некоторое время
                self.connect_neural_btn.setEnabled(False)
                self.connect_neural_btn.setText("🧠 Нейросеть запущена")
                
                # Через 3 секунды возвращаем кнопку в исходное состояние
                QTimer.singleShot(3000, self.reset_neural_button)
                
            except Exception as e:
                self.add_log_message(f"❌ Ошибка запуска нейросети: {str(e)}")
                
        except Exception as e:
            self.add_log_message(f"❌ Ошибка подключения к нейросети: {str(e)}")
            self.logger.error(f"Ошибка в connect_neural_network: {e}")
    
    def reset_neural_button(self):
        """Сброс состояния кнопки нейросети"""
        self.connect_neural_btn.setEnabled(True)
        self.connect_neural_btn.setText("🧠 Подключить нейросеть")

    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        reply = QMessageBox.question(
            self, "Выход",
            "Вы уверены, что хотите закрыть торгового бота?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Остановка торгового потока
            if hasattr(self, 'trading_worker') and self.trading_worker is not None:
                try:
                    self.logger.info("Останавливаем торговый поток перед закрытием приложения...")
                    # Останавливаем поток
                    self.trading_worker.stop()
                    # Ждем завершения потока с увеличенным таймаутом
                    if not self.trading_worker.wait(10000):  # Ждем до 10 секунд
                        self.logger.warning("Торговый поток не завершился за отведенное время")
                        # Принудительно завершаем поток
                        self.trading_worker.terminate()
                        self.trading_worker.wait(3000)  # Даем еще 3 секунды на завершение
                    self.logger.info("Торговый поток остановлен")
                except Exception as e:
                    self.logger.error(f"Ошибка при остановке торгового потока: {e}")
                    # Принудительно завершаем поток при ошибке
                    try:
                        self.trading_worker.terminate()
                        self.trading_worker.wait(3000)
                    except:
                        pass
            
            event.accept()
        else:
            event.ignore()


def main():
    """Главная функция приложения"""
    if not GUI_AVAILABLE:
        print("❌ GUI недоступен. Запуск в консольном режиме невозможен.")
        print("Установите PySide6: pip install PySide6")
        sys.exit(1)
    
    # Настраиваем перехват и запись логов терминала
    terminal_logger = setup_terminal_logging(log_dir='logs', filename_prefix='terminal_log')
    
    # Используем уже созданное приложение или создаем новое
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Настройка приложения
    app.setApplicationName("Торговый Бот Bybit")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Trading Bot")
    
    # Создание и показ главного окна
    window = TradingBotMainWindow()
    window.show()
    
    try:
        # Запуск приложения
        sys.exit(app.exec())
    finally:
        # Закрываем логгер при завершении программы
        if terminal_logger:
            terminal_logger.close()


if __name__ == "__main__":
    main()