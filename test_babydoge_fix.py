#!/usr/bin/env python3
"""
Test script to verify BABYDOGEUSDT quantity calculation fix
"""

import math

def test_quantity_calculation():
    """Test the quantity calculation with the new maxMarketOrderQty limit"""
    
    # BABYDOGEUSDT parameters from the logs
    price = 0.000000001962600  # Calculated price
    effective_min_amount = 5.0  # $5 minimum trade
    min_order_qty = 0.1
    min_order_amt = 1.0
    qty_step = 0.1
    
    # Old maxOrderQty (problematic)
    old_max_order_qty = 9.876543210987654e+17
    
    # New maxMarketOrderQty (from API, still very large)
    new_max_market_order_qty = 1.2345678901234568e+17
    
    print("=== BABYDOGEUSDT Quantity Calculation Test ===")
    print(f"Price: {price}")
    print(f"Effective min amount: ${effective_min_amount}")
    print(f"Min order qty: {min_order_qty}")
    print(f"Min order amt: ${min_order_amt}")
    print(f"Qty step: {qty_step}")
    print()
    
    # Calculate effective_min_check
    effective_min_check = max(min_order_qty * price, effective_min_amount)
    print(f"Effective min check: ${effective_min_check}")
    
    # Calculate qty_needed
    qty_needed = effective_min_check / price
    print(f"Qty needed: {qty_needed}")
    
    # Round up with qty_step
    precision_decimals = len(str(qty_step).split('.')[-1]) if '.' in str(qty_step) else 0
    qty_before_limit = math.ceil(qty_needed / qty_step) * qty_step
    qty_before_limit = round(qty_before_limit, precision_decimals)
    print(f"Qty before max limit: {qty_before_limit}")
    
    # Apply old max limit
    old_final_qty = min(qty_before_limit, old_max_order_qty)
    print(f"Old final qty (with old maxOrderQty): {old_final_qty}")
    
    # Apply new max limit
    new_final_qty = min(qty_before_limit, new_max_market_order_qty)
    
    # Apply reasonable maximum limit (new fix)
    reasonable_max_qty = 1e12  # 1 trillion tokens
    reasonable_final_qty = min(qty_before_limit, reasonable_max_qty)
    
    print(f"Old final qty (with old maxOrderQty): {old_final_qty}")
    print(f"New final qty (with maxMarketOrderQty): {new_final_qty}")
    print(f"Reasonable final qty (with 1T limit): {reasonable_final_qty}")
    
    # Calculate final trade amounts
    old_trade_usdt = old_final_qty * price
    new_trade_usdt = new_final_qty * price
    reasonable_trade_usdt = reasonable_final_qty * price
    
    print()
    print("=== Results ===")
    print(f"Old system: {old_final_qty:,.1f} BABYDOGE = ${old_trade_usdt:.8f}")
    print(f"New system: {new_final_qty:,.1f} BABYDOGE = ${new_trade_usdt:.8f}")
    print(f"Reasonable system: {reasonable_final_qty:,.1f} BABYDOGE = ${reasonable_trade_usdt:.8f}")
    
    # Check if the reasonable limit fix is effective
    if reasonable_final_qty < old_final_qty:
        print("✅ Reasonable limit fix is working: Quantity is properly limited!")
        improvement = (old_final_qty - reasonable_final_qty) / old_final_qty * 100
        print(f"   Quantity reduced by {improvement:.1f}%")
        print(f"   Trade amount reduced from ${old_trade_usdt:.2f} to ${reasonable_trade_usdt:.2f}")
    else:
        print("⚠️  Reasonable limit fix may not be effective")
    
    # Check if quantity is now reasonable
    if reasonable_final_qty <= 1e12:
        print("✅ Quantity is now within reasonable limits (≤ 1 trillion tokens)")
    else:
        print("⚠️  Warning: Quantity is still extremely large")

if __name__ == "__main__":
    test_quantity_calculation()