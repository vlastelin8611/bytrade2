#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вкладка портфолио с функционалом отображения тикеров
Адаптировано из ticker_viewer_gui.py для использования с PySide6
"""

import logging
import sys
import json
import threading
import time
import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
    QHeaderView, QSplitter, QFrame, QTextEdit, QGroupBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QColor

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Добавляем корневую директорию проекта в sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

# Импортируем BybitClient из модуля api
from src.api.bybit_client import BybitClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('portfolio_tab')

# Интервалы для исторических данных
INTERVALS = {
    "1 минута": "1",
    "5 минут": "5",
    "15 минут": "15",
    "30 минут": "30",
    "1 час": "60",
    "4 часа": "240",
    "1 день": "D",
    "1 неделя": "W",
    "1 месяц": "M"
}

class UpdateTickersThread(QThread):
    """Поток для обновления тикеров"""
    update_signal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
    
    def run(self):
        while self.running:
            self.update_signal.emit()
            time.sleep(30)  # Обновление каждые 30 секунд
    
    def stop(self):
        self.running = False

class PortfolioTab(QWidget):
    """Вкладка портфолио с функционалом отображения тикеров"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Инициализация клиента Bybit
        self.client = self.initialize_bybit_client()
        
        # Текущий выбранный тикер
        self.selected_ticker = None
        self.historical_data = {}
        self.all_tickers = []
        
        # Настройка интерфейса
        self.setup_ui()
        
        # Запуск обновления данных в отдельном потоке
        self.update_thread = UpdateTickersThread(self)
        self.update_thread.update_signal.connect(self.refresh_tickers)
        self.update_thread.start()
    
    def initialize_bybit_client(self):
        """Инициализация клиента Bybit с ключами из файла"""
        keys_path = Path(__file__).parent.parent.parent / 'keys'
        if not keys_path.exists():
            logger.error(f"Файл с API ключами не найден: {keys_path}")
            return None
        
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
            return None
        
        if not api_key or not api_secret:
            logger.error("API ключи не найдены в конфигурации")
            return None
        
        return BybitClient(api_key, api_secret)
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        main_layout = QVBoxLayout(self)
        
        # Основной сплиттер
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель с таблицей тикеров
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Фрейм для фильтров
        filter_frame = QFrame()
        filter_layout = QHBoxLayout(filter_frame)
        
        # Фильтр по типу тикера
        filter_layout.addWidget(QLabel("Фильтр:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["ALL", "USDT", "BTC", "ETH", "USDC"])
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.filter_combo)
        
        # Поле поиска
        filter_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.search_edit)
        
        # Кнопка обновления
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.clicked.connect(self.refresh_tickers)
        filter_layout.addWidget(self.refresh_button)
        
        left_layout.addWidget(filter_frame)
        
        # Таблица тикеров
        self.ticker_table = QTableWidget()
        self.ticker_table.setColumnCount(8)
        self.ticker_table.setHorizontalHeaderLabels([
            "Символ", "Последняя цена", "Макс. 24ч", "Мин. 24ч", 
            "Объем 24ч", "Оборот 24ч", "Изм. 24ч (%)", "Изм. за период (%)"
        ])
        self.ticker_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ticker_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ticker_table.setSelectionMode(QTableWidget.SingleSelection)
        self.ticker_table.itemSelectionChanged.connect(self.on_ticker_select)
        
        left_layout.addWidget(self.ticker_table)
        
        # Правая панель с графиком
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Панель управления графиком
        chart_control_frame = QFrame()
        chart_control_layout = QHBoxLayout(chart_control_frame)
        
        chart_control_layout.addWidget(QLabel("Интервал:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(list(INTERVALS.keys()))
        self.interval_combo.setCurrentText("1 час")
        self.interval_combo.currentIndexChanged.connect(self.on_interval_changed)
        chart_control_layout.addWidget(self.interval_combo)
        
        right_layout.addWidget(chart_control_frame)
        
        # График
        self.figure = Figure(figsize=(6, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        right_layout.addWidget(self.canvas)
        
        # Информация о тикере
        self.ticker_info_group = QGroupBox("Информация о тикере")
        ticker_info_layout = QVBoxLayout(self.ticker_info_group)
        
        self.ticker_info_text = QTextEdit()
        self.ticker_info_text.setReadOnly(True)
        ticker_info_layout.addWidget(self.ticker_info_text)
        
        right_layout.addWidget(self.ticker_info_group)
        
        # Добавляем виджеты в сплиттер
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])
        
        main_layout.addWidget(splitter)
        
        # Статусная строка
        self.status_label = QLabel("Загрузка тикеров...")
        main_layout.addWidget(self.status_label)
        
        # Первоначальная загрузка данных
        QTimer.singleShot(100, self.refresh_tickers)
    
    def update_tickers_thread(self):
        """Поток для периодического обновления тикеров"""
        while True:
            try:
                self.refresh_tickers()
            except Exception as e:
                logger.error(f"Ошибка при обновлении тикеров: {e}")
            
            # Обновление каждые 30 секунд
            time.sleep(30)
    
    def refresh_tickers(self):
        """Обновление данных о тикерах"""
        if not self.client:
            self.status_label.setText("Ошибка: клиент Bybit не инициализирован")
            return
        
        try:
            self.status_label.setText("Загрузка тикеров...")
            
            # Получение тикеров
            tickers = self.client.get_tickers(category="spot")
            
            if not tickers:
                self.status_label.setText("Не удалось получить информацию о тикерах")
                return
            
            # Сохраняем все тикеры
            self.all_tickers = tickers
            
            # Обновляем интерфейс
            self.update_ticker_table(tickers)
            self.status_label.setText(f"Загружено {len(tickers)} тикеров")
            
        except Exception as e:
            logger.error(f"Ошибка при получении тикеров: {e}")
            self.status_label.setText(f"Ошибка: {str(e)}")
    
    def update_ticker_table(self, tickers):
        """Обновление таблицы тикеров"""
        # Очистка таблицы
        self.ticker_table.setRowCount(0)
        
        # Применение фильтра
        filtered_tickers = self.filter_tickers(tickers)
        
        # Добавление тикеров в таблицу
        self.ticker_table.setRowCount(len(filtered_tickers))
        
        for row, ticker in enumerate(filtered_tickers):
            symbol = ticker.get('symbol', '')
            
            # Расчет изменения цены за 24 часа в процентах
            try:
                prev_price = float(ticker.get('prevPrice24h', 0))
                last_price = float(ticker.get('lastPrice', 0))
                if prev_price > 0:
                    change_pct = (last_price - prev_price) / prev_price * 100
                    change_str = f"{change_pct:.2f}%"
                    
                    # Цвет в зависимости от изменения
                    if change_pct > 0:
                        change_color = QColor(0, 128, 0)  # Зеленый
                    elif change_pct < 0:
                        change_color = QColor(255, 0, 0)  # Красный
                    else:
                        change_color = QColor(0, 0, 0)    # Черный
                else:
                    change_str = "N/A"
                    change_color = QColor(0, 0, 0)
            except (ValueError, TypeError):
                change_str = "N/A"
                change_color = QColor(0, 0, 0)
            
            # Расчет изменения цены за период (если есть исторические данные)
            change_period_str = "N/A"
            change_period_color = QColor(0, 0, 0)
            
            if symbol in self.historical_data and self.historical_data[symbol]:
                try:
                    klines = self.historical_data[symbol]
                    if len(klines) > 1:
                        latest = klines[-1]  # Последняя свеча (самая новая)
                        oldest = klines[0]   # Первая свеча (самая старая)
                        
                        latest_close = float(latest['close'])
                        oldest_close = float(oldest['close'])
                        
                        if oldest_close > 0:
                            price_change_pct = ((latest_close - oldest_close) / oldest_close) * 100
                            change_period_str = f"{price_change_pct:.2f}%"
                            
                            # Цвет в зависимости от изменения
                            if price_change_pct > 0:
                                change_period_color = QColor(0, 128, 0)  # Зеленый
                            elif price_change_pct < 0:
                                change_period_color = QColor(255, 0, 0)  # Красный
                except (ValueError, TypeError, KeyError) as e:
                    logger.error(f"Ошибка при расчете изменения за период для {symbol}: {e}")
            
            # Заполнение ячеек таблицы
            items = [
                QTableWidgetItem(symbol),
                QTableWidgetItem(ticker.get('lastPrice', '')),
                QTableWidgetItem(ticker.get('highPrice24h', '')),
                QTableWidgetItem(ticker.get('lowPrice24h', '')),
                QTableWidgetItem(ticker.get('volume24h', '')),
                QTableWidgetItem(ticker.get('turnover24h', '')),
                QTableWidgetItem(change_str),
                QTableWidgetItem(change_period_str)
            ]
            
            # Установка цветов для изменений
            items[6].setForeground(change_color)
            items[7].setForeground(change_period_color)
            
            # Добавление элементов в таблицу
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                self.ticker_table.setItem(row, col, item)
    
    def filter_tickers(self, tickers):
        """Фильтрация тикеров по выбранным критериям"""
        filter_type = self.filter_combo.currentText()
        search_text = self.search_edit.text().upper()
        
        filtered = []
        for ticker in tickers:
            symbol = ticker.get('symbol', '')
            
            # Фильтр по типу
            if filter_type != "ALL" and not symbol.endswith(filter_type):
                continue
            
            # Фильтр по поисковому запросу
            if search_text and search_text not in symbol:
                continue
            
            filtered.append(ticker)
        
        return filtered
    
    def apply_filter(self):
        """Применение фильтра к текущим тикерам"""
        self.update_ticker_table(self.all_tickers)
    
    def on_ticker_select(self):
        """Обработчик выбора тикера в таблице"""
        selected_items = self.ticker_table.selectedItems()
        if not selected_items:
            return
        
        row = selected_items[0].row()
        symbol = self.ticker_table.item(row, 0).text()
        
        self.selected_ticker = symbol
        self.status_label.setText(f"Загрузка исторических данных для {symbol}...")
        
        # Загрузка исторических данных в отдельном потоке
        threading.Thread(target=self.load_historical_data, args=(symbol,)).start()
    
    def load_historical_data(self, symbol):
        """Загрузка исторических данных для выбранного тикера"""
        try:
            interval = INTERVALS[self.interval_combo.currentText()]
            
            # Расчет временного диапазона
            end_time = int(time.time() * 1000)  # Текущее время в миллисекундах
            
            # Определяем начальное время в зависимости от интервала
            interval_ms = {
                "1": 60_000, "3": 180_000, "5": 300_000, "15": 900_000, "30": 1_800_000,
                "60": 3_600_000, "120": 7_200_000, "240": 14_400_000, "360": 21_600_000,
                "720": 43_200_000, "D": 86_400_000, "W": 604_800_000, "M": 2_592_000_000
            }
            
            # Получаем количество миллисекунд для выбранного интервала
            ms_per_interval = interval_ms.get(interval, 3_600_000)  # По умолчанию 1 час
            
            # Начальное время: текущее время минус (500 интервалов) для получения большего объема данных
            start_time = end_time - (ms_per_interval * 500)
            
            # Обновляем статус в основном потоке
            self.status_label.setText(f"Загрузка исторических данных для {symbol}...")
            
            # Реализация пагинации для получения полного набора данных
            all_klines = []
            current_end = end_time
            
            # Максимальное количество итераций для предотвращения бесконечного цикла
            max_iterations = 5
            iterations = 0
            
            while current_end > start_time and iterations < max_iterations:
                # Запрос исторических данных с указанием временного диапазона
                klines = self.client.get_kline(
                    category="spot", 
                    symbol=symbol, 
                    interval=interval, 
                    limit=1000,  # Максимальное количество свечей
                    start=start_time,
                    end=current_end
                )
                
                if not klines or len(klines) == 0:
                    break
                    
                all_klines.extend(klines)
                
                # Обновляем конечное время для следующего запроса
                # Берем время первой свечи (самой новой) и вычитаем 1 мс
                # Так как API возвращает свечи в обратном порядке (от новых к старым)
                first_timestamp = int(klines[0]['timestamp'])
                current_end = first_timestamp - 1
                
                # Обновляем статус в основном потоке
                self.status_label.setText(f"Загружено {len(all_klines)} свечей для {symbol}...")
                
                iterations += 1
                # Небольшая задержка для предотвращения превышения лимита запросов
                time.sleep(0.2)
            
            if not all_klines:
                self.status_label.setText(f"Не удалось загрузить исторические данные для {symbol}")
                return
            
            # Сортируем данные по времени (от старых к новым)
            all_klines.sort(key=lambda x: int(x['timestamp']))
            
            # Сохраняем данные
            self.historical_data[symbol] = all_klines
            
            # Обновляем график и информацию в основном потоке
            self.update_chart()
            self.update_ticker_info(symbol)
            # Обновляем таблицу тикеров, чтобы отобразить изменение за период для выбранного тикера
            self.update_ticker_table(self.all_tickers)
            self.status_label.setText(f"Загружено {len(all_klines)} свечей для {symbol}")
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке исторических данных: {e}")
            self.status_label.setText(f"Ошибка: {str(e)}")
    
    def update_chart(self):
        """Обновление графика с историческими данными"""
        if not self.selected_ticker or self.selected_ticker not in self.historical_data:
            return
        
        klines = self.historical_data[self.selected_ticker]
        
        # Очистка графика
        self.ax.clear()
        
        # Подготовка данных для графика
        dates = [datetime.datetime.fromtimestamp(int(k['timestamp'])/1000) for k in klines]
        closes = [float(k['close']) for k in klines]
        
        # Построение графика
        self.ax.plot(dates, closes, 'b-')
        self.ax.set_title(f"{self.selected_ticker} - {self.interval_combo.currentText()}")
        self.ax.set_xlabel('Время')
        self.ax.set_ylabel('Цена')
        self.figure.autofmt_xdate()  # Автоматическое форматирование дат
        
        # Обновление холста
        self.canvas.draw()
    
    def update_ticker_info(self, symbol):
        """Обновление информации о тикере"""
        if not self.selected_ticker or self.selected_ticker not in self.historical_data:
            return
        
        klines = self.historical_data[self.selected_ticker]
        
        if not klines:
            return
        
        # Получение последних данных
        latest = klines[-1]  # Последняя свеча (самая новая)
        oldest = klines[0]   # Первая свеча (самая старая)
        
        # Расчет изменения цены
        latest_close = float(latest['close'])
        oldest_close = float(oldest['close'])
        price_change = latest_close - oldest_close
        
        if oldest_close > 0:
            price_change_pct = (price_change / oldest_close) * 100
        else:
            price_change_pct = 0
        
        # Форматирование информации
        info = f"Символ: {symbol}\n"
        info += f"Текущая цена: {latest_close}\n"
        info += f"Изменение за период: {price_change:.8f} ({price_change_pct:.2f}%)\n"
        info += f"Максимум: {max(float(k['high']) for k in klines)}\n"
        info += f"Минимум: {min(float(k['low']) for k in klines)}\n"
        
        # Обновление текстового поля
        self.ticker_info_text.setText(info)
    
    def on_interval_changed(self):
        """Обработчик изменения интервала"""
        if self.selected_ticker:
            threading.Thread(target=self.load_historical_data, args=(self.selected_ticker,)).start()
    
    def start_auto_update(self):
        """Запуск автоматического обновления данных"""
        # Автоматическое обновление уже запущено в конструкторе через QThread
        self.status_label.setText("Автоматическое обновление тикеров активно")
    
    def closeEvent(self, event):
        """Обработчик закрытия вкладки"""
        # Остановка потока обновления
        if hasattr(self, 'update_thread'):
            self.update_thread.stop()
            self.update_thread.wait()