import json
from pathlib import Path
from typing import Optional, Dict, Any

class SignalState:
    def __init__(self, file_path: Path):
        self.file_path = file_path

    def load(self) -> Optional[Dict[str, Any]]:
        """Load the last signal state from file."""
        if not self.file_path.exists():
            return None
        try:
            content = self.file_path.read_text(encoding="utf-8")
            if not content.strip():
                return None
            return json.loads(content)
        except Exception:
            return None

    def save(self, signal_data: Dict[str, Any]) -> None:
        """Save the current signal state to file."""
        try:
            self.file_path.write_text(
                json.dumps(signal_data, ensure_ascii=False, indent=2), 
                encoding="utf-8"
            )
        except Exception as e:
            # We don't want to crash if state saving fails, but it's good to know
            print(f"[WARNING] Failed to save signal state: {e}")

    def is_new(self, current_signal: Dict[str, Any]) -> bool:
        """
        Check if the current signal is new based on direction.
        Rule:
        - Direction changed -> New
        - Direction same -> Not New (deduplicated)
        """
        last_signal = self.load()
        
        # If no last signal, it's new
        if not last_signal:
            return True
            
        # Compare direction
        last_direction = last_signal.get("direction")
        current_direction = current_signal.get("direction")
        
        return last_direction != current_direction

    def should_notify(self, current_signal: Dict[str, Any], cooldown_bars: int) -> tuple[bool, str]:
        """
        Decide whether to notify based on direction change and cooldown windows.
        Inputs:
        - current_signal: payload dict that MUST contain 'direction' and SHOULD contain 'bar_index'.
          Optional fields: 'date'
        - cooldown_bars: number of bars to wait before re-notifying the same direction
        Returns:
        - (True, "OK") if notification is allowed
        - (False, "<reason>") if blocked (e.g., cooldown)
        """
        last_signal = self.load()
        # No last record -> allow immediately
        if not last_signal:
            return True, "首次通知"
        current_dir = current_signal.get("direction")
        last_dir = last_signal.get("direction")
        # Direction changed -> allow regardless of cooldown
        if current_dir != last_dir:
            return True, "方向变化"
        # Same direction -> check cooldown
        try:
            current_idx = int(current_signal.get("bar_index")) if current_signal.get("bar_index") is not None else None
        except Exception:
            current_idx = None
        try:
            last_idx = int(last_signal.get("last_notify_bar_index")) if last_signal.get("last_notify_bar_index") is not None else None
        except Exception:
            last_idx = None
        if current_idx is None or last_idx is None:
            # Missing indices -> conservatively block to avoid spamming
            return False, "缺少bar_index，已按冷却拦截"
        gap = max(0, current_idx - last_idx)
        if gap < cooldown_bars:
            return False, f"冷却中({gap}/{cooldown_bars})，已拦截"
        return True, "冷却已过"
