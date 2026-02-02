import time
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from datafeed import get_bars, PriceBar
from strategy.rebar_strategy import RebarOptimizedChanSystem
from strategy.notification import WeChatNotifier
from strategy.chan_core import Signal
from strategy.position_manager import PositionManager

logger = logging.getLogger(__name__)

class RealTimeTradingSystem:
    """
    实时交易系统 (Real-Time Trading System)
    
    Responsibilities:
    1. Fetch market data periodically (every 5 mins).
    2. Analyze data using RebarOptimizedChanSystem (30 min cycle).
    3. Generate signals and send notifications via WeChat (replacing order execution).
    """
    
    def __init__(
        self, 
        symbol: str, 
        webhook_url: str = None,
        data_source: str = "tq",
        strategy_config: Dict[str, Any] = None,
        notifier: WeChatNotifier = None
    ):
        self.symbol = symbol
        self.period = "30m" # Fixed 30 minute cycle as requested
        self.data_source = data_source
        self.update_interval = 300 # 5 minutes update
        
        # Initialize components
        self.notifier = notifier or WeChatNotifier(webhook_url=webhook_url)
        self.strategy = RebarOptimizedChanSystem(config=strategy_config or {})
        self.position_manager = PositionManager(symbol)
        
        self.last_signal_time = None
        self.running = False
        self._thread = None

    def start(self, background: bool = False):
        """Start the trading loop"""
        if self.running:
            logger.warning("System is already running.")
            return

        self.running = True
        logger.info(f"Starting RealTimeTradingSystem for {self.symbol} [{self.period}]")
        
        if background:
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
        else:
            self._run_loop()

    def stop(self):
        """Stop the trading loop"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("RealTimeTradingSystem stopped.")

    def _run_loop(self):
        while self.running:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
            
            # Wait for next update
            # We sleep in small chunks to allow quick stopping
            for _ in range(self.update_interval):
                if not self.running:
                    break
                time.sleep(1)

    def run_once(self):
        """Execute one cycle of data fetch and analysis"""
        logger.debug(f"Fetching data for {self.symbol}...")
        
        # 1. Fetch Data
        # We need enough bars for Chan theory logic (e.g., 2000 bars)
        bars, msg = get_bars(
            source=self.data_source, 
            symbol=self.symbol, 
            period=self.period, 
            count=2000
        )
        
        if not bars:
            logger.warning(f"No data retrieved for {self.symbol}: {msg}")
            return
            
        current_bar = bars[-1]
        current_price = current_bar.close
        current_time = current_bar.date or datetime.now()

        # 0. Check Positions (TP/SL)
        events = self.position_manager.check_conditions(current_price, current_time)
        for event in events:
            self._send_position_event_notification(event)

        # 2. Run Strategy Analysis
        # RebarOptimizedChanSystem.analyze expects raw bars
        self.strategy.analyze(bars)
        
        # 3. Get Signals
        # Access '买卖点记录' from the strategy
        signals = getattr(self.strategy, '买卖点记录', [])
        
        if not signals:
            return

        # 4. Check for New Signal
        latest_signal = signals[-1]
        
        # Deduplication: Check if we already processed this signal
        if self.last_signal_time and latest_signal.time <= self.last_signal_time:
            return
            
        # Update last processed signal time
        self.last_signal_time = latest_signal.time
        
        # 5. Process Signal (Notify instead of Execute)
        self._send_notification(latest_signal, current_price)

    def _send_position_event_notification(self, event: Dict[str, Any]):
        """Send TP/SL notification"""
        emoji = "💰" if event['pnl'] > 0 else "💸"
        content = (
            f"{emoji} **平仓通知**\n"
            f"-----------------------\n"
            f"类型: {event['type']} (Stop/Limit)\n"
            f"方向: {event['direction']}\n"
            f"价格: {event['price']}\n"
            f"盈亏: {event['pnl']:.2f}\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        self.notifier.send_text(content)

    def _send_notification(self, signal: Signal, current_price: float):
        """Send signal notification via WeChat"""
        # Determine direction
        direction = "BUY" if "B" in signal.type else "SELL"
        
        # Basic Risk Management Logic for Notification (Example)
        # In a real system, this would come from RiskManager
        atr = 50.0 # Placeholder or calculate from bars if available
        
        stop_loss = 0.0
        take_profit = 0.0
        
        if direction == "BUY":
            stop_loss = current_price - 1.2 * atr
            take_profit = current_price + 2.0 * atr
        else:
            stop_loss = current_price + 1.2 * atr
            take_profit = current_price - 2.0 * atr

        order_info = {
            "signal": signal,
            "type": direction,
            "price": current_price,
            "size": 1, # Default size
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2)
        }
        
        # Record Position
        self.position_manager.open_position(signal, order_info['stop_loss'], order_info['take_profit'])
        
        self.notifier.send_order_notification(order_info)
