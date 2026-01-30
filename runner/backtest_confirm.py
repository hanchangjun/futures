from collections import defaultdict
from typing import Any, Dict, List, Tuple, Optional

from .confirm import check_confirm

class ConfirmBacktester:
    def __init__(self, compute_func, atr_period: int, max_wait_bars: int):
        self.compute_func = compute_func
        self.atr_period = atr_period
        self.max_wait_bars = max_wait_bars

    def run(self, bars: List[Any], args: Any) -> Dict[str, Any]:
        total_signals = 0
        hits = 0
        fails = 0
        waits: List[int] = []
        wait_dist = defaultdict(int)

        pending: Optional[Dict[str, Any]] = None
        start_idx: Optional[int] = None

        for i in range(max(self.atr_period + 2, 1), len(bars)):
            subset = bars[: i + 1]
            sig = self.compute_func(subset, None, args)
            # Allow "strong" (dual resonance) and "normal" (single period valid) signals
            # "weak" signals (hands=0 or direction mismatch) are ignored
            strength = getattr(sig, "strength", "normal")
            
            # Check if it's a continuation of the current pending signal
            is_continuation = (pending is not None and pending["direction"] == sig.direction)

            if sig and strength in ("strong", "normal") and not is_continuation:
                if pending is not None and start_idx is not None:
                    fails += 1
                total_signals += 1
                pending = {
                    "symbol": getattr(args, "symbol", None),
                    "direction": sig.direction,
                    "entry": sig.entry,
                    "bar_index": i + 1,
                    "date": subset[-1].date.isoformat() if subset[-1].date else None,
                }
                start_idx = i

            if pending is not None and start_idx is not None:
                confirmed, last_close, last_atr, _ = check_confirm(subset, pending, self.atr_period)
                if confirmed:
                    hits += 1
                    wait = i - start_idx
                    waits.append(wait)
                    wait_dist[wait] += 1
                    pending = None
                    start_idx = None
                else:
                    if i - start_idx >= self.max_wait_bars:
                        fails += 1
                        pending = None
                        start_idx = None

        hit_rate = (hits / total_signals) if total_signals > 0 else 0.0
        avg_wait = (sum(waits) / len(waits)) if waits else 0.0
        return {
            "total_signals": total_signals,
            "hits": hits,
            "fails": fails,
            "hit_rate": round(hit_rate, 4),
            "avg_wait_bars": round(avg_wait, 2),
            "wait_distribution": dict(sorted(wait_dist.items())),
        }
