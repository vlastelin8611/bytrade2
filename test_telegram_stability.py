#!/usr/bin/env python3
"""
Тест стабильности Telegram уведомлений
Проверяет работу retry механизма и обработки ошибок
"""

import time
import logging
from telegram_notifier import TelegramNotifier

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_telegram_stability():
    """Тестирование стабильности Telegram уведомлений"""
    print("🧪 Тестирование стабильности Telegram уведомлений...")
    
    # Создание экземпляра уведомлений
    notifier = TelegramNotifier()
    
    # Загрузка настроек из файла
    try:
        with open('keys', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            token = None
            chat_id = None
            
            for line in lines:
                if 'TELEGRAM_BOT_TOKEN' in line:
                    token = line.split('=')[1].strip()
                elif 'TELEGRAM_CHAT_ID' in line:
                    chat_id = line.split('=')[1].strip()
        
        if not token or not chat_id:
            print("❌ Не найдены настройки Telegram в файле keys")
            return False
            
        notifier.set_credentials(token, chat_id)
        print(f"✅ Настройки загружены: токен={token[:10]}..., chat_id={chat_id}")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки настроек: {e}")
        return False
    
    # Инициализация бота
    if not notifier.initialize_bot():
        print("❌ Не удалось инициализировать бота")
        return False
    
    print("✅ Бот инициализирован успешно")
    
    # Тест 1: Отправка простого сообщения
    print("\n📤 Тест 1: Отправка простого сообщения...")
    success = notifier.send_message_instant("🧪 Тест стабильности Telegram уведомлений")
    print(f"Результат: {'✅ Успешно' if success else '❌ Ошибка'}")
    
    # Ждем отправки
    time.sleep(3)
    
    # Тест 2: Отправка множественных сообщений
    print("\n📤 Тест 2: Отправка множественных сообщений...")
    for i in range(5):
        success = notifier.send_message_instant(f"📨 Тестовое сообщение #{i+1}")
        print(f"Сообщение {i+1}: {'✅' if success else '❌'}")
        time.sleep(0.5)
    
    # Ждем обработки очереди
    time.sleep(10)
    
    # Тест 3: Сообщение с кнопками
    print("\n📤 Тест 3: Сообщение с кнопками...")
    buttons = [
        [{"text": "✅ Тест 1", "callback_data": "test_1"}],
        [{"text": "🔄 Тест 2", "callback_data": "test_2"}]
    ]
    success = notifier.send_message_instant("🎛️ Тест кнопок", buttons)
    print(f"Результат: {'✅ Успешно' if success else '❌ Ошибка'}")
    
    # Ждем отправки
    time.sleep(3)
    
    # Проверка статистики
    print("\n📊 Статистика уведомлений:")
    stats = notifier.stats
    print(f"Отправлено: {stats['sent']}")
    print(f"Ошибок: {stats['failed']}")
    print(f"Последняя ошибка: {stats.get('last_error', 'Нет')}")
    print(f"Последняя отправка: {stats.get('last_sent', 'Нет')}")
    print(f"Размер очереди: {stats.get('queue_size', 0)}")
    
    # Тест 4: Стресс-тест очереди
    print("\n🔥 Тест 4: Стресс-тест очереди (20 сообщений)...")
    start_time = time.time()
    
    for i in range(20):
        success = notifier.send_message_instant(f"🔥 Стресс-тест #{i+1}/20")
        if not success:
            print(f"❌ Ошибка в сообщении {i+1}")
    
    # Ждем обработки всех сообщений
    print("⏳ Ожидание обработки всех сообщений...")
    time.sleep(30)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"⏱️ Время выполнения стресс-теста: {total_time:.2f} секунд")
    
    # Финальная статистика
    print("\n📊 Финальная статистика:")
    final_stats = notifier.stats
    print(f"Всего отправлено: {final_stats['sent']}")
    print(f"Всего ошибок: {final_stats['failed']}")
    print(f"Успешность: {(final_stats['sent'] / (final_stats['sent'] + final_stats['failed']) * 100):.1f}%" if (final_stats['sent'] + final_stats['failed']) > 0 else "0%")
    
    # Завершение
    notifier.__del__()
    
    # Оценка результатов
    success_rate = (final_stats['sent'] / (final_stats['sent'] + final_stats['failed']) * 100) if (final_stats['sent'] + final_stats['failed']) > 0 else 0
    
    if success_rate >= 90:
        print("🎉 Тест стабильности ПРОЙДЕН! Система работает стабильно.")
        return True
    elif success_rate >= 70:
        print("⚠️ Тест стабильности частично пройден. Есть проблемы, но система работает.")
        return True
    else:
        print("❌ Тест стабильности НЕ ПРОЙДЕН! Система нестабильна.")
        return False

if __name__ == "__main__":
    test_telegram_stability()