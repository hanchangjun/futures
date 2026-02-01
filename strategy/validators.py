from typing import Dict, Any


def validate_context(context: Dict[str, Any]) -> None:
    """
    Validate that the context dictionary contains all required fields for 3B/3S analysis.

    Required keys:
    ['zd', 'zg', 'gg', 'dd', 'center_bars', 'leave_bar', 'retrace_bar',
     'volume_leave', 'volume_retrace', 'higher_tf_buy', 'lower_tf_buy',
     'higher_tf_sell', 'lower_tf_sell']

    Args:
        context: Dictionary containing market data and structure info.

    Raises:
        ValueError: If keys are missing.
    """
    required_keys = [
        "zd",
        "zg",
        "gg",
        "dd",
        "center_bars",
        "leave_bar",
        "retrace_bar",
        "volume_leave",
        "volume_retrace",
        "higher_tf_buy",
        "lower_tf_buy",
        "higher_tf_sell",
        "lower_tf_sell",
    ]

    missing_keys = [key for key in required_keys if key not in context]

    if missing_keys:
        raise ValueError(f"Missing required keys in context: {missing_keys}")
