#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Notifier - Класс для отправки уведомлений в Telegram
Поддерживает отправку сообщений с inline-кнопками и обработку callback'ов
"""

import asyncio
import threading
import queue
import time
from datetime import datetime
import logging
from typing import Optional, List, Dict, Any, Callable

try:
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ python-telegram-bot не установлен. Установите: pip install python-telegram-bot")


class TelegramNotifier:
    """Класс для отправки уведомлений в Telegram с оптимизированной скоростью"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = False
        self.bot = None
        self.application = None
        
        # Очередь для быстрой отправки уведомлений
        self.notification_queue = queue.Queue()
        self.worker_thread = None
        self.worker_running = False
        
        # Event loop для асинхронных операций
        self.loop = None
        self.loop_thread = None
        
        # Статистика уведомлений
        self.stats = {
            'sent': 0,
            'failed': 0,
            'last_sent': None,
            'last_error': None,
            'queue_size': 0,
            'avg_send_time': 0
        }
        
        # Callback функции для обработки команд
        self.callbacks = {}
        
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        
        # Инициализация бота если есть токен
        if bot_token and chat_id:
            self.initialize_bot()
    
    def initialize_bot(self):
        """Инициализация Telegram бота с фоновым worker'ом"""
        try:
            if not TELEGRAM_AVAILABLE:
                self.logger.error("python-telegram-bot не установлен")
                return False
            
            self.bot = Bot(token=self.bot_token)
            
            # Создание приложения для обработки callback'ов
            self.application = Application.builder().token(self.bot_token).build()
            
            # Добавление обработчиков
            self.application.add_handler(CallbackQueryHandler(self._handle_callback))
            self.application.add_handler(CommandHandler("start", self._handle_start))
            self.application.add_handler(CommandHandler("balance", self._handle_balance_command))
            self.application.add_handler(CommandHandler("stop_trading", self._handle_stop_trading_command))
            
            # Запуск фонового worker'а для обработки очереди
            self._start_worker_thread()
            
            self.enabled = True
            self.logger.info("✅ Telegram бот инициализирован с быстрой отправкой")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации Telegram бота: {e}")
            self.stats['last_error'] = str(e)
            return False
    
    def _start_worker_thread(self):
        """Запуск фонового потока для обработки очереди уведомлений"""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        self.worker_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        # Запуск event loop в отдельном потоке
        self.loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.loop_thread.start()
        
        self.logger.info("✅ Фоновый worker для Telegram уведомлений запущен")
    
    def _run_event_loop(self):
        """Запуск event loop в отдельном потоке"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def _worker_loop(self):
        """Основной цикл worker'а для обработки очереди"""
        while self.worker_running:
            try:
                # Получаем задачу из очереди с таймаутом
                task = self.notification_queue.get(timeout=1.0)
                
                if task is None:  # Сигнал остановки
                    break
                
                start_time = time.time()
                
                # Выполняем отправку
                if self.loop and not self.loop.is_closed():
                    future = asyncio.run_coroutine_threadsafe(
                        self.send_message(task['text'], task.get('buttons')), 
                        self.loop
                    )
                    success = future.result(timeout=10)  # 10 секунд таймаут
                    
                    # Обновляем статистику времени отправки
                    send_time = time.time() - start_time
                    if self.stats['avg_send_time'] == 0:
                        self.stats['avg_send_time'] = send_time
                    else:
                        self.stats['avg_send_time'] = (self.stats['avg_send_time'] + send_time) / 2
                
                self.notification_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"❌ Ошибка в worker'е: {e}")
                self.stats['failed'] += 1
                self.stats['last_error'] = str(e)
    
    def stop_worker(self):
        """Остановка фонового worker'а"""
        self.worker_running = False
        if self.notification_queue:
            self.notification_queue.put(None)  # Сигнал остановки
        
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)
    
    def set_credentials(self, bot_token: str, chat_id: str):
        """Установка учетных данных бота"""
        self.bot_token = bot_token
        self.chat_id = chat_id
        return self.initialize_bot()
    
    def set_callback(self, command: str, callback: Callable):
        """Установка callback функции для команды"""
        self.callbacks[command] = callback
    
    async def send_message(self, text: str, inline_buttons: list = None) -> bool:
        """Отправка сообщения в Telegram"""
        if not self.enabled or not self.bot or not self.chat_id:
            return False
        
        try:
            # Создание inline клавиатуры если есть кнопки
            reply_markup = None
            if inline_buttons:
                keyboard = []
                for row in inline_buttons:
                    button_row = []
                    for button in row:
                        button_row.append(
                            InlineKeyboardButton(
                                text=button['text'],
                                callback_data=button['callback_data']
                            )
                        )
                    keyboard.append(button_row)
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправка сообщения
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            # Обновление статистики
            self.stats['sent'] += 1
            self.stats['last_sent'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.logger.info(f"✅ Сообщение отправлено в Telegram: {text[:50]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки сообщения в Telegram: {e}")
            self.stats['failed'] += 1
            self.stats['last_error'] = str(e)
            return False
    
    def send_message_sync(self, text: str, buttons=None):
        """Синхронная отправка сообщения (устаревший метод)"""
        self.logger.warning("⚠️ Используется устаревший синхронный метод отправки")
        return self.send_message_instant(text, buttons)
    
    def send_message_instant(self, text: str, buttons=None):
        """Мгновенная отправка сообщения через очередь"""
        if not self.enabled or not self.bot_token or not self.chat_id:
            self.logger.warning("⚠️ Telegram не настроен или отключен")
            return False
        
        try:
            # Добавляем задачу в очередь для мгновенной обработки
            task = {
                'text': text,
                'buttons': buttons,
                'timestamp': time.time()
            }
            
            self.notification_queue.put(task, block=False)
            self.stats['queue_size'] = self.notification_queue.qsize()
            
            self.logger.info(f"📤 Сообщение добавлено в очередь (размер: {self.stats['queue_size']})")
            return True
            
        except queue.Full:
            self.logger.error("❌ Очередь уведомлений переполнена")
            self.stats['failed'] += 1
            return False
        except Exception as e:
            self.logger.error(f"❌ Ошибка добавления в очередь: {e}")
            self.stats['failed'] += 1
            self.stats['last_error'] = str(e)
            return False
    
    async def _handle_callback(self, update, context):
        """Обработка callback'ов от inline кнопок"""
        if not TELEGRAM_AVAILABLE:
            return
            
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        self.logger.info(f"Получен callback: {callback_data}")
        
        # Выполнение соответствующего callback'а
        if callback_data in self.callbacks:
            try:
                result = self.callbacks[callback_data]()
                if result:
                    await query.edit_message_text(text=result)
            except Exception as e:
                self.logger.error(f"Ошибка выполнения callback {callback_data}: {e}")
                await query.edit_message_text(text=f"❌ Ошибка: {str(e)}")
    
    async def _handle_start(self, update, context):
        """Обработка команды /start"""
        if not TELEGRAM_AVAILABLE:
            return
            
        await update.message.reply_text(
            "🤖 Привет! Я бот для уведомлений о торговле.\n\n"
            "Доступные команды:\n"
            "/balance - показать баланс\n"
            "/stop_trading - остановить торговлю"
        )
    
    async def _handle_balance_command(self, update, context):
        """Обработка команды /balance"""
        if not TELEGRAM_AVAILABLE:
            return
            
        if 'get_balance' in self.callbacks:
            try:
                balance_info = self.callbacks['get_balance']()
                await update.message.reply_text(balance_info, parse_mode='HTML')
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка получения баланса: {e}")
        else:
            await update.message.reply_text("❌ Функция получения баланса не настроена")
    
    async def _handle_stop_trading_command(self, update, context):
        """Обработка команды /stop_trading"""
        if not TELEGRAM_AVAILABLE:
            return
            
        if 'stop_trading' in self.callbacks:
            try:
                result = self.callbacks['stop_trading']()
                await update.message.reply_text(result)
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка остановки торговли: {e}")
        else:
            await update.message.reply_text("❌ Функция остановки торговли не настроена")
    
    def start_polling(self):
        """Запуск polling для обработки команд (в отдельном потоке)"""
        if not self.application:
            return False
        
        def run_polling():
            try:
                self.application.run_polling()
            except Exception as e:
                self.logger.error(f"Ошибка polling: {e}")
        
        polling_thread = threading.Thread(target=run_polling, daemon=True)
        polling_thread.start()
        return True
    
    def __del__(self):
        """Деструктор - корректное завершение работы"""
        try:
            self.stop_worker()
        except:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики работы"""
        self.stats['queue_size'] = self.notification_queue.qsize() if self.notification_queue else 0
        return self.stats.copy()
    
    # Методы для отправки специфических уведомлений
    
    def notify_trade_executed(self, trade_type: str, symbol: str, quantity: float, price: float, total_usd: float):
        """Уведомление о выполненной сделке"""
        emoji = "🟢" if trade_type.upper() == "BUY" else "🔴"
        action = "Покупка" if trade_type.upper() == "BUY" else "Продажа"
        
        text = (
            f"{emoji} <b>{action} выполнена!</b>\n\n"
            f"💰 Символ: <code>{symbol}</code>\n"
            f"📊 Количество: <code>{quantity:.8f}</code>\n"
            f"💵 Цена: <code>${price:.6f}</code>\n"
            f"💸 Сумма: <code>${total_usd:.2f}</code>\n"
            f"🕐 Время: <code>{datetime.now().strftime('%H:%M:%S')}</code>"
        )
        
        # Inline кнопки
        buttons = [
            [
                {"text": "💰 Баланс", "callback_data": "get_balance"},
                {"text": "⏹️ Стоп", "callback_data": "stop_trading"}
            ]
        ]
        
        return self.send_message_instant(text, buttons)
    
    def notify_balance_change(self, old_balance: float, new_balance: float, currency: str = "USDT"):
        """Уведомление об изменении баланса"""
        change = new_balance - old_balance
        emoji = "📈" if change > 0 else "📉"
        sign = "+" if change > 0 else ""
        
        text = (
            f"{emoji} <b>Изменение баланса</b>\n\n"
            f"💰 Валюта: <code>{currency}</code>\n"
            f"📊 Было: <code>{old_balance:.2f}</code>\n"
            f"📊 Стало: <code>{new_balance:.2f}</code>\n"
            f"📈 Изменение: <code>{sign}{change:.2f}</code>\n"
            f"🕐 Время: <code>{datetime.now().strftime('%H:%M:%S')}</code>"
        )
        
        buttons = [
            [
                {"text": "💰 Баланс", "callback_data": "get_balance"},
                {"text": "⏹️ Остановить торговлю", "callback_data": "stop_trading"}
            ]
        ]
        
        return self.send_message_instant(text, buttons)
    
    def notify_trading_status(self, is_started: bool, message: str = ""):
        """Уведомление о статусе торговли"""
        emoji = "🟢" if is_started else "🔴"
        status_text = "запущена" if is_started else "остановлена"
        
        text = (
            f"{emoji} <b>Торговля {status_text}</b>\n\n"
            f"📝 {message if message else ('Автоматическая торговля активна' if is_started else 'Автоматическая торговля приостановлена')}\n"
            f"🕐 Время: <code>{datetime.now().strftime('%H:%M:%S')}</code>"
        )
        
        if is_started:
            buttons = [
                [{"text": "⏹️ Остановить торговлю", "callback_data": "stop_trading"}]
            ]
        else:
            buttons = [
                [{"text": "💰 Баланс", "callback_data": "get_balance"}]
            ]
        
        return self.send_message_instant(text, buttons)
    
    def notify_error(self, error_message: str, error_type: str = "Ошибка"):
        """Уведомление об ошибке"""
        text = (
            f"❌ <b>{error_type}</b>\n\n"
            f"📝 Описание: <code>{error_message}</code>\n"
            f"🕐 Время: <code>{datetime.now().strftime('%H:%M:%S')}</code>"
        )
        
        buttons = [
            [
                {"text": "💰 Баланс", "callback_data": "get_balance"},
                {"text": "⏹️ Остановить торговлю", "callback_data": "stop_trading"}
            ]
        ]
        
        return self.send_message_instant(text, buttons)


    def send_test_message(self):
        """Отправка тестового сообщения"""
        test_text = "🧪 Тестовое уведомление\n\n"
        test_text += f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n"
        test_text += f"📊 Статистика:\n"
        test_text += f"  • Отправлено: {self.stats['sent']}\n"
        test_text += f"  • Ошибок: {self.stats['failed']}\n"
        test_text += f"  • Размер очереди: {self.stats['queue_size']}\n"
        test_text += f"  • Среднее время: {self.stats['avg_send_time']:.3f}с"
        
        buttons = [
            [
                {"text": "💰 Баланс", "callback_data": "get_balance"},
                {"text": "⏹️ Остановить торговлю", "callback_data": "stop_trading"}
            ]
        ]
        
        return self.send_message_instant(test_text, buttons)


# Глобальный экземпляр для использования в других модулях
telegram_notifier = TelegramNotifier()