import csv
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .base import PriceBar, log_debug, parse_date, parse_float


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
    header, data_rows, _, _ = read_csv_rows(csv_path, debug)
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


def latest_csv(csv_dir: Optional[Path]) -> Optional[Path]:
    if not csv_dir:
        return None
    candidates = list(csv_dir.glob("*.csv"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def select_csv_path(
    period: str,
    csv_dir: Optional[Path],
    csv_path: Optional[Path],
    csv_path_daily: Optional[Path],
    csv_path_60: Optional[Path],
) -> Optional[Path]:
    if csv_path_daily or csv_path_60:
        if period == "60m":
            return csv_path_60
        return csv_path_daily
    if csv_path:
        return csv_path
    return latest_csv(csv_dir)


def get_bars_file(
    symbol: str,
    period: str,
    count: int,
    csv_dir: Optional[Path] = None,
    csv_path: Optional[Path] = None,
    csv_path_daily: Optional[Path] = None,
    csv_path_60: Optional[Path] = None,
    debug: bool = False,
    **_,
) -> Tuple[List[PriceBar], str]:
    csv_file = select_csv_path(period, csv_dir, csv_path, csv_path_daily, csv_path_60)
    if csv_file is None or not csv_file.exists():
        log_debug(debug, f"主文件不存在: {csv_file}")
        return [], symbol
    bars = read_csv_bars(csv_file, debug)
    return bars, symbol
