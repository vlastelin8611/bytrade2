#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для просмотра тикеров Bybit
"""

import json
import time
import logging
import datetime
import threading
import tkinter as tk
import requests
from tkinter import ttk
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Настройка логирования
logger = logging.getLogger(__name__)

class TickerViewerApp:
    """Приложение для просмотра тикеров Bybit"""
    
    def __init__(self, root):
        """Инициализация приложения"""
        self.root = root
        self.root.title("Bybit Ticker Viewer")
        self.root.geometry("1200x800")
        
        # Путь для сохранения данных
        self.data_path = Path.home() / "AppData" / "Local" / "BybitTradingBot" / "data"
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # Данные тикеров
        self.all_tickers = []
        self.tickers_data = {}
        self.historical_data = {}
        self.selected_ticker = None
        
        # Флаги состояния
        self.is_loading = False
        self.stop_event = threading.Event()
        
        # Создание интерфейса
        self.create_widgets()
        
        # Запуск потока обновления тикеров
        self.update_thread = threading.Thread(target=self.update_tickers_thread)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        # Загрузка данных при запуске
        self.load_saved_data()
        self.refresh_tickers()
    
    def create_widgets(self):
        """Создание элементов интерфейса"""
        # Основной фрейм
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Верхняя панель с фильтрами
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Фильтр:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar(value="ALL")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var, 
                                   values=["ALL", "USDT", "BTC", "ETH", "USDC"])
        filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        
        ttk.Label(filter_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.search_var.trace_add("write", lambda *args: self.apply_filter())
        
        refresh_btn = ttk.Button(filter_frame, text="Обновить", command=self.refresh_tickers)
        refresh_btn.pack(side=tk.RIGHT)
        
        # Разделитель на две панели
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Левая панель с таблицей тикеров
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        # Таблица тикеров
        columns = ("symbol", "price", "high", "low", "volume", "change")
        self.ticker_table = ttk.Treeview(left_frame, columns=columns, show="headings")
        
        # Заголовки столбцов
        self.ticker_table.heading("symbol", text="Символ")
        self.ticker_table.heading("price", text="Цена")
        self.ticker_table.heading("high", text="Макс. 24ч")
        self.ticker_table.heading("low", text="Мин. 24ч")
        self.ticker_table.heading("volume", text="Объем 24ч")
        self.ticker_table.heading("change", text="Изм. 24ч (%)")
        
        # Настройка ширины столбцов
        self.ticker_table.column("symbol", width=100)
        self.ticker_table.column("price", width=100)
        self.ticker_table.column("high", width=100)
        self.ticker_table.column("low", width=100)
        self.ticker_table.column("volume", width=100)
        self.ticker_table.column("change", width=100)
        
        # Добавление прокрутки
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.ticker_table.yview)
        self.ticker_table.configure(yscrollcommand=scrollbar.set)
        
        # Размещение таблицы и прокрутки
        self.ticker_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Обработка выбора тикера
        self.ticker_table.bind("<<TreeviewSelect>>", self.on_ticker_select)
        
        # Правая панель с графиком и информацией
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        
        # Панель управления графиком
        chart_control = ttk.Frame(right_frame)
        chart_control.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(chart_control, text="Интервал:").pack(side=tk.LEFT, padx=(0, 5))
        self.interval_var = tk.StringVar(value="1 месяц")
        interval_combo = ttk.Combobox(chart_control, textvariable=self.interval_var, 
                                     values=["1h", "4h", "1d", "1w", "1 месяц", "3 месяца", "6 месяцев", "1 год", "2 года"])
        interval_combo.pack(side=tk.LEFT)
        interval_combo.bind("<<ComboboxSelected>>", lambda e: self.load_historical_data())
        
        # Фрейм для графика
        chart_frame = ttk.Frame(right_frame)
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Создание графика
        self.fig, self.ax = plt.subplots(figsize=(8, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Информация о тикере
        info_frame = ttk.LabelFrame(right_frame, text="Информация о тикере")
        info_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))
        
        self.info_text = tk.Text(info_frame, height=5, wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Статусная строка
        self.status_var = tk.StringVar(value="Готово")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))
    
    def on_closing(self):
        """Обработка закрытия приложения"""
        self.stop_event.set()
        self.root.destroy()
    
    def load_saved_data(self):
        """Загрузка сохраненных данных тикеров"""
        try:
            data_file = self.data_path / 'tickers_data.json'
            
            if not data_file.exists():
                logger.info("Файл с данными тикеров не найден")
                return
            
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not all(key in data for key in ['timestamp', 'tickers', 'historical_data']):
                logger.error("Некорректная структура данных в файле тикеров")
                return
            
            self.tickers_data = data['tickers']
            self.historical_data = data['historical_data']
            last_update = datetime.datetime.fromtimestamp(data['timestamp'])
            
            logger.info(f"Загружены сохраненные данные тикеров. Последнее обновление: {last_update}")
            self.status_var.set(f"Загружены сохраненные данные. Последнее обновление: {last_update}")
            
            # Обновляем интерфейс
            self.update_ticker_table(self.tickers_data)
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке сохраненных данных: {e}")
    
    def save_tickers_data(self):
        """Сохранение данных тикеров в файл для использования основной программой"""
        try:
            data_path = self.data_path / 'tickers_data.json'
            
            # Подготовка данных для сохранения
            save_data = {
                'timestamp': datetime.datetime.now().timestamp(),
                'tickers': self.tickers_data,
                'historical_data': self.historical_data
            }
            
            # Сохранение данных в файл
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, default=str)
            
            logger.info(f"Данные тикеров сохранены в {data_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных тикеров: {e}")
            return False
            
    def update_tickers_thread(self):
        """Поток для периодического обновления тикеров"""
        while not self.stop_event.is_set():
            try:
                if not self.is_loading:
                    self.refresh_tickers()
                    # Сохраняем данные после каждого обновления
                    self.save_tickers_data()
            except Exception as e:
                logger.error(f"Ошибка при обновлении тикеров: {e}")
            
            # Обновление каждые 30 секунд
            time.sleep(30)
            
    def process_historical_data_result(self, result):
        """Обработка результатов загрузки исторических данных"""
        symbol = result.get("symbol")
        
        if "error" in result:
            self.status_var.set(f"Ошибка: {result['error']}")
            # Очищаем график и показываем сообщение об ошибке
            self.ax.clear()
            self.ax.text(0.5, 0.5, f"Ошибка загрузки данных для {symbol}:\n{result['error']}", 
                        horizontalalignment='center', verticalalignment='center')
            self.canvas.draw()
            return
        
        klines = result.get("data", [])
        
        # Сохраняем данные
        self.historical_data[symbol] = klines
        
        # Обновляем график и информацию
        self.update_chart()
        self.update_ticker_info(symbol)
        # Обновляем таблицу тикеров, чтобы отобразить изменение за период для выбранного тикера
        self.update_ticker_table(self.all_tickers)
        self.status_var.set(f"Загружено {len(klines)} свечей для {symbol}")
        
        # Автоматически сохраняем данные в файл
        self.save_tickers_data()
            
    def process_tickers_result(self, result):
        """Обработка результатов получения тикеров"""
        if isinstance(result, dict) and "error" in result:
            self.status_var.set(f"Ошибка: {result['error']}")
            return
        
        if not result:
            self.status_var.set("Не удалось получить информацию о тикерах")
            return
        
        # Сохраняем все тикеры
        self.all_tickers = result
        self.tickers_data = result
        
        # Обновляем интерфейс
        self.update_ticker_table(result)
        self.status_var.set(f"Загружено {len(result)} тикеров")
        
        # Автоматически сохраняем данные в файл
        self.save_tickers_data()
        
    def get_bybit_tickers(self):
        """Получение данных тикеров через API Bybit"""
        try:
            url = "https://api.bybit.com/v5/market/tickers"
            params = {"category": "spot"}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Ошибка API: статус {response.status_code}")
                return None
                
            data = response.json()
            
            if data.get("retCode") != 0:
                logger.error(f"Ошибка API: {data.get('retMsg')}")
                return None
                
            tickers_list = data.get("result", {}).get("list", [])
            
            # Преобразуем данные в нужный формат
            formatted_tickers = []
            for ticker in tickers_list:
                formatted_ticker = {
                    "symbol": ticker.get("symbol"),
                    "lastPrice": ticker.get("lastPrice"),
                    "highPrice": ticker.get("highPrice24h"),
                    "lowPrice": ticker.get("lowPrice24h"),
                    "volume": ticker.get("volume24h"),
                    "priceChangePercent": ticker.get("price24hPcnt", "0")
                }
                formatted_tickers.append(formatted_ticker)
                
            logger.info(f"Получено {len(formatted_tickers)} тикеров через API Bybit")
            return formatted_tickers
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных тикеров: {e}")
            return None
    
    def refresh_tickers(self):
        """Обновление данных тикеров"""
        self.status_var.set("Загрузка данных тикеров...")
        self.is_loading = True
        
        # Получаем реальные данные через API Bybit
        tickers_data = self.get_bybit_tickers()
        
        if tickers_data:
            self.process_tickers_result(tickers_data)
            self.status_var.set(f"Загружено {len(tickers_data)} тикеров через API Bybit")
        else:
            self.status_var.set("Ошибка при получении данных тикеров")
            
        self.is_loading = False
        
    def update_ticker_table(self, tickers):
        """Обновление таблицы тикеров"""
        # Очистка таблицы
        for item in self.ticker_table.get_children():
            self.ticker_table.delete(item)
        
        # Применение фильтров
        filtered_tickers = self.apply_filter(tickers)
        
        # Заполнение таблицы
        for ticker in filtered_tickers:
            symbol = ticker.get("symbol", "")
            price = ticker.get("lastPrice", "0")
            high = ticker.get("highPrice", "0")
            low = ticker.get("lowPrice", "0")
            volume = ticker.get("volume", "0")
            change = ticker.get("priceChangePercent", "0")
            
            # Добавление строки в таблицу
            self.ticker_table.insert("", tk.END, values=(symbol, price, high, low, volume, change))
    
    def apply_filter(self, tickers=None):
        """Применение фильтров к списку тикеров"""
        if tickers is None:
            tickers = self.all_tickers
        
        if not tickers:
            return []
        
        # Получаем текущие значения фильтров
        filter_type = self.filter_var.get()
        search_text = self.search_var.get().upper()
        
        # Фильтрация по типу
        if filter_type == "ALL":
            filtered_tickers = tickers
        else:
            filtered_tickers = [t for t in tickers if t.get('symbol', '').endswith(filter_type)]
        
        # Фильтрация по поисковому запросу
        if search_text:
            filtered_tickers = [t for t in filtered_tickers if search_text in t.get('symbol', '')]
        
        return filtered_tickers
    
    def on_ticker_select(self, event):
        """Обработка выбора тикера в таблице"""
        selection = self.ticker_table.selection()
        if not selection:
            return
        
        # Получаем выбранный тикер
        item = self.ticker_table.item(selection[0])
        symbol = item['values'][0]
        
        self.selected_ticker = symbol
        self.status_var.set(f"Выбран тикер: {symbol}")
        
        # Обновляем информацию о тикере
        self.update_ticker_info(symbol)
        
        # Загружаем исторические данные
        self.load_historical_data()
    
    def update_ticker_info(self, symbol):
        """Обновление информации о выбранном тикере"""
        # Поиск тикера в данных
        ticker_data = next((t for t in self.all_tickers if t.get('symbol') == symbol), None)
        
        if not ticker_data:
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, f"Нет данных для {symbol}")
            return
        
        # Формирование информации
        info = f"Символ: {symbol}\n"
        info += f"Текущая цена: {ticker_data.get('lastPrice', 'N/A')}\n"
        info += f"Изменение за 24ч: {ticker_data.get('priceChangePercent', 'N/A')}%\n"
        info += f"Максимум 24ч: {ticker_data.get('highPrice', 'N/A')}\n"
        info += f"Минимум 24ч: {ticker_data.get('lowPrice', 'N/A')}\n"
        info += f"Объем 24ч: {ticker_data.get('volume', 'N/A')}\n"
        
        # Обновление текстового поля
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, info)
    
    def get_bybit_historical_data(self, symbol, interval):
        """Получение исторических данных через API Bybit"""
        try:
            # Преобразование интервалов в формат API Bybit
            interval_mapping = {
                # Старые интервалы
                "1h": {"interval": "60", "limit": 200},
                "4h": {"interval": "240", "limit": 200},
                "1d": {"interval": "D", "limit": 200},
                "1w": {"interval": "W", "limit": 100},
                # Новые интервалы
                "1 месяц": {"interval": "D", "limit": 30},
                "3 месяца": {"interval": "D", "limit": 90},
                "6 месяцев": {"interval": "D", "limit": 180},
                "1 год": {"interval": "W", "limit": 52},
                "2 года": {"interval": "W", "limit": 104}
            }
            
            api_interval = interval_mapping.get(interval, {"interval": "D", "limit": 30})
            
            url = "https://api.bybit.com/v5/market/kline"
            params = {
                "category": "spot",
                "symbol": symbol,
                "interval": api_interval["interval"],
                "limit": api_interval["limit"]
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Ошибка API исторических данных: статус {response.status_code}")
                return {"symbol": symbol, "error": f"Ошибка API: статус {response.status_code}"}
                
            data = response.json()
            
            if data.get("retCode") != 0:
                logger.error(f"Ошибка API исторических данных: {data.get('retMsg')}")
                return {"symbol": symbol, "error": f"Ошибка API: {data.get('retMsg')}"}
                
            klines = data.get("result", {}).get("list", [])
            
            # Преобразуем данные в нужный формат
            formatted_data = []
            for kline in klines:
                # Формат данных: [timestamp, open, high, low, close, volume, ...]
                if len(kline) >= 6:
                    formatted_kline = {
                        'timestamp': int(kline[0]) / 1000,  # Bybit возвращает время в миллисекундах
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    }
                    formatted_data.append(formatted_kline)
            
            # Сортировка по времени (от старых к новым)
            formatted_data.sort(key=lambda x: x['timestamp'])
            
            logger.info(f"Получено {len(formatted_data)} исторических свечей для {symbol}")
            
            return {
                'symbol': symbol,
                'data': formatted_data
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении исторических данных: {e}")
            return {"symbol": symbol, "error": str(e)}
    
    def load_historical_data(self):
        """Загрузка исторических данных для выбранного тикера"""
        if not self.selected_ticker:
            return
        
        symbol = self.selected_ticker
        interval = self.interval_var.get()
        
        self.status_var.set(f"Загрузка исторических данных для {symbol}...")
        
        # Получаем реальные исторические данные через API Bybit
        result = self.get_bybit_historical_data(symbol, interval)
        
        if result:
            self.process_historical_data_result(result)
        else:
            self.status_var.set(f"Ошибка при загрузке исторических данных для {symbol}")
    
    def update_chart(self):
        """Обновление графика для выбранного тикера"""
        if not self.selected_ticker or self.selected_ticker not in self.historical_data:
            return
        
        symbol = self.selected_ticker
        data = self.historical_data[symbol]
        
        if not data:
            return
        
        # Очистка графика
        self.ax.clear()
        
        # Подготовка данных для графика
        timestamps = [datetime.datetime.fromtimestamp(d['timestamp']) for d in data]
        closes = [float(d['close']) for d in data]
        
        # Построение графика
        self.ax.plot(timestamps, closes, label=f"{symbol} Close")
        
        # Настройка графика
        self.ax.set_title(f"{symbol} - {self.interval_var.get()}")
        self.ax.set_xlabel("Время")
        self.ax.set_ylabel("Цена")
        self.ax.legend()
        self.ax.grid(True)
        
        # Поворот меток времени для лучшей читаемости
        plt.setp(self.ax.get_xticklabels(), rotation=45, ha='right')
        
        # Автоматическая настройка макета
        self.fig.tight_layout()
        
        # Обновление холста
        self.canvas.draw()