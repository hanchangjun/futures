import argparse
import json
import os
import csv
from typing import List, Optional
from datetime import datetime

from datafeed import get_bars, log_debug, PriceBar
from strategy import chan_strategy, pure_chan_strategy
from backtest.engine import BacktestEngine
from backtest.event import SignalEvent
from backtest.broker import BacktestBroker
from portfolio.manager import PortfolioManager
from risk.manager import RiskManager

from chan.indicators import calculate_macd
import pandas as pd

class ChanStrategyAdapter:
    def __init__(self, period: str, filter_trend_map: Optional[dict] = None, strategy_name: str = "standard"):
        self.seen_signals = set()
        self.period = period
        self.filter_trend_map = filter_trend_map # {dt: 1/-1/0}
        self.strategy_name = strategy_name

    def __call__(self, history: List[PriceBar], symbol: str) -> Optional[SignalEvent]:
        # Optimization: Use last 500 bars to speed up calculation
        subset = history[-500:] if len(history) > 500 else history
        
        # Check Trend Filter First
        last_dt = history[-1].date
        
        try:
            # Instantiate strategy
            if self.strategy_name == "pure_chan":
                 strat = pure_chan_strategy.PureChanStrategy(symbol, self.period)
            else:
                 strat = chan_strategy.ChanStrategy(symbol, self.period)
                 
            signals = strat.run(subset)
        except Exception as e:
            # log_debug(True, f"Strategy Error: {e}")
            return None
            
        if not signals:
            return None
            
        # Only check the LAST signal to avoid re-triggering old history
        s = signals[-1]
        sig_id = f"{s['type']}_{s['dt']}"
        
        if sig_id not in self.seen_signals:
            self.seen_signals.add(sig_id)
            
            # Check if signal is recent (within last bar)
            # This is important for backtest to respect time
            last_dt = history[-1].date
            
            # --- Apply MTF Filter ---
            if self.filter_trend_map is not None:
                # Find trend at signal time (s['dt'])
                # We need the trend of the larger timeframe AT that time.
                # Since s['dt'] is the signal time (end of bar), we look for filter_trend <= s['dt']
                
                # Simple lookup:
                # Get keys of trend map
                # Since we don't want to sort keys every time, we assume map is built sequentially or use bisect.
                # Actually, dict lookup is O(1) if we have exact match. 
                # But 4H bar ends at 10:30, 15:00... 30m bar ends at 10:00, 10:30...
                # If 30m ends at 10:00, we want the 4H bar that covers it.
                # The 4H bar covering 10:00 might not be finished if it ends at 11:30.
                # So we should look at the *previous* completed 4H bar?
                # Or if we use "Realtime" filter, we look at the indicator value *as of* that time.
                # Let's use the `asof` logic from pandas if possible, or simple iteration.
                
                # To be efficient: pass the *current trend* to this adapter from the runner loop?
                # No, the runner loop calls `strategy_func(engine.history, symbol)`.
                # `engine` doesn't know about trend.
                
                # Let's iterate keys reversed? Slow.
                # Let's rely on pandas `asof` if we convert map to Series.
                pass 

            # Refined Filter Logic
            allowed = True
            if self.filter_trend_map is not None:
                # filter_trend_map is a pd.Series indexed by datetime
                try:
                    # Get index of trend <= s['dt']
                    idx = self.filter_trend_map.index.searchsorted(s['dt'], side='right') - 1
                    if idx >= 0:
                        trend_val = self.filter_trend_map.iloc[idx]
                        
                        # Rule: Long only if Trend >= 0, Short only if Trend <= 0
                        is_long = 'B' in s['type'] or 'LONG' in s['type']
                        is_short = 'S' in s['type'] or 'SHORT' in s['type']
                        
                        if is_long and trend_val < 0:
                            allowed = False
                            # print(f"🚫 Filtered LONG at {s['dt']} (Trend: {trend_val})")
                        elif is_short and trend_val > 0:
                            allowed = False
                            # print(f"🚫 Filtered SHORT at {s['dt']} (Trend: {trend_val})")
                except Exception as e:
                    print(f"Filter Error: {e}")

            if not allowed:
                return None
            
            return SignalEvent(
                symbol=symbol,
                dt=last_dt, 
                signal_type=s['type'],
                price=s['price'],
                sl=s.get('sl'),
                tp=s.get('tp')
            )
            
        return None

def run_event_backtest(args: argparse.Namespace):
    start_time = datetime.now()
    print(f"🚀 启动事件驱动回测 | 品种: {args.symbol} | 周期: {args.period}")
    
    # 1. Fetch Data using system's standard get_bars
    # This allows using TQ, TDX, or File data sources
    required = max(args.slow, args.atr) + 500 # Ensure enough history for strategy
    
    # Use standard get_bars from datafeed
    # args must have source, symbol, period etc.
    username = args.tq_username
    password = args.tq_password
    count = args.tq_count if args.source == "tq" else args.tdx_count
    
    bars, used_symbol = get_bars(
        source=args.source,
        symbol=args.symbol,
        period=args.period,
        count=count,
        csv_dir=args.csv_dir,
        csv_path=args.csv_path,
        tdx_host=args.tdx_host,
        tdx_port=args.tdx_port,
        tdx_market=args.tdx_market,
        username=username,
        password=password,
        required=required,
        debug=args.debug
    )
    
    if not bars:
        print("❌ 未找到回测数据")
        return

    print(f"✅ 加载数据完成: {len(bars)} 根K线")
    
    # --- Prepare Filter Data (MTF) ---
    filter_trend_series = None
    filter_period = None
    if args.period == '30m':
        filter_period = '1d' # Use Daily for 30m? Or 4h? User suggested 4H.
        # But TQ/TDX might not support '4h' easily if not standard?
        # Let's try '1d' as it's safer, or check if '4h' works.
        # User said "combine large cycle (e.g. 4H)".
        # I'll try to fetch 4h. If fails, fallback to 1d.
        filter_period = '1d' # Let's use 1d for robustness first, or 4h if source supports it.
        # Given "KQ.m@SHFE.rb" is futures, 1d is standard.
        
    if filter_period:
        print(f"🔍 加载过滤数据: {filter_period}")
        try:
            fbars, _ = get_bars(
                source=args.source,
                symbol=args.symbol,
                period=filter_period,
                count=count, # same count
                username=username,
                password=password,
                required=100
            )
            if fbars:
                # Calculate Trend on Filter Bars
                # Trend Definition: MACD Diff > 0 -> Bullish (1), Else Bearish (-1)
                f_macd = calculate_macd(fbars)
                # Align timestamps
                dates = [b.date for b in fbars]
                
                # Trend: 1 if diff > 0 else -1
                trend_vals = f_macd['diff'].apply(lambda x: 1 if x > 0 else -1).values
                
                filter_trend_series = pd.Series(trend_vals, index=dates).sort_index()
                print(f"✅ 过滤数据就绪: {len(filter_trend_series)} 记录")
        except Exception as e:
            print(f"⚠️ 加载过滤数据失败: {e}")

    # 2. Initialize Modules
    portfolio = PortfolioManager(initial_capital=args.equity, default_qty=10) # Default 10 lots or from args?
    # TODO: Add args.default_qty if needed, for now hardcoded or derived
    
    risk = RiskManager(max_pos_size=50) # Hardcoded for now
    broker = BacktestBroker(slippage=1.0, commission_rate=0.0001)
    
    # 3. Initialize Strategy
    # Pass filter map if available
    strategy_name = getattr(args, 'strategy_name', 'standard')
    strategy = ChanStrategyAdapter(args.period, filter_trend_map=filter_trend_series, strategy_name=strategy_name)
    
    # 4. Run Backtest
    engine = BacktestEngine(portfolio, risk, broker)
    engine.run(bars, strategy, used_symbol)
    end_time = datetime.now()
    
    # 5. Report
    duration = (end_time - start_time).total_seconds()
    print(f"\n📊 回测报告 (耗时 {duration:.2f}s)")
    print("-" * 40)
    print(f"初始资金: {portfolio.initial_capital:,.2f}")
    print(f"最终权益: {portfolio.equity:,.2f}")
    print(f"累计收益: {portfolio.equity - portfolio.initial_capital:,.2f}")
    roi = (portfolio.equity - portfolio.initial_capital) / portfolio.initial_capital * 100
    print(f"收益率:   {roi:.2f}%")
    print(f"持仓状态: {dict(portfolio.positions)}")
    print("-" * 40)
    
    # Save Results
    results_dir = "backtest_results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"{args.symbol}_{args.period}_{timestamp}"
    
    # 1. Save Report JSON
    # 2. Save Trades CSV
    # 3. Save Equity Curve CSV
    # NOTE: Disabled file saving as per requirement. Only DB persistence is used in web mode.
    # If CLI mode needs it, we can check args.source or similar.
    
    # report = { ... }
    # with open(os.path.join(results_dir, f"{base_filename}_report.json"), "w", encoding="utf-8") as f:
    #     json.dump(report, f, indent=4, ensure_ascii=False)
        
    # if engine.trades:
    #     fieldnames = ["dt", "symbol", "direction", "quantity", "price", "commission", "pnl", "type"]
    #     with open(os.path.join(results_dir, f"{base_filename}_trades.csv"), "w", newline="", encoding="utf-8") as f:
    #         writer = csv.DictWriter(f, fieldnames=fieldnames)
    #         writer.writeheader()
    #         writer.writerows(engine.trades)
            
    # if engine.equity_curve:
    #     with open(os.path.join(results_dir, f"{base_filename}_equity.csv"), "w", newline="", encoding="utf-8") as f:
    #         writer = csv.DictWriter(f, fieldnames=["dt", "equity"])
    #         writer.writeheader()
    #         writer.writerows(engine.equity_curve)
            
    # print(f"✅ 回测结果已保存至 {results_dir}")

    # Optional: Print trade history or save to file
    if engine.history:
        print(f"已处理K线数: {len(engine.history)}")
        
    # Calculate Win Rate
    wins = [t for t in engine.trades if t.get('pnl', 0) > 0]
    win_rate = len(wins) / len(engine.trades) if engine.trades else 0.0
        
    return {
        "duration": duration,
        "initial_capital": portfolio.initial_capital,
        "final_equity": portfolio.equity,
        "pnl": portfolio.equity - portfolio.initial_capital,
        "roi": (portfolio.equity - portfolio.initial_capital) / portfolio.initial_capital * 100,
        "positions": dict(portfolio.positions),
        "bars_processed": len(engine.history),
        "total_trades": len(engine.trades),
        "win_rate": win_rate,
        "trades": engine.trades,
        "logs": engine.logs
    }
