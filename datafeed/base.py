import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class PriceBar:
    date: Optional[datetime]
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def parse_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def parse_date(value: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            pass
    return None


def parse_timestamp(value: object) -> Optional[datetime]:
    if value is None:
        return None
    try:
        if isinstance(value, datetime):
            return value
        ts = float(value)
        if ts > 10_000_000_000:
            ts = ts / 1_000_000_000
        return datetime.fromtimestamp(ts)
    except Exception:
        return None


def cache_key(source: str, symbol: str, period: str) -> str:
    return f"{source}:{symbol}:{period}"


def load_bar_cache(cache_file: Path) -> dict:
    if not cache_file.exists():
        return {}
    try:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_bar_cache(cache_file: Path, cache: dict) -> None:
    cache_file.write_text(json.dumps(cache, ensure_ascii=False))


def bars_to_cache(bars: List[PriceBar]) -> List[dict]:
    payload = []
    for bar in bars:
        payload.append(
            {
                "date": bar.date.isoformat() if bar.date else None,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
            }
        )
    return payload


def bars_from_cache(payload: List[dict]) -> List[PriceBar]:
    bars: List[PriceBar] = []
    for row in payload:
        date_raw = row.get("date")
        date_v = parse_date(date_raw) if isinstance(date_raw, str) else None
        if date_v is None and date_raw:
            date_v = parse_timestamp(date_raw)
        bars.append(
            PriceBar(
                date=date_v,
                open=float(row.get("open", 0)),
                high=float(row.get("high", 0)),
                low=float(row.get("low", 0)),
                close=float(row.get("close", 0)),
            )
        )
    return bars


def merge_bars(cached: List[PriceBar], fresh: List[PriceBar], max_keep: int) -> List[PriceBar]:
    merged = []
    seen = {}
    for bar in cached:
        if bar.date:
            seen[bar.date.isoformat()] = bar
        else:
            merged.append(bar)
    for bar in fresh:
        if bar.date:
            seen[bar.date.isoformat()] = bar
        else:
            merged.append(bar)
    merged.extend(sorted(seen.values(), key=lambda b: b.date or datetime.min))
    if len(merged) > max_keep:
        merged = merged[-max_keep:]
    return merged


def log_debug(debug: bool, message: str) -> None:
    if debug:
        print(f"[DEBUG] {message}")


def get_bars(
    source: str,
    symbol: str,
    period: str,
    count: int,
    **kwargs,
) -> Tuple[List[PriceBar], str]:
    source_norm = (source or "").lower()
    if source_norm == "file":
        from .file_feed import get_bars_file

        return get_bars_file(symbol=symbol, period=period, count=count, **kwargs)
    if source_norm == "db":
        from .db_feed import get_bars_db
        return get_bars_db(symbol=symbol, period=period, count=count, **kwargs)
    if source_norm == "tq":
        from .tq_feed import get_bars_tq

        return get_bars_tq(symbol=symbol, period=period, count=count, **kwargs)
    from .tdx_feed import get_bars_tdx

    return get_bars_tdx(symbol=symbol, period=period, count=count, **kwargs)
