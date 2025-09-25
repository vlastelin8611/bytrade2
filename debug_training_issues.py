#!/usr/bin/env python3
"""
Скрипт для диагностики проблем с обучением и проверки подлинности данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.api.bybit_client import BybitClient
from src.strategies.adaptive_ml import AdaptiveMLStrategy
from config import get_api_credentials
import json
import numpy as np
from collections import Counter
import statistics

def analyze_symbol_data(api_client, symbol, limit=1000):
    """Анализирует данные для конкретного символа"""
    print(f"\n🔍 Анализ данных для {symbol}:")
    
    try:
        # Получаем данные - используем правильную категорию
        response = api_client.get_klines('linear', symbol, '1h', limit)
        
        if isinstance(response, dict) and 'result' in response and 'list' in response['result']:
            raw_klines = response['result']['list']
        elif isinstance(response, dict) and 'list' in response:
            raw_klines = response['list']
        else:
            raw_klines = response
            
        if not raw_klines:
            print(f"❌ Нет данных для {symbol}")
            return None
            
        # Преобразуем в нужный формат
        klines = []
        for item in raw_klines:
            klines.append({
                'timestamp': int(item[0]),
                'open': float(item[1]),
                'high': float(item[2]),
                'low': float(item[3]),
                'close': float(item[4]),
                'volume': float(item[5])
            })
        
        print(f"📊 Загружено {len(klines)} записей")
        
        # Анализ данных на подлинность
        analysis = analyze_data_authenticity(klines)
        
        # Анализ меток
        labels_analysis = analyze_labels(klines)
        
        return {
            'symbol': symbol,
            'records_count': len(klines),
            'authenticity': analysis,
            'labels': labels_analysis
        }
        
    except Exception as e:
        print(f"❌ Ошибка для {symbol}: {e}")
        return None

def analyze_data_authenticity(klines):
    """Проверяет подлинность данных"""
    if len(klines) < 10:
        return {'status': 'insufficient_data'}
    
    # Проверка 1: Разумные цены
    prices = [k['close'] for k in klines]
    if any(p <= 0 for p in prices):
        return {'status': 'invalid_prices', 'issue': 'zero_or_negative_prices'}
    
    # Проверка 2: Разумная волатильность
    price_changes = []
    for i in range(1, len(prices)):
        change = abs(prices[i] - prices[i-1]) / prices[i-1]
        price_changes.append(change)
    
    avg_change = statistics.mean(price_changes)
    max_change = max(price_changes)
    
    # Слишком низкая волатильность может указывать на фейковые данные
    if avg_change < 0.0001:
        return {'status': 'suspicious', 'issue': 'too_low_volatility', 'avg_change': avg_change}
    
    # Слишком высокая волатильность тоже подозрительна
    if max_change > 0.5:
        return {'status': 'suspicious', 'issue': 'too_high_volatility', 'max_change': max_change}
    
    # Проверка 3: Логичность OHLC
    ohlc_errors = 0
    for k in klines:
        if not (k['low'] <= k['open'] <= k['high'] and 
                k['low'] <= k['close'] <= k['high']):
            ohlc_errors += 1
    
    if ohlc_errors > len(klines) * 0.01:  # Более 1% ошибок
        return {'status': 'invalid', 'issue': 'ohlc_logic_errors', 'error_rate': ohlc_errors/len(klines)}
    
    # Проверка 4: Объемы
    volumes = [k['volume'] for k in klines]
    zero_volumes = sum(1 for v in volumes if v == 0)
    
    if zero_volumes > len(volumes) * 0.1:  # Более 10% нулевых объемов
        return {'status': 'suspicious', 'issue': 'too_many_zero_volumes', 'zero_rate': zero_volumes/len(volumes)}
    
    # Проверка 5: Временные метки
    timestamps = [k['timestamp'] for k in klines]
    time_diffs = []
    for i in range(1, len(timestamps)):
        diff = timestamps[i-1] - timestamps[i]  # Данные идут в обратном порядке
        time_diffs.append(diff)
    
    expected_diff = 3600000  # 1 час в миллисекундах
    irregular_intervals = sum(1 for d in time_diffs if abs(d - expected_diff) > 60000)  # Отклонение более минуты
    
    if irregular_intervals > len(time_diffs) * 0.05:  # Более 5% неправильных интервалов
        return {'status': 'suspicious', 'issue': 'irregular_time_intervals', 'irregular_rate': irregular_intervals/len(time_diffs)}
    
    return {
        'status': 'authentic',
        'avg_volatility': avg_change,
        'max_volatility': max_change,
        'ohlc_errors': ohlc_errors,
        'zero_volumes_rate': zero_volumes/len(volumes)
    }

def analyze_labels(klines):
    """Анализирует распределение меток"""
    if len(klines) < 21:  # Минимум для анализа с окном 20
        return {'status': 'insufficient_data'}
    
    labels = []
    window = 20
    
    for j in range(window, len(klines) - 1):
        try:
            current_price = float(klines[j]['close'])
            future_price = float(klines[j + 1]['close'])
            change = (future_price - current_price) / current_price
            
            # Адаптивные пороги
            volatility = abs(float(klines[j]['high']) - float(klines[j]['low'])) / current_price
            threshold = max(0.001, volatility * 0.5)
            
            if change > threshold:
                labels.append(1)  # рост
            elif change < -threshold:
                labels.append(-1)  # падение
            else:
                labels.append(0)  # боковик
        except:
            continue
    
    if not labels:
        return {'status': 'no_labels'}
    
    label_counts = Counter(labels)
    unique_labels = len(label_counts)
    
    return {
        'status': 'success',
        'total_labels': len(labels),
        'unique_labels': unique_labels,
        'distribution': dict(label_counts),
        'balance_ratio': min(label_counts.values()) / max(label_counts.values()) if label_counts else 0
    }

def main():
    print("🔍 Диагностика проблем с обучением и проверка подлинности данных")
    print("=" * 70)
    
    # Инициализация
    api_creds = get_api_credentials()
    api_client = BybitClient(
        api_creds['api_key'],
        api_creds['api_secret'],
        api_creds['testnet']
    )
    
    # Получаем список символов
    print("\n📋 Получение списка символов...")
    try:
        symbols_response = api_client.get_instruments_info('spot')
        if symbols_response:
            all_symbols = []
            for item in symbols_response:
                symbol = item.get('symbol', '')
                status = item.get('status', '')
                if symbol.endswith('USDT') and status == 'Trading':
                    all_symbols.append(symbol)
        else:
            all_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'DOTUSDT', 'LINKUSDT']
            
        print(f"✅ Найдено {len(all_symbols)} торговых символов USDT")
        
        # Анализируем первые 10 символов для диагностики
        test_symbols = all_symbols[:10]
        print(f"\n🧪 Анализируем первые {len(test_symbols)} символов для диагностики...")
        
        results = []
        authentic_count = 0
        suspicious_count = 0
        invalid_count = 0
        
        for i, symbol in enumerate(test_symbols, 1):
            print(f"\n[{i}/{len(test_symbols)}] Анализ {symbol}...")
            result = analyze_symbol_data(api_client, symbol)
            
            if result:
                results.append(result)
                
                # Статистика подлинности
                auth_status = result['authenticity']['status']
                if auth_status == 'authentic':
                    authentic_count += 1
                    print(f"✅ Данные подлинные")
                elif auth_status == 'suspicious':
                    suspicious_count += 1
                    print(f"⚠️ Подозрительные данные: {result['authenticity']['issue']}")
                else:
                    invalid_count += 1
                    print(f"❌ Недействительные данные: {result['authenticity']['issue']}")
                
                # Статистика меток
                labels_info = result['labels']
                if labels_info['status'] == 'success':
                    print(f"📊 Меток: {labels_info['total_labels']}, уникальных: {labels_info['unique_labels']}")
                    print(f"📈 Распределение: {labels_info['distribution']}")
                else:
                    print(f"⚠️ Проблема с метками: {labels_info['status']}")
        
        # Итоговая статистика
        print(f"\n" + "=" * 70)
        print(f"📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"🔍 Проанализировано символов: {len(results)}")
        print(f"✅ Подлинные данные: {authentic_count}")
        print(f"⚠️ Подозрительные данные: {suspicious_count}")
        print(f"❌ Недействительные данные: {invalid_count}")
        
        if suspicious_count > 0 or invalid_count > 0:
            print(f"\n⚠️ ВНИМАНИЕ: Обнаружены проблемы с данными!")
            print(f"Рекомендуется проверить источник данных и настройки API.")
        else:
            print(f"\n✅ Все проверенные данные выглядят подлинными.")
        
        # Сохраняем результаты
        with open('training_diagnostics_results.json', 'w', encoding='utf-8') as f:
            json.dump({
                'total_symbols_available': len(all_symbols),
                'analyzed_symbols': len(results),
                'authenticity_stats': {
                    'authentic': authentic_count,
                    'suspicious': suspicious_count,
                    'invalid': invalid_count
                },
                'detailed_results': results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Результаты сохранены в training_diagnostics_results.json")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()