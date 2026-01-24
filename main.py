import argparse
import csv
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

DEFAULT_TDX_HOSTS = [
    "119.147.212.81",
    "119.147.212.80",
    "110.185.73.53",
    "110.185.73.54",
    "124.74.236.94",
    "180.153.18.170",
    "180.153.18.171",
]


@dataclass
class PriceBar:
    date: Optional[datetime]
    open: float
    high: float
    low: float
    close: float


@dataclass
class Signal:
    direction: str
    entry: float
    stop: float
    take_profit: Optional[float]
    support: Optional[float]
    resistance: Optional[float]
    hands: int
    risk: float
    reason: str


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


def find_column(row: dict, candidates: Iterable[str]) -> Optional[str]:
    for key in row.keys():
        normalized = key.strip().lower()
        for candidate in candidates:
            if normalized == candidate:
                return key
    for key in row.keys():
        normalized = key.strip().lower()
        for candidate in candidates:
            if candidate in normalized:
                return key
    return None


def log_debug(debug: bool, message: str) -> None:
    if debug:
        print(f"[DEBUG] {message}")


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


def detect_delimiter(sample: str) -> Optional[str]:
    delimiters = [",", "\t", ";", "|"]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=delimiters)
        return dialect.delimiter
    except Exception:
        for delimiter in delimiters:
            if delimiter in sample:
                return delimiter
    return None


def split_whitespace_row(row: str) -> List[str]:
    normalized = (
        row.replace("\u00a0", " ")
        .replace("\u3000", " ")
        .replace("\t", " ")
        .strip()
    )
    return [cell for cell in normalized.split() if cell]


def normalize_rows(rows: List[List[str]]) -> List[List[str]]:
    if not rows:
        return rows
    if all(len(row) == 1 for row in rows):
        merged = [row[0] for row in rows]
        if any("\t" in line for line in merged):
            return [line.split("\t") for line in merged]
        if any(" " in line for line in merged):
            return [split_whitespace_row(line) for line in merged]
    return rows


def read_csv_rows(csv_path: Path, debug: bool) -> Tuple[List[str], List[List[str]], Optional[str], Optional[str]]:
    encodings = ["utf-8-sig", "gbk", "utf-8"]
    last_error: Optional[Exception] = None
    for encoding in encodings:
        try:
            with csv_path.open("r", encoding=encoding, newline="") as f:
                sample = f.read(4096)
                delimiter = detect_delimiter(sample)
                f.seek(0)
                if delimiter:
                    reader = csv.reader(f, delimiter=delimiter)
                    rows = [row for row in reader if row]
                else:
                    rows = [split_whitespace_row(line) for line in f if line.strip()]
            rows = normalize_rows(rows)
            if not rows:
                return [], [], encoding, None
            if debug and all(len(row) == 1 for row in rows[:3]):
                log_debug(debug, f"首行内容: {rows[0][0]!r}")
            header = rows[0]
            data = rows[1:]
            log_debug(debug, f"读取文件: {csv_path} 编码: {encoding} 分隔符: {delimiter}")
            return header, data, encoding, delimiter
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return [], [], None, None


def is_header_row(header: List[str]) -> bool:
    if not header:
        return False
    candidates = {"date", "datetime", "open", "high", "low", "close", "日期", "时间", "开盘", "最高", "最低", "收盘"}
    for cell in header:
        cell_norm = cell.strip().lower()
        if cell_norm in candidates:
            return True
        for candidate in candidates:
            if candidate in cell_norm:
                return True
    return False


def read_csv_bars(csv_path: Path, debug: bool) -> List[PriceBar]:
    header, data_rows, encoding, delimiter = read_csv_rows(csv_path, debug)
    if not header and not data_rows:
        log_debug(debug, f"文件为空或无法读取: {csv_path}")
        return []
    if not is_header_row(header):
        found_header = False
        for idx, row in enumerate(data_rows):
            if is_header_row(row):
                header = row
                data_rows = data_rows[idx + 1 :]
                found_header = True
                log_debug(debug, f"跳过标题行，表头行索引: {idx + 1}")
                break
        if not found_header:
            data_rows = [header] + data_rows
            header = ["datetime", "open", "high", "low", "close", "volume", "amount"]
    rows = [dict(zip(header, row)) for row in data_rows if row]
    if not rows:
        return []
    sample = rows[0]
    date_col = find_column(sample, ["date", "datetime", "日期", "时间"])
    open_col = find_column(sample, ["open", "开盘"])
    high_col = find_column(sample, ["high", "最高"])
    low_col = find_column(sample, ["low", "最低"])
    close_col = find_column(sample, ["close", "收盘", "现价", "最新"])
    if not all([open_col, high_col, low_col, close_col]):
        log_debug(debug, f"列无法识别: {list(sample.keys())}")
        return []
    bars: List[PriceBar] = []
    for row in rows:
        open_v = parse_float(row.get(open_col, ""))
        high_v = parse_float(row.get(high_col, ""))
        low_v = parse_float(row.get(low_col, ""))
        close_v = parse_float(row.get(close_col, ""))
        if None in (open_v, high_v, low_v, close_v):
            continue
        date_v = parse_date(row.get(date_col, "")) if date_col else None
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
    log_debug(debug, f"有效K线数量: {len(bars)}")
    return bars


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
    period_map = {"1m": 0, "5m": 1, "15m": 2, "30m": 3, "60m": 4, "1d": 5}
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


def ema(values: List[float], period: int) -> List[float]:
    if not values or period <= 0:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return result


def atr(highs: List[float], lows: List[float], closes: List[float], period: int) -> List[float]:
    if len(highs) < 2 or period <= 0:
        return []
    trs = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if len(trs) < period:
        return []
    result = []
    first = sum(trs[:period]) / period
    result.append(first)
    for v in trs[period:]:
        result.append((result[-1] * (period - 1) + v) / period)
    padding = [result[0]] * (len(highs) - len(result))
    return padding + result


def compute_signal(
    bars: List[PriceBar],
    fast_period: int,
    slow_period: int,
    atr_period: int,
    stop_atr_multiplier: float,
    take_profit_multiplier: float,
    sr_lookback: int,
    equity: float,
    risk_pct: float,
    contract_multiplier: float,
) -> Optional[Signal]:
    if len(bars) < max(slow_period, atr_period) + 2:
        return None
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    fast = ema(closes, fast_period)
    slow = ema(closes, slow_period)
    if not fast or not slow:
        return None
    last_close = closes[-1]
    last_fast = fast[-1]
    last_slow = slow[-1]
    atr_series = atr(highs, lows, closes, atr_period)
    if not atr_series:
        return None
    last_atr = atr_series[-1]
    direction = "观望"
    if last_fast > last_slow and last_close > last_slow:
        direction = "多"
    elif last_fast < last_slow and last_close < last_slow:
        direction = "空"
    entry = last_close
    if direction == "多":
        stop = entry - last_atr * stop_atr_multiplier
    elif direction == "空":
        stop = entry + last_atr * stop_atr_multiplier
    else:
        return Signal(direction="观望", entry=entry, stop=entry, take_profit=None, support=None, resistance=None, hands=0, risk=0.0, reason="无趋势")
    stop_distance = abs(entry - stop)
    if stop_distance <= 0:
        return None
    if direction == "多":
        take_profit = entry + stop_distance * take_profit_multiplier
    else:
        take_profit = entry - stop_distance * take_profit_multiplier
    lookback = min(len(bars), max(sr_lookback, 2))
    recent = bars[-lookback:]
    support = min(b.low for b in recent) if recent else None
    resistance = max(b.high for b in recent) if recent else None
    risk_per_contract = stop_distance * contract_multiplier
    total_risk = equity * risk_pct
    hands = max(int(math.floor(total_risk / risk_per_contract)), 0)
    risk = hands * risk_per_contract
    reason = f"EMA{fast_period}/{slow_period}"
    return Signal(
        direction=direction,
        entry=entry,
        stop=stop,
        take_profit=take_profit,
        support=support,
        resistance=resistance,
        hands=hands,
        risk=risk,
        reason=reason,
    )


def resolve_contract_label(symbol: str) -> str:
    raw = symbol.strip()
    upper = raw.upper()
    lower = raw.lower()
    if lower == "kq.m@shfe.rb":
        return "螺纹钢主力合约"
    if lower == "kq.m@czce.fg":
        return "玻璃主力合约"
    if upper == "RB":
        return "螺纹钢主力合约"
    if upper == "FG":
        return "玻璃主力合约"
    def extract_suffix(code: str, prefix: str) -> Optional[str]:
        if code.startswith(prefix) and len(code) > len(prefix):
            suffix = code[len(prefix) :]
            if suffix.isdigit():
                return suffix
        return None
    for prefix, name in (("RB", "螺纹钢"), ("FG", "玻璃"), ("SHFE.RB", "螺纹钢"), ("CZCE.FG", "玻璃")):
        suffix = extract_suffix(upper, prefix)
        if suffix:
            return f"{name}{suffix}合约"
    return symbol


def format_signal(symbol: str, signal: Signal) -> str:
    risk_value = int(round(signal.risk))
    entry_value = int(round(signal.entry))
    stop_value = int(round(signal.stop))
    take_profit_value = int(round(signal.take_profit)) if signal.take_profit is not None else None
    support_value = int(round(signal.support)) if signal.support is not None else None
    resistance_value = int(round(signal.resistance)) if signal.resistance is not None else None
    extra_lines = ""
    if take_profit_value is not None:
        extra_lines += f"\n止盈：{take_profit_value}"
    if support_value is not None:
        extra_lines += f"\n支撑：{support_value}"
    if resistance_value is not None:
        extra_lines += f"\n压力：{resistance_value}"
    contract_label = resolve_contract_label(symbol)
    return (
        f"【{symbol} 波段信号】\n"
        f"合约：{contract_label}\n"
        f"方向：{signal.direction}\n"
        f"入场：{entry_value}\n"
        f"止损：{stop_value}\n"
        f"手数：{signal.hands}\n"
        f"风险：{risk_value}"
        f"{extra_lines}\n"
        f"依据：{signal.reason}"
    )


def signal_payload(symbol: str, signal: Signal, latest_date: Optional[datetime]) -> dict:
    return {
        "symbol": symbol,
        "direction": signal.direction,
        "entry": int(round(signal.entry)),
        "stop": int(round(signal.stop)),
        "take_profit": int(round(signal.take_profit)) if signal.take_profit is not None else None,
        "support": int(round(signal.support)) if signal.support is not None else None,
        "resistance": int(round(signal.resistance)) if signal.resistance is not None else None,
        "hands": signal.hands,
        "risk": int(round(signal.risk)),
        "reason": signal.reason,
        "date": latest_date.isoformat() if latest_date else None,
    }


def is_new_signal(signal: dict, state_file: Path) -> bool:
    if not state_file.exists():
        state_file.write_text(json.dumps(signal, ensure_ascii=False))
        return True
    try:
        last = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        last = None
    if signal != last:
        state_file.write_text(json.dumps(signal, ensure_ascii=False))
        return True
    return False


def notify(message: str, popup: bool, webhook: Optional[str]) -> None:
    print(message)
    if not popup:
        pass
    else:
        try:
            import tkinter
            from tkinter import messagebox

            root = tkinter.Tk()
            root.withdraw()
            messagebox.showinfo("交易信号", message)
            root.destroy()
        except Exception:
            pass
    if webhook:
        try:
            import json
            import urllib.request

            payload = json.dumps({"text": message}).encode("utf-8")
            req = urllib.request.Request(
                webhook,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as _:
                pass
        except Exception:
            pass


def latest_csv(csv_dir: Path) -> Optional[Path]:
    candidates = list(csv_dir.glob("*.csv"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


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


def resolve_tdx_symbol(args: argparse.Namespace) -> Tuple[str, int]:
    raw_symbol = (args.tdx_symbol or args.symbol).upper()
    market = args.tdx_market if args.tdx_market is not None else 0
    if not args.tdx_auto_main or not raw_symbol.isalpha():
        return raw_symbol, market
    try:
        from pytdx.exhq import TdxExHq_API
    except Exception:
        log_debug(args.debug, "未安装 pytdx，无法自动识别主力合约")
        return raw_symbol, market
    api = TdxExHq_API()
    if not connect_tdx(api, args.tdx_host, args.tdx_port, args.debug):
        return raw_symbol, market
    try:
        instruments = api.get_instrument_info(0, 10000) or []
    finally:
        api.disconnect()
    chosen = choose_main_contract(instruments, raw_symbol)
    if not chosen:
        log_debug(args.debug, f"未找到主力合约，使用默认合约: {raw_symbol}")
        return raw_symbol, market
    log_debug(args.debug, f"识别主力合约: {chosen[0]}")
    return chosen


def resolve_tq_symbol(args: argparse.Namespace) -> str:
    if args.tq_symbol:
        return args.tq_symbol
    raw_symbol = (args.symbol or "").upper()
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
    return raw_symbol


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
    duration_map = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "60m": 3600, "1d": 86400}
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
            date_v = parse_timestamp(row.get("datetime"))
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
        log_debug(debug, f"tqsdk K线数量: {len(bars)}")
        return bars
    except Exception as exc:
        log_debug(debug, f"tqsdk 连接失败: {exc}")
        return []
    finally:
        if api:
            api.close()


def compute_dual_signal(
    primary_bars: List[PriceBar],
    secondary_bars: Optional[List[PriceBar]],
    args: argparse.Namespace,
) -> Optional[Signal]:
    primary_signal = compute_signal(
        bars=primary_bars,
        fast_period=args.fast,
        slow_period=args.slow,
        atr_period=args.atr,
        stop_atr_multiplier=args.stop_mult,
        take_profit_multiplier=args.tp_mult,
        sr_lookback=args.sr_lookback,
        equity=args.equity,
        risk_pct=args.risk_pct,
        contract_multiplier=args.contract_multiplier,
    )
    if primary_signal is None:
        return None
    if secondary_bars is None:
        return primary_signal
    secondary_signal = compute_signal(
        bars=secondary_bars,
        fast_period=args.fast_2,
        slow_period=args.slow_2,
        atr_period=args.atr_2,
        stop_atr_multiplier=args.stop_mult_2,
        take_profit_multiplier=args.tp_mult_2,
        sr_lookback=args.sr_lookback_2,
        equity=args.equity,
        risk_pct=args.risk_pct,
        contract_multiplier=args.contract_multiplier,
    )
    if secondary_signal is None:
        return None
    if secondary_signal.direction != primary_signal.direction:
        return Signal(
            direction="观望",
            entry=secondary_signal.entry,
            stop=secondary_signal.stop,
            take_profit=secondary_signal.take_profit,
            support=secondary_signal.support,
            resistance=secondary_signal.resistance,
            hands=0,
            risk=0.0,
            reason="方向不一致",
        )
    return Signal(
        direction=secondary_signal.direction,
        entry=secondary_signal.entry,
        stop=secondary_signal.stop,
        take_profit=secondary_signal.take_profit,
        support=secondary_signal.support,
        resistance=secondary_signal.resistance,
        hands=secondary_signal.hands,
        risk=secondary_signal.risk,
        reason=f"{primary_signal.reason}+{secondary_signal.reason}",
    )


def resolve_csv_paths(args: argparse.Namespace) -> Tuple[Optional[Path], Optional[Path]]:
    if args.csv_path_daily or args.csv_path_60:
        return args.csv_path_daily, args.csv_path_60
    if args.csv_path:
        return args.csv_path, None
    latest = latest_csv(args.csv_dir)
    return latest, None


def load_bars(args: argparse.Namespace) -> Tuple[List[PriceBar], Optional[List[PriceBar]], str]:
    if args.source == "file":
        primary_path, secondary_path = resolve_csv_paths(args)
        if primary_path is None or not primary_path.exists():
            log_debug(args.debug, f"主文件不存在: {primary_path}")
            return [], None, args.symbol
        primary_bars = read_csv_bars(primary_path, args.debug)
        secondary_bars = read_csv_bars(secondary_path, args.debug) if secondary_path and secondary_path.exists() else None
        return primary_bars, secondary_bars, args.symbol
    if args.source == "tq":
        symbol = resolve_tq_symbol(args)
        username = args.tq_username or os.getenv("TQ_USERNAME")
        password = args.tq_password or os.getenv("TQ_PASSWORD")
        log_debug(args.debug, f"tqsdk 准备拉取: {symbol} 周期 {args.period}")
        cache = load_bar_cache(args.cache_file) if args.increment else {}
        primary_key = cache_key(args.source, symbol, args.period)
        cached_primary = bars_from_cache(cache.get(primary_key, []))
        required = max(args.slow, args.atr, args.slow_2, args.atr_2) + 5
        fetch_count = (args.increment_count + args.increment_overlap) if cached_primary else args.tq_count
        if len(cached_primary) < required:
            fetch_count = args.tq_count
        log_debug(args.debug, f"tqsdk 拉取根数: {fetch_count} 缓存根数: {len(cached_primary)}")
        primary_bars = fetch_tq_bars(
            symbol=symbol,
            period=args.period,
            count=fetch_count,
            username=username,
            password=password,
            timeout=args.tq_timeout,
            wait_update_once=not args.once,
            debug=args.debug,
        )
        if args.increment:
            primary_bars = merge_bars(cached_primary, primary_bars, max(args.tq_count, required))
            cache[primary_key] = bars_to_cache(primary_bars)
            save_bar_cache(args.cache_file, cache)
        secondary_bars = None
        if args.period_2:
            secondary_key = cache_key(args.source, symbol, args.period_2)
            cached_secondary = bars_from_cache(cache.get(secondary_key, [])) if args.increment else []
            secondary_fetch = (args.increment_count + args.increment_overlap) if cached_secondary else args.tq_count
            if len(cached_secondary) < required:
                secondary_fetch = args.tq_count
            log_debug(args.debug, f"tqsdk 副周期拉取: {args.period_2} 根数 {secondary_fetch} 缓存根数: {len(cached_secondary)}")
            secondary_bars = fetch_tq_bars(
                symbol=symbol,
                period=args.period_2,
                count=secondary_fetch,
                username=username,
                password=password,
                timeout=args.tq_timeout,
                wait_update_once=not args.once,
                debug=args.debug,
            )
            if args.increment:
                secondary_bars = merge_bars(cached_secondary, secondary_bars, max(args.tq_count, required))
                cache[secondary_key] = bars_to_cache(secondary_bars)
                save_bar_cache(args.cache_file, cache)
        return primary_bars, secondary_bars, symbol
    symbol, market = resolve_tdx_symbol(args)
    cache = load_bar_cache(args.cache_file) if args.increment else {}
    primary_key = cache_key(args.source, symbol, args.period)
    cached_primary = bars_from_cache(cache.get(primary_key, []))
    required = max(args.slow, args.atr, args.slow_2, args.atr_2) + 5
    fetch_count = (args.increment_count + args.increment_overlap) if cached_primary else args.tdx_count
    if len(cached_primary) < required:
        fetch_count = args.tdx_count
    primary_bars = fetch_tdx_bars(
        symbol=symbol,
        period=args.period,
        count=fetch_count,
        host=args.tdx_host,
        port=args.tdx_port,
        market=market,
        debug=args.debug,
    )
    if args.increment:
        primary_bars = merge_bars(cached_primary, primary_bars, max(args.tdx_count, required))
        cache[primary_key] = bars_to_cache(primary_bars)
        save_bar_cache(args.cache_file, cache)
    secondary_bars = None
    if args.period_2:
        secondary_key = cache_key(args.source, symbol, args.period_2)
        cached_secondary = bars_from_cache(cache.get(secondary_key, [])) if args.increment else []
        secondary_fetch = (args.increment_count + args.increment_overlap) if cached_secondary else args.tdx_count
        if len(cached_secondary) < required:
            secondary_fetch = args.tdx_count
        secondary_bars = fetch_tdx_bars(
            symbol=symbol,
            period=args.period_2,
            count=secondary_fetch,
            host=args.tdx_host,
            port=args.tdx_port,
            market=market,
            debug=args.debug,
        )
        if args.increment:
            secondary_bars = merge_bars(cached_secondary, secondary_bars, max(args.tdx_count, required))
            cache[secondary_key] = bars_to_cache(secondary_bars)
            save_bar_cache(args.cache_file, cache)
    return primary_bars, secondary_bars, symbol


def run_once(args: argparse.Namespace) -> Optional[str]:
    log_debug(args.debug, f"开始执行 once: source={args.source} symbol={args.symbol}")
    primary_bars, secondary_bars, used_symbol = load_bars(args)
    if not primary_bars:
        log_debug(args.debug, "主周期无有效K线")
        return None
    log_debug(args.debug, f"主周期K线数量: {len(primary_bars)}")
    signal = compute_dual_signal(primary_bars, secondary_bars, args)
    if signal is None or signal.direction == "观望":
        log_debug(args.debug, "无有效信号或处于观望")
        return None
    latest_date = primary_bars[-1].date if primary_bars else None
    payload = signal_payload(used_symbol, signal, latest_date)
    if not is_new_signal(payload, args.state_file):
        log_debug(args.debug, "信号未变化，跳过提醒")
        return None
    message = format_signal(used_symbol, signal)
    notify(message, args.popup, args.webhook)
    return message


def run_watch(args: argparse.Namespace) -> None:
    last_mtime: Optional[float] = None
    while True:
        if args.source == "file":
            primary_path, secondary_path = resolve_csv_paths(args)
            if primary_path and primary_path.exists():
                mtime = primary_path.stat().st_mtime
                if secondary_path and secondary_path.exists():
                    mtime = max(mtime, secondary_path.stat().st_mtime)
                if last_mtime is None or mtime > last_mtime:
                    last_mtime = mtime
                    run_once(args)
        else:
            run_once(args)
        time.sleep(args.interval)


def demo_signal() -> str:
    prices = [3500 + i * 2 for i in range(80)]
    bars = [
        PriceBar(
            date=None,
            open=v - 5,
            high=v + 5,
            low=v - 8,
            close=v,
        )
        for v in prices
    ]
    signal = compute_signal(
        bars=bars,
        fast_period=20,
        slow_period=60,
        atr_period=14,
        stop_atr_multiplier=2.0,
        take_profit_multiplier=2.0,
        sr_lookback=20,
        equity=50000,
        risk_pct=0.02,
        contract_multiplier=10,
    )
    if signal is None:
        return ""
    return format_signal("RB", signal)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, choices=["file", "tdx", "tq"], default="tq")
    parser.add_argument("--csv-dir", type=Path, default=Path("."))
    parser.add_argument("--csv-path", type=Path, default=None)
    parser.add_argument("--csv-path-daily", type=Path, default=None)
    parser.add_argument("--csv-path-60", type=Path, default=None)
    parser.add_argument("--symbol", type=str, default="RB")
    parser.add_argument("--period", type=str, default="1d")
    parser.add_argument("--period-2", type=str, default=None)
    parser.add_argument("--tdx-symbol", type=str, default=None)
    parser.add_argument("--tdx-host", type=str, default="119.147.212.81")
    parser.add_argument("--tdx-port", type=int, default=7727)
    parser.add_argument("--tdx-count", type=int, default=800)
    parser.add_argument("--tdx-market", type=int, default=None)
    parser.add_argument("--tdx-auto-main", action="store_true", default=True)
    parser.add_argument("--tq-symbol", type=str, default=None)
    parser.add_argument("--tq-count", type=int, default=800)
    parser.add_argument("--tq-username", type=str, default=None)
    parser.add_argument("--tq-password", type=str, default=None)
    parser.add_argument("--tq-timeout", type=int, default=10)
    parser.add_argument("--tq-check", action="store_true")
    parser.add_argument("--cache-file", type=Path, default=Path("bars_cache.json"))
    parser.add_argument("--increment-count", type=int, default=200)
    parser.add_argument("--increment-overlap", type=int, default=20)
    parser.add_argument("--no-increment", action="store_false", dest="increment", default=True)
    parser.add_argument("--equity", type=float, default=50000)
    parser.add_argument("--risk-pct", type=float, default=0.02)
    parser.add_argument("--contract-multiplier", type=float, default=10)
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=60)
    parser.add_argument("--atr", type=int, default=14)
    parser.add_argument("--stop-mult", type=float, default=2.0)
    parser.add_argument("--tp-mult", type=float, default=2.0)
    parser.add_argument("--sr-lookback", type=int, default=20)
    parser.add_argument("--fast-2", type=int, default=10)
    parser.add_argument("--slow-2", type=int, default=30)
    parser.add_argument("--atr-2", type=int, default=14)
    parser.add_argument("--stop-mult-2", type=float, default=2.0)
    parser.add_argument("--tp-mult-2", type=float, default=2.0)
    parser.add_argument("--sr-lookback-2", type=int, default=20)
    parser.add_argument("--state-file", type=Path, default=Path("signal_state.json"))
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--popup", action="store_true")
    parser.add_argument("--webhook", type=str, default=None)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.demo:
        print(demo_signal())
        return
    if args.tq_check:
        username = args.tq_username or os.getenv("TQ_USERNAME")
        password = args.tq_password or os.getenv("TQ_PASSWORD")
        print(f"TQ_USERNAME={'已设置' if username else '未设置'}")
        print(f"TQ_PASSWORD={'已设置' if password else '未设置'}")
        return
    if args.once:
        run_once(args)
        return
    run_watch(args)


if __name__ == "__main__":
    main()
