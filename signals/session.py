from datetime import datetime, time
from typing import List, Tuple


def _parse_time(value: str) -> time:
    parts = value.strip().split(":")
    hour = int(parts[0]) if parts else 0
    minute = int(parts[1]) if len(parts) > 1 else 0
    return time(hour=hour, minute=minute)


def is_trade_time(
    now: datetime,
    sessions: List[Tuple[str, str]],
) -> bool:
    current = now.time()
    for start_raw, end_raw in sessions:
        start = _parse_time(start_raw)
        end = _parse_time(end_raw)
        if start <= end and start <= current <= end:
            return True
    return False
