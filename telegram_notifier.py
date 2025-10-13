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
            'avg_send_time': 0.0,
            'total_send_time': 0.0
        }
        
        # Callback функции для обработки команд
        self.callbacks = {}
        
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        
        # Настройки retry
        self.max_retries = 3
        self.retry_delay = 1  # начальная задержка в секундах
        
        # Очередь для повторных попыток
        self.retry_queue = queue.Queue()
        
        # Инициализация бота если есть токен
        if bot_token and chat_id:
            self.initialize_bot()
    
    def initialize_bot(self):
        """Инициализация Telegram бота с фоновым worker'ом"""
        try:
            if not TELEGRAM_AVAILABLE:
                self.logger.error("python-telegram-bot не установлен")
                return False
            
            if not self.bot_token or not self.chat_id:
                self.logger.warning("⚠️ Токен бота или Chat ID не установлены")
                return False
            
            # Создание бота с увеличенными timeout'ами (для версии 22.x)
            from telegram.request import HTTPXRequest
            
            # Создаем кастомный request с timeout'ами
            request = HTTPXRequest(
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30
            )
            
            self.bot = Bot(
                token=self.bot_token,
                request=request
            )
            
            # Создание Application для обработки команд
            self.application = Application.builder().token(self.bot_token).build()
            
            # Добавление обработчиков команд
            self.application.add_handler(CommandHandler("start", self._handle_start))
            self.application.add_handler(CommandHandler("balance", self._handle_balance_command))
            self.application.add_handler(CommandHandler("stop_trading", self._handle_stop_trading_command))
            self.application.add_handler(CallbackQueryHandler(self._handle_callback))
            
            self.enabled = True
            self._start_worker_thread()
            
            self.logger.info("✅ Telegram бот инициализирован с быстрой отправкой")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации Telegram бота: {e}")
            self.enabled = False
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
        """Фоновый worker для обработки очереди сообщений"""
        while self.worker_running:
            try:
                # Обработка основной очереди
                try:
                    task = self.notification_queue.get(timeout=1.0)
                    if task is None:  # Сигнал завершения
                        break
                    
                    start_time = time.time()
                    
                    # Отправка сообщения с retry
                    if self.loop and not self.loop.is_closed():
                        success = asyncio.run_coroutine_threadsafe(
                            self._send_with_retry(task), 
                            self.loop
                        ).result()
                        
                        if success:
                            self.stats['sent'] += 1
                            self.stats['last_sent'] = datetime.now().isoformat()
                            
                            # Обновляем статистику времени отправки
                            send_time = time.time() - start_time
                            if self.stats['avg_send_time'] == 0:
                                self.stats['avg_send_time'] = send_time
                            else:
                                self.stats['avg_send_time'] = (self.stats['avg_send_time'] + send_time) / 2
                        else:
                            self.stats['failed'] += 1
                            
                    self.notification_queue.task_done()
                    
                except queue.Empty:
                    continue
                    
                # Обработка очереди повторных попыток
                try:
                    retry_data = self.retry_queue.get_nowait()
                    if retry_data['attempts'] < self.max_retries:
                        # Увеличиваем задержку экспоненциально
                        delay = self.retry_delay * (2 ** retry_data['attempts'])
                        time.sleep(delay)
                        
                        if self.loop and not self.loop.is_closed():
                            success = asyncio.run_coroutine_threadsafe(
                                self._send_with_retry(retry_data['task']), 
                                self.loop
                            ).result()
                            
                            if success:
                                self.stats['sent'] += 1
                                self.stats['last_sent'] = datetime.now().isoformat()
                            else:
                                retry_data['attempts'] += 1
                                if retry_data['attempts'] < self.max_retries:
                                    self.retry_queue.put(retry_data)
                                else:
                                    self.stats['failed'] += 1
                                    self.logger.error(f"❌ Не удалось отправить сообщение после {self.max_retries} попыток")
                                    
                except queue.Empty:
                    continue
                    
            except Exception as e:
                self.logger.error(f"❌ Ошибка в worker'е: {e}")
                self.stats['failed'] += 1
                self.stats['last_error'] = str(e)
                time.sleep(1)
    
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
    
    async def _send_with_retry(self, task: dict) -> bool:
        """Отправка сообщения с retry механизмом"""
        text = task['text']
        inline_buttons = task.get('buttons')
        
        return await self.send_message(text, inline_buttons)
    
    async def send_message(self, text: str, inline_buttons: list = None, max_retries: int = 3) -> bool:
        """Отправка сообщения в Telegram с retry механизмом"""
        if not self.enabled or not self.bot or not self.chat_id:
            return False
        
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
        
        # Попытки отправки с retry механизмом
        for attempt in range(max_retries):
            try:
                # Отправка сообщения с увеличенным timeout
                await asyncio.wait_for(
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode='HTML',
                        read_timeout=30,
                        write_timeout=30,
                        connect_timeout=30
                    ),
                    timeout=60  # Общий timeout 60 секунд
                )
                
                # Обновление статистики при успехе
                self.stats['sent'] += 1
                self.stats['last_sent'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if attempt > 0:
                    self.logger.info(f"✅ Сообщение отправлено в Telegram с попытки {attempt + 1}: {text[:50]}...")
                else:
                    self.logger.info(f"✅ Сообщение отправлено в Telegram: {text[:50]}...")
                return True
                
            except asyncio.TimeoutError:
                self.logger.warning(f"⚠️ Timeout при отправке в Telegram (попытка {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                continue
                
            except Exception as e:
                error_msg = str(e)
                if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                    self.logger.warning(f"⚠️ Timeout ошибка при отправке в Telegram (попытка {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                    continue
                else:
                    # Не timeout ошибка - не повторяем
                    self.logger.error(f"❌ Ошибка отправки сообщения в Telegram: {e}")
                    self.stats['failed'] += 1
                    self.stats['last_error'] = str(e)
                    return False
        
        # Все попытки исчерпаны
        self.logger.error(f"❌ Не удалось отправить сообщение в Telegram после {max_retries} попыток")
        self.stats['failed'] += 1
        self.stats['last_error'] = f"Timeout после {max_retries} попыток"
        return False
    
    def send_message_sync(self, text: str, buttons=None):
        """Синхронная отправка сообщения (устаревший метод)"""
        self.logger.warning("⚠️ Используется устаревший синхронный метод отправки")
        return self.send_message_instant(text, buttons)
    
    def send_message_instant(self, text: str, buttons=None):
        """Мгновенная отправка сообщения через очередь с retry механизмом"""
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
            
            # Если очередь становится слишком большой, очищаем старые сообщения
            if self.notification_queue.qsize() > 100:
                self.logger.warning("⚠️ Очередь сообщений переполнена, очищаем старые сообщения")
                # Очищаем половину очереди
                temp_queue = queue.Queue()
                for _ in range(self.notification_queue.qsize() // 2):
                    try:
                        temp_queue.put(self.notification_queue.get_nowait())
                    except queue.Empty:
                        break
                
                # Заменяем очередь
                self.notification_queue = temp_queue
                self.notification_queue.put(task, block=False)
            
            self.logger.info(f"📤 Сообщение добавлено в очередь (размер: {self.stats['queue_size']})")
            return True
            
        except queue.Full:
            self.logger.error("❌ Очередь уведомлений переполнена")
            self.stats['failed'] += 1
            
            # Пытаемся добавить в очередь повторных попыток
            try:
                retry_data = {
                    'task': task,
                    'attempts': 0
                }
                self.retry_queue.put(retry_data)
                self.logger.info("📝 Сообщение добавлено в очередь повторных попыток")
            except Exception as retry_error:
                self.logger.error(f"❌ Не удалось добавить в retry очередь: {retry_error}")
            
            return False
        except Exception as e:
            self.logger.error(f"❌ Ошибка добавления в очередь: {e}")
            self.stats['failed'] += 1
            self.stats['last_error'] = str(e)
            
            # Пытаемся добавить в очередь повторных попыток
            try:
                retry_data = {
                    'task': task,
                    'attempts': 0
                }
                self.retry_queue.put(retry_data)
                self.logger.info("📝 Сообщение добавлено в очередь повторных попыток")
            except Exception as retry_error:
                self.logger.error(f"❌ Не удалось добавить в retry очередь: {retry_error}")
            
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