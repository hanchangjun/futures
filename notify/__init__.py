import os
from typing import Optional, Union, Any

from .console import send_console
from .wecom import send_wecom
from .types import NotificationLevel
from .styles import format_signal, format_error

def notify(message: str, level: Union[str, NotificationLevel] = "INFO", webhook_url: Optional[str] = None, **kwargs) -> None:
    # 1. Normalize Level
    if isinstance(level, str):
        try:
            level_enum = NotificationLevel(level.upper())
        except ValueError:
            level_enum = NotificationLevel.INFO
    else:
        level_enum = level

    # 2. Routing Logic
    
    # BLOCKED: Console only
    if level_enum == NotificationLevel.BLOCKED:
        send_console(f"[BLOCKED] {message}")
        return

    # DEBUG / INFO: Console only
    if level_enum in (NotificationLevel.DEBUG, NotificationLevel.INFO):
        send_console(f"[{level_enum.value}] {message}")
        return

    # SIGNAL / ERROR: WeCom (Markdown) -> Fallback to Console
    if level_enum in (NotificationLevel.SIGNAL, NotificationLevel.ERROR):
        webhook = webhook_url or os.getenv("WECOM_WEBHOOK_URL") or os.getenv("WECOM_WEBHOOK")
        
        # Prepare content and type
        content = message
        msg_type = "text"
        
        if level_enum == NotificationLevel.SIGNAL:
            # If kwargs are provided, use them to format the signal
            if kwargs:
                content = format_signal(kwargs)
                msg_type = "markdown"
            else:
                # If no structured data, just wrap the message in a header
                content = f"## 📢 交易信号\n{message}"
                msg_type = "markdown"
                
        elif level_enum == NotificationLevel.ERROR:
            content = format_error(message)
            msg_type = "markdown"

        # Send
        if webhook:
            try:
                send_wecom(webhook, content, msg_type=msg_type)
                # Also log to console for local visibility
                send_console(f"[{level_enum.value}] {message} >> WeCom")
                return
            except Exception as e:
                send_console(f"[WARNING] WeCom push failed: {e}")
                # Fallback to console
                send_console(f"[{level_enum.value}] {message}")
                return
        
        # No webhook, fallback to console
        send_console(f"[{level_enum.value}] {message}")
        return
