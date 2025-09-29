#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
РАБОЧЕЕ РЕШЕНИЕ: Покупка ETH на Bybit Testnet
===============================================

Этот файл содержит проверенное рабочее решение для покупки ETH на фиксированную сумму в USDT.
Решение было найдено после нескольких попыток и успешно протестировано.

Дата создания: 29.09.2025
Статус: ✅ РАБОТАЕТ
"""

import asyncio
from PySide6.QtCore import QTimer

class WorkingBuyOrderSolution:
    """
    Класс с рабочим решением для покупки ETH на Bybit
    """
    
    def buy_eth_fixed_amount(self):
        """
        ✅ РАБОЧИЙ МЕТОД: Покупка ETHUSDT на сумму 10 USDT
        
        Ключевые особенности решения:
        1. Использование marketUnit='quoteCoin' 
        2. qty указывается в USDT (валюта котировки)
        3. Асинхронное выполнение через QTimer
        4. Полная обработка ошибок
        """
        try:
            self.add_log_message("🔄 Начинаю покупку ETHUSDT на 10 USDT...")
            
            # Отключаем кнопку на время выполнения
            self.buy_lowest_btn.setEnabled(False)
            self.buy_lowest_btn.setText("⏳ Покупка...")
            
            # Используем QTimer для неблокирующего выполнения
            def execute_buy_async():
                try:
                    symbol = "ETHUSDT"
                    quote_order_qty = "10"  # Покупаем на 10 USDT
                    
                    self.add_log_message(f"📊 Покупаем {symbol} на {quote_order_qty} USDT")
                    
                    # Проверяем наличие торгового воркера
                    if not hasattr(self, 'trading_worker') or self.trading_worker is None:
                        self.add_log_message("❌ Торговый воркер не инициализирован")
                        return
                    
                    # Проверяем наличие API клиента
                    if not hasattr(self.trading_worker, 'bybit_client') or self.trading_worker.bybit_client is None:
                        self.add_log_message("❌ API клиент не инициализирован")
                        return
                    
                    # 🔑 КЛЮЧЕВАЯ ЧАСТЬ: Выполняем покупку с правильными параметрами
                    try:
                        self.add_log_message(f"💰 Размещаю ордер на покупку {symbol} на {quote_order_qty} USDT...")
                        
                        # ✅ РАБОЧИЕ ПАРАМЕТРЫ:
                        order_result = self.trading_worker.bybit_client.place_order(
                            category='spot',                    # Спотовая торговля
                            symbol=symbol,                      # ETHUSDT
                            side='Buy',                         # Покупка
                            order_type='Market',                # Рыночный ордер
                            qty=quote_order_qty,                # Количество в USDT (10)
                            marketUnit='quoteCoin'              # 🔑 КЛЮЧЕВОЙ ПАРАМЕТР!
                        )
                        
                        self.add_log_message(f"📋 Результат API: {order_result}")
                        
                        if order_result:
                            self.add_log_message(f"✅ Успешно размещен ордер на покупку {symbol} на {quote_order_qty} USDT")
                            
                            # Расчет примерного количества ETH
                            try:
                                tickers = self.trading_worker.bybit_client.get_tickers(category="spot")
                                eth_price = 0
                                if tickers and isinstance(tickers, list):
                                    for ticker in tickers:
                                        if ticker.get('symbol') == symbol:
                                            eth_price = float(ticker.get('lastPrice', 0))
                                            break
                                if eth_price > 0:
                                    estimated_qty = float(quote_order_qty) / eth_price
                                    self.add_log_message(f"📊 Примерное количество: ~{estimated_qty:.6f} ETH")
                            except Exception as price_error:
                                self.add_log_message(f"⚠️ Не удалось получить цену: {price_error}")
                        else:
                            self.add_log_message(f"❌ Не удалось разместить ордер на покупку {symbol}")
                            
                    except Exception as api_error:
                        self.add_log_message(f"❌ Ошибка API при покупке {symbol}: {str(api_error)}")
                        self.logger.error(f"API Error: {api_error}")
                    
                except Exception as e:
                    self.add_log_message(f"❌ Ошибка при покупке: {str(e)}")
                    self.logger.error(f"Ошибка в buy_lowest_ticker: {e}")
                finally:
                    # Возвращаем кнопку в исходное состояние
                    self.buy_lowest_btn.setEnabled(True)
                    self.buy_lowest_btn.setText("💰 Купить ETH на 10$")
            
            # Выполняем асинхронно через QTimer
            QTimer.singleShot(100, execute_buy_async)
            
        except Exception as e:
            self.add_log_message(f"❌ Критическая ошибка при покупке: {str(e)}")
            self.logger.error(f"Критическая ошибка в buy_lowest_ticker: {e}")
            # Возвращаем кнопку в исходное состояние при ошибке
            self.buy_lowest_btn.setEnabled(True)
            self.buy_lowest_btn.setText("💰 Купить ETH на 10$")


# 🔧 АЛЬТЕРНАТИВНЫЕ ВАРИАНТЫ ИСПОЛЬЗОВАНИЯ

def buy_btc_for_usdt(api_client, amount_usdt: str = "20"):
    """
    Покупка BTC на фиксированную сумму в USDT
    """
    return api_client.place_order(
        category='spot',
        symbol='BTCUSDT',
        side='Buy',
        order_type='Market',
        qty=amount_usdt,
        marketUnit='quoteCoin'  # qty в USDT
    )

def buy_eth_fixed_quantity(api_client, eth_quantity: str = "0.01"):
    """
    Покупка фиксированного количества ETH
    """
    return api_client.place_order(
        category='spot',
        symbol='ETHUSDT',
        side='Buy',
        order_type='Market',
        qty=eth_quantity,
        marketUnit='baseCoin'  # qty в ETH
    )

def sell_eth_for_usdt(api_client, amount_usdt: str = "10"):
    """
    Продажа ETH на фиксированную сумму в USDT
    """
    return api_client.place_order(
        category='spot',
        symbol='ETHUSDT',
        side='Sell',
        order_type='Market',
        qty=amount_usdt,
        marketUnit='quoteCoin'  # qty в USDT
    )


# 📊 ПРИМЕРЫ УСПЕШНЫХ ЛОГОВ

"""
УСПЕШНЫЙ РЕЗУЛЬТАТ:
🔄 Начинаю покупку ETHUSDT на 10 USDT...
📊 Покупаем ETHUSDT на 10 USDT
💰 Размещаю ордер на покупку ETHUSDT на 10 USDT...
📋 Результат API: {'retCode': 0, 'retMsg': 'OK', 'result': {...}}
✅ Успешно размещен ордер на покупку ETHUSDT на 10 USDT
📊 Примерное количество: ~0.002500 ETH
"""


# 🚨 ВАЖНЫЕ ЗАМЕЧАНИЯ

"""
КРИТИЧЕСКИ ВАЖНЫЕ МОМЕНТЫ:

1. marketUnit='quoteCoin' - ОБЯЗАТЕЛЬНЫЙ параметр для покупки на сумму
2. qty должно быть строкой, не числом
3. Минимальная сумма для ETHUSDT: ~10 USDT
4. Используйте только Market ордера для гарантированного исполнения
5. Всегда проверяйте результат API перед логированием успеха

ПАРАМЕТРЫ marketUnit:
- 'quoteCoin' - qty в валюте котировки (USDT для ETHUSDT)
- 'baseCoin' - qty в базовой валюте (ETH для ETHUSDT)
"""


if __name__ == "__main__":
    print("✅ Рабочее решение для покупки ETH на Bybit загружено!")
    print("📖 Основной метод: buy_eth_fixed_amount()")
    print("🔑 Ключевой параметр: marketUnit='quoteCoin'")