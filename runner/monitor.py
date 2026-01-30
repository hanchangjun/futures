import time
import traceback
import os
import argparse
from typing import Optional
from datetime import datetime
from pathlib import Path

from notify import notify, NotificationLevel
from state.signal_state import SignalState
from state.confirm_state import ConfirmState
from datafeed import get_bars, log_debug
from .confirm import check_confirm

# Note: We import compute_dual_signal and signal_payload from main 
# (or wherever they are defined) to reuse logic. 
# Since main.py is the entry point, circular imports might be tricky if we import main.
# However, user said "Don't modify signal / decision layer".
# To avoid circular import if main imports runner, we should ideally move business logic 
# out of main. But for now, we will assume main imports runner, so runner CANNOT import main.
# We will ask for compute_dual_signal to be passed in or defined here?
# Let's see. compute_dual_signal is in main.py. 
# To solve this cleanly without big refactor, we can copy the orchestration logic or 
# pass the function as a callback. 
# Or better: Extract compute_dual_signal to a new module `signal/bridge.py`? 
# No, user said "Don't modify signal layer".
# Let's assume we can move `compute_dual_signal` to `signal/engine.py` or similar?
# Or just implement the loop in runner and let main call it, passing necessary functions?
# That's dependency injection. Good pattern.

class MonitorRunner:
    def __init__(self, args: argparse.Namespace, compute_func, payload_func):
        self.args = args
        self.state = SignalState(args.state_file)
        self.confirm = ConfirmState(getattr(args, "confirm_state_file", Path("confirm_state.json")))
        self.compute_func = compute_func
        self.payload_func = payload_func
        
        # Calculate period seconds for index generation (robust bar_index)
        self.period_seconds = 300
        try:
            if args.period.endswith("m"):
                self.period_seconds = int(args.period[:-1]) * 60
            elif args.period.endswith("h"):
                self.period_seconds = int(args.period[:-1]) * 3600
            elif args.period.endswith("d"):
                self.period_seconds = int(args.period[:-1]) * 86400
        except:
            pass

    def get_sleep_interval(self) -> int:
        """Determine sleep interval based on period."""
        period = self.args.period
        if period.endswith("d"):
            return 1800  # 30 minutes for daily
        if period.endswith("h"):
            return 1800  # 30 minutes for hourly
        if period.endswith("m"):
            try:
                minutes = int(period[:-1])
                # Sleep for half the candle time or at least 1 minute
                return max(60, min(minutes * 60, 300))
            except ValueError:
                pass
        return 60  # Default 1 minute

    def run(self):
        notify(f"🚀 系统启动监控 | 周期: {self.args.period} | 品种: {self.args.symbol}", level=NotificationLevel.INFO)
        
        while True:
            try:
                self._run_once()
                
                # Sleep
                sleep_seconds = self.get_sleep_interval()
                # notify(f"Sleeping for {sleep_seconds}s...", level=NotificationLevel.DEBUG)
                time.sleep(sleep_seconds)
                
            except KeyboardInterrupt:
                notify("🛑 系统手动停止", level=NotificationLevel.INFO)
                break
            except Exception as e:
                error_msg = f"系统运行异常:\n{str(e)}\n{traceback.format_exc()}"
                notify(error_msg, level=NotificationLevel.ERROR)
                time.sleep(60) # Prevent rapid error loops

    def _run_once(self):
        args = self.args
        log_debug(args.debug, f"[{datetime.now().strftime('%H:%M:%S')}] 开始检查信号...")
        
        # 1. Fetch Data
        required = max(args.slow, args.atr, args.slow_2, args.atr_2) + 5
        username = args.tq_username or os.getenv("TQ_USERNAME")
        password = args.tq_password or os.getenv("TQ_PASSWORD")
        count = args.tq_count if args.source == "tq" else args.tdx_count
        
        primary_bars, used_symbol = get_bars(
            source=args.source,
            symbol=args.symbol,
            period=args.period,
            count=count,
            csv_dir=args.csv_dir,
            csv_path=args.csv_path,
            csv_path_daily=args.csv_path_daily,
            csv_path_60=args.csv_path_60,
            tdx_symbol=args.tdx_symbol,
            tdx_host=args.tdx_host,
            tdx_port=args.tdx_port,
            tdx_market=args.tdx_market,
            tdx_auto_main=args.tdx_auto_main,
            tq_symbol=args.tq_symbol,
            username=username,
            password=password,
            timeout=args.tq_timeout,
            wait_update_once=True, # Always wait in monitor mode? Or False? run_watch had wait_update_once=not args.once (which is True)
            increment=args.increment,
            cache_file=args.cache_file,
            increment_count=args.increment_count,
            increment_overlap=args.increment_overlap,
            required=required,
            debug=args.debug,
        )

        secondary_bars = None
        if args.period_2:
            # Construct secondary kwargs (similar to main.py logic)
            secondary_kwargs = {
                "csv_dir": args.csv_dir,
                "csv_path": args.csv_path,
                "csv_path_daily": args.csv_path_daily,
                "csv_path_60": args.csv_path_60,
                "tdx_symbol": args.tdx_symbol,
                "tdx_host": args.tdx_host,
                "tdx_port": args.tdx_port,
                "tdx_market": args.tdx_market,
                "tdx_auto_main": args.tdx_auto_main,
                "tq_symbol": args.tq_symbol,
                "username": username,
                "password": password,
                "timeout": args.tq_timeout,
                "wait_update_once": True,
                "increment": args.increment,
                "cache_file": args.cache_file,
                "increment_count": args.increment_count,
                "increment_overlap": args.increment_overlap,
                "required": required,
                "debug": args.debug,
            }
            if args.source == "tq":
                secondary_kwargs["tq_symbol"] = used_symbol
            if args.source == "tdx":
                secondary_kwargs["tdx_symbol"] = used_symbol
                
            secondary_bars, _ = get_bars(
                source=args.source,
                symbol=args.symbol,
                period=args.period_2,
                count=count,
                **secondary_kwargs,
            )

        if not primary_bars:
            log_debug(args.debug, "主周期无有效K线")
            return

        # 2. Compute Signal (Dependency Injection)
        signal = self.compute_func(primary_bars, secondary_bars, args)
        
        if signal is None or signal.direction == "观望":
            log_debug(args.debug, "无有效信号或处于观望")
            # Even if "观望", we might want to update state? 
            # User said: "Current signal direction != Last signal direction -> Notify".
            # If "观望" is a direction, we handle it.
            # But usually we don't notify "观望". 
            # If previous was "Buy", and now "Hold", do we notify "Hold"?
            # User requirement: "Current signal direction != Last signal direction -> Allow notification"
            # If logic returns None, it means no signal calculated? Or "Hold"?
            # In compute_signal: returns Signal with direction="观望" or None (if not enough bars).
            # If None, we skip.
            # If "观望", we treat it as a valid signal state.
            return

        # 3. Check State & Notify
        latest_date = primary_bars[-1].date if primary_bars else None
        payload = self.payload_func(used_symbol, signal, latest_date)
        # Augment payload with current bar index for cooldown logic
        # Since TQ returns fixed-length list and PriceBar lacks ID, we use timestamp-based index
        # Index = timestamp // period_seconds. This ensures index increases even with fixed buffer.
        last_bar = primary_bars[-1]
        if last_bar.date:
            payload["bar_index"] = int(last_bar.date.timestamp() // self.period_seconds)
        else:
            payload["bar_index"] = len(primary_bars)
        # Strength-based routing; runner does not decide strength, it reads from payload
        strength = (payload.get("strength") or "normal").lower()
        if strength == "weak":
            # Ignore completely: no cooldown, no notify
            log_debug(args.debug, f"弱信号忽略: {signal.direction}")
            return
            
        # Pre-check: If this is the EXACT SAME bar as the last notification (gap=0) and direction is same,
        # silently skip to avoid spamming logs.
        # Note: We need to peek at the state without loading it twice if possible, 
        # but should_notify loads it anyway. Let's rely on should_notify return or check manually.
        # To avoid race conditions or complex logic, we'll let should_notify handle it,
        # but filter the log output.
        
        allow, reason = self.state.should_notify(payload, getattr(args, "cooldown_bars", 5))
        
        if not allow:
            # If blocked because of "gap=0" (same bar), we might want to silence the log
            # The reason string from signal_state for gap=0 is usually "冷却中(0/5)..."
            if "0/" in reason and "冷却中" in reason:
                # This means it's the same bar index. Silent skip.
                # log_debug(args.debug, f"同K线重复信号忽略: {reason}")
                return
            
            # Cooldown blocked (genuine cooling for subsequent bars): only log, no WeCom push
            notify(f"信号被冷却拦截: {signal.direction} | 原因: {reason}", level=NotificationLevel.BLOCKED)
            return
            
        # Cooldown passed
        if strength == "normal":
            # Log INFO only, do not push WeCom, and do NOT write state
            notify(f"普通信号通过冷却: {signal.direction} | {reason}", level=NotificationLevel.INFO)
            return
        # strength == "strong": push WeCom (SIGNAL) and write state
        msg = f"检测到新强信号: {signal.direction}"
        # Determine actual webhook used (follow notify's env resolution)
        webhook_final = args.webhook or os.getenv("WECOM_WEBHOOK_URL") or os.getenv("WECOM_WEBHOOK")
        try:
            notify(msg, level=NotificationLevel.SIGNAL, webhook_url=args.webhook, **payload)
            
            # ALWAYS save state for strong signals to prevent repetition, regardless of webhook existence
            to_save = dict(payload)
            to_save["last_notify_bar_index"] = payload["bar_index"]
            self.state.save(to_save)
            log_debug(args.debug, f"强信号已保存状态: {signal.direction} ({reason})")
            
            if webhook_final:
                # Save pending confirm state only if we really expect to notify later
                self.confirm.save_pending(payload)
            else:
                log_debug(args.debug, "未配置Webhook，仅保存信号状态，不进入Confirm流程")
        except Exception as e:
            log_debug(args.debug, f"通知发送异常，未写入状态: {e}")
            return
        # After notification attempt, check confirm for existing pending
        pending = self.confirm.get_pending()
        if pending:
            confirmed, last_close, last_atr, why = check_confirm(primary_bars, pending, args.atr)
            if confirmed:
                # Send confirm notification (only once)
                webhook_final = args.webhook or os.getenv("WECOM_WEBHOOK_URL") or os.getenv("WECOM_WEBHOOK")
                confirm_msg = f"✅ 信号确认: {pending.get('direction')} | 价格 {last_close} 已突破入场 {pending.get('entry')} 至少 0.5ATR({last_atr:.2f})"
                notify(confirm_msg, level=NotificationLevel.SIGNAL, webhook_url=args.webhook, **pending)
                if webhook_final:
                    self.confirm.mark_confirmed({
                        "symbol": pending.get("symbol"),
                        "direction": pending.get("direction"),
                        "entry": pending.get("entry"),
                        "confirm_bar_index": len(primary_bars),
                        "confirm_price": last_close,
                        "date": pending.get("date"),
                    })
                    log_debug(args.debug, "确认已写入并清除pending")
                else:
                    log_debug(args.debug, "未配置Webhook，确认仅本地日志")

def start_monitor(args, compute_func, payload_func):
    runner = MonitorRunner(args, compute_func, payload_func)
    runner.run()
