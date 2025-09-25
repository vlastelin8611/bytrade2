#!/usr/bin/env python3
"""
Детальная отладка API ответов Bybit
Анализирует почему API возвращает только 3 записи
"""

import sys
import os
import json
import requests
import time
import hmac
import hashlib
from datetime import datetime

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import get_api_credentials
except ImportError as e:
    print(f"Ошибка импорта config: {e}")
    sys.exit(1)

class APIDebugger:
    """Отладчик API ответов"""
    
    def __init__(self):
        self.api_creds = get_api_credentials()
        self.api_key = self.api_creds['api_key']
        self.api_secret = self.api_creds['api_secret']
        self.testnet = self.api_creds['testnet']
        
        # URL для testnet и mainnet
        if self.testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"
        
        print(f"🔧 Инициализация отладчика API")
        print(f"   Testnet: {self.testnet}")
        print(f"   Base URL: {self.base_url}")
    
    def _generate_signature(self, timestamp: str, payload: str) -> str:
        """Генерация подписи для API"""
        message = timestamp + self.api_key + "5000" + payload
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_server_time(self) -> int:
        """Получение времени сервера"""
        try:
            url = f"{self.base_url}/v5/market/time"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get('retCode') == 0:
                return int(data.get('result', {}).get('timeSecond', 0)) * 1000
        except Exception as e:
            print(f"⚠️ Ошибка получения времени сервера: {e}")
        return int(time.time() * 1000)
    
    def debug_klines_request(self, symbol: str = 'BTCUSDT', interval: str = '240', limit: int = 200, category: str = 'spot'):
        """Детальная отладка запроса klines"""
        print(f"\n🔍 Отладка запроса klines:")
        print(f"   Symbol: {symbol}")
        print(f"   Interval: {interval}")
        print(f"   Limit: {limit}")
        print(f"   Category: {category}")
        
        # Подготовка параметров
        timestamp = str(self._get_server_time())
        params = {
            'category': category,
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        # Сортируем параметры для query string
        sorted_params = sorted(params.items())
        query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        print(f"   Query string: {query_string}")
        print(f"   Timestamp: {timestamp}")
        
        # Генерация подписи
        signature = self._generate_signature(timestamp, query_string)
        print(f"   Signature: {signature[:20]}...")
        
        # Заголовки
        headers = {
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-SIGN': signature,
            'X-BAPI-RECV-WINDOW': '5000',
            'Content-Type': 'application/json'
        }
        
        # URL запроса
        url = f"{self.base_url}/v5/market/kline"
        print(f"   URL: {url}")
        
        try:
            # Выполняем запрос
            print(f"\n📡 Выполняем запрос...")
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response Headers: {dict(response.headers)}")
            
            # Парсим ответ
            try:
                data = response.json()
                print(f"\n📊 Ответ API:")
                print(f"   retCode: {data.get('retCode')}")
                print(f"   retMsg: {data.get('retMsg')}")
                
                result = data.get('result', {})
                print(f"   result keys: {list(result.keys())}")
                
                # Анализируем данные klines
                klines_list = result.get('list', [])
                print(f"   klines count: {len(klines_list)}")
                
                if klines_list:
                    print(f"\n📈 Анализ данных klines:")
                    print(f"   Первая запись: {klines_list[0]}")
                    if len(klines_list) > 1:
                        print(f"   Последняя запись: {klines_list[-1]}")
                    
                    # Проверяем временные метки
                    timestamps = []
                    for kline in klines_list:
                        try:
                            ts = int(kline[0])  # Первый элемент - timestamp
                            timestamps.append(ts)
                        except (ValueError, IndexError):
                            pass
                    
                    if timestamps:
                        timestamps.sort()
                        start_time = datetime.fromtimestamp(timestamps[0] / 1000)
                        end_time = datetime.fromtimestamp(timestamps[-1] / 1000)
                        print(f"   Временной диапазон: {start_time} - {end_time}")
                        
                        # Проверяем интервалы между записями
                        if len(timestamps) > 1:
                            intervals = []
                            for i in range(1, len(timestamps)):
                                interval_ms = timestamps[i] - timestamps[i-1]
                                intervals.append(interval_ms)
                            
                            avg_interval = sum(intervals) / len(intervals)
                            print(f"   Средний интервал между записями: {avg_interval/1000/60:.1f} минут")
                
                # Дополнительная информация из ответа
                if 'category' in result:
                    print(f"   category: {result['category']}")
                if 'symbol' in result:
                    print(f"   symbol: {result['symbol']}")
                
                return data
                
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка парсинга JSON: {e}")
                print(f"   Raw response: {response.text[:500]}...")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка HTTP запроса: {e}")
            return None
    
    def test_different_parameters(self):
        """Тестирование различных параметров"""
        print(f"\n🧪 Тестирование различных параметров...")
        
        test_cases = [
            # Базовые тесты
            {'symbol': 'BTCUSDT', 'interval': '240', 'limit': 200, 'category': 'spot'},
            {'symbol': 'BTCUSDT', 'interval': '240', 'limit': 1000, 'category': 'spot'},
            {'symbol': 'BTCUSDT', 'interval': '240', 'limit': 50, 'category': 'spot'},
            
            # Разные интервалы
            {'symbol': 'BTCUSDT', 'interval': '60', 'limit': 200, 'category': 'spot'},
            {'symbol': 'BTCUSDT', 'interval': 'D', 'limit': 200, 'category': 'spot'},
            {'symbol': 'BTCUSDT', 'interval': '15', 'limit': 200, 'category': 'spot'},
            
            # Разные категории
            {'symbol': 'BTCUSDT', 'interval': '240', 'limit': 200, 'category': 'linear'},
            
            # Разные символы
            {'symbol': 'ETHUSDT', 'interval': '240', 'limit': 200, 'category': 'spot'},
            {'symbol': 'ADAUSDT', 'interval': '240', 'limit': 200, 'category': 'spot'},
        ]
        
        results = []
        for i, test_case in enumerate(test_cases):
            print(f"\n--- Тест {i+1}/{len(test_cases)} ---")
            result = self.debug_klines_request(**test_case)
            
            if result:
                klines_count = len(result.get('result', {}).get('list', []))
                results.append({
                    'test_case': test_case,
                    'klines_count': klines_count,
                    'success': True
                })
                print(f"✅ Получено {klines_count} записей")
            else:
                results.append({
                    'test_case': test_case,
                    'klines_count': 0,
                    'success': False
                })
                print(f"❌ Запрос неудачен")
            
            # Небольшая пауза между запросами
            time.sleep(0.5)
        
        # Сводка результатов
        print(f"\n📋 Сводка результатов:")
        for i, result in enumerate(results):
            status = "✅" if result['success'] else "❌"
            test_case = result['test_case']
            count = result['klines_count']
            print(f"   {status} Тест {i+1}: {test_case['symbol']} {test_case['interval']} {test_case['category']} -> {count} записей")
        
        # Сохраняем результаты
        with open('api_debug_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        return results
    
    def check_api_status(self):
        """Проверка статуса API"""
        print(f"\n🔍 Проверка статуса API...")
        
        # Проверяем время сервера
        try:
            url = f"{self.base_url}/v5/market/time"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if data.get('retCode') == 0:
                server_time = int(data.get('result', {}).get('timeSecond', 0))
                local_time = int(time.time())
                time_diff = abs(server_time - local_time)
                
                print(f"   ✅ Время сервера: {datetime.fromtimestamp(server_time)}")
                print(f"   ✅ Локальное время: {datetime.fromtimestamp(local_time)}")
                print(f"   ✅ Разница: {time_diff} секунд")
                
                if time_diff > 5:
                    print(f"   ⚠️ Большая разница во времени может вызывать проблемы!")
            else:
                print(f"   ❌ Ошибка получения времени сервера: {data}")
                
        except Exception as e:
            print(f"   ❌ Ошибка проверки времени сервера: {e}")
        
        # Проверяем доступность инструментов
        try:
            url = f"{self.base_url}/v5/market/instruments-info"
            params = {'category': 'spot', 'limit': 10}
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('retCode') == 0:
                instruments = data.get('result', {}).get('list', [])
                print(f"   ✅ Доступно инструментов (spot): {len(instruments)}")
                if instruments:
                    print(f"   ✅ Пример инструмента: {instruments[0].get('symbol')}")
            else:
                print(f"   ❌ Ошибка получения инструментов: {data}")
                
        except Exception as e:
            print(f"   ❌ Ошибка проверки инструментов: {e}")

def main():
    """Главная функция"""
    debugger = APIDebugger()
    
    # Проверяем статус API
    debugger.check_api_status()
    
    # Тестируем различные параметры
    debugger.test_different_parameters()
    
    print(f"\n✅ Отладка завершена!")
    print(f"📄 Результаты сохранены в api_debug_results.json")

if __name__ == "__main__":
    main()