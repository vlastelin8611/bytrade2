#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portfolio Viewer - Программа для просмотра баланса и портфолио
Использует API Bybit для получения данных о балансе и монетах
"""

import sys
import os
import logging
import traceback
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
        QTableWidget, QTableWidgetItem, QPushButton, QLabel, QGroupBox,
        QProgressBar, QTextEdit, QTabWidget, QGridLayout, QFrame,
        QHeaderView, QMessageBox, QSplitter
    )
    from PySide6.QtCore import QThread, Signal, QTimer, Qt
    from PySide6.QtGui import QFont, QPalette, QColor
except ImportError:
    print("❌ Ошибка: PySide6 не установлен")
    print("Установите: pip install PySide6")
    sys.exit(1)

try:
    from src.api.bybit_client import BybitClient
    from config import API_KEY, API_SECRET
except ImportError as e:
    print(f"❌ Ошибка импорта модулей: {e}")
    print("Убедитесь, что все файлы находятся в правильных директориях")
    traceback.print_exc()
    sys.exit(1)


class BalanceWorker(QThread):
    """Рабочий поток для получения данных баланса"""
    
    balance_updated = Signal(dict)
    fund_balance_updated = Signal(dict)
    error_occurred = Signal(str)
    log_message = Signal(str)
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.running = False
        
        # Инициализация клиента API
        self.bybit_client = None
        
        # Настройка логирования
        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f'portfolio_viewer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Логи сохраняются в файл: {log_file}")
    
    def run(self):
        """Основной цикл получения данных"""
        try:
            self.running = True
            self.log_message.emit("Инициализация API клиента...")
            
            # Инициализация клиента API
            self.bybit_client = BybitClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            
            self.log_message.emit(f"✅ API клиент инициализирован (testnet: {self.testnet})")
            
            # Основной цикл обновления данных
            while self.running:
                try:
                    # Получение UNIFIED баланса
                    self.log_message.emit("🔄 Получение UNIFIED баланса...")
                    unified_balance = self.bybit_client.get_unified_balance_flat()
                    if unified_balance:
                        self.balance_updated.emit(unified_balance)
                        self.log_message.emit("✅ UNIFIED баланс обновлен")
                    
                    # Получение FUND баланса
                    self.log_message.emit("🔄 Получение FUND баланса...")
                    fund_balance = self.bybit_client.get_fund_balance_flat()
                    if fund_balance:
                        self.fund_balance_updated.emit(fund_balance)
                        self.log_message.emit("✅ FUND баланс обновлен")
                    
                except Exception as e:
                    error_msg = f"Ошибка получения баланса: {str(e)}"
                    self.logger.error(error_msg)
                    self.error_occurred.emit(error_msg)
                
                # Пауза между обновлениями (30 секунд)
                self.msleep(30000)
                
        except Exception as e:
            error_msg = f"Критическая ошибка в рабочем потоке: {str(e)}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)
    
    def stop(self):
        """Остановка рабочего потока"""
        self.running = False
        self.quit()
        self.wait()


class PortfolioViewer(QMainWindow):
    """Главное окно программы просмотра портфолио"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Portfolio Viewer - Просмотр баланса и портфолио")
        self.setGeometry(100, 100, 1200, 800)
        
        # Инициализация переменных
        self.balance_worker = None
        self.current_unified_balance = {}
        self.current_fund_balance = {}
        
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        
        # Создание интерфейса
        self.setup_ui()
        
        # Инициализация рабочего потока
        self.init_balance_worker()
    
    def setup_ui(self):
        """Создание пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        
        # Заголовок
        title_label = QLabel("Portfolio Viewer")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)
        
        # Кнопки управления
        controls_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("🔄 Обновить данные")
        self.refresh_button.clicked.connect(self.manual_refresh)
        controls_layout.addWidget(self.refresh_button)
        
        self.start_button = QPushButton("▶️ Запустить автообновление")
        self.start_button.clicked.connect(self.start_auto_update)
        controls_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("⏹️ Остановить автообновление")
        self.stop_button.clicked.connect(self.stop_auto_update)
        self.stop_button.setEnabled(False)
        controls_layout.addWidget(self.stop_button)
        
        controls_layout.addStretch()
        main_layout.addLayout(controls_layout)
        
        # Создание вкладок
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Вкладка UNIFIED баланса
        self.create_unified_tab()
        
        # Вкладка FUND баланса
        self.create_fund_tab()
        
        # Вкладка логов
        self.create_logs_tab()
        
        # Статус бар
        self.status_label = QLabel("Готов к работе")
        main_layout.addWidget(self.status_label)
    
    def create_unified_tab(self):
        """Создание вкладки UNIFIED баланса"""
        unified_widget = QWidget()
        layout = QVBoxLayout(unified_widget)
        
        # Общая информация
        info_group = QGroupBox("Общая информация UNIFIED кошелька")
        info_layout = QGridLayout(info_group)
        
        self.unified_total_label = QLabel("Общий баланс: $0.00")
        self.unified_total_label.setFont(QFont("Arial", 12, QFont.Bold))
        info_layout.addWidget(self.unified_total_label, 0, 0)
        
        self.unified_available_label = QLabel("Доступно: $0.00")
        info_layout.addWidget(self.unified_available_label, 0, 1)
        
        self.unified_coins_count_label = QLabel("Монет: 0")
        info_layout.addWidget(self.unified_coins_count_label, 1, 0)
        
        layout.addWidget(info_group)
        
        # Таблица монет
        coins_group = QGroupBox("Монеты в UNIFIED кошельке")
        coins_layout = QVBoxLayout(coins_group)
        
        self.unified_table = QTableWidget()
        self.unified_table.setColumnCount(4)
        self.unified_table.setHorizontalHeaderLabels([
            "Монета", "Количество", "USD стоимость", "Доступно к выводу"
        ])
        
        # Настройка таблицы
        header = self.unified_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        coins_layout.addWidget(self.unified_table)
        layout.addWidget(coins_group)
        
        self.tabs.addTab(unified_widget, "UNIFIED Кошелек")
    
    def create_fund_tab(self):
        """Создание вкладки FUND баланса"""
        fund_widget = QWidget()
        layout = QVBoxLayout(fund_widget)
        
        # Общая информация
        info_group = QGroupBox("Общая информация FUND кошелька")
        info_layout = QGridLayout(info_group)
        
        self.fund_coins_count_label = QLabel("Монет: 0")
        info_layout.addWidget(self.fund_coins_count_label, 0, 0)
        
        layout.addWidget(info_group)
        
        # Таблица монет
        coins_group = QGroupBox("Монеты в FUND кошельке")
        coins_layout = QVBoxLayout(coins_group)
        
        self.fund_table = QTableWidget()
        self.fund_table.setColumnCount(2)
        self.fund_table.setHorizontalHeaderLabels([
            "Монета", "Количество"
        ])
        
        # Настройка таблицы
        header = self.fund_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        
        coins_layout.addWidget(self.fund_table)
        layout.addWidget(coins_group)
        
        self.tabs.addTab(fund_widget, "FUND Кошелек")
    
    def create_logs_tab(self):
        """Создание вкладки логов"""
        logs_widget = QWidget()
        layout = QVBoxLayout(logs_widget)
        
        # Заголовок
        logs_label = QLabel("Логи операций")
        logs_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(logs_label)
        
        # Текстовое поле для логов
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.logs_text)
        
        # Кнопка очистки логов
        clear_button = QPushButton("🗑️ Очистить логи")
        clear_button.clicked.connect(self.clear_logs)
        layout.addWidget(clear_button)
        
        self.tabs.addTab(logs_widget, "Логи")
    
    def init_balance_worker(self):
        """Инициализация рабочего потока"""
        try:
            self.balance_worker = BalanceWorker(API_KEY, API_SECRET, testnet=True)
            
            # Подключение сигналов
            self.balance_worker.balance_updated.connect(self.update_unified_balance)
            self.balance_worker.fund_balance_updated.connect(self.update_fund_balance)
            self.balance_worker.error_occurred.connect(self.handle_error)
            self.balance_worker.log_message.connect(self.add_log_message)
            
            self.add_log_message("✅ Рабочий поток инициализирован")
            
        except Exception as e:
            error_msg = f"❌ Ошибка инициализации: {str(e)}"
            self.add_log_message(error_msg)
            QMessageBox.critical(self, "Ошибка", error_msg)
    
    def start_auto_update(self):
        """Запуск автоматического обновления"""
        if self.balance_worker and not self.balance_worker.isRunning():
            self.balance_worker.start()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.status_label.setText("Автообновление запущено")
            self.add_log_message("🚀 Автообновление запущено")
    
    def stop_auto_update(self):
        """Остановка автоматического обновления"""
        if self.balance_worker and self.balance_worker.isRunning():
            self.balance_worker.stop()
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.status_label.setText("Автообновление остановлено")
            self.add_log_message("⏹️ Автообновление остановлено")
    
    def manual_refresh(self):
        """Ручное обновление данных"""
        if not self.balance_worker:
            self.add_log_message("❌ Рабочий поток не инициализирован")
            return
        
        try:
            self.add_log_message("🔄 Ручное обновление данных...")
            
            # Создаем временный клиент для разового запроса
            client = BybitClient(API_KEY, API_SECRET, testnet=True)
            
            # Получение UNIFIED баланса
            unified_balance = client.get_unified_balance_flat()
            if unified_balance:
                self.update_unified_balance(unified_balance)
            
            # Получение FUND баланса
            fund_balance = client.get_fund_balance_flat()
            if fund_balance:
                self.update_fund_balance(fund_balance)
            
            self.add_log_message("✅ Ручное обновление завершено")
            
        except Exception as e:
            error_msg = f"❌ Ошибка ручного обновления: {str(e)}"
            self.add_log_message(error_msg)
            self.logger.error(error_msg)
    
    def update_unified_balance(self, balance_info: dict):
        """Обновление UNIFIED баланса"""
        try:
            self.current_unified_balance = balance_info
            
            # Обновление общей информации
            total_usd = balance_info.get('total_wallet_usd', Decimal('0'))
            available_usd = balance_info.get('total_available_usd', Decimal('0'))
            coins = balance_info.get('coins', {})
            
            self.unified_total_label.setText(f"Общий баланс: ${float(total_usd):.2f}")
            self.unified_available_label.setText(f"Доступно: ${float(available_usd):.2f}")
            self.unified_coins_count_label.setText(f"Монет: {len(coins)}")
            
            # Обновление таблицы монет
            self.unified_table.setRowCount(0)
            
            for coin_name, balance in coins.items():
                if float(balance) > 0:  # Показываем только монеты с балансом > 0
                    row_position = self.unified_table.rowCount()
                    self.unified_table.insertRow(row_position)
                    
                    # Название монеты
                    self.unified_table.setItem(row_position, 0, QTableWidgetItem(coin_name))
                    
                    # Количество
                    balance_str = f"{float(balance):.8f}".rstrip('0').rstrip('.') if float(balance) < 1 else f"{float(balance):.2f}"
                    self.unified_table.setItem(row_position, 1, QTableWidgetItem(balance_str))
                    
                    # USD стоимость (пока N/A)
                    self.unified_table.setItem(row_position, 2, QTableWidgetItem("N/A"))
                    
                    # Доступно к выводу (пока N/A)
                    self.unified_table.setItem(row_position, 3, QTableWidgetItem("N/A"))
            
            self.add_log_message(f"✅ UNIFIED баланс обновлен: {len(coins)} монет, ${float(total_usd):.2f}")
            
        except Exception as e:
            error_msg = f"❌ Ошибка обновления UNIFIED баланса: {str(e)}"
            self.add_log_message(error_msg)
            self.logger.error(error_msg)
    
    def update_fund_balance(self, balance_info: dict):
        """Обновление FUND баланса"""
        try:
            self.current_fund_balance = balance_info
            
            coins = balance_info.get('coins', {})
            
            # Обновление общей информации
            self.fund_coins_count_label.setText(f"Монет: {len(coins)}")
            
            # Обновление таблицы монет
            self.fund_table.setRowCount(0)
            
            for coin_name, balance in coins.items():
                if float(balance) > 0:  # Показываем только монеты с балансом > 0
                    row_position = self.fund_table.rowCount()
                    self.fund_table.insertRow(row_position)
                    
                    # Название монеты
                    self.fund_table.setItem(row_position, 0, QTableWidgetItem(coin_name))
                    
                    # Количество
                    balance_str = f"{float(balance):.8f}".rstrip('0').rstrip('.') if float(balance) < 1 else f"{float(balance):.2f}"
                    self.fund_table.setItem(row_position, 1, QTableWidgetItem(balance_str))
            
            self.add_log_message(f"✅ FUND баланс обновлен: {len(coins)} монет")
            
        except Exception as e:
            error_msg = f"❌ Ошибка обновления FUND баланса: {str(e)}"
            self.add_log_message(error_msg)
            self.logger.error(error_msg)
    
    def handle_error(self, error_message: str):
        """Обработка ошибок"""
        self.add_log_message(f"❌ {error_message}")
        self.status_label.setText(f"Ошибка: {error_message}")
    
    def add_log_message(self, message: str):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.logs_text.append(formatted_message)
        
        # Автопрокрутка к последнему сообщению
        cursor = self.logs_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.logs_text.setTextCursor(cursor)
        
        # Логирование в файл
        self.logger.info(message)
    
    def clear_logs(self):
        """Очистка логов"""
        self.logs_text.clear()
        self.add_log_message("🗑️ Логи очищены")
    
    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        if self.balance_worker and self.balance_worker.isRunning():
            self.balance_worker.stop()
        event.accept()


def main():
    """Главная функция"""
    app = QApplication(sys.argv)
    
    # Проверка наличия API ключей
    if not API_KEY or not API_SECRET:
        QMessageBox.critical(None, "Ошибка", 
                           "API ключи не настроены!\n"
                           "Проверьте файл config.py")
        sys.exit(1)
    
    # Создание и показ главного окна
    window = PortfolioViewer()
    window.show()
    
    # Запуск приложения
    sys.exit(app.exec())


if __name__ == "__main__":
    main()