"""
Асинхронный загрузчик исторических данных для получения большого объема свечей
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import time
from pathlib import Path


class AsyncHistoricalDataLoader:
    """Асинхронный загрузчик исторических данных с поддержкой больших объемов"""
    
    def __init__(self, api_base_url: str = "https://api-testnet.bybit.com", 
                 data_cache_path: str = "data/historical_cache"):
        self.api_base_url = api_base_url
        self.cache_path = Path(data_cache_path)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Настройки для пакетной загрузки
        self.max_concurrent_requests = 5
        self.request_delay = 0.2  # Задержка между запросами
        self.max_klines_per_request = 1000  # Максимум свечей за один запрос
        
    async def load_historical_data_bulk(self, symbol: str, interval: str, 
                                      start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Загрузка большого объема исторических данных с разбивкой на пакеты
        
        Args:
            symbol: Торговый символ (например, BTCUSDT)
            interval: Интервал свечей (1, 5, 15, 60, 240, D)
            start_time: Начальная дата
            end_time: Конечная дата
            
        Returns:
            List[Dict]: Список исторических свечей
        """
        try:
            # Проверяем кэш
            cache_key = f"{symbol}_{interval}_{start_time.strftime('%Y%m%d')}_{end_time.strftime('%Y%m%d')}"
            cached_data = self._load_from_cache(cache_key)
            if cached_data:
                self.logger.info(f"Загружены данные из кэша для {symbol} {interval}")
                return cached_data
            
            # Разбиваем период на части для пакетной загрузки
            time_chunks = self._split_time_range(start_time, end_time, interval)
            
            # Создаем семафор для ограничения количества одновременных запросов
            semaphore = asyncio.Semaphore(self.max_concurrent_requests)
            
            # Создаем задачи для асинхронной загрузки
            tasks = []
            async with aiohttp.ClientSession() as session:
                for chunk_start, chunk_end in time_chunks:
                    task = self._fetch_chunk_data(session, semaphore, symbol, interval, 
                                                chunk_start, chunk_end)
                    tasks.append(task)
                
                # Выполняем все задачи параллельно
                chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Объединяем результаты
            all_klines = []
            for result in chunk_results:
                if isinstance(result, Exception):
                    self.logger.error(f"Ошибка загрузки чанка: {result}")
                    continue
                if result:
                    all_klines.extend(result)
            
            # Сортируем по времени и удаляем дубликаты
            all_klines = self._deduplicate_klines(all_klines)
            
            # Сохраняем в кэш
            self._save_to_cache(cache_key, all_klines)
            
            self.logger.info(f"Загружено {len(all_klines)} свечей для {symbol} {interval}")
            return all_klines
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки исторических данных: {e}")
            return []
    
    async def _fetch_chunk_data(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore,
                              symbol: str, interval: str, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Загрузка одного чанка данных"""
        async with semaphore:
            try:
                # Задержка между запросами
                await asyncio.sleep(self.request_delay)
                
                # Конвертируем интервал в формат Bybit
                bybit_interval = self._convert_interval_to_bybit(interval)
                
                # Параметры запроса
                params = {
                    'category': 'spot',
                    'symbol': symbol,
                    'interval': bybit_interval,
                    'start': int(start_time.timestamp() * 1000),
                    'end': int(end_time.timestamp() * 1000),
                    'limit': self.max_klines_per_request
                }
                
                url = f"{self.api_base_url}/v5/market/kline"
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('retCode') == 0 and 'result' in data:
                            klines_data = data['result'].get('list', [])
                            
                            # Форматируем данные
                            formatted_klines = []
                            for kline in klines_data:
                                formatted_klines.append({
                                    'timestamp': int(kline[0]),
                                    'open': float(kline[1]),
                                    'high': float(kline[2]),
                                    'low': float(kline[3]),
                                    'close': float(kline[4]),
                                    'volume': float(kline[5])
                                })
                            
                            return formatted_klines
                        else:
                            self.logger.warning(f"API вернул ошибку: {data.get('retMsg', 'Unknown error')}")
                    else:
                        self.logger.warning(f"HTTP ошибка: {response.status}")
                
                return []
                
            except Exception as e:
                self.logger.error(f"Ошибка загрузки чанка {start_time}-{end_time}: {e}")
                return []
    
    def _split_time_range(self, start_time: datetime, end_time: datetime, interval: str) -> List[tuple]:
        """Разбивка временного диапазона на чанки"""
        chunks = []
        
        # Определяем размер чанка в зависимости от интервала
        if interval in ['1', '5']:
            chunk_hours = 24  # 1 день для минутных интервалов
        elif interval in ['15', '60']:
            chunk_hours = 168  # 1 неделя для часовых интервалов
        else:
            chunk_hours = 720  # 1 месяц для дневных интервалов
        
        current_time = start_time
        while current_time < end_time:
            chunk_end = min(current_time + timedelta(hours=chunk_hours), end_time)
            chunks.append((current_time, chunk_end))
            current_time = chunk_end
        
        return chunks
    
    def _convert_interval_to_bybit(self, interval: str) -> str:
        """Конвертация интервала в формат Bybit API"""
        interval_map = {
            '1': '1',      # 1 минута
            '5': '5',      # 5 минут
            '15': '15',    # 15 минут
            '60': '60',    # 1 час
            '240': '240',  # 4 часа
            '1h': '60',    # 1 час (альтернативный формат)
            'D': 'D'       # 1 день
        }
        return interval_map.get(interval, '60')
    
    def _deduplicate_klines(self, klines: List[Dict]) -> List[Dict]:
        """Удаление дубликатов и сортировка по времени"""
        # Создаем словарь для удаления дубликатов по timestamp
        unique_klines = {}
        for kline in klines:
            timestamp = kline['timestamp']
            unique_klines[timestamp] = kline
        
        # Сортируем по времени
        sorted_klines = sorted(unique_klines.values(), key=lambda x: x['timestamp'])
        return sorted_klines
    
    def _load_from_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """Загрузка данных из кэша"""
        try:
            cache_file = self.cache_path / f"{cache_key}.json"
            if cache_file.exists():
                # Проверяем возраст кэша (не старше 1 дня)
                file_age = time.time() - cache_file.stat().st_mtime
                if file_age < 86400:  # 24 часа
                    with open(cache_file, 'r') as f:
                        return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"Ошибка загрузки из кэша: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, data: List[Dict]):
        """Сохранение данных в кэш"""
        try:
            cache_file = self.cache_path / f"{cache_key}.json"
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения в кэш: {e}")
    
    async def load_multiple_symbols(self, symbols: List[str], interval: str, 
                                  days_back: int = 30) -> Dict[str, List[Dict]]:
        """
        Загрузка данных для нескольких символов одновременно
        
        Args:
            symbols: Список торговых символов
            interval: Интервал свечей
            days_back: Количество дней назад для загрузки
            
        Returns:
            Dict[str, List[Dict]]: Словарь с данными для каждого символа
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        tasks = []
        for symbol in symbols:
            task = self.load_historical_data_bulk(symbol, interval, start_time, end_time)
            tasks.append((symbol, task))
        
        results = {}
        for symbol, task in tasks:
            try:
                data = await task
                results[symbol] = data
            except Exception as e:
                self.logger.error(f"Ошибка загрузки данных для {symbol}: {e}")
                results[symbol] = []
        
        return results
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Получение информации о кэше"""
        cache_files = list(self.cache_path.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'cache_files_count': len(cache_files),
            'total_cache_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_path': str(self.cache_path)
        }
    
    def clear_cache(self, older_than_days: int = 7):
        """Очистка старого кэша"""
        try:
            cutoff_time = time.time() - (older_than_days * 86400)
            removed_count = 0
            
            for cache_file in self.cache_path.glob("*.json"):
                if cache_file.stat().st_mtime < cutoff_time:
                    cache_file.unlink()
                    removed_count += 1
            
            self.logger.info(f"Удалено {removed_count} старых файлов кэша")
            
        except Exception as e:
            self.logger.error(f"Ошибка очистки кэша: {e}")


# Пример использования
async def main():
    """Пример использования асинхронного загрузчика"""
    loader = AsyncHistoricalDataLoader()
    
    # Загрузка данных за последние 30 дней
    end_time = datetime.now()
    start_time = end_time - timedelta(days=30)
    
    # Загрузка для одного символа
    btc_data = await loader.load_historical_data_bulk('BTCUSDT', '60', start_time, end_time)
    print(f"Загружено {len(btc_data)} свечей для BTCUSDT")
    
    # Загрузка для нескольких символов
    symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
    multi_data = await loader.load_multiple_symbols(symbols, '60', days_back=7)
    
    for symbol, data in multi_data.items():
        print(f"{symbol}: {len(data)} свечей")
    
    # Информация о кэше
    cache_info = loader.get_cache_info()
    print(f"Кэш: {cache_info}")


if __name__ == "__main__":
    asyncio.run(main())