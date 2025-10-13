#!/usr/bin/env python3
"""
Тест скорости Telegram уведомлений
"""

import time
import json
from datetime import datetime
from telegram_notifier import TelegramNotifier

def load_telegram_settings():
    """Загрузка настроек Telegram"""
    try:
        with open('telegram_settings.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка загрузки настроек: {e}")
        return None

def test_notification_speed():
    """Тест скорости отправки уведомлений"""
    print("🧪 Тестирование скорости Telegram уведомлений...")
    
    # Загрузка настроек
    settings = load_telegram_settings()
    if not settings:
        return
    
    # Инициализация уведомителя
    notifier = TelegramNotifier()
    notifier.set_credentials(settings['token'], settings['chat_id'])
    
    if not notifier.initialize_bot():
        print("❌ Не удалось инициализировать бота")
        return
    
    print("✅ Бот инициализирован, начинаем тесты...")
    
    # Тест 1: Одиночное уведомление
    print("\n📤 Тест 1: Одиночное уведомление")
    start_time = time.time()
    
    success = notifier.send_message_instant("🚀 Тест скорости #1\n⏱️ Время отправки: " + 
                                          datetime.now().strftime('%H:%M:%S.%f')[:-3])
    
    if success:
        elapsed = (time.time() - start_time) * 1000
        print(f"✅ Сообщение добавлено в очередь за {elapsed:.1f}мс")
    else:
        print("❌ Ошибка отправки")
    
    # Тест 2: Множественные уведомления
    print("\n📤 Тест 2: Серия из 5 уведомлений")
    start_time = time.time()
    
    for i in range(5):
        msg_time = time.time()
        success = notifier.send_message_instant(f"🚀 Тест #{i+1}/5\n⏱️ {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        if success:
            elapsed = (time.time() - msg_time) * 1000
            print(f"  ✅ Сообщение {i+1} добавлено за {elapsed:.1f}мс")
        else:
            print(f"  ❌ Ошибка сообщения {i+1}")
    
    total_elapsed = (time.time() - start_time) * 1000
    print(f"📊 Общее время серии: {total_elapsed:.1f}мс")
    
    # Тест 3: Уведомление с кнопками
    print("\n📤 Тест 3: Уведомление с кнопками")
    start_time = time.time()
    
    buttons = [
        [
            {"text": "✅ Быстро", "callback_data": "fast"},
            {"text": "⚡ Мгновенно", "callback_data": "instant"}
        ]
    ]
    
    success = notifier.send_message_instant(
        "🚀 Тест с кнопками\n⏱️ " + datetime.now().strftime('%H:%M:%S.%f')[:-3] + 
        "\n\n📊 Как быстро пришло это сообщение?", 
        buttons
    )
    
    if success:
        elapsed = (time.time() - start_time) * 1000
        print(f"✅ Сообщение с кнопками добавлено за {elapsed:.1f}мс")
    else:
        print("❌ Ошибка отправки")
    
    # Показать статистику
    time.sleep(2)  # Дать время обработать очередь
    stats = notifier.get_stats()
    print(f"\n📊 Статистика системы:")
    print(f"  • Отправлено: {stats['sent']}")
    print(f"  • Ошибок: {stats['failed']}")
    print(f"  • Размер очереди: {stats['queue_size']}")
    print(f"  • Среднее время отправки: {stats['avg_send_time']:.3f}с")
    
    print("\n🎯 Тестирование завершено!")
    print("📱 Проверьте Telegram - все сообщения должны прийти практически мгновенно")

if __name__ == "__main__":
    test_notification_speed()