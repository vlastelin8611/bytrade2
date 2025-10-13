#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест Telegram бота - проверка подключения и отправка тестового сообщения
"""

import json
import asyncio
import sys
from pathlib import Path

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    print("❌ Библиотека python-telegram-bot не установлена")
    print("Установите: pip install python-telegram-bot")
    sys.exit(1)

def load_telegram_settings():
    """Загрузка настроек Telegram"""
    settings_file = Path(__file__).parent / 'telegram_settings.json'
    
    if not settings_file.exists():
        print(f"❌ Файл настроек не найден: {settings_file}")
        return None
    
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        print(f"✅ Настройки загружены из {settings_file}")
        print(f"   Token: {settings.get('token', 'НЕ НАЙДЕН')[:20]}...")
        print(f"   Chat ID: {settings.get('chat_id', 'НЕ НАЙДЕН')}")
        print(f"   Enabled: {settings.get('enabled', False)}")
        
        return settings
    except Exception as e:
        print(f"❌ Ошибка загрузки настроек: {e}")
        return None

async def test_telegram_bot():
    """Тест Telegram бота"""
    print("🚀 Начинаем тест Telegram бота...")
    
    # Загрузка настроек
    settings = load_telegram_settings()
    if not settings:
        return False
    
    if not settings.get('enabled', False):
        print("❌ Telegram уведомления отключены в настройках")
        return False
    
    token = settings.get('token')
    chat_id = settings.get('chat_id')
    
    if not token or not chat_id:
        print("❌ Не указан токен или chat_id")
        return False
    
    try:
        # Создание бота
        print("🔄 Создание Telegram бота...")
        bot = Bot(token=token)
        
        # Получение информации о боте
        print("🔄 Получение информации о боте...")
        bot_info = await bot.get_me()
        print(f"✅ Бот найден: @{bot_info.username} ({bot_info.first_name})")
        
        # Отправка тестового сообщения
        print("🔄 Отправка тестового сообщения...")
        test_message = "🧪 Тестовое сообщение от торгового бота\n\n" \
                      "Если вы видите это сообщение, значит Telegram уведомления работают корректно! ✅"
        
        message = await bot.send_message(
            chat_id=chat_id,
            text=test_message,
            parse_mode='HTML'
        )
        
        print(f"✅ Тестовое сообщение отправлено! Message ID: {message.message_id}")
        
        # Тест с inline кнопками
        print("🔄 Отправка сообщения с inline кнопками...")
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        keyboard = [
            [InlineKeyboardButton("✅ Тест прошел", callback_data="test_success")],
            [InlineKeyboardButton("❌ Есть проблемы", callback_data="test_failed")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        button_message = await bot.send_message(
            chat_id=chat_id,
            text="🎛️ Тест inline кнопок:\nНажмите любую кнопку для проверки",
            reply_markup=reply_markup
        )
        
        print(f"✅ Сообщение с кнопками отправлено! Message ID: {button_message.message_id}")
        
        return True
        
    except TelegramError as e:
        print(f"❌ Ошибка Telegram API: {e}")
        if "Unauthorized" in str(e):
            print("   Возможные причины:")
            print("   - Неверный токен бота")
            print("   - Бот был удален или заблокирован")
        elif "Bad Request" in str(e):
            print("   Возможные причины:")
            print("   - Неверный chat_id")
            print("   - Бот не может отправить сообщение в этот чат")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

async def main():
    """Главная функция"""
    print("=" * 50)
    print("🤖 ТЕСТ TELEGRAM БОТА")
    print("=" * 50)
    
    success = await test_telegram_bot()
    
    print("=" * 50)
    if success:
        print("✅ ТЕСТ ПРОЙДЕН УСПЕШНО!")
        print("Telegram уведомления должны работать корректно.")
    else:
        print("❌ ТЕСТ НЕ ПРОЙДЕН!")
        print("Проверьте настройки и исправьте ошибки.")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())