import asyncio
import contextlib
import functools
import socket
import ssl
import traceback
from collections.abc import AsyncGenerator, Awaitable, Callable
from email import utils as email_utils
from email.message import EmailMessage

import aiosmtplib
from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException
from outbound_guard import OutboundGuard
from starlette.concurrency import run_in_threadpool

from api import models
from api.exceptions import EmailSendError
from api.logging import get_logger
from api.schemas.misc import EmailSettings, SMTPAuthMode
from api.schemas.policies import Policy

logger = get_logger(__name__)

SMTP_TIMEOUT = 5
DELIVERABILITY_DNS_TIMEOUT = 5
TLS_CONTEXT = ssl.create_default_context()
OWNER_DENIAL_HINT = ". Server admins can allow it in the store owner's allowed internal hosts"

type Connect = Callable[[str, int], Awaitable[socket.socket]]


async def connect_directly(host: str, port: int) -> socket.socket:
    connection = asyncio.to_thread(socket.create_connection, (host, port), SMTP_TIMEOUT)
    return await asyncio.wait_for(connection, SMTP_TIMEOUT)


class Mailer:
    def __init__(self, settings: EmailSettings, connect: Connect) -> None:
        self.settings = settings
        self.connect = connect

    async def check_ping(self) -> bool:
        if not EmailService.is_enabled(self.settings):
            logger.debug("Checking ping failed: some parameters empty")
            return False
        try:
            async with self._smtp_session() as client:
                await client.vrfy(self.settings.address)
        except Exception:
            logger.debug(f"Checking ping error for {self._describe()}\n{traceback.format_exc()}")
            return False
        logger.debug(f"Checking ping successful for {self._describe()}")
        return True

    async def send(self, to: str, subject: str, body: str, html: bool = False) -> None:
        if not EmailService.is_enabled(self.settings):
            raise EmailSendError("Email is not configured")
        try:
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = self.settings.address
            message["To"] = to
            message["Date"] = email_utils.formatdate()
            message.set_content(body, subtype="html" if html else "plain")
            async with self._smtp_session() as client:
                await client.send_message(message)
        except Exception as e:
            raise EmailSendError(f"Failed to send email via {self._describe()}: {e}") from e

    def _describe(self) -> str:
        return f"{self.settings.user}@{self.settings.host}:{self.settings.port} ({self.settings.auth_mode})"

    @contextlib.asynccontextmanager
    async def _smtp_session(self) -> AsyncGenerator[aiosmtplib.SMTP]:
        settings = self.settings
        client = aiosmtplib.SMTP(
            hostname=settings.host,
            port=None,
            username=settings.user,
            password=settings.password,
            use_tls=settings.auth_mode == SMTPAuthMode.SSL_TLS,
            start_tls=settings.auth_mode == SMTPAuthMode.STARTTLS,
            tls_context=TLS_CONTEXT,
            timeout=SMTP_TIMEOUT,
        )
        sock = await self.connect(settings.host, settings.port)
        try:
            await client.connect(sock=sock)
            yield client
            with contextlib.suppress(Exception):
                await client.quit()
        finally:
            client.close()


class EmailService:
    @staticmethod
    def is_enabled(settings: EmailSettings) -> bool:
        return bool(settings.host and settings.port and settings.user and settings.password and settings.address)

    def for_store(self, store: models.Store, owner_hosts: list[str]) -> Mailer:
        guard = OutboundGuard(owner_hosts, denial_hint=OWNER_DENIAL_HINT)
        return Mailer(store.email_settings, functools.partial(guard.connect, timeout=SMTP_TIMEOUT))

    def for_server(self, policy: Policy) -> Mailer:
        return Mailer(policy.email_settings, connect_directly)

    async def ensure_deliverable(self, address: str) -> None:
        try:
            await run_in_threadpool(validate_email, address, check_deliverability=True, timeout=DELIVERABILITY_DNS_TIMEOUT)
        except EmailNotValidError as e:
            raise HTTPException(422, str(e)) from None
