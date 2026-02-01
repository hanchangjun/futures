import logging
from typing import Tuple, Dict, Any, List

# Setup logger
logger = logging.getLogger(__name__)

class LevelValidator:
    """
    级别层级验证器
    负责验证本级别笔(Bi)是否足以构成次级别走势段(Segment)
    """
    
    # Constants for validation
    MIN_K_LINES = 3 # Minimum K-lines to form a valid structure (Sub-level segment proxy)
    
    @classmethod
    def validate(cls, bi, context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate if the Bi represents a valid sub-level structure.
        
        Args:
            bi: The Bi object (SimpleBi or equivalent)
            context: Strategy context containing bars, etc.
            
        Returns:
            (is_valid, debug_message)
        """
        # 1. Check K-line count (Proxy for sub-level structure in single timeframe)
        # bi.start_fx.index and bi.end_fx.index are indices in the merged K-line list (ChanBar)
        # We need to estimate the number of raw bars or merged bars.
        
        start_idx = bi.start_fx.index
        end_idx = bi.end_fx.index
        
        # Calculate covered bars (inclusive)
        k_count = abs(end_idx - start_idx) + 1
        
        if k_count < cls.MIN_K_LINES:
            msg = f"LevelValidation Failed: Bi length {k_count} < {cls.MIN_K_LINES}"
            # logger.debug(msg)
            return False, msg
            
        # 2. (Optional) Amplitude check could go here
        
        return True, f"LevelValidation Passed: Bi length {k_count}"
