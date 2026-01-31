from typing import List, Any
from backtest.event import OrderEvent, FillEvent, MarketEvent

class BacktestBroker:
    def __init__(self, commission_rate=0.0001, slippage=0.0):
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.pending_orders: List[OrderEvent] = []
        
    def submit_order(self, order: OrderEvent):
        self.pending_orders.append(order)
        
    def match_orders(self, market_event: MarketEvent) -> List[FillEvent]:
        """
        Match pending orders against the new market bar.
        Assume Market Order fills at Open.
        """
        bar = market_event.bar
        symbol = market_event.symbol
        dt = bar.date
        open_price = bar.open
        
        fills = []
        still_pending = []
        
        for order in self.pending_orders:
            if order.symbol != symbol:
                still_pending.append(order)
                continue
                
            # Execute Market Order
            if order.order_type == 'MKT':
                # Apply slippage
                fill_price = open_price
                if order.direction == 'BUY':
                    fill_price += self.slippage
                else:
                    fill_price -= self.slippage
                    
                commission = fill_price * order.quantity * self.commission_rate
                
                fill = FillEvent(
                    symbol=symbol,
                    dt=dt,
                    quantity=order.quantity,
                    direction=order.direction,
                    fill_price=fill_price,
                    commission=commission
                )
                fills.append(fill)
            else:
                # Limit order logic (simplified, ignored for now)
                still_pending.append(order)
                
        self.pending_orders = still_pending
        return fills
