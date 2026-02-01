from typing import Protocol, Union
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# Using protocols to decouple from specific implementation classes if needed,
# but since the prompt asks for specific fields, we can define them here.
# The user's prompt implies we should be able to accept "list of center objects".
# Let's define Protocols for what we expect.

class TrendDirection(Enum):
    UP = "up"
    DOWN = "down"

class IQuantBi(Protocol):
    """Protocol for Bi (Stroke) used in quantification."""
    direction: Union[str, TrendDirection] # 'up' or 'down'
    start_time: datetime
    end_time: datetime
    
    # Fields for Divergence
    amplitude: float
    macd_area: float
    macd_diff_peak: float
    slope: float
    duration: float # or int (number of bars or time delta)

class IQuantCenter(Protocol):
    """Protocol for Center (ZhongShu) used in quantification."""
    gg: float # High High
    dd: float # Low Low
    start_time: datetime
    end_time: datetime
    count: int # K-line count
    # Indices are optional in protocol but recommended for accurate duration check
    start_index: int 
    end_index: int

# Also defining concrete dummy classes for testing/usage if needed, 
# or we just rely on the user passing objects that satisfy these.
# But for type hinting in our functions, we use these Protocols.
