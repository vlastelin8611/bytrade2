import logging
from datetime import datetime

class StrategyEngine:
    """Движок стратегий для управления торговыми стратегиями"""
    
    def __init__(self, api_client=None, db_manager=None, config_manager=None):
        self.api_client = api_client
        self.db_manager = db_manager
        self.config_manager = config_manager
        self.active_strategy = None
        self.is_active = False
        self.logger = logging.getLogger(__name__)
        
    def activate_strategy(self, strategy_name, risk_level, trade_amount):
        """
        Активирует выбранную стратегию
        
        Args:
            strategy_name (str): Название стратегии
            risk_level (str): Уровень риска
            trade_amount (float): Сумма для торговли
            
        Returns:
            bool: Успешность активации стратегии
        """
        try:
            self.logger.info(f"Активация стратегии: {strategy_name}, риск: {risk_level}, сумма: {trade_amount}")
            
            # Сохраняем параметры активной стратегии
            self.active_strategy = {
                'name': strategy_name,
                'risk_level': risk_level,
                'trade_amount': trade_amount,
                'activated_at': datetime.now()
            }
            
            # Устанавливаем флаг активности
            self.is_active = True
            
            # Здесь можно добавить логику запуска стратегии
            # Например, запуск отдельного потока для мониторинга рынка
            
            self.logger.info(f"Стратегия {strategy_name} успешно активирована")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при активации стратегии: {str(e)}")
            return False
    
    def deactivate_strategy(self):
        """
        Деактивирует текущую активную стратегию
        
        Returns:
            bool: Успешность деактивации стратегии
        """
        try:
            if not self.is_active:
                self.logger.warning("Попытка деактивировать неактивную стратегию")
                return False
            
            strategy_name = self.active_strategy.get('name', 'Неизвестная')
            self.logger.info(f"Деактивация стратегии: {strategy_name}")
            
            # Здесь можно добавить логику остановки стратегии
            # Например, остановка потока мониторинга рынка
            
            # Сбрасываем параметры активной стратегии
            self.active_strategy = None
            self.is_active = False
            
            self.logger.info(f"Стратегия {strategy_name} успешно деактивирована")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при деактивации стратегии: {str(e)}")
            return False
    
    def get_active_strategy(self):
        """
        Возвращает информацию о текущей активной стратегии
        
        Returns:
            dict: Информация о стратегии или None, если нет активной стратегии
        """
        return self.active_strategy
    
    def is_strategy_active(self):
        """
        Проверяет, активна ли какая-либо стратегия
        
        Returns:
            bool: True, если стратегия активна, иначе False
        """
        return self.is_active