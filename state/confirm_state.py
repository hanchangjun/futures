import json
from pathlib import Path
from typing import Optional, Dict, Any

class ConfirmState:
    def __init__(self, file_path: Path):
        self.file_path = file_path

    def _load_all(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return {}
        try:
            text = self.file_path.read_text(encoding="utf-8")
            return json.loads(text) if text.strip() else {}
        except Exception:
            return {}

    def _save_all(self, data: Dict[str, Any]) -> None:
        try:
            self.file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get_pending(self) -> Optional[Dict[str, Any]]:
        data = self._load_all()
        pending = data.get("pending")
        return pending if isinstance(pending, dict) else None

    def save_pending(self, pending_signal: Dict[str, Any]) -> None:
        data = self._load_all()
        data["pending"] = {
            "symbol": pending_signal.get("symbol"),
            "direction": pending_signal.get("direction"),
            "entry": pending_signal.get("entry"),
            "bar_index": pending_signal.get("bar_index"),
            "date": pending_signal.get("date"),
        }
        self._save_all(data)

    def mark_confirmed(self, confirm_info: Dict[str, Any]) -> None:
        """
        confirm_info should include: symbol, direction, entry, confirm_bar_index, confirm_price, date
        """
        data = self._load_all()
        data["last_confirmed"] = {
            "symbol": confirm_info.get("symbol"),
            "direction": confirm_info.get("direction"),
            "entry": confirm_info.get("entry"),
            "confirm_bar_index": confirm_info.get("confirm_bar_index"),
            "confirm_price": confirm_info.get("confirm_price"),
            "date": confirm_info.get("date"),
        }
        # clear pending to ensure idempotency
        data.pop("pending", None)
        self._save_all(data)
