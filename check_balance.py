#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки баланса кошелька через API Bybit
"""

import sys
import os
import json

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from api.bybit_client import BybitClient
    from config import API_KEY, API_SECRET, USE_TESTNET
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

def main():
    """Основная функция"""
    try:
        print("🔄 Загрузка API ключей...")
        api_key = API_KEY
        api_secret = API_SECRET
        testnet = USE_TESTNET
        print(f"✅ API ключи загружены (testnet: {testnet})")
        
        print("🔄 Инициализация API клиента...")
        client = BybitClient(api_key, api_secret, testnet=testnet)
        print("✅ API клиент инициализирован")
        
        print("🔄 Получение баланса кошелька...")
        balance = client.get_wallet_balance()
        
        print("\n" + "="*50)
        print("💰 БАЛАНС КОШЕЛЬКА")
        print("="*50)
        print(json.dumps(balance, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Ошибка получения баланса: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()