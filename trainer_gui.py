#!/usr/bin/env python3
"""
GUI приложение для визуализации обучения нейросети
Отдельное приложение для мониторинга и управления процессом обучения ML моделей
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QTableWidget, QTableWidgetItem,
    QTextEdit, QGroupBox, QGridLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QSplitter, QTabWidget, QScrollArea
)
from PySide6.QtCore import QTimer, QThread, Signal, Qt
from PySide6.QtGui import QFont, QColor, QPalette

# Добавляем путь к модулям проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.strategies.adaptive_ml import AdaptiveMLStrategy
    from src.api.bybit_client import BybitClient
    from config import get_api_credentials, get_ml_config
except ImportError as e:
    print(f"Ошибка импорта модулей: {e}")
    print("Убедитесь, что все необходимые модули доступны")


class TrainingWorker(QThread):
    """Поток для обучения моделей в фоновом режиме"""
    progress_updated = Signal(str, int)  # symbol, progress
    status_updated = Signal(str, str, float)  # symbol, status, accuracy
    log_updated = Signal(str)  # log message
    training_completed = Signal()

    def __init__(self, ml_strategy, symbols, symbol_categories=None):
        super().__init__()
        self.ml_strategy = ml_strategy
        self.symbols = symbols
        self.symbol_categories = symbol_categories or {}
        self.is_running = False

    def run(self):
        """Запуск обучения моделей"""
        self.is_running = True
        self.log_updated.emit("🚀 Начинаем обучение моделей...")
        
        # Счетчики для статистики
        total_symbols = len(self.symbols)
        successful_trainings = 0
        failed_trainings = 0
        
        for i, symbol in enumerate(self.symbols):
            if not self.is_running:
                break
                
            try:
                self.log_updated.emit(f"📊 Обучение модели для {symbol} ({i+1}/{total_symbols})...")
                self.progress_updated.emit(symbol, 0)
                
                # Получаем исторические данные с правильной категорией
                category = self.choose_category(symbol)
                klines = []
                
                # Пытаемся получить данные через API с оптимизированной логикой
                try:
                    klines_response = self.ml_strategy.api_client.get_klines(category=category, symbol=symbol, interval='60', limit=1000)
                    if not klines_response or 'list' not in klines_response or not klines_response['list']:
                        # Пробуем альтернативную категорию только если символ поддерживает несколько категорий
                        available_categories = self.symbol_categories.get(symbol, [category])
                        alt_categories = [cat for cat in available_categories if cat != category]
                        
                        if alt_categories:
                            alt_category = alt_categories[0]
                            self.log_updated.emit(f"🔄 Пробуем альтернативную категорию '{alt_category}' для {symbol}")
                            klines_response = self.ml_strategy.api_client.get_klines(category=alt_category, symbol=symbol, interval='60', limit=1000)
                        else:
                            self.log_updated.emit(f"⚠️ Символ {symbol} не поддерживается в других категориях")
                    
                    # Извлекаем данные из ответа API
                    if klines_response and 'list' in klines_response and klines_response['list']:
                        klines_data = klines_response['list']
                        # Преобразуем в нужный формат
                        for kline in klines_data:
                            klines.append({
                                'open': float(kline[1]),
                                'high': float(kline[2]), 
                                'low': float(kline[3]),
                                'close': float(kline[4]),
                                'volume': float(kline[5])
                            })
                        self.log_updated.emit(f"✅ Загружено {len(klines)} свечей для {symbol} через API")
                    else:
                        self.log_updated.emit(f"⚠️ API не вернул данные для {symbol}")
                        
                except Exception as e:
                    error_msg = str(e)
                    if "Category is invalid" in error_msg:
                        self.log_updated.emit(f"⚠️ Неверная категория для {symbol}: API ошибка: {error_msg}")
                    elif "Not supported symbols" in error_msg:
                        self.log_updated.emit(f"⚠️ Символ {symbol} не поддерживается: API ошибка: {error_msg}")
                    elif "Symbol Is Invalid" in error_msg:
                        self.log_updated.emit(f"⚠️ Ошибка API для {symbol}: API ошибка: {error_msg}")
                    else:
                        self.log_updated.emit(f"⚠️ Ошибка API для {symbol}: API ошибка: {error_msg}")
                
                # Если API не дал данных, пытаемся загрузить из TickerDataLoader
                if not klines or len(klines) < 100:
                    try:
                        if hasattr(self.ml_strategy, 'ticker_loader') and self.ml_strategy.ticker_loader:
                            historical_data = self.ml_strategy.ticker_loader.get_historical_data(symbol)
                            if historical_data and len(historical_data) > len(klines):
                                klines = historical_data
                                self.log_updated.emit(f"📁 Загружены данные из кэша для {symbol}: {len(klines)} записей")
                    except Exception as e:
                        self.log_updated.emit(f"⚠️ Ошибка загрузки из кэша для {symbol}: {e}")
                
                self.progress_updated.emit(symbol, 20)
                
                # Проверяем достаточность данных
                min_required = 30  # Уменьшенный минимум для обучения на малых датасетах
                if not klines or len(klines) < min_required:
                    self.status_updated.emit(symbol, f"Мало данных ({len(klines) if klines else 0})", 0.0)
                    self.log_updated.emit(f"⚠️ Недостаточно данных для {symbol}: {len(klines) if klines else 0} < {min_required}")
                    failed_trainings += 1
                    continue
                
                self.progress_updated.emit(symbol, 40)
                
                # Извлекаем признаки и метки с улучшенной логикой
                features, labels = [], []
                window = self.ml_strategy.feature_window
                
                for j in range(window, len(klines) - 1):
                    if not self.is_running:
                        break
                        
                    try:
                        f = self.ml_strategy.extract_features(klines[j-window:j])
                        if f and len(f) > 0:
                            features.append(f)
                            # Создаем метку на основе изменения цены
                            current_price = float(klines[j]['close'])
                            future_price = float(klines[j + 1]['close'])
                            change = (future_price - current_price) / current_price
                            
                            # Адаптивные пороги в зависимости от волатильности
                            volatility = abs(float(klines[j]['high']) - float(klines[j]['low'])) / current_price
                            threshold = max(0.001, volatility * 0.5)  # Минимум 0.1%, максимум зависит от волатильности
                            
                            if change > threshold:
                                labels.append(1)  # рост
                            elif change < -threshold:
                                labels.append(-1)  # падение
                            else:
                                labels.append(0)  # боковик
                    except Exception as e:
                        continue  # Пропускаем проблемные данные
                
                self.progress_updated.emit(symbol, 60)
                
                # Проверяем качество данных
                min_features = 20  # Уменьшенный минимум признаков для обучения на малых датасетах
                if len(features) < min_features:
                    self.status_updated.emit(symbol, f"Мало признаков ({len(features)})", 0.0)
                    self.log_updated.emit(f"⚠️ Недостаточно признаков для {symbol}: {len(features)} < {min_features}")
                    failed_trainings += 1
                    continue
                
                # Проверяем баланс классов
                unique_labels = set(labels)
                if len(unique_labels) < 2:
                    self.status_updated.emit(symbol, "Нет разнообразия меток", 0.0)
                    self.log_updated.emit(f"⚠️ Недостаточное разнообразие меток для {symbol}")
                    failed_trainings += 1
                    continue
                
                self.progress_updated.emit(symbol, 80)
                
                # Обучаем модель
                success = self.ml_strategy.train_model(symbol, features, labels)
                
                if success:
                    # Сохраняем модель
                    try:
                        self.ml_strategy.save_models()
                        
                        # Получаем метрики точности
                        accuracy = self.ml_strategy.performance.get(symbol, {}).get('accuracy', 0.0)
                        samples = self.ml_strategy.performance.get(symbol, {}).get('samples', len(features))
                        
                        self.status_updated.emit(symbol, "Обучена", accuracy)
                        self.log_updated.emit(f"✅ Модель для {symbol} обучена (точность: {accuracy:.2%}, образцов: {samples})")
                        successful_trainings += 1
                        
                    except Exception as e:
                        self.log_updated.emit(f"⚠️ Ошибка сохранения модели для {symbol}: {e}")
                        self.status_updated.emit(symbol, "Ошибка сохранения", 0.0)
                        failed_trainings += 1
                else:
                    self.status_updated.emit(symbol, "Ошибка обучения", 0.0)
                    self.log_updated.emit(f"❌ Ошибка обучения модели для {symbol}")
                    failed_trainings += 1
                
                self.progress_updated.emit(symbol, 100)
                
            except Exception as e:
                self.status_updated.emit(symbol, f"Ошибка: {str(e)[:20]}", 0.0)
                self.log_updated.emit(f"❌ Критическая ошибка при обучении {symbol}: {e}")
                failed_trainings += 1
        
        # Итоговая статистика
        self.log_updated.emit(f"🎉 Обучение завершено!")
        self.log_updated.emit(f"📊 Статистика: успешно {successful_trainings}, ошибок {failed_trainings} из {total_symbols}")
        if successful_trainings > 0:
            success_rate = (successful_trainings / total_symbols) * 100
            self.log_updated.emit(f"📈 Процент успеха: {success_rate:.1f}%")
        
        self.training_completed.emit()

    def stop(self):
        """Остановка обучения"""
        self.is_running = False
        
    def choose_category(self, symbol: str) -> str:
        """Определение категории для символа с использованием предварительной валидации"""
        # Используем информацию из валидации, если доступна
        if symbol in self.symbol_categories:
            categories = self.symbol_categories[symbol]
            if categories:
                # Предпочитаем spot, если доступен
                if 'spot' in categories:
                    return 'spot'
                else:
                    return categories[0]  # Берем первую доступную категорию
        
        # Fallback: простая эвристика
        if symbol.endswith('USDT') and not symbol.endswith('PERP'):
            return 'spot'
        elif symbol.endswith('PERP') or symbol.endswith('USD'):
            return 'linear'
        else:
            return 'spot'


class TrainingMonitor(QMainWindow):
    """Главное окно приложения для мониторинга обучения"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ML Training Monitor - Визуализация обучения нейросети")
        self.setGeometry(100, 100, 1200, 800)

        # Атрибуты состояния обучения
        self.training_in_progress = False
        self.pending_training = False
        self.symbol_progress = {}
        self.expected_symbol_count = 0
        self.last_ticker_file_mtime = None
        self.ticker_data_file = None

        # Инициализация компонентов
        self.init_ml_components()
        self.init_ui()
        self.setup_timers()

        # Загружаем список символов
        self.load_symbols()

    def init_ml_components(self):
        """Инициализация ML компонентов"""
        try:
            # Получаем API credentials
            api_creds = get_api_credentials()
            
            # Инициализируем API клиент
            self.bybit_client = BybitClient(
                api_creds['api_key'],
                api_creds['api_secret'],
                api_creds['testnet']
            )
            
            # Инициализируем TickerDataLoader для кэширования данных
            try:
                from src.tools.ticker_data_loader import TickerDataLoader
                self.ticker_loader = TickerDataLoader()
                self.ticker_data_file = self.ticker_loader.get_data_file_path()
                if self.ticker_data_file.exists():
                    self.last_ticker_file_mtime = self.ticker_data_file.stat().st_mtime
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
            print(f"Ошибка инициализации ML компонентов: {e}")

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        
        # Заголовок
        title_label = QLabel("🤖 ML Training Monitor")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Создаем вкладки
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # Вкладка обучения
        training_tab = self.create_training_tab()
        tab_widget.addTab(training_tab, "🎯 Обучение")
        
        # Вкладка мониторинга
        monitoring_tab = self.create_monitoring_tab()
        tab_widget.addTab(monitoring_tab, "📊 Мониторинг")
        
        # Вкладка настроек
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, "⚙️ Настройки")

    def create_training_tab(self):
        """Создание вкладки обучения"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Панель управления
        control_group = QGroupBox("Управление обучением")
        control_layout = QHBoxLayout(control_group)
        
        self.train_button = QPushButton("🚀 Начать обучение")
        self.train_button.clicked.connect(self.start_training)
        control_layout.addWidget(self.train_button)
        
        self.stop_button = QPushButton("⏹️ Остановить")
        self.stop_button.clicked.connect(self.stop_training)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        
        self.refresh_button = QPushButton("🔄 Обновить")
        self.refresh_button.clicked.connect(self.refresh_data)
        control_layout.addWidget(self.refresh_button)
        
        control_layout.addStretch()
        layout.addWidget(control_group)
        
        # Статус обучения
        status_group = QGroupBox("Статус обучения")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("Готов к обучению")
        status_layout.addWidget(self.status_label)
        
        self.overall_progress = QProgressBar()
        status_layout.addWidget(self.overall_progress)
        
        layout.addWidget(status_group)
        
        # Таблица прогресса по символам
        progress_group = QGroupBox("Прогресс по символам")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_table = QTableWidget(0, 4)
        self.progress_table.setHorizontalHeaderLabels(["Символ", "Прогресс", "Статус", "Точность"])
        self.progress_table.horizontalHeader().setStretchLastSection(True)
        progress_layout.addWidget(self.progress_table)
        
        layout.addWidget(progress_group)
        
        return widget

    def create_monitoring_tab(self):
        """Создание вкладки мониторинга"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Метрики моделей
        metrics_group = QGroupBox("Метрики моделей")
        metrics_layout = QVBoxLayout(metrics_group)
        
        self.metrics_table = QTableWidget(0, 6)
        self.metrics_table.setHorizontalHeaderLabels([
            "Символ", "Точность", "Precision", "Recall", "F1-Score", "Последнее обучение"
        ])
        self.metrics_table.horizontalHeader().setStretchLastSection(True)
        metrics_layout.addWidget(self.metrics_table)
        
        layout.addWidget(metrics_group)
        
        # Логи
        logs_group = QGroupBox("Логи обучения")
        logs_layout = QVBoxLayout(logs_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        logs_layout.addWidget(self.log_text)
        
        layout.addWidget(logs_group)
        
        return widget

    def create_settings_tab(self):
        """Создание вкладки настроек"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Настройки ML
        ml_group = QGroupBox("Настройки машинного обучения")
        ml_layout = QGridLayout(ml_group)
        
        ml_layout.addWidget(QLabel("Feature Window:"), 0, 0)
        self.feature_window_spin = QSpinBox()
        self.feature_window_spin.setRange(5, 100)
        self.feature_window_spin.setValue(15)  # Уменьшенное значение по умолчанию
        ml_layout.addWidget(self.feature_window_spin, 0, 1)
        
        ml_layout.addWidget(QLabel("Confidence Threshold:"), 1, 0)
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.1, 0.9)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setValue(0.65)
        ml_layout.addWidget(self.confidence_spin, 1, 1)
        
        ml_layout.addWidget(QLabel("Model Type:"), 2, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItems(["random_forest", "gradient_boosting", "neural_network"])
        ml_layout.addWidget(self.model_combo, 2, 1)
        
        self.use_indicators_check = QCheckBox("Использовать технические индикаторы")
        self.use_indicators_check.setChecked(True)
        ml_layout.addWidget(self.use_indicators_check, 3, 0, 1, 2)
        
        layout.addWidget(ml_group)
        
        # Настройки символов
        symbols_group = QGroupBox("Символы для обучения")
        symbols_layout = QVBoxLayout(symbols_group)
        
        self.symbols_text = QTextEdit()
        self.symbols_text.setMaximumHeight(100)
        self.symbols_text.setPlainText("BTCUSDT\nETHUSDT\nADAUSDT\nSOLUSDT\nDOTUSDT")
        symbols_layout.addWidget(self.symbols_text)
        
        layout.addWidget(symbols_group)
        
        # Кнопка сохранения настроек
        save_button = QPushButton("💾 Сохранить настройки")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)
        
        layout.addStretch()
        
        return widget

    def setup_timers(self):
        """Настройка таймеров"""
        # Таймер для обновления метрик
        self.metrics_timer = QTimer()
        self.metrics_timer.timeout.connect(self.update_metrics)
        self.metrics_timer.start(5000)  # Обновление каждые 5 секунд

        # Таймер для отслеживания обновлений данных тикеров
        self.ticker_data_timer = QTimer()
        self.ticker_data_timer.timeout.connect(self.check_ticker_data_updates)
        self.ticker_data_timer.start(2000)

    def check_ticker_data_updates(self):
        """Отслеживает появление новых данных тикеров и запускает автообучение."""
        if not self.ticker_loader:
            return

        try:
            data_file = self.ticker_data_file or self.ticker_loader.get_data_file_path()
            if not data_file.exists():
                return

            mtime = data_file.stat().st_mtime
            if self.last_ticker_file_mtime is None or mtime > self.last_ticker_file_mtime:
                self.last_ticker_file_mtime = mtime
                self.log("📥 Обнаружено обновление данных тикеров. Запускаем автоматическое обучение.")
                self.handle_new_ticker_data()
        except Exception as e:
            self.log(f"⚠️ Ошибка отслеживания данных тикеров: {e}")

    def handle_new_ticker_data(self):
        """Загружает свежие тикеры и запускает обучение при необходимости."""
        try:
            if self.ticker_loader:
                self.ticker_loader.load_tickers_data()

            self.load_symbols()

            if not self.symbols:
                self.log("⚠️ Список символов пуст. Автообучение не запущено.")
                return

            if self.training_in_progress:
                self.pending_training = True
                self.log("⏳ Обучение уже выполняется. Перезапуск запланирован после завершения текущей сессии.")
            else:
                self.start_training(auto=True)
        except Exception as e:
            self.log(f"❌ Ошибка автообучения по новым данным: {e}")

    def extract_symbols_from_ticker_data(self, ticker_data) -> List[str]:
        """Извлекает список символов из сохранённых данных тикеров."""
        symbols = []
        suspicious_symbols = []

        if isinstance(ticker_data, dict):
            iterable = ticker_data.items()
        elif isinstance(ticker_data, list):
            iterable = ((entry.get('symbol'), entry) for entry in ticker_data if isinstance(entry, dict))
        else:
            return symbols

        seen = set()
        for symbol, payload in iterable:
            if not symbol or symbol in seen:
                continue

            seen.add(symbol)
            symbols.append(symbol)

            try:
                price = float(payload.get('lastPrice') or payload.get('last_price') or 0)
                volume = float(payload.get('volume') or payload.get('volume24h') or 0)
                if price <= 0 or volume < 0:
                    suspicious_symbols.append(symbol)
            except (TypeError, ValueError):
                suspicious_symbols.append(symbol)

        if suspicious_symbols:
            preview = ', '.join(suspicious_symbols[:10])
            self.log(f"⚠️ Обнаружены подозрительные значения в данных тикеров: {preview}")

        return symbols

    def validate_symbols_with_api(self, symbols: List[str]) -> List[str]:
        """Валидация символов через API Bybit

        Args:
            symbols: Список символов для валидации

        Returns:
            List[str]: Список поддерживаемых символов с информацией о категории
        """
        try:
            self.log("🔍 Валидация символов через API...")
            
            # Получаем поддерживаемые инструменты для разных категорий
            categories = ['spot', 'linear']
            supported_symbols = {}
            symbol_categories = {}

            for category in categories:
                try:
                    instruments = self.ml_strategy.api_client.get_instruments_info(category=category)
                    if instruments:
                        category_symbols = set()
                        for instrument in instruments:
                            symbol = instrument.get('symbol', '')
                            status = instrument.get('status', '')
                            
                            # Более мягкие критерии валидации - принимаем больше символов
                            if (symbol.endswith('USDT') and 
                                status in ['Trading', 'PreLaunch']):
                                category_symbols.add(symbol)
                                
                                # Сохраняем информацию о категории
                                supported_symbols.setdefault(category, set()).add(symbol)

                                if symbol not in symbol_categories:
                                    symbol_categories[symbol] = []
                                symbol_categories[symbol].append(category)

                        if category not in supported_symbols:
                            supported_symbols[category] = set()
                        self.log(f"✅ Категория '{category}': {len(supported_symbols[category])} активных USDT инструментов")
                    else:
                        supported_symbols[category] = set()
                        self.log(f"❌ Не удалось получить инструменты для категории '{category}'")
                except Exception as e:
                    supported_symbols[category] = set()
                    self.log(f"❌ Ошибка при получении инструментов для категории '{category}': {e}")

            api_confirmed = set()
            for category_symbols in supported_symbols.values():
                api_confirmed.update(category_symbols)

            missing_confirmation = [symbol for symbol in symbols if symbol not in api_confirmed]

            # Сохраняем информацию о категориях; для неподтверждённых символов используем значение по умолчанию
            for symbol in symbols:
                if symbol not in symbol_categories:
                    symbol_categories[symbol] = ['spot']

            self.symbol_categories = symbol_categories

            confirmed_count = len(symbols) - len(missing_confirmation)
            self.log(f"✅ Проверено символов: {len(symbols)}. Подтверждено API: {confirmed_count}")

            if missing_confirmation:
                preview = ', '.join(missing_confirmation[:10])
                self.log(f"⚠️ API не подтвердил {len(missing_confirmation)} символов. Используем данные тикеров: {preview}")

            return symbols

        except Exception as e:
            self.log(f"❌ Ошибка валидации символов: {e}")
            # В случае ошибки возвращаем все USDT символы
            usdt_symbols = [s for s in symbols if s.endswith('USDT')]
            self.symbol_categories = {symbol: ['spot'] for symbol in usdt_symbols}
            return usdt_symbols

    def load_symbols(self):
        """Загрузка списка символов с валидацией через API"""
        try:
            # Сначала пытаемся загрузить из TickerDataLoader
            if self.ticker_loader:
                ticker_data = self.ticker_loader.get_ticker_data()
                if ticker_data:
                    # Получаем все символы из загруженных данных
                    all_symbols = self.extract_symbols_from_ticker_data(ticker_data)
                    # Фильтруем только USDT пары
                    usdt_symbols = [symbol for symbol in all_symbols if symbol.endswith('USDT')]
                    unique_symbols = sorted(set(usdt_symbols))
                    self.expected_symbol_count = len(unique_symbols)
                    self.log(f"📊 Загружено символов из программы тикеров: {self.expected_symbol_count}")

                    if unique_symbols:
                        # Валидируем символы через API (категории сохраняются для обучения)
                        validated_symbols = self.validate_symbols_with_api(unique_symbols)

                        self.symbols = validated_symbols
                        self.log(
                            f"✅ Символы для обучения обновлены: {len(self.symbols)} (ожидается по тикерам: {self.expected_symbol_count})"
                        )

                        if hasattr(self, 'symbols_text'):
                            self.symbols_text.setPlainText('\n'.join(self.symbols))

                        return
                    else:
                        self.log("⚠️ В данных тикеров не найдено USDT-символов")
                else:
                    self.log("⚠️ Не удалось загрузить символы из TickerDataLoader")
            
            # Fallback: загружаем напрямую из API
            self.log("🔄 Загружаем символы напрямую из API...")
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
                        self.symbols = api_symbols  # Убираем ограничение на 100 символов
                        self.log(f"✅ Загружено символов из API: {len(self.symbols)}")
                        
                        # Создаем информацию о категориях для API символов
                        self.symbol_categories = {symbol: ['spot'] for symbol in self.symbols}
                        return
                    
            except Exception as e:
                self.log(f"❌ Ошибка загрузки из API: {e}")
            
            # Последний fallback
            self.symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'DOTUSDT', 'LINKUSDT']
            self.symbol_categories = {symbol: ['spot'] for symbol in self.symbols}
            self.log(f"⚠️ Используем резервный список символов: {len(self.symbols)}")
            
        except Exception as e:
            self.log(f"❌ Критическая ошибка загрузки символов: {e}")
            self.symbols = ['BTCUSDT', 'ETHUSDT']
            self.symbol_categories = {symbol: ['spot'] for symbol in self.symbols}

    def start_training(self, auto=False):
        """Запуск обучения"""
        try:
            if self.training_in_progress:
                if not auto:
                    self.log("⚠️ Обучение уже выполняется")
                return

            if auto:
                self.log("🤖 Автоматический запуск обучения на свежих данных")
            else:
                self.log("🚀 Запуск обучения моделей")

            self.training_in_progress = True
            self.pending_training = False

            self.load_symbols()

            if not self.symbols:
                self.log("⚠️ Нет символов для обучения")
                self.training_in_progress = False
                self.pending_training = False
                self.status_label.setText("⚠️ Нет символов для обучения")
                return

            # Обновляем таблицу прогресса
            self.progress_table.setRowCount(len(self.symbols))
            for i, symbol in enumerate(self.symbols):
                self.progress_table.setItem(i, 0, QTableWidgetItem(symbol))
                self.progress_table.setItem(i, 1, QTableWidgetItem("0%"))
                self.progress_table.setItem(i, 2, QTableWidgetItem("Ожидание"))
                self.progress_table.setItem(i, 3, QTableWidgetItem("-"))

            self.symbol_progress = {symbol: 0 for symbol in self.symbols}
            self.overall_progress.setValue(0)

            # Создаем и запускаем поток обучения
            self.training_worker = TrainingWorker(
                self.ml_strategy,
                self.symbols,
                getattr(self, 'symbol_categories', {})
            )
            self.training_worker.progress_updated.connect(self.update_progress)
            self.training_worker.status_updated.connect(self.update_status)
            self.training_worker.log_updated.connect(self.log)
            self.training_worker.training_completed.connect(self.training_finished)

            self.training_worker.start()

            # Обновляем UI
            self.train_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            if auto:
                self.status_label.setText("🤖 Автоматическое обучение запущено...")
            else:
                self.status_label.setText("🚀 Обучение запущено...")

        except Exception as e:
            self.log(f"Ошибка запуска обучения: {e}")

    def stop_training(self):
        """Остановка обучения"""
        if hasattr(self, 'training_worker'):
            self.training_worker.stop()
            self.training_finished()

    def training_finished(self):
        """Завершение обучения"""
        self.train_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.training_in_progress = False

        overall = 0
        if self.symbol_progress:
            overall = sum(self.symbol_progress.values()) / len(self.symbol_progress)
            self.overall_progress.setValue(int(overall))
        else:
            self.overall_progress.setValue(0)

        if overall >= 99.9:
            self.status_label.setText("✅ Обучение завершено")
            self.log("✅ Обучение завершено")
        else:
            self.status_label.setText("⏹️ Обучение остановлено")
            self.log("⏹️ Обучение остановлено до завершения")

        if hasattr(self, 'training_worker'):
            self.training_worker = None

        if self.pending_training:
            self.log("🔁 Запускаем отложенное обучение после завершения текущей сессии")
            self.pending_training = False
            QTimer.singleShot(1000, lambda: self.start_training(auto=True))

    def update_progress(self, symbol: str, progress: int):
        """Обновление прогресса для символа"""
        for row in range(self.progress_table.rowCount()):
            if self.progress_table.item(row, 0).text() == symbol:
                self.progress_table.setItem(row, 1, QTableWidgetItem(f"{progress}%"))
                break

        if symbol in self.symbol_progress:
            self.symbol_progress[symbol] = progress
            total_symbols = len(self.symbol_progress)
            if total_symbols:
                overall = sum(self.symbol_progress.values()) / total_symbols
                self.overall_progress.setValue(int(overall))

    def update_status(self, symbol: str, status: str, accuracy: float):
        """Обновление статуса для символа"""
        for row in range(self.progress_table.rowCount()):
            if self.progress_table.item(row, 0).text() == symbol:
                self.progress_table.setItem(row, 2, QTableWidgetItem(status))
                if accuracy > 0:
                    self.progress_table.setItem(row, 3, QTableWidgetItem(f"{accuracy:.2%}"))
                break

    def update_metrics(self):
        """Обновление метрик моделей"""
        try:
            if not hasattr(self, 'ml_strategy'):
                return
                
            performance = self.ml_strategy.performance
            self.metrics_table.setRowCount(len(performance))
            
            for i, (symbol, metrics) in enumerate(performance.items()):
                self.metrics_table.setItem(i, 0, QTableWidgetItem(symbol))
                self.metrics_table.setItem(i, 1, QTableWidgetItem(f"{metrics.get('accuracy', 0):.2%}"))
                self.metrics_table.setItem(i, 2, QTableWidgetItem(f"{metrics.get('precision', 0):.2%}"))
                self.metrics_table.setItem(i, 3, QTableWidgetItem(f"{metrics.get('recall', 0):.2%}"))
                self.metrics_table.setItem(i, 4, QTableWidgetItem(f"{metrics.get('f1_score', 0):.2%}"))
                
                last_trained = metrics.get('last_trained', 'Никогда')
                if isinstance(last_trained, (int, float)):
                    last_trained = datetime.fromtimestamp(last_trained).strftime('%Y-%m-%d %H:%M')
                self.metrics_table.setItem(i, 5, QTableWidgetItem(str(last_trained)))
                
        except Exception as e:
            self.log(f"Ошибка обновления метрик: {e}")

    def refresh_data(self):
        """Обновление данных"""
        self.update_metrics()
        self.log("🔄 Данные обновлены")

    def save_settings(self):
        """Сохранение настроек"""
        try:
            # Обновляем конфигурацию ML стратегии
            if hasattr(self, 'ml_strategy'):
                self.ml_strategy.feature_window = self.feature_window_spin.value()
                self.ml_strategy.confidence_threshold = self.confidence_spin.value()
                self.ml_strategy.use_technical_indicators = self.use_indicators_check.isChecked()
            
            self.log("💾 Настройки сохранены")
            
        except Exception as e:
            self.log(f"Ошибка сохранения настроек: {e}")

    def log(self, message: str):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_message = f"[{timestamp}] {message}"
        
        if hasattr(self, 'log_text'):
            self.log_text.append(formatted_message)
            # Автопрокрутка к последнему сообщению
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)
        
        print(formatted_message)


def main():
    """Главная функция"""
    app = QApplication(sys.argv)
    
    # Устанавливаем стиль приложения
    app.setStyle('Fusion')
    
    # Создаем и показываем главное окно
    window = TrainingMonitor()
    window.show()
    
    # Запускаем приложение
    sys.exit(app.exec())


if __name__ == "__main__":
    main()