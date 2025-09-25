import os
import sys
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit,
    QFormLayout, QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QTabWidget, QScrollArea, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QColor

class StrategiesTab(QWidget):
    """Класс для вкладки стратегий"""
    
    def __init__(self, config=None, db_manager=None, api_client=None, strategy_engine=None):
        super().__init__()
        self.config = config
        self.db_manager = db_manager
        self.api_client = api_client
        self.strategy_engine = strategy_engine
        self.is_trading_active = False
        
        self.init_ui()
        
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        main_layout = QVBoxLayout(self)
        
        # Заголовок и кнопки управления
        header_layout = QHBoxLayout()
        title_label = QLabel("Управление стратегиями")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        # Кнопка активации торговли
        self.activate_trading_btn = QPushButton("Включить торговлю")
        self.activate_trading_btn.setMinimumSize(180, 30)
        self.activate_trading_btn.setStyleSheet("background-color: #3498db; color: white;")
        self.activate_trading_btn.clicked.connect(self.toggle_trading)
        
        # Кнопка обновления стратегий
        refresh_btn = QPushButton("🔄 Обновить стратегии")
        refresh_btn.setMinimumSize(180, 30)
        refresh_btn.clicked.connect(self.refresh_strategies)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.activate_trading_btn)
        header_layout.addWidget(refresh_btn)
        
        main_layout.addLayout(header_layout)
        
        # Секция настройки стратегий
        strategies_group = QGroupBox("Настройки стратегий")
        strategies_layout = QVBoxLayout(strategies_group)
        
        # Выбор стратегии
        strategy_form = QFormLayout()
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["Адаптивная ML", "Скальпинг", "Трендовая"])
        strategy_form.addRow("Стратегия:", self.strategy_combo)
        
        # Параметры стратегии
        self.risk_level = QComboBox()
        self.risk_level.addItems(["Низкий", "Средний", "Высокий"])
        strategy_form.addRow("Уровень риска:", self.risk_level)
        
        self.trade_amount = QDoubleSpinBox()
        self.trade_amount.setRange(10, 1000)
        self.trade_amount.setValue(100)
        self.trade_amount.setSingleStep(10)
        strategy_form.addRow("Сумма сделки (USDT):", self.trade_amount)
        
        strategies_layout.addLayout(strategy_form)
        
        # Добавляем группу настроек в основной макет
        main_layout.addWidget(strategies_group)
        
        # Статус стратегии
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Статус: Неактивна")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        main_layout.addLayout(status_layout)
        main_layout.addStretch()
    
    def toggle_trading(self):
        """Переключение состояния торговли"""
        try:
            if not self.is_trading_active:
                # Активация торговли
                self.activate_trading()
            else:
                # Деактивация торговли
                self.deactivate_trading()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при переключении торговли: {str(e)}")
    
    def activate_trading(self):
        """Активация торговли"""
        try:
            # Проверка наличия API клиента
            if not self.api_client:
                QMessageBox.warning(self, "Предупреждение", "API клиент не инициализирован")
                return
            
            # Проверка наличия движка стратегий
            if not self.strategy_engine:
                QMessageBox.warning(self, "Предупреждение", "Движок стратегий не инициализирован")
                return
            
            # Получение параметров стратегии
            strategy_name = self.strategy_combo.currentText()
            risk_level = self.risk_level.currentText()
            trade_amount = self.trade_amount.value()
            
            # Активация стратегии в движке стратегий
            success = self.strategy_engine.activate_strategy(
                strategy_name=strategy_name,
                risk_level=risk_level,
                trade_amount=trade_amount
            )
            
            if success:
                # Обновление UI
                self.is_trading_active = True
                self.activate_trading_btn.setText("Отключить торговлю")
                self.activate_trading_btn.setStyleSheet("background-color: #e74c3c; color: white;")
                self.status_label.setText("Статус: Активна")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                
                QMessageBox.information(self, "Успех", f"Стратегия {strategy_name} успешно активирована")
            else:
                QMessageBox.warning(self, "Предупреждение", "Не удалось активировать стратегию")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при активации стратегии: {str(e)}")
    
    def deactivate_trading(self):
        """Деактивация торговли"""
        try:
            # Проверка наличия движка стратегий
            if not self.strategy_engine:
                QMessageBox.warning(self, "Предупреждение", "Движок стратегий не инициализирован")
                return
            
            # Деактивация стратегии в движке стратегий
            success = self.strategy_engine.deactivate_strategy()
            
            if success:
                # Обновление UI
                self.is_trading_active = False
                self.activate_trading_btn.setText("Включить торговлю")
                self.activate_trading_btn.setStyleSheet("background-color: #3498db; color: white;")
                self.status_label.setText("Статус: Неактивна")
                self.status_label.setStyleSheet("color: gray; font-weight: bold;")
                
                QMessageBox.information(self, "Успех", "Стратегия успешно деактивирована")
            else:
                QMessageBox.warning(self, "Предупреждение", "Не удалось деактивировать стратегию")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при деактивации стратегии: {str(e)}")
    
    def refresh_strategies(self):
        """Обновление списка стратегий"""
        try:
            # Здесь можно добавить логику обновления списка стратегий
            QMessageBox.information(self, "Информация", "Список стратегий обновлен")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при обновлении стратегий: {str(e)}")