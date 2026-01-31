from backtest.event import OrderEvent
from portfolio.manager import PortfolioManager

class RiskManager:
    def __init__(self, max_pos_size=10, stop_loss_pct=0.02):
        self.max_pos_size = max_pos_size
        self.stop_loss_pct = stop_loss_pct
        
    def check_order(self, order: OrderEvent, portfolio: PortfolioManager) -> bool:
        """
        Return True if order is allowed, False otherwise.
        """
        # 1. Check Quantity Limit
        current_pos = portfolio.positions[order.symbol]
        projected_pos = current_pos
        
        if order.direction == 'BUY':
            projected_pos += order.quantity
        else:
            projected_pos -= order.quantity
            
        if abs(projected_pos) > self.max_pos_size:
            # print(f"Risk Reject: Max position size exceeded for {order.symbol}")
            return False
            
        # 2. Check Capital (Naive)
        # Assuming margin requirement is 10% of value? 
        # For now, just check if we have cash for Buy (for Spot) or Margin (for Futures)
        # This is simplified.
        
        return True
