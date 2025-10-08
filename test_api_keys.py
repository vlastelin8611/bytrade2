#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование API ключей Bybit
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from config import get_api_credentials
from api.bybit_client import BybitClient
import time

def test_api_keys():
    """Тестирование API ключей"""
    print("=== Тестирование API ключей Bybit ===")
    
    # Получаем API ключи
    try:
        credentials = get_api_credentials()
        api_key = credentials['api_key']
        api_secret = credentials['api_secret']
        testnet = credentials['testnet']
        
        print(f"\n🔑 API Key: {api_key[:10]}...")
        print(f"🔐 API Secret: {api_secret[:10]}...")
        print(f"🧪 Testnet: {testnet}")
        
    except Exception as e:
        print(f"❌ Ошибка получения API ключей: {e}")
        return
    
    # Тестируем подключение к testnet
    print(f"\n📡 Тестирование подключения к testnet...")
    try:
        testnet_client = BybitClient(api_key, api_secret, testnet=True)
        
        # Проверяем время сервера
        server_time = testnet_client.get_server_time()
        print(f"✅ Testnet время сервера: {server_time}")
        
        # Проверяем баланс
        balance = testnet_client.get_wallet_balance()
        if balance and balance.get('retCode') == 0:
            print(f"✅ Testnet баланс получен успешно")
            if balance['result']['list']:
                for coin_info in balance['result']['list'][0].get('coin', []):
                    if float(coin_info['walletBalance']) > 0:
                        print(f"   {coin_info['coin']}: {coin_info['walletBalance']}")
        else:
            print(f"❌ Testnet ошибка баланса: {balance.get('retMsg', 'Unknown error') if balance else 'No response'}")
            
    except Exception as e:
        print(f"❌ Testnet исключение: {e}")
    
    # Тестируем подключение к mainnet
    print(f"\n📡 Тестирование подключения к mainnet...")
    try:
        mainnet_client = BybitClient(api_key, api_secret, testnet=False)
        
        # Проверяем время сервера
        server_time = mainnet_client.get_server_time()
        print(f"✅ Mainnet время сервера: {server_time}")
        
        # Проверяем баланс
        balance = mainnet_client.get_wallet_balance()
        if balance and balance.get('retCode') == 0:
            print(f"✅ Mainnet баланс получен успешно")
            if balance['result']['list']:
                for coin_info in balance['result']['list'][0].get('coin', []):
                    if float(coin_info['walletBalance']) > 0:
                        print(f"   {coin_info['coin']}: {coin_info['walletBalance']}")
        else:
            print(f"❌ Mainnet ошибка баланса: {balance.get('retMsg', 'Unknown error') if balance else 'No response'}")
            
    except Exception as e:
        print(f"❌ Mainnet исключение: {e}")
    
    # Рекомендации
    print(f"\n💡 Рекомендации:")
    print(f"1. Если testnet работает, а mainnet нет - проверьте права API ключа")
    print(f"2. Если оба не работают - ключи могут быть недействительными")
    print(f"3. Для testnet используйте ключи с https://testnet.bybit.com/")
    print(f"4. Для mainnet используйте ключи с https://www.bybit.com/")

if __name__ == "__main__":
    test_api_keys()