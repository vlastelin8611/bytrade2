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
from decimal import Decimal


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
        # Очистка API ключа и секрета от пробелов и невидимых символов
        api_key = self.api_key.strip()
        api_secret = self.api_secret.strip()
        
        # Формирование строки для подписи
        sign_str = f"{timestamp}{api_key}{self.recv_window}{payload}"
        
        self.logger.debug(f"Строка для подписи: {sign_str}")
        
        # Генерация подписи
        return hmac.new(
            api_secret.encode('utf-8'),
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
        # Отключаем кэширование для отладки
        # cache_key = f"wallet_balance_{account_type}_{coin or 'all'}"
        # cached_data = self._get_cached_data(cache_key)
        # if cached_data:
        #     return cached_data
        
        self.logger.info(f"Запрос баланса кошелька: {account_type}, монета: {coin or 'все'}")
        
        try:
            params = {'accountType': account_type}
            if coin:
                params['coin'] = coin
                
            result = self._make_request('GET', '/v5/account/wallet-balance', params)
            
            # self._set_cached_data(cache_key, result)
            return result
        except Exception as e:
            self.logger.error(f"Ошибка получения баланса кошелька: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {}
    
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
        # Отключаем кэширование для отладки
        # cache_key = f"positions_{category}_{symbol or 'all'}_{settle_coin}"
        # cached_data = self._get_cached_data(cache_key)
        # if cached_data:
        #     return cached_data
        
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
        else:
            # Если symbol не указан, используем settleCoin для получения всех позиций
            if settle_coin:
                params['settleCoin'] = settle_coin
        
        self.logger.info(f"Запрос позиций: {params}")
        
        try:
            result = self._make_request('GET', '/v5/position/list', params)
            positions = result.get('list', [])
            
            self.logger.info(f"Получено позиций: {len(positions)}")
            if not positions:
                self.logger.warning(f"Нет позиций для {category} с параметрами {params}")
            
            # self._set_cached_data(cache_key, positions)
            return positions
        except Exception as e:
            self.logger.error(f"Ошибка получения позиций: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []
    
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
        
    def _flatten_unified_balance(self, resp: dict) -> dict:
        """UNIFIED → удобный словарь:
           {
             'total_wallet_usd': Decimal,
             'total_available_usd': Decimal,
             'coins': { 'USDT': Decimal, 'BTC': Decimal, ... }
           }
        """
        out = {'total_wallet_usd': Decimal('0'), 'total_available_usd': Decimal('0'), 'coins': {}}
        try:
            # Проверяем, что получили корректный ответ
            if not resp or 'result' not in resp:
                self.logger.warning("Получен пустой или некорректный ответ при запросе баланса")
                return out
                
            # Проверяем, что есть список аккаунтов
            if 'list' not in resp['result'] or not resp['result']['list']:
                self.logger.warning(f"Нет данных о балансе в ответе API")
                return out
                
            acc = resp['result']['list'][0]
            out['total_wallet_usd'] = Decimal(str(acc.get('totalWalletBalance', '0')))
            out['total_available_usd'] = Decimal(str(acc.get('totalAvailableBalance', '0')))
            
            # Логируем полный ответ для отладки
            self.logger.info(f"Полный ответ баланса: {acc}")
            
            for c in acc.get('coin', []):
                coin = c.get('coin')
                # Используем walletBalance для получения точного количества монеты
                bal = Decimal(str(c.get('walletBalance', '0')))
                if coin:
                    out['coins'][coin] = bal
                    # Логируем каждую монету отдельно для отладки
                    self.logger.info(f"Монета {coin}: walletBalance={bal}, usdValue={c.get('usdValue', '0')}")
            
            self.logger.info(f"Обработан баланс: {len(out['coins'])} монет, всего: {out['total_wallet_usd']} USD")
            self.logger.info(f"Детальный баланс монет: {out['coins']}")
        except Exception as e:
            self.logger.error(f"Ошибка обработки баланса: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        return out

    def _flatten_fund_balance(self, resp: dict) -> dict:
        """FUND → {'coins': {'USDT': Decimal(...), 'BTC': Decimal(...), ...}}"""
        out = {'coins': {}, 'accountType': 'FUND'}
        try:
            for c in resp['result'].get('balance', []):
                coin = c.get('coin')
                bal  = Decimal(str(c.get('walletBalance', '0')))
                if coin:
                    out['coins'][coin] = bal
        except Exception:
            pass
        return out
        
    def get_unified_balance_flat(self, coins: list[str] = None) -> dict:
        """Получение плоской структуры баланса UNIFIED кошелька"""
        # Отключаем кэширование для отладки
        self.logger.info("Запрос баланса UNIFIED кошелька")
        try:
            params = {'accountType': 'UNIFIED'}
            if coins:
                params['coin'] = ','.join(coins)
            raw = self._make_request('GET', '/v5/account/wallet-balance', params)
            flat_result = self._flatten_unified_balance(raw)
            
            self.logger.info(f"Получен баланс: {flat_result}")
            return flat_result
        except Exception as e:
            self.logger.error(f"Ошибка получения баланса: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {'total_wallet_usd': Decimal('0'), 'total_available_usd': Decimal('0'), 'coins': {}}

    def get_fund_balance_flat(self, coins: list[str] = None) -> dict:
        """Получение плоской структуры баланса FUND кошелька"""
        params = {'accountType': 'FUND'}
        if coins:
            params['coin'] = ','.join(coins)
        raw = self._make_request('GET', '/v5/asset/transfer/query-account-coins-balance', params)
        return self._flatten_fund_balance(raw)

    def usd_to_btc(self, usd: Decimal) -> Decimal:
        """Конвертация USD в BTC по текущему курсу"""
        tick = self._make_request('GET', '/v5/market/tickers', {'category': 'spot', 'symbol': 'BTCUSDT'})
        try:
            price = Decimal(str(tick['result']['list'][0]['lastPrice']))
            return (usd / price) if price > 0 else Decimal('0')
        except Exception:
            return Decimal('0')
    
    def get_kline(self, category: str, symbol: str, interval: str, limit: int = 200, start: int = None, end: int = None) -> List[Dict]:
        """Получение исторических данных (свечи)
        
        Args:
            category: Категория (spot, linear и т.д.)
            symbol: Символ тикера (например, BTCUSDT)
            interval: Интервал (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            limit: Количество свечей (макс. 1000)
            start: Начальное время в миллисекундах (UNIX timestamp)
            end: Конечное время в миллисекундах (UNIX timestamp)
        """
        params = {
            'category': category,
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        # Добавляем временной диапазон, если указан
        if start is not None:
            params['start'] = int(start)
        if end is not None:
            params['end'] = int(end)
        
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
    
    def get_klines(self, category: str, symbol: str, interval: str, limit: int = 200, start: int = None, end: int = None) -> Dict:
        """Получение исторических данных (свечи) - обертка для совместимости
        
        Этот метод является оберткой для get_kline, возвращающей результат в формате,
        ожидаемом в trading_bot_main.py
        """
        try:
            # Расширенная карта интервалов с поддержкой множественных форматов
            interval_map = {
                # Минутные интервалы
                "1": "1", "1m": "1", "1min": "1",
                "3": "3", "3m": "3", "3min": "3",
                "5": "5", "5m": "5", "5min": "5",
                "15": "15", "15m": "15", "15min": "15",
                "30": "30", "30m": "30", "30min": "30",
                
                # Часовые интервалы
                "60": "60", "1h": "60", "1hour": "60",
                "120": "120", "2h": "120", "2hour": "120",
                "240": "240", "4h": "240", "4hour": "240",
                "360": "360", "6h": "360", "6hour": "360",
                "720": "720", "12h": "720", "12hour": "720",
                
                # Дневные и недельные интервалы
                "D": "D", "1d": "D", "1day": "D", "daily": "D",
                "W": "W", "1w": "W", "1week": "W", "weekly": "W",
                "M": "M", "1M": "M", "1month": "M", "monthly": "M"
            }
            
            api_interval = interval_map.get(interval, interval)
            
            # Получаем данные через базовый метод
            klines = self._make_request('GET', '/v5/market/kline', {
                'category': category,
                'symbol': symbol,
                'interval': api_interval,
                'limit': limit,
                **({"start": start} if start is not None else {}),
                **({"end": end} if end is not None else {})
            })
            
            return klines
        except Exception as e:
            error_msg = str(e)
            # Если ошибка связана с неподдерживаемым интервалом, пробуем альтернативные
            if "Invalid period" in error_msg or "invalid interval" in error_msg.lower():
                self.logger.warning(f"Интервал {interval} не поддерживается для {symbol}, пробуем альтернативные")
                
                # Расширенный список альтернативных интервалов в порядке приоритета
                alternative_intervals = []
                
                # Определяем альтернативы на основе исходного интервала
                if interval in ["1h", "60", "1hour"]:
                    alternative_intervals = ["30", "15", "240", "120"]  # 30m, 15m, 4h, 2h
                elif interval in ["4h", "240", "4hour"]:
                    alternative_intervals = ["120", "60", "360", "D"]  # 2h, 1h, 6h, 1d
                elif interval in ["1d", "D", "daily"]:
                    alternative_intervals = ["720", "240", "W"]  # 12h, 4h, 1w
                elif interval in ["15", "15m", "15min"]:
                    alternative_intervals = ["5", "30", "60"]  # 5m, 30m, 1h
                elif interval in ["5", "5m", "5min"]:
                    alternative_intervals = ["1", "15", "30"]  # 1m, 15m, 30m
                else:
                    # Универсальные альтернативы для неизвестных интервалов
                    alternative_intervals = ["60", "15", "240", "D", "5", "30"]
                
                # Пробуем альтернативные интервалы
                for alt_interval in alternative_intervals:
                    try:
                        self.logger.info(f"Пробуем интервал {alt_interval} для {symbol}")
                        klines = self._make_request('GET', '/v5/market/kline', {
                            'category': category,
                            'symbol': symbol,
                            'interval': alt_interval,
                            'limit': limit,
                            **({"start": start} if start is not None else {}),
                            **({"end": end} if end is not None else {})
                        })
                        self.logger.info(f"✅ Успешно получены данные с интервалом {alt_interval} для {symbol}")
                        return klines
                    except Exception as alt_error:
                        self.logger.debug(f"Альтернативный интервал {alt_interval} также не работает: {alt_error}")
                        continue
                
                # Если все альтернативы не сработали, пробуем базовые интервалы
                basic_intervals = ["60", "15", "D", "5"]  # Самые распространенные интервалы
                for basic_interval in basic_intervals:
                    if basic_interval not in alternative_intervals:  # Избегаем повторных попыток
                        try:
                            self.logger.info(f"Пробуем базовый интервал {basic_interval} для {symbol}")
                            klines = self._make_request('GET', '/v5/market/kline', {
                                'category': category,
                                'symbol': symbol,
                                'interval': basic_interval,
                                'limit': limit,
                                **({"start": start} if start is not None else {}),
                                **({"end": end} if end is not None else {})
                            })
                            self.logger.info(f"✅ Успешно получены данные с базовым интервалом {basic_interval} для {symbol}")
                            return klines
                        except Exception as basic_error:
                            self.logger.debug(f"Базовый интервал {basic_interval} также не работает: {basic_error}")
                            continue
                
                # Если все альтернативы не сработали
                self.logger.error(f"❌ Не удалось получить данные для {symbol} ни с одним интервалом")
            
            self.logger.error(f"API ошибка: {error_msg}")
            raise Exception(f"API ошибка: {error_msg}")
    
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
    
    def get_open_orders(self, category: str = "spot", symbol: str = None, limit: int = 50) -> Dict:
        """Получение открытых ордеров
        
        Args:
            category: Категория (spot, linear, inverse)
            symbol: Символ торговой пары (опционально)
            limit: Количество записей (макс. 50)
            
        Returns:
            Dict: Информация об открытых ордерах
        """
        params = {'category': category, 'limit': limit}
        
        if symbol:
            params['symbol'] = symbol
        
        return self._make_request('GET', '/v5/order/realtime', params)
    
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