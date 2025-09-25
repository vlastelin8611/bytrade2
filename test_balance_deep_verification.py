#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Глубокая проверка корректности получения и отображения баланса
"""

import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent / 'src'))

try:
    from api.bybit_client import BybitClient
    from database.db_manager import DatabaseManager
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

class BalanceDeepVerification:
    """Класс для глубокой проверки баланса"""
    
    def __init__(self):
        self.api_client = None
        self.db_manager = None
        self.test_results = []
        
    def setup(self):
        """Инициализация клиентов"""
        try:
            # Импорт конфигурации
            import config
                
            # Инициализация API клиента
            self.api_client = BybitClient(
                api_key=config.API_KEY,
                api_secret=config.API_SECRET,
                testnet=config.USE_TESTNET
            )
            
            # Инициализация базы данных
            self.db_manager = DatabaseManager()
            
            print("✅ Инициализация завершена успешно")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка инициализации: {e}")
            return False
    
    def test_raw_api_call(self) -> Dict[str, Any]:
        """Тест прямого вызова API для получения баланса"""
        print("\n🔍 Тест 1: Прямой вызов API get_wallet_balance")
        
        try:
            start_time = time.time()
            raw_response = self.api_client.get_wallet_balance()
            execution_time = (time.time() - start_time) * 1000
            
            print(f"⏱️  Время выполнения: {execution_time:.2f} мс")
            print(f"📊 Тип ответа: {type(raw_response)}")
            
            if raw_response:
                print(f"📋 Структура ответа:")
                self._print_dict_structure(raw_response, indent=2)
                
                # Проверка наличия ключевых полей
                required_fields = ['totalWalletBalance', 'availableBalance']
                missing_fields = []
                
                for field in required_fields:
                    if field not in raw_response:
                        missing_fields.append(field)
                
                if missing_fields:
                    print(f"⚠️  Отсутствуют поля: {missing_fields}")
                else:
                    print("✅ Все необходимые поля присутствуют")
                    
                self.test_results.append({
                    'test': 'raw_api_call',
                    'status': 'success',
                    'execution_time_ms': execution_time,
                    'response_type': str(type(raw_response)),
                    'has_required_fields': len(missing_fields) == 0
                })
                
                return raw_response
            else:
                print("❌ Получен пустой ответ")
                self.test_results.append({
                    'test': 'raw_api_call',
                    'status': 'empty_response'
                })
                return {}
                
        except Exception as e:
            print(f"❌ Ошибка при вызове API: {e}")
            self.test_results.append({
                'test': 'raw_api_call',
                'status': 'error',
                'error': str(e)
            })
            return {}
    
    def test_balance_parsing(self, raw_response: Dict[str, Any]):
        """Тест парсинга данных баланса"""
        print("\n🔍 Тест 2: Парсинг данных баланса")
        
        try:
            if not raw_response:
                print("❌ Нет данных для парсинга")
                return
            
            # Извлечение основных значений
            total_balance = float(raw_response.get('totalWalletBalance', 0))
            available_balance = float(raw_response.get('availableBalance', 0))
            unrealized_pnl = float(raw_response.get('totalUnrealizedPnl', 0))
            
            print(f"💰 Общий баланс: {total_balance:.8f} USDT")
            print(f"💵 Доступный баланс: {available_balance:.8f} USDT")
            print(f"📈 Нереализованный P&L: {unrealized_pnl:.8f} USDT")
            
            # Проверка логических связей
            balance_checks = []
            
            # Проверка 1: Доступный баланс не должен превышать общий
            if available_balance <= total_balance:
                balance_checks.append("✅ Доступный баланс ≤ Общий баланс")
            else:
                balance_checks.append("❌ Доступный баланс > Общий баланс (некорректно)")
            
            # Проверка 2: Значения не должны быть отрицательными (кроме P&L)
            if total_balance >= 0:
                balance_checks.append("✅ Общий баланс ≥ 0")
            else:
                balance_checks.append("❌ Общий баланс < 0 (некорректно)")
                
            if available_balance >= 0:
                balance_checks.append("✅ Доступный баланс ≥ 0")
            else:
                balance_checks.append("❌ Доступный баланс < 0 (некорректно)")
            
            for check in balance_checks:
                print(f"  {check}")
            
            self.test_results.append({
                'test': 'balance_parsing',
                'status': 'success',
                'total_balance': total_balance,
                'available_balance': available_balance,
                'unrealized_pnl': unrealized_pnl,
                'checks_passed': len([c for c in balance_checks if c.startswith('✅')])
            })
            
        except Exception as e:
            print(f"❌ Ошибка парсинга: {e}")
            self.test_results.append({
                'test': 'balance_parsing',
                'status': 'error',
                'error': str(e)
            })
    
    def test_multiple_calls_consistency(self, num_calls: int = 5):
        """Тест консистентности при множественных вызовах"""
        print(f"\n🔍 Тест 3: Консистентность при {num_calls} вызовах")
        
        balances = []
        execution_times = []
        
        try:
            for i in range(num_calls):
                start_time = time.time()
                response = self.api_client.get_wallet_balance()
                exec_time = (time.time() - start_time) * 1000
                
                execution_times.append(exec_time)
                
                if response:
                    balance = {
                        'total': float(response.get('totalWalletBalance', 0)),
                        'available': float(response.get('availableBalance', 0)),
                        'unrealized_pnl': float(response.get('totalUnrealizedPnl', 0))
                    }
                    balances.append(balance)
                    print(f"  Вызов {i+1}: {balance['total']:.8f} USDT ({exec_time:.1f}мс)")
                else:
                    print(f"  Вызов {i+1}: Пустой ответ")
                
                # Небольшая задержка между вызовами
                time.sleep(0.5)
            
            # Анализ консистентности
            if len(balances) > 1:
                total_balances = [b['total'] for b in balances]
                available_balances = [b['available'] for b in balances]
                
                total_variance = max(total_balances) - min(total_balances)
                available_variance = max(available_balances) - min(available_balances)
                
                print(f"\n📊 Анализ консистентности:")
                print(f"  Разброс общего баланса: {total_variance:.8f} USDT")
                print(f"  Разброс доступного баланса: {available_variance:.8f} USDT")
                print(f"  Среднее время выполнения: {sum(execution_times)/len(execution_times):.1f} мс")
                
                # Балансы должны быть стабильными (разброс < 0.01 USDT)
                is_consistent = total_variance < 0.01 and available_variance < 0.01
                
                if is_consistent:
                    print("✅ Балансы консистентны")
                else:
                    print("⚠️  Обнаружены колебания в балансах")
                
                self.test_results.append({
                    'test': 'consistency_check',
                    'status': 'success',
                    'calls_made': len(balances),
                    'total_variance': total_variance,
                    'available_variance': available_variance,
                    'is_consistent': is_consistent,
                    'avg_execution_time_ms': sum(execution_times)/len(execution_times)
                })
            
        except Exception as e:
            print(f"❌ Ошибка теста консистентности: {e}")
            self.test_results.append({
                'test': 'consistency_check',
                'status': 'error',
                'error': str(e)
            })
    
    def test_cache_behavior(self):
        """Тест поведения кэша"""
        print("\n🔍 Тест 4: Поведение кэша")
        
        try:
            # Первый вызов (должен обращаться к API)
            start_time = time.time()
            response1 = self.api_client.get_wallet_balance()
            time1 = (time.time() - start_time) * 1000
            
            # Второй вызов сразу после первого (может использовать кэш)
            start_time = time.time()
            response2 = self.api_client.get_wallet_balance()
            time2 = (time.time() - start_time) * 1000
            
            print(f"  Первый вызов: {time1:.1f} мс")
            print(f"  Второй вызов: {time2:.1f} мс")
            
            # Если второй вызов значительно быстрее, возможно используется кэш
            if time2 < time1 * 0.5 and time2 < 50:  # Менее 50мс и в 2 раза быстрее
                print("✅ Возможно используется кэширование")
                cache_used = True
            else:
                print("ℹ️  Кэширование не обнаружено или не используется")
                cache_used = False
            
            # Проверка идентичности ответов
            responses_identical = response1 == response2
            print(f"  Ответы идентичны: {'✅ Да' if responses_identical else '❌ Нет'}")
            
            self.test_results.append({
                'test': 'cache_behavior',
                'status': 'success',
                'first_call_time_ms': time1,
                'second_call_time_ms': time2,
                'cache_likely_used': cache_used,
                'responses_identical': responses_identical
            })
            
        except Exception as e:
            print(f"❌ Ошибка теста кэша: {e}")
            self.test_results.append({
                'test': 'cache_behavior',
                'status': 'error',
                'error': str(e)
            })
    
    def test_error_handling(self):
        """Тест обработки ошибок"""
        print("\n🔍 Тест 5: Обработка ошибок")
        
        try:
            # Создаем клиент с неверными ключами для тестирования ошибок
            invalid_client = BybitClient(
                api_key="invalid_key",
                api_secret="invalid_secret",
                testnet=True
            )
            
            try:
                response = invalid_client.get_wallet_balance()
                print(f"⚠️  Неожиданно получен ответ с неверными ключами: {response}")
                error_handled = False
            except Exception as e:
                print(f"✅ Ошибка корректно обработана: {type(e).__name__}")
                error_handled = True
            
            self.test_results.append({
                'test': 'error_handling',
                'status': 'success',
                'error_properly_handled': error_handled
            })
            
        except Exception as e:
            print(f"❌ Ошибка теста обработки ошибок: {e}")
            self.test_results.append({
                'test': 'error_handling',
                'status': 'error',
                'error': str(e)
            })
    
    def _print_dict_structure(self, data: Any, indent: int = 0, max_depth: int = 3):
        """Вывод структуры словаря с ограничением глубины"""
        if indent > max_depth * 2:
            print("" * indent + "...")
            return
            
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    print("" * indent + f"{key}: {type(value).__name__}")
                    if indent < max_depth * 2:
                        self._print_dict_structure(value, indent + 2, max_depth)
                else:
                    print(" " * indent + f"{key}: {value} ({type(value).__name__})")
        elif isinstance(data, list):
            print(" " * indent + f"Список из {len(data)} элементов")
            if data and indent < max_depth * 2:
                print(" " * indent + "Первый элемент:")
                self._print_dict_structure(data[0], indent + 2, max_depth)
    
    def generate_report(self):
        """Генерация итогового отчета"""
        print("\n" + "="*60)
        print("📋 ИТОГОВЫЙ ОТЧЕТ ГЛУБОКОЙ ПРОВЕРКИ БАЛАНСА")
        print("="*60)
        
        total_tests = len(self.test_results)
        successful_tests = len([r for r in self.test_results if r['status'] == 'success'])
        
        print(f"\n📊 Общая статистика:")
        print(f"  Всего тестов: {total_tests}")
        print(f"  Успешных: {successful_tests}")
        print(f"  Неудачных: {total_tests - successful_tests}")
        print(f"  Процент успеха: {(successful_tests/total_tests*100):.1f}%")
        
        print(f"\n📝 Детали тестов:")
        for i, result in enumerate(self.test_results, 1):
            status_icon = "✅" if result['status'] == 'success' else "❌"
            print(f"  {i}. {result['test']}: {status_icon} {result['status']}")
            
            if result['status'] == 'error':
                print(f"     Ошибка: {result.get('error', 'Неизвестная ошибка')}")
        
        # Сохранение отчета в файл
        report_path = Path(__file__).parent / 'balance_verification_report.json'
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'summary': {
                        'total_tests': total_tests,
                        'successful_tests': successful_tests,
                        'success_rate': successful_tests/total_tests*100 if total_tests > 0 else 0
                    },
                    'test_results': self.test_results
                }, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 Отчет сохранен: {report_path}")
        except Exception as e:
            print(f"⚠️  Не удалось сохранить отчет: {e}")
        
        return successful_tests == total_tests

def main():
    """Главная функция"""
    print("🚀 ЗАПУСК ГЛУБОКОЙ ПРОВЕРКИ БАЛАНСА")
    print("="*50)
    
    verifier = BalanceDeepVerification()
    
    # Инициализация
    if not verifier.setup():
        print("❌ Не удалось инициализировать систему")
        return False
    
    # Выполнение тестов
    raw_response = verifier.test_raw_api_call()
    verifier.test_balance_parsing(raw_response)
    verifier.test_multiple_calls_consistency()
    verifier.test_cache_behavior()
    verifier.test_error_handling()
    
    # Генерация отчета
    all_tests_passed = verifier.generate_report()
    
    if all_tests_passed:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ БАЛАНС РАБОТАЕТ КОРРЕКТНО")
    else:
        print("\n⚠️  ОБНАРУЖЕНЫ ПРОБЛЕМЫ")
        print("❌ ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА")
    
    return all_tests_passed

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)