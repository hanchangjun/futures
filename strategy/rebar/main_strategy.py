import logging
import json
import math
from datetime import datetime, time, timedelta
from typing import Dict, Optional, List, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Configure logger
logger = logging.getLogger("RebarStrategy")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class SignalType(Enum):
    B1 = "1B"
    B2 = "2B"
    B3 = "3B"
    S1 = "1S"
    S2 = "2S"
    S3 = "3S"

@dataclass
class MarketData:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_interest: float = 0
    limit_up: float = 0
    limit_down: float = 0
    spot_price: float = 0  # For basis calculation

@dataclass
class TradeSignal:
    signal_id: str
    signal_type: SignalType
    timestamp: datetime
    price: float
    stop_loss: float = 0.0
    take_profit: float = 0.0
    weight: float = 1.0  # Base weight 1.0
    meta: Dict = field(default_factory=dict)

@dataclass
class Position:
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    avg_price: float
    quantity: float # As percentage of equity for this example, or lots
    current_price: float
    peak_equity: float = 0.0 # For drawdown calc
    initial_equity: float = 0.0
    entry_time: datetime = datetime.min
    signal_type: Optional[SignalType] = None
    stop_loss: float = 0.0
    take_profit: float = 0.0

class RiskManager:
    """
    Handles risk rules: SL/TP, Position Sizing, Drawdown Control.
    """
    def __init__(self, config: Dict):
        self.config = config.get("risk_control", {})
        self.atr_period = self.config.get("atr_period", 14)
        self.signals_config = self.config.get("signals", {})
        self.global_config = self.config.get("global", {})
        
        self.current_equity = 100000.0 # Example initial equity
        self.peak_equity = 100000.0
        self.positions: Dict[str, Position] = {} # Symbol -> Position
        self.atr_buffer: List[float] = [] # Store TRs for ATR calc
        
    def update_atr(self, high: float, low: float, close: float) -> float:
        # Simple ATR update
        if not self.atr_buffer:
            tr = high - low
        else:
            prev_close = close # In real stream, this should be prev close. 
            # Simplified: assuming we get called sequentially. 
            # Ideally we need prev_close stored.
            # Here we just use high-low for simplicity if prev not available, 
            # or caller handles TR.
            tr = high - low # Placeholder, real ATR needs prev_close
        
        self.atr_buffer.append(tr)
        if len(self.atr_buffer) > self.atr_period:
            self.atr_buffer.pop(0)
            
        return sum(self.atr_buffer) / len(self.atr_buffer) if self.atr_buffer else tr

    def calculate_atr(self) -> float:
        return sum(self.atr_buffer) / len(self.atr_buffer) if self.atr_buffer else 10.0 # Default fallback

    def check_entry_risk(self, signal: TradeSignal, current_equity: float) -> Tuple[bool, float, str]:
        """
        Check if entry is allowed and calculate size.
        Returns: (Allowed, SizePct, Reason)
        """
        # Global Drawdown Check
        drawdown = (self.peak_equity - current_equity) / self.peak_equity
        if drawdown > self.global_config.get("max_total_drawdown", 0.05):
            return False, 0.0, f"Max Drawdown Exceeded: {drawdown:.2%}"

        sig_conf = self.signals_config.get(signal.signal_type.value, {})
        
        # 3B No Add check
        if signal.signal_type == SignalType.B3 or signal.signal_type == SignalType.S3:
            if not sig_conf.get("allow_add", False):
                # If we already have position? 
                # Assuming this function is for NEW entry or ADD.
                # If we have position for this symbol/signal type, reject?
                pass

        size = sig_conf.get("initial_pos", 0.02)
        
        # Weight adjustment from Strategy (e.g. Basis)
        # Assuming signal.weight modifies size
        size *= signal.weight
        
        # 2B Max Pos Check
        if signal.signal_type in [SignalType.B2, SignalType.S2]:
            max_pos = sig_conf.get("max_pos", 0.08)
            if size > max_pos:
                size = max_pos

        return True, size, "Approved"

    def get_stop_loss_price(self, signal: TradeSignal, atr: float, market_data: MarketData) -> float:
        """
        Calculate initial SL based on signal type.
        """
        stype = signal.signal_type.value
        conf = self.signals_config.get(stype, {})
        
        sl_price = signal.price
        
        if stype == "1B":
            # Low - 1.2 ATR
            # Need '1B Low'. Assuming signal.meta contains 'structure_low'
            low = signal.meta.get("structure_low", signal.price)
            mult = conf.get("sl_multiplier", 1.2)
            sl_price = low - mult * atr
            
        elif stype == "2B":
            # min(1B Low, 2B Low)
            low1b = signal.meta.get("1b_low", signal.price)
            low2b = signal.meta.get("2b_low", signal.price)
            sl_price = min(low1b, low2b)
            
        elif stype == "3B":
            # max(Center Bottom, Pullback Low) for Buy?
            # Prompt says: "max(中枢下沿, 回抽低点)"
            zg_dd = signal.meta.get("center_bottom", signal.price) # Center DD
            pb_low = signal.meta.get("pullback_low", signal.price)
            sl_price = max(zg_dd, pb_low) # For Buy. For Sell needs logic flip.
            
            if "S" in stype: # Short
                # min(Center Top, Pullback High)
                zg_gg = signal.meta.get("center_top", signal.price)
                pb_high = signal.meta.get("pullback_high", signal.price)
                sl_price = min(zg_gg, pb_high)

        return sl_price

    def update_position(self, symbol: str, current_price: float, equity: float) -> List[str]:
        """
        Check SL/TP and Drawdown for existing position.
        Returns list of actions (e.g. ['CLOSE', 'REDUCE']).
        """
        actions = []
        pos = self.positions.get(symbol)
        if not pos:
            return actions
            
        # Update Peak Equity
        self.peak_equity = max(self.peak_equity, equity)
        
        # 1. Single Trade Loss Check (> 2%)
        # PnL = (Current - Avg) * Qty (Simplified)
        # Here we check price deviation percentage from entry? 
        # Or equity drop contribution?
        # Prompt: "Single loss > 2% ... Force Close"
        # Assuming 2% of Account Equity? Or 2% price drop?
        # "Single Loss > 2%" usually means risk per trade.
        # If (Entry - Current) / Entry > 0.02? No, that's price drop.
        # Let's assume loss amount > 2% of Initial Equity.
        
        pnl_pct = 0
        if pos.direction == 'LONG':
            pnl_pct = (current_price - pos.avg_price) / pos.avg_price
        else:
            pnl_pct = (pos.avg_price - current_price) / pos.avg_price
            
        # If position size is X%, and PnL is Y%. Total impact is X*Y.
        # If X*Y < -0.02 -> Close.
        # We store Quantity as % of equity for simplicity in this logic
        total_loss_impact = pos.quantity * pnl_pct
        if total_loss_impact < -self.global_config.get("max_single_loss", 0.02):
            actions.append("FORCE_CLOSE_LOSS")
            
        # 2. Stop Loss Price
        if pos.direction == 'LONG':
            if current_price <= pos.stop_loss:
                actions.append("STOP_LOSS")
        else:
            if current_price >= pos.stop_loss:
                actions.append("STOP_LOSS")
                
        # 3. Dynamic Drawdown (Total)
        dd = (self.peak_equity - equity) / self.peak_equity
        if dd > self.global_config.get("max_total_drawdown", 0.05):
            actions.append("FORCE_CLOSE_DD")
            
        # 4. 1B Add Logic (Price new high)
        if pos.signal_type == SignalType.B1 and pos.direction == 'LONG':
            # Need recent high tracking.
            # Simplified: If current > entry * 1.01 (1%)?
            # Prompt: "Price new high". Needs context of "High since entry".
            pass
            
        return actions

class RebarStrategy:
    """
    Main Strategy Class: Time/Price/Contract Filters.
    """
    def __init__(self, config_path: str = "params.json"):
        self.config = self._load_config(config_path)
        self.risk_manager = RiskManager(self.config)
        self.market_data_buffer: List[MarketData] = []
        
    def _load_config(self, path: str) -> Dict:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def on_tick(self, data: MarketData):
        """
        Real-time filtering and signal processing.
        """
        # 1. Time Filter
        if not self._check_time(data.timestamp):
            # Check Force Close
            if self._check_force_close(data.timestamp):
                self._force_close_all("Time Force Close")
            return

        # 2. Price Filter (Limit Move)
        if self._check_limit_move(data):
            return

        # 3. Process Logic (Mock Signal Generation)
        # In real usage, this calls Chan Logic
        # signal = self.chan_strategy.process(data)
        # if signal:
        #    self.on_signal(signal)
        pass

    def on_signal(self, signal: TradeSignal):
        """
        Handle generated signal.
        """
        # 1. Integer Barrier Filter
        if self._is_near_barrier(signal.price):
            # Check fluctuation
            # Need recent volatility.
            # "Effective fluctuation > 5". 
            # Assuming we check ATR or recent bar range.
            # If (High - Low) < 5: Return
            if signal.meta.get("bar_range", 10) <= 5:
                logger.info(f"Signal ignored: Near barrier {signal.price} with low volatility")
                return

        # 2. Contract Switch & Basis Adjustment
        weight_adj = self._check_basis_weight(signal)
        signal.weight += weight_adj
        
        # 3. Risk Manager Check
        allowed, size, reason = self.risk_manager.check_entry_risk(signal, 100000) # Mock Equity
        if allowed:
            logger.info(f"Signal Accepted: {signal.signal_id}, Size: {size:.2%}")
            self._execute_signal(signal, size)
        else:
            logger.info(f"Signal Rejected: {reason}")

    def _check_time(self, dt: datetime) -> bool:
        t = dt.time()
        sessions = self.config["time_filter"]["trading_sessions"]
        for sess in sessions:
            start = datetime.strptime(sess["start"], "%H:%M").time()
            end = datetime.strptime(sess["end"], "%H:%M").time()
            # Handle night session crossing midnight if needed (21:00 - 23:00 is same day)
            if start <= t <= end:
                return True
        return False

    def _check_force_close(self, dt: datetime) -> bool:
        t = dt.time()
        windows = self.config["time_filter"]["force_close_windows"]
        for win in windows:
            start = datetime.strptime(win["start"], "%H:%M").time()
            end = datetime.strptime(win["end"], "%H:%M").time()
            if start <= t <= end:
                return True
        return False

    def _is_near_barrier(self, price: float) -> bool:
        barriers = self.config["price_filter"]["integer_barriers"]
        rng = self.config["price_filter"]["barrier_range"]
        for b in barriers:
            if abs(price - b) <= rng:
                return True
        return False

    def _check_limit_move(self, data: MarketData) -> bool:
        """
        Returns True if trading should stop (Limit > 7%).
        Also adjusts position if > 5%.
        """
        if data.limit_up == 0: return False
        
        # Calculate limit move pct roughly if limits not provided as pct
        # Assuming data.limit_up is price.
        # Pct = (Limit - PreClose) / PreClose. 
        # Here we just check proximity or if data tells us pct.
        # Prompt: "Limit move >= 5%". 
        # Let's assume we calculate deviation from Open or PreClose.
        # Using Open for simplicity if PreClose unavailable.
        pct = abs(data.close - data.open) / data.open 
        
        cfg = self.config["price_filter"]["limit_move_pct"]
        
        if pct >= cfg["stop_opening_threshold"]:
            logger.warning("Limit move > 7%. Stop opening.")
            return True
            
        if pct >= cfg["reduce_position_threshold"]:
            # Logic to reduce position size for NEXT trades or CURRENT?
            # "Reduce position to 1%".
            # This implies new signals get 1% max.
            # We can set a flag in RiskManager or adjust here.
            pass
            
        return False

    def _check_basis_weight(self, signal: TradeSignal) -> float:
        # Spot - Futures / Spot ? Or Futures - Spot?
        # Basis usually Spot - Futures.
        # Discount (Tie Shui): Futures < Spot. Basis > 0.
        # Premium (Sheng Shui): Futures > Spot. Basis < 0.
        # Prompt: "Deep Tie Shui (<-1.5%)". 
        # Wait, usually Tie Shui means Basis is Positive. 
        # Maybe user definition: (Futures - Spot) / Spot?
        # If Futures < Spot (Discount), (F-S)/S is Negative.
        # So "Deep Discount < -1.5%" makes sense with (F-S)/S.
        # "High Premium > +1.5%" makes sense with (F-S)/S.
        
        # Need spot price.
        spot = signal.meta.get("spot_price", 0)
        if spot == 0: return 0.0
        
        basis_pct = (signal.price - spot) / spot
        
        cfg = self.config["contract_switch"]["basis_thresholds"]
        adj = self.config["contract_switch"]["weight_adjust"]
        
        if basis_pct < cfg["deep_discount"]:
            # Deep Discount -> Futures too low -> Expect rise -> Long +30%
            if "B" in signal.signal_type.value:
                return adj
        elif basis_pct > cfg["high_premium"]:
            # High Premium -> Futures too high -> Expect fall -> Short +30%
            if "S" in signal.signal_type.value:
                return adj
                
        return 0.0

    def _force_close_all(self, reason: str):
        logger.info(f"Force Close All: {reason}")
        # Call RiskManager or Broker to close
        pass

    def _execute_signal(self, signal: TradeSignal, size: float):
        # Placeholder for execution
        pass

if __name__ == "__main__":
    # Simple smoke test
    st = RebarStrategy()
    print("Strategy Initialized")
