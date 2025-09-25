#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для загрузки данных тикеров из файла
"""

import json
import logging
import datetime
from pathlib import Path


logger = logging.getLogger(__name__)

class TickerDataLoader:
    """Класс для загрузки данных тикеров из файла"""
    
    def __init__(self, data_path=None):
        """
        Инициализация загрузчика данных тикеров
        
        Args:
            data_path (Path, optional): Путь к директории с данными. 
                                       По умолчанию используется директория data в корне проекта.
        """
        if data_path is None:
            # Если путь не указан, используем директорию data в корне проекта
            self.data_path = Path.home() / "AppData" / "Local" / "BybitTradingBot" / "data"
        else:
            self.data_path = Path(data_path)
        
        # Убедимся, что директория существует
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        self.tickers_data = {}
        self.historical_data = {}
        self.last_update_timestamp = None

    def get_data_file_path(self) -> Path:
        """Возвращает путь к файлу с сохранёнными данными тикеров."""
        return self.data_path / 'tickers_data.json'
    
    def load_tickers_data(self):
        """
        Загрузка данных тикеров из файла
        
        Returns:
            dict: Словарь с данными тикеров и временем последнего обновления
                  или None в случае ошибки
        """
        try:
            data_file = self.get_data_file_path()
            
            if not data_file.exists():
                logger.warning(f"Файл с данными тикеров не найден: {data_file}")
                return None
            
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Проверяем структуру данных
            if not all(key in data for key in ['timestamp', 'tickers', 'historical_data']):
                logger.error("Некорректная структура данных в файле тикеров")
                return None
            
            self.tickers_data = data['tickers']
            self.historical_data = data['historical_data']
            self.last_update_timestamp = data['timestamp']
            
            # Преобразуем timestamp в читаемый формат для логирования
            update_time = datetime.datetime.fromtimestamp(self.last_update_timestamp)
            logger.info(f"Загружены данные тикеров. Последнее обновление: {update_time}")
            
            return {
                'tickers': self.tickers_data,
                'historical_data': self.historical_data,
                'timestamp': self.last_update_timestamp,
                'update_time': update_time
            }
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных тикеров: {e}")
            return None
    
    def get_ticker_data(self, symbol=None):
        """
        Получение данных конкретного тикера или всех тикеров
        
        Args:
            symbol (str, optional): Символ тикера. Если None, возвращаются все тикеры.
        
        Returns:
            dict: Данные тикера или словарь всех тикеров
        """
        if not self.tickers_data:
            self.load_tickers_data()
        
        if symbol:
            return self.tickers_data.get(symbol)
        return self.tickers_data
    
    def get_historical_data(self, symbol=None):
        """
        Получение исторических данных конкретного тикера или всех тикеров
        
        Args:
            symbol (str, optional): Символ тикера. Если None, возвращаются данные всех тикеров.
        
        Returns:
            dict: Исторические данные тикера или словарь исторических данных всех тикеров
        """
        if not self.historical_data:
            self.load_tickers_data()
        
        if symbol:
            return self.historical_data.get(symbol)
        return self.historical_data
    
    def is_data_fresh(self, max_age_minutes=5):
        """
        Проверка свежести данных
        
        Args:
            max_age_minutes (int): Максимальный возраст данных в минутах
            
        Returns:
            bool: True, если данные свежие, иначе False
        """
        if not self.last_update_timestamp:
            return False
        
        current_time = datetime.datetime.now().timestamp()
        data_age_minutes = (current_time - self.last_update_timestamp) / 60
        
        return data_age_minutes <= max_age_minutes