#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Новая система автоматической торговли с фокусом на нейросеть и шорты
Полностью переписанная система генерации торговых сигналов
"""

import numpy as np
import pandas as pd
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class NeuralTradingEngine:
    """
    Новая система автоматической торговли с акцентом на:
    1. Анализ данных нейросети
    2. Торговля шортами (SELL сигналы)
    3. Выбор наиболее уверенных позиций
    4. Интеграция с историческими данными тикеров
    """
    
    def __init__(self, config: Dict, api_client, db_manager, ticker_loader):
        self.config = config
        self.api_client = api_client
        self.db_manager = db_manager
        self.ticker_loader = ticker_loader
        self.logger = logging.getLogger(__name__)
        
        # Параметры торговли
        self.confidence_threshold = 0.7  # Высокий порог уверенности для шортов
        self.max_positions = 5  # Максимум позиций одновременно
        self.risk_per_trade = 0.02  # 2% риска на сделку
        self.short_bias = 1.5  # Предпочтение шортов
        
        # Данные нейросети
        self.neural_models = {}
        self.neural_scalers = {}
        self.neural_performance = {}
        
        # Кэш данных
        self.price_cache = {}
        self.signal_cache = {}
        self.last_analysis_time = {}
        
        # Инициализация
        self._load_neural_models()
        self._initialize_indicators()
        
    def _load_neural_models(self):
        """Загрузка обученных нейросетевых моделей"""
        try:
            models_path = Path("src/strategies/models")
            
            # Загружаем модели
            models_file = models_path / "adaptive_ml_models.pkl"
            scalers_file = models_path / "adaptive_ml_scalers.pkl"
            performance_file = models_path / "adaptive_ml_performance.json"
            
            if models_file.exists():
                import pickle
                with open(models_file, 'rb') as f:
                    self.neural_models = pickle.load(f)
                self.logger.info(f"Загружено {len(self.neural_models)} нейросетевых моделей")
            
            if scalers_file.exists():
                with open(scalers_file, 'rb') as f:
                    self.neural_scalers = pickle.load(f)
                self.logger.info(f"Загружено {len(self.neural_scalers)} скейлеров")
            
            if performance_file.exists():
                with open(performance_file, 'r') as f:
                    self.neural_performance = json.load(f)
                self.logger.info(f"Загружена статистика по {len(self.neural_performance)} символам")
                
        except Exception as e:
            self.logger.error(f"Ошибка загрузки нейросетевых моделей: {e}")
    
    def _initialize_indicators(self):
        """Инициализация технических индикаторов"""
        self.indicators = {
            'rsi_period': 14,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'bb_period': 20,
            'bb_std': 2,
            'volume_sma': 20
        }
    
    def analyze_market_comprehensive(self, symbol: str) -> Dict[str, Any]:
        """
        Комплексный анализ рынка для генерации торговых сигналов
        Фокус на шорты и высокую уверенность
        """
        try:
            # 1. Получаем данные тикеров
            ticker_data = self._get_ticker_data(symbol)
            if not ticker_data:
                return self._no_signal_result("Нет данных тикера")
            
            # 2. Получаем исторические данные
            historical_data = self._get_historical_data(symbol)
            if not historical_data:
                return self._no_signal_result("Нет исторических данных")
            
            # 3. Анализ нейросети
            neural_signal = self._analyze_neural_network(symbol, historical_data)
            
            # 4. Технический анализ
            technical_signal = self._analyze_technical_indicators(historical_data)
            
            # 5. Анализ объемов и ликвидности
            volume_signal = self._analyze_volume_patterns(historical_data, ticker_data)
            
            # 6. Анализ рыночных условий
            market_conditions = self._analyze_market_conditions(symbol, ticker_data)
            
            # 7. Комбинированный сигнал с фокусом на шорты
            final_signal = self._combine_signals_for_shorts(
                neural_signal, technical_signal, volume_signal, market_conditions
            )
            
            # 8. Проверка уверенности и риск-менеджмент
            if final_signal['confidence'] >= self.confidence_threshold:
                final_signal = self._apply_risk_management(symbol, final_signal)
            
            # Кэшируем результат
            self.signal_cache[symbol] = {
                'signal': final_signal,
                'timestamp': time.time()
            }
            
            return final_signal
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа рынка для {symbol}: {e}")
            return self._no_signal_result(f"Ошибка анализа: {str(e)}")
    
    def _get_ticker_data(self, symbol: str) -> Optional[Dict]:
        """Получение данных тикера"""
        try:
            ticker_data = self.ticker_loader.get_ticker_data(symbol)
            if ticker_data:
                # Кэшируем цену
                self.price_cache[symbol] = {
                    'price': float(ticker_data.get('lastPrice', 0)),
                    'volume': float(ticker_data.get('volume24h', 0)),
                    'change': float(ticker_data.get('price24hPcnt', 0)),
                    'timestamp': time.time()
                }
            return ticker_data
        except Exception as e:
            self.logger.error(f"Ошибка получения данных тикера {symbol}: {e}")
            return None
    
    def _get_historical_data(self, symbol: str) -> Optional[List[Dict]]:
        """Получение исторических данных"""
        try:
            # Получаем данные через API
            klines = self.api_client.get_kline(
                category='spot',
                symbol=symbol,
                interval='60',  # 1 час
                limit=200
            )
            
            if klines and 'result' in klines and 'list' in klines['result']:
                historical_data = []
                for kline in klines['result']['list']:
                    historical_data.append({
                        'timestamp': int(kline[0]),
                        'open': float(kline[1]),
                        'high': float(kline[2]),
                        'low': float(kline[3]),
                        'close': float(kline[4]),
                        'volume': float(kline[5])
                    })
                return historical_data[::-1]  # Обращаем порядок (от старых к новым)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка получения исторических данных {symbol}: {e}")
            return None
    
    def _analyze_neural_network(self, symbol: str, historical_data: List[Dict]) -> Dict[str, Any]:
        """Анализ с использованием нейросетевых моделей"""
        try:
            if symbol not in self.neural_models or not SKLEARN_AVAILABLE:
                return self._fallback_neural_analysis(historical_data)
            
            # Извлекаем признаки для нейросети
            features = self._extract_neural_features(historical_data)
            if not features:
                return self._fallback_neural_analysis(historical_data)
            
            # Нормализация
            if symbol in self.neural_scalers:
                features_scaled = self.neural_scalers[symbol].transform([features])[0]
            else:
                features_scaled = features
            
            # Предсказание
            model = self.neural_models[symbol]
            prediction_proba = model.predict_proba([features_scaled])[0]
            prediction_class = model.predict([features_scaled])[0]
            
            # Интерпретация результата с фокусом на шорты
            if prediction_class == 2:  # SELL
                signal = 'SELL'
                confidence = prediction_proba[2] * self.short_bias  # Усиливаем шорты
            elif prediction_class == 1:  # BUY
                signal = 'BUY'
                confidence = prediction_proba[1] * 0.7  # Ослабляем лонги
            else:  # HOLD
                signal = None
                confidence = 0.0
            
            # Учитываем производительность модели
            if symbol in self.neural_performance:
                perf = self.neural_performance[symbol]
                accuracy_boost = perf.get('accuracy', 0.5)
                confidence *= accuracy_boost
            
            return {
                'signal': signal,
                'confidence': min(confidence, 1.0),
                'source': 'neural_network',
                'model_accuracy': self.neural_performance.get(symbol, {}).get('accuracy', 0.5)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка нейросетевого анализа {symbol}: {e}")
            return self._fallback_neural_analysis(historical_data)
    
    def _fallback_neural_analysis(self, historical_data: List[Dict]) -> Dict[str, Any]:
        """Резервный анализ без нейросети"""
        if len(historical_data) < 20:
            return {'signal': None, 'confidence': 0.0, 'source': 'fallback'}
        
        # Простой анализ тренда
        closes = [d['close'] for d in historical_data[-20:]]
        short_ma = np.mean(closes[-5:])
        long_ma = np.mean(closes[-20:])
        
        price_change = (closes[-1] - closes[-10]) / closes[-10]
        
        # Фокус на шорты
        if short_ma < long_ma and price_change < -0.02:
            return {'signal': 'SELL', 'confidence': 0.6, 'source': 'fallback_short'}
        elif short_ma > long_ma and price_change > 0.03:
            return {'signal': 'BUY', 'confidence': 0.4, 'source': 'fallback_long'}
        
        return {'signal': None, 'confidence': 0.0, 'source': 'fallback'}
    
    def _extract_neural_features(self, historical_data: List[Dict]) -> Optional[List[float]]:
        """Извлечение признаков для нейросети"""
        try:
            if len(historical_data) < 50:
                return None
            
            closes = [d['close'] for d in historical_data]
            highs = [d['high'] for d in historical_data]
            lows = [d['low'] for d in historical_data]
            volumes = [d['volume'] for d in historical_data]
            
            features = []
            
            # Ценовые изменения
            features.append((closes[-1] - closes[-2]) / closes[-2])  # 1h change
            features.append((closes[-1] - closes[-24]) / closes[-24])  # 24h change
            features.append((closes[-1] - closes[-48]) / closes[-48])  # 48h change
            
            # RSI
            rsi = self._calculate_rsi(closes, 14)
            features.append(rsi[-1] if rsi else 50)
            
            # MACD
            macd_line, macd_signal, macd_hist = self._calculate_macd(closes)
            if macd_line and macd_signal:
                features.append(macd_line[-1])
                features.append(macd_signal[-1])
                features.append(macd_hist[-1])
            else:
                features.extend([0, 0, 0])
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(closes)
            if bb_upper and bb_lower:
                bb_position = (closes[-1] - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1])
                features.append(bb_position)
            else:
                features.append(0.5)
            
            # Объемы
            volume_sma = np.mean(volumes[-20:])
            volume_ratio = volumes[-1] / volume_sma if volume_sma > 0 else 1
            features.append(volume_ratio)
            
            # Волатильность
            returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
            volatility = np.std(returns[-20:]) if len(returns) >= 20 else 0
            features.append(volatility)
            
            return features
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения признаков: {e}")
            return None
    
    def _analyze_technical_indicators(self, historical_data: List[Dict]) -> Dict[str, Any]:
        """Технический анализ с фокусом на шорты"""
        try:
            closes = [d['close'] for d in historical_data]
            volumes = [d['volume'] for d in historical_data]
            
            if len(closes) < 30:
                return {'signal': None, 'confidence': 0.0, 'source': 'technical'}
            
            # RSI - ищем перекупленность для шортов
            rsi = self._calculate_rsi(closes, 14)
            rsi_signal = 0
            if rsi and rsi[-1] > 70:
                rsi_signal = 0.8  # Сильный сигнал на шорт
            elif rsi and rsi[-1] < 30:
                rsi_signal = -0.3  # Слабый сигнал на лонг
            
            # MACD - ищем медвежьи дивергенции
            macd_line, macd_signal_line, macd_hist = self._calculate_macd(closes)
            macd_signal = 0
            if macd_line and macd_signal_line:
                if macd_line[-1] < macd_signal_line[-1] and macd_hist[-1] < 0:
                    macd_signal = 0.6  # Медвежий сигнал
                elif macd_line[-1] > macd_signal_line[-1] and macd_hist[-1] > 0:
                    macd_signal = -0.4  # Бычий сигнал (ослабленный)
            
            # Bollinger Bands - ищем выходы за верхнюю границу
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(closes)
            bb_signal = 0
            if bb_upper and bb_lower:
                if closes[-1] > bb_upper[-1]:
                    bb_signal = 0.7  # Перекупленность - шорт
                elif closes[-1] < bb_lower[-1]:
                    bb_signal = -0.2  # Перепроданность - слабый лонг
            
            # Комбинированный технический сигнал
            total_signal = rsi_signal + macd_signal + bb_signal
            
            if total_signal > 1.0:
                return {'signal': 'SELL', 'confidence': min(total_signal / 2.0, 0.9), 'source': 'technical'}
            elif total_signal < -0.5:
                return {'signal': 'BUY', 'confidence': min(abs(total_signal) / 2.0, 0.6), 'source': 'technical'}
            
            return {'signal': None, 'confidence': 0.0, 'source': 'technical'}
            
        except Exception as e:
            self.logger.error(f"Ошибка технического анализа: {e}")
            return {'signal': None, 'confidence': 0.0, 'source': 'technical'}
    
    def _analyze_volume_patterns(self, historical_data: List[Dict], ticker_data: Dict) -> Dict[str, Any]:
        """Анализ объемов и паттернов ликвидности"""
        try:
            volumes = [d['volume'] for d in historical_data]
            closes = [d['close'] for d in historical_data]
            
            if len(volumes) < 20:
                return {'signal': None, 'confidence': 0.0, 'source': 'volume'}
            
            # Анализ объемов
            current_volume = volumes[-1]
            avg_volume = np.mean(volumes[-20:])
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Анализ цены и объема
            price_change = (closes[-1] - closes[-2]) / closes[-2]
            
            # Паттерны для шортов
            if volume_ratio > 1.5 and price_change > 0.02:
                # Высокий объем при росте - возможная вершина
                return {'signal': 'SELL', 'confidence': 0.7, 'source': 'volume_climax'}
            elif volume_ratio > 2.0 and price_change < -0.01:
                # Высокий объем при падении - продолжение тренда
                return {'signal': 'SELL', 'confidence': 0.6, 'source': 'volume_breakdown'}
            elif volume_ratio < 0.5 and price_change > 0.01:
                # Низкий объем при росте - слабый рост
                return {'signal': 'SELL', 'confidence': 0.5, 'source': 'volume_weak_rally'}
            
            return {'signal': None, 'confidence': 0.0, 'source': 'volume'}
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа объемов: {e}")
            return {'signal': None, 'confidence': 0.0, 'source': 'volume'}
    
    def _analyze_market_conditions(self, symbol: str, ticker_data: Dict) -> Dict[str, Any]:
        """Анализ общих рыночных условий"""
        try:
            # Анализ 24-часового изменения
            price_change_24h = float(ticker_data.get('price24hPcnt', 0))
            
            # Анализ спреда
            bid = float(ticker_data.get('bid1Price', 0))
            ask = float(ticker_data.get('ask1Price', 0))
            spread = (ask - bid) / bid if bid > 0 else 0
            
            # Условия для шортов
            market_signal = 0
            
            # Сильный рост - возможная коррекция
            if price_change_24h > 0.1:  # 10%+ рост
                market_signal += 0.6
            elif price_change_24h > 0.05:  # 5%+ рост
                market_signal += 0.3
            
            # Широкий спред - низкая ликвидность
            if spread > 0.001:  # 0.1%+ спред
                market_signal += 0.2
            
            # Высокая волатильность
            if abs(price_change_24h) > 0.05:
                market_signal += 0.1
            
            if market_signal > 0.5:
                return {'signal': 'SELL', 'confidence': min(market_signal, 0.8), 'source': 'market_conditions'}
            
            return {'signal': None, 'confidence': 0.0, 'source': 'market_conditions'}
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа рыночных условий: {e}")
            return {'signal': None, 'confidence': 0.0, 'source': 'market_conditions'}
    
    def _combine_signals_for_shorts(self, neural_signal: Dict, technical_signal: Dict, 
                                   volume_signal: Dict, market_signal: Dict) -> Dict[str, Any]:
        """Комбинирование сигналов с приоритетом шортов"""
        try:
            signals = [neural_signal, technical_signal, volume_signal, market_signal]
            
            # Весовые коэффициенты (приоритет нейросети и техническому анализу)
            weights = {
                'neural_network': 0.4,
                'fallback_short': 0.3,
                'fallback_long': 0.2,
                'technical': 0.3,
                'volume_climax': 0.2,
                'volume_breakdown': 0.25,
                'volume_weak_rally': 0.15,
                'volume': 0.1,
                'market_conditions': 0.2
            }
            
            sell_confidence = 0.0
            buy_confidence = 0.0
            total_weight = 0.0
            
            for signal in signals:
                source = signal.get('source', 'unknown')
                weight = weights.get(source, 0.1)
                confidence = signal.get('confidence', 0.0)
                
                if signal.get('signal') == 'SELL':
                    sell_confidence += confidence * weight
                elif signal.get('signal') == 'BUY':
                    buy_confidence += confidence * weight
                
                total_weight += weight
            
            # Нормализация
            if total_weight > 0:
                sell_confidence /= total_weight
                buy_confidence /= total_weight
            
            # Применяем bias к шортам
            sell_confidence *= self.short_bias
            
            # Определяем финальный сигнал
            if sell_confidence > buy_confidence and sell_confidence >= self.confidence_threshold:
                return {
                    'signal': 'SELL',
                    'confidence': min(sell_confidence, 1.0),
                    'source': 'combined_short_focused',
                    'components': {
                        'neural': neural_signal,
                        'technical': technical_signal,
                        'volume': volume_signal,
                        'market': market_signal
                    }
                }
            elif buy_confidence > sell_confidence and buy_confidence >= 0.8:  # Высокий порог для лонгов
                return {
                    'signal': 'BUY',
                    'confidence': min(buy_confidence, 0.7),  # Ограничиваем уверенность лонгов
                    'source': 'combined_long_limited',
                    'components': {
                        'neural': neural_signal,
                        'technical': technical_signal,
                        'volume': volume_signal,
                        'market': market_signal
                    }
                }
            
            return self._no_signal_result("Недостаточная уверенность")
            
        except Exception as e:
            self.logger.error(f"Ошибка комбинирования сигналов: {e}")
            return self._no_signal_result(f"Ошибка комбинирования: {str(e)}")
    
    def _apply_risk_management(self, symbol: str, signal: Dict) -> Dict[str, Any]:
        """Применение риск-менеджмента"""
        try:
            # Проверяем максимальное количество позиций
            current_positions = len([s for s in self.signal_cache.values() 
                                   if s.get('signal', {}).get('signal') in ['BUY', 'SELL']])
            
            if current_positions >= self.max_positions:
                return self._no_signal_result("Превышен лимит позиций")
            
            # Проверяем недавние сигналы по этому символу
            if symbol in self.last_analysis_time:
                time_since_last = time.time() - self.last_analysis_time[symbol]
                if time_since_last < 300:  # 5 минут
                    signal['confidence'] *= 0.8  # Снижаем уверенность
            
            # Обновляем время последнего анализа
            self.last_analysis_time[symbol] = time.time()
            
            # Рассчитываем размер позиции
            if symbol in self.price_cache:
                current_price = self.price_cache[symbol]['price']
                signal['position_size'] = self._calculate_position_size(current_price, signal['confidence'])
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Ошибка риск-менеджмента: {e}")
            return signal
    
    def _calculate_position_size(self, price: float, confidence: float) -> float:
        """Расчет размера позиции"""
        try:
            # Базовый размер позиции на основе риска
            base_size = self.risk_per_trade * confidence
            
            # Корректировка на цену (для дорогих активов меньше размер)
            if price > 1000:
                base_size *= 0.5
            elif price > 100:
                base_size *= 0.7
            
            return min(base_size, 0.05)  # Максимум 5% на позицию
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета размера позиции: {e}")
            return 0.01
    
    def get_top_trading_opportunities(self, symbols: List[str], limit: int = 5) -> List[Dict]:
        """Получение топ торговых возможностей"""
        try:
            opportunities = []
            
            for symbol in symbols:
                signal = self.analyze_market_comprehensive(symbol)
                if signal.get('signal') and signal.get('confidence', 0) >= self.confidence_threshold:
                    opportunities.append({
                        'symbol': symbol,
                        'signal': signal['signal'],
                        'confidence': signal['confidence'],
                        'source': signal.get('source', 'unknown'),
                        'timestamp': time.time()
                    })
            
            # Сортируем по уверенности (приоритет шортам)
            opportunities.sort(key=lambda x: (
                x['confidence'] * (1.5 if x['signal'] == 'SELL' else 1.0)
            ), reverse=True)
            
            return opportunities[:limit]
            
        except Exception as e:
            self.logger.error(f"Ошибка получения торговых возможностей: {e}")
            return []
    
    def _no_signal_result(self, reason: str) -> Dict[str, Any]:
        """Результат без сигнала"""
        return {
            'signal': None,
            'confidence': 0.0,
            'reason': reason,
            'timestamp': time.time()
        }
    
    # Технические индикаторы
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """Расчет RSI"""
        try:
            if len(prices) < period + 1:
                return []
            
            deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]
            
            avg_gain = np.mean(gains[:period])
            avg_loss = np.mean(losses[:period])
            
            rsi_values = []
            
            for i in range(period, len(deltas)):
                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                
                rsi_values.append(rsi)
                
                # Обновляем средние
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            return rsi_values
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета RSI: {e}")
            return []
    
    def _calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
        """Расчет MACD"""
        try:
            if len(prices) < slow + signal:
                return [], [], []
            
            # EMA
            def ema(data, period):
                alpha = 2 / (period + 1)
                ema_values = [data[0]]
                for price in data[1:]:
                    ema_values.append(alpha * price + (1 - alpha) * ema_values[-1])
                return ema_values
            
            ema_fast = ema(prices, fast)
            ema_slow = ema(prices, slow)
            
            # MACD line
            macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]
            
            # Signal line
            macd_signal = ema(macd_line, signal)
            
            # Histogram
            macd_hist = [macd_line[i] - macd_signal[i] for i in range(len(macd_signal))]
            
            return macd_line, macd_signal, macd_hist
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета MACD: {e}")
            return [], [], []
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2) -> Tuple[List[float], List[float], List[float]]:
        """Расчет полос Боллинджера"""
        try:
            if len(prices) < period:
                return [], [], []
            
            bb_upper = []
            bb_middle = []
            bb_lower = []
            
            for i in range(period - 1, len(prices)):
                window = prices[i - period + 1:i + 1]
                sma = np.mean(window)
                std = np.std(window)
                
                bb_middle.append(sma)
                bb_upper.append(sma + std_dev * std)
                bb_lower.append(sma - std_dev * std)
            
            return bb_upper, bb_middle, bb_lower
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета Bollinger Bands: {e}")
            return [], [], []