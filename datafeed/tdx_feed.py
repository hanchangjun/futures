from datetime import datetime
from typing import List, Optional, Tuple

from .base import (
    PriceBar,
    bars_from_cache,
    bars_to_cache,
    cache_key,
    load_bar_cache,
    log_debug,
    merge_bars,
    parse_date,
    parse_float,
    save_bar_cache,
)

DEFAULT_TDX_HOSTS = [
    "119.147.212.81",
    "119.147.212.80",
    "110.185.73.53",
    "110.185.73.54",
    "124.74.236.94",
    "180.153.18.170",
    "180.153.18.171",
]


def normalize_hosts(hosts: str) -> List[str]:
    return [host.strip() for host in hosts.split(",") if host.strip()]


def connect_tdx(api, host: str, port: int, debug: bool) -> Optional[str]:
    candidates = normalize_hosts(host)
    for fallback in DEFAULT_TDX_HOSTS:
        if fallback not in candidates:
            candidates.append(fallback)
    for candidate in candidates:
        if api.connect(candidate, port):
            log_debug(debug, f"连接行情服务器: {candidate}:{port}")
            return candidate
    log_debug(debug, f"无法连接通达信行情服务器: {host}:{port}")
    return None


def fetch_tdx_bars(
    symbol: str,
    period: str,
    count: int,
    host: str,
    port: int,
    market: int,
    debug: bool,
) -> List[PriceBar]:
    try:
        from pytdx.exhq import TdxExHq_API
    except Exception:
        log_debug(debug, "未安装 pytdx，无法通过接口获取行情")
        return []
    period_map = {
        "1m": 0, "1min": 0,
        "5m": 1, "5min": 1,
        "15m": 2, "15min": 2,
        "30m": 3, "30min": 3,
        "60m": 4, "60min": 4, "1h": 4,
        "1d": 5, "day": 5,
    }
    category = period_map.get(period, 5)
    api = TdxExHq_API()
    if not connect_tdx(api, host, port, debug):
        return []
    try:
        data = api.get_instrument_bars(category, market, symbol, 0, count)
    finally:
        api.disconnect()
    if not data:
        return []
    bars: List[PriceBar] = []
    for row in data:
        open_v = parse_float(str(row.get("open", "")))
        high_v = parse_float(str(row.get("high", "")))
        low_v = parse_float(str(row.get("low", "")))
        close_v = parse_float(str(row.get("close", "")))
        if None in (open_v, high_v, low_v, close_v):
            continue
        date_v = parse_date(str(row.get("datetime", "")))
        bars.append(
            PriceBar(
                date=date_v,
                open=open_v,
                high=high_v,
                low=low_v,
                close=close_v,
            )
        )
    if bars and bars[0].date and bars[-1].date and bars[0].date > bars[-1].date:
        bars.reverse()
    log_debug(debug, f"接口K线数量: {len(bars)}")
    return bars


def choose_main_contract(instruments: List[dict], base_symbol: str) -> Optional[Tuple[str, int]]:
    candidates = []
    for inst in instruments:
        code = str(inst.get("code", "")).upper()
        if not code.startswith(base_symbol):
            continue
        suffix = code[len(base_symbol) :]
        if len(suffix) != 4 or not suffix.isdigit():
            continue
        market = int(inst.get("market", 0))
        candidates.append((code, market, int(suffix)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[2], reverse=True)
    return candidates[0][0], candidates[0][1]


def resolve_tdx_symbol(
    symbol: str,
    tdx_symbol: Optional[str],
    tdx_market: Optional[int],
    tdx_auto_main: bool,
    tdx_host: str,
    tdx_port: int,
    debug: bool,
) -> Tuple[str, int]:
    raw_symbol = (tdx_symbol or symbol).upper()
    market = tdx_market if tdx_market is not None else 0
    if not tdx_auto_main or not raw_symbol.isalpha():
        return raw_symbol, market
    try:
        from pytdx.exhq import TdxExHq_API
    except Exception:
        log_debug(debug, "未安装 pytdx，无法自动识别主力合约")
        return raw_symbol, market
    api = TdxExHq_API()
    if not connect_tdx(api, tdx_host, tdx_port, debug):
        return raw_symbol, market
    try:
        instruments = api.get_instrument_info(0, 10000) or []
    finally:
        api.disconnect()
    chosen = choose_main_contract(instruments, raw_symbol)
    if not chosen:
        log_debug(debug, f"未找到主力合约，使用默认合约: {raw_symbol}")
        return raw_symbol, market
    log_debug(debug, f"识别主力合约: {chosen[0]}")
    return chosen


def get_bars_tdx(
    symbol: str,
    period: str,
    count: int,
    tdx_symbol: Optional[str] = None,
    tdx_host: str = "119.147.212.81",
    tdx_port: int = 7727,
    tdx_market: Optional[int] = None,
    tdx_auto_main: bool = True,
    increment: bool = True,
    cache_file=None,
    increment_count: int = 200,
    increment_overlap: int = 20,
    required: int = 0,
    debug: bool = False,
    **_,
) -> Tuple[List[PriceBar], str]:
    used_symbol, market = resolve_tdx_symbol(
        symbol=symbol,
        tdx_symbol=tdx_symbol,
        tdx_market=tdx_market,
        tdx_auto_main=tdx_auto_main,
        tdx_host=tdx_host,
        tdx_port=tdx_port,
        debug=debug,
    )
    cache = load_bar_cache(cache_file) if increment and cache_file else {}
    primary_key = cache_key("tdx", used_symbol, period)
    cached_primary = bars_from_cache(cache.get(primary_key, [])) if increment else []
    fetch_count = (increment_count + increment_overlap) if cached_primary else count
    if len(cached_primary) < required:
        fetch_count = count
    bars = fetch_tdx_bars(
        symbol=used_symbol,
        period=period,
        count=fetch_count,
        host=tdx_host,
        port=tdx_port,
        market=market,
        debug=debug,
    )
    if increment:
        max_keep = max(count, required)
        bars = merge_bars(cached_primary, bars, max_keep)
        if cache_file:
            cache[primary_key] = bars_to_cache(bars)
            save_bar_cache(cache_file, cache)
    return bars, used_symbol
