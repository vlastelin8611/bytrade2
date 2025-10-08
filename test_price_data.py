#!/usr/bin/env python3
"""
Test script to examine price data and label generation
"""

def test_label_generation():
    """Test label generation with sample price data"""
    
    # Sample price data with realistic 4h candle changes
    sample_prices = [
        100000.0,  # Base price
        100050.0,  # +0.05%
        100025.0,  # -0.025%
        100150.0,  # +0.125%
        99950.0,   # -0.2%
        100100.0,  # +0.15%
        100080.0,  # -0.02%
        100200.0,  # +0.12%
        99800.0,   # -0.4%
        100300.0,  # +0.5%
    ]
    
    print("Testing label generation with sample data:")
    print("=" * 50)
    
    labels_001 = []   # 0.1% threshold
    labels_0005 = []  # 0.05% threshold
    labels_0001 = []  # 0.01% threshold
    
    for i in range(1, len(sample_prices)):
        current_price = sample_prices[i-1]
        future_price = sample_prices[i]
        change = (future_price - current_price) / current_price
        
        print(f"Step {i}: {current_price:.2f} -> {future_price:.2f}, change: {change:.6f} ({change*100:.4f}%)")
        
        abs_change = abs(change)
        
        # Test different thresholds
        # 0.1% threshold
        if abs_change > 0.001:
            label_001 = 1 if change > 0 else -1
        else:
            label_001 = 0
        
        # 0.05% threshold
        if abs_change > 0.0005:
            label_0005 = 1 if change > 0 else -1
        else:
            label_0005 = 0
        
        # 0.01% threshold
        if abs_change > 0.0001:
            label_0001 = 1 if change > 0 else -1
        else:
            label_0001 = 0
        
        print(f"  Labels - 0.1%: {label_001}, 0.05%: {label_0005}, 0.01%: {label_0001}")
        
        labels_001.append(label_001)
        labels_0005.append(label_0005)
        labels_0001.append(label_0001)
    
    # Count labels
    def count_labels(labels):
        counts = {-1: 0, 0: 0, 1: 0}
        for label in labels:
            counts[label] += 1
        return counts
    
    print(f"\nLabel distribution:")
    print(f"0.1% threshold: {count_labels(labels_001)}")
    print(f"0.05% threshold: {count_labels(labels_0005)}")
    print(f"0.01% threshold: {count_labels(labels_0001)}")
    
    # Check diversity
    def check_diversity(labels, name):
        unique_labels = set(labels)
        counts = count_labels(labels)
        min_class_size = min(counts.values()) if counts.values() else 0
        
        print(f"\n{name}:")
        print(f"  Unique labels: {len(unique_labels)}")
        print(f"  Min class size: {min_class_size}")
        print(f"  Passes diversity check (>=2 unique): {len(unique_labels) >= 2}")
        print(f"  Passes min class check (>=3 per class): {min_class_size >= 3}")
    
    check_diversity(labels_001, "0.1% threshold")
    check_diversity(labels_0005, "0.05% threshold") 
    check_diversity(labels_0001, "0.01% threshold")

if __name__ == "__main__":
    test_label_generation()