import pandas as pd
import numpy as np
from typing import List, Dict, Any, Union, Optional
from datetime import datetime
import logging
from dataclasses import asdict

from strategy.chan_core import Signal
from datafeed.base import PriceBar

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics_history: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []
        
    def monitor_signals(self, signals: List[Signal], market_data: Union[pd.DataFrame, List[PriceBar]]):
        """
        监控信号性能
        :param signals: 信号列表
        :param market_data: 市场数据 (DataFrame or List[PriceBar])
        """
        # Ensure market_data is DataFrame
        if isinstance(market_data, list):
            market_data = self._convert_bars_to_df(market_data)
            
        for signal in signals:
            # 跟踪信号后续表现
            try:
                performance = self.track_signal_performance(signal, market_data)
                if performance is None:
                    continue
                    
                # 更新历史记录
                # Check duplicates based on signal timestamp and type to avoid re-adding
                if not any(m['timestamp'] == performance['timestamp'] and m['signal_type'] == performance['signal_type'] for m in self.metrics_history):
                    self.metrics_history.append(performance)
                
                # 检查异常
                if self.is_abnormal_performance(performance):
                    self.trigger_alert(signal, performance)
            except Exception as e:
                logger.error(f"Error tracking signal {signal}: {e}")
                
            # 实时优化参数
            if len(self.metrics_history) > 100:  # 有足够数据后
                self.optimize_parameters()

    def track_signal_performance(self, signal: Signal, market_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """跟踪信号表现"""
        entry_price = signal.price
        entry_time = signal.time
        
        # 获取后续价格
        future_data = self.get_future_data(entry_time, market_data, periods=20)
        
        if future_data.empty:
            return None

        # 计算最大有利变动 (MFE)
        max_favorable = self.calculate_max_favorable(entry_price, future_data, signal.type)
        
        # 计算最大不利变动 (MAE)
        max_adverse = self.calculate_max_adverse(entry_price, future_data, signal.type)
        
        # 计算最终收益（如果持有到20期后）
        final_return = self.calculate_final_return(entry_price, future_data.iloc[-1], signal.type)
        
        performance = {
            'signal_type': signal.type,
            'score': getattr(signal, 'score', 0),
            'entry_price': entry_price,
            'max_favorable': max_favorable,
            'max_adverse': max_adverse,
            'final_return': final_return,
            'timestamp': entry_time
        }
        
        return performance

    def get_future_data(self, entry_time: datetime, market_data: pd.DataFrame, periods: int = 20) -> pd.DataFrame:
        """获取信号之后的K线数据"""
        # Assuming market_data has 'date' or index is datetime
        # Check column name for date
        date_col = 'date' if 'date' in market_data.columns else None
        
        if date_col:
            mask = market_data[date_col] > entry_time
            future = market_data[mask]
        else:
            # Fallback to index if datetime index
            if isinstance(market_data.index, pd.DatetimeIndex):
                future = market_data[market_data.index > entry_time]
            else:
                return pd.DataFrame()
                
        return future.head(periods)

    def calculate_max_favorable(self, entry_price: float, data: pd.DataFrame, signal_type: str) -> float:
        """计算最大有利变动 (MFE)"""
        if 'B' in signal_type: # Long
            # High - Entry
            return data['high'].max() - entry_price
        else: # Short
            # Entry - Low
            return entry_price - data['low'].min()

    def calculate_max_adverse(self, entry_price: float, data: pd.DataFrame, signal_type: str) -> float:
        """计算最大不利变动 (MAE)"""
        if 'B' in signal_type: # Long
            # Entry - Low
            val = entry_price - data['low'].min()
            return val if val > 0 else 0 # Should be positive representing loss magnitude
        else: # Short
            # High - Entry
            val = data['high'].max() - entry_price
            return val if val > 0 else 0

    def calculate_final_return(self, entry_price: float, last_bar: pd.Series, signal_type: str) -> float:
        """计算最终收益"""
        close = last_bar['close']
        if 'B' in signal_type:
            return close - entry_price
        else:
            return entry_price - close

    def is_abnormal_performance(self, performance: Dict[str, Any]) -> bool:
        """检查表现是否异常"""
        # Example: MAE is very large (e.g. > 100 points or huge ratio vs MFE)
        # Here we use a simple absolute threshold or ratio
        mae = performance['max_adverse']
        mfe = performance['max_favorable']
        
        # If Loss > 2 * Profit (and Profit is not zero), or absolute Loss is huge
        if mae > 100: # Placeholder threshold
            return True
        return False

    def trigger_alert(self, signal: Signal, performance: Dict[str, Any]):
        """触发报警"""
        alert = {
            'time': datetime.now(),
            'signal_id': f"{signal.type}_{signal.time}",
            'message': f"Abnormal performance detected for {signal.type} at {signal.time}",
            'detail': performance
        }
        self.alerts.append(alert)
        logger.warning(f"Performance Alert: {alert['message']} | MAE: {performance['max_adverse']}")

    def optimize_parameters(self) -> Dict[str, Dict[str, Any]]:
        """基于历史表现优化参数"""
        if not self.metrics_history:
            return {}
            
        # 按信号类型分析
        signal_types = set([m['signal_type'] for m in self.metrics_history])
        
        optimized_params = {}
        
        for stype in signal_types:
            type_metrics = [m for m in self.metrics_history if m['signal_type'] == stype]
            
            if len(type_metrics) < 20:  # 样本不足
                continue
                
            # 分析胜率 (Win if final_return > 0)
            win_rate = self.calculate_win_rate(type_metrics)
            
            # 分析盈亏比
            profit_loss_ratio = self.calculate_profit_loss_ratio(type_metrics)
            
            # 分析最佳分数阈值
            best_score_threshold = self.find_best_score_threshold(type_metrics)
            
            # 优化参数
            if win_rate < 0.5 or profit_loss_ratio < 1.5:
                # 表现不佳，需要调整参数
                optimized_params[stype] = {
                    'min_score': max(70, best_score_threshold),  # 提高分数阈值
                    'adjustment_factor': 0.8  # 降低仓位
                }
            else:
                # 表现良好，可适当放松
                optimized_params[stype] = {
                    'min_score': min(60, best_score_threshold),
                    'adjustment_factor': 1.0
                }
        
        return optimized_params

    def calculate_win_rate(self, metrics: List[Dict[str, Any]]) -> float:
        """计算胜率"""
        if not metrics:
            return 0.0
        wins = sum(1 for m in metrics if m['final_return'] > 0)
        return wins / len(metrics)

    def calculate_profit_loss_ratio(self, metrics: List[Dict[str, Any]]) -> float:
        """计算盈亏比"""
        wins = [m['final_return'] for m in metrics if m['final_return'] > 0]
        losses = [abs(m['final_return']) for m in metrics if m['final_return'] <= 0]
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        
        if avg_loss == 0:
            return float('inf') if avg_win > 0 else 0
        return avg_win / avg_loss

    def find_best_score_threshold(self, metrics: List[Dict[str, Any]]) -> float:
        """寻找最佳分数阈值"""
        # Grid search score thresholds
        scores = [m['score'] for m in metrics]
        if not scores:
            return 60.0
            
        min_s, max_s = min(scores), max(scores)
        best_threshold = 60.0
        best_metric = -float('inf')
        
        # Test thresholds from min to max with step 5
        for threshold in range(int(min_s), int(max_s) + 1, 5):
            filtered = [m for m in metrics if m['score'] >= threshold]
            if len(filtered) < 10: # Minimum sample size
                continue
                
            wr = self.calculate_win_rate(filtered)
            pl = self.calculate_profit_loss_ratio(filtered)
            
            # Simple combined metric: WinRate * P/L
            # Or expectation: WR * AvgWin - (1-WR) * AvgLoss
            # Let's use expectation per trade approximation
            expectation = wr * pl # roughly proportional to expectancy if avg loss is constant unit
            
            if expectation > best_metric:
                best_metric = expectation
                best_threshold = threshold
                
        return float(best_threshold)

    def _convert_bars_to_df(self, bars: List[PriceBar]) -> pd.DataFrame:
        """Convert list of PriceBar to DataFrame"""
        data = [asdict(b) for b in bars]
        df = pd.DataFrame(data)
        # Ensure date is datetime
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        return df
