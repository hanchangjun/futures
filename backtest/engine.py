from typing import List, Callable, Optional
from backtest.event import MarketEvent, SignalEvent, FillEvent
from backtest.broker import BacktestBroker
from portfolio.manager import PortfolioManager
from risk.manager import RiskManager

class BacktestEngine:
    def __init__(self, 
                 portfolio: PortfolioManager, 
                 risk: RiskManager, 
                 broker: BacktestBroker):
        self.portfolio = portfolio
        self.risk = risk
        self.broker = broker
        self.history = []
        self.equity_curve = []  # List of {dt, equity}
        self.trades = []        # List of trades (fills for now)
        self.active_sl = {}     # symbol -> {price, direction}
        self.active_tp = {}     # symbol -> {price, direction}
        self.logs = []          # Capture logs for UI display

    def log(self, message: str):
        self.logs.append(message)
        print(message)

    def run(self, bars: List, strategy_func: Callable[[List], Optional[SignalEvent]], symbol: str):
        """
        Run the backtest loop.
        :param bars: List of PriceBar objects (time-sorted)
        :param strategy_func: Function that takes list of bars and returns SignalEvent or None
        :param symbol: Symbol name
        """
        self.log(f"Starting Backtest for {symbol} with {len(bars)} bars...")
        
        for bar in bars:
            # 1. Create Market Event
            market_event = MarketEvent(bar, symbol)
            
            # 2. Broker Execution (Match pending orders at Open of this bar)
            fills = self.broker.match_orders(market_event)
            for fill in fills:
                # Capture PnL change
                prev_pnl = self.portfolio.realized_pnl
                self.portfolio.update_fill(fill)
                trade_pnl = self.portfolio.realized_pnl - prev_pnl
                
                self.trades.append({
                    "dt": fill.dt,
                    "symbol": fill.symbol,
                    "direction": fill.direction,
                    "quantity": fill.quantity,
                    "price": fill.fill_price,
                    "commission": fill.commission,
                    "pnl": trade_pnl,
                    "type": "SIGNAL"
                })
                self.log(f"[{fill.dt}] FILL: {fill.direction} {fill.quantity} @ {fill.fill_price:.2f} (Comm: {fill.commission:.2f})")

            # 3. Check Stop Loss (Intra-bar)
            if symbol in self.active_sl:
                sl_info = self.active_sl[symbol]
                sl_price = sl_info['price']
                direction = sl_info['direction']
                
                triggered = False
                fill_price = sl_price
                
                # Check High/Low for SL trigger
                if direction == 'LONG' and bar.low <= sl_price:
                    triggered = True
                    if bar.open < sl_price: # Gap down
                        fill_price = bar.open
                elif direction == 'SHORT' and bar.high >= sl_price:
                    triggered = True
                    if bar.open > sl_price: # Gap up
                        fill_price = bar.open
                        
                if triggered:
                    qty = self.portfolio.positions[symbol]
                    # Only close if we actually have a position matching the SL direction
                    # (Simple check: if Long SL triggered, must have positive qty)
                    if (direction == 'LONG' and qty > 0) or (direction == 'SHORT' and qty < 0):
                        self.log(f"[{bar.date}] 🛑 STOP LOSS TRIGGERED at {fill_price:.2f} (SL: {sl_price})")
                        
                        fill_dir = 'SELL' if qty > 0 else 'BUY'
                        commission = fill_price * abs(qty) * self.broker.commission_rate
                        
                        fill = FillEvent(
                            symbol=symbol,
                            dt=bar.date,
                            quantity=abs(qty),
                            direction=fill_dir,
                            fill_price=fill_price,
                            commission=commission
                        )
                        
                        # Capture PnL change
                        prev_pnl = self.portfolio.realized_pnl
                        self.portfolio.update_fill(fill)
                        trade_pnl = self.portfolio.realized_pnl - prev_pnl
                        
                        self.trades.append({
                            "dt": bar.date, 
                            "symbol": symbol, 
                            "direction": fill_dir, 
                            "quantity": abs(qty), 
                            "price": fill_price, 
                            "commission": commission,
                            "pnl": trade_pnl,
                            "type": "STOP_LOSS"
                        })
                        
                        # Clear SL, TP and Pending Orders
                        del self.active_sl[symbol]
                        if symbol in self.active_tp:
                            del self.active_tp[symbol]
                        self.broker.pending_orders = [o for o in self.broker.pending_orders if o.symbol != symbol]
                    else:
                        # SL exists but no position? Clear it.
                        del self.active_sl[symbol]
                        if symbol in self.active_tp:
                            del self.active_tp[symbol]

            # 3.1 Check Take Profit (Intra-bar)
            if symbol in self.active_tp:
                tp_info = self.active_tp[symbol]
                tp_price = tp_info['price']
                direction = tp_info['direction']
                
                triggered = False
                fill_price = tp_price
                
                # Check High/Low for TP trigger
                # LONG TP: High >= TP
                # SHORT TP: Low <= TP
                if direction == 'LONG' and bar.high >= tp_price:
                    triggered = True
                    if bar.open > tp_price: # Gap up
                        fill_price = bar.open
                elif direction == 'SHORT' and bar.low <= tp_price:
                    triggered = True
                    if bar.open < tp_price: # Gap down
                        fill_price = bar.open
                        
                if triggered:
                    qty = self.portfolio.positions[symbol]
                    if (direction == 'LONG' and qty > 0) or (direction == 'SHORT' and qty < 0):
                        self.log(f"[{bar.date}] 💰 TAKE PROFIT TRIGGERED at {fill_price:.2f} (TP: {tp_price})")
                        
                        fill_dir = 'SELL' if qty > 0 else 'BUY'
                        commission = fill_price * abs(qty) * self.broker.commission_rate
                        
                        fill = FillEvent(
                            symbol=symbol,
                            dt=bar.date,
                            quantity=abs(qty),
                            direction=fill_dir,
                            fill_price=fill_price,
                            commission=commission
                        )
                        
                        # Capture PnL change
                        prev_pnl = self.portfolio.realized_pnl
                        self.portfolio.update_fill(fill)
                        trade_pnl = self.portfolio.realized_pnl - prev_pnl
                        
                        self.trades.append({
                            "dt": bar.date, 
                            "symbol": symbol, 
                            "direction": fill_dir, 
                            "quantity": abs(qty), 
                            "price": fill_price, 
                            "commission": commission,
                            "pnl": trade_pnl,
                            "type": "TAKE_PROFIT"
                        })
                        
                        # Clear SL, TP and Pending Orders
                        del self.active_tp[symbol]
                        if symbol in self.active_sl:
                            del self.active_sl[symbol]
                        self.broker.pending_orders = [o for o in self.broker.pending_orders if o.symbol != symbol]
                    else:
                        del self.active_tp[symbol]
                        if symbol in self.active_sl:
                            del self.active_sl[symbol]
            
            # 4. Update Portfolio MTM (at Close)
            self.portfolio.update_market(symbol, bar.close)
            self.equity_curve.append({"dt": bar.date, "equity": self.portfolio.equity})
            
            # 5. Strategy Execution
            # Append current bar to history available for strategy
            self.history.append(bar)
            
            # Run strategy (simulate "on close" signal generation)
            # Pass a window to speed up if strategy supports it, or full history
            # Assuming strategy needs at least some bars
            if len(self.history) > 100: 
                signal = strategy_func(self.history, symbol)
                
                if signal:
                    self.log(f"[{signal.dt}] SIGNAL: {signal.signal_type} @ {signal.price}")
                    
                    # Update SL if provided
                    if signal.sl:
                        # Infer direction from signal type
                        # If buying (Long), SL is below. If selling (Short), SL is above.
                        # Signal types: 1B, 2B, 3B, LONG -> Long
                        # Signal types: 1S, 2S, 3S, SHORT -> Short
                        sl_dir = 'LONG' if 'B' in signal.signal_type or 'LONG' in signal.signal_type else 'SHORT'
                        self.active_sl[symbol] = {'price': signal.sl, 'direction': sl_dir}
                        self.log(f"[{signal.dt}] SET SL: {signal.sl} ({sl_dir})")
                    
                    if signal.tp:
                        tp_dir = 'LONG' if 'B' in signal.signal_type or 'LONG' in signal.signal_type else 'SHORT'
                        self.active_tp[symbol] = {'price': signal.tp, 'direction': tp_dir}
                        self.log(f"[{signal.dt}] SET TP: {signal.tp:.2f} ({tp_dir})")
                        
                    # 5. Generate Order
                    order = self.portfolio.generate_order(signal)
                    
                    if order:
                        # 6. Risk Check
                        if self.risk.check_order(order, self.portfolio):
                            # 7. Submit to Broker (will be filled at NEXT bar's Open)
                            self.broker.submit_order(order)
                        else:
                            self.log(f"[{bar.date}] RISK REJECT: {order.direction} {order.quantity}")
                            
        self.log("Backtest Completed.")
        self.log(f"Final Equity: {self.portfolio.equity:.2f}")
        self.log(f"Realized PnL: {self.portfolio.realized_pnl:.2f}")
        self.log(f"Positions: {dict(self.portfolio.positions)}")
