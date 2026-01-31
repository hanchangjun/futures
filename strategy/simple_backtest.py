
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from database.models import StockBar
from datetime import datetime, timedelta

def run_simple_swing_strategy(
    symbol: str, 
    period: str, 
    db: Session, 
    days: int = 365,
    atr_period: int = 14,
    zs_swing_num: int = 3,
    break_atr: float = 0.5,
    risk_per_trade: float = 0.01,
    max_drawdown: float = 0.02
):
    # =========================
    # 1. 读取数据 (From DB)
    # =========================
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Query bars
    bars = db.query(StockBar).filter(
        StockBar.symbol == symbol,
        StockBar.period == period,
        StockBar.dt >= start_date
    ).order_by(StockBar.dt.asc()).all()
    
    if not bars:
        return {"error": f"No data found for {symbol} {period}"}

    # Convert to DataFrame
    data = [{
        "datetime": b.dt,
        "open": b.open,
        "high": b.high,
        "low": b.low,
        "close": b.close,
        "volume": b.volume
    } for b in bars]
    
    df = pd.DataFrame(data)
    df = df.sort_values("datetime").reset_index(drop=True)

    # =========================
    # 2. ATR 计算
    # =========================
    high, low, close = df.high, df.low, df.close

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)

    df["atr"] = tr.rolling(atr_period).mean()

    # =========================
    # 3. Swing High / Low (去主观)
    # =========================
    # Shift(-1) implies looking at the NEXT bar. 
    # For a backtest iterating index i, we can only know swing at k if k < i (or k <= i-1).
    # Swing High at k: H[k] > H[k-1] AND H[k] > H[k+1].
    # This pattern is confirmed at k+1.
    # So at index i (current price), we can see swings up to i-1.
    
    df["swing_high"] = (df.high > df.high.shift(1)) & (df.high > df.high.shift(-1))
    df["swing_low"]  = (df.low  < df.low.shift(1))  & (df.low  < df.low.shift(-1))

    # 收集 swing 点 (Use list for fast lookup, or just iterate)
    # Note: df.iterrows is slow, but acceptable for thousands of bars. 
    # Optimization: Pre-calculate indices of swings.
    swings = []
    # We iterate through the DF to build the swing list compatible with the loop logic
    # But strictly speaking, swing at index k is only known at index k+1.
    # The user's loop logic checks `s["i"] < i`.
    # If s["i"] is k, and k < i, then k <= i-1.
    # If k = i-1, we need to know k+1 = i to confirm.
    # So at bar i, we confirm swing at i-1.
    # The logic holds.
    
    swing_high_indices = df.index[df["swing_high"]].tolist()
    swing_low_indices = df.index[df["swing_low"]].tolist()
    
    # Merge and sort
    all_swings = []
    for idx in swing_high_indices:
        all_swings.append({"i": idx, "high": df.at[idx, "high"], "low": np.nan, "type": "high"})
    for idx in swing_low_indices:
        all_swings.append({"i": idx, "high": np.nan, "low": df.at[idx, "low"], "type": "low"})
    
    all_swings.sort(key=lambda x: x["i"])
    
    # =========================
    # 4. 回测主循环
    # =========================
    equity = 1.0
    peak_equity = 1.0
    position = 0
    entry_price = 0
    # entry_i = 0
    
    equity_curve = []
    trades = []
    trade_logs = []

    # Iterate
    # Start from max(ATR_PERIOD, ZS_SWING_NUM*some_factor) to ensure data
    start_idx = atr_period + 1
    
    for i in range(start_idx, len(df)):
        price = df.at[i, "close"]
        atr = df.at[i, "atr"]
        current_dt = df.at[i, "datetime"]

        if np.isnan(atr):
            equity_curve.append(equity)
            continue

        # ===== 找最近中枢 =====
        # Filter swings that happened strictly before i
        # Logic: Swing at k is confirmed at k+1. So if we are at i, we know swings up to i-1.
        # But wait, swing at i-1 requires i to close.
        # User code: `s["i"] < i`.
        # If s["i"] is i-1, it uses high[i]. This implies we use Close[i] to trade based on pattern formed by Close[i] (High[i]).
        # This is essentially "Close on signal".
        
        recent = [s for s in all_swings if s["i"] < i][-zs_swing_num:]
        zs = None
        if len(recent) == zs_swing_num:
            highs = [s["high"] for s in recent if not np.isnan(s["high"])]
            lows  = [s["low"]  for s in recent if not np.isnan(s["low"])]
            if highs and lows:
                zs_low = max(lows)
                zs_high = min(highs)
                if zs_low < zs_high:
                    zs = (zs_low, zs_high)

        # ===== 开仓（离开中枢）=====
        if position == 0 and zs:
            # Buy Condition
            if price > zs[1] and (price - zs[1]) > break_atr * atr:
                position = 1
                entry_price = price
                # entry_i = i
                trade_logs.append({
                    "dt": current_dt.isoformat(),
                    "action": "BUY",
                    "price": price,
                    "reason": "Break ZS High",
                    "zs": zs
                })

        # ===== 平仓 =====
        elif position == 1:
            # 1）跌回中枢
            if zs and price < zs[1]:
                ret = (price - entry_price) / entry_price
                equity *= (1 + ret)
                trades.append(ret)
                position = 0
                trade_logs.append({
                    "dt": current_dt.isoformat(),
                    "action": "SELL",
                    "price": price,
                    "reason": "Fall back to ZS",
                    "pnl": ret
                })

            # 2）ATR 止损
            elif price < entry_price - 1.5 * atr:
                ret = (price - entry_price) / entry_price
                equity *= (1 + ret)
                trades.append(ret)
                position = 0
                trade_logs.append({
                    "dt": current_dt.isoformat(),
                    "action": "SELL",
                    "price": price,
                    "reason": "Stop Loss (ATR)",
                    "pnl": ret
                })

        # ===== 回撤风控 =====
        peak_equity = max(peak_equity, equity)
        drawdown = (equity / peak_equity - 1)
        
        if drawdown < -max_drawdown:
            trade_logs.append({
                "dt": current_dt.isoformat(),
                "action": "STOP",
                "price": price,
                "reason": f"Max Drawdown reached: {drawdown:.2%}",
                "pnl": 0
            })
            break

        equity_curve.append(equity)

    # =========================
    # 5. 统计指标
    # =========================
    win = [t for t in trades if t > 0]
    loss = [t for t in trades if t <= 0]
    
    total_trades = len(trades)
    win_rate = len(win) / total_trades if total_trades else 0
    avg_win = np.mean(win) if win else 0
    avg_loss = np.mean(loss) if loss else 0
    pnl_ratio = (avg_win / abs(avg_loss)) if (win and loss and avg_loss != 0) else 0
    
    final_equity = equity_curve[-1] if equity_curve else 1.0
    cum_return = final_equity - 1
    
    # Calculate Max Drawdown from curve
    eq_series = pd.Series(equity_curve)
    if not eq_series.empty:
        max_dd = (eq_series / eq_series.cummax() - 1).min()
    else:
        max_dd = 0

    return {
        "metrics": {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 4),
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
            "pnl_ratio": round(pnl_ratio, 4),
            "cum_return": round(cum_return, 4),
            "max_drawdown": round(max_dd, 4),
            "final_equity": round(final_equity, 4)
        },
        "trades": trade_logs,
        "equity_curve": [round(x, 4) for x in equity_curve]
    }
