#!/usr/bin/env python3
"""
Simple threshold test using synthetic data to understand label generation
"""
import random
import numpy as np

def generate_realistic_price_data(num_points=1000, base_price=50000, volatility=0.02):
    """Generate realistic price data with controlled volatility"""
    prices = [base_price]
    
    for i in range(num_points - 1):
        # Random walk with mean reversion
        change = random.gauss(0, volatility)
        # Add some trend and mean reversion
        if random.random() < 0.1:  # 10% chance of significant move
            change *= 3
        
        new_price = prices[-1] * (1 + change)
        prices.append(max(new_price, base_price * 0.5))  # Prevent negative prices
    
    return prices

def analyze_threshold_effectiveness(prices, thresholds):
    """Analyze how different thresholds affect label generation"""
    if len(prices) < 2:
        return {}
    
    # Calculate price changes
    changes = []
    for i in range(1, len(prices)):
        change = (prices[i] - prices[i-1]) / prices[i-1]
        changes.append(change)
    
    results = {}
    
    for threshold in thresholds:
        labels = []
        for change in changes:
            if abs(change) > threshold:
                labels.append(1 if change > 0 else -1)
            else:
                labels.append(0)
        
        unique_labels = set(labels)
        label_counts = {label: labels.count(label) for label in unique_labels}
        min_class_size = min(label_counts.values()) if label_counts else 0
        
        results[threshold] = {
            'unique_labels': len(unique_labels),
            'label_counts': label_counts,
            'min_class_size': min_class_size,
            'diversity_ok': len(unique_labels) >= 2,
            'min_class_ok': min_class_size >= 2,
            'both_ok': len(unique_labels) >= 2 and min_class_size >= 2
        }
        
        # Calculate statistics
        abs_changes = [abs(c) for c in changes]
        results[threshold]['stats'] = {
            'max_change': max(abs_changes),
            'min_change': min(abs_changes),
            'avg_change': sum(abs_changes) / len(abs_changes),
            'changes_above_threshold': sum(1 for c in abs_changes if c > threshold),
            'percentage_above_threshold': (sum(1 for c in abs_changes if c > threshold) / len(abs_changes)) * 100
        }
    
    return results

def main():
    print("🔍 Тест эффективности порогов для генерации меток")
    print("=" * 60)
    
    # Test different volatility scenarios
    volatility_scenarios = [
        (0.005, "Низкая волатильность (0.5%)"),
        (0.01, "Средняя волатильность (1%)"),
        (0.02, "Высокая волатильность (2%)"),
        (0.05, "Очень высокая волатильность (5%)")
    ]
    
    thresholds = [0.001, 0.0005, 0.0001, 0.00005, 0.00001]  # 0.1%, 0.05%, 0.01%, 0.005%, 0.001%
    
    for volatility, description in volatility_scenarios:
        print(f"\n📊 {description}")
        print("-" * 40)
        
        # Generate price data
        prices = generate_realistic_price_data(1000, 50000, volatility)
        
        # Analyze thresholds
        results = analyze_threshold_effectiveness(prices, thresholds)
        
        print(f"{'Порог':<8} {'Уник.':<6} {'Мин.кл.':<8} {'Выше%':<8} {'Макс.изм.':<10} {'Ср.изм.':<10} {'Статус'}")
        print("-" * 70)
        
        for threshold in thresholds:
            if threshold in results:
                r = results[threshold]
                stats = r['stats']
                status = "✅ ОК" if r['both_ok'] else "❌ НЕТ"
                
                print(f"{threshold*100:>6.3f}% {r['unique_labels']:<6} {r['min_class_size']:<8} "
                      f"{stats['percentage_above_threshold']:>6.1f}% {stats['max_change']*100:>8.3f}% "
                      f"{stats['avg_change']*100:>8.3f}% {status}")
        
        # Find optimal threshold
        optimal_thresholds = [t for t in thresholds if results[t]['both_ok']]
        if optimal_thresholds:
            best_threshold = max(optimal_thresholds)  # Highest threshold that works
            print(f"\n🎯 Оптимальный порог: {best_threshold*100:.3f}%")
        else:
            print(f"\n⚠️ Ни один порог не подходит для данной волатильности")
    
    print(f"\n✅ Анализ завершен")
    print(f"\n💡 Рекомендации:")
    print(f"   - Для 4-часовых данных используйте порог 0.01-0.05%")
    print(f"   - Для более коротких таймфреймов можно использовать более низкие пороги")
    print(f"   - Если все еще получаете только метку 0, проверьте реальную волатильность данных")

if __name__ == "__main__":
    main()