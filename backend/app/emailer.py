"""Отправка писем. С SMTP_HOST — через SMTP (в Docker это Mailpit), без него — в лог."""
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("fsp_talent.email")


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        log.warning("EMAIL (SMTP не настроен) to=%s subject=%s\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as s:
            s.send_message(msg)
    except OSError as e:  # почта не должна ронять регистрацию — ссылку можно запросить повторно
        log.error("Не удалось отправить письмо %s: %s", to, e)
