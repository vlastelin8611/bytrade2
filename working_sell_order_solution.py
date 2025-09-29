#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
РАБОЧЕЕ РЕШЕНИЕ: Продажа криптовалют на Bybit Testnet
====================================================

Этот файл содержит проверенное рабочее решение для продажи самого дешевого актива 
в портфеле на фиксированную сумму в USDT.

Дата создания: 29.09.2025
Статус: ✅ РАБОТАЕТ
"""

import asyncio
from PySide6.QtCore import QTimer

class WorkingSellOrderSolution:
    """
    Класс с рабочим решением для продажи криптовалют на Bybit
    """
    
    def sell_cheapest_asset_fixed_amount(self):
        """
        ✅ РАБОЧИЙ МЕТОД: Продажа самого дешевого актива на сумму 5 USDT
        
        Ключевые особенности решения:
        1. Получение актуального баланса через API в реальном времени
        2. Поиск самого дешевого актива (исключая стейблкоины)
        3. Использование marketUnit='quoteCoin' для продажи на фиксированную сумму
        4. Асинхронное выполнение через QTimer
        5. Полная обработка ошибок и блокировка кнопки
        """
        try:
            self.add_log_message("🔄 Начинаю поиск самого дешевого актива для продажи...")
            
            # Отключаем кнопку на время выполнения
            self.sell_lowest_btn.setEnabled(False)
            self.sell_lowest_btn.setText("⏳ Продажа...")
            
            # Используем QTimer для неблокирующего выполнения
            def execute_sell_async():
                try:
                    # Проверяем наличие торгового воркера
                    if not hasattr(self, 'trading_worker') or self.trading_worker is None:
                        self.add_log_message("❌ Торговый воркер не инициализирован")
                        return
                    
                    # Проверяем наличие API клиента
                    if not hasattr(self.trading_worker, 'bybit_client') or self.trading_worker.bybit_client is None:
                        self.add_log_message("❌ API клиент не инициализирован")
                        return
                    
                    # 🔑 КЛЮЧЕВАЯ ЧАСТЬ: Получаем актуальный баланс
                    self.add_log_message("📊 Получаю актуальный баланс...")
                    balance = self.trading_worker.bybit_client.get_unified_balance_flat()
                    
                    if not balance or not balance.get('coins'):
                        self.add_log_message("❌ Не удалось получить данные о балансе")
                        return
                    
                    # Фильтруем монеты с положительным балансом (исключаем стейблкоины)
                    tradeable_coins = []
                    for coin in balance['coins']:
                        coin_name = coin.get('coin', '')
                        wallet_balance = float(coin.get('walletBalance', 0))
                        usd_value = float(coin.get('usdValue', 0))
                        
                        # Исключаем стейблкоины и монеты с очень малым балансом
                        if (coin_name not in ['USDT', 'USDC', 'BUSD', 'DAI'] and 
                            wallet_balance > 0 and usd_value > 1.0):  # Минимум $1
                            tradeable_coins.append({
                                'coin': coin_name,
                                'balance': wallet_balance,
                                'usd_value': usd_value
                            })
                    
                    if not tradeable_coins:
                        self.add_log_message("❌ Нет активов для продажи (минимум $1)")
                        return
                    
                    # Находим актив с минимальной USD стоимостью
                    lowest_coin = min(tradeable_coins, key=lambda c: c['usd_value'])
                    symbol = lowest_coin['coin'] + "USDT"
                    
                    self.add_log_message(f"🎯 Выбран актив для продажи: {symbol}")
                    self.add_log_message(f"💰 Стоимость позиции: ${lowest_coin['usd_value']:.2f}")
                    self.add_log_message(f"📊 Количество: {lowest_coin['balance']:.6f} {lowest_coin['coin']}")
                    
                    # 🔑 КЛЮЧЕВАЯ ЧАСТЬ: Выполняем продажу с правильными параметрами
                    try:
                        # Продаем на сумму 5 USDT (используем marketUnit='quoteCoin')
                        sell_amount_usdt = "5"
                        self.add_log_message(f"💸 Размещаю ордер на продажу {symbol} на {sell_amount_usdt} USDT...")
                        
                        # ✅ РАБОЧИЕ ПАРАМЕТРЫ:
                        order_result = self.trading_worker.bybit_client.place_order(
                            category='spot',                    # Спотовая торговля
                            symbol=symbol,                      # Например, ETHUSDT
                            side='Sell',                        # Продажа
                            order_type='Market',                # Рыночный ордер
                            qty=sell_amount_usdt,               # Сумма в USDT (5)
                            marketUnit='quoteCoin'              # 🔑 КЛЮЧЕВОЙ ПАРАМЕТР!
                        )
                        
                        self.add_log_message(f"📋 Результат API: {order_result}")
                        
                        if order_result:
                            self.add_log_message(f"✅ Успешно размещен ордер на продажу {symbol} на {sell_amount_usdt} USDT")
                            
                            # Рассчитываем примерное количество проданных монет
                            try:
                                tickers = self.trading_worker.bybit_client.get_tickers(category="spot")
                                coin_price = 0
                                if tickers and isinstance(tickers, list):
                                    for ticker in tickers:
                                        if ticker.get('symbol') == symbol:
                                            coin_price = float(ticker.get('lastPrice', 0))
                                            break
                                if coin_price > 0:
                                    estimated_qty = float(sell_amount_usdt) / coin_price
                                    self.add_log_message(f"📊 Примерное количество: ~{estimated_qty:.6f} {lowest_coin['coin']}")
                            except Exception as price_error:
                                self.add_log_message(f"⚠️ Не удалось получить цену: {price_error}")
                        else:
                            self.add_log_message(f"❌ Не удалось разместить ордер на продажу {symbol}")
                            
                    except Exception as api_error:
                        self.add_log_message(f"❌ Ошибка API при продаже {symbol}: {str(api_error)}")
                        self.logger.error(f"API Error: {api_error}")
                    
                except Exception as e:
                    self.add_log_message(f"❌ Ошибка при продаже: {str(e)}")
                    self.logger.error(f"Ошибка в sell_lowest_ticker: {e}")
                finally:
                    # Возвращаем кнопку в исходное состояние
                    self.sell_lowest_btn.setEnabled(True)
                    self.sell_lowest_btn.setText("💸 Продать самый дешевый")
            
            # Выполняем асинхронно через QTimer
            QTimer.singleShot(100, execute_sell_async)
            
        except Exception as e:
            self.add_log_message(f"❌ Критическая ошибка при продаже: {str(e)}")
            self.logger.error(f"Критическая ошибка в sell_lowest_ticker: {e}")
            # Возвращаем кнопку в исходное состояние при ошибке
            self.sell_lowest_btn.setEnabled(True)
            self.sell_lowest_btn.setText("💸 Продать самый дешевый")


# 🔧 АЛЬТЕРНАТИВНЫЕ ВАРИАНТЫ ИСПОЛЬЗОВАНИЯ

def sell_btc_for_usdt(api_client, amount_usdt: str = "10"):
    """
    Продажа BTC на фиксированную сумму в USDT
    """
    return api_client.place_order(
        category='spot',
        symbol='BTCUSDT',
        side='Sell',
        order_type='Market',
        qty=amount_usdt,
        marketUnit='quoteCoin'  # qty в USDT
    )

def sell_eth_fixed_quantity(api_client, eth_quantity: str = "0.01"):
    """
    Продажа фиксированного количества ETH
    """
    return api_client.place_order(
        category='spot',
        symbol='ETHUSDT',
        side='Sell',
        order_type='Market',
        qty=eth_quantity,
        marketUnit='baseCoin'  # qty в ETH
    )

def sell_all_of_coin(api_client, coin_symbol: str, balance: float):
    """
    Продажа всего количества определенной монеты
    """
    return api_client.place_order(
        category='spot',
        symbol=f'{coin_symbol}USDT',
        side='Sell',
        order_type='Market',
        qty=str(balance),
        marketUnit='baseCoin'  # qty в базовой валюте
    )


# 📊 ПРИМЕРЫ УСПЕШНЫХ ЛОГОВ

"""
УСПЕШНЫЙ РЕЗУЛЬТАТ:
🔄 Начинаю поиск самого дешевого актива для продажи...
📊 Получаю актуальный баланс...
🎯 Выбран актив для продажи: ETHUSDT
💰 Стоимость позиции: $17.09
📊 Количество: 0.004137 ETH
💸 Размещаю ордер на продажу ETHUSDT на 5 USDT...
📋 Результат API: {'retCode': 0, 'retMsg': 'OK', 'result': {...}}
✅ Успешно размещен ордер на продажу ETHUSDT на 5 USDT
📊 Примерное количество: ~0.001037 ETH
"""


# 🚨 ВАЖНЫЕ ЗАМЕЧАНИЯ

"""
КРИТИЧЕСКИ ВАЖНЫЕ МОМЕНТЫ:

1. marketUnit='quoteCoin' - ОБЯЗАТЕЛЬНЫЙ параметр для продажи на сумму
2. Получение актуального баланса через get_unified_balance_flat()
3. Фильтрация стейблкоинов: ['USDT', 'USDC', 'BUSD', 'DAI']
4. Минимальная стоимость позиции: $1 для продажи
5. Продажа на фиксированную сумму: 5 USDT

ЛОГИКА ВЫБОРА АКТИВА:
- Исключаются стейблкоины
- Исключаются позиции менее $1
- Выбирается актив с минимальной USD стоимостью
- Используется min() функция для поиска

ПАРАМЕТРЫ marketUnit:
- 'quoteCoin' - qty в валюте котировки (USDT для ETHUSDT)
- 'baseCoin' - qty в базовой валюте (ETH для ETHUSDT)
"""


# 🔍 АЛГОРИТМ ПОИСКА САМОГО ДЕШЕВОГО АКТИВА

def find_cheapest_tradeable_asset(balance_data):
    """
    Алгоритм поиска самого дешевого актива для продажи
    """
    tradeable_coins = []
    
    for coin in balance_data['coins']:
        coin_name = coin.get('coin', '')
        wallet_balance = float(coin.get('walletBalance', 0))
        usd_value = float(coin.get('usdValue', 0))
        
        # Критерии отбора:
        # 1. Не стейблкоин
        # 2. Положительный баланс
        # 3. Стоимость больше $1
        if (coin_name not in ['USDT', 'USDC', 'BUSD', 'DAI'] and 
            wallet_balance > 0 and usd_value > 1.0):
            
            tradeable_coins.append({
                'coin': coin_name,
                'balance': wallet_balance,
                'usd_value': usd_value,
                'symbol': coin_name + 'USDT'
            })
    
    if not tradeable_coins:
        return None
    
    # Возвращаем актив с минимальной USD стоимостью
    return min(tradeable_coins, key=lambda c: c['usd_value'])


if __name__ == "__main__":
    print("✅ Рабочее решение для продажи криптовалют на Bybit загружено!")
    print("📖 Основной метод: sell_cheapest_asset_fixed_amount()")
    print("🔑 Ключевые параметры: marketUnit='quoteCoin', qty='5' USDT")
    print("🎯 Логика: Поиск самого дешевого актива > $1, исключая стейблкоины")