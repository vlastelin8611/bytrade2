#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер базы данных для детального логирования торговых операций
Ведет подробные логи всех действий программы для анализа и обучения
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import threading
from contextlib import contextmanager

class DatabaseManager:
    """
    Менеджер базы данных для торгового бота
    Обеспечивает детальное логирование всех операций
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        
        # Путь к базе данных
        if db_path is None:
            db_dir = Path(__file__).parent.parent.parent / 'data'
            db_dir.mkdir(exist_ok=True)
            self.db_path = db_dir / 'trading_bot.db'
        else:
            self.db_path = Path(db_path)
        
        # Блокировка для потокобезопасности
        self._lock = threading.Lock()
        
        # Инициализация базы данных
        self.init_database()
        
        self.logger.info(f"Инициализирован менеджер БД: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для безопасной работы с БД"""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Ошибка работы с БД: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def init_database(self):
        """Инициализация структуры базы данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Таблица для логирования всех действий системы
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        level TEXT NOT NULL,
                        component TEXT NOT NULL,
                        action TEXT NOT NULL,
                        details TEXT,
                        execution_time_ms REAL,
                        session_id TEXT,
                        thread_id TEXT
                    )
                """)
                
                # Таблица торговых операций
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        order_type TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        price REAL,
                        order_id TEXT,
                        status TEXT NOT NULL,
                        pnl REAL,
                        commission REAL,
                        analysis_data TEXT,
                        execution_time_ms REAL
                    )
                """)
                
                # Индексы для оптимизации запросов
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
                
                conn.commit()
                self.logger.info("База данных инициализирована")
                
        except Exception as e:
            self.logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    def log_system_action(self, level: str, component: str, action: str, 
                         details: Optional[Dict] = None, execution_time_ms: Optional[float] = None,
                         session_id: Optional[str] = None):
        """Логирование системного действия"""
        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO system_logs 
                        (level, component, action, details, execution_time_ms, session_id, thread_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        level,
                        component,
                        action,
                        json.dumps(details) if details else None,
                        execution_time_ms,
                        session_id,
                        str(threading.current_thread().ident)
                    ))
                    
                    conn.commit()
                    
        except Exception as e:
            self.logger.error(f"Ошибка логирования системного действия: {e}")
    
    def log_trade(self, trade_info: Dict):
        """Логирование торговой операции"""
        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO trades 
                        (symbol, side, order_type, quantity, price, order_id, status, 
                         pnl, commission, analysis_data, execution_time_ms)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade_info.get('symbol'),
                        trade_info.get('side'),
                        trade_info.get('order_type', 'Market'),
                        trade_info.get('size', 0),
                        trade_info.get('price'),
                        trade_info.get('order_id'),
                        trade_info.get('status', 'Executed'),
                        trade_info.get('pnl'),
                        trade_info.get('commission'),
                        json.dumps(trade_info.get('analysis', {})),
                        trade_info.get('execution_time_ms')
                    ))
                    
                    conn.commit()
                    
                    # Логирование системного действия
                    self.log_system_action(
                        'INFO', 'TRADING', 'TRADE_EXECUTED',
                        {'symbol': trade_info.get('symbol'), 'side': trade_info.get('side')}
                    )
                    
        except Exception as e:
            self.logger.error(f"Ошибка логирования торговли: {e}")
    
    def get_recent_trades(self, limit: int = 100, symbol: Optional[str] = None) -> List[Dict]:
        """Получение последних торговых операций"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if symbol:
                    cursor.execute("""
                        SELECT * FROM trades 
                        WHERE symbol = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (symbol, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM trades 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (limit,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            self.logger.error(f"Ошибка получения торговых операций: {e}")
            return []
    
    def get_system_logs(self, level: Optional[str] = None, component: Optional[str] = None,
                       hours_back: int = 24, limit: int = 1000) -> List[Dict]:
        """Получение системных логов"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT * FROM system_logs 
                    WHERE timestamp >= datetime('now', '-{} hours')
                """.format(hours_back)
                
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
            self.logger.error(f"Ошибка получения системных логов: {e}")
            return []
    
    def log_account_snapshot(self, account_data: Dict[str, Any]):
        """Логирование снимка состояния аккаунта"""
        try:
            self.log_system_action(
                level='INFO',
                component='ACCOUNT',
                action='account_snapshot',
                details=account_data,
                execution_time_ms=account_data.get('execution_time_ms'),
                session_id=account_data.get('session_id')
            )
        except Exception as e:
            self.logger.error(f"Ошибка логирования снимка аккаунта: {e}")
    
    def log_entry(self, entry: Dict[str, Any]):
        """Универсальный метод логирования с поддержкой нового формата"""
        try:
            level = entry.get('level', 'INFO')
            logger_name = entry.get('logger_name', 'SYSTEM')
            message = entry.get('message', '')
            session_id = entry.get('session_id')
            exception = entry.get('exception')
            
            # Формирование деталей для старого формата
            details = {}
            if exception:
                details['exception'] = str(exception)
                details['exception_type'] = type(exception).__name__ if hasattr(exception, '__class__') else 'Exception'
            
            # Используем существующий метод log_system_action
            self.log_system_action(
                level=level,
                component=logger_name,
                action=message,
                details=details if details else None,
                session_id=session_id
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка универсального логирования: {e}")