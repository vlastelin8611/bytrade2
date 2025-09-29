#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовая программа для торговли
Простой GUI для покупки/продажи активов через Bybit API
"""

import sys
import os
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import time

# Добавляем путь к модулям
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QPushButton, QLabel, QTextEdit, QTableWidget, 
    QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox,
    QProgressBar, QStatusBar
)
from PySide6.QtCore import QTimer, QThread, Signal, Qt
from PySide6.QtGui import QFont, QPalette, QColor

# Импорт API клиента и загрузчика тикеров
from api.bybit_client import BybitClient
from tools.ticker_data_loader import TickerDataLoader


class TradingWorker(QThread):
    """Рабочий поток для торговых операций"""
    
    balance_updated = Signal(dict)
    positions_updated = Signal(list)
    trade_executed = Signal(dict)
    log_message = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.running = False
        
        # Инициализация компонентов
        self.bybit_client = None
        self.ticker_loader = None
        
        # Настройка логирования
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """Основной цикл рабочего потока"""
        try:
            self.running = True
            self.log_message.emit("🚀 Инициализация торгового клиента...")
            
            # Инициализация API клиента
            self.bybit_client = BybitClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            
            # Инициализация загрузчика тикеров
            self.ticker_loader = TickerDataLoader()
            
            self.log_message.emit("✅ Клиент инициализирован успешно")
            
            # Основной цикл обновления данных
            while self.running:
                try:
                    # Обновление баланса
                    self.update_balance()
                    
                    # Обновление позиций
                    self.update_positions()
                    
                    # Пауза между обновлениями
                    self.msleep(5000)  # 5 секунд
                    
                except Exception as e:
                    self.error_occurred.emit(f"Ошибка в цикле обновления: {str(e)}")
                    self.msleep(10000)  # 10 секунд при ошибке
                    
        except Exception as e:
            self.error_occurred.emit(f"Критическая ошибка: {str(e)}")
    
    def update_balance(self):
        """Обновление баланса"""
        try:
            balance_response = self.bybit_client.get_wallet_balance()
            
            if balance_response and balance_response.get('list'):
                balance_data = balance_response['list'][0]
                
                balance_info = {
                    'totalWalletBalance': balance_data.get('totalWalletBalance', '0'),
                    'totalAvailableBalance': balance_data.get('totalAvailableBalance', '0'),
                    'coins': balance_data.get('coin', [])
                }
                
                self.balance_updated.emit(balance_info)
                
        except Exception as e:
            self.error_occurred.emit(f"Ошибка обновления баланса: {str(e)}")
    
    def update_positions(self):
        """Обновление позиций"""
        try:
            # Получаем активные ордера
            orders_response = self.bybit_client.get_open_orders(category='spot', limit=50)
            
            positions = []
            if orders_response and orders_response.get('list'):
                positions = orders_response['list']
            
            self.positions_updated.emit(positions)
            
        except Exception as e:
            self.error_occurred.emit(f"Ошибка обновления позиций: {str(e)}")
    
    def buy_cheapest_ticker(self):
        """Покупка самого дешевого тикера"""
        try:
            self.log_message.emit("🔍 Поиск самого дешевого тикера...")
            
            # Загружаем данные тикеров
            tickers_data = self.ticker_loader.load_tickers_data()
            
            if not tickers_data:
                self.error_occurred.emit("❌ Нет данных по тикерам")
                return
            
            # Находим самый дешевый тикер
            cheapest_symbol = None
            cheapest_price = float('inf')
            
            for symbol, data in tickers_data.items():
                if symbol.endswith('USDT'):
                    try:
                        price = float(data.get('lastPrice', 0))
                        if 0 < price < cheapest_price:
                            cheapest_price = price
                            cheapest_symbol = symbol
                    except (ValueError, TypeError):
                        continue
            
            if not cheapest_symbol:
                self.error_occurred.emit("❌ Не найден подходящий тикер")
                return
            
            self.log_message.emit(f"💰 Найден самый дешевый тикер: {cheapest_symbol} (${cheapest_price:.6f})")
            
            # Размещаем ордер на покупку
            order_result = self.bybit_client.place_order(
                category='spot',
                symbol=cheapest_symbol,
                side='Buy',
                order_type='Market',
                qty='10'  # Покупаем на $10
            )
            
            if order_result:
                self.log_message.emit(f"✅ Ордер на покупку {cheapest_symbol} размещен успешно")
                self.trade_executed.emit({
                    'symbol': cheapest_symbol,
                    'side': 'Buy',
                    'qty': '10',
                    'price': cheapest_price,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                self.error_occurred.emit("❌ Не удалось разместить ордер на покупку")
                
        except Exception as e:
            self.error_occurred.emit(f"❌ Ошибка покупки: {str(e)}")
    
    def sell_cheapest_position(self):
        """Продажа самого дешевого актива из портфеля"""
        try:
            self.log_message.emit("🔍 Поиск самого дешевого актива в портфеле...")
            
            # Получаем баланс
            balance_response = self.bybit_client.get_wallet_balance()
            
            if not balance_response or not balance_response.get('list'):
                self.error_occurred.emit("❌ Не удалось получить данные баланса")
                return
            
            coins = balance_response['list'][0].get('coin', [])
            
            # Фильтруем монеты с положительным балансом
            tradeable_coins = []
            for coin in coins:
                coin_name = coin.get('coin', '')
                wallet_balance = float(coin.get('walletBalance', 0))
                usd_value = float(coin.get('usdValue', 0))
                
                # Исключаем стейблкоины и монеты с малым балансом
                if (coin_name not in ['USDT', 'USDC', 'BUSD', 'DAI'] and 
                    wallet_balance > 0 and usd_value > 0.1):
                    tradeable_coins.append({
                        'coin': coin_name,
                        'balance': wallet_balance,
                        'usd_value': usd_value
                    })
            
            if not tradeable_coins:
                self.error_occurred.emit("❌ Нет активов для продажи")
                return
            
            # Находим самый дешевый актив
            cheapest_coin = min(tradeable_coins, key=lambda c: c['usd_value'])
            symbol = cheapest_coin['coin'] + 'USDT'
            
            # Рассчитываем количество для продажи (10% от баланса)
            sell_qty = max(cheapest_coin['balance'] * 0.1, 0.001)
            
            self.log_message.emit(f"💸 Продажа {sell_qty:.6f} {cheapest_coin['coin']} (${cheapest_coin['usd_value']:.2f})")
            
            # Размещаем ордер на продажу
            order_result = self.bybit_client.place_order(
                category='spot',
                symbol=symbol,
                side='Sell',
                order_type='Market',
                qty=str(sell_qty)
            )
            
            if order_result:
                self.log_message.emit(f"✅ Ордер на продажу {symbol} размещен успешно")
                self.trade_executed.emit({
                    'symbol': symbol,
                    'side': 'Sell',
                    'qty': str(sell_qty),
                    'usd_value': cheapest_coin['usd_value'],
                    'timestamp': datetime.now().isoformat()
                })
            else:
                self.error_occurred.emit("❌ Не удалось разместить ордер на продажу")
                
        except Exception as e:
            self.error_occurred.emit(f"❌ Ошибка продажи: {str(e)}")
    
    def stop(self):
        """Остановка рабочего потока"""
        self.running = False
        self.quit()
        self.wait()


class TestTradingApp(QMainWindow):
    """Главное окно тестовой торговой программы"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Тестовая торговая программа")
        self.setGeometry(100, 100, 1000, 700)
        
        # Загрузка API ключей
        self.api_key, self.api_secret = self.load_api_keys()
        
        # Инициализация рабочего потока
        self.trading_worker = None
        
        # Данные
        self.current_balance = {}
        self.current_positions = []
        
        # Настройка UI
        self.init_ui()
        
        # Запуск рабочего потока
        self.start_trading_worker()
    
    def load_api_keys(self) -> tuple:
        """Загрузка API ключей из файла"""
        try:
            keys_file = Path(__file__).parent / 'keys'
            if keys_file.exists():
                with open(keys_file, 'r') as f:
                    lines = f.read().strip().split('\n')
                    if len(lines) >= 2:
                        return lines[0].strip(), lines[1].strip()
            
            # Если файл не найден, возвращаем пустые ключи
            QMessageBox.warning(self, "Ошибка", "Файл с API ключами не найден!")
            return "", ""
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки API ключей: {str(e)}")
            return "", ""
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        
        # Заголовок
        title_label = QLabel("🚀 Тестовая торговая программа")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Горизонтальный layout для основного содержимого
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)
        
        # Левая панель - баланс и позиции
        left_panel = self.create_left_panel()
        content_layout.addWidget(left_panel, 2)
        
        # Правая панель - кнопки и логи
        right_panel = self.create_right_panel()
        content_layout.addWidget(right_panel, 1)
        
        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе")
    
    def create_left_panel(self) -> QWidget:
        """Создание левой панели с балансом и позициями"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Группа баланса
        balance_group = QGroupBox("💰 Баланс портфеля")
        balance_layout = QVBoxLayout(balance_group)
        
        self.balance_label = QLabel("Загрузка...")
        self.balance_label.setFont(QFont("Arial", 12))
        balance_layout.addWidget(self.balance_label)
        
        # Таблица монет
        self.coins_table = QTableWidget()
        self.coins_table.setColumnCount(3)
        self.coins_table.setHorizontalHeaderLabels(["Монета", "Баланс", "USD стоимость"])
        self.coins_table.horizontalHeader().setStretchLastSection(True)
        balance_layout.addWidget(self.coins_table)
        
        layout.addWidget(balance_group)
        
        # Группа позиций
        positions_group = QGroupBox("📊 Активные ордера")
        positions_layout = QVBoxLayout(positions_group)
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(4)
        self.positions_table.setHorizontalHeaderLabels(["Символ", "Сторона", "Количество", "Цена"])
        self.positions_table.horizontalHeader().setStretchLastSection(True)
        positions_layout.addWidget(self.positions_table)
        
        layout.addWidget(positions_group)
        
        return panel
    
    def create_right_panel(self) -> QWidget:
        """Создание правой панели с кнопками и логами"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Группа торговых кнопок
        trading_group = QGroupBox("🎯 Торговые операции")
        trading_layout = QVBoxLayout(trading_group)
        
        # Кнопка покупки
        self.buy_button = QPushButton("💰 Купить самый дешевый тикер")
        self.buy_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.buy_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #229954;
            }
        """)
        self.buy_button.clicked.connect(self.on_buy_clicked)
        trading_layout.addWidget(self.buy_button)
        
        # Кнопка продажи
        self.sell_button = QPushButton("💸 Продать самый дешевый актив")
        self.sell_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.sell_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
        self.sell_button.clicked.connect(self.on_sell_clicked)
        trading_layout.addWidget(self.sell_button)
        
        layout.addWidget(trading_group)
        
        # Группа логов
        logs_group = QGroupBox("📝 Логи операций")
        logs_layout = QVBoxLayout(logs_group)
        
        self.logs_text = QTextEdit()
        self.logs_text.setFont(QFont("Consolas", 9))
        self.logs_text.setReadOnly(True)
        self.logs_text.setMaximumHeight(300)
        logs_layout.addWidget(self.logs_text)
        
        layout.addWidget(logs_group)
        
        return panel
    
    def start_trading_worker(self):
        """Запуск рабочего потока"""
        if not self.api_key or not self.api_secret:
            self.add_log("❌ API ключи не загружены")
            return
        
        self.trading_worker = TradingWorker(self.api_key, self.api_secret, testnet=True)
        
        # Подключение сигналов
        self.trading_worker.balance_updated.connect(self.update_balance_display)
        self.trading_worker.positions_updated.connect(self.update_positions_display)
        self.trading_worker.trade_executed.connect(self.on_trade_executed)
        self.trading_worker.log_message.connect(self.add_log)
        self.trading_worker.error_occurred.connect(self.add_error_log)
        
        # Запуск потока
        self.trading_worker.start()
        self.add_log("🚀 Торговый поток запущен")
    
    def on_buy_clicked(self):
        """Обработка нажатия кнопки покупки"""
        if self.trading_worker:
            self.buy_button.setEnabled(False)
            self.add_log("🔄 Запуск покупки самого дешевого тикера...")
            
            # Запускаем покупку асинхронно
            QTimer.singleShot(100, self.execute_buy)
    
    def execute_buy(self):
        """Выполнение покупки"""
        try:
            self.trading_worker.buy_cheapest_ticker()
        finally:
            # Включаем кнопку обратно через 3 секунды
            QTimer.singleShot(3000, lambda: self.buy_button.setEnabled(True))
    
    def on_sell_clicked(self):
        """Обработка нажатия кнопки продажи"""
        if self.trading_worker:
            self.sell_button.setEnabled(False)
            self.add_log("🔄 Запуск продажи самого дешевого актива...")
            
            # Запускаем продажу асинхронно
            QTimer.singleShot(100, self.execute_sell)
    
    def execute_sell(self):
        """Выполнение продажи"""
        try:
            self.trading_worker.sell_cheapest_position()
        finally:
            # Включаем кнопку обратно через 3 секунды
            QTimer.singleShot(3000, lambda: self.sell_button.setEnabled(True))
    
    def update_balance_display(self, balance_info: dict):
        """Обновление отображения баланса"""
        self.current_balance = balance_info
        
        # Обновляем общий баланс
        total_balance = balance_info.get('totalWalletBalance', '0')
        available_balance = balance_info.get('totalAvailableBalance', '0')
        
        self.balance_label.setText(
            f"Общий баланс: ${float(total_balance):.2f} | "
            f"Доступно: ${float(available_balance):.2f}"
        )
        
        # Обновляем таблицу монет
        coins = balance_info.get('coins', [])
        self.coins_table.setRowCount(len(coins))
        
        for i, coin in enumerate(coins):
            coin_name = coin.get('coin', '')
            wallet_balance = coin.get('walletBalance', '0')
            usd_value = coin.get('usdValue', '0')
            
            self.coins_table.setItem(i, 0, QTableWidgetItem(coin_name))
            self.coins_table.setItem(i, 1, QTableWidgetItem(f"{float(wallet_balance):.6f}"))
            self.coins_table.setItem(i, 2, QTableWidgetItem(f"${float(usd_value):.2f}"))
    
    def update_positions_display(self, positions: list):
        """Обновление отображения позиций"""
        self.current_positions = positions
        
        self.positions_table.setRowCount(len(positions))
        
        for i, position in enumerate(positions):
            symbol = position.get('symbol', '')
            side = position.get('side', '')
            qty = position.get('qty', '0')
            price = position.get('price', '0')
            
            self.positions_table.setItem(i, 0, QTableWidgetItem(symbol))
            self.positions_table.setItem(i, 1, QTableWidgetItem(side))
            self.positions_table.setItem(i, 2, QTableWidgetItem(qty))
            self.positions_table.setItem(i, 3, QTableWidgetItem(price))
    
    def on_trade_executed(self, trade_info: dict):
        """Обработка выполненной сделки"""
        symbol = trade_info.get('symbol', '')
        side = trade_info.get('side', '')
        qty = trade_info.get('qty', '')
        
        self.add_log(f"✅ Сделка выполнена: {side} {qty} {symbol}")
        self.status_bar.showMessage(f"Последняя сделка: {side} {symbol}", 10000)
    
    def add_log(self, message: str):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs_text.append(log_entry)
        
        # Прокручиваем к последнему сообщению
        cursor = self.logs_text.textCursor()
        cursor.movePosition(cursor.End)
        self.logs_text.setTextCursor(cursor)
    
    def add_error_log(self, message: str):
        """Добавление сообщения об ошибке"""
        self.add_log(f"❌ {message}")
    
    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        if self.trading_worker:
            self.trading_worker.stop()
        event.accept()


def main():
    """Главная функция"""
    app = QApplication(sys.argv)
    
    # Настройка стиля приложения
    app.setStyle('Fusion')
    
    # Создание и показ главного окна
    window = TestTradingApp()
    window.show()
    
    # Запуск приложения
    sys.exit(app.exec())


if __name__ == "__main__":
    main()