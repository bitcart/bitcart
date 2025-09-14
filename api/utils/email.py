import smtplib
import traceback
from dataclasses import dataclass
from email import utils as email_utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from api import models
from api.constants import DEFAULT_SENDMAIL_SUBJECT
from api.logging import get_logger
from api.schemas.misc import SMTPAuthMode

logger = get_logger(__name__)

# TODO: create a service?


@dataclass
class Email:
    host: str
    port: int
    user: str
    password: str
    address: str
    mode: str = SMTPAuthMode.STARTTLS

    use_html_templates: bool = False

    def is_enabled(self) -> bool:
        return bool(self.host and self.port and self.user and self.password and self.address)

    def __str__(self) -> str:
        return f"{self.user}:{self.password}@{self.host}:{self.port}?email={self.address}&mode={self.mode}"

    def init_smtp_server(self) -> smtplib.SMTP | smtplib.SMTP_SSL:  # pragma: no cover
        server: smtplib.SMTP | smtplib.SMTP_SSL
        if self.mode == SMTPAuthMode.SSL_TLS:
            server = smtplib.SMTP_SSL(host=self.host, port=self.port, timeout=5)
        else:
            server = smtplib.SMTP(host=self.host, port=self.port, timeout=5)
        if self.mode == SMTPAuthMode.STARTTLS:
            server.starttls()
        return server

    def check_ping(self) -> bool:  # pragma: no cover
        dsn = str(self)
        if not self.is_enabled():
            logger.debug("Checking ping failed: some parameters empty")
            return False
        try:
            with self.init_smtp_server() as server:
                server.login(self.user, self.password)
                server.verify(self.address)
            logger.debug(f"Checking ping successful for {dsn}")
            return True
        except OSError:
            logger.debug(f"Checking ping error for {dsn}\n{traceback.format_exc()}")
            return False

    def send_mail(
        self, where: str, text: str, subject: str = DEFAULT_SENDMAIL_SUBJECT, use_html_templates: bool = False
    ) -> None:  # pragma: no cover
        if not where:
            return
        message_obj = MIMEMultipart()
        message_obj["Subject"] = subject
        message_obj["From"] = self.address
        message_obj["To"] = where
        message_obj["Date"] = email_utils.formatdate()
        message_obj.attach(MIMEText(text, "html" if use_html_templates else "plain"))
        message = message_obj.as_string()
        with self.init_smtp_server() as server:
            server.login(self.user, self.password)
            server.sendmail(self.address, where, message)

    @classmethod
    def get_email(cls, model: Any) -> "Email":
        email_settings = model.email_settings
        return cls(
            email_settings.host,
            email_settings.port,
            email_settings.user,
            email_settings.password,
            email_settings.address,
            email_settings.auth_mode,
        )


class StoreEmail(Email):
    use_html_templates: bool

    @classmethod
    def get_email(cls, store: models.Store) -> Email:
        email = super().get_email(store)
        email.use_html_templates = store.checkout_settings.use_html_templates
        return email

    def send_mail(self, where: str, text: str, subject: str = DEFAULT_SENDMAIL_SUBJECT) -> None:  # type: ignore
        super().send_mail(where, text, subject, self.use_html_templates)
