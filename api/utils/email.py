import smtplib
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from api.logger import get_logger

logger = get_logger(__name__)


def get_email_dsn(host, port, user, password, email, ssl=True):
    return f"{user}:{password}@{host}:{port}?email={email}&ssl={ssl}"


def check_ping(host, port, user, password, email, ssl=True):  # pragma: no cover
    dsn = get_email_dsn(host, port, user, password, email, ssl)
    if not (host and port and user and password and email):
        logger.debug("Checking ping failed: some parameters empty")
        return False
    try:
        server = smtplib.SMTP(host=host, port=port, timeout=2)
        if ssl:
            server.starttls()
        server.login(user, password)
        server.verify(email)
        server.quit()
        logger.debug(f"Checking ping successful for {dsn}")
        return True
    except OSError:
        logger.debug(f"Checking ping error for {dsn}\n{traceback.format_exc()}")
        return False


def send_mail(
    host, port, user, password, email, ssl, where, text, subject="Thank you for your purchase", use_html_templates=False
):  # pragma: no cover
    if not where:
        return
    message_obj = MIMEMultipart()
    message_obj["Subject"] = subject
    message_obj["From"] = email
    message_obj["To"] = where
    message_obj.attach(MIMEText(text, "html" if use_html_templates else "plain"))
    message = message_obj.as_string()
    server = smtplib.SMTP(host=host, port=port, timeout=2)
    if ssl:
        server.starttls()
    server.login(user, password)
    server.sendmail(email, where, message)
    server.quit()
