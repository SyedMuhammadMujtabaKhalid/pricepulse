"""
PricePulse — Notification System
================================
Dispatch alerts to external systems (Console, Email).
"""

from abc import ABC, abstractmethod
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.core.logger import get_logger
from src.storage.models import Alert

log = get_logger(__name__)


class BaseNotifier(ABC):
    """Abstract strategy for dispatching alerts."""

    @abstractmethod
    def send(self, alert: Alert) -> bool:
        pass


class ConsoleNotifier(BaseNotifier):
    """Simple sink for development."""

    def send(self, alert: Alert) -> bool:
        log.info("notifier.console", severity=alert.severity, message=alert.message)
        return True


class SMTPNotifier(BaseNotifier):
    """Sends emails via SMTP."""

    def __init__(
        self, host: str, port: int, username: str, password: str, to_address: str
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.to_address = to_address

    def send(self, alert: Alert) -> bool:
        try:
            msg = MIMEMultipart()
            msg["From"] = self.username
            msg["To"] = self.to_address
            msg["Subject"] = f"[PricePulse] {alert.severity.upper()} Alert"

            body = f"Alert Type: {alert.alert_type}\nSeverity: {alert.severity}\n\n{alert.message}"
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(msg)

            log.info("notifier.smtp.success", alert_id=str(alert.id))
            return True
        except Exception as e:
            log.error("notifier.smtp.failed", error=str(e))
            return False


class TelegramNotifier(BaseNotifier):
    """Sends alerts via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, alert: Alert) -> bool:
        import httpx

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": f"🚨 [{alert.severity.upper()}] {alert.alert_type}\n{alert.message}",
                "parse_mode": "HTML",
            }
            response = httpx.post(url, json=payload, timeout=5.0)
            if response.status_code == 200:
                log.info("notifier.telegram.success", alert_id=str(alert.id))
                return True
            else:
                log.error(
                    "notifier.telegram.failed",
                    status=response.status_code,
                    body=response.text,
                )
                return False
        except Exception as e:
            log.error("notifier.telegram.error", error=str(e))
            return False


class DiscordWebhookNotifier(BaseNotifier):
    """Sends alerts via Discord Webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, alert: Alert) -> bool:
        import httpx

        try:
            payload = {
                "embeds": [
                    {
                        "title": f"🚨 PricePulse Alert [{alert.severity.upper()}]",
                        "description": alert.message,
                        "color": 15158332 if alert.severity == "critical" else 15105570,
                    }
                ]
            }
            response = httpx.post(self.webhook_url, json=payload, timeout=5.0)
            if response.status_code in (200, 204):
                log.info("notifier.discord.success", alert_id=str(alert.id))
                return True
            else:
                log.error(
                    "notifier.discord.failed",
                    status=response.status_code,
                    body=response.text,
                )
                return False
        except Exception as e:
            log.error("notifier.discord.error", error=str(e))
            return False


class NotificationDispatcher:
    def __init__(self, notifiers: list[BaseNotifier]):
        self.notifiers = notifiers

    def dispatch(self, alert: Alert) -> None:
        for notifier in self.notifiers:
            notifier.send(alert)
