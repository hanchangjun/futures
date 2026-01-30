from typing import List


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
