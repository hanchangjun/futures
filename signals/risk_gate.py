def allow_trade(
    enabled: bool,
    today_loss: float,
    max_daily_loss: float,
) -> bool:
    if not enabled:
        return False
    if today_loss >= max_daily_loss:
        return False
    return True
