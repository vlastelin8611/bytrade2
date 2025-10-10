"""
Система мониторинга производительности для торгового бота
Отслеживает метрики производительности, время выполнения операций и использование ресурсов
"""

import time
import psutil
import threading
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import defaultdict, deque
import logging


class PerformanceMetrics:
    """Класс для хранения метрик производительности"""
    
    def __init__(self):
        self.start_time = time.time()
        self.operation_times = defaultdict(list)
        self.operation_counts = defaultdict(int)
        self.error_counts = defaultdict(int)
        self.memory_usage = deque(maxlen=100)  # Последние 100 измерений
        self.cpu_usage = deque(maxlen=100)
        self.api_response_times = deque(maxlen=100)
        self.ml_analysis_times = deque(maxlen=100)
        self.trade_execution_times = deque(maxlen=100)
        
        # Счетчики операций
        self.total_api_calls = 0
        self.successful_api_calls = 0
        self.failed_api_calls = 0
        self.total_ml_analyses = 0
        self.successful_trades = 0
        self.failed_trades = 0
        
        # Временные метки важных событий
        self.last_successful_trade = None
        self.last_api_error = None
        self.last_ml_analysis = None
        
        self._lock = threading.Lock()
    
    def record_operation_time(self, operation: str, duration_ms: float):
        """Записывает время выполнения операции"""
        with self._lock:
            self.operation_times[operation].append(duration_ms)
            self.operation_counts[operation] += 1
            
            # Ограничиваем размер списка для экономии памяти
            if len(self.operation_times[operation]) > 1000:
                self.operation_times[operation] = self.operation_times[operation][-500:]
    
    def record_error(self, operation: str):
        """Записывает ошибку операции"""
        with self._lock:
            self.error_counts[operation] += 1
    
    def record_system_metrics(self):
        """Записывает системные метрики"""
        with self._lock:
            # Использование памяти процессом
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.memory_usage.append(memory_mb)
            
            # Использование CPU
            cpu_percent = process.cpu_percent()
            self.cpu_usage.append(cpu_percent)
    
    def get_average_time(self, operation: str) -> float:
        """Возвращает среднее время выполнения операции"""
        with self._lock:
            times = self.operation_times.get(operation, [])
            return sum(times) / len(times) if times else 0.0
    
    def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """Возвращает статистику по операции"""
        with self._lock:
            times = self.operation_times.get(operation, [])
            if not times:
                return {
                    'count': 0,
                    'avg_time_ms': 0.0,
                    'min_time_ms': 0.0,
                    'max_time_ms': 0.0,
                    'error_count': self.error_counts.get(operation, 0)
                }
            
            return {
                'count': len(times),
                'avg_time_ms': sum(times) / len(times),
                'min_time_ms': min(times),
                'max_time_ms': max(times),
                'error_count': self.error_counts.get(operation, 0),
                'success_rate': (len(times) / (len(times) + self.error_counts.get(operation, 0))) * 100
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Возвращает системную статистику"""
        with self._lock:
            uptime_seconds = time.time() - self.start_time
            
            return {
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': str(timedelta(seconds=int(uptime_seconds))),
                'memory_usage_mb': {
                    'current': list(self.memory_usage)[-1] if self.memory_usage else 0,
                    'avg': sum(self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0,
                    'max': max(self.memory_usage) if self.memory_usage else 0
                },
                'cpu_usage_percent': {
                    'current': list(self.cpu_usage)[-1] if self.cpu_usage else 0,
                    'avg': sum(self.cpu_usage) / len(self.cpu_usage) if self.cpu_usage else 0,
                    'max': max(self.cpu_usage) if self.cpu_usage else 0
                },
                'api_stats': {
                    'total_calls': self.total_api_calls,
                    'successful_calls': self.successful_api_calls,
                    'failed_calls': self.failed_api_calls,
                    'success_rate': (self.successful_api_calls / self.total_api_calls * 100) if self.total_api_calls > 0 else 0
                },
                'trading_stats': {
                    'total_ml_analyses': self.total_ml_analyses,
                    'successful_trades': self.successful_trades,
                    'failed_trades': self.failed_trades,
                    'last_successful_trade': self.last_successful_trade.isoformat() if self.last_successful_trade else None,
                    'last_ml_analysis': self.last_ml_analysis.isoformat() if self.last_ml_analysis else None
                }
            }


class PerformanceMonitor:
    """Основной класс мониторинга производительности"""
    
    def __init__(self, log_file: Optional[Path] = None):
        self.metrics = PerformanceMetrics()
        self.logger = logging.getLogger(__name__)
        self.log_file = log_file
        self.monitoring_active = False
        self.monitoring_thread = None
        self.monitoring_interval = 30  # секунд
        
        # Создаем директорию для логов производительности
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def start_monitoring(self):
        """Запускает мониторинг производительности"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        self.logger.info("🔍 Мониторинг производительности запущен")
    
    def stop_monitoring(self):
        """Останавливает мониторинг производительности"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        self.logger.info("🔍 Мониторинг производительности остановлен")
    
    def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        while self.monitoring_active:
            try:
                # Записываем системные метрики
                self.metrics.record_system_metrics()
                
                # Логируем статистику каждые 5 минут
                if int(time.time()) % 300 == 0:
                    self._log_performance_summary()
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Ошибка в цикле мониторинга: {e}")
                time.sleep(self.monitoring_interval)
    
    def record_api_call(self, operation: str, duration_ms: float, success: bool = True):
        """Записывает метрики API вызова"""
        self.metrics.record_operation_time(f"api_{operation}", duration_ms)
        self.metrics.total_api_calls += 1
        
        if success:
            self.metrics.successful_api_calls += 1
        else:
            self.metrics.failed_api_calls += 1
            self.metrics.record_error(f"api_{operation}")
            self.metrics.last_api_error = datetime.now()
        
        # Записываем время ответа API
        self.metrics.api_response_times.append(duration_ms)
    
    def record_ml_analysis(self, symbol: str, duration_ms: float, success: bool = True):
        """Записывает метрики ML анализа"""
        self.metrics.record_operation_time("ml_analysis", duration_ms)
        self.metrics.total_ml_analyses += 1
        self.metrics.last_ml_analysis = datetime.now()
        
        if not success:
            self.metrics.record_error("ml_analysis")
        
        # Записываем время ML анализа
        self.metrics.ml_analysis_times.append(duration_ms)
    
    def record_trade_execution(self, symbol: str, duration_ms: float, success: bool = True):
        """Записывает метрики выполнения торговых операций"""
        self.metrics.record_operation_time("trade_execution", duration_ms)
        
        if success:
            self.metrics.successful_trades += 1
            self.metrics.last_successful_trade = datetime.now()
        else:
            self.metrics.failed_trades += 1
            self.metrics.record_error("trade_execution")
        
        # Записываем время выполнения торговых операций
        self.metrics.trade_execution_times.append(duration_ms)
    
    def record_operation(self, operation: str, duration_ms: float, success: bool = True):
        """Записывает метрики произвольной операции"""
        self.metrics.record_operation_time(operation, duration_ms)
        
        if not success:
            self.metrics.record_error(operation)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Возвращает сводку производительности"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'system_stats': self.metrics.get_system_stats(),
            'operation_stats': {}
        }
        
        # Добавляем статистику по всем операциям
        all_operations = set(self.metrics.operation_times.keys()) | set(self.metrics.error_counts.keys())
        for operation in all_operations:
            summary['operation_stats'][operation] = self.metrics.get_operation_stats(operation)
        
        return summary
    
    def _log_performance_summary(self):
        """Логирует сводку производительности"""
        try:
            summary = self.get_performance_summary()
            
            # Логируем в основной лог
            system_stats = summary['system_stats']
            self.logger.info(
                f"📊 Производительность: "
                f"Память: {system_stats['memory_usage_mb']['current']:.1f}MB, "
                f"CPU: {system_stats['cpu_usage_percent']['current']:.1f}%, "
                f"API успешность: {system_stats['api_stats']['success_rate']:.1f}%, "
                f"Время работы: {system_stats['uptime_formatted']}"
            )
            
            # Сохраняем детальную статистику в файл
            if self.log_file:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
                    
        except Exception as e:
            self.logger.error(f"Ошибка при логировании производительности: {e}")
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """Возвращает список предупреждений о производительности"""
        alerts = []
        
        try:
            # Проверяем использование памяти
            if self.metrics.memory_usage:
                current_memory = list(self.metrics.memory_usage)[-1]
                if current_memory > 500:  # Более 500MB
                    alerts.append({
                        'type': 'memory_high',
                        'severity': 'warning',
                        'message': f'Высокое использование памяти: {current_memory:.1f}MB',
                        'value': current_memory
                    })
            
            # Проверяем использование CPU
            if self.metrics.cpu_usage:
                current_cpu = list(self.metrics.cpu_usage)[-1]
                if current_cpu > 80:  # Более 80%
                    alerts.append({
                        'type': 'cpu_high',
                        'severity': 'warning',
                        'message': f'Высокое использование CPU: {current_cpu:.1f}%',
                        'value': current_cpu
                    })
            
            # Проверяем успешность API вызовов
            if self.metrics.total_api_calls > 10:
                success_rate = (self.metrics.successful_api_calls / self.metrics.total_api_calls) * 100
                if success_rate < 90:  # Менее 90% успешности
                    alerts.append({
                        'type': 'api_errors',
                        'severity': 'error',
                        'message': f'Низкая успешность API: {success_rate:.1f}%',
                        'value': success_rate
                    })
            
            # Проверяем время ответа API
            if self.metrics.api_response_times:
                avg_response_time = sum(self.metrics.api_response_times) / len(self.metrics.api_response_times)
                if avg_response_time > 5000:  # Более 5 секунд
                    alerts.append({
                        'type': 'api_slow',
                        'severity': 'warning',
                        'message': f'Медленные API ответы: {avg_response_time:.0f}ms',
                        'value': avg_response_time
                    })
            
        except Exception as e:
            self.logger.error(f"Ошибка при проверке предупреждений: {e}")
        
        return alerts


# Глобальный экземпляр монитора производительности
_performance_monitor = None


def get_performance_monitor() -> PerformanceMonitor:
    """Возвращает глобальный экземпляр монитора производительности"""
    global _performance_monitor
    if _performance_monitor is None:
        log_file = Path("logs") / "performance" / f"performance_{datetime.now().strftime('%Y%m%d')}.json"
        _performance_monitor = PerformanceMonitor(log_file)
    return _performance_monitor


def start_performance_monitoring():
    """Запускает глобальный мониторинг производительности"""
    monitor = get_performance_monitor()
    monitor.start_monitoring()


def stop_performance_monitoring():
    """Останавливает глобальный мониторинг производительности"""
    global _performance_monitor
    if _performance_monitor:
        _performance_monitor.stop_monitoring()


# Декоратор для автоматического измерения времени выполнения функций
def measure_performance(operation_name: str = None):
    """Декоратор для измерения производительности функций"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                monitor = get_performance_monitor()
                monitor.record_operation(op_name, duration_ms, success)
        
        return wrapper
    return decorator