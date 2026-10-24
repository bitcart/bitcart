import contextlib
import ssl
import traceback
from collections.abc import AsyncGenerator
from email import utils as email_utils
from email.message import EmailMessage

import aiosmtplib
from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from api.exceptions import EmailSendError
from api.logging import get_logger
from api.schemas.misc import EmailSettings, SMTPAuthMode

logger = get_logger(__name__)

SMTP_TIMEOUT = 5
DELIVERABILITY_DNS_TIMEOUT = 5
TLS_CONTEXT = ssl.create_default_context()


class EmailService:
    @staticmethod
    def is_enabled(settings: EmailSettings) -> bool:
        return bool(settings.host and settings.port and settings.user and settings.password and settings.address)

    async def check_ping(self, settings: EmailSettings) -> bool:
        if not self.is_enabled(settings):
            logger.debug("Checking ping failed: some parameters empty")
            return False
        try:
            async with self._smtp_session(settings) as client:
                await client.vrfy(settings.address)
        except Exception:
            logger.debug(f"Checking ping error for {self._describe(settings)}\n{traceback.format_exc()}")
            return False
        logger.debug(f"Checking ping successful for {self._describe(settings)}")
        return True

    async def send(self, settings: EmailSettings, to: str, subject: str, body: str, html: bool = False) -> None:
        if not self.is_enabled(settings):
            raise EmailSendError("Email is not configured")
        try:
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = settings.address
            message["To"] = to
            message["Date"] = email_utils.formatdate()
            message.set_content(body, subtype="html" if html else "plain")
            async with self._smtp_session(settings) as client:
                await client.send_message(message)
        except Exception as e:
            raise EmailSendError(f"Failed to send email via {self._describe(settings)}: {e}") from e

    async def ensure_deliverable(self, address: str) -> None:
        try:
            await run_in_threadpool(validate_email, address, check_deliverability=True, timeout=DELIVERABILITY_DNS_TIMEOUT)
        except EmailNotValidError as e:
            raise HTTPException(422, str(e)) from None

    @staticmethod
    def _describe(settings: EmailSettings) -> str:
        return f"{settings.user}@{settings.host}:{settings.port} ({settings.auth_mode})"

    @staticmethod
    @contextlib.asynccontextmanager
    async def _smtp_session(settings: EmailSettings) -> AsyncGenerator[aiosmtplib.SMTP]:
        client = aiosmtplib.SMTP(
            hostname=settings.host,
            port=settings.port,
            username=settings.user,
            password=settings.password,
            use_tls=settings.auth_mode == SMTPAuthMode.SSL_TLS,
            start_tls=settings.auth_mode == SMTPAuthMode.STARTTLS,
            tls_context=TLS_CONTEXT,
            timeout=SMTP_TIMEOUT,
        )
        try:
            await client.connect()
            yield client
            with contextlib.suppress(Exception):
                await client.quit()
        finally:
            client.close()
