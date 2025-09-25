#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit API клиент для торгового бота
Безопасное взаимодействие с Bybit API
"""

import time
import hmac
import hashlib
import requests
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import threading


class RateLimiter:
    """Контроль частоты запросов к API"""
    
    def __init__(self, max_requests: int = 120, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Ожидание если превышен лимит запросов"""
        with self.lock:
            now = time.time()
            # Удаляем старые запросы
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            if len(self.requests) >= self.max_requests:
                sleep_time = self.time_window - (now - self.requests[0]) + 1
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    self.requests = []
            
            self.requests.append(now)


class BybitClient:
    """Клиент для работы с Bybit API"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.recv_window = 20000  # Увеличиваем recv_window для избежания ошибок синхронизации
        
        # URLs для API
        if testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"
        
        # Rate limiter
        self.rate_limiter = RateLimiter()
        
        # Кэш для данных
        self.cache = {}
        self.cache_timeout = 30  # секунд
        
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        
        # Сессия для HTTP запросов
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'TradingBot/1.0'
        })
    
    def _generate_signature(self, timestamp: str, payload: str) -> str:
        """Генерация подписи для запроса согласно спецификации Bybit V5
        
        Строка для подписи: timestamp + api_key + recv_window + payload
        где payload - это query string для GET или raw body для POST
        """
        sign_str = f"{timestamp}{self.api_key}{self.recv_window}{payload}"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_server_time_raw(self) -> int:
        """Получение времени сервера без аутентификации"""
        try:
            url = f"{self.base_url}/v5/market/time"
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get('retCode') == 0:
                return int(data.get('result', {}).get('timeSecond', 0)) * 1000
        except:
            pass
        return int(time.time() * 1000)
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, body: Dict = None) -> Dict:
        """Выполнение HTTP запроса к API"""
        self.rate_limiter.wait_if_needed()
        
        url = f"{self.base_url}{endpoint}"
        # Получаем серверное время для синхронизации
        timestamp = str(self._get_server_time_raw())
        
        # Подготовка query string для GET запросов
        query_string = ''
        if params and method.upper() == 'GET':
            sorted_params = sorted(params.items())
            query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        # Подготовка body для POST запросов
        body_str = ''
        if body is not None and method.upper() != 'GET':
            body_str = json.dumps(body, separators=(',', ':'))
        elif params and method.upper() != 'GET':
            body_str = json.dumps(params, separators=(',', ':'))
        
        # Определение payload для подписи
        payload = query_string if method.upper() == 'GET' else body_str
        
        # Генерация подписи
        signature = self._generate_signature(timestamp, payload)
        
        # Заголовки
        headers = {
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-SIGN': signature,
            'X-BAPI-RECV-WINDOW': str(self.recv_window),
            'Content-Type': 'application/json'
        }
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                request_body = body if body is not None else params
                response = self.session.post(url, data=body_str if body_str else None, json=request_body if not body_str else None, headers=headers, timeout=10)
            else:
                raise ValueError(f"Неподдерживаемый HTTP метод: {method}")
            
            response.raise_for_status()
            data = response.json()
            
            # Проверка ответа API
            if data.get('retCode') != 0:
                error_msg = data.get('retMsg', 'Неизвестная ошибка API')
                self.logger.error(f"API ошибка: {error_msg}")
                raise Exception(f"API ошибка: {error_msg}")
            
            return data.get('result', {})
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка HTTP запроса: {e}")
            raise Exception(f"Ошибка соединения с API: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Ошибка парсинга JSON: {e}")
            raise Exception(f"Некорректный ответ API: {e}")
    
    def _get_cached_data(self, cache_key: str) -> Optional[Dict]:
        """Получение данных из кэша"""
        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_timeout:
                return data
            else:
                del self.cache[cache_key]
        return None
    
    def _set_cached_data(self, cache_key: str, data: Dict):
        """Сохранение данных в кэш"""
        self.cache[cache_key] = (data, time.time())
    
    def get_wallet_balance(self, account_type: str = "UNIFIED", coin: str = None) -> Dict:
        """Получение баланса кошелька для UNIFIED аккаунта
        
        Args:
            account_type: Тип аккаунта (только UNIFIED поддерживается)
            coin: Фильтр по монете (опционально)
        """
        cache_key = f"wallet_balance_{account_type}_{coin or 'all'}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        params = {'accountType': account_type}
        if coin:
            params['coin'] = coin
            
        result = self._make_request('GET', '/v5/account/wallet-balance', params)
        
        self._set_cached_data(cache_key, result)
        return result
    
    def get_fund_balance(self, coin: str = None) -> Dict:
        """Получение баланса FUND кошелька
        
        Args:
            coin: Фильтр по монете (опционально)
        """
        cache_key = f"fund_balance_{coin or 'all'}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        params = {'accountType': 'FUND'}
        if coin:
            params['coin'] = coin
            
        result = self._make_request('GET', '/v5/asset/transfer/query-account-coins-balance', params)
        
        self._set_cached_data(cache_key, result)
        return result
    
    def inter_transfer(self, coin: str, amount: str, from_account: str, to_account: str) -> Dict:
        """Внутренний перевод между кошельками
        
        Args:
            coin: Символ монеты (например, 'BTC', 'USDT')
            amount: Сумма для перевода (строка)
            from_account: Исходный кошелек (например, 'FUND')
            to_account: Целевой кошелек (например, 'UNIFIED')
        """
        import uuid
        transfer_id = str(uuid.uuid4())
        
        body = {
            'transferId': transfer_id,
            'coin': coin,
            'amount': amount,
            'fromAccountType': from_account,
            'toAccountType': to_account
        }
        
        return self._make_request('POST', '/v5/asset/transfer/inter-transfer', body=body)
    
    def get_transfer_coin_list(self, from_account: str = 'FUND', to_account: str = 'UNIFIED') -> Dict:
        """Получение списка монет, доступных для перевода
        
        Args:
            from_account: Исходный кошелек
            to_account: Целевой кошелек
        """
        params = {
            'fromAccountType': from_account,
            'toAccountType': to_account
        }
        
        return self._make_request('GET', '/v5/asset/transfer/query-transfer-coin-list', params)
    
    def get_positions(self, category: str = "linear", symbol: str = None, settle_coin: str = "USDT") -> List[Dict]:
        """Получение позиций"""
        cache_key = f"positions_{category}_{symbol or 'all'}_{settle_coin}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
        else:
            # Если symbol не указан, используем settleCoin для получения всех позиций
            params['settleCoin'] = settle_coin
        
        result = self._make_request('GET', '/v5/position/list', params)
        positions = result.get('list', [])
        
        self._set_cached_data(cache_key, positions)
        return positions
    
    def get_tickers(self, category: str = "linear", symbol: str = None) -> List[Dict]:
        """Получение тикеров"""
        cache_key = f"tickers_{category}_{symbol or 'all'}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
        
        result = self._make_request('GET', '/v5/market/tickers', params)
        tickers = result.get('list', [])
        
        self._set_cached_data(cache_key, tickers)
        return tickers
    
    def get_kline(self, category: str, symbol: str, interval: str, limit: int = 200) -> List[Dict]:
        """Получение исторических данных (свечи)"""
        params = {
            'category': category,
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        result = self._make_request('GET', '/v5/market/kline', params)
        klines = result.get('list', [])
        
        # Преобразование в удобный формат
        formatted_klines = []
        for kline in klines:
            formatted_klines.append({
                'timestamp': int(kline[0]),
                'open': float(kline[1]),
                'high': float(kline[2]),
                'low': float(kline[3]),
                'close': float(kline[4]),
                'volume': float(kline[5])
            })
        
        return formatted_klines
    
    def place_order(self, category: str, symbol: str, side: str, order_type: str, 
                   qty: str, price: str = None, **kwargs) -> Dict:
        """Размещение ордера"""
        params = {
            'category': category,
            'symbol': symbol,
            'side': side,
            'orderType': order_type,
            'qty': qty
        }
        
        if price:
            params['price'] = price
        
        # Дополнительные параметры
        params.update(kwargs)
        
        result = self._make_request('POST', '/v5/order/create', params)
        return result
    
    def cancel_order(self, category: str, symbol: str, order_id: str = None, 
                    order_link_id: str = None) -> Dict:
        """Отмена ордера"""
        params = {
            'category': category,
            'symbol': symbol
        }
        
        if order_id:
            params['orderId'] = order_id
        elif order_link_id:
            params['orderLinkId'] = order_link_id
        else:
            raise ValueError("Необходимо указать order_id или order_link_id")
        
        result = self._make_request('POST', '/v5/order/cancel', params)
        return result
    
    def get_order_history(self, category: str, symbol: str = None, limit: int = 50) -> List[Dict]:
        """Получение истории ордеров"""
        params = {
            'category': category,
            'limit': limit
        }
        
        if symbol:
            params['symbol'] = symbol
        
        result = self._make_request('GET', '/v5/order/history', params)
        return result.get('list', [])
    
    def get_execution_list(self, category: str, symbol: str = None, limit: int = 50) -> List[Dict]:
        """Получение истории исполнений"""
        params = {
            'category': category,
            'limit': limit
        }
        
        if symbol:
            params['symbol'] = symbol
        
        result = self._make_request('GET', '/v5/execution/list', params)
        return result.get('list', [])
    
    def test_connection(self) -> bool:
        """Тест соединения с API"""
        try:
            # Простой запрос для проверки соединения
            self._make_request('GET', '/v5/market/time')
            return True
        except Exception as e:
            self.logger.error(f"Ошибка соединения: {e}")
            return False
    
    def get_server_time(self) -> int:
        """Получение времени сервера"""
        result = self._make_request('GET', '/v5/market/time')
        return int(result.get('timeSecond', 0))
    
    def get_instruments_info(self, category: str, symbol: str = None) -> List[Dict]:
        """Получение информации об инструментах"""
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
        
        result = self._make_request('GET', '/v5/market/instruments-info', params)
        return result.get('list', [])