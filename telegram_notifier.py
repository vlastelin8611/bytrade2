"""
Telegram уведомления для торгового бота
"""
import asyncio
import logging
import threading
import time
from datetime import datetime
from queue import Queue
from typing import Dict, Callable, Optional, Any

try:
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
    DEFAULT_TYPE = ContextTypes.DEFAULT_TYPE
except ImportError:
    TELEGRAM_AVAILABLE = False
    Bot = None
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    Update = None
    Application = None
    CallbackQueryHandler = None
    CommandHandler = None
    ContextTypes = None
    DEFAULT_TYPE = Any


class TelegramNotifier:
    """Класс для отправки Telegram уведомлений"""
    
    def __init__(self, token: str, chat_id: str):
        if not TELEGRAM_AVAILABLE:
            raise ImportError("python-telegram-bot не установлен")
        
        self.token = token
        self.chat_id = chat_id
        self.bot = Bot(token=token)
        self.application = None
        self.callbacks: Dict[str, Callable] = {}
        self.message_queue = Queue()
        self.running = False
        self.thread = None
        self.polling_thread = None
        
        # Статистика
        self.messages_sent = 0
        self.errors_count = 0
        
        # Логирование
        self.logger = logging.getLogger(__name__)
        
        # Запускаем обработчик очереди сообщений
        self._start_message_processor()
    
    def set_callback(self, callback_name: str, callback_func: Callable):
        """Регистрация callback функции"""
        self.logger.info(f"🔍 DEBUG: Регистрируем callback '{callback_name}' -> {callback_func}")
        self.callbacks[callback_name] = callback_func
    
    def start_polling(self):
        """Запуск polling для обработки callback'ов"""
        if not TELEGRAM_AVAILABLE:
            self.logger.error("Telegram библиотека недоступна")
            return
        
        try:
            self.logger.info("🔍 DEBUG: Запускаем Telegram polling...")
            
            # Создаем приложение
            self.application = Application.builder().token(self.token).build()
            
            # Регистрируем обработчики
            self.application.add_handler(CallbackQueryHandler(self._handle_callback))
            self.application.add_handler(CommandHandler("balance", self._handle_balance_command))
            self.application.add_handler(CommandHandler("stop_trading", self._handle_stop_command))
            
            # Запускаем polling в отдельном потоке
            self.polling_thread = threading.Thread(target=self._run_polling, daemon=True)
            self.polling_thread.start()
            
            self.logger.info("✅ Telegram polling запущен")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка запуска polling: {e}")
            import traceback
            self.logger.error(f"🔍 DEBUG: Полная ошибка: {traceback.format_exc()}")
    
    def _run_polling(self):
        """Запуск polling в отдельном потоке"""
        try:
            # Создаем новый event loop для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Запускаем polling
            self.application.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка в polling потоке: {e}")
    
    async def _handle_callback(self, update: Update, context: DEFAULT_TYPE):
        """Обработка callback запросов от кнопок"""
        try:
            callback_data = update.callback_query.data
            self.logger.info(f"🔍 DEBUG: Получен callback: '{callback_data}'")
            
            # Подтверждаем получение callback
            await update.callback_query.answer()
            
            # Ищем соответствующую функцию
            if callback_data in self.callbacks:
                self.logger.info(f"🔍 DEBUG: Вызываем callback функцию для '{callback_data}'")
                callback_func = self.callbacks[callback_data]
                
                # Вызываем функцию и получаем результат
                try:
                    result = callback_func()
                    if result:
                        # Отправляем результат как новое сообщение
                        await update.callback_query.message.reply_text(result)
                        self.logger.info(f"✅ Callback '{callback_data}' выполнен успешно")
                    else:
                        self.logger.warning(f"⚠️ Callback '{callback_data}' не вернул результат")
                except Exception as e:
                    error_msg = f"Ошибка выполнения команды: {e}"
                    await update.callback_query.message.reply_text(error_msg)
                    self.logger.error(f"❌ Ошибка в callback '{callback_data}': {e}")
            else:
                self.logger.warning(f"⚠️ Неизвестный callback: '{callback_data}'")
                await update.callback_query.message.reply_text("Неизвестная команда")
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка обработки callback: {e}")
            import traceback
            self.logger.error(f"🔍 DEBUG: Полная ошибка: {traceback.format_exc()}")
    
    async def _handle_balance_command(self, update: Update, context: DEFAULT_TYPE):
        """Обработка команды /balance"""
        try:
            if 'get_balance' in self.callbacks:
                result = self.callbacks['get_balance']()
                await update.message.reply_text(result or "Баланс недоступен")
            else:
                await update.message.reply_text("Команда недоступна")
        except Exception as e:
            await update.message.reply_text(f"Ошибка получения баланса: {e}")
    
    async def _handle_stop_command(self, update: Update, context: DEFAULT_TYPE):
        """Обработка команды /stop_trading"""
        try:
            if 'stop_trading' in self.callbacks:
                result = self.callbacks['stop_trading']()
                await update.message.reply_text(result or "Торговля остановлена")
            else:
                await update.message.reply_text("Команда недоступна")
        except Exception as e:
            await update.message.reply_text(f"Ошибка остановки торговли: {e}")
    
    def _start_message_processor(self):
        """Запуск обработчика очереди сообщений"""
        self.running = True
        self.thread = threading.Thread(target=self._process_messages, daemon=True)
        self.thread.start()
    
    def _process_messages(self):
        """Обработка очереди сообщений"""
        while self.running:
            try:
                if not self.message_queue.empty():
                    message_data = self.message_queue.get(timeout=1)
                    self._send_message_sync(message_data)
                else:
                    time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Ошибка обработки сообщения: {e}")
                time.sleep(1)
    
    def _send_message_sync(self, message_data: Dict[str, Any]):
        """Синхронная отправка сообщения"""
        try:
            # Создаем новый event loop для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Отправляем сообщение
            loop.run_until_complete(self._send_message_async(message_data))
            
            self.messages_sent += 1
            
        except Exception as e:
            self.errors_count += 1
            self.logger.error(f"Ошибка отправки сообщения: {e}")
        finally:
            loop.close()
    
    async def _send_message_async(self, message_data: Dict[str, Any]):
        """Асинхронная отправка сообщения"""
        text = message_data.get('text', '')
        reply_markup = message_data.get('reply_markup')
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    def send_message(self, text: str, reply_markup=None):
        """Добавление сообщения в очередь"""
        message_data = {
            'text': text,
            'reply_markup': reply_markup
        }
        self.message_queue.put(message_data)
    
    def send_test_message(self):
        """Отправка тестового сообщения"""
        # Создаем кнопки с правильными callback_data
        inline_keyboard = [
            [
                InlineKeyboardButton(text="💰 Баланс", callback_data="get_balance"),
                InlineKeyboardButton(text="🛑 Остановить торговлю", callback_data="stop_trading")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard)
        
        test_text = f"🧪 Тестовое уведомление\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        self.send_message(test_text, reply_markup)
    
    def notify_trade_executed(self, trade_info: Dict[str, Any]):
        """Уведомление о выполненной сделке"""
        symbol = trade_info.get('symbol', 'Unknown')
        side = trade_info.get('side', 'Unknown')
        amount = trade_info.get('amount', 0)
        price = trade_info.get('price', 0)
        confidence = trade_info.get('confidence', 0)
        
        # Создаем кнопки с правильными callback_data
        inline_keyboard = [
            [
                InlineKeyboardButton(text="💰 Баланс", callback_data="get_balance"),
                InlineKeyboardButton(text="🛑 Остановить торговлю", callback_data="stop_trading")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard)
        
        text = f"""
🎯 <b>Сделка выполнена</b>
📊 Пара: {symbol}
📈 Тип: {side}
💰 Сумма: ${amount:.2f}
💲 Цена: ${price:.6f}
🎯 Уверенность: {confidence:.1f}%
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
        
        self.send_message(text, reply_markup)
    
    def notify_balance_change(self, balance_info: Dict[str, Any]):
        """Уведомление об изменении баланса"""
        text = f"""
💰 <b>Изменение баланса</b>
💵 USDT: ${balance_info.get('usdt', 0):.2f}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
        
        self.send_message(text)
    
    def notify_trading_status(self, status: str, message: str = ""):
        """Уведомление о статусе торговли"""
        text = f"""
🤖 <b>Статус торговли</b>
📊 {status}
{message}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
        
        self.send_message(text)
    
    def notify_error(self, error_message: str):
        """Уведомление об ошибке"""
        text = f"""
❌ <b>Ошибка</b>
🔍 {error_message}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
        
        self.send_message(text)
    
    def get_stats(self) -> Dict[str, int]:
        """Получение статистики"""
        return {
            'messages_sent': self.messages_sent,
            'errors_count': self.errors_count
        }
    
    def stop(self):
        """Остановка уведомлений"""
        self.running = False
        if self.application:
            try:
                self.application.stop()
            except:
                pass
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=2)