#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Адаптивная ML стратегия для торговли на основе исторических данных
Использует машинное обучение для анализа рынка и принятия торговых решений
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
from pathlib import Path
import pickle
import json
import time

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score, classification_report
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn не установлен. ML функции будут ограничены.")

class TechnicalIndicators:
    """
    Класс для расчета технических индикаторов
    """
    
    @staticmethod
    def sma(data: List[float], period: int) -> List[float]:
        """Простая скользящая средняя"""
        if len(data) < period:
            return []
        
        sma_values = []
        for i in range(period - 1, len(data)):
            sma_values.append(sum(data[i - period + 1:i + 1]) / period)
        
        return sma_values
    
    @staticmethod
    def ema(data: List[float], period: int) -> List[float]:
        """Экспоненциальная скользящая средняя"""
        if len(data) < period:
            return []
        
        multiplier = 2 / (period + 1)
        ema_values = [sum(data[:period]) / period]  # Первое значение - SMA
        
        for i in range(period, len(data)):
            ema_values.append((data[i] * multiplier) + (ema_values[-1] * (1 - multiplier)))
        
        return ema_values
    
    @staticmethod
    def rsi(data: List[float], period: int = 14) -> List[float]:
        """Индекс относительной силы"""
        if len(data) < period + 1:
            return []
        
        deltas = [data[i] - data[i-1] for i in range(1, len(data))]
        gains = [delta if delta > 0 else 0 for delta in deltas]
        losses = [-delta if delta < 0 else 0 for delta in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        rsi_values = []
        
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi_values.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100 - (100 / (1 + rs)))
        
        return rsi_values
    
    @staticmethod
    def macd(data: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, List[float]]:
        """MACD индикатор"""
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        
        if len(ema_fast) < len(ema_slow):
            ema_slow = ema_slow[len(ema_slow) - len(ema_fast):]
        elif len(ema_slow) < len(ema_fast):
            ema_fast = ema_fast[len(ema_fast) - len(ema_slow):]
        
        macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(ema_fast))]
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        
        histogram = []
        if len(signal_line) > 0:
            start_idx = len(macd_line) - len(signal_line)
            histogram = [macd_line[start_idx + i] - signal_line[i] for i in range(len(signal_line))]
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    @staticmethod
    def bollinger_bands(data: List[float], period: int = 20, std_dev: float = 2) -> Dict[str, List[float]]:
        """Полосы Боллинджера"""
        sma = TechnicalIndicators.sma(data, period)
        
        if len(sma) == 0:
            return {'upper': [], 'middle': [], 'lower': []}
        
        upper_band = []
        lower_band = []
        
        for i in range(len(sma)):
            data_slice = data[i:i + period]
            std = np.std(data_slice)
            upper_band.append(sma[i] + (std * std_dev))
            lower_band.append(sma[i] - (std * std_dev))
        
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band
        }

class MarketRegimeDetector:
    """
    Детектор рыночного режима (тренд, флэт, волатильность)
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_regime(self, prices: List[float], volume: List[float] = None) -> Dict[str, Any]:
        """Определение текущего рыночного режима"""
        if len(prices) < 50:
            return {'regime': 'unknown', 'confidence': 0.0}
        
        # Расчет волатильности
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        volatility = np.std(returns) * 100
        
        # Определение тренда
        sma_short = TechnicalIndicators.sma(prices, 10)
        sma_long = TechnicalIndicators.sma(prices, 30)
        
        if len(sma_short) == 0 or len(sma_long) == 0:
            return {'regime': 'unknown', 'confidence': 0.0}
        
        # Сравнение последних значений
        trend_strength = (sma_short[-1] - sma_long[-1]) / sma_long[-1] * 100
        
        # Определение режима
        if abs(trend_strength) > 2 and volatility < 5:
            regime = 'trending_up' if trend_strength > 0 else 'trending_down'
            confidence = min(abs(trend_strength) / 5, 1.0)
        elif volatility > 8:
            regime = 'high_volatility'
            confidence = min(volatility / 15, 1.0)
        else:
            regime = 'sideways'
            confidence = 1.0 - min(abs(trend_strength) / 2, 0.8)
        
        return {
            'regime': regime,
            'confidence': confidence,
            'volatility': volatility,
            'trend_strength': trend_strength
        }

class AdaptiveMLStrategy:
    """
    Адаптивная ML стратегия для торговли
    """
    
    def __init__(self, name: str, config: Dict, api_client, db_manager, config_manager):
        self.name = name
        self.config = config
        self.api_client = api_client
        self.db_manager = db_manager
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Параметры стратегии
        self.feature_window = config.get('feature_window', 50)
        self.confidence_threshold = config.get('confidence_threshold', 0.5)  # Временно снижен с 0.65 до 0.5 для тестирования
        self.use_technical_indicators = config.get('use_technical_indicators', True)
        self.use_market_regime = config.get('use_market_regime', True)
        
        # ML модели
        self.models = {}
        self.scalers = {}
        self.model_performance = {}
        self.performance = {}  # Добавляем атрибут для хранения метрик обучения
        
        # Компоненты анализа
        self.technical_indicators = TechnicalIndicators()
        self.regime_detector = MarketRegimeDetector()
        
        # Данные для обучения
        self.training_data = []
        self.model_path = Path(__file__).parent / 'models'
        self.model_path.mkdir(exist_ok=True)
        
        # Загрузка существующих моделей
        self.load_models()
        
        self.logger.info(f"Инициализирована ML стратегия: {name}")
    
    def prepare_historical_data(self, symbol: str, timeframe: str, limit: int = 500):
        """
        Подготовка исторических данных для стратегии с использованием ticker_loader
        
        Args:
            symbol: Торговый символ
            timeframe: Временной интервал
            limit: Количество исторических свечей для загрузки
            
        Returns:
            bool: True если данные успешно загружены, иначе False
        """
        try:
            if hasattr(self, 'ticker_loader') and self.ticker_loader:
                self.logger.info(f"Загрузка исторических данных для {symbol} из ticker_loader")
                return self.load_historical_data_from_ticker_loader(symbol, timeframe, limit)
            else:
                self.logger.warning("ticker_loader не доступен, используем стандартный метод загрузки")
                return self.load_historical_data_from_api(symbol, timeframe, limit)
        except Exception as e:
            self.logger.error(f"Ошибка при подготовке исторических данных: {e}")
            return False
    
    def load_historical_data_from_ticker_loader(self, symbol: str, timeframe: str, limit: int = 500):
        """Загрузка исторических данных из ticker_loader"""
        try:
            if not hasattr(self, 'ticker_loader') or not self.ticker_loader:
                return False
                
            # Получаем данные из ticker_loader
            data = self.ticker_loader.get_ticker_data(symbol)
            if not data or 'klines' not in data:
                self.logger.warning(f"Нет данных в ticker_loader для {symbol}")
                return False
                
            klines = data['klines'][-limit:] if len(data['klines']) > limit else data['klines']
            
            if len(klines) < self.feature_window:
                self.logger.warning(f"Недостаточно данных для {symbol}: {len(klines)} < {self.feature_window}")
                return False
                
            # Обучаем модель на исторических данных
            return self.train_on_historical_data(symbol, klines)
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки из ticker_loader для {symbol}: {e}")
            return False
    
    def load_historical_data_from_api(self, symbol: str, timeframe: str, limit: int = 500):
        """Загрузка исторических данных напрямую через API"""
        try:
            if not self.api_client:
                return False
                
            # Получаем исторические данные через API
            result = self.api_client.get_klines(
                category='spot',
                symbol=symbol,
                interval=timeframe,
                limit=limit
            )
            
            if not result or 'list' not in result:
                self.logger.warning(f"API не вернул данные для {symbol}")
                return False
                
            klines = result['list']
            if len(klines) < self.feature_window:
                self.logger.warning(f"Недостаточно данных от API для {symbol}: {len(klines)} < {self.feature_window}")
                return False
                
            # Преобразуем формат данных API в стандартный формат
            formatted_klines = []
            for kline in klines:
                formatted_klines.append({
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[5]),
                    'timestamp': int(kline[0])
                })
                
            # Обучаем модель на исторических данных
            return self.train_on_historical_data(symbol, formatted_klines)
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки через API для {symbol}: {e}")
            return False
    
    def train_on_historical_data(self, symbol: str, klines: List[Dict]):
        """Обучение модели на исторических данных"""
        try:
            if not SKLEARN_AVAILABLE or len(klines) < self.feature_window + 10:
                return False
                
            features = []
            labels = []
            
            # Извлекаем признаки и создаем метки
            for i in range(self.feature_window, len(klines) - 1):
                window = klines[i - self.feature_window : i]
                feat = self.extract_features(window)
                if feat:
                    features.append(feat)
                    
                    # Создаем метку на основе изменения цены
                    current_price = float(klines[i]['close'])
                    future_price = float(klines[i + 1]['close'])
                    change = (future_price - current_price) / current_price
                    
                    # Метки: 1 (BUY), -1 (SELL), 0 (HOLD)
                    if change > 0.002:  # рост > 0.2%
                        label = 1
                    elif change < -0.002:  # падение > 0.2%
                        label = -1
                    else:
                        label = 0
                    labels.append(label)
            
            if len(features) < 50:  # Минимум данных для обучения
                self.logger.warning(f"Недостаточно признаков для обучения {symbol}: {len(features)}")
                return False
                
            # Обучаем модель
            self.train_model(symbol, features, labels)
            self.logger.info(f"✅ Модель обучена для {symbol} на {len(features)} примерах")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка обучения на исторических данных для {symbol}: {e}")
            return False
            
    def analyze_market(self, market_data: Dict) -> Dict[str, Any]:
        """Анализ рынка и генерация торгового сигнала"""
        try:
            symbol = market_data['symbol']
            klines = market_data['klines']
            current_price = market_data['current_price']
            
            if len(klines) < self.feature_window:
                return {'signal': None, 'confidence': 0.0, 'reason': 'Недостаточно данных'}
            
            # Извлечение признаков
            features = self.extract_features(klines)
            if not features:
                return {'signal': None, 'confidence': 0.0, 'reason': 'Ошибка извлечения признаков'}
            
            # Определение рыночного режима
            prices = [float(k['close']) for k in klines]
            regime_info = self.regime_detector.detect_regime(prices)
            
            # Получение предсказания от ML модели
            prediction = self.predict_signal(symbol, features, regime_info)
            
            # Логирование анализа
            analysis_log = {
                'timestamp': datetime.now(),
                'symbol': symbol,
                'current_price': current_price,
                'features': features,
                'regime': regime_info,
                'prediction': prediction
            }
            self.db_manager.log_analysis(analysis_log)
            
            return prediction
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа рынка {market_data.get('symbol', 'unknown')}: {e}")
            return {'signal': None, 'confidence': 0.0, 'reason': f'Ошибка: {str(e)}'}
    
    def extract_features(self, klines: List[Dict]) -> Optional[List[float]]:
        """Извлечение признаков из исторических данных"""
        try:
            # Базовые цены
            opens = [float(k['open']) for k in klines]
            highs = [float(k['high']) for k in klines]
            lows = [float(k['low']) for k in klines]
            closes = [float(k['close']) for k in klines]
            volumes = [float(k['volume']) for k in klines]
            
            features = []
            
            # Ценовые признаки
            current_price = closes[-1]
            
            # Безопасный расчет изменений цены
            if len(closes) > 1 and closes[-2] != 0 and np.isfinite(closes[-1]) and np.isfinite(closes[-2]):
                price_change_1h = (closes[-1] - closes[-2]) / closes[-2]
                price_change_1h = np.clip(price_change_1h, -0.5, 0.5)  # Ограничиваем экстремальные изменения
            else:
                price_change_1h = 0
                
            if len(closes) > 24 and closes[-25] != 0 and np.isfinite(closes[-1]) and np.isfinite(closes[-25]):
                price_change_24h = (closes[-1] - closes[-25]) / closes[-25]
                price_change_24h = np.clip(price_change_24h, -0.5, 0.5)  # Ограничиваем экстремальные изменения
            else:
                price_change_24h = 0
            
            features.extend([current_price, price_change_1h, price_change_24h])
            
            # Технические индикаторы
            if self.use_technical_indicators:
                # RSI
                rsi_values = self.technical_indicators.rsi(closes, 14)
                current_rsi = rsi_values[-1] if rsi_values else 50
                features.append(current_rsi)
                
                # MACD
                macd_data = self.technical_indicators.macd(closes)
                if macd_data['macd'] and macd_data['signal']:
                    macd_value = macd_data['macd'][-1]
                    signal_value = macd_data['signal'][-1]
                    features.extend([macd_value, signal_value, macd_value - signal_value])
                else:
                    features.extend([0, 0, 0])
                
                # Bollinger Bands
                bb_data = self.technical_indicators.bollinger_bands(closes)
                if bb_data['middle'] and bb_data['upper'] and bb_data['lower']:
                    upper_val = bb_data['upper'][-1]
                    lower_val = bb_data['lower'][-1]
                    # Проверяем на деление на ноль и бесконечные значения
                    if upper_val != lower_val and np.isfinite(upper_val) and np.isfinite(lower_val) and np.isfinite(current_price):
                        bb_position = (current_price - lower_val) / (upper_val - lower_val)
                        # Ограничиваем значение в разумных пределах
                        bb_position = np.clip(bb_position, -2.0, 3.0)
                        features.append(bb_position)
                    else:
                        features.append(0.5)
                else:
                    features.append(0.5)
                
                # Скользящие средние
                sma_10 = self.technical_indicators.sma(closes, 10)
                sma_20 = self.technical_indicators.sma(closes, 20)
                
                if sma_10 and sma_20 and sma_20[-1] != 0 and np.isfinite(sma_10[-1]) and np.isfinite(sma_20[-1]):
                    sma_ratio = sma_10[-1] / sma_20[-1]
                    # Ограничиваем значение в разумных пределах
                    sma_ratio = np.clip(sma_ratio, 0.5, 2.0)
                    features.append(sma_ratio)
                else:
                    features.append(1.0)
            
            # Объемные признаки
            if len(volumes) > 1:
                volume_change = (volumes[-1] - volumes[-2]) / volumes[-2] if volumes[-2] > 0 and np.isfinite(volumes[-1]) and np.isfinite(volumes[-2]) else 0
                avg_volume = sum(volumes[-10:]) / min(10, len(volumes))
                volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 and np.isfinite(volumes[-1]) and np.isfinite(avg_volume) else 1
                # Ограничиваем значения в разумных пределах
                volume_change = np.clip(volume_change, -10.0, 10.0)
                volume_ratio = np.clip(volume_ratio, 0.1, 10.0)
                features.extend([volume_change, volume_ratio])
            else:
                features.extend([0, 1])
            
            # Волатильность
            if len(closes) > 20:
                returns = []
                for i in range(1, len(closes)):
                    if closes[i-1] != 0 and np.isfinite(closes[i]) and np.isfinite(closes[i-1]):
                        ret = (closes[i] - closes[i-1]) / closes[i-1]
                        # Ограничиваем экстремальные значения доходности
                        ret = np.clip(ret, -0.5, 0.5)
                        returns.append(ret)
                    else:
                        returns.append(0)
                
                if returns:
                    volatility = np.std(returns[-20:]) * 100
                    # Ограничиваем волатильность в разумных пределах
                    volatility = np.clip(volatility, 0, 50)
                    features.append(volatility)
                else:
                    features.append(0)
            else:
                features.append(0)
            
            return features
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения признаков: {e}")
            return None
    
    def predict_signal(self, symbol: str, features: List[float], regime_info: Dict) -> Dict[str, Any]:
        """Предсказание торгового сигнала"""
        try:
            # Если ML недоступен, используем простую логику
            if not SKLEARN_AVAILABLE or symbol not in self.models:
                return self.simple_signal_logic(features, regime_info)
            
            # Нормализация признаков
            if symbol in self.scalers:
                features_scaled = self.scalers[symbol].transform([features])[0]
            else:
                features_scaled = features
            
            # Получение предсказания
            model = self.models[symbol]
            prediction_proba = model.predict_proba([features_scaled])[0]
            prediction_class = model.predict([features_scaled])[0]
            
            # Определение сигнала и уверенности
            if prediction_class == 1:  # BUY
                signal = 'BUY'
                confidence = prediction_proba[1]
            elif prediction_class == 2:  # SELL
                signal = 'SELL'
                confidence = prediction_proba[2]
            else:  # HOLD
                signal = None
                confidence = prediction_proba[0]
            
            # Корректировка на основе рыночного режима
            if self.use_market_regime:
                regime_adjustment = self.adjust_for_regime(signal, confidence, regime_info)
                signal = regime_adjustment['signal']
                confidence = regime_adjustment['confidence']
            
            # Проверка порога уверенности
            if confidence < self.confidence_threshold:
                signal = None
            
            return {
                'signal': signal,
                'confidence': confidence,
                'regime': regime_info,
                'model_used': True
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка предсказания для {symbol}: {e}")
            return self.simple_signal_logic(features, regime_info)
    
    def simple_signal_logic(self, features: List[float], regime_info: Dict) -> Dict[str, Any]:
        """Простая логика сигналов без ML"""
        try:
            if len(features) < 4:
                return {'signal': None, 'confidence': 0.0, 'model_used': False}
            
            price_change_1h = features[1]
            price_change_24h = features[2]
            rsi = features[3] if len(features) > 3 else 50
            
            signal = None
            confidence = 0.0
            
            # Простые правила
            if price_change_1h > 0.02 and price_change_24h > 0.05 and rsi < 70:
                signal = 'BUY'
                confidence = min(0.7, (price_change_1h + price_change_24h) * 5)
            elif price_change_1h < -0.02 and price_change_24h < -0.05 and rsi > 30:
                signal = 'SELL'
                confidence = min(0.7, abs(price_change_1h + price_change_24h) * 5)
            
            # Корректировка на волатильность
            if regime_info.get('regime') == 'high_volatility':
                confidence *= 0.7  # Снижаем уверенность в волатильном рынке
            
            return {
                'signal': signal,
                'confidence': confidence,
                'regime': regime_info,
                'model_used': False
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка простой логики: {e}")
            return {'signal': None, 'confidence': 0.0, 'model_used': False}
    
    def adjust_for_regime(self, signal: str, confidence: float, regime_info: Dict) -> Dict[str, Any]:
        """Корректировка сигнала на основе рыночного режима"""
        regime = regime_info.get('regime', 'unknown')
        regime_confidence = regime_info.get('confidence', 0.5)
        
        adjusted_confidence = confidence
        adjusted_signal = signal
        
        # Корректировки для разных режимов
        if regime == 'trending_up' and signal == 'BUY':
            adjusted_confidence *= (1 + regime_confidence * 0.2)
        elif regime == 'trending_down' and signal == 'SELL':
            adjusted_confidence *= (1 + regime_confidence * 0.2)
        elif regime == 'high_volatility':
            adjusted_confidence *= 0.8  # Снижаем уверенность в волатильном рынке
        elif regime == 'sideways':
            adjusted_confidence *= 0.9  # Немного снижаем уверенность во флэте
        
        # Ограничиваем уверенность
        adjusted_confidence = min(adjusted_confidence, 0.95)
        
        return {
            'signal': adjusted_signal,
            'confidence': adjusted_confidence
        }
    
    def learn_from_trade(self, trade_result: Dict):
        """Обучение на результатах торговли"""
        try:
            # Добавляем результат торговли в данные для обучения
            self.training_data.append(trade_result)
            
            # Переобучение модели каждые 50 сделок
            if len(self.training_data) % 50 == 0:
                self.retrain_models()
            
            self.logger.debug(f"Добавлен результат торговли для обучения: {trade_result['symbol']}")
            
        except Exception as e:
            self.logger.error(f"Ошибка обучения на результате торговли: {e}")
    
    def retrain_models(self):
        """Переобучение ML моделей"""
        if not SKLEARN_AVAILABLE or len(self.training_data) < 100:
            return
        
        try:
            # Группировка данных по символам
            symbol_data = {}
            for trade in self.training_data:
                symbol = trade['symbol']
                if symbol not in symbol_data:
                    symbol_data[symbol] = []
                symbol_data[symbol].append(trade)
            
            # Переобучение для каждого символа
            for symbol, trades in symbol_data.items():
                if len(trades) >= 50:  # Минимум данных для обучения
                    self.train_symbol_model(symbol, trades)
            
            # Сохранение моделей
            self.save_models()
            
            self.logger.info(f"Переобучение завершено для {len(symbol_data)} символов")
            
        except Exception as e:
            self.logger.error(f"Ошибка переобучения моделей: {e}")
    
    def train_symbol_model(self, symbol: str, trades: List[Dict]):
        """Обучение модели для конкретного символа"""
        try:
            # Подготовка данных
            X = []
            y = []
            
            for trade in trades:
                if 'analysis' in trade and 'features' in trade['analysis']:
                    features = trade['analysis']['features']
                    
                    # Определение целевой переменной на основе результата
                    # Это упрощенная логика, в реальности нужно анализировать PnL
                    if trade['side'] == 'Buy':
                        target = 1  # BUY
                    elif trade['side'] == 'Sell':
                        target = 2  # SELL
                    else:
                        target = 0  # HOLD
                    
                    X.append(features)
                    y.append(target)
            
            if len(X) < 20:  # Минимум для обучения
                return
            
            X = np.array(X)
            y = np.array(y)
            
            # Разделение на обучающую и тестовую выборки
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Нормализация признаков
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Обучение модели
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            # Оценка качества
            y_pred = model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            
            # Сохранение модели и скейлера
            self.models[symbol] = model
            self.scalers[symbol] = scaler
            self.model_performance[symbol] = accuracy
            
            self.logger.info(f"Модель для {symbol} обучена с точностью: {accuracy:.3f}")
            
        except Exception as e:
            self.logger.error(f"Ошибка обучения модели для {symbol}: {e}")
    
    def train_model(self, symbol: str, features: List[List[float]], labels: List[int]):
        """Обучение модели для конкретного символа"""
        try:
            if not SKLEARN_AVAILABLE or len(features) < 20:
                self.logger.warning(f"Недостаточно данных для обучения {symbol}: {len(features)}")
                return False
            
            X = np.array(features)
            y = np.array(labels)
            
            # Разделение на обучающую и тестовую выборки
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Нормализация признаков
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Обучение модели
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            # Оценка качества
            y_pred = model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)

            report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
            precision = report.get('weighted avg', {}).get('precision', 0.0)
            recall = report.get('weighted avg', {}).get('recall', 0.0)
            f1_score = report.get('weighted avg', {}).get('f1-score', 0.0)

            # Сохранение модели и скейлера
            self.models[symbol] = model
            self.scalers[symbol] = scaler
            self.model_performance[symbol] = accuracy

            # Обновляем атрибут performance для GUI
            self.performance[symbol] = {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1_score': f1_score,
                'samples': len(features),
                'last_trained': time.time()
            }

            self.logger.info(f"Модель для {symbol} обучена с точностью: {accuracy:.3f}")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка обучения модели для {symbol}: {e}")
            return False
    
    def load_models(self):
        """Загрузка сохраненных моделей"""
        try:
            self.logger.info("🔍 Начало загрузки моделей...")
            models_file = self.model_path / f"{self.name}_models.pkl"
            scalers_file = self.model_path / f"{self.name}_scalers.pkl"
            performance_file = self.model_path / f"{self.name}_performance.json"
            training_state_file = self.model_path / f"{self.name}_training_state.json"
            self.logger.info(
                f"📁 Проверка файлов: {models_file.name}, {scalers_file.name}, {performance_file.name}, {training_state_file.name}"
            )

            if models_file.exists():
                self.logger.info("📊 Загрузка моделей...")
                with open(models_file, 'rb') as f:
                    self.models = pickle.load(f)
                self.logger.info(f"Загружено {len(self.models)} моделей")
            else:
                self.logger.info("❌ Файл моделей не найден")

            if scalers_file.exists():
                self.logger.info("📏 Загрузка скейлеров...")
                with open(scalers_file, 'rb') as f:
                    self.scalers = pickle.load(f)
            else:
                self.logger.info("❌ Файл скейлеров не найден")

            if performance_file.exists():
                self.logger.info("📈 Загрузка статистики производительности...")
                with open(performance_file, 'r') as f:
                    self.model_performance = json.load(f)
            else:
                self.logger.info("❌ Файл статистики не найден")

            if training_state_file.exists():
                self.logger.info("📈 Загрузка состояния обучения моделей...")
                with open(training_state_file, 'r') as f:
                    stored_state = json.load(f)

                if isinstance(stored_state, dict):
                    self.performance = stored_state
                    for symbol, metrics in stored_state.items():
                        if isinstance(metrics, dict):
                            accuracy = metrics.get('accuracy')
                            if accuracy is not None:
                                self.model_performance[symbol] = accuracy
                else:
                    self.logger.warning("Некорректный формат файла состояния обучения")
            else:
                # Обеспечиваем обратную совместимость
                self.performance = {
                    symbol: {
                        'accuracy': accuracy,
                        'precision': 0.0,
                        'recall': 0.0,
                        'f1_score': 0.0,
                        'samples': 0,
                        'last_trained': None
                    }
                    for symbol, accuracy in self.model_performance.items()
                }

            self.logger.info("✅ Загрузка моделей завершена")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки моделей: {e}")

    def save_models(self):
        """Сохранение моделей"""
        try:
            models_file = self.model_path / f"{self.name}_models.pkl"
            scalers_file = self.model_path / f"{self.name}_scalers.pkl"
            performance_file = self.model_path / f"{self.name}_performance.json"
            training_state_file = self.model_path / f"{self.name}_training_state.json"

            with open(models_file, 'wb') as f:
                pickle.dump(self.models, f)

            with open(scalers_file, 'wb') as f:
                pickle.dump(self.scalers, f)

            with open(performance_file, 'w') as f:
                json.dump(self.model_performance, f)

            with open(training_state_file, 'w') as f:
                json.dump(self.performance, f)

            self.logger.info("Модели сохранены")

        except Exception as e:
            self.logger.error(f"Ошибка сохранения моделей: {e}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Получение статистики производительности"""
        if not self.model_performance:
            return {'average_accuracy': 0.0, 'models_count': 0}
        
        avg_accuracy = sum(self.model_performance.values()) / len(self.model_performance)
        
        return {
            'average_accuracy': avg_accuracy,
            'models_count': len(self.models),
            'symbols': list(self.models.keys()),
            'individual_performance': self.model_performance
        }