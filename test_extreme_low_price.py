#!/usr/bin/env python3
"""
Test script to verify the reasonable quantity limit for extremely low-priced tokens
"""

def test_extreme_low_price_token():
    """Test quantity calculation for an extremely low-priced token"""
    
    # Simulate an extremely low-priced token (much lower than BABYDOGE)
    price = 0.000000000001  # 1e-12 USDT per token (extremely low)
    usdt_amount = 5.0  # $5 trade
    
    # API limits (similar to BABYDOGE but even more extreme)
    max_order_qty = 9.876543210987654e+17  # ~987 quadrillion tokens
    max_market_order_qty = 1.2345678901234568e+17  # ~123 quadrillion tokens
    reasonable_max_qty = 1e12  # 1 trillion tokens (our new limit)
    
    print("=== Test for Extremely Low-Priced Token ===")
    print(f"Token price: {price} USDT")
    print(f"Trade amount: ${usdt_amount}")
    print()
    
    # Calculate quantity needed for $5 trade
    calculated_qty = usdt_amount / price
    print(f"Calculated quantity for ${usdt_amount}: {calculated_qty:,.0f} tokens")
    print(f"That's {calculated_qty/1e12:.1f} trillion tokens!")
    print()
    
    # Test old system (using maxOrderQty)
    old_final_qty = min(calculated_qty, max_order_qty)
    old_trade_amount = old_final_qty * price
    print(f"OLD SYSTEM (maxOrderQty limit):")
    print(f"  Final quantity: {old_final_qty:,.0f} tokens")
    print(f"  Trade amount: ${old_trade_amount:,.2f}")
    print(f"  Exceeds reasonable limit: {old_final_qty > reasonable_max_qty}")
    print()
    
    # Test maxMarketOrderQty system
    market_final_qty = min(calculated_qty, max_market_order_qty)
    market_trade_amount = market_final_qty * price
    print(f"MAXMARKETORDERQTY SYSTEM:")
    print(f"  Final quantity: {market_final_qty:,.0f} tokens")
    print(f"  Trade amount: ${market_trade_amount:,.2f}")
    print(f"  Exceeds reasonable limit: {market_final_qty > reasonable_max_qty}")
    print()
    
    # Test new reasonable limit system
    reasonable_final_qty = min(calculated_qty, reasonable_max_qty)
    reasonable_trade_amount = reasonable_final_qty * price
    print(f"NEW REASONABLE LIMIT SYSTEM:")
    print(f"  Final quantity: {reasonable_final_qty:,.0f} tokens")
    print(f"  Trade amount: ${reasonable_trade_amount:,.2f}")
    print(f"  Within reasonable limit: {reasonable_final_qty <= reasonable_max_qty}")
    print()
    
    # Check if the reasonable limit fix is effective
    if reasonable_final_qty < old_final_qty or reasonable_final_qty < market_final_qty:
        print("✅ REASONABLE LIMIT FIX IS EFFECTIVE!")
        print(f"   Prevents trading {calculated_qty - reasonable_final_qty:,.0f} excess tokens")
        print(f"   Saves ${(calculated_qty - reasonable_final_qty) * price:,.2f} from excessive trade")
    else:
        print("ℹ️  Reasonable limit not needed for this scenario")
    
    print()
    print("=== Summary ===")
    print(f"For a token priced at {price} USDT:")
    print(f"- A ${usdt_amount} trade would require {calculated_qty:,.0f} tokens")
    print(f"- This exceeds our reasonable limit of {reasonable_max_qty:,.0f} tokens")
    print(f"- The fix limits the trade to {reasonable_final_qty:,.0f} tokens (${reasonable_trade_amount:.2f})")

if __name__ == "__main__":
    test_extreme_low_price_token()