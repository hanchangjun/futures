import requests
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class WeChatNotifier:
    """
    企业微信消息推送
    """
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
        # If no webhook provided, we can log only or look for env var
        # For now, we allow None and just log warning if try to send
    
    def send_text(self, content: str, mentioned_list: list = None) -> bool:
        """
        发送文本消息
        """
        if not self.webhook_url:
            logger.warning("WeChat webhook URL not set. Notification skipped: %s", content)
            return False
            
        headers = {'Content-Type': 'application/json'}
        data = {
            "msgtype": "text",
            "text": {
                "content": content,
                "mentioned_list": mentioned_list or []
            }
        }
        
        try:
            response = requests.post(self.webhook_url, headers=headers, json=data, timeout=5)
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get('errcode') == 0:
                    return True
                else:
                    logger.error("WeChat send failed: %s", res_json)
            else:
                logger.error("WeChat HTTP error: %s", response.status_code)
        except Exception as e:
            logger.error("WeChat request exception: %s", e)
            
        return False

    def send_order_notification(self, order: Dict[str, Any]):
        """
        发送订单通知
        """
        signal = order.get('signal')
        signal_type = signal.type if signal else 'Unknown'
        price = order.get('price')
        size = order.get('size')
        direction = order.get('type') # BUY/SELL
        
        emoji = "🟢" if direction == 'BUY' else "🔴"
        
        content = (
            f"{emoji} **交易指令生成**\n"
            f"-----------------------\n"
            f"方向: {direction}\n"
            f"类型: {signal_type}\n"
            f"价格: {price}\n"
            f"数量: {size}手\n"
            f"止损: {order.get('stop_loss')}\n"
            f"止盈: {order.get('take_profit')}\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        
        # Add score if available
        if signal and hasattr(signal, 'score'):
            content += f"评分: {signal.score:.1f}\n"
            
        self.send_text(content)
