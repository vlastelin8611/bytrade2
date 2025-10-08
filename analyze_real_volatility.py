#!/usr/bin/env python3
"""
Анализ реальной волатильности данных для определения оптимального порога
"""

import os
import sys
import json
import numpy as np
from collections import Counter

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def analyze_price_movements(data_file):
    """Анализирует движения цен в реальных данных"""
    
    if not os.path.exists(data_file):
        print(f"❌ Файл {data_file} не найден")
        return
    
    print(f"📊 Анализ файла: {data_file}")
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return
    
    # Проверяем структуру данных
    if 'tickers' in data:
        tickers = data['tickers']
        print(f"📊 Найдено {len(tickers)} тикеров")
        
        all_changes = []
        analyzed_count = 0
        
        for ticker in tickers:
            if analyzed_count >= 10:  # Анализируем только первые 10 для экономии времени
                break
                
            symbol = ticker.get('symbol', 'Unknown')
            price_change_percent = ticker.get('priceChangePercent', '0')
            
            try:
                change_percent = float(price_change_percent)
                abs_change = abs(change_percent / 100)  # Конвертируем в десятичную дробь
                all_changes.append(abs_change)
                
                print(f"🔍 {symbol}: {change_percent}% ({abs_change:.6f})")
                analyzed_count += 1
                
            except (ValueError, TypeError):
                continue
        
        if all_changes:
            print(f"\n📈 СТАТИСТИКА ПО {len(all_changes)} ИЗМЕНЕНИЯМ")
            all_changes_array = np.array(all_changes)
            print(f"Макс. изменение: {max(all_changes)*100:.4f}%")
            print(f"Среднее изменение: {np.mean(all_changes)*100:.4f}%")
            print(f"Медиана: {np.median(all_changes)*100:.4f}%")
            print(f"95-й процентиль: {np.percentile(all_changes, 95)*100:.4f}%")
            print(f"99-й процентиль: {np.percentile(all_changes, 99)*100:.4f}%")
            
            print(f"\n🎯 АНАЛИЗ ПОРОГОВ:")
            thresholds = [0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.02]
            for threshold in thresholds:
                above_threshold = sum(1 for c in all_changes if c > threshold)
                percentage = (above_threshold / len(all_changes)) * 100
                status = "✅ ХОРОШО" if 10 <= percentage <= 70 else "⚠️ ПРОВЕРИТЬ" if percentage > 0 else "❌ СЛИШКОМ ВЫСОКИЙ"
                print(f"{threshold*100:.3f}%: {above_threshold}/{len(all_changes)} ({percentage:.1f}%) {status}")
        
    else:
        print("❌ Неожиданная структура данных")

def main():
    """Основная функция"""
    
    # Ищем файлы данных
    data_dir = os.path.expanduser("~/AppData/Local/BybitTradingBot/data")
    tickers_file = os.path.join(data_dir, "tickers_data.json")
    
    print("🔍 Анализ реальной волатильности данных")
    print("=" * 50)
    
    if os.path.exists(tickers_file):
        analyze_price_movements(tickers_file)
    elif os.path.exists("tickers_data_copy.json"):
        print(f"📁 Используем локальную копию: tickers_data_copy.json")
        analyze_price_movements("tickers_data_copy.json")
    else:
        print(f"❌ Файл данных не найден: {tickers_file}")
        
        # Попробуем найти в текущей директории
        local_file = "tickers_data.json"
        if os.path.exists(local_file):
            print(f"📁 Найден локальный файл: {local_file}")
            analyze_price_movements(local_file)
        else:
            print("❌ Файлы данных не найдены")

if __name__ == "__main__":
    main()