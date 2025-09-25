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
                
                # Таблица для хранения позиций
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT NOT NULL,
                        category TEXT NOT NULL,
                        side TEXT NOT NULL,
                        size REAL NOT NULL,
                        entry_price REAL NOT NULL,
                        mark_price REAL,
                        pnl REAL,
                        leverage TEXT,
                        position_value REAL,
                        position_idx INTEGER,
                        risk_id INTEGER,
                        position_status TEXT,
                        auto_add_margin INTEGER,
                        position_data TEXT,
                        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Таблица для хранения истории цен
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS price_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT NOT NULL,
                        price REAL NOT NULL,
                        price_1h_ago REAL,
                        price_24h_ago REAL,
                        price_7d_ago REAL,
                        price_30d_ago REAL,
                        price_180d_ago REAL,
                        volume_24h REAL,
                        change_1h REAL,
                        change_24h REAL,
                        change_7d REAL,
                        change_30d REAL,
                        change_180d REAL,
                        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Таблица для хранения доступных для торговли символов
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS available_symbols (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT NOT NULL,
                        category TEXT NOT NULL,
                        base_coin TEXT NOT NULL,
                        quote_coin TEXT NOT NULL,
                        price_scale INTEGER,
                        taker_fee REAL,
                        maker_fee REAL,
                        min_leverage REAL,
                        max_leverage REAL,
                        leverage_step REAL,
                        min_price REAL,
                        max_price REAL,
                        tick_size REAL,
                        min_order_qty REAL,
                        max_order_qty REAL,
                        qty_step REAL,
                        post_only_max_order_qty REAL,
                        symbol_status TEXT,
                        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, category)
                    )
                """)
                
                # Индексы для оптимизации запросов
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON positions(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_symbol ON price_history(symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_timestamp ON price_history(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_available_symbols_symbol ON available_symbols(symbol)")
                
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
            self.logger.error(f"Ошибка логирования торговой операции: {e}")
    
    def log_analysis(self, analysis_data: Dict):
        """Логирование результатов анализа ML стратегии"""
        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Создаем таблицу для анализа если не существует
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS ml_analysis (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                            symbol TEXT,
                            current_price REAL,
                            features TEXT,
                            regime TEXT,
                            prediction TEXT,
                            confidence REAL,
                            signal TEXT
                        )
                    """)
                    
                    # Вставляем данные анализа
                    cursor.execute("""
                        INSERT INTO ml_analysis 
                        (symbol, current_price, features, regime, prediction, confidence, signal)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        analysis_data.get('symbol'),
                        analysis_data.get('current_price'),
                        json.dumps(analysis_data.get('features', [])),
                        json.dumps(analysis_data.get('regime', {})),
                        json.dumps(analysis_data.get('prediction', {})),
                        analysis_data.get('prediction', {}).get('confidence', 0.0),
                        analysis_data.get('prediction', {}).get('signal')
                    ))
                    
                    conn.commit()
                    
                    # Логирование системного действия
                    self.log_system_action(
                        'INFO', 'ML_STRATEGY', 'ANALYSIS_COMPLETED',
                        {
                            'symbol': analysis_data.get('symbol'),
                            'signal': analysis_data.get('prediction', {}).get('signal'),
                            'confidence': analysis_data.get('prediction', {}).get('confidence', 0.0)
                        }
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
            
    def save_positions(self, positions_data):
        """Сохранение позиций в базу данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Сначала удаляем все старые записи, так как мы всегда сохраняем актуальное состояние
                cursor.execute("DELETE FROM positions")
                
                # Вставляем новые данные
                for position in positions_data:
                    position_data_json = json.dumps(position)
                    cursor.execute("""
                        INSERT INTO positions (
                            symbol, category, side, size, entry_price, mark_price, pnl,
                            leverage, position_value, position_idx, risk_id, position_status,
                            auto_add_margin, position_data, last_updated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        position.get('symbol', ''),
                        position.get('category', ''),
                        position.get('side', ''),
                        float(position.get('size', 0)),
                        float(position.get('entryPrice', 0)),
                        float(position.get('markPrice', 0)),
                        float(position.get('unrealisedPnl', 0)),
                        position.get('leverage', ''),
                        float(position.get('positionValue', 0)),
                        int(position.get('positionIdx', 0)),
                        int(position.get('riskId', 0)) if position.get('riskId') else None,
                        position.get('positionStatus', ''),
                        int(position.get('autoAddMargin', 0)),
                        position_data_json
                    ))
                conn.commit()
                self.logger.info(f"Сохранено {len(positions_data)} позиций в базу данных")
                return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении позиций в базу данных: {e}")
            return False
            
    def get_positions(self, limit=100):
        """Получение текущих позиций из базы данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM positions 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Ошибка при получении позиций из базы данных: {e}")
            return []
            
    def get_price_history(self, symbol=None):
        """Получение истории цен из базы данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if symbol:
                    cursor.execute("""
                        SELECT * FROM price_history 
                        WHERE symbol = ?
                    """, (symbol,))
                    return cursor.fetchone()
                else:
                    cursor.execute("""
                        SELECT * FROM price_history
                    """)
                    return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Ошибка при получении истории цен из базы данных: {e}")
            return None
            
    def save_price_history(self, symbol, price_data):
        """Сохранение истории цен в базу данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем, есть ли уже запись для этого символа
                cursor.execute("SELECT id FROM price_history WHERE symbol = ?", (symbol,))
                existing_record = cursor.fetchone()
                
                if existing_record:
                    # Обновляем существующую запись
                    cursor.execute("""
                        UPDATE price_history SET 
                            price = ?, price_1h_ago = ?, price_24h_ago = ?, 
                            price_7d_ago = ?, price_30d_ago = ?, price_180d_ago = ?,
                            volume_24h = ?, change_1h = ?, change_24h = ?, 
                            change_7d = ?, change_30d = ?, change_180d = ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE symbol = ?
                    """, (
                        float(price_data.get('price', 0)),
                        float(price_data.get('price_1h_ago', 0)),
                        float(price_data.get('price_24h_ago', 0)),
                        float(price_data.get('price_7d_ago', 0)),
                        float(price_data.get('price_30d_ago', 0)),
                        float(price_data.get('price_180d_ago', 0)),
                        float(price_data.get('volume_24h', 0)),
                        float(price_data.get('change_1h', 0)),
                        float(price_data.get('change_24h', 0)),
                        float(price_data.get('change_7d', 0)),
                        float(price_data.get('change_30d', 0)),
                        float(price_data.get('change_180d', 0)),
                        symbol
                    ))
                else:
                    # Вставляем новую запись
                    cursor.execute("""
                        INSERT INTO price_history (
                            symbol, price, price_1h_ago, price_24h_ago, price_7d_ago,
                            price_30d_ago, price_180d_ago, volume_24h, change_1h,
                            change_24h, change_7d, change_30d, change_180d
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol,
                        float(price_data.get('price', 0)),
                        float(price_data.get('price_1h_ago', 0)),
                        float(price_data.get('price_24h_ago', 0)),
                        float(price_data.get('price_7d_ago', 0)),
                        float(price_data.get('price_30d_ago', 0)),
                        float(price_data.get('price_180d_ago', 0)),
                        float(price_data.get('volume_24h', 0)),
                        float(price_data.get('change_1h', 0)),
                        float(price_data.get('change_24h', 0)),
                        float(price_data.get('change_7d', 0)),
                        float(price_data.get('change_30d', 0)),
                        float(price_data.get('change_180d', 0))
                    ))
                conn.commit()
                self.logger.info(f"Сохранена история цен для {symbol} в базу данных")
                return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении истории цен в базу данных: {e}")
            return False
            
    def get_price_history(self, symbol=None, limit=100):
        """Получение истории цен из базы данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if symbol:
                    cursor.execute("""
                        SELECT * FROM price_history 
                        WHERE symbol = ? 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (symbol, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM price_history 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (limit,))
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Ошибка при получении истории цен из базы данных: {e}")
            return []
            
    def save_available_symbols(self, symbols_data):
        """Сохранение доступных символов в базу данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Сначала удаляем все старые записи, так как мы всегда сохраняем актуальное состояние
                cursor.execute("DELETE FROM available_symbols")
                
                # Вставляем новые данные
                for symbol_data in symbols_data:
                    cursor.execute("""
                        INSERT INTO available_symbols (
                            symbol, category, base_coin, quote_coin, price_scale,
                            taker_fee, maker_fee, min_leverage, max_leverage, leverage_step,
                            min_price, max_price, tick_size, min_order_qty, max_order_qty,
                            qty_step, post_only_max_order_qty, symbol_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol_data.get('symbol', ''),
                        symbol_data.get('category', ''),
                        symbol_data.get('baseCoin', ''),
                        symbol_data.get('quoteCoin', ''),
                        int(symbol_data.get('priceScale', 0)),
                        float(symbol_data.get('takerFee', 0)),
                        float(symbol_data.get('makerFee', 0)),
                        float(symbol_data.get('minLeverage', 0)),
                        float(symbol_data.get('maxLeverage', 0)),
                        float(symbol_data.get('leverageStep', 0)),
                        float(symbol_data.get('minPrice', 0)),
                        float(symbol_data.get('maxPrice', 0)),
                        float(symbol_data.get('tickSize', 0)),
                        float(symbol_data.get('minOrderQty', 0)),
                        float(symbol_data.get('maxOrderQty', 0)),
                        float(symbol_data.get('qtyStep', 0)),
                        float(symbol_data.get('postOnlyMaxOrderQty', 0)),
                        symbol_data.get('status', '')
                    ))
                conn.commit()
                self.logger.info(f"Сохранено {len(symbols_data)} доступных символов в базу данных")
                return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении доступных символов в базу данных: {e}")
            return False
            
    def get_available_symbols(self, category=None, limit=1000):
        """Получение доступных символов из базы данных"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if category:
                    cursor.execute("""
                        SELECT * FROM available_symbols 
                        WHERE category = ? 
                        ORDER BY symbol ASC 
                        LIMIT ?
                    """, (category, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM available_symbols 
                        ORDER BY symbol ASC 
                        LIMIT ?
                    """, (limit,))
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Ошибка при получении доступных символов из базы данных: {e}")
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
    
    def log_analysis(self, analysis_log: Dict):
        """Логирование результатов ML-анализа"""
        try:
            details_json = {
                'symbol': analysis_log.get('symbol'),
                'current_price': analysis_log.get('current_price'),
                'features': analysis_log.get('features'),
                'regime': analysis_log.get('regime'),
                'prediction': analysis_log.get('prediction')
            }

            self.log_system_action(
                level='INFO',
                component='ML_ANALYSIS',
                action=f"Analysis for {analysis_log.get('symbol', 'unknown')}",
                details=details_json,
                execution_time_ms=None,
                session_id=None
            )
        except Exception as e:
            self.logger.error(f"Ошибка логирования анализа: {e}")

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