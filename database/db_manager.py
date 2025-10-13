import sqlite3
import threading
import logging
from datetime import datetime
import json
from typing import Optional, Dict, Any, List

class DatabaseManager:
    """
    Менеджер базы данных для торгового бота
    Обеспечивает потокобезопасную работу с SQLite базой данных
    """
    
    def __init__(self, db_path: str = "data/trading_bot.db"):
        """
        Инициализация менеджера базы данных
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # Создаем таблицы при инициализации
        self._create_tables()
    
    def _get_connection(self):
        """Получение подключения к базе данных"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
        return conn
    
    def _create_tables(self):
        """Создание необходимых таблиц"""
        with self.lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # Таблица системных логов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        component TEXT,
                        details TEXT
                    )
                ''')
                
                # Таблица сделок
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        price REAL NOT NULL,
                        order_id TEXT,
                        strategy TEXT,
                        profit_loss REAL,
                        commission REAL,
                        status TEXT DEFAULT 'executed'
                    )
                ''')
                
                # Таблица позиций
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        size REAL NOT NULL,
                        entry_price REAL NOT NULL,
                        current_price REAL,
                        unrealized_pnl REAL,
                        strategy TEXT,
                        status TEXT DEFAULT 'open'
                    )
                ''')
                
                # Таблица истории цен
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS price_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT NOT NULL,
                        price REAL NOT NULL,
                        volume REAL,
                        high REAL,
                        low REAL,
                        open_price REAL,
                        timeframe TEXT DEFAULT '1m'
                    )
                ''')
                
                # Таблица доступных символов
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS available_symbols (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT UNIQUE NOT NULL,
                        base_asset TEXT NOT NULL,
                        quote_asset TEXT NOT NULL,
                        status TEXT DEFAULT 'active',
                        min_order_qty REAL,
                        max_order_qty REAL,
                        tick_size REAL,
                        lot_size_filter REAL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                self.logger.info("Database tables created successfully")
                
            except Exception as e:
                self.logger.error(f"Error creating tables: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def log_system_action(self, level: str, message: str, component: str = None, details: Dict = None):
        """
        Логирование системных действий
        
        Args:
            level: Уровень лога (INFO, WARNING, ERROR, etc.)
            message: Сообщение
            component: Компонент системы
            details: Дополнительные детали в формате словаря
        """
        with self.lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                details_json = json.dumps(details) if details else None
                
                cursor.execute('''
                    INSERT INTO system_logs (level, message, component, details)
                    VALUES (?, ?, ?, ?)
                ''', (level, message, component, details_json))
                
                conn.commit()
                
            except Exception as e:
                self.logger.error(f"Error logging system action: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def log_trade(self, symbol: str, side: str, quantity: float, price: float, 
                  order_id: str = None, strategy: str = None, profit_loss: float = None, 
                  commission: float = None):
        """
        Логирование сделки
        
        Args:
            symbol: Торговая пара
            side: Сторона сделки (buy/sell)
            quantity: Количество
            price: Цена
            order_id: ID ордера
            strategy: Стратегия
            profit_loss: Прибыль/убыток
            commission: Комиссия
        """
        with self.lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO trades (symbol, side, quantity, price, order_id, 
                                      strategy, profit_loss, commission)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (symbol, side, quantity, price, order_id, strategy, profit_loss, commission))
                
                conn.commit()
                self.logger.info(f"Trade logged: {side} {quantity} {symbol} at {price}")
                
            except Exception as e:
                self.logger.error(f"Error logging trade: {e}")
                conn.rollback()
            finally:
                conn.close()

    def log_analysis(self, analysis_data: Dict[str, Any]):
        """
        Логирование результатов ML анализа
        
        Args:
            analysis_data: Словарь с данными анализа, содержащий:
                - symbol: торговая пара
                - price: текущая цена
                - features: признаки для ML
                - regime: рыночный режим
                - prediction: предсказание модели
                - confidence: уверенность модели
                - signal: торговый сигнал
        """
        with self.lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # Создаем таблицу для ML анализа если её нет
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ml_analysis (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT NOT NULL,
                        price REAL NOT NULL,
                        features TEXT,
                        regime TEXT,
                        prediction REAL,
                        confidence REAL,
                        signal TEXT
                    )
                ''')
                
                # Преобразуем features в JSON строку если это словарь или список
                features_json = None
                if 'features' in analysis_data:
                    if isinstance(analysis_data['features'], (dict, list)):
                        features_json = json.dumps(analysis_data['features'])
                    else:
                        features_json = str(analysis_data['features'])
                
                cursor.execute('''
                    INSERT INTO ml_analysis (symbol, price, features, regime, prediction, confidence, signal)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    analysis_data.get('symbol'),
                    analysis_data.get('price'),
                    features_json,
                    analysis_data.get('regime'),
                    analysis_data.get('prediction'),
                    analysis_data.get('confidence'),
                    analysis_data.get('signal')
                ))
                
                conn.commit()
                
                # Логируем системное действие
                self.log_system_action(
                    'INFO', 
                    f"ML analysis logged for {analysis_data.get('symbol')}", 
                    'ML_STRATEGY',
                    {'prediction': analysis_data.get('prediction'), 'confidence': analysis_data.get('confidence')}
                )
                
            except Exception as e:
                self.logger.error(f"Error logging ML analysis: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def get_recent_trades(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """
        Получение последних сделок
        
        Args:
            symbol: Торговая пара (опционально)
            limit: Количество записей
            
        Returns:
            Список сделок
        """
        with self.lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                if symbol:
                    cursor.execute('''
                        SELECT * FROM trades 
                        WHERE symbol = ? 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    ''', (symbol, limit))
                else:
                    cursor.execute('''
                        SELECT * FROM trades 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    ''', (limit,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
            except Exception as e:
                self.logger.error(f"Error getting recent trades: {e}")
                return []
            finally:
                conn.close()
    
    def get_system_logs(self, level: str = None, component: str = None, limit: int = 100) -> List[Dict]:
        """
        Получение системных логов
        
        Args:
            level: Уровень лога (опционально)
            component: Компонент (опционально)
            limit: Количество записей
            
        Returns:
            Список логов
        """
        with self.lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                query = "SELECT * FROM system_logs WHERE 1=1"
                params = []
                
                if level:
                    query += " AND level = ?"
                    params.append(level)
                
                if component:
                    query += " AND component = ?"
                    params.append(component)
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
            except Exception as e:
                self.logger.error(f"Error getting system logs: {e}")
                return []
            finally:
                conn.close()
    
    def cleanup_old_data(self, days: int = 30):
        """
        Очистка старых данных
        
        Args:
            days: Количество дней для хранения данных
        """
        with self.lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # Удаляем старые логи
                cursor.execute('''
                    DELETE FROM system_logs 
                    WHERE timestamp < datetime('now', '-{} days')
                '''.format(days))
                
                # Удаляем старую историю цен
                cursor.execute('''
                    DELETE FROM price_history 
                    WHERE timestamp < datetime('now', '-{} days')
                '''.format(days))
                
                conn.commit()
                self.logger.info(f"Cleaned up data older than {days} days")
                
            except Exception as e:
                self.logger.error(f"Error cleaning up old data: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def close(self):
        """Закрытие соединения с базой данных"""
        # SQLite автоматически закрывает соединения при завершении работы
        self.logger.info("Database manager closed")