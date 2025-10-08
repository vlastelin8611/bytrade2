#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Симуляция торговли для проверки логики без реальных API ключей
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from strategies.adaptive_ml import AdaptiveMLStrategy
from config import get_ml_config
import json
from datetime import datetime

class MockBybitClient:
    """Мок-клиент для симуляции API Bybit"""
    
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        # Симуляция баланса
        self.balance = {
            'USDT': 100.0,  # 100 USDT для тестирования
            'BTC': 0.0,
            'ETH': 0.0,
            'ATOM': 0.0
        }
        self.orders = []
        self.positions = []
    
    def get_wallet_balance(self, account_type="UNIFIED"):
        """Симуляция получения баланса"""
        coins = []
        for coin, balance in self.balance.items():
            if balance > 0:
                coins.append({
                    'coin': coin,
                    'walletBalance': str(balance),
                    'availableToWithdraw': str(balance * 0.9),  # 90% доступно
                    'usdValue': str(balance if coin == 'USDT' else balance * 50000)  # Примерная цена
                })
        
        return {
            'retCode': 0,
            'retMsg': 'OK',
            'result': {
                'list': [{
                    'accountType': 'UNIFIED',
                    'totalEquity': str(sum(self.balance.values())),
                    'totalAvailableBalance': str(sum(self.balance.values()) * 0.9),
                    'coin': coins
                }]
            }
        }
    
    def get_klines(self, symbol, interval, limit=1000):
        """Симуляция получения klines"""
        # Генерируем тестовые данные
        import time
        current_time = int(time.time() * 1000)
        klines = []
        
        for i in range(limit):
            timestamp = current_time - (i * 4 * 60 * 60 * 1000)  # 4h интервалы
            open_price = 50000 + (i % 100) * 10
            close_price = open_price + (-50 + (i % 100))
            high_price = max(open_price, close_price) + 20
            low_price = min(open_price, close_price) - 20
            volume = 100 + (i % 50)
            
            klines.append([
                str(timestamp),
                str(open_price),
                str(high_price),
                str(low_price),
                str(close_price),
                str(volume),
                str(timestamp + 4 * 60 * 60 * 1000)
            ])
        
        return {
            'retCode': 0,
            'retMsg': 'OK',
            'result': {
                'list': klines
            }
        }
    
    def place_order(self, symbol, side, order_type, qty, price=None):
        """Симуляция размещения ордера"""
        # Проверяем баланс
        if side == 'Buy':
            required_usdt = float(qty) * (float(price) if price else 50000)
            if self.balance['USDT'] < required_usdt:
                return {
                    'retCode': 10001,
                    'retMsg': 'Insufficient balance',
                    'result': {}
                }
            # Списываем USDT
            self.balance['USDT'] -= required_usdt
            # Добавляем купленную монету
            coin = symbol.replace('USDT', '')
            self.balance[coin] = self.balance.get(coin, 0) + float(qty)
        
        elif side == 'Sell':
            coin = symbol.replace('USDT', '')
            if self.balance.get(coin, 0) < float(qty):
                return {
                    'retCode': 10001,
                    'retMsg': 'Insufficient balance',
                    'result': {}
                }
            # Списываем монету
            self.balance[coin] -= float(qty)
            # Добавляем USDT
            received_usdt = float(qty) * (float(price) if price else 50000)
            self.balance['USDT'] += received_usdt
        
        order_id = f"order_{len(self.orders) + 1}"
        order = {
            'orderId': order_id,
            'symbol': symbol,
            'side': side,
            'orderType': order_type,
            'qty': qty,
            'price': price,
            'status': 'Filled'
        }
        self.orders.append(order)
        
        return {
            'retCode': 0,
            'retMsg': 'OK',
            'result': order
        }

class MockDBManager:
    """Мок-менеджер базы данных"""
    def log_analysis(self, *args, **kwargs):
        pass

class MockConfigManager:
    """Мок-менеджер конфигурации"""
    def get_config(self, key, default=None):
        return default

def test_trading_simulation():
    """Тестирование торговой симуляции"""
    print("=== Симуляция торговли ===")
    
    # Создаем мок-клиент
    mock_client = MockBybitClient("test_key", "test_secret")
    
    # Проверяем начальный баланс
    print("\n💰 Начальный баланс:")
    balance_response = mock_client.get_wallet_balance()
    if balance_response['retCode'] == 0:
        for coin_info in balance_response['result']['list'][0]['coin']:
            print(f"   {coin_info['coin']}: {coin_info['walletBalance']}")
    
    # Создаем ML стратегию
    print("\n🤖 Инициализация ML стратегии...")
    ml_config = get_ml_config()
    mock_db = MockDBManager()
    mock_config = MockConfigManager()
    strategy = AdaptiveMLStrategy("test_strategy", ml_config, mock_client, mock_db, mock_config)
    
    # Заменяем клиент на мок (уже установлен в конструкторе)
    # strategy.client = mock_client
    
    # Тестируем обучение на исторических данных
    print("\n📚 Тестирование обучения...")
    symbols = ['BTCUSDT', 'ETHUSDT']
    
    for symbol in symbols:
        print(f"\n   Обучение для {symbol}...")
        try:
            # Получаем исторические данные
            klines_response = mock_client.get_klines(symbol, '4h', 1000)
            if klines_response['retCode'] == 0:
                klines = klines_response['result']['list']
                print(f"   ✅ Получено {len(klines)} klines")
                
                # Пытаемся обучить модель
                training_result = strategy.train_on_historical_data(symbol, klines)
                if training_result:
                    print(f"   ✅ Модель обучена для {symbol}")
                else:
                    print(f"   ❌ Ошибка обучения для {symbol}")
            else:
                print(f"   ❌ Ошибка получения данных для {symbol}")
        except Exception as e:
            print(f"   ❌ Исключение при обучении {symbol}: {e}")
    
    # Тестируем торговые сигналы
    print("\n📊 Тестирование торговых сигналов...")
    
    # Симулируем получение сигнала на покупку
    print("\n   Тест 1: Сигнал на покупку BTCUSDT")
    try:
        # Размещаем ордер на покупку
        order_result = mock_client.place_order(
            symbol='BTCUSDT',
            side='Buy',
            order_type='Market',
            qty='0.001',  # Покупаем 0.001 BTC
            price='50000'
        )
        
        if order_result['retCode'] == 0:
            print(f"   ✅ Ордер размещен: {order_result['result']['orderId']}")
        else:
            print(f"   ❌ Ошибка размещения ордера: {order_result['retMsg']}")
    except Exception as e:
        print(f"   ❌ Исключение при размещении ордера: {e}")
    
    # Проверяем баланс после торговли
    print("\n💰 Баланс после торговли:")
    balance_response = mock_client.get_wallet_balance()
    if balance_response['retCode'] == 0:
        for coin_info in balance_response['result']['list'][0]['coin']:
            print(f"   {coin_info['coin']}: {coin_info['walletBalance']}")
    
    # Тестируем недостаточный баланс
    print("\n   Тест 2: Недостаточный баланс")
    try:
        # Пытаемся купить на сумму больше доступного баланса
        order_result = mock_client.place_order(
            symbol='BTCUSDT',
            side='Buy',
            order_type='Market',
            qty='10',  # Покупаем 10 BTC (больше чем есть USDT)
            price='50000'
        )
        
        if order_result['retCode'] == 0:
            print(f"   ❌ Неожиданно: ордер прошел при недостатке средств")
        else:
            print(f"   ✅ Правильно: {order_result['retMsg']}")
    except Exception as e:
        print(f"   ❌ Исключение: {e}")
    
    print("\n✅ Симуляция торговли завершена")

if __name__ == "__main__":
    test_trading_simulation()