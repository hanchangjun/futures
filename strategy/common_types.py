from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class SignalResult:
    code: int  # 0: Invalid, 1: Valid (1st Class), 2: Valid (2nd Class), 3: Valid (3rd Class)
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def __bool__(self):
        return self.code > 0
