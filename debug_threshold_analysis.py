#!/usr/bin/env python3
"""
Debug script to analyze why threshold-based label generation isn't working
"""
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from api.bybit_client import BybitClient

def load_api_credentials():
    """Load API credentials from keys file"""
    keys_file = Path(__file__).parent / 'keys'
    if not keys_file.exists():
        print("❌ Файл keys не найден")
        return None, None
    
    try:
        with open(keys_file, 'r') as f:
            lines = f.readlines()
            api_key = lines[0].strip()
            api_secret = lines[1].strip()
            return api_key, api_secret
    except Exception as e:
        print(f"❌ Ошибка загрузки ключей: {e}")
        return None, None

def analyze_price_movements(klines_data, symbol):
    """Analyze price movements in klines data"""
    if not klines_data or len(klines_data) < 2:
        return None
    
    movements = []
    for i in range(1, len(klines_data)):
        prev_close = float(klines_data[i-1][4])  # Previous close
        curr_close = float(klines_data[i][4])    # Current close
        
        if prev_close > 0:
            change = (curr_close - prev_close) / prev_close
            movements.append(change)
    
    if not movements:
        return None
    
    # Analyze movements
    analysis = {
        'symbol': symbol,
        'total_movements': len(movements),
        'min_change': min(movements),
        'max_change': max(movements),
        'avg_change': sum(movements) / len(movements),
        'movements_above_0_001': sum(1 for m in movements if abs(m) > 0.001),  # 0.1%
        'movements_above_0_0005': sum(1 for m in movements if abs(m) > 0.0005),  # 0.05%
        'movements_above_0_0001': sum(1 for m in movements if abs(m) > 0.0001),  # 0.01%
        'movements_above_0_00005': sum(1 for m in movements if abs(m) > 0.00005),  # 0.005%
        'movements_above_0_00001': sum(1 for m in movements if abs(m) > 0.00001),  # 0.001%
    }
    
    # Generate labels for different thresholds
    thresholds = [0.001, 0.0005, 0.0001, 0.00005, 0.00001]
    for threshold in thresholds:
        labels = []
        for change in movements:
            if abs(change) > threshold:
                labels.append(1 if change > 0 else -1)
            else:
                labels.append(0)
        
        unique_labels = set(labels)
        analysis[f'labels_threshold_{threshold}'] = {
            'unique_labels': len(unique_labels),
            'label_counts': {str(label): labels.count(label) for label in unique_labels},
            'min_class_size': min(labels.count(label) for label in unique_labels) if unique_labels else 0
        }
    
    return analysis

def main():
    print("🔍 Анализ порогов для генерации меток")
    print("=" * 50)
    
    # Load API credentials
    api_key, api_secret = load_api_credentials()
    if not api_key or not api_secret:
        print("❌ Не удалось загрузить API ключи")
        return
    
    # Initialize client
    try:
        client = BybitClient(api_key, api_secret)
        print("✅ API клиент инициализирован")
    except Exception as e:
        print(f"❌ Ошибка инициализации API клиента: {e}")
        return
    
    # Test symbols
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOGEUSDT']
    
    for symbol in test_symbols:
        print(f"\n📊 Анализ {symbol}...")
        
        try:
            # Get klines data (4h interval, last 100 candles)
            klines = client.get_klines(
                category='linear',
                symbol=symbol,
                interval='4h',
                limit=100
            )
            
            if not klines:
                print(f"❌ Нет данных для {symbol}")
                continue
            
            analysis = analyze_price_movements(klines, symbol)
            if not analysis:
                print(f"❌ Не удалось проанализировать {symbol}")
                continue
            
            print(f"📈 Всего движений: {analysis['total_movements']}")
            print(f"📉 Мин. изменение: {analysis['min_change']:.6f} ({analysis['min_change']*100:.4f}%)")
            print(f"📈 Макс. изменение: {analysis['max_change']:.6f} ({analysis['max_change']*100:.4f}%)")
            print(f"📊 Среднее изменение: {analysis['avg_change']:.6f} ({analysis['avg_change']*100:.4f}%)")
            
            print(f"\n🎯 Движения выше порогов:")
            print(f"  > 0.1%:   {analysis['movements_above_0_001']}")
            print(f"  > 0.05%:  {analysis['movements_above_0_0005']}")
            print(f"  > 0.01%:  {analysis['movements_above_0_0001']}")
            print(f"  > 0.005%: {analysis['movements_above_0_00005']}")
            print(f"  > 0.001%: {analysis['movements_above_0_00001']}")
            
            print(f"\n🏷️ Анализ меток:")
            thresholds = [0.001, 0.0005, 0.0001, 0.00005, 0.00001]
            for threshold in thresholds:
                label_info = analysis[f'labels_threshold_{threshold}']
                print(f"  Порог {threshold*100:.3f}%: {label_info['unique_labels']} уникальных меток, "
                      f"мин. размер класса: {label_info['min_class_size']}")
                print(f"    Распределение: {label_info['label_counts']}")
            
        except Exception as e:
            print(f"❌ Ошибка анализа {symbol}: {e}")
    
    print(f"\n✅ Анализ завершен")

if __name__ == "__main__":
    main()