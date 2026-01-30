import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from state.signal_state import SignalState
from datafeed import get_bars, log_debug

def start_init(args, compute_func, payload_func) -> bool:
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
        wait_update_once=True,
        increment=args.increment,
        cache_file=args.cache_file,
        increment_count=args.increment_count,
        increment_overlap=args.increment_overlap,
        required=required,
        debug=args.debug,
    )
    if not primary_bars:
        return False
    secondary_bars = None
    if args.period_2:
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
    signal = compute_func(primary_bars, secondary_bars, args)
    if signal is None or signal.direction == "观望":
        return False
    latest_date = primary_bars[-1].date if primary_bars else None
    payload = payload_func(used_symbol, signal, latest_date)
    payload["bar_index"] = len(primary_bars)
    if not payload.get("date"):
        payload["date"] = datetime.utcnow().isoformat()
    strength = (payload.get("strength") or "normal").lower()
    if strength != "strong" and not getattr(args, "init_allow_normal", False):
        return False
    state = SignalState(args.state_file)
    to_save = dict(payload)
    to_save["last_notify_bar_index"] = payload["bar_index"]
    state.save(to_save)
    log_debug(args.debug, "初始化状态已写入")
    return True
