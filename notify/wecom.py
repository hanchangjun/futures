from typing import Optional

import requests


def send_wecom(
    webhook_url: str,
    content: str,
    msg_type: str = "text",
) -> Optional[requests.Response]:
    payload = {"msgtype": msg_type}
    if msg_type == "markdown":
        payload["markdown"] = {"content": content}
    else:
        payload["text"] = {"content": content}
    return requests.post(webhook_url, json=payload, timeout=10)
