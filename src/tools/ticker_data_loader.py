#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для загрузки данных тикеров через Bybit API
"""

import json
import logging
import datetime
from pathlib import Path
import sys
import os

# Добавляем путь к API модулям
sys.path.append(str(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.api.bybit_client import BybitClient

logger = logging.getLogger(__name__)

class TickerDataLoader:
    """Класс для загрузки данных тикеров через Bybit API"""
    
    def __init__(self, api_key=None, api_secret=None, testnet=True):
        """
        Инициализация загрузчика данных тикеров
        
        Args:
            api_key (str, optional): API ключ Bybit
            api_secret (str, optional): API секрет Bybit  
            testnet (bool): Использовать тестовую сеть
        """
        # Если ключи не переданы, используем значения по умолчанию или из переменных окружения
        if not api_key:
            api_key = os.getenv('BYBIT_API_KEY', 'test_key')
        if not api_secret:
            api_secret = os.getenv('BYBIT_API_SECRET', 'test_secret')
            
        self.bybit_client = BybitClient(api_key, api_secret, testnet)
        self.tickers_data = {}
        self.historical_data = {}
        self.last_update_timestamp = None
        
        # Инициализируем путь для данных
        self.data_path = Path(__file__).parent.parent.parent / 'data'
        self.data_path.mkdir(exist_ok=True)

    def get_data_file_path(self) -> Path:
        """Возвращает путь к файлу с сохранёнными данными тикеров."""
        return self.data_path / 'tickers_data.json'
    
    def load_tickers_data(self):
        """
        Загрузка данных тикеров через Bybit API
        
        Returns:
            dict: Словарь с данными тикеров и временем последнего обновления
                  или None в случае ошибки
        """
        try:
            logger.info("Загрузка данных тикеров через Bybit API...")
            
            # Получаем данные тикеров через API для spot торговли
            tickers_list = self.bybit_client.get_tickers(category="spot")
            
            if not tickers_list:
                logger.error("Не удалось получить данные тикеров через API")
                return None
            
            # Преобразуем список тикеров в словарь
            self.tickers_data = {}
            for ticker in tickers_list:
                symbol = ticker.get('symbol')
                if symbol:
                    self.tickers_data[symbol] = ticker
            
            # Устанавливаем время обновления
            self.last_update_timestamp = datetime.datetime.now().timestamp()
            update_time = datetime.datetime.fromtimestamp(self.last_update_timestamp)
            
            logger.info(f"Загружены данные {len(self.tickers_data)} тикеров через API. Время обновления: {update_time}")
            
            return {
                'tickers': self.tickers_data,
                'historical_data': self.historical_data,
                'timestamp': self.last_update_timestamp,
                'update_time': update_time
            }
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных тикеров через API: {e}")
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
        Для реального API возвращает пустой словарь, так как исторические данные 
        получаются отдельными запросами
        
        Args:
            symbol (str, optional): Символ тикера. Если None, возвращаются данные всех тикеров.
        
        Returns:
            dict: Пустой словарь (исторические данные получаются отдельно)
        """
        logger.info("Исторические данные получаются отдельными запросами к API")
        return {}
    
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
    
    def get_data_file_path(self):
        """
        Метод для совместимости с существующим кодом
        Возвращает None, так как данные получаются через API
        """
        logger.warning("get_data_file_path() вызван, но данные получаются через API, а не из файла")
        return None