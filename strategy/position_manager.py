import logging
from datetime import datetime
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from database.models import TradeRecord
from database.connection import SessionLocal

logger = logging.getLogger(__name__)

class PositionManager:
    """
    管理实盘/模拟持仓，负责止盈止损检查和状态持久化
    """
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.db: Session = SessionLocal()
        self.active_trades: List[TradeRecord] = []
        self._load_active_trades()

    def _load_active_trades(self):
        """从数据库加载当前活跃持仓"""
        try:
            self.active_trades = self.db.query(TradeRecord).filter(
                TradeRecord.symbol == self.symbol,
                TradeRecord.status == "OPEN"
            ).all()
            logger.info(f"Loaded {len(self.active_trades)} active trades for {self.symbol}")
        except Exception as e:
            logger.error(f"Failed to load active trades: {e}")

    def open_position(self, signal, sl: float, tp: float):
        """开仓"""
        # 简单风控：同一方向不重复开仓
        for trade in self.active_trades:
            if trade.direction == signal.type: # signal.type like "1B" (Buy) or "1S" (Sell)
                logger.info(f"Position already exists for {signal.type}, skipping.")
                return None
                
        direction = "BUY" if "B" in signal.type or "LONG" in signal.type else "SELL"
        
        new_trade = TradeRecord(
            symbol=self.symbol,
            direction=direction,
            status="OPEN",
            entry_price=signal.price,
            entry_time=signal.time,
            entry_signal_id=f"{signal.type}_{signal.time}",
            stop_loss=sl,
            take_profit=tp
        )
        
        try:
            self.db.add(new_trade)
            self.db.commit()
            self.db.refresh(new_trade)
            self.active_trades.append(new_trade)
            logger.info(f"Opened position: {direction} @ {signal.price} (SL: {sl}, TP: {tp})")
            return new_trade
        except Exception as e:
            logger.error(f"Failed to open position: {e}")
            self.db.rollback()
            return None

    def check_conditions(self, current_price: float, current_time: datetime) -> List[Dict]:
        """
        检查止盈止损
        返回触发的事件列表
        """
        events = []
        closed_indices = []
        
        for i, trade in enumerate(self.active_trades):
            reason = None
            
            if trade.direction == "BUY":
                if current_price <= trade.stop_loss:
                    reason = "SL"
                elif trade.take_profit and current_price >= trade.take_profit:
                    reason = "TP"
            elif trade.direction == "SELL":
                if current_price >= trade.stop_loss:
                    reason = "SL"
                elif trade.take_profit and current_price <= trade.take_profit:
                    reason = "TP"
            
            if reason:
                self._close_trade(trade, current_price, current_time, reason)
                closed_indices.append(i)
                events.append({
                    "trade_id": trade.id,
                    "type": reason,
                    "price": current_price,
                    "direction": trade.direction,
                    "pnl": trade.pnl
                })
        
        # Remove closed trades from memory
        for i in sorted(closed_indices, reverse=True):
            self.active_trades.pop(i)
            
        return events

    def _close_trade(self, trade: TradeRecord, price: float, time: datetime, reason: str):
        """平仓逻辑"""
        trade.exit_price = price
        trade.exit_time = time
        trade.exit_reason = reason
        trade.status = "CLOSED"
        
        # Calculate PnL
        if trade.direction == "BUY":
            trade.pnl = price - trade.entry_price
        else:
            trade.pnl = trade.entry_price - price
            
        # Calculate ROI (Simple)
        if trade.entry_price:
            trade.roi = (trade.pnl / trade.entry_price) * 100
            
        try:
            self.db.commit()
            logger.info(f"Closed trade {trade.id}: {reason} @ {price}, PnL: {trade.pnl:.2f}")
        except Exception as e:
            logger.error(f"Failed to close trade: {e}")
            self.db.rollback()

    def close(self):
        self.db.close()
