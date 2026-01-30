from typing import List, Optional, Tuple

from .base import (
    PriceBar,
    bars_from_cache,
    bars_to_cache,
    cache_key,
    load_bar_cache,
    log_debug,
    merge_bars,
    parse_float,
    parse_timestamp,
    save_bar_cache,
)


def resolve_tq_symbol(symbol: str, tq_symbol: Optional[str] = None) -> str:
    if tq_symbol:
        return tq_symbol
    raw_symbol = (symbol or "").upper()
    if raw_symbol == "RB":
        return "KQ.m@SHFE.rb"
    if raw_symbol == "FG":
        return "KQ.m@CZCE.FG"
    if raw_symbol.startswith("RB") and len(raw_symbol) == 6:
        return f"SHFE.rb{raw_symbol[2:]}"
    if raw_symbol.startswith("FG") and len(raw_symbol) == 6:
        year = raw_symbol[2:4]
        month = raw_symbol[4:6]
        if year.isdigit() and month.isdigit():
            return f"CZCE.FG{year[-1]}{month}"
        return f"CZCE.FG{raw_symbol[2:]}"
    return symbol


def fetch_tq_bars(
    symbol: str,
    period: str,
    count: int,
    username: Optional[str],
    password: Optional[str],
    timeout: int,
    wait_update_once: bool,
    debug: bool,
) -> List[PriceBar]:
    try:
        from tqsdk import TqApi, TqAuth
    except Exception:
        log_debug(debug, "未安装 tqsdk，无法通过该接口获取行情")
        return []
    if not username or not password:
        log_debug(debug, "tqsdk 需要账号密码，请设置 TQ_USERNAME/TQ_PASSWORD 或传入 --tq-username/--tq-password")
        return []
    duration_map = {
        "1m": 60, "1min": 60,
        "5m": 300, "5min": 300,
        "15m": 900, "15min": 900,
        "30m": 1800, "30min": 1800,
        "60m": 3600, "60min": 3600, "1h": 3600,
        "1d": 86400, "day": 86400,
    }
    duration = duration_map.get(period, 86400)
    api = None
    try:
        log_debug(debug, "tqsdk 初始化 TqApi")
        api = TqApi(auth=TqAuth(username, password))
        log_debug(debug, "tqsdk 请求 K 线序列")
        klines = api.get_kline_serial(symbol, duration_seconds=duration, data_length=count)
        if wait_update_once:
            log_debug(debug, "tqsdk 等待一次行情更新")
            try:
                api.wait_update(timeout=max(timeout, 1))
            except TypeError:
                api.wait_update()
        else:
            log_debug(debug, "tqsdk 跳过等待更新，直接读取历史K线")
        if len(klines) == 0:
            log_debug(debug, "tqsdk 拉取超时或无数据")
            return []
        log_debug(debug, f"tqsdk K线返回: {len(klines)}")
        bars: List[PriceBar] = []
        for _, row in klines.iterrows():
            open_v = parse_float(str(row.get("open", "")))
            high_v = parse_float(str(row.get("high", "")))
            low_v = parse_float(str(row.get("low", "")))
            close_v = parse_float(str(row.get("close", "")))
            if None in (open_v, high_v, low_v, close_v):
                continue
            vol_v = parse_float(str(row.get("volume", "0"))) or 0.0
            date_v = parse_timestamp(row.get("datetime"))
            bars.append(
                PriceBar(
                    date=date_v,
                    open=open_v,
                    high=high_v,
                    low=low_v,
                    close=close_v,
                    volume=vol_v,
                )
            )
        if bars and bars[0].date and bars[-1].date and bars[0].date > bars[-1].date:
            bars.reverse()
        log_debug(debug, f"tqsdk K线数量: {len(bars)}")
        return bars
    except Exception as exc:
        log_debug(debug, f"tqsdk 连接失败: {exc}")
        return []
    finally:
        if api:
            api.close()


def get_bars_tq(
    symbol: str,
    period: str,
    count: int,
    tq_symbol: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: int = 10,
    wait_update_once: bool = True,
    increment: bool = True,
    cache_file=None,
    increment_count: int = 200,
    increment_overlap: int = 20,
    required: int = 0,
    debug: bool = False,
    **_,
) -> Tuple[List[PriceBar], str]:
    used_symbol = resolve_tq_symbol(symbol, tq_symbol)
    cache = load_bar_cache(cache_file) if increment and cache_file else {}
    primary_key = cache_key("tq", used_symbol, period)
    cached_primary = bars_from_cache(cache.get(primary_key, [])) if increment else []
    fetch_count = (increment_count + increment_overlap) if cached_primary else count
    if len(cached_primary) < required:
        fetch_count = count
    log_debug(debug, f"tqsdk 准备拉取: {used_symbol} 周期 {period}")
    log_debug(debug, f"tqsdk 拉取根数: {fetch_count} 缓存根数: {len(cached_primary)}")
    bars = fetch_tq_bars(
        symbol=used_symbol,
        period=period,
        count=fetch_count,
        username=username,
        password=password,
        timeout=timeout,
        wait_update_once=wait_update_once,
        debug=debug,
    )
    if increment:
        max_keep = max(count, required)
        bars = merge_bars(cached_primary, bars, max_keep)
        if cache_file:
            cache[primary_key] = bars_to_cache(bars)
            save_bar_cache(cache_file, cache)
    return bars, used_symbol
