from collections import defaultdict
from typing import Dict, Optional
from backtest.event import SignalEvent, OrderEvent, FillEvent

class PortfolioManager:
    def __init__(self, initial_capital=100000.0, default_qty=1):
        self.initial_capital = initial_capital
        self.current_cash = initial_capital
        self.default_qty = default_qty
        
        # Positions: symbol -> quantity (positive for Long, negative for Short)
        self.positions: Dict[str, int] = defaultdict(int)
        
        # Holdings: symbol -> current market value
        self.holdings: Dict[str, float] = defaultdict(float)
        
        # Realized PnL
        self.realized_pnl = 0.0
        
        self.equity = initial_capital
        
        # Track last price for MTM
        self.last_prices: Dict[str, float] = {}
        
        # Track Average Cost for PnL calculation
        self.avg_prices: Dict[str, float] = defaultdict(float)

    def update_market(self, symbol: str, price: float):
        """Update market value of positions based on new price"""
        self.last_prices[symbol] = price
        if symbol in self.positions:
            qty = self.positions[symbol]
            # Market Value = Qty * Price
            # For Short (negative qty), Market Value is negative (liability)
            self.holdings[symbol] = qty * price
            
        self._update_equity()

    def update_fill(self, fill: FillEvent):
        """Update portfolio state upon trade execution"""
        cost = fill.fill_price * fill.quantity
        commission = fill.commission
        
        symbol = fill.symbol
        qty = fill.quantity
        price = fill.fill_price
        direction = fill.direction
        
        current_pos = self.positions[symbol]
        
        # 1. Update Realized PnL and Avg Cost
        if direction == 'BUY':
            if current_pos >= 0:
                # Adding to Long (or opening)
                total_val = (current_pos * self.avg_prices[symbol]) + (qty * price)
                new_pos_val = current_pos + qty
                self.avg_prices[symbol] = total_val / new_pos_val if new_pos_val != 0 else 0
            else:
                # Closing Short
                close_qty = min(abs(current_pos), qty)
                # PnL for Short = (Entry - Exit) * Qty
                pnl = (self.avg_prices[symbol] - price) * close_qty
                self.realized_pnl += pnl
                
                # Handle Reversal (Flip to Long)
                remaining = qty - close_qty
                if remaining > 0:
                    self.avg_prices[symbol] = price
                    
        elif direction == 'SELL':
            if current_pos <= 0:
                # Adding to Short (or opening)
                total_val = (abs(current_pos) * self.avg_prices[symbol]) + (qty * price)
                new_pos_val = abs(current_pos) + qty
                self.avg_prices[symbol] = total_val / new_pos_val if new_pos_val != 0 else 0
            else:
                # Closing Long
                close_qty = min(current_pos, qty)
                # PnL for Long = (Exit - Entry) * Qty
                pnl = (price - self.avg_prices[symbol]) * close_qty
                self.realized_pnl += pnl
                
                # Handle Reversal (Flip to Short)
                remaining = qty - close_qty
                if remaining > 0:
                    self.avg_prices[symbol] = price

        # Deduct Commission from Realized PnL (optional, but cleaner)
        self.realized_pnl -= commission

        # 2. Update Cash and Positions
        if fill.direction == 'BUY':
            self.current_cash -= (cost + commission)
            self.positions[fill.symbol] += fill.quantity
        elif fill.direction == 'SELL':
            self.current_cash += (cost - commission)
            self.positions[fill.symbol] -= fill.quantity
            
        # Update Holdings with fill price (temporary, will be updated by next market tick)
        self.update_market(fill.symbol, fill.fill_price)

    def _update_equity(self):
        """Recalculate total equity"""
        market_value = sum(self.holdings.values())
        self.equity = self.current_cash + market_value

    def generate_order(self, signal: SignalEvent) -> Optional[OrderEvent]:
        """
        Convert Signal to Order.
        Simple logic: 
        - LONG signal -> Buy 1 unit if flat or short.
        - SHORT signal -> Sell 1 unit if flat or long.
        - EXIT signal -> Close position.
        """
        symbol = signal.symbol
        curr_pos = self.positions[symbol]
        qty = self.default_qty
        
        order = None
        
        if signal.signal_type == 'LONG' or signal.signal_type == '1B' or signal.signal_type == '2B' or signal.signal_type == '3B':
            # Entry Long
            # If already long, maybe add? For now, flat or reverse.
            if curr_pos <= 0:
                # If short, buy 2*qty to reverse? Or just close?
                # Simple mode: target position = +qty
                buy_qty = qty - curr_pos 
                if buy_qty > 0:
                    order = OrderEvent(symbol, 'MKT', buy_qty, 'BUY')
                    
        elif signal.signal_type == 'SHORT' or signal.signal_type == '1S' or signal.signal_type == '2S' or signal.signal_type == '3S':
            # Entry Short
            if curr_pos >= 0:
                sell_qty = curr_pos + qty
                if sell_qty > 0:
                    order = OrderEvent(symbol, 'MKT', sell_qty, 'SELL')
                    
        elif signal.signal_type == 'EXIT':
            if curr_pos > 0:
                order = OrderEvent(symbol, 'MKT', abs(curr_pos), 'SELL')
            elif curr_pos < 0:
                order = OrderEvent(symbol, 'MKT', abs(curr_pos), 'BUY')
                
        return order
