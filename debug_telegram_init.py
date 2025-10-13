#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отладочный скрипт для проверки инициализации Telegram из настроек
"""

import json
import os
import sys

def test_telegram_init():
    """Тестирование инициализации Telegram из настроек"""
    print("🔍 Проверка инициализации Telegram из настроек...")
    
    # Проверяем файл настроек
    settings_file = 'telegram_settings.json'
    if not os.path.exists(settings_file):
        print(f"❌ Файл настроек {settings_file} не найден")
        return False
    
    try:
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        print(f"✅ Настройки загружены: {settings}")
    except Exception as e:
        print(f"❌ Ошибка загрузки настроек: {e}")
        return False
    
    # Проверяем наличие необходимых полей
    required_fields = ['token', 'chat_id', 'enabled']
    for field in required_fields:
        if field not in settings:
            print(f"❌ Отсутствует поле {field} в настройках")
            return False
        print(f"✅ Поле {field}: {settings[field]}")
    
    # Проверяем, что уведомления включены
    if not settings.get('enabled'):
        print("⚠️ Telegram уведомления отключены в настройках")
        return False
    
    # Проверяем, что токен и chat_id не пустые
    if not settings.get('token') or not settings.get('chat_id'):
        print("❌ Токен или chat_id пустые")
        return False
    
    # Пытаемся инициализировать TelegramNotifier
    try:
        from telegram_notifier import TelegramNotifier
        print("✅ Модуль telegram_notifier импортирован")
        
        notifier = TelegramNotifier(settings['token'], settings['chat_id'])
        print("✅ TelegramNotifier создан")
        
        # Проверяем инициализацию бота
        if notifier.initialize_bot():
            print("✅ Telegram бот инициализирован")
            
            # Отправляем тестовое сообщение
            print("📤 Отправка тестового сообщения...")
            result = notifier.send_test_message()
            if result:
                print("✅ Тестовое сообщение отправлено успешно!")
                return True
            else:
                print("❌ Не удалось отправить тестовое сообщение")
                return False
        else:
            print("❌ Не удалось инициализировать Telegram бота")
            return False
            
    except ImportError as e:
        print(f"❌ Ошибка импорта telegram_notifier: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка инициализации TelegramNotifier: {e}")
        return False

if __name__ == "__main__":
    success = test_telegram_init()
    if success:
        print("\n🎉 Все проверки пройдены! Telegram должен работать.")
    else:
        print("\n❌ Обнаружены проблемы с инициализацией Telegram.")
    
    input("\nНажмите Enter для выхода...")