from dataclasses import dataclass


@dataclass
class ThirdClassConfig:
    """
    Configuration for Third Class Signal (3B/3S)
    """

    leave_amplitude_ratio: float = 0.5  # Ratio of leaving bi amplitude to center height
    retrace_max_k: int = 3  # Note: User specified 3, though typically a Bi needs 5.
    # Treating this as a strict filter if user meant "bars in retrace < X"?
    # Or maybe "retrace_min_k"? Adhering to prompt name.
    retrace_zg_safe_ratio: float = 0.3  # Safe distance from ZG as % of center height
    max_duration_ratio: float = 2.0  # Retrace duration / Leaving duration
    min_center_segments: int = 3  # Minimum number of Bis in the center
