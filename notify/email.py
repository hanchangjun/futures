import smtplib
from email.message import EmailMessage
from typing import Iterable


def send_email(
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
    to_addrs: Iterable[str],
    subject: str,
    content: str,
) -> None:
    message = EmailMessage()
    message["From"] = username
    message["To"] = ",".join(to_addrs)
    message["Subject"] = subject
    message.set_content(content)
    with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)
